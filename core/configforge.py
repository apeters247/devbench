#!/usr/bin/env python3
"""ConfigForge — Multi-format config file converter.
Converts between JSON, JSONC, YAML, TOML, XML, CSV, INI, .env, HCL, .properties.
Preserves comments. Offline. Batch capable.
"""
import csv
import io
import json
import math
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

# JSON metadata key for carrying YAML comments through JSON intermediate.
# The prefix can be overridden via the DEVBENCH_META_PREFIX env var to avoid
# collisions with real keys in the data. Default: __cf_ (distinctive but short).
_CF_PREFIX = os.environ.get("DEVBENCH_META_PREFIX", "__cf_")
_COMMENT_META_KEY = f"{_CF_PREFIX}comments__"
_COMMENT_DATA_KEY = f"{_CF_PREFIX}data__"
# JSON metadata key for carrying YAML blank-line positions through JSON.
# Blank lines in YAML are structural (they separate logical blocks), so they
# are preserved through the conversion pipeline just like comments. This is the
# fix for yq#515 — the most-voted unresolved issue in yq.
_BLANK_META_KEY = f"{_CF_PREFIX}blanks__"

# ── Optional imports (graceful fallback) ──
HAS_YAML = False
HAS_RUAMEL_YAML = False
HAS_TOML = False
HAS_XML = False
HAS_HCL = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    pass

try:
    from ruamel.yaml import YAML as RuamelYAML
    HAS_RUAMEL_YAML = True
except ImportError:
    pass

try:
    import hcl2
    HAS_HCL = True
except ImportError:
    HAS_HCL = False

try:
    import tomllib
    HAS_TOML = True
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
        HAS_TOML = True
    except ImportError:
        pass

try:
    import xml.etree.ElementTree as ET
    HAS_XML = True
except ImportError:
    pass

HAS_JSONSCHEMA = False
try:
    import jsonschema as _jsonschema_mod
    HAS_JSONSCHEMA = True
except ImportError:
    pass

import configparser
from collections import OrderedDict


def _is_escaped(line: str, pos: int) -> bool:
    """Return True if char at `pos` is preceded by an odd number of backslashes,
    i.e., the character is escaped rather than literal."""
    if pos == 0:
        return False
    bs = 0
    i = pos - 1
    while i >= 0 and line[i] == "\\":
        bs += 1
        i -= 1
    return bs % 2 == 1


def _count_delims_outside_quotes(line: str, delim: str) -> int:
    """Count how many `delim` characters appear outside string quotes."""
    count = 0
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch in ('"', "'"):
            # Skip escaped quotes — don't toggle in_quotes
            if _is_escaped(line, i):
                i += 1
                continue
            in_quotes = not in_quotes
        elif ch == delim and not in_quotes:
            count += 1
        i += 1
    return count


# ── Comment Preservation (YAML + INI) ──
_COMMENT_CACHE = {}


def _yaml_find_comment(line: str) -> int:
    """Return the index of the '#' that starts a YAML comment on `line`,
    or -1 if there is none.

    Honours the real YAML rule: a '#' opens a comment only when it is outside
    quotes AND is at the start of the line or preceded by whitespace. This is
    why `url: http://x#frag` has no comment, `color: "#fff"  # c` keeps only
    the trailing `# c`, and scanning never stops at the first '#' it sees."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == '"' and not in_single:
            # Skip escaped quotes (\") — don't toggle in_double
            if _is_escaped(line, i):
                continue
            in_double = not in_double
        elif ch == "'" and not in_double:
            # Skip escaped single quotes (\') — don't toggle in_single
            if _is_escaped(line, i):
                continue
            in_single = not in_single
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or line[i - 1] in " \t":
                return i
    return -1


def _yaml_unquote(s: str) -> str:
    """Strip a single pair of matching surrounding quotes, for comparing a
    list item's source text against its (possibly re-quoted) serialized form."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def _build_key_paths(lines):
    """Build a dict mapping line index -> (full_path, indent, key) for every
    key:value line, respecting YAML indentation hierarchy.

    Returns: {line_index: {"path": "parent.child.key", "indent": N, "key": "key"}, ...}
    """
    indent_stack = []  # [(indent, key), ...]
    result = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue

        indent = len(line) - len(line.lstrip())

        # Pop stack entries that are at the same or deeper indent (siblings or ancestors)
        while indent_stack and indent_stack[-1][0] >= indent:
            indent_stack.pop()

        # Extract key before ':', respecting quoted keys that contain colons.
        # A key like `"my:key": value` must not be truncated at the colon
        # inside the quotes.
        head = None
        if stripped[0:1] == '"':
            close = 1
            while close < len(stripped):
                if stripped[close] == '"' and not _is_escaped(stripped, close):
                    break
                close += 1
            if close > 1 and close < len(stripped):
                head = stripped[1:close]
        elif stripped[0:1] == "'":
            close = 1
            while close < len(stripped):
                if stripped[close] == "'" and not _is_escaped(stripped, close):
                    break
                close += 1
            if close > 1 and close < len(stripped):
                head = stripped[1:close]
        if head is None:
            head = stripped.split(":", 1)[0].strip()

        if head:
            path_parts = [k for _, k in indent_stack]
            path_parts.append(head)
            full_path = ".".join(path_parts)
            result[i] = {"path": full_path, "indent": indent, "key": head}
            indent_stack.append((indent, head))
    return result


def _extract_yaml_comments(text: str) -> list:
    """Extract # comments from YAML text, preserving their full key path context."""
    lines = text.split("\n")

    # Build key-path map for the source lines
    key_paths = _build_key_paths(lines)

    # For standalone comments between keys at a given indent level, track the
    # last seen key at each indent level so we can associate orphan comments.
    # key by indent level -> most recent key path before the comment
    last_key_at_indent = {}  # indent -> path
    for li in sorted(key_paths):
        indent = key_paths[li]["indent"]
        last_key_at_indent[indent] = key_paths[li]["path"]

    comments = []
    for i, line in enumerate(lines):
        ci = _yaml_find_comment(line)
        if ci < 0:
            continue
        before = line[:ci]
        is_inline = bool(before.strip())
        comment_text = line[ci + 1:].strip()
        indent = len(line) - len(line.lstrip())
        key = None
        list_item = None
        full_path = None

        if is_inline:
            head = before.strip()
            if head.startswith("-"):
                # List item (no `key:`) — anchor the comment on the item value.
                list_item = head[1:].strip()
            elif ":" in head:
                key = head.split(":", 1)[0].strip()
                if key and ((key.startswith('"') and key.endswith('"')) or
                            (key.startswith("'") and key.endswith("'"))):
                    key = key[1:-1]
                # Use the key_paths map to get the full path
                if i in key_paths:
                    full_path = key_paths[i]["path"]
        else:
            # Block-level comment: find the NEXT key at the same or deeper indent
            # If there's a key_paths entry for this exact line, use it
            if i in key_paths:
                key = key_paths[i]["key"]
                full_path = key_paths[i]["path"]
            else:
                # Comment on its own line before a key: find next key at this indent
                for li in sorted(key_paths):
                    if li > i and key_paths[li]["indent"] >= indent:
                        key = key_paths[li]["key"]
                        full_path = key_paths[li]["path"]
                        break
        comments.append({
            "line": i, "key": key, "text": comment_text,
            "is_inline": is_inline, "indent": indent,
            "list_item": list_item, "path": full_path,
        })
    return comments


def _reinsert_yaml_comments(yaml_text: str, comments: list) -> str:
    """Reinsert extracted comments into YAML output, matching by full key path
    and indentation to handle deeply nested keys with the same name."""
    if not comments:
        return yaml_text
    lines = yaml_text.split("\n")

    # Build key-path map for the output lines
    out_key_paths = _build_key_paths(lines)

    # Reverse map: path -> list of line indices (handle duplicate paths)
    path_to_lines = {}
    for li, info in out_key_paths.items():
        p = info["path"]
        if p not in path_to_lines:
            path_to_lines[p] = []
        path_to_lines[p].append(li)

    # Separate comments by type
    standalone = [c for c in comments
                  if c["key"] is None and not c.get("list_item") and not c.get("path")]
    path_keyed = [c for c in comments if c.get("path") is not None]
    key_only = [c for c in comments if c["key"] is not None and not c.get("path")]
    list_items = [c for c in comments if c.get("list_item") is not None]

    # First pass: standalone comments (no key context) at top
    header_pos = 0
    for c in standalone:
        if not c["is_inline"]:
            indent = " " * c.get("indent", 0)
            lines.insert(header_pos, f"{indent}# {c['text']}")
            header_pos += 1

    # Rebuild path_to_lines after standalone insertion shifted line indices
    if header_pos > 0:
        out_key_paths = _build_key_paths(lines)
        path_to_lines = {}
        for li, info in out_key_paths.items():
            p = info["path"]
            if p not in path_to_lines:
                path_to_lines[p] = []
            path_to_lines[p].append(li)

    # Track which lines have had comments inserted, to avoid double-insertion
    inserted_set = set()

    # Second pass: comments with full path — most reliable
    # Process block comments first, then inline
    path_block = [c for c in path_keyed if not c["is_inline"]]
    path_inline = [c for c in path_keyed if c["is_inline"]]

    # Group block comments by path, preserving original order
    path_block_groups = OrderedDict()
    for c in path_block:
        p = c["path"]
        if p not in path_block_groups:
            path_block_groups[p] = []
        path_block_groups[p].append(c)

    # Insert ALL block comments for a path as a stack before the first occurrence
    path_already_serviced = set()
    for p, comments_for_path in path_block_groups.items():
        if p in path_to_lines and path_to_lines[p]:
            li = path_to_lines[p][0]
            # Compute indent for the FIRST matching path's indent level
            target_indent = comments_for_path[0].get("indent", 0)
            # If there's an exact indent match in the output key, use its indent
            for out_li, info in out_key_paths.items():
                if info["path"] == p:
                    target_indent = info["indent"]
                    break
            # Insert all comments for this path in reverse order so the first
            # comment ends up first visually. Each insert goes at the same `li`
            # (before the key line); the first-inserted (last in original order)
            # gets shifted down by subsequent inserts.
            for c in reversed(comments_for_path):
                indent = " " * target_indent
                lines.insert(li, f"{indent}# {c['text']}")
            path_already_serviced.add(p)
            # Shift all line tracking by the number of inserted lines
            shift = len(comments_for_path)
            new_ptl = {}
            for pp, ll_list in path_to_lines.items():
                new_ptl[pp] = [x + shift if x >= li else x for x in ll_list]
            path_to_lines = new_ptl
            inserted_set = {x + shift if x >= li else x for x in inserted_set}

    # Remaining path_block comments that didn't match a path -> group by indent level
    # and insert at the top of their section
    remaining_block = [c for c in path_block if c["path"] not in path_already_serviced]
    if remaining_block:
        # Insert near the top as contextual header
        for c in remaining_block:
            indent = " " * c.get("indent", 0)
            lines.insert(0, f"{indent}# {c['text']}")

    for c in path_inline:
        p = c["path"]
        if p in path_to_lines:
            for li in path_to_lines[p]:
                if li < len(lines) and _yaml_find_comment(lines[li]) < 0:
                    lines[li] = lines[li] + f"  # {c['text']}"
                    inserted_set.add(li)
                    break

    # Third pass: fallback for key-only comments (no path info — legacy)
    # These use leaf-key matching with indentation hints
    keyed_block = [c for c in key_only if not c["is_inline"]]
    keyed_inline = [c for c in key_only if c["is_inline"]]

    # For key-only comments, try to find matching lines that haven't been used
    for c in keyed_block:
        target_key = c["key"]
        target_indent = c.get("indent", 0)
        lines_to_check = sorted(out_key_paths.keys())
        for li in lines_to_check:
            if li in inserted_set:
                continue
            info = out_key_paths[li]
            if info["key"] == target_key and info["indent"] == target_indent:
                indent = " " * target_indent
                lines.insert(li, f"{indent}# {c['text']}")
                inserted_set.add(li)
                # Shift
                new_ptl = {}
                for pp, ll_list in path_to_lines.items():
                    new_ptl[pp] = [x + 1 if x >= li else x for x in ll_list]
                path_to_lines = new_ptl
                inserted_set = {x + 1 if x >= li else x for x in inserted_set}
                break

    for c in keyed_inline:
        target_key = c["key"]
        for li in sorted(out_key_paths.keys()):
            if li in inserted_set:
                continue
            info = out_key_paths[li]
            if info["key"] == target_key:
                if li < len(lines) and _yaml_find_comment(lines[li]) < 0:
                    lines[li] = lines[li] + f"  # {c['text']}"
                    inserted_set.add(li)
                    break

    # Fourth pass: inline comments on list items, anchored by item value.
    for c in list_items:
        anchor = _yaml_unquote(c["list_item"])
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("-") or i in inserted_set:
                continue
            rest = stripped[1:].strip()
            if _yaml_unquote(rest) == anchor and _yaml_find_comment(line) < 0:
                lines[i] = line + f"  # {c['text']}"
                inserted_set.add(i)
                break

    # Final pass: any remaining orphan inline comments that weren't inserted
    # (block comments were already handled above). Track what was inserted.
    comment_texts_inserted = set()
    for l in lines:
        ci = _yaml_find_comment(l)
        if ci >= 0:
            comment_texts_inserted.add(l[ci+1:].strip())
    orphan_inline = [c for c in path_inline
                     if c.get("text") not in comment_texts_inserted]
    if orphan_inline:
        # Insert as a small header note rather than silently dropping
        top_indent = 0
        lines.insert(0, f"# Inline comments not re-inserted ({len(orphan_inline)}):")
        for c in orphan_inline[:5]:
            lines.insert(1, f"#   {c.get('path','?' )}: {c['text'][:80]}")

    return "\n".join(lines)


def _yaml_context_lines(lines: list, lineno: int, col: int = None, radius: int = 2) -> str:
    """Return an annotated multi-line block centred on *lineno* (1-based).

    Shows up to *radius* lines before and after the error line, each prefixed
    with its line number.  The error line is marked with '→'; others with ' '.
    An optional column pointer is appended on a separate line.
    """
    n = len(lines)
    start = max(1, lineno - radius)
    end = min(n, lineno + radius)
    block = []
    for i in range(start, end + 1):
        marker = "→" if i == lineno else " "
        block.append(f"  {marker} {i:4d}: {lines[i - 1]}")
    if col is not None and lineno <= n:
        # prefix width: "  →  NNN: " = 10 chars; then col spaces to reach the caret
        block.append(" " * (col + 9) + "^")
    return "\n".join(block)


def _yaml_find_indent_source(lines: list, error_lineno: int) -> int:
    """Scan backward from *error_lineno* (1-based) for the likely misindented line.

    PyYAML reports where parsing *failed*, not where the block was misindented.
    For example an array item indented too deeply will cause the parser to fail
    at the next mapping key — which is the wrong line for the user to fix.

    Walk back up to 15 non-blank lines and return the first line whose
    indentation is deeper than the error line's indent (the probable offender).
    Returns *error_lineno* when no better candidate is found.
    """
    if error_lineno <= 1 or error_lineno > len(lines):
        return error_lineno
    err_line = lines[error_lineno - 1]
    err_indent = len(err_line) - len(err_line.lstrip())
    for i in range(error_lineno - 2, max(-1, error_lineno - 16), -1):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent > err_indent:
            return i + 1  # 1-based
    return error_lineno


def _yaml_error_message(exc: "yaml.YAMLError", text: str) -> str:
    """Translate a raw yaml.YAMLError into an actionable error message.

    Covers the most common confusing cases:
    - Scanner/ComposerError on '*foo' or '&foo' tokens (alias/anchor misparse)
    - "could not find expected ':'" — indentation/missing-colon key error
    - "mapping values are not allowed" — key indented at wrong block level
    - Tab character in indentation
    - Duplicate anchor name

    Multi-line numbered context is shown for all errors so users can see
    surrounding lines rather than just the exact failure point.
    """
    raw = str(exc)
    lines = text.splitlines()

    problem_mark = getattr(exc, "problem_mark", None)
    context_mark = getattr(exc, "context_mark", None)

    def _loc(m):
        """Return (location_string, excerpt_block) for a mark object."""
        if not m:
            return "", ""
        ln = m.line + 1
        co = m.column + 1
        loc = f" (line {ln}, column {co})"
        ex = "\n" + _yaml_context_lines(lines, ln, co) if 1 <= ln <= len(lines) else ""
        return loc, ex

    p_context, p_excerpt = _loc(problem_mark or context_mark)

    # For "could not find expected ':'" the context_mark holds the actual problem key;
    # problem_mark only shows where the scanner gave up (usually a later line).
    c_context, c_excerpt = _loc(context_mark) if context_mark else (p_context, p_excerpt)

    # --- Alias/anchor ---
    if "could not find expected" in raw or "found undefined alias" in raw:
        problem = getattr(exc, "problem", "")
        if "alias" in raw.lower() or "*" in problem:
            return (
                f"YAML alias error{p_context}: an unquoted value starts with '*' "
                f"and was parsed as an alias reference but the anchor name is "
                f"invalid or undefined.{p_excerpt}\n"
                f"  Fix: quote the value (e.g. '*.html' → \"'*.html'\") or "
                f"define the anchor with '&name' before referencing it with '*name'."
            )

        # "could not find expected ':'" — a key is missing its colon or is wrongly indented.
        # context_mark already points at the problematic key; no backward scan needed.
        return (
            f"YAML indentation error{c_context}: a key is missing its ':' separator "
            f"— check that this line is properly indented and followed by a colon."
            f"{c_excerpt}\n"
            f"  Fix: add ':' after the key or align its indentation with its parent "
            f"block. Use spaces, not tabs."
        )

    if "alias" in raw.lower() and "anchor" in raw.lower():
        return (
            f"YAML anchor/alias error{p_context}: an anchor name may contain only "
            f"letters, digits, hyphens, underscores, and colons.{p_excerpt}\n"
            f"  Fix: quote any value that starts with '*' or '&', "
            f"e.g. change  key: *.html  to  key: \"*.html\"."
        )

    # --- Scanner errors ---
    if "scanner" in type(exc).__name__.lower() or "scanner" in raw.lower():
        problem = getattr(exc, "problem", "")

        # Special character (* or &) in a value position → anchor/alias hint
        if "*" in problem or "&" in problem or "special character" in raw:
            return (
                f"YAML syntax error{p_context}: a value contains a special character "
                f"('*' or '&') that YAML reserved for anchors and aliases.{p_excerpt}\n"
                f"  Fix: wrap the value in quotes, e.g. \"*.html\" or '*.html'."
            )

        # Mapping key at the wrong indentation level
        if "mapping values are not allowed" in raw:
            pm_lineno = problem_mark.line + 1 if problem_mark else None
            source_line = _yaml_find_indent_source(lines, pm_lineno) if pm_lineno else pm_lineno
            hint = ""
            if source_line and source_line != pm_lineno:
                hint = (
                    f"\n  Note: this key may have been indented under line {source_line}:\n"
                    + _yaml_context_lines(lines, source_line, radius=1)
                )
            return (
                f"YAML indentation error{p_context}: a mapping key ':' appears at "
                f"the wrong indentation level.{p_excerpt}{hint}\n"
                f"  Fix: align this key with its parent block. "
                f"Use consistent spaces (not tabs)."
            )

    # --- Tab character ---
    if "found character '\\t'" in raw or "tab" in raw.lower():
        return (
            f"YAML indentation error{p_context}: YAML does not allow tab characters "
            f"for indentation — use spaces only.{p_excerpt}\n"
            f"  Fix: replace tabs with spaces (e.g. expand-tabs in your editor)."
        )

    # --- Duplicate anchor ---
    if "duplicate" in raw.lower() and "anchor" in raw.lower():
        return (
            f"YAML anchor error{p_context}: the same anchor name is defined more "
            f"than once. Anchor names must be unique within a document.{p_excerpt}\n"
            f"  Fix: rename one of the duplicate anchors."
        )

    # --- Jinja/Helm template syntax ({{ var }}) ---
    if "unhashable" in raw.lower() and _has_template_syntax(text):
        return (
            f"YAML parse error{p_context}: a value containing '{{{{ ... }}}}' template "
            f"syntax was interpreted as a nested YAML mapping.{p_excerpt}\n"
            f"  Fix: quote the value, e.g.  key: '{{{{ var }}}}'  or use --template-safe."
        )

    # Generic YAML error with multi-line location context
    return f"YAML parse error{p_context}: {raw}{p_excerpt}"


def _has_template_syntax(text: str) -> bool:
    """Return True if text contains Jinja/Helm/Ansible template markers."""
    return bool(re.search(r"\{\{|\{%|\{#", text))


def _quote_template_values(text: str) -> str:
    """Pre-quote unquoted Jinja/Helm template expressions so PyYAML can parse them.

    Handles the yq#1126 / yq#2270 complaint: YAML files containing values like
      key: {{ var }}
      host: {{ domain }}-api.example.com
    fail to parse because PyYAML treats {{ as a flow-mapping start.
    This function single-quotes such values so they survive round-trip parsing.
    """
    result_lines = []
    for line in text.split("\n"):
        if "{{" not in line and "{%" not in line and "{#" not in line:
            result_lines.append(line)
            continue
        # Only rewrite key: value lines where the value is unquoted
        m = re.match(r"^(\s*(?:[^:#\s][^:]*)?:\s*)(.+)$", line)
        if m:
            prefix = m.group(1)
            value = m.group(2).rstrip()
            # Skip if already quoted or a comment
            if value and value[0] not in ("'", '"', "#"):
                escaped = value.replace("'", "''")
                result_lines.append(f"{prefix}'{escaped}'")
                continue
        result_lines.append(line)
    return "\n".join(result_lines)


def _make_yaml12_loader():
    """Return a SafeLoader subclass with YAML 1.2 boolean rules.

    YAML 1.1 (PyYAML's default) treats yes/no/on/off as booleans — the
    "Norway problem" that bites DevOps users who write `allow_postgres: no`
    and get False in JSON. YAML 1.2 only recognises true/false (any case).
    This loader implements the stricter rule so yes/no/on/off stay as strings.
    """
    class YAML12Loader(yaml.SafeLoader):
        pass

    YAML12Loader.yaml_implicit_resolvers = {
        ch: [(t, r) for t, r in resolvers if t != "tag:yaml.org,2002:bool"]
        for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    YAML12Loader.add_implicit_resolver(
        "tag:yaml.org,2002:bool",
        re.compile(r"^(?:true|false)$", re.IGNORECASE),
        list("tTfF"),
    )
    return YAML12Loader


def _extract_yaml_blank_lines(text: str) -> list:
    """Extract blank-line positions from YAML text, anchored to the full key
    path of the NEXT key line that follows each blank.

    Anchoring to the following key (rather than an absolute line number) is what
    lets a blank line survive the trip through a structure-only intermediate
    like JSON: even though serialization re-renders the document, the key paths
    are stable (insertion order is preserved), so we can put the blank back in
    front of the same key. Each blank line yields one entry; N consecutive
    blanks before the same key yield N entries. A trailing blank with no
    following key is dropped (YAML output already ends in a newline).
    """
    lines = text.split("\n")
    key_paths = _build_key_paths(lines)
    sorted_keys = sorted(key_paths)
    blanks = []
    for i, line in enumerate(lines):
        if line.strip() != "":
            continue
        # The split on a trailing newline produces a final empty element that
        # is not a real blank line — skip it.
        if i == len(lines) - 1:
            continue
        next_path = None
        for li in sorted_keys:
            if li > i:
                next_path = key_paths[li]["path"]
                break
        if next_path is not None:
            blanks.append({"before_path": next_path})
    return blanks


def _reinsert_yaml_blank_lines(yaml_text: str, blanks: list) -> str:
    """Reinsert blank lines into YAML output before the key whose full path each
    blank was anchored to. Inserts bottom-up so earlier line indices stay valid.
    Must run BEFORE comment reinsertion so that, when a key has both a leading
    blank and a leading comment, the result is blank → comment → key."""
    if not blanks:
        return yaml_text
    lines = yaml_text.split("\n")
    out_key_paths = _build_key_paths(lines)

    path_to_lines = {}
    for li, info in out_key_paths.items():
        path_to_lines.setdefault(info["path"], []).append(li)

    # Count blanks anchored to each path, preserving first-seen order.
    counts = OrderedDict()
    for b in blanks:
        p = b.get("before_path")
        if p is not None:
            counts[p] = counts.get(p, 0) + 1

    insertions = []  # (line_index, count)
    for p, cnt in counts.items():
        if p in path_to_lines and path_to_lines[p]:
            insertions.append((path_to_lines[p][0], cnt))

    for li, cnt in sorted(insertions, reverse=True):
        for _ in range(cnt):
            lines.insert(li, "")
    return "\n".join(lines)


def _extract_ini_comments(text: str) -> list:
    """Extract # and ; comments from INI text."""
    comments = []
    lines = text.split("\n")
    current_key = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Track keys
        if "=" in stripped and not stripped.startswith(("#", ";")):
            current_key = stripped.split("=", 1)[0].strip()
        elif stripped.startswith("[") and stripped.endswith("]"):
            current_key = None
        # Extract comments
        for marker in ("#", ";"):
            if marker in stripped:
                ci = stripped.index(marker)
                # Not inside a value string
                before = stripped[:ci]
                if before.count('"') % 2 == 0:
                    comment_text = stripped[ci + 1 :].strip()
                    is_inline = ci > 0
                    comments.append({
                        "line": i,
                        "key": current_key,
                        "text": comment_text,
                        "is_inline": is_inline,
                        "marker": marker,
                    })
                    break
    return comments


def _reinsert_ini_comments(ini_text: str, comments: list) -> str:
    """Reinsert extracted comments into INI output."""
    if not comments:
        return ini_text
    lines = ini_text.split("\n")
    inserted = set()

    # First pass: standalone comments (no key context) at top
    standalone = [c for c in comments if c["key"] is None]
    keyed = [c for c in comments if c["key"] is not None]

    for c in standalone:
        if not c["is_inline"]:
            lines.insert(0, f"# {c['text']}")
            inserted = {j + 1 for j in inserted}

    # Second pass: keyed comments
    for c in keyed:
        if c["is_inline"]:
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(c["key"] + " =") and i not in inserted:
                    if "#" not in stripped and ";" not in stripped:
                        lines[i] = line + f"  {c['marker']} {c['text']}"
                        inserted.add(i)
                        break
        else:
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(c["key"] + " =") and i not in inserted:
                    lines.insert(i, f"# {c['text']}")
                    inserted.add(i)
                    inserted = {j + 1 if j >= i else j for j in inserted}
                    break
    return "\n".join(lines)


# ── TOML comment preservation ──
_TOML_HEADER_RE = re.compile(r"^\[\[?\s*(.+?)\s*\]\]?\s*$")


def _toml_line_map(lines: list) -> dict:
    """Map line index -> {"section", "key", "is_header"} for every TOML header
    and `key = value` line, tracking the current [section] / [[array]] path.
    The '#' part of a line is ignored when reading code (so a trailing comment
    never confuses key detection)."""
    info = {}
    section = ""
    for i, line in enumerate(lines):
        ci = _yaml_find_comment(line)  # '#' rules are the same in TOML
        code = (line[:ci] if ci >= 0 else line).strip()
        if not code:
            continue
        m = _TOML_HEADER_RE.match(code)
        if m:
            section = m.group(1)
            info[i] = {"section": section, "key": None, "is_header": True}
        elif "=" in code:
            key = code.split("=", 1)[0].strip()
            if len(key) >= 2 and key[0] == key[-1] and key[0] in ("'", '"'):
                key = key[1:-1]
            info[i] = {"section": section, "key": key, "is_header": False}
    return info


def _extract_toml_comments(text: str) -> list:
    """Extract # comments from TOML, anchored to (section, key).

    Inline comments attach to the key (or header) on their own line; full-line
    comments attach to the NEXT key/header line. Anchoring by section+key (not
    line number) is what lets a comment survive a structure-preserving round
    trip through JSON, since the serializer re-emits the same keys. Comments
    BETWEEN elements of a multi-line array are not representable here because
    the serializer renders arrays on a single line — a documented limitation."""
    lines = text.split("\n")
    info = _toml_line_map(lines)
    sorted_keys = sorted(info)
    comments = []
    for i, line in enumerate(lines):
        ci = _yaml_find_comment(line)
        if ci < 0:
            continue
        is_inline = bool(line[:ci].strip())
        ctext = line[ci + 1:].strip()
        if is_inline:
            anchor = info.get(i, {})
        else:
            anchor = {}
            for j in sorted_keys:
                if j > i:
                    anchor = info[j]
                    break
        comments.append({
            "section": anchor.get("section", ""),
            "key": anchor.get("key"),
            "is_header": anchor.get("is_header", False),
            "text": ctext,
            "is_inline": is_inline,
        })
    return comments


def _reinsert_toml_comments(toml_text: str, comments: list) -> str:
    """Reinsert extracted TOML comments, matching by (section, key, is_header).
    Inline comments are appended to their key's line; full-line comments are
    inserted just before it."""
    if not comments:
        return toml_text
    lines = toml_text.split("\n")

    def _match(meta, c):
        return (meta["section"] == c["section"]
                and meta["key"] == c["key"]
                and meta["is_header"] == c.get("is_header", False))

    inserted = set()
    inline = [c for c in comments if c["is_inline"]]
    block = [c for c in comments if not c["is_inline"]]

    # Inline comments first — they don't shift line numbers.
    info = _toml_line_map(lines)
    for c in inline:
        for i in sorted(info):
            if i in inserted or not _match(info[i], c):
                continue
            if _yaml_find_comment(lines[i]) < 0:
                lines[i] = lines[i] + f"  # {c['text']}"
                inserted.add(i)
                break

    # Block comments — rebuild the map after each insert since indices shift.
    for c in block:
        info = _toml_line_map(lines)
        target = next((i for i in sorted(info) if _match(info[i], c)), None)
        if target is not None:
            indent = lines[target][:len(lines[target]) - len(lines[target].lstrip())]
            lines.insert(target, f"{indent}# {c['text']}")
        else:
            lines.insert(0, f"# {c['text']}")
    return "\n".join(lines)


# ── Java .properties (pure-Python, no external library) ──
_PROP_WS = (" ", "\t", "\f")


def _properties_logical_lines(text: str) -> list:
    """Split .properties text into logical lines, honouring backslash
    continuation. Comment (# / !) and blank lines are dropped here and are
    never subject to continuation (matching java.util.Properties)."""
    physical = text.split("\n")
    logical = []
    buf = None
    for raw in physical:
        line = raw[:-1] if raw.endswith("\r") else raw  # tolerate CRLF
        if buf is None:
            stripped = line.strip()
            if not stripped or stripped[0] in ("#", "!"):
                continue  # comment or blank line — not continued
            buf = line.lstrip()  # leading whitespace before the key is ignored
        else:
            buf += line.lstrip()
        # A logical line continues iff it ends in an ODD number of backslashes.
        trailing = len(buf) - len(buf.rstrip("\\"))
        if trailing % 2 == 1:
            buf = buf[:-1]  # drop the continuation backslash, keep accumulating
            continue
        logical.append(buf)
        buf = None
    if buf is not None:
        logical.append(buf)
    return logical


def _properties_decode(s: str) -> str:
    """Decode .properties escape sequences: \\uXXXX, \\n \\r \\t \\f, and
    \\<char> (which yields the literal char, e.g. \\= -> =, \\\\ -> \\)."""
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "u" and i + 6 <= n:
                hex4 = s[i + 2:i + 6]
                try:
                    out.append(chr(int(hex4, 16)))
                    i += 6
                    continue
                except ValueError:
                    # Malformed \\uXXXX — log a warning and fall through to
                    # literal handling so the output is still usable
                    import logging
                    logging.getLogger("configforge.properties").warning(
                        "Malformed \\\\uXXXX escape: '%s' in '%s'", hex4, s
                    )
            mapping = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}
            out.append(mapping.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _properties_split_kv(line: str):
    """Split one logical line into (key, value) per the Java spec: the key ends
    at the first unescaped whitespace, '=' or ':'. One such separator (plus the
    whitespace around it) is consumed; the remainder is the value."""
    i, n = 0, len(line)
    key_chars = []
    while i < n:
        c = line[i]
        if c == "\\":
            key_chars.append(c)
            if i + 1 < n:
                key_chars.append(line[i + 1])
                i += 2
            else:
                i += 1
            continue
        if c in _PROP_WS or c in ("=", ":"):
            break
        key_chars.append(c)
        i += 1
    while i < n and line[i] in _PROP_WS:
        i += 1
    if i < n and line[i] in ("=", ":"):
        i += 1
        while i < n and line[i] in _PROP_WS:
            i += 1
    # Per spec, trim trailing whitespace from the value — but keep whitespace
    # that was explicitly escaped (e.g. a trailing "\ ").
    value_raw = line[i:]
    j = len(value_raw)
    while j > 0 and value_raw[j - 1] in _PROP_WS:
        bs = 0
        k = j - 2
        while k >= 0 and value_raw[k] == "\\":
            bs += 1
            k -= 1
        if bs % 2 == 1:
            break  # escaped whitespace — preserve it
        j -= 1
    return _properties_decode("".join(key_chars)), _properties_decode(value_raw[:j])


def _parse_properties(text: str) -> dict:
    """Parse Java .properties text into a flat dict."""
    result = {}
    for line in _properties_logical_lines(text):
        key, value = _properties_split_kv(line)
        result[key] = value
    return result


def _properties_escape(s: str, is_key: bool, multiline: bool = False) -> str:
    """Escape a key or value for .properties output. Non-ASCII becomes \\uXXXX.
    In keys, whitespace and '=' ':' '#' '!' are escaped. In values, only a
    leading space is escaped. With multiline=True, embedded newlines in a value
    are emitted as an escape + physical backslash continuation."""
    out = []
    for idx, ch in enumerate(s):
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n\\\n" if (multiline and not is_key) else "\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\f":
            out.append("\\f")
        elif ch == " ":
            out.append("\\ " if (is_key or idx == 0) else " ")
        elif ch in ("=", ":", "#", "!"):
            out.append("\\" + ch if is_key else ch)
        elif o < 0x20 or o > 0x7e:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    return "".join(out)


def _properties_flatten(data, prefix: str = "") -> dict:
    """Flatten nested dicts/lists into dotted (and index) keys — the idiomatic
    Java .properties representation of structure, e.g. {"server": {"host": x}}
    becomes {"server.host": x} and a list becomes key.0, key.1, ..."""
    items = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            items.update(_properties_flatten(v, key))
    elif isinstance(data, list):
        for idx, v in enumerate(data):
            key = f"{prefix}.{idx}" if prefix else str(idx)
            items.update(_properties_flatten(v, key))
    else:
        items[prefix] = data
    return items


def _serialize_properties(data: dict, comments=None, multiline: bool = False) -> str:
    """Serialize a dict to Java .properties text. Nested structure is flattened
    to dotted keys. `comments` is an optional list of strings emitted as leading
    '# ' comment lines."""
    if not isinstance(data, dict):
        raise ValueError("properties requires a dict")
    lines = []
    for c in (comments or []):
        lines.append(f"# {c}")
    for k, v in _properties_flatten(data).items():
        if isinstance(v, bool):
            v = "true" if v else "false"
        elif v is None:
            v = ""
        key = _properties_escape(str(k), is_key=True)
        val = _properties_escape(str(v), is_key=False, multiline=multiline)
        lines.append(f"{key}={val}")
    return "\n".join(lines) + "\n"


def _looks_like_properties(text: str) -> bool:
    """Heuristic: >30% of non-blank lines are .properties comments or key/value
    pairs whose key is NOT an all-uppercase ENV-style identifier (so we don't
    steal .env files)."""
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return False
    # Detection requires an explicit '=' or ':' separator (bare-whitespace
    # separators are supported when parsing, but too loose to detect on — they
    # would match ordinary prose). For ':' we additionally require the colon to
    # be immediately followed by a non-space, which keeps YAML ('key: value',
    # 'nested:') out of properties territory.
    env_key = re.compile(r"^[A-Z_][A-Z0-9_]*$")
    eq = re.compile(r"^\s*([^\s=:#!][^=:]*?)\s*=")
    colon = re.compile(r"^\s*([^\s=:#!][^=:]*?):\S")
    comment_matches = 0
    kv_matches = 0
    for line in lines:
        stripped = line.strip()
        if stripped[0] in ("#", "!"):
            comment_matches += 1
            continue
        m = eq.match(line) or colon.match(line)
        if m and not env_key.match(m.group(1).strip()):
            kv_matches += 1
    # Comments alone never classify (a single '#' comment atop a YAML file must
    # not steal it); require at least one real key/value pair.
    if kv_matches == 0:
        return False
    return (kv_matches + comment_matches) > len(lines) * 0.30


def _strip_jsonc(text: str) -> str:
    """Strip // line comments and /* block comments */ from JSONC, then remove
    trailing commas before } or ]. Does not modify string literal contents."""
    result = []
    i, n = 0, len(text)
    in_string = False

    while i < n:
        ch = text[i]
        if in_string:
            if ch == '\\' and i + 1 < n:
                result.append(ch)
                result.append(text[i + 1])
                i += 2
                continue
            result.append(ch)
            if ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue

        # Line comment: skip to end of line
        if ch == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                i += 1
            continue

        # Block comment: skip until */
        if ch == '/' and i + 1 < n and text[i + 1] == '*':
            i += 2
            while i < n - 1:
                if text[i] == '*' and text[i + 1] == '/':
                    i += 2
                    break
                i += 1
            else:
                i = n
            continue

        result.append(ch)
        i += 1

    stripped = ''.join(result)
    # Remove trailing commas before } or ]
    return re.sub(r',(\s*[}\]])', r'\1', stripped)


def detect_format(text: str) -> str:
    """Detect config format from text content."""
    text = text.strip()
    if not text:
        return "unknown"

    # JSON / JSONC: starts with { or [
    if text.startswith("{") or text.startswith("["):
        try:
            json.loads(text)
            return "json"
        except json.JSONDecodeError:
            # Could be JSONC (// line comments, /* block comments */, trailing commas)
            try:
                json.loads(_strip_jsonc(text))
                return "jsonc"
            except (json.JSONDecodeError, Exception):
                pass

    # HCL: terraform-style block headers — `name "label" "label2" {` or a bare
    # `name {`, optionally alongside top-level `key = value` lines. This brace
    # block form (identifier + optional quoted labels + `{`, no `=`) is what
    # distinguishes HCL from TOML/INI, which use `[section]` headers instead.
    _hcl_block = re.search(
        r'^[ \t]*[A-Za-z_][\w-]*(?:[ \t]+"[^"]*")*[ \t]*\{[ \t]*$',
        text, re.MULTILINE)
    if _hcl_block:
        if HAS_HCL:
            try:
                hcl2.loads(text)
                return "hcl"
            except Exception:
                pass
        else:
            return "hcl"

    # TOML: contains [section] with typed values (quotes, booleans, integers)
    if re.search(r"^\[[\w\-\"]+]", text, re.MULTILINE):
        # Check for TOML-typical patterns (quoted strings, booleans, integers without quotes)
        lines_after = text.strip().split("\n")
        toml_indicators = 0
        ini_indicators = 0
        total_values = 0
        for line in lines_after:
            if "=" in line and not line.strip().startswith("["):
                total_values += 1
                val = line.split("=", 1)[1].strip()
                if val.startswith('"') or val.startswith("'"):
                    toml_indicators += 1
                elif val in ("true", "false", "True", "False"):
                    toml_indicators += 1
                elif val.isdigit():
                    toml_indicators += 1
                elif val.startswith("[") or val.startswith("{"):
                    toml_indicators += 1
                else:
                    ini_indicators += 1
        # Require >80% typed values to classify as TOML, else INI
        if total_values > 0 and toml_indicators / total_values > 0.8:
            return "toml"
        return "ini"

    # TOML (top-level keys only, no sections): key = typed_value
    if re.search(r"^[\w\-]+\s*=\s*(?:\"|'|\d+|true|false|\[|\{)", text, re.MULTILINE):
        try:
            import tomllib
            tomllib.loads(text)
            return "toml"
        except Exception:
            pass

    # .env: contains KEY=VALUE lines (check BEFORE INI since ENV is more specific)
    if re.search(r"^[A-Z_][A-Z0-9_]*=", text, re.MULTILINE):
        lines = text.strip().split("\n")
        env_count = sum(1 for l in lines if re.match(r"^[A-Z_][A-Z0-9_]*=", l.strip()))
        if env_count > 0 and env_count >= len(lines) * 0.5:
            return "env"

    # YAML: check for key: value pattern or multi-doc ---
    # Checked BEFORE .properties so Helm values.yaml and similar documented
    # YAML files with "host:port" patterns are not mis-classified as properties.
    if ":" in text or text.strip().startswith("---"):
        for line in text.strip().split("\n"):
            line = line.strip()
            if re.match(r"^[\w\-\"]+:(?:\s|$)", line) or line == "---":
                try:
                    if HAS_YAML:
                        # safe_load rejects multi-doc YAML, so try safe_load_all as fallback
                        try:
                            yaml.safe_load(text)
                        except yaml.composer.ComposerError:
                            list(yaml.safe_load_all(text))
                        except yaml.YAMLError:
                            # Jinja/Helm template syntax ({{ var }}) fails normal parse;
                            # retry with values quoted to confirm it's valid YAML structure.
                            if _has_template_syntax(text):
                                yaml.safe_load(_quote_template_values(text))
                            else:
                                raise
                    return "yaml"
                except Exception:
                    pass
                break

    # .properties: # / ! comments and key=value | key:value | key value pairs.
    # Checked BEFORE INI (which would otherwise swallow bare key=value files)
    # but after YAML and ENV; _looks_like_properties excludes all-uppercase ENV
    # keys so .env files are not stolen. No [section] headers allowed here.
    if not re.search(r"^\s*\[.*\]\s*$", text, re.MULTILINE) and _looks_like_properties(text):
        return "properties"

    # INI: contains key=value (bare values, no types)
    if re.search(r"^\[.*\]$", text, re.MULTILINE) or re.search(r"^[\w]+\s*=", text, re.MULTILINE):
        try:
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read_string(text)
            return "ini"
        except configparser.MissingSectionHeaderError:
            # Bare key=value without section headers — wrap in DEFAULT
            try:
                cfg = configparser.ConfigParser(interpolation=None)
                cfg.read_string("[DEFAULT]\n" + text)
                if cfg.defaults():
                    return "ini"
            except Exception:
                pass
        except Exception:
            pass

    # Binary plist: magic bytes bplist00 (readable even from text)
    if text[:6] == "bplist":
        return "plist"

    # Plist: Apple property list XML — must check before generic XML
    if text.strip().startswith("<") and (
        "<!DOCTYPE plist" in text[:500] or "<plist version=" in text[:500]
    ):
        return "plist"

    # XML: starts with <
    if text.strip().startswith("<") and text.strip().endswith(">"):
        try:
            if HAS_XML:
                ET.fromstring(text)
                return "xml"
        except Exception:
            pass

    # CSV: use csv.Sniffer or delimiter consistency check
    lines = text.strip().split("\n")
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) >= 2:
        # First: try csv.Sniffer for robust detection
        try:
            import io, csv as csvmod
            dialect = csvmod.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            if dialect and len(non_empty) > 0 and non_empty[0].count(dialect.delimiter) >= 1:
                return "csv"
        except Exception:
            pass
        # Fallback: majority-vote delimiter counting
        for delim in [",", "\t", "|", ";"]:
            first_count = _count_delims_outside_quotes(non_empty[0], delim)
            # Check if MOST lines without the first share the same delimiter count
            counts = [_count_delims_outside_quotes(l, delim) for l in non_empty[:5]]
            matching = sum(1 for c in counts[1:] if c == first_count)
            if first_count >= 1 and len(counts) > 1 and matching >= len(counts[1:]) / 2:
                return "csv"
        # Final fallback: lines contain a consistent delimiter
        comma_lines = sum(1 for l in non_empty[:5] if "," in l)
        if comma_lines >= 2:
            return "csv"
    elif len(non_empty) == 1 and non_empty[0].count(",") >= 1:
        # Single line with commas: try csv.Sniffer for header-only CSV
        try:
            import io, csv as csvmod
            dialect = csvmod.Sniffer().sniff(non_empty[0][:4096], delimiters=",;\t|")
            if dialect and non_empty[0].count(dialect.delimiter) >= 1:
                return "csv"
        except Exception:
            pass

    return "unknown"


# ── Parser ──
def _detect_timestamp(val: str):
    """Detect ISO 8601 / RFC 3339 datetime strings.
    Returns True if val looks like a timestamp, False otherwise.
    Matches: 2024-01-15, 2024-01-15T10:30:00Z, 2024-01-15T10:30:00+05:00"""
    # Date-only: YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        return True
    # Datetime: YYYY-MM-DD[T ]HH:MM:SS[.fraction][Z|±HH:MM]
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", val):
        return True
    return False


def _infer_type(val: str):
    """Infer int/float/bool/datetime from a string value."""
    if val.lower() in ("true", "false", "yes", "no", "on", "off"):
        return val.lower() in ("true", "yes", "on")
    # Try timestamp detection (ISO 8601 / RFC 3339)
    if _detect_timestamp(val):
        try:
            # Try full datetime first
            cleaned = val.replace(" ", "T")
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            try:
                return date.fromisoformat(val[:10])
            except (ValueError, TypeError):
                pass
    # Strict numeric inference. Reject things that int()/float() accept but
    # that silently corrupt config values:
    #   • underscore grouping ("1_000" -> 1000)
    #   • leading zeros ("007" -> 7, drops the zeros) — not a canonical integer
    #   • overflow to non-finite ("1e500" -> inf, which is not valid JSON)
    if re.fullmatch(r"[+-]?(?:0|[1-9]\d*)", val):
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
    if re.fullmatch(r"[+-]?(?:(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)", val):
        try:
            f = float(val)
            if math.isfinite(f):
                return f
        except (ValueError, TypeError):
            pass
    return val


def _coerce_dates(data):
    """Recursively turn ISO 8601 / RFC 3339 timestamp strings into real
    date/datetime objects.

    Addresses the "TOML converters keep dates as strings" complaint: once the
    string is a real date object, the TOML serializer emits it unquoted as a
    native datetime instead of a quoted string. Date-only strings become
    `date` (so they don't sprout a spurious 00:00:00 time component)."""
    if isinstance(data, dict):
        return {k: _coerce_dates(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_coerce_dates(v) for v in data]
    if isinstance(data, str) and _detect_timestamp(data):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
            try:
                return date.fromisoformat(data)
            except ValueError:
                return data
        cleaned = data.replace(" ", "T")
        # fromisoformat only learned to accept a trailing 'Z' in 3.11; normalize.
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            return data
    return data


def _hcl_unquote(v):
    """hcl2.loads returns string values (and block-label keys) wrapped in their
    literal double quotes — 'my-app' comes back as '"my-app"'. Strip one
    surrounding pair so downstream formats see the bare value."""
    if isinstance(v, str) and len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    return v


def _hcl_normalize(obj):
    """Recursively undo hcl2's literal quoting on values and block-label keys,
    and drop the internal `__is_block__` markers hcl2 injects into block dicts."""
    if isinstance(obj, dict):
        return {_hcl_unquote(k): _hcl_normalize(v)
                for k, v in obj.items() if k != "__is_block__"}
    if isinstance(obj, list):
        return [_hcl_normalize(i) for i in obj]
    return _hcl_unquote(obj)


def _hcl_requote(obj):
    """Inverse of _hcl_normalize for serialization: re-wrap string values in
    double quotes so hcl2.dumps (which emits strings verbatim, without adding
    quotes) produces valid, re-parseable HCL. Non-strings are left for dumps to
    render natively (numbers bare, bools as true/false, None as null)."""
    if isinstance(obj, dict):
        return {k: _hcl_requote(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_hcl_requote(i) for i in obj]
    if isinstance(obj, str):
        esc = obj.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{esc}"'
    return obj


def parse_text(text: str, fmt: str = None, **options) -> dict:
    """Parse text into a Python dict. Auto-detects format if not specified."""
    result = _parse_text_impl(text, fmt=fmt, **options)
    if options.get("env_expand", False) and isinstance(result.get("data"), (dict, list)):
        result = dict(result, data=_expand_env_vars(result["data"]))
    return result


def _parse_text_impl(text: str, fmt: str = None, **options) -> dict:
    """Internal implementation — use parse_text() externally."""
    if not fmt or fmt == "auto":
        fmt = detect_format(text)

    if fmt == "json":
        return {"data": json.loads(text), "format": "json"}

    elif fmt == "jsonc":
        return {"data": json.loads(_strip_jsonc(text)), "format": "jsonc"}

    elif fmt == "yaml" and HAS_YAML:
        # Handle multi-document YAML (--- separator)
        multi_doc = options.get("multi_doc", True)
        yaml12 = options.get("yaml12", True)
        template_safe = options.get("template_safe", False)
        loader_cls = _make_yaml12_loader() if yaml12 else yaml.SafeLoader

        def _parse_yaml_text(src: str) -> dict:
            if multi_doc and src.count("---") > 0:
                docs = list(yaml.load_all(src, Loader=loader_cls))
                docs = [d for d in docs if d is not None]
                if len(docs) == 1:
                    return {"data": docs[0], "format": "yaml"}
                return {"data": docs, "format": "yaml-multi"}
            return {"data": yaml.load(src, Loader=loader_cls), "format": "yaml"}

        # --template-safe: pre-quote template expressions (Helm/Ansible) first.
        # Useful when the caller knows the file contains {{ var }} expressions.
        if template_safe and _has_template_syntax(text):
            try:
                result = _parse_yaml_text(_quote_template_values(text))
                result["template_quoted"] = True
                return result
            except yaml.YAMLError:
                pass  # fall through to normal parse

        try:
            return _parse_yaml_text(text)
        except yaml.YAMLError as e:
            # Auto-retry with Jinja/Helm template quoting (yq#1126 / yq#2270).
            # Files like  key: {{ var }}  or  host: {{ d }}-api  fail because
            # PyYAML treats {{ as a flow-mapping start. Quote those values and retry.
            if _has_template_syntax(text):
                try:
                    result = _parse_yaml_text(_quote_template_values(text))
                    result["template_quoted"] = True
                    return result
                except yaml.YAMLError:
                    pass
            raise ValueError(_yaml_error_message(e, text)) from e

    elif fmt == "toml" and HAS_TOML:
        return {"data": tomllib.loads(text), "format": "toml"}

    elif fmt == "hcl":
        if not HAS_HCL:
            raise ValueError(
                "HCL support requires the python-hcl2 library, which is not "
                "available in this environment")
        return {"data": _hcl_normalize(hcl2.loads(text)), "format": "hcl"}

    elif fmt == "xml" and HAS_XML:
        root = ET.fromstring(text)
        flatten_xml = options.get("flatten_xml", False)
        if len(root) == 0:
            # Leaf root: capture its text and/or attributes instead of dropping them.
            root_text = root.text.strip() if root.text and root.text.strip() else None
            root_attrs = dict(root.attrib) if root.attrib else None
            if root_attrs:
                data = {"#text": root_text, **root_attrs} if root_text else root_attrs
            elif root_text is not None:
                data = root_text
            else:
                data = {}
        else:
            data = _xml_to_dict(root)
            if flatten_xml:
                data = _flatten_dict(data)
        return {"data": data, "format": "xml"}

    elif fmt == "ini":
        infer_types = options.get("infer_types", True)
        cfg = configparser.ConfigParser(interpolation=None)
        try:
            cfg.read_string(text)
        except configparser.MissingSectionHeaderError:
            # Bare key=value without section headers — wrap in DEFAULT
            cfg.read_string("[DEFAULT]\n" + text)
        result = {}
        # cfg.sections() excludes DEFAULT — handle it explicitly
        if cfg.defaults():
            result["DEFAULT"] = {k: (_infer_type(v) if infer_types else v) for k, v in cfg.defaults().items()}
        for section in cfg.sections():
            result[section] = {k: (_infer_type(v) if infer_types else v) for k, v in cfg[section].items()}
        return {"data": result, "format": "ini"}

    elif fmt == "env":
        infer_types = options.get("infer_types", True)
        result = {}
        input_lines = text.split("\n")
        line_idx = 0
        while line_idx < len(input_lines):
            line = input_lines[line_idx].strip()
            line_idx += 1
            if not line or line.startswith("#"):
                continue
            rest = line
            if rest.startswith("export "):
                rest = rest[7:].strip()
            if "=" not in rest:
                continue
            k, v = rest.split("=", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith('"'):
                # Double-quoted: scan character-by-character for closing unescaped
                # quote, crossing newlines for multiline values (e.g. PEM certs).
                segment = v[1:]  # drop opening quote
                out = []
                found_close = False
                while not found_close:
                    ci = 0
                    while ci < len(segment):
                        ch = segment[ci]
                        if ch == "\\" and ci + 1 < len(segment):
                            nc = segment[ci + 1]
                            if nc == "n":
                                out.append("\n")
                            elif nc == "r":
                                out.append("\r")
                            elif nc == "t":
                                out.append("\t")
                            elif nc == '"':
                                out.append('"')
                            elif nc == "\\":
                                out.append("\\")
                            else:
                                out.append("\\")
                                out.append(nc)
                            ci += 2
                        elif ch == '"':
                            found_close = True
                            break
                        else:
                            out.append(ch)
                            ci += 1
                    if not found_close:
                        # No closing quote on this segment — consume next line
                        if line_idx < len(input_lines):
                            out.append("\n")
                            segment = input_lines[line_idx]
                            line_idx += 1
                        else:
                            break
                v = "".join(out)
            elif len(v) >= 2 and v[0] == "'" and v[-1] == "'":
                # Single-quoted: literal, no escape processing
                v = v[1:-1]
            else:
                # Unquoted: strip inline comment (whitespace + #), then infer type
                m = re.search(r"\s+#", v)
                if m:
                    v = v[: m.start()]
                if infer_types:
                    result[k] = _infer_type(v)
                    continue
            result[k] = v
        return {"data": result, "format": "env"}

    elif fmt == "properties":
        return {"data": _parse_properties(text), "format": "properties"}

    elif fmt == "csv":
        # Strip BOM character from CSV text so field names aren't polluted
        if text.startswith("\ufeff"):
            text = text[1:]
        # Use strict CSV parsing with proper dialect detection
        sample = text[:4096]
        try:
            # Try to sniff dialect; fall back to excel if ambiguous
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            has_header = csv.Sniffer().has_header(sample) if len(sample) > 10 else True
        except csv.Error:
            dialect = csv.excel
            has_header = len(sample) > 0
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        result = []
        for row in reader:
            cleaned = {}
            for k, v in row.items():
                if k is not None:
                    cleaned[k.strip() if isinstance(k, str) else k] = v.strip() if v and isinstance(v, str) else v
            result.append(cleaned)
        if not result:
            # Empty CSV or no rows parsed — try as column list
            reader2 = csv.reader(io.StringIO(text), dialect=dialect)
            rows = list(reader2)
            if rows:
                first_row = rows[0] if rows else []
                has_header = len(rows) > 1 if has_header else (len(rows) > 0)
                headers = [h.strip() if h else f"col{i}" for i, h in enumerate(first_row)]
                data_rows = rows[1:] if len(rows) > 1 else []
                result = [dict(zip(headers, [v.strip() if v else v for v in row])) for row in data_rows]
                # If after all parsing there's still no data, return empty list
                if not result and len(rows) == 1:
                    result = []
        return {"data": result, "format": "csv"}

    elif fmt == "plist":
        import plistlib
        try:
            if isinstance(text, (bytes, bytearray)):
                raw = bytes(text)
            elif text[:6] == "bplist":
                # Binary plist read as text — preserve byte values via latin-1
                raw = text.encode("latin-1")
            else:
                raw = text.encode("utf-8")
            data = plistlib.loads(raw)
            return {"data": _plist_normalize(data), "format": "plist"}
        except Exception as exc:
            raise ValueError(f"Invalid plist: {exc}") from exc

    else:
        if fmt == "unknown":
            raise ValueError(
                "Could not detect format. Try --from yaml or paste valid "
                "YAML/JSON/TOML/XML/CSV/INI/ENV/HCL/PROPERTIES/PLIST"
            )
        raise ValueError(f"Unsupported format: {fmt}")


def _xml_to_dict(element, flatten=False):
    """Recursively convert XML element to dict.
    If flatten=True, skip intermediate nesting for single-child elements."""
    result = {}
    for child in element:
        tag = child.tag
        text = child.text.strip() if child.text and child.text.strip() else None
        attribs = dict(child.attrib) if child.attrib else None
        children = _xml_to_dict(child, flatten) if len(child) > 0 else None

        if children:
            if attribs:
                val = {"#text": text, **attribs} if text else attribs
            else:
                val = children
        elif attribs:
            val = attribs if not text else {"#text": text, **attribs}
        else:
            val = text

        # Flatten: if a child is the sole child having the same tag as parent, skip level
        if flatten and tag in result and isinstance(result[tag], dict) and not isinstance(val, dict):
            pass  # Keep duplicate tags as list below
        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(val)
        else:
            result[tag] = val
    return result


def _sort_keys_recursive(data):
    """Recursively sort dict keys for consistent, deterministic output.

    Addresses the HN yq-alternatives complaint that key ordering is
    non-deterministic and "a non-starter" for API cleanup workflows where
    diffs must be readable.  Used when --sort-keys is passed to serialize().
    """
    if isinstance(data, dict):
        return {k: _sort_keys_recursive(data[k]) for k in sorted(data.keys(), key=str)}
    if isinstance(data, list):
        return [_sort_keys_recursive(item) for item in data]
    return data


def _sort_keys_reverse_recursive(data):
    """Recursively sort dict keys in reverse order.

    Inverse of _sort_keys_recursive. Addresses yq#2390 request for
    sort_keys_reverse() or reverse(sort_keys(.)). Used when
    --sort-keys-reverse is passed to serialize().
    """
    if isinstance(data, dict):
        return {k: _sort_keys_reverse_recursive(data[k]) for k in sorted(data.keys(), key=str, reverse=True)}
    if isinstance(data, list):
        return [_sort_keys_reverse_recursive(item) for item in data]
    return data


def _expand_env_vars(data):
    """Recursively substitute ${VAR} and $VAR references in all string values.

    Only string values are substituted — keys, numbers, booleans are unchanged.
    Missing env vars are left as-is (not replaced with empty string) so that
    partially-expanded configs don't silently lose data.
    """
    import os, re as _re
    _pat = _re.compile(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)')

    def _sub(s):
        def _replace(m):
            name = m.group(1) or m.group(2)
            return os.environ[name] if name in os.environ else m.group(0)
        return _pat.sub(_replace, s)

    if isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    if isinstance(data, str):
        return _sub(data)
    return data


def _split_path(path: str) -> list:
    r"""Split a dot-notation path on unescaped dots only.

    Escape rules (applied left-to-right):
      \.  → literal dot in key name (not a separator)
      \\  → literal backslash in key name

    This fixes the macOS plist complaint where bundle IDs like com.apple.finder
    are flat keys, not nested paths — escape the dots: com\.apple\.finder.

    'a.b.c'         → ['a', 'b', 'c']
    'a\.b.c'        → ['a.b', 'c']
    'a\.b\.c'       → ['a.b.c']
    'a\\.b'         → ['a\', 'b']   (literal backslash key, dot is separator)
    """
    parts: list = []
    current: list = []
    i = 0
    n = len(path)
    while i < n:
        ch = path[i]
        if ch == '\\' and i + 1 < n:
            nxt = path[i + 1]
            if nxt in ('.', '\\'):
                current.append(nxt)  # \. → dot,  \\ → backslash
                i += 2
                continue
        if ch == '.':
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    parts.append(''.join(current))
    return parts


def _get_by_path(data, path: str):
    """Extract a value from a nested dict/list using a dot-notation path.

    Addresses the HN complaint that jq/yq query syntax is too complex for
    simple value extraction — 'server.port' beats '.server | .port // empty'.
    Integer path segments are tried as list indices when the current node is
    a list.  Raises KeyError/IndexError if the path does not exist.
    Use backslash-escaped dots (\\.) to address keys containing literal dots."""
    parts = _split_path(path)
    node = data
    for part in parts:
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                raise KeyError(f"index '{part}' not valid for list")
        elif isinstance(node, dict):
            if part not in node:
                raise KeyError(f"key '{part}' not found")
            node = node[part]
        else:
            raise KeyError(f"cannot traverse '{part}' in {type(node).__name__}")
    return node


def _set_by_path(data, path: str, value):
    """Set a value at a dot-notation path in a nested dict/list.

    Creates intermediate dicts as needed when traversing a dict node.
    Integer path segments index into lists (must be in-range).
    Raises KeyError when a list index is invalid or the path cannot be
    traversed through a scalar.
    Use backslash-escaped dots (\\.) to address keys containing literal dots."""
    parts = _split_path(path)
    node = data
    for part in parts[:-1]:
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError) as exc:
                raise KeyError(f"index '{part}' not valid for list") from exc
        elif isinstance(node, dict):
            if part not in node:
                node[part] = {}
            node = node[part]
        else:
            raise KeyError(f"cannot traverse '{part}' in {type(node).__name__}")
    last = parts[-1]
    if isinstance(node, list):
        try:
            node[int(last)] = value
        except (ValueError, IndexError) as exc:
            raise KeyError(f"index '{last}' not valid for list") from exc
    elif isinstance(node, dict):
        node[last] = value
    else:
        raise KeyError(f"cannot set '{last}' in {type(node).__name__}")


def _append_to_path(data, path: str, value):
    """Append *value* to the list at *path*.

    Addresses the yq v4 verbosity complaint: instead of `.key += ["v"]` the
    caller can simply pass PATH and VALUE.  If the key does not yet exist it is
    created as a single-element list.  Raises KeyError when the existing value
    at *path* is not a list.
    Use backslash-escaped dots (\\.) to address keys containing literal dots."""
    parts = _split_path(path)
    node = data
    for part in parts[:-1]:
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError) as exc:
                raise KeyError(f"index '{part}' not valid for list") from exc
        elif isinstance(node, dict):
            if part not in node:
                node[part] = {}
            node = node[part]
        else:
            raise KeyError(f"cannot traverse '{part}' in {type(node).__name__}")
    last = parts[-1]
    if isinstance(node, list):
        try:
            target = node[int(last)]
        except ValueError:
            raise KeyError(f"index '{last}' not valid for list")
        except IndexError as exc:
            raise KeyError(f"index '{last}' out of range") from exc
        if not isinstance(target, list):
            raise KeyError(f"value at '{last}' is {type(target).__name__}, not a list")
        target.append(value)
    elif isinstance(node, dict):
        if last not in node:
            node[last] = [value]
        elif isinstance(node[last], list):
            node[last].append(value)
        else:
            raise KeyError(f"value at '{last}' is {type(node[last]).__name__}, not a list")
    else:
        raise KeyError(f"cannot append to '{last}' in {type(node).__name__}")


_PYTHON_LITERALS: dict = {"True": True, "False": False, "None": None}


def _coerce_set_value(s: str):
    """Parse --set VALUE: JSON if valid, Python literal if matched, otherwise plain string."""
    if s in _PYTHON_LITERALS:
        return _PYTHON_LITERALS[s]
    try:
        return json.loads(s)
    except (ValueError, json.JSONDecodeError):
        return s


def _deep_merge(base, overlay, list_mode: str = "replace"):
    """Recursively merge overlay onto base.

    Addresses the r/devops complaint that yq has no ergonomic way to merge
    Kubernetes YAML files with nested lists — users needed a full sub-expression
    for something that should be a one-liner.

    list_mode="replace": overlay list replaces base list (default, safe for most configs).
    list_mode="append":  overlay list is appended to base list (useful for k8s env vars,
                         volumes, containers).
    """
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = dict(base)
        for key, val in overlay.items():
            if key in result:
                result[key] = _deep_merge(result[key], val, list_mode)
            else:
                result[key] = val
        return result
    if isinstance(base, list) and isinstance(overlay, list):
        if list_mode == "append":
            return list(base) + list(overlay)
        return list(overlay)
    return overlay


def _delete_by_path(data, path: str):
    """Delete the key/element at a dot-notation path in a nested dict/list.

    Raises KeyError when any path segment is missing or when a list index is
    invalid.  Raises IndexError when a list index is out of range.
    Use backslash-escaped dots (\\.) to address keys containing literal dots."""
    parts = _split_path(path)
    node = data
    for part in parts[:-1]:
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError) as exc:
                raise KeyError(f"index '{part}' not valid for list") from exc
        elif isinstance(node, dict):
            if part not in node:
                raise KeyError(f"key '{part}' not found")
            node = node[part]
        else:
            raise KeyError(f"cannot traverse '{part}' in {type(node).__name__}")
    last = parts[-1]
    if isinstance(node, list):
        try:
            del node[int(last)]
        except (ValueError, IndexError) as exc:
            raise KeyError(f"index '{last}' not valid for list") from exc
    elif isinstance(node, dict):
        if last not in node:
            raise KeyError(f"key '{last}' not found")
        del node[last]
    else:
        raise KeyError(f"cannot delete '{last}' from {type(node).__name__}")


def _rename_by_path(data, old_path: str, new_path: str):
    """Move the value at old_path to new_path (rename / move key).

    Fetches the value, writes it to new_path (creating intermediate dicts as
    needed via _set_by_path), then deletes old_path.  If old_path == new_path
    this is a no-op.  Raises KeyError if old_path does not exist or if either
    path cannot be traversed.
    Use backslash-escaped dots (\\.) to address keys containing literal dots."""
    if old_path == new_path:
        return
    value = _get_by_path(data, old_path)
    _set_by_path(data, new_path, value)
    _delete_by_path(data, old_path)


def _flatten_dict(data, parent_key="", sep="."):
    """Collapse nested dicts into dotted keys to defeat XML-style verbosity.

    Addresses the "XML→YAML produces deeply nested unreadable output" complaint:
    instead of {root:{project:{name: app}}} the caller gets {"project.name": app}.
    Lists and scalars are left in place under their dotted path."""
    if not isinstance(data, dict):
        return data
    items = {}
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict) and v:
            items.update(_flatten_dict(v, new_key, sep))
        else:
            items[new_key] = v
    return items


def _unflatten_dict(data: dict, sep: str = ".") -> dict:
    """Expand flat dotted-key pairs back to a nested dict.

    Inverse of _flatten_dict:
      {"a.b.c": 1, "a.b.d": 2} → {"a": {"b": {"c": 1, "d": 2}}}

    Lists at a given path are kept as-is (not expanded further).
    Raises ValueError if a key collision is detected (e.g. "a" is both a scalar
    and a dict prefix — unresolvable ambiguity)."""
    if not isinstance(data, dict):
        return data
    result: dict = {}
    for key, value in data.items():
        parts = str(key).split(sep)
        d = result
        for i, part in enumerate(parts[:-1]):
            if part in d:
                if not isinstance(d[part], dict):
                    conflict = sep.join(parts[: i + 1])
                    raise ValueError(
                        f"key collision: '{conflict}' is both a scalar and a dict prefix"
                    )
            else:
                d[part] = {}
            d = d[part]
        leaf = parts[-1]
        if leaf in d and isinstance(d[leaf], dict):
            raise ValueError(
                f"key collision: '{key}' is both a value key and a dict prefix"
            )
        d[leaf] = value
    return result


def _format_get_output(val, raw: bool = False) -> str:
    """Format a --get extracted value for stdout.

    Implements round-trip safety (yq #2608): without --raw, string scalars that
    contain YAML-parseable content (colons, booleans, numbers, etc.) are emitted
    with YAML quoting so the output can be safely re-parsed as YAML.  --raw gives
    the bare string value, matching jq -r / yq -r behaviour for scripting use.
    """
    if isinstance(val, (dict, list)):
        return json.dumps(val, indent=2, ensure_ascii=False)
    if val is None:
        return "null"
    if raw:
        return str(val)
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    # String: emit YAML-safe scalar — quote if the value would be misinterpreted.
    # yaml.dump emits a trailing '\n...' document-end marker for plain scalars;
    # strip it so the caller can add exactly one newline.
    if HAS_YAML:
        dumped = yaml.dump(str(val), default_flow_style=False, allow_unicode=True)
        dumped = dumped.rstrip()
        if dumped.endswith("\n..."):
            dumped = dumped[: -len("\n...")].rstrip()
        return dumped
    return str(val)


# ── Serializers ──
def _ini_format_value(v) -> str:
    """Format a scalar value for a ConfigParser INI line.
    None → empty string; booleans → lowercase true/false."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _env_format_value(v) -> str:
    """Format a value for a single .env line.
    Newlines (and carriage returns) would otherwise break the file structure
    and swallow subsequent KEY=VALUE lines, so such values are quoted and the
    line breaks escaped to keep the value on one physical line. Values with
    leading/trailing whitespace, or that begin/end with a quote character,
    are also quoted so the parser round-trips them losslessly.
    None maps to empty string; booleans map to lowercase true/false."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v)
    if "\n" in s or "\r" in s:
        esc = s.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")
        return f'"{esc}"'
    if s != s.strip() or s[:1] in ('"', "'") or s[-1:] in ('"', "'"):
        q = "'" if ('"' in s and "'" not in s) else '"'
        return f"{q}{s}{q}"
    return s


def _plist_normalize(data):
    """Normalize parsed plist data for cross-format use.
    bytes → base64 string; datetime/date → ISO-8601 string."""
    import base64
    if isinstance(data, bytes):
        return base64.b64encode(data).decode("ascii")
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    elif isinstance(data, dict):
        return {str(k): _plist_normalize(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_plist_normalize(v) for v in data]
    return data


def _plist_prepare(data):
    """Coerce arbitrary data to plistlib-compatible types before serialization.
    None maps to empty string (plist has no null type)."""
    if isinstance(data, dict):
        return {str(k): _plist_prepare(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_plist_prepare(v) for v in data]
    elif isinstance(data, (bool, int, float, bytes)):
        return data
    elif isinstance(data, (datetime, date)):
        return data
    elif data is None:
        return ""
    return str(data)


def serialize(data, fmt: str, **options) -> str:
    """Convert Python data to config format string."""
    if fmt in ("json", "jsonc"):
        indent = options.get("indent", 2)
        sort_keys = options.get("sort_keys", False)
        sort_keys_reverse = options.get("sort_keys_reverse", False)
        if sort_keys_reverse:
            data = _sort_keys_reverse_recursive(data)

        class _DatetimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                return super().default(obj)

        return json.dumps(data, indent=indent, sort_keys=sort_keys,
                          ensure_ascii=False, cls=_DatetimeEncoder)

    elif fmt == "yaml" and HAS_YAML:
        indent = options.get("indent", 2)
        sort_keys = options.get("sort_keys", False)
        sort_keys_reverse = options.get("sort_keys_reverse", False)
        if sort_keys_reverse:
            data = _sort_keys_reverse_recursive(data)
        # Handle multi-document YAML: list of dicts → --- separated docs
        if isinstance(data, list) and all(isinstance(d, dict) for d in data):
            return yaml.dump_all(data, default_flow_style=False, allow_unicode=True,
                                 sort_keys=sort_keys, indent=indent)
        return yaml.dump(data, default_flow_style=False, allow_unicode=True,
                         sort_keys=sort_keys, indent=indent)

    elif fmt == "toml":
        if options.get("sort_keys", False):
            data = _sort_keys_recursive(data)
        if options.get("sort_keys_reverse", False):
            data = _sort_keys_reverse_recursive(data)
        if options.get("infer_dates", True):
            data = _coerce_dates(data)
        null_handling = options.get("null_handling", "skip")
        return _to_toml(data, root=True, null_handling=null_handling)

    elif fmt == "hcl":
        if not HAS_HCL:
            raise ValueError(
                "HCL support requires the python-hcl2 library, which is not "
                "available in this environment")
        if not isinstance(data, dict):
            # hcl2.dumps only accepts a dict body at the top level.
            raise ValueError(
                f"HCL requires a dict at the top level, not {type(data).__name__}")
        if options.get("sort_keys", False):
            data = _sort_keys_recursive(data)
        if options.get("sort_keys_reverse", False):
            data = _sort_keys_reverse_recursive(data)
        return hcl2.dumps(_hcl_requote(data))

    elif fmt == "ini":
        if options.get("sort_keys", False):
            data = _sort_keys_recursive(data)
        if options.get("sort_keys_reverse", False):
            data = _sort_keys_reverse_recursive(data)
        if not isinstance(data, dict):
            raise ValueError("INI requires a dict of sections")
        cfg = configparser.ConfigParser(interpolation=None)
        # Check if data has section structure (dict of dicts)
        has_sections = any(isinstance(v, dict) for v in data.values())
        if has_sections:
            top_scalars = {}
            for section, values in data.items():
                if not isinstance(values, dict):
                    # Top-level scalar mixed in with sections: route it to the
                    # DEFAULT section rather than crashing on values.items().
                    if isinstance(values, list):
                        raise ValueError(f"INI cannot represent top-level list '{section}'")
                    top_scalars[section] = values
                    continue
                # Fail if any section value is non-primitive (nested dict/list)
                for k, v in values.items():
                    if isinstance(v, (dict, list)) and not isinstance(v, str):
                        raise ValueError(f"INI cannot represent nested value '{k}' in section '{section}'")
                cfg[section] = {str(k): _ini_format_value(v) for k, v in values.items()}
            if top_scalars:
                cfg["DEFAULT"] = {str(k): _ini_format_value(v) for k, v in top_scalars.items()}
        else:
            # Flat dict → wrap in DEFAULT section
            for k, v in data.items():
                if isinstance(v, (dict, list)) and not isinstance(v, str):
                    raise ValueError(f"INI cannot represent nested value '{k}'")
            cfg["DEFAULT"] = {str(k): _ini_format_value(v) for k, v in data.items()}
        buf = io.StringIO()
        cfg.write(buf)
        return buf.getvalue()

    elif fmt == "env":
        if options.get("sort_keys", False):
            data = _sort_keys_recursive(data)
        if options.get("sort_keys_reverse", False):
            data = _sort_keys_reverse_recursive(data)
        if not isinstance(data, dict):
            raise ValueError("ENV requires a flat dict")
        lines = []
        for k, v in data.items():
            if isinstance(v, dict):
                # Flatten section data from INI sources
                for sk, sv in v.items():
                    lines.append(f"{sk}={_env_format_value(sv)}")
            else:
                lines.append(f"{k}={_env_format_value(v)}")
        return "\n".join(lines)

    elif fmt == "properties":
        if options.get("sort_keys", False):
            data = _sort_keys_recursive(data)
        if options.get("sort_keys_reverse", False):
            data = _sort_keys_reverse_recursive(data)
        return _serialize_properties(
            data,
            comments=options.get("comments"),
            multiline=options.get("multiline", False),
        )

    elif fmt == "csv":
        sort_keys = options.get("sort_keys", False)
        sort_keys_reverse = options.get("sort_keys_reverse", False)
        if isinstance(data, list) and data:
            # Collect ALL fieldnames across all rows for heterogeneous lists
            fieldnames = []
            seen = set()
            for row in data:
                if isinstance(row, dict):
                    for k in row:
                        if k not in seen:
                            fieldnames.append(k)
                            seen.add(k)
            if not fieldnames:
                raise ValueError("CSV requires at least one dict with keys")
            if sort_keys:
                fieldnames = sorted(fieldnames)
            if sort_keys_reverse:
                fieldnames = sorted(fieldnames, reverse=True)
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
            return buf.getvalue()
        elif isinstance(data, dict) and data:
            # Single flat dict → CSV with one row
            if sort_keys_reverse:
                fieldnames = sorted(data.keys(), reverse=True)
            elif sort_keys:
                fieldnames = sorted(data.keys())
            else:
                fieldnames = list(data.keys())
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(data)
            return buf.getvalue()
        raise ValueError("CSV requires a list of dicts or a flat dict")

    elif fmt == "xml":
        if options.get("sort_keys", False):
            data = _sort_keys_recursive(data)
        root_name = options.get("root_name", "root")
        item_name = options.get("item_name", "item")
        return _from_dict_to_xml(data, root_name, item_name)

    elif fmt == "plist":
        import plistlib
        if options.get("sort_keys", False):
            data = _sort_keys_recursive(data)
        prepared = _plist_prepare(data)
        return plistlib.dumps(prepared, fmt=plistlib.FMT_XML).decode("utf-8")

    else:
        raise ValueError(f"Unsupported output format: {fmt}")


def _toml_key(k) -> str:
    """Render a dict key as a TOML key.

    TOML bare keys may only contain A-Z a-z 0-9 _ and -. Anything else
    (spaces, dots, unicode, empty) must be a quoted key, otherwise the
    emitted document is not valid/re-parseable TOML.
    """
    k = str(k)
    if re.fullmatch(r"[A-Za-z0-9_-]+", k):
        return k
    esc = k.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{esc}"'


def _toml_scalar(v):
    """Format a single scalar as a TOML value (bool, int, float, datetime, string)."""
    if v is None:
        # TOML has no null type. Reaching here means a None is nested inside an
        # array or inline table (top-level None keys are handled earlier via
        # null_handling). Refuse rather than silently emit the string "None".
        raise ValueError("TOML cannot represent a null value inside an array or inline table")
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    s = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{s}"'


def _toml_inline(v):
    """Render a value as an inline TOML value: nested dicts become inline
    tables, lists become arrays, scalars use _toml_scalar."""
    if isinstance(v, dict):
        parts = [f"{_toml_key(k)} = {_toml_inline(iv)}" for k, iv in v.items()]
        return "{ " + ", ".join(parts) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(_toml_inline(i) for i in v) + "]"
    return _toml_scalar(v)


def _to_toml(data, prefix="", root=False, null_handling="skip"):
    """Convert dict or list to TOML string. Handles scalar arrays and key ordering.

    TOML has no null type, so `null_handling` decides what happens to None values:
      • "skip"    — omit the key entirely (default, lossy but valid TOML)
      • "comment" — emit `# key = null` so the omission is documented, not silent
      • "empty"   — emit `key = ""`
      • "error"   — raise, refusing to silently drop data"""
    lines = []
    if isinstance(data, list):
        if not prefix:
            if data and not any(isinstance(item, dict) for item in data):
                raise ValueError(
                    "TOML cannot represent a top-level array of scalars")
            rows = []
            for item in data:
                if isinstance(item, dict):
                    parts = [f"{_toml_key(k)} = {_toml_inline(v)}" for k, v in item.items()]
                    rows.append("{ " + ", ".join(parts) + " }")
            return "\n".join(rows)
        lines.append(f"# {len(data)} items (array)")
        return "\n".join(lines)
    elif isinstance(data, dict):
        deferred = []
        scalar_lines = []
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                deferred.append(("table", full_key, v))
            elif isinstance(v, list) and any(isinstance(i, dict) for i in v):
                deferred.append(("tablearray", full_key, v))
            elif isinstance(v, list):
                scalar_lines.append(f"{_toml_key(k)} = [{', '.join(_toml_scalar(i) for i in v)}]")
            elif v is None:  # pragma: no branch (None already handled earlier)
                if null_handling == "comment":
                    scalar_lines.append(f"# {_toml_key(k)} = null")
                elif null_handling == "empty":
                    scalar_lines.append(f'{_toml_key(k)} = ""')
                elif null_handling == "error":
                    raise ValueError(f"TOML cannot represent null value '{full_key}'")
            else:
                scalar_lines.append(f"{_toml_key(k)} = {_toml_scalar(v)}")
        # Only emit a [section] header when there are direct scalar values at this
        # level — intermediate-only tables (like [tool] in pyproject.toml) are
        # implicit in TOML and clutter the output unnecessarily.
        if prefix and not root and scalar_lines:
            quoted_prefix = ".".join(_toml_key(seg) for seg in prefix.split("."))
            lines.append(f"\n[{quoted_prefix}]")
        lines.extend(scalar_lines)
        for kind, full_key, v in deferred:
            if kind == "table":
                lines.append(_to_toml(v, full_key, null_handling=null_handling).strip())
            else:
                for item in v:
                    quoted_tarr = ".".join(_toml_key(seg) for seg in full_key.split("."))
                    lines.append(f"[[{quoted_tarr}]]")
                    if isinstance(item, dict):
                        for ik, iv in item.items():
                            if iv is not None:
                                lines.append(f"{_toml_key(ik)} = {_toml_inline(iv)}")
                    else:
                        lines.append(f"value = {_toml_scalar(item)}")
        return "\n".join(lines)
    # Top-level non-dict non-list (scalar string/int/bool/None) -> fail
    raise ValueError(f"TOML requires a dict (or list of dicts) at the top level, not {type(data).__name__}")


def _from_dict_to_xml(data, root_name="root", item_name="item"):
    """Convert dict to XML string."""
    def _escape_xml(s):
        if s is None:
            return ""
        s = str(s)
        s = s.replace("&", "&amp;")
        s = s.replace("<", "&lt;")
        s = s.replace(">", "&gt;")
        s = s.replace('"', "&quot;")
        s = s.replace("'", "&apos;")
        return s

    def _xml_name(name):
        """Coerce an arbitrary key into a well-formed XML element name.
        XML names cannot contain spaces and must start with a letter or '_'."""
        s = re.sub(r"[^\w.\-]", "_", str(name), flags=re.UNICODE)
        if not s or not re.match(r"[A-Za-z_]", s):
            s = "_" + s
        return s

    def _to_xml(d, name):
        name = _xml_name(name)
        if isinstance(d, dict):
            parts = []
            for k, v in d.items():
                parts.append(_to_xml(v, k))
            return f"<{name}>\n{''.join(parts)}\n</{name}>"
        elif isinstance(d, list):
            return "\n".join(_to_xml(item, item_name) for item in d)
        else:
            if d is None:
                return f"<{name}/>"
            return f"<{name}>{_escape_xml(d)}</{name}>"

    if isinstance(data, list):
        inner = "\n".join(_to_xml(item, item_name) for item in data)
        return f"<{_xml_name(root_name)}>\n{inner}\n</{_xml_name(root_name)}>"
    return _to_xml(data, root_name)


# ── CLI ──
def convert(text: str, to_fmt: str, from_fmt: str = "auto", **options) -> dict:
    """Convert config text from one format to another."""
    try:
        preserve_comments = options.pop("preserve_comments", True)
        carry_comments = options.pop("_carry_comments", None)
        carry_blanks = options.pop("_carry_blanks", None)
        comments = carry_comments if carry_comments is not None else []
        blanks = carry_blanks if carry_blanks is not None else []
        if preserve_comments and not carry_comments:
            in_fmt = from_fmt if from_fmt != "auto" else detect_format(text)
            if in_fmt == "yaml":
                comments = _extract_yaml_comments(text)
                blanks = _extract_yaml_blank_lines(text)
            elif in_fmt == "ini":
                comments = _extract_ini_comments(text)
            elif in_fmt == "toml":
                comments = _extract_toml_comments(text)

        parsed = parse_text(text, from_fmt, **options)
        data = parsed["data"]

        # ── Cross-process comment round-trip through JSON ──
        # When going YAML → JSON: embed extracted comments into the JSON data
        # so they survive a pipe to a separate `devbench cf` process.
        # When going JSON → YAML: extract embedded comments from the JSON data
        # and use them for re-insertion into YAML.
        if preserve_comments and not carry_comments:
            if to_fmt == "json" and (comments or blanks):
                # Embed comments and blank-line positions into JSON data before
                # serialization so they survive a pipe to a separate process.
                if isinstance(data, dict):
                    if comments:
                        data[_COMMENT_META_KEY] = comments
                    if blanks:
                        data[_BLANK_META_KEY] = blanks
                elif isinstance(data, list) and comments:
                    # Top-level array (e.g. multi-doc YAML): wrap so comments
                    # ride along. Blank lines are NOT preserved for top-level
                    # arrays — that would change the JSON shape from array to
                    # object and break consumers expecting an array.
                    data = {_COMMENT_META_KEY: comments, _COMMENT_DATA_KEY: data}
                comments = []  # consumed — now lives in the JSON output
                blanks = []
            elif to_fmt in ("yaml", "ini", "toml") and (from_fmt == "json" or from_fmt == "auto"):
                # Check if the JSON data carries embedded metadata from a prior
                # YAML/TOML→JSON step.
                if isinstance(data, dict) and (
                    _COMMENT_META_KEY in data or _BLANK_META_KEY in data
                ):
                    comments = data.pop(_COMMENT_META_KEY, comments)
                    blanks = data.pop(_BLANK_META_KEY, blanks)
                    inner = data.pop(_COMMENT_DATA_KEY, None)
                    if inner is not None:
                        data = inner
                    # Remove empty shell so the YAML output isn't contaminated
                    elif not data:
                        data = None

        output = serialize(data, to_fmt, **options)

        # Re-insert blank lines and comments if target format supports them.
        # Blanks go in first so a key with both a leading blank and a leading
        # comment ends up as blank → comment → key.
        if to_fmt == "yaml":
            if blanks:
                output = _reinsert_yaml_blank_lines(output, blanks)
                blanks = []  # consumed
            if comments:
                output = _reinsert_yaml_comments(output, comments)
                comments = []  # consumed
        elif comments and to_fmt == "ini":
            output = _reinsert_ini_comments(output, comments)
            comments = []  # consumed
        elif comments and to_fmt == "toml":
            output = _reinsert_toml_comments(output, comments)
            comments = []  # consumed

        result = {
            "success": True,
            "input_format": parsed["format"],
            "output_format": to_fmt,
            "output": output,
            "input_size": len(text),
            "output_size": len(output),
        }
        if comments:
            result["_comments"] = comments
            # Warn when comments are silently dropped (target format doesn't support them)
            _comment_formats = [f for f in ("yaml", "toml", "ini") if f != to_fmt]
            _alt = (
                f" To preserve comments, convert to {' or '.join(_comment_formats)} instead."
                if _comment_formats else ""
            )
            result["comment_loss_warning"] = (
                f"⚠️  {len(comments)} comment(s) were lost: '{to_fmt}' does not support "
                f"comments.{_alt}"
            )
        return result
    except Exception as e:
        err_msg = str(e)
        # Enrich cryptic errors with suggested fixes
        hints = []
        if "Unsupported" in err_msg:
            hints.append("Use --list-formats to see all supported formats.")
        elif "parse" in err_msg.lower() or "invalid" in err_msg.lower():
            hints.append("Check that your input is valid for its format. "
                         "Try --from to specify the source format explicitly.")
        elif "JSON" in err_msg:
            hints.append("JSON must be valid: double-quote strings, no trailing commas.")
        elif "YAML" in err_msg:
            # _yaml_error_message already embeds a "Fix:" line for known errors
            if "Fix:" not in err_msg:
                hints.append("YAML is indentation-sensitive. Check for mixed tabs/spaces.")
        elif "TOML" in err_msg:
            hints.append("TOML requires proper sections [like.this] and no duplicate keys.")
        elif "not found" in err_msg.lower():
            hints.append("Double-check the file path and ensure it exists.")
        elif "dict" in err_msg.lower() and "require" in err_msg.lower():
            hints.append("The input format expects a different structure. "
                         "Try converting with --flatten-xml or --no-comments.")

        enriched = err_msg
        if hints:
            enriched = f"{err_msg}\n  ℹ️  {' '.join(hints)}"
        return {
            "success": False,
            "error": enriched,
            "input_format": from_fmt if from_fmt != "auto" else detect_format(text),
            "output_format": to_fmt,
        }


def convert_file(input_path: str, output_path: str = None, to_fmt: str = None, **options) -> dict:
    """Convert a config file. Auto-detects input/output formats from extensions."""
    path = Path(input_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {input_path}"}

    ext_map = {".json": "json", ".jsonc": "jsonc", ".yaml": "yaml", ".yml": "yaml",
               ".toml": "toml", ".xml": "xml", ".csv": "csv",
               ".ini": "ini", ".env": "env", ".hcl": "hcl",
               ".properties": "properties", ".plist": "plist"}

    input_fmt = ext_map.get(path.suffix.lower(), "auto")
    # Read plist files as bytes to support binary plist format (bplist00 magic)
    if input_fmt == "plist":
        content = path.read_bytes()
    else:
        content = path.read_text(encoding="utf-8", errors="replace")

    if not to_fmt and output_path:
        out_path = Path(output_path)
        to_fmt = ext_map.get(out_path.suffix.lower(), "json")
    elif not to_fmt:
        to_fmt = "json"

    result = convert(content, to_fmt, input_fmt, **options)

    if result["success"] and output_path:
        try:
            Path(output_path).write_text(result["output"], encoding="utf-8")
        except OSError as exc:
            result = {"success": False, "error": f"Cannot write output: {exc}"}

    return result


def _list_keys(data, prefix: str = "", recursive: bool = False) -> list:
    """Return key names (or dot-notation paths when recursive) from a nested structure.

    Non-recursive (default): returns top-level keys only.
    Recursive: returns all leaf and intermediate keys in dot-notation.
    """
    keys = []
    if isinstance(data, dict):
        for k in data:
            full = f"{prefix}.{k}" if prefix else str(k)
            keys.append(full)
            if recursive and isinstance(data[k], (dict, list)):
                keys.extend(_list_keys(data[k], prefix=full, recursive=True))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            full = f"{prefix}.{i}" if prefix else str(i)
            keys.append(full)
            if recursive and isinstance(v, (dict, list)):
                keys.extend(_list_keys(v, prefix=full, recursive=True))
    return keys


def batch_convert_stream(input_glob: str, to_fmt: str, output_dir: str = None, **options):
    """Generator that lazily converts matching files, yielding results one at a time.

    Memory-efficient alternative to ``batch_convert()`` for 10K+ file workloads.
    Instead of collecting all results into a list, each result is yielded as
    soon as the file is processed.

    Yields ``dict`` results with the same fields as ``batch_convert()`` items.
    The final result (after the last file) includes a summary under ``_summary``.
    """
    import glob

    show_progress = options.pop("show_progress", True)
    recursive = options.pop("recursive", False)
    files = sorted(glob.glob(input_glob, recursive=recursive))
    total = len(files)

    if total == 0:
        if show_progress:
            print(f"[batch] No files matched: {input_glob}")
        yield {"_empty": True, "_summary": {"total": 0, "success": 0, "errors": 0}}
        return

    if show_progress:
        print(f"[batch] Converting {total} file(s) matching '{input_glob}' -> {to_fmt}")
        print(f"[batch] {'─' * 50}")

    success_count = 0
    for idx, fpath in enumerate(files, 1):
        out_path = None
        if output_dir:
            in_path = Path(fpath)
            out_path = Path(output_dir) / f"{in_path.stem}.{to_fmt}"
            out_path.parent.mkdir(parents=True, exist_ok=True)

        if show_progress:
            pct = idx * 100 // total
            bar_len = 30
            filled = bar_len * idx // total
            bar = '█' * filled + '░' * (bar_len - filled)
            print(f"\r[batch] |{bar}| {idx}/{total} ({pct}%) {fpath}...   ", end="", flush=True)

        result = convert_file(fpath, str(out_path) if out_path else None, to_fmt, **options)
        result["file"] = fpath
        result["_batch_index"] = idx
        result["_batch_total"] = total

        if result.get("success"):
            success_count += 1

        if show_progress:
            if result["success"]:
                cw = result.get("comment_loss_warning")
                if cw:
                    print(f" ✓ ({result.get('output_size', 0)} bytes) ⚠️ comments lost")
                else:
                    print(f" ✓ ({result.get('output_size', 0)} bytes)")
            else:
                print(f" ✗ {result.get('error', 'unknown error')}")

        yield result

    if show_progress:
        print(f"[batch] {'─' * 50}")
        print(f"[batch] Done: {success_count}/{total} successful")

    # Final summary yield so callers get a completion signal
    yield {
        "_summary": {
            "total": total,
            "success": success_count,
            "errors": total - success_count,
        }
    }


def batch_convert(input_glob: str, to_fmt: str, output_dir: str = None, **options) -> list:
    """Convert all matching files in batch with progress output.

    For 10K+ file workloads, prefer ``batch_convert_stream()`` which yields
    results incrementally instead of building an in-memory list.
    """
    import glob
    show_progress = options.pop("show_progress", True)
    recursive = options.pop("recursive", False)

    files = sorted(glob.glob(input_glob, recursive=recursive))
    total = len(files)
    if total == 0:
        if show_progress:
            print(f"[batch] No files matched: {input_glob}")
        return []

    if show_progress:
        print(f"[batch] Converting {total} file(s) matching '{input_glob}' -> {to_fmt}")
        print(f"[batch] {'─' * 50}")

    results = []
    for idx, fpath in enumerate(files, 1):
        out_path = None
        if output_dir:
            in_path = Path(fpath)
            out_path = Path(output_dir) / f"{in_path.stem}.{to_fmt}"
            out_path.parent.mkdir(parents=True, exist_ok=True)

        if show_progress:
            print(f"[batch] [{idx}/{total}] {fpath} -> {out_path or to_fmt}...", end="")

        result = convert_file(fpath, str(out_path) if out_path else None, to_fmt, **options)
        result["file"] = fpath
        results.append(result)

        if show_progress:
            if result["success"]:
                print(f" \u2713 ({result.get('output_size', 0)} bytes)")
            else:
                print(f" \u2717 {result.get('error', 'unknown error')}")

    success_count = sum(1 for r in results if r["success"])
    if show_progress:
        print(f"[batch] {'─' * 50}")
        print(f"[batch] Done: {success_count}/{total} successful")
    return results


def round_trip(text: str, via: str = "json", fmt: str = "auto", **options) -> dict:
    """Convert text to an intermediate format and back, preserving comments.

    Directly addresses the #1 complaint — "YAML→JSON→YAML destroys all comments".
    Comments are extracted on the way out (and returned by convert() in
    `_comments`) then carried back in on the return leg so the round-trip is
    comment-lossless even though the intermediate (e.g. JSON) cannot hold them."""
    src = fmt if fmt != "auto" else detect_format(text)
    forward = convert(text, via, src, **options)
    if not forward.get("success"):
        return forward
    carry = forward.get("_comments", [])
    return convert(forward["output"], src, via, _carry_comments=carry, **options)


def validate_indentation(text: str, unit: int = 2) -> dict:
    """Validate that YAML-style indentation is consistent.

    Addresses the "converter produced mixed 2/4-space indents that kubectl
    silently ignored" complaint. Every non-blank line's leading whitespace must
    be a multiple of `unit`, must never contain a tab, and must not jump by more
    than one level at a time. Returns {'valid': bool, 'issues': [str, ...]}."""
    issues = []
    prev_indent = 0
    for i, line in enumerate(text.split("\n"), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        leading = line[: len(line) - len(line.lstrip())]
        if "\t" in leading:
            issues.append(f"line {i}: tab character in indentation")
            continue
        indent = len(leading)
        if indent % unit != 0:
            issues.append(f"line {i}: indent {indent} is not a multiple of {unit}")
        elif indent > prev_indent + unit:
            issues.append(f"line {i}: indent jumps from {prev_indent} to {indent}")
        prev_indent = indent
    return {"valid": not issues, "issues": issues}


def mask_sensitive(data, key_pattern: str, replacement: str = "***REDACTED***"):
    """Recursively mask config values whose key names match *key_pattern* (regex).

    - Dict key matching pattern → value replaced with *replacement* (any depth).
    - Dict key not matching → recurse into the value.
    - Lists → recurse into each element.
    - Scalars → returned unchanged.

    ``re.IGNORECASE`` is always applied so ``--mask 'password'`` catches
    ``Password``, ``PASSWORD``, etc.

    Returns a new object; the original *data* is not modified.
    """
    import re as _re
    pat = _re.compile(key_pattern, _re.IGNORECASE)

    def _walk(obj):
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if pat.search(str(k)):
                    out[k] = replacement
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(obj, list):
            return [_walk(item) for item in obj]
        return obj

    return _walk(data)


def schema_validate(data, schema: dict) -> dict:
    """Validate *data* against a JSON Schema *schema*.

    Returns ``{"valid": bool, "errors": list[str]}``.
    Requires the ``jsonschema`` package (``pip install jsonschema``).
    """
    if not HAS_JSONSCHEMA:
        return {
            "valid": False,
            "errors": ["jsonschema not installed — run: pip install jsonschema"],
        }
    try:
        validator_cls = _jsonschema_mod.Draft7Validator
        validator = validator_cls(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if not errors:
            return {"valid": True, "errors": []}
        msgs = []
        for err in errors:
            path = ".".join(str(p) for p in err.absolute_path) or "(root)"
            msgs.append(f"{path}: {err.message}")
        return {"valid": False, "errors": msgs}
    except Exception as exc:
        return {"valid": False, "errors": [f"Schema error: {exc}"]}


# ── SUPPORTED FORMATS ──
SUPPORTED_FORMATS = ["json", "jsonc", "yaml", "toml", "xml", "csv", "ini", "env", "hcl",
                     "properties", "plist"]

# Telemetry opt-out: set DEVBENCH_NO_TELEMETRY=1 (canonical; the misspelled
# DEVEBENCH_NO_TELEMETRY is also accepted for backward compatibility)
# ConfigForge never sends data externally — this flag exists as an
# explicit trust signal for compliance audits.
_telemetry_disabled = (
    os.environ.get("DEVBENCH_NO_TELEMETRY", "").strip() in ("1", "true", "yes")
    or os.environ.get("DEVEBENCH_NO_TELEMETRY", "").strip() in ("1", "true", "yes")
)


try:
    from core._version import __version__ as _Version
except ImportError:
    try:
        from _version import __version__ as _Version
    except ImportError:
        _Version = "1.0.0"


# ── Unified offline CLI ──
def main(argv=None) -> int:
    """Single unified CLI for all conversions — file, stdin/stdout, or batch glob.

    Addresses the "no unified CLI tool" and "no offline converter" complaints:
    one entry point, zero network calls, all nine formats."""
    import argparse

    ext_map = {".json": "json", ".jsonc": "jsonc", ".yaml": "yaml", ".yml": "yaml",
               ".toml": "toml", ".xml": "xml", ".csv": "csv", ".ini": "ini",
               ".env": "env", ".hcl": "hcl", ".properties": "properties",
               ".plist": "plist"}

    parser = argparse.ArgumentParser(
        prog="configforge",
        description="Offline multi-format config converter "
                    "(JSON/JSONC/YAML/TOML/XML/CSV/INI/.env/HCL/.properties). "
                    "No network, no telemetry. "
                    "Set DEVBENCH_NO_TELEMETRY=1 (or legacy DEVEBENCH_NO_TELEMETRY) for explicit assurance.",
        epilog="""Examples:
  # Convert Kubernetes YAML to JSON
  configforge deployment.yaml -t json
  # Convert Docker Compose to TOML (pipe)
  cat docker-compose.yml | configforge -t toml
  # Convert Spring Boot .properties to YAML
  configforge application.properties -t yaml
  # Batch convert all INI files in a directory to TOML
  configforge 'configs/*.ini' -t toml --batch --output-dir out/
  # Convert .env to JSON for a monitoring dashboard
  configforge production.env -t json
  # Download demo: curl -s https://naxiai.com/tools/devbench/demo/

Compared to yq/jq:
  * Unified tool: one CLI for EVERY format (not just YAML↔JSON)
  * Offline: no network calls, paste production configs safely
  * Typed: INI booleans become real booleans, dates become TOML datetimes
  * Batch: glob-based conversion of 1000s of files in one command
  * Comments: preserved through YAML↔INI round-trips
  * No data leaves your machine (unlike online converters)
""",
    )
    parser.add_argument("--version", "-V", action="version",
                        version=f"configforge {_Version}")
    parser.add_argument("input", nargs="?",
                        help="Input file (or glob with --batch). Reads stdin if omitted.")
    parser.add_argument("-t", "--to", help="Target format.")
    parser.add_argument("-f", "--from", dest="from_fmt", default="auto",
                        help="Source format (default: auto-detect).")
    parser.add_argument("-o", "--output", help="Output file (default: stdout).")
    parser.add_argument("--batch", action="store_true",
                        help="Treat input as a glob and convert every match.")
    parser.add_argument("--recursive", "-R", action="store_true",
                        help="For --batch: recursively match files in subdirectories. "
                             "Use with ** glob patterns, e.g. '**/*.yaml'.")
    parser.add_argument("--output-dir", help="Output directory for --batch mode.")
    parser.add_argument("--keys", action="store_true",
                        help="List all top-level keys from the input config. "
                             "Add --recursive to list every nested key in dot-notation.")
    parser.add_argument("--raw-keys", action="store_true", dest="raw_keys",
                        help="With --keys: output each key on its own line with no formatting "
                             "(default behaviour — flag exists for explicitness).")
    parser.add_argument("--indent", type=int, default=2,
                        help="Indentation width for YAML/JSON output.")
    parser.add_argument("--flatten-xml", action="store_true",
                        help="Flatten nested XML into dotted keys.")
    parser.add_argument("--no-comments", action="store_true",
                        help="Do not preserve comments.")
    parser.add_argument("--yaml12", action="store_true",
                        help="Use YAML 1.2 boolean rules: only true/false are booleans. "
                             "Treats yes/no/on/off as plain strings (prevents the Norway problem).")
    parser.add_argument("--template-safe", action="store_true", dest="template_safe",
                        help="Pre-quote Jinja/Helm/Ansible {{ var }} template values in YAML "
                             "before parsing. Use for Helm charts, Ansible playbooks, or any "
                             "YAML with unquoted {{ ... }} expressions. Auto-retry is the "
                             "default; this flag forces quoting on the first pass.")
    parser.add_argument("--sort-keys", action="store_true", help="Sort keys in output.")
    parser.add_argument("--sort-keys-reverse", action="store_true", dest="sort_keys_reverse",
                        help="Sort keys in reverse alphabetical order.")
    parser.add_argument("--compact", "-c", action="store_true",
                        help="Output compact/minified JSON (no whitespace). Only affects JSON output.")
    parser.add_argument("--no-infer-dates", action="store_true",
                        help="Keep ISO-8601 date strings as strings (TOML).")
    parser.add_argument("--null", dest="null_handling", default="skip",
                        choices=["skip", "comment", "empty", "error"],
                        help="How to represent null values in TOML.")
    parser.add_argument("--get", metavar="PATH",
                        help="Extract a single value by dot-notation path "
                             "(e.g. server.port, items.0.name). "
                             "--to is not required when --get is used.")
    parser.add_argument("--raw", "-r", action="store_true",
                        help="Raw string output for --get: print the string value without "
                             "YAML quoting. By default --get emits a YAML-safe scalar "
                             "(quoted if needed for round-trip safety, like jq -r).")
    parser.add_argument("--default", metavar="VALUE", default=None, dest="get_default",
                        help="Fallback value when --get path is missing. "
                             "Prints VALUE and exits 0 instead of an error. "
                             "Example: configforge config.yaml --get timeout --default 30")
    parser.add_argument("--set", metavar=("PATH", "VALUE"), nargs=2,
                        help="Set a value by dot-notation path and write the result. "
                             "VALUE is parsed as JSON (booleans, numbers, null, "
                             "arrays, objects); strings need no quoting. "
                             "Output format defaults to the input format. "
                             "Use --in-place to overwrite the source file.")
    parser.add_argument("--append", metavar=("PATH", "VALUE"), nargs=2,
                        help="Append VALUE to the list at PATH. Creates the list if the key "
                             "is absent. VALUE is parsed as JSON; strings need no quoting. "
                             "Output format defaults to the input format. "
                             "Use --in-place to overwrite the source file.")
    parser.add_argument("--in-place", "-i", action="store_true", dest="in_place",
                        help="Write --set/--append/--delete output back to the input file (requires "
                             "a file argument, not stdin).")
    parser.add_argument("--delete", metavar="PATH",
                        help="Delete a key by dot-notation path and write the result. "
                             "Output format defaults to the input format. "
                             "Use --in-place to overwrite the source file.")
    parser.add_argument("--merge", metavar="OVERLAY",
                        help="Deep-merge OVERLAY file onto the base input and emit the result. "
                             "Dict keys from OVERLAY override base; list behaviour is "
                             "controlled by --list-merge. Output format defaults to the "
                             "base input format.  Use --in-place to overwrite the base file.")
    parser.add_argument("--list-merge", metavar="MODE", dest="list_merge",
                        default="replace", choices=["replace", "append"],
                        help="How to merge lists when using --merge: "
                             "'replace' (default) replaces the base list with the overlay list; "
                             "'append' appends the overlay list to the base list "
                             "(useful for Kubernetes env-vars, volumes, containers).")
    parser.add_argument("--select", metavar="FIELD=VALUE", default=None, dest="select_expr",
                        help="Filter a list: keep items where FIELD equals VALUE. "
                             "Use FIELD!=VALUE to negate. Exit 0=matches, 1=no matches. "
                             "Combine with --get to navigate to a nested list first. "
                             "Example: configforge pods.yaml --select status=Running")
    parser.add_argument("--template", metavar="FILE", default=None, dest="template_file",
                        help="Render a template file using config values as context. "
                             "${key} and {{ key }} (Jinja2) syntax supported. "
                             "Dot-path keys available with dots replaced by underscores. "
                             "Example: configforge app.yaml --template deploy.tmpl > deploy.sh")
    args = parser.parse_args(argv)

    options = {
        "indent": args.indent,
        "flatten_xml": args.flatten_xml,
        "preserve_comments": not args.no_comments,
        "sort_keys": args.sort_keys,
        "sort_keys_reverse": getattr(args, "sort_keys_reverse", False),
        "infer_dates": not args.no_infer_dates,
        "null_handling": args.null_handling,
        "yaml12": args.yaml12,
        "template_safe": args.template_safe,
    }
    # Parse-only options passed to parse_text() in CRUD handlers.
    parse_opts = {"yaml12": args.yaml12, "template_safe": args.template_safe}

    if args.batch:
        if not args.input:
            print("error: --batch requires an input glob", file=sys.stderr)
            return 2
        if not args.to:
            print("error: --batch requires --to", file=sys.stderr)
            return 2
        results = batch_convert(args.input, args.to, args.output_dir,
                                recursive=args.recursive, **options)
        return 0 if results and all(r.get("success") for r in results) else 1

    if args.keys:
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        try:
            parsed = parse_text(text, fmt=args.from_fmt if args.from_fmt != "auto" else None,
                                **parse_opts)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        data = parsed.get("data", parsed)
        for k in _list_keys(data, recursive=args.recursive):
            print(k)
        return 0

    if args.select_expr:
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        try:
            parsed = parse_text(text, fmt=args.from_fmt if args.from_fmt != "auto" else None,
                                **parse_opts)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        data = parsed.get("data", parsed)
        detected_fmt = parsed.get("format", "yaml")
        if args.get:
            try:
                data = _get_by_path(data, args.get)
            except (KeyError, IndexError) as exc:
                default = getattr(args, "get_default", None)
                if default is not None:
                    sys.stdout.write(default + "\n")
                    return 0
                print(f"error: {exc}", file=sys.stderr)
                return 1
        if not isinstance(data, list):
            print("error: --select requires a list; input is not a list "
                  "(use --get PATH to navigate to one)", file=sys.stderr)
            return 1
        expr = args.select_expr
        if "!=" in expr:
            field, raw_val = expr.split("!=", 1)
            negate = True
        elif "=" in expr:
            field, raw_val = expr.split("=", 1)
            negate = False
        else:
            print(f"error: invalid --select expression {expr!r}; "
                  "expected FIELD=VALUE or FIELD!=VALUE", file=sys.stderr)
            return 1
        coerced_val = _coerce_set_value(raw_val)
        def _item_matches(item):
            if not isinstance(item, dict):
                return False
            try:
                item_val = _get_by_path(item, field)
            except (KeyError, IndexError, TypeError):
                return False
            match = (item_val == coerced_val)
            return (not match) if negate else match
        filtered = [item for item in data if _item_matches(item)]
        if not filtered:
            return 1
        to_fmt_sel = args.to or detected_fmt
        indent = args.indent
        compact = getattr(args, "compact", False)
        if to_fmt_sel in ("yaml", "yml"):
            import yaml as _yaml
            output_text = _yaml.dump(filtered, default_flow_style=False,
                                     allow_unicode=True, indent=indent)
        elif to_fmt_sel in ("json", "jsonc"):
            output_text = (json.dumps(filtered, separators=(",", ":"))
                           if compact else json.dumps(filtered, indent=indent)) + "\n"
        else:
            try:
                output_text = serialize(filtered, to_fmt_sel, **options)
            except ValueError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
        if not output_text.endswith("\n"):
            output_text += "\n"
        sys.stdout.write(output_text)
        return 0

    if args.get:
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        try:
            parsed = parse_text(text, fmt=args.from_fmt if args.from_fmt != "auto" else None,
                                **parse_opts)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        data = parsed.get("data", parsed)
        try:
            val = _get_by_path(data, args.get)
        except (KeyError, IndexError) as exc:
            default = getattr(args, "get_default", None)
            if default is not None:
                sys.stdout.write(default + "\n")
                return 0
            print(f"error: {exc}", file=sys.stderr)
            return 1
        sys.stdout.write(_format_get_output(val, raw=getattr(args, "raw", False)) + "\n")
        return 0

    if args.set:
        path, raw_value = args.set
        value = _coerce_set_value(raw_value)
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        from_fmt_set = args.from_fmt if args.from_fmt != "auto" else None
        try:
            parsed = parse_text(text, fmt=from_fmt_set, **parse_opts)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        detected_fmt = parsed.get("format")
        data = parsed.get("data", parsed)
        try:
            _set_by_path(data, path, value)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        to_fmt_set = args.to or detected_fmt
        if not to_fmt_set:
            print("error: cannot determine output format; use --to", file=sys.stderr)
            return 2
        try:
            output_text = serialize(data, to_fmt_set, **options)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not output_text.endswith("\n"):
            output_text += "\n"
        if args.in_place:
            if not args.input:
                print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
                return 2
            Path(args.input).write_text(output_text, encoding="utf-8")
        else:
            sys.stdout.write(output_text)
        return 0

    if args.append:
        path_app, raw_val_app = args.append
        value_app = _coerce_set_value(raw_val_app)
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        from_fmt_app = args.from_fmt if args.from_fmt != "auto" else None
        try:
            parsed = parse_text(text, fmt=from_fmt_app, **parse_opts)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        detected_fmt = parsed.get("format")
        data = parsed.get("data", parsed)
        try:
            _append_to_path(data, path_app, value_app)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        to_fmt_app = args.to or detected_fmt
        if not to_fmt_app:
            print("error: cannot determine output format; use --to", file=sys.stderr)
            return 2
        try:
            output_text = serialize(data, to_fmt_app, **options)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not output_text.endswith("\n"):
            output_text += "\n"
        if args.in_place:
            if not args.input:
                print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
                return 2
            Path(args.input).write_text(output_text, encoding="utf-8")
        else:
            sys.stdout.write(output_text)
        return 0

    if args.delete:
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        from_fmt_del = args.from_fmt if args.from_fmt != "auto" else None
        try:
            parsed = parse_text(text, fmt=from_fmt_del, **parse_opts)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        detected_fmt = parsed.get("format")
        data = parsed.get("data", parsed)
        try:
            _delete_by_path(data, args.delete)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        to_fmt_del = args.to or detected_fmt
        if not to_fmt_del:
            print("error: cannot determine output format; use --to", file=sys.stderr)
            return 2
        try:
            output_text = serialize(data, to_fmt_del, **options)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not output_text.endswith("\n"):
            output_text += "\n"
        if args.in_place:
            if not args.input:
                print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
                return 2
            Path(args.input).write_text(output_text, encoding="utf-8")
        else:
            sys.stdout.write(output_text)
        return 0

    if args.merge:
        try:
            base_text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        except OSError as e:
            print(f"error: cannot read base file: {e}", file=sys.stderr)
            return 1
        from_fmt_merge = args.from_fmt if args.from_fmt != "auto" else None
        try:
            base_parsed = parse_text(base_text, fmt=from_fmt_merge, **parse_opts)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        detected_fmt = base_parsed.get("format")
        base_data = base_parsed.get("data", base_parsed)
        try:
            overlay_text = Path(args.merge).read_text(encoding="utf-8")
        except OSError as e:
            print(f"error: cannot read overlay file: {e}", file=sys.stderr)
            return 1
        try:
            overlay_parsed = parse_text(overlay_text, **parse_opts)
        except ValueError as exc:
            print(f"error reading overlay: {exc}", file=sys.stderr)
            return 1
        overlay_data = overlay_parsed.get("data", overlay_parsed)
        merged = _deep_merge(base_data, overlay_data, list_mode=args.list_merge)
        to_fmt_merge = args.to or detected_fmt
        if not to_fmt_merge:
            print("error: cannot determine output format; use --to", file=sys.stderr)
            return 2
        try:
            output_text = serialize(merged, to_fmt_merge, **options)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not output_text.endswith("\n"):
            output_text += "\n"
        if args.in_place:
            if not args.input:
                print("error: --in-place requires a file argument, not stdin", file=sys.stderr)
                return 2
            Path(args.input).write_text(output_text, encoding="utf-8")
        else:
            sys.stdout.write(output_text)
        return 0

    if args.template_file:
        import re
        import string as _string
        try:
            template_text = Path(args.template_file).read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"error: template file not found: {args.template_file}", file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"error: cannot read template file: {exc}", file=sys.stderr)
            return 1
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        try:
            parsed = parse_text(text, fmt=args.from_fmt if args.from_fmt != "auto" else None,
                                **parse_opts)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        data = parsed.get("data", parsed)
        flat = _flatten_dict(data, sep=".") if isinstance(data, dict) else {}
        def _to_str(v) -> str:
            if isinstance(v, bool):
                return "true" if v else "false"
            return str(v)
        context: dict = {}
        for k, v in flat.items():
            str_val = _to_str(v)
            lower_key = re.sub(r"[^a-z0-9]", "_", k.lower())
            upper_key = re.sub(r"[^A-Z0-9]", "_", k.upper())
            context[lower_key] = str_val
            context[upper_key] = str_val
        use_jinja2 = "{{" in template_text or "{%" in template_text
        if use_jinja2:
            try:
                import jinja2
                env = jinja2.Environment(undefined=jinja2.Undefined, keep_trailing_newline=True)
                tmpl = env.from_string(template_text)
                rendered = tmpl.render(config=data, **context)
                sys.stdout.write(rendered if rendered.endswith("\n") else rendered + "\n")
                return 0
            except ImportError:
                pass  # fall through to string.Template
            except Exception as exc:
                print(f"error: Jinja2 template rendering failed: {exc}", file=sys.stderr)
                return 1
        try:
            rendered = _string.Template(template_text).safe_substitute(context)
        except (KeyError, ValueError) as exc:
            print(f"error: template substitution failed: {exc}", file=sys.stderr)
            return 1
        sys.stdout.write(rendered if rendered.endswith("\n") else rendered + "\n")
        return 0

    to_fmt = args.to
    if not to_fmt and args.output:
        to_fmt = ext_map.get(Path(args.output).suffix.lower())

    # jq-style passthrough: no --to → auto-detect format and pretty-print in place
    if not to_fmt:
        raw_text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        detected = detect_format(raw_text)
        if detected == "unknown":
            print("error: could not auto-detect format; use --to", file=sys.stderr)
            return 2
        to_fmt = detected
        result = convert(raw_text, to_fmt, to_fmt, **options)
        if result.get("success") and args.output:
            Path(args.output).write_text(result["output"], encoding="utf-8")
    elif args.input:
        result = convert_file(args.input, args.output, to_fmt, **options)
    else:
        text = sys.stdin.read()
        result = convert(text, to_fmt, args.from_fmt, **options)
        if result.get("success") and args.output:
            Path(args.output).write_text(result["output"], encoding="utf-8")

    if not result.get("success"):
        print(f"error: {result.get('error', 'conversion failed')}", file=sys.stderr)
        return 1

    if not args.output:
        out = result["output"]
        if getattr(args, "compact", False) and to_fmt in ("json", "jsonc"):
            try:
                out = json.dumps(json.loads(out), separators=(",", ":"), ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        sys.stdout.write(out if out.endswith("\n") else out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())