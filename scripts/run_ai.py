#!/usr/bin/env python3
"""run_ai.py — Run Claude Code CLI with Gemini fallback.

Tries Claude Opus 4.8 first (uses Claude Max subscription, $0/call).
If Claude fails (rate limit, token exhaustion, crash), falls back to
Gemini 3.1 Pro Preview (uses Gemini Pro subscription, $0/call).

Usage:
    echo "prompt text" | python3 run_ai.py --output forge/report.md
    python3 run_ai.py --prompt "prompt text" --output forge/report.md

The output file gets the AI response + a footer noting which model was used.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

_LOCK_DIR = Path("/tmp/devbench_locks")
_LOCK_DIR.mkdir(parents=True, exist_ok=True)
_LOCK_TIMEOUT = 300  # 5 minute max wait


def run_claude(prompt_text: str, workdir: str = None) -> tuple[str, bool]:
    """Run Claude Code CLI with the prompt. Returns (output, success)."""
    workdir = workdir or "/var/www/devbench"
    try:
        result = subprocess.run(
            [
                "claude",
                "--dangerously-skip-permissions",
                "--model", "opus",
                "--effort", "high",
                "-p", prompt_text,
            ],
            capture_output=True,
            text=True,
            timeout=480,
            cwd=workdir,
        )
        output = result.stdout + "\n" + result.stderr
        output = output.strip()
        success = result.returncode == 0
        return output, success
    except subprocess.TimeoutExpired:
        return "TIMEOUT: Claude took longer than 300 seconds", False
    except FileNotFoundError:
        return "ERROR: Claude CLI not found", False
    except Exception as e:
        return f"ERROR: Claude crashed: {e}", False


def run_gemini(prompt_text: str) -> tuple[str, bool]:
    """Try Gemini CLI in YOLO mode first, fall back to REST API.

    Gemini CLI (--yolo) can write files like Claude Code CLI.
    REST API ask_gemini.py is the safe fallback when CLI is unavailable.
    """
    gemini_cli = "/home/andrew/.nvm/versions/node/v22.22.0/bin/gemini"
    workdir = "/var/www/devbench"

    # Try Gemini CLI YOLO mode first (can write files)
    if os.path.exists(gemini_cli):
        try:
            result = subprocess.run(
                [gemini_cli, "-p", prompt_text, "-y", "-m", "gemini-2.5-flash"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=workdir,
            )
            output = result.stdout.strip()
            if result.stderr:
                stderr_clean = "\n".join(
                    l for l in result.stderr.split("\n")
                    if "YOLO mode" not in l and "Directory mismatch" not in l and l.strip()
                )
                if stderr_clean:
                    output += "\n" + stderr_clean
            success = result.returncode == 0 and len(output) > 0
            if success:
                return output, success
        except subprocess.TimeoutExpired:
            print("    Gemini CLI timed out, falling back to REST API...", file=sys.stderr)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"    Gemini CLI error: {e}", file=sys.stderr)

    # Fall back to REST API (ask_gemini.py with model rotation)
    script = Path("/var/www/devbench/scripts/ask_gemini.py")
    if not script.exists():
        return "ERROR: ask_gemini.py not found", False
    try:
        result = subprocess.run(
            ["python3", str(script), prompt_text],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip()
        success = result.returncode == 0 and len(output) > 0
        return output, success
    except subprocess.TimeoutExpired:
        return "TIMEOUT: Gemini took longer than 120 seconds", False
    except Exception as e:
        return f"ERROR: Gemini crashed: {e}", False


def get_best_gemini_model() -> str:
    """Determine the best available Gemini model."""
    script = Path("/var/www/devbench/scripts/ask_gemini.py")
    env_path = Path("/var/www/herbalist/.env")

    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key and env_path.exists():
        for line in env_path.read_text().splitlines():
            if "GOOGLE_API_KEY" in line and not line.startswith("#"):
                parts = line.split("=", 1)
                if len(parts) > 1:
                    key = parts[1].strip().strip("\"'")
                    break

    if not key:
        return "gemini-2.5-pro"

    # Try to fetch available models
    try:
        import json, urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        resp = urllib.request.urlopen(url, timeout=10)
        data = json.loads(resp.read())
        models = [m["name"].split("/")[-1] for m in data.get("models", [])
                  if "gemini" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]

        # Prioritize: 3.5 Flash (only working model) > 3.1 Pro > 3 Pro > 2.5 Pro
        for pref in ["gemini-3.5-flash", "gemini-3.1-pro", "gemini-3-pro", "gemini-2.5-pro", "gemini-3-flash-preview"]:
            for m in models:
                if m.startswith(pref) and "preview" in m:
                    return m
            for m in models:
                if m == pref:
                    return m
        return "gemini-2.5-pro"
    except Exception:
        return "gemini-2.5-pro"


def main():
    parser = argparse.ArgumentParser(description="Run Claude with Gemini fallback")
    parser.add_argument("--prompt", "-p", help="Prompt text (inline)")
    parser.add_argument("--output", "-o", required=True, help="Output file path")
    parser.add_argument("--workdir", "-w", default="/var/www/devbench", help="Working directory")
    parser.add_argument("--label", "-l", default="task", help="Task label for logging")
    args = parser.parse_args()

    # Get prompt from arg or stdin
    prompt_text = args.prompt
    if not prompt_text:
        prompt_text = sys.stdin.read().strip()
    if not prompt_text:
        print("ERROR: No prompt provided. Use --prompt or pipe stdin.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Try Claude first
    print(f"[{args.label}] Trying Claude Opus 4.8...", file=sys.stderr)
    claude_output, claude_ok = run_claude(prompt_text, args.workdir)

    if claude_ok:
        print(f"[{args.label}] Claude succeeded.", file=sys.stderr)
        with open(output_path, "w") as f:
            f.write(claude_output)
            f.write("\n\n---\n_Generated by: Claude Opus 4.8 (high effort)_\n")
        print(f"[{args.label}] Wrote to {output_path}", file=sys.stderr)
        return

    # Claude failed — fall back to Gemini
    print(f"[{args.label}] Claude FAILED. Falling back to Gemini...", file=sys.stderr)
    if claude_output:
        print(f"[{args.label}] Claude error: {claude_output[:200]}", file=sys.stderr)

    gemini_model = get_best_gemini_model()
    print(f"[{args.label}] Using Gemini model: {gemini_model}", file=sys.stderr)
    gemini_output, gemini_ok = run_gemini(prompt_text)

    if gemini_ok:
        print(f"[{args.label}] Gemini succeeded.", file=sys.stderr)
        with open(output_path, "w") as f:
            f.write(gemini_output)
            f.write(f"\n\n---\n_Generated by: Gemini {gemini_model} (Claude fallback)_\n")
        print(f"[{args.label}] Wrote to {output_path}", file=sys.stderr)
        return

    # Both failed
    print(f"[{args.label}] BOTH Claude and Gemini FAILED.", file=sys.stderr)
    with open(output_path, "w") as f:
        f.write(f"ERROR: Both Claude and Gemini failed for task '{args.label}'\n\n")
        f.write(f"Claude: {claude_output[:300]}\n\n")
        f.write(f"Gemini: {gemini_output[:300]}\n")
    print(f"[{args.label}] Error report written to {output_path}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()