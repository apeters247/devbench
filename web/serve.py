#!/usr/bin/env python3
"""ConfigForge web UI — a zero-dependency local server.

Serves a single self-contained HTML page (all CSS/JS inline) that lets you
paste a config, auto-detects its format, and converts it to any supported
format using the existing ``core.configforge`` engine.

Run via the CLI:
    python3 -m core.cli cf --serve
    python3 -m core.cli cf --serve --port 9000

Or standalone:
    python3 web/serve.py
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Make ``core`` importable no matter the current working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core import configforge as cf  # noqa: E402

DEFAULT_PORT = 8080

# Reject request bodies larger than this to avoid trivial memory-exhaustion
# from a huge Content-Length. 10 MB is far above any real config payload.
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

# ---------------------------------------------------------------------------
# HTML page (everything inline — no external CSS/JS/fonts/assets)
# ---------------------------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ConfigForge — Config Converter</title>
<style>
  :root {
    --bg: #0f1117;
    --panel: #1a1d27;
    --border: #2a2e3c;
    --text: #e6e8ef;
    --muted: #8b90a1;
    --accent: #5b8cff;
    --accent-hover: #4a7bf0;
    --ok: #3ecf8e;
    --err: #ff6b6b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  header {
    padding: 20px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: baseline;
    gap: 12px;
  }
  header h1 { font-size: 20px; margin: 0; font-weight: 600; }
  header .sub { color: var(--muted); font-size: 13px; }
  main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }
  @media (max-width: 800px) { main { grid-template-columns: 1fr; } }
  .panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    min-height: 420px;
  }
  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    gap: 8px;
  }
  .panel-head label { font-size: 13px; color: var(--muted); font-weight: 600; }
  textarea {
    flex: 1;
    width: 100%;
    resize: vertical;
    background: #11131b;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    font-family: "SF Mono", ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
    font-size: 13px;
    line-height: 1.5;
    min-height: 320px;
    tab-size: 2;
  }
  textarea:focus { outline: none; border-color: var(--accent); }
  textarea[readonly] { background: #0d0f16; }
  .badge {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 20px;
    background: #232735;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .badge.detected { color: var(--ok); border-color: rgba(62,207,142,.4); }
  select {
    background: #11131b;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
  }
  select:focus { outline: none; border-color: var(--accent); }
  .controls {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: center;
    margin-top: -4px;
  }
  button {
    cursor: pointer;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    transition: background .15s ease;
  }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
  .btn-ghost { background: #232735; color: var(--text); border: 1px solid var(--border); }
  .btn-ghost:hover:not(:disabled) { background: #2c3142; }
  .status { font-size: 13px; min-height: 18px; }
  .status.ok { color: var(--ok); }
  .status.err { color: var(--err); }
  .field { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
  footer { text-align: center; color: var(--muted); font-size: 12px; padding: 16px; }
</style>
</head>
<body>
<header>
  <h1>ConfigForge</h1>
  <span class="sub">Paste a config, pick a target format, convert. Runs locally.</span>
</header>

<main>
  <section class="panel">
    <div class="panel-head">
      <label for="input">Input</label>
      <span id="detected" class="badge">format: —</span>
    </div>
    <textarea id="input" placeholder="Paste JSON, YAML, TOML, XML, CSV, INI, ENV, HCL, or .properties here…" spellcheck="false"></textarea>
  </section>

  <section class="panel">
    <div class="panel-head">
      <label for="output">Output</label>
      <button id="copy" class="btn-ghost" style="padding:4px 12px;font-size:12px;">Copy</button>
    </div>
    <textarea id="output" readonly placeholder="Converted output appears here…" spellcheck="false"></textarea>
  </section>

  <div class="controls">
    <div class="field">
      <span>Convert to</span>
      <select id="format">
        <option value="json">JSON</option>
        <option value="yaml">YAML</option>
        <option value="toml">TOML</option>
        <option value="xml">XML</option>
        <option value="csv">CSV</option>
        <option value="ini">INI</option>
        <option value="env">ENV</option>
        <option value="hcl">HCL</option>
        <option value="properties">Properties</option>
      </select>
    </div>
    <button id="convert" class="btn-primary">Convert</button>
    <button id="swap" class="btn-ghost">Swap</button>
    <span id="status" class="status"></span>
  </div>
</main>

<footer>ConfigForge · stdlib only · no data leaves your machine · 9 formats</footer>

<script>
(function () {
  "use strict";
  var input = document.getElementById("input");
  var output = document.getElementById("output");
  var format = document.getElementById("format");
  var detected = document.getElementById("detected");
  var statusEl = document.getElementById("status");
  var convertBtn = document.getElementById("convert");
  var copyBtn = document.getElementById("copy");
  var swapBtn = document.getElementById("swap");
  var detectTimer = null;

  function setStatus(msg, cls) {
    statusEl.textContent = msg || "";
    statusEl.className = "status" + (cls ? " " + cls : "");
  }

  function setDetected(fmt) {
    if (fmt && fmt !== "unknown") {
      detected.textContent = "format: " + fmt;
      detected.className = "badge detected";
    } else {
      detected.textContent = "format: —";
      detected.className = "badge";
    }
  }

  function post(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }

  function detect() {
    var text = input.value;
    if (!text.trim()) { setDetected(null); return; }
    post("/detect", { source: text })
      .then(function (d) { setDetected(d.format); })
      .catch(function () { setDetected(null); });
  }

  function scheduleDetect() {
    if (detectTimer) clearTimeout(detectTimer);
    detectTimer = setTimeout(detect, 250);
  }

  function convert() {
    var text = input.value;
    if (!text.trim()) { setStatus("Nothing to convert — paste a config first.", "err"); return; }
    convertBtn.disabled = true;
    setStatus("Converting…");
    post("/convert", { source: text, to_format: format.value, from_format: "auto" })
      .then(function (d) {
        if (d.success) {
          output.value = d.output;
          setDetected(d.input_format);
          setStatus(d.input_format + " → " + d.output_format + " ✓", "ok");
        } else {
          output.value = "";
          setStatus("Error: " + (d.error || "conversion failed"), "err");
        }
      })
      .catch(function (e) { setStatus("Request failed: " + e, "err"); })
      .finally(function () { convertBtn.disabled = false; });
  }

  function copyOutput() {
    if (!output.value) { setStatus("Nothing to copy.", "err"); return; }
    var done = function () {
      var orig = copyBtn.textContent;
      copyBtn.textContent = "Copied!";
      setTimeout(function () { copyBtn.textContent = orig; }, 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(output.value).then(done, function () {
        output.select(); document.execCommand("copy"); done();
      });
    } else {
      output.select(); document.execCommand("copy"); done();
    }
  }

  function swap() {
    if (!output.value && !input.value) { setStatus("Nothing to swap.", "err"); return; }
    // Exchange the two panes: the converted output becomes the new input
    // (and vice-versa), so you can immediately convert back the other way.
    var prevIn = input.value;
    var prevOut = output.value;
    input.value = prevOut;
    output.value = prevIn;
    setStatus("");
    detect();
  }

  // Auto-detect on paste (and on typing, debounced).
  input.addEventListener("paste", function () { setTimeout(detect, 0); });
  input.addEventListener("input", scheduleDetect);
  convertBtn.addEventListener("click", convert);
  copyBtn.addEventListener("click", copyOutput);
  swapBtn.addEventListener("click", swap);
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class ConfigForgeHandler(BaseHTTPRequestHandler):
    """Serves the single page and the JSON conversion/detection endpoints."""

    server_version = "ConfigForge/0.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002
        sys.stderr.write("  %s - %s\n" % (self.address_string(), fmt % args))

    # -- helpers ----------------------------------------------------------

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/health":
            self._send_json({"ok": True})
        elif path == "/robots.txt":
            self._send(200, b"User-agent: *\nAllow: /\n", "text/plain; charset=utf-8")
        elif path.startswith("/demo/"):
            self._handle_demo(path)
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_OPTIONS(self) -> None:  # noqa: N802
        # CORS preflight — empty 204 with the allow headers.
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors_headers()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            length = 0
        if length > MAX_BODY_SIZE:
            self._send_json(
                {"error": f"Request body too large (limit is {MAX_BODY_SIZE} bytes)."},
                status=413,
            )
            return
        if path in ("/detect", "/api/detect"):
            self._handle_detect()
        elif path in ("/convert", "/api/convert"):
            self._handle_convert()
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")

    def _handle_detect(self) -> None:
        body = self._read_json_body()
        # Accept either {source} (spec) or {text} (legacy).
        text = body.get("source", body.get("text", ""))
        if not isinstance(text, str):
            text = ""
        try:
            fmt = cf.detect_format(text) if text.strip() else "unknown"
        except Exception:
            fmt = "unknown"
        self._send_json({"format": fmt})

    def _handle_demo(self, path: str) -> None:
        """Serve files from the /demo/static/ directory."""
        from pathlib import Path as _Path
        demo_root = _Path(__file__).resolve().parent.parent / "demo" / "static"
        # Map /demo/index.html or /demo/ to the static index
        rel = path[len("/demo/"):] if path.startswith("/demo/") else path
        if not rel or rel == "index.html":
            rel = "index.html"
        target = demo_root / rel
        # Security: only serve files under demo/static/
        try:
            target.relative_to(demo_root)
        except ValueError:
            self._send(403, b"Forbidden", "text/plain; charset=utf-8")
            return
        if not target.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        try:
            body = target.read_bytes()
        except OSError:
            self._send(500, b"Server error", "text/plain; charset=utf-8")
            return
        # Simple content-type map
        ext = target.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }.get(ext, "application/octet-stream")
        self._send(200, body, ctype)

    def _handle_convert(self) -> None:
        body = self._read_json_body()
        # Spec field names: {source, to_format, from_format?}. Legacy: {text, to, from}.
        text = body.get("source", body.get("text", ""))
        to_fmt = body.get("to_format", body.get("to", "json"))
        from_fmt = body.get("from_format", body.get("from", "auto")) or "auto"

        if not isinstance(text, str) or not text.strip():
            self._send_json(self._convert_error("Empty input — paste a config first.", to_fmt))
            return
        if to_fmt not in cf.SUPPORTED_FORMATS:
            self._send_json(self._convert_error("Unsupported target format: %s" % to_fmt, to_fmt))
            return

        try:
            result = cf.convert(text, to_fmt, from_fmt)
        except Exception as e:  # defensive — convert() already traps most errors
            print(f"convert error: {e}", file=sys.stderr)
            self._send_json(self._convert_error("Internal server error", to_fmt))
            return

        self._send_json({
            "success": result.get("success", False),
            "output": result.get("output", ""),
            "error": result.get("error"),
            "input_format": result.get("input_format"),
            "output_format": result.get("output_format", to_fmt),
        })

    @staticmethod
    def _convert_error(message: str, to_fmt: str) -> dict:
        return {
            "success": False,
            "output": "",
            "error": message,
            "input_format": None,
            "output_format": to_fmt,
        }


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------


def run_server(port: int = DEFAULT_PORT, host: str = "127.0.0.1") -> int:
    """Start the ConfigForge web server. Blocks until interrupted."""
    try:
        httpd = ThreadingHTTPServer((host, port), ConfigForgeHandler)
    except OSError as e:
        print("Could not start server on %s:%d — %s" % (host, port, e), file=sys.stderr)
        return 1

    url = "http://%s:%d/" % (host, port)
    print("ConfigForge web UI running at %s" % url)
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="ConfigForge web UI")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (default: 8080)")
    ap.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    raise SystemExit(run_server(ap.parse_args().port, ap.parse_args().host))
