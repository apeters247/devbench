#!/usr/bin/env python3
"""ConfigForge REST API — a zero-dependency JSON HTTP server.

Exposes ``core.configforge.convert()`` (and friends) over a small REST API
built entirely on the Python standard library — no Flask, no third-party
dependencies. Same pattern as ``web/serve.py`` (which serves the browser UI),
but this module is purely a JSON API and runs on its own port.

Endpoints:
    POST /api/v1/convert   {source, to_format, from_format?}  -> conversion
    GET  /api/v1/formats                                      -> supported formats
    GET  /health                                              -> liveness probe
    GET  /                                                    -> API summary

Run via the CLI:
    python3 -m core.cli cf --api
    python3 -m core.cli cf --api --port 8081

Or standalone:
    python3 web/api.py --port 8081

Features:
    * CORS headers on every response (browser-callable).
    * Simple in-memory per-IP rate limiting (60 requests/minute).
    * All responses are JSON (Content-Type: application/json).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Make ``core`` importable no matter the current working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core import configforge as cf  # noqa: E402

DEFAULT_PORT = 8081
API_VERSION = "0.1.0"

# Static health-check facts (kept in sync with the project's headline numbers).
MODELS_COUNT = 7
TESTS_PASSING = 771

# Rate limiting: max requests per IP within a rolling window.
RATE_LIMIT_MAX = 60        # requests
RATE_LIMIT_WINDOW = 60.0   # seconds


# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-IP — not Redis)
# ---------------------------------------------------------------------------


class RateLimiter:
    """Sliding-window request counter keyed by client IP.

    Holds ``{ip: [timestamps]}`` and trims entries older than the window. A
    background thread periodically evicts stale IPs so the dict doesn't grow
    without bound. Thread-safe (the server is threaded).
    """

    def __init__(self, max_requests: int = RATE_LIMIT_MAX, window: float = RATE_LIMIT_WINDOW) -> None:
        self.max_requests = max_requests
        self.window = window
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, ip: str, now: float | None = None) -> bool:
        """Record a request for ``ip``; return False if over the limit."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        with self._lock:
            hits = self._hits[ip]
            # Drop timestamps outside the current window.
            hits[:] = [t for t in hits if t > cutoff]
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True

    def cleanup(self, now: float | None = None) -> None:
        """Evict IPs whose timestamps have all aged out of the window."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        with self._lock:
            for ip in list(self._hits):
                self._hits[ip][:] = [t for t in self._hits[ip] if t > cutoff]
                if not self._hits[ip]:
                    del self._hits[ip]

    def start_cleanup_thread(self) -> threading.Thread:
        """Spawn a daemon thread that calls :meth:`cleanup` every window."""
        def _loop() -> None:
            while True:
                time.sleep(self.window)
                try:
                    self.cleanup()
                except Exception as exc:  # noqa: BLE001 — keep daemon thread alive
                    # Log the exception type only — mirror the HIGH-5 generic
                    # error pattern and avoid echoing raw exception detail
                    # (which can carry environment/context) into the logs.
                    print(
                        f"api-rate-cleanup: cleanup failed ({type(exc).__name__})",
                        file=sys.stderr,
                    )

        thread = threading.Thread(target=_loop, name="api-rate-cleanup", daemon=True)
        thread.start()
        return thread


# A single shared limiter instance for the handler class.
RATE_LIMITER = RateLimiter()


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class ConfigForgeAPIHandler(BaseHTTPRequestHandler):
    """Routes the JSON REST API. All responses are JSON with CORS headers."""

    server_version = "ConfigForgeAPI/" + API_VERSION

    # Shared limiter — overridable in tests.
    rate_limiter = RATE_LIMITER

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002
        sys.stderr.write("  %s - %s\n" % (self.address_string(), fmt % args))

    # -- low-level senders ------------------------------------------------

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        # HEAD has no body, but we only call this from GET/POST/OPTIONS.
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json_body(self) -> tuple[dict | None, str | None]:
        """Read and parse the request body as a JSON object.

        Returns ``(data, None)`` on success or ``(None, error_message)`` when
        the body is missing or malformed.
        """
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return None, "Request body is empty — expected a JSON object."
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return None, f"Invalid JSON body: {e}"
        if not isinstance(data, dict):
            return None, "JSON body must be an object."
        return data, None

    # -- rate limiting ----------------------------------------------------

    def _rate_limited(self) -> bool:
        """Return True (and send a 429) if this client is over the limit."""
        ip = self.client_address[0] if self.client_address else "unknown"
        if not self.rate_limiter.allow(ip):
            self._send_json(
                {
                    "success": False,
                    "error": "Rate limit exceeded — max %d requests per %d seconds."
                    % (self.rate_limiter.max_requests, int(self.rate_limiter.window)),
                },
                status=429,
            )
            return True
        return False

    # -- routing ----------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802 (http.server API)
        # CORS preflight — empty 204 with the allow headers.
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self._rate_limited():
            return
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        try:
            if path == "/":
                self._handle_root()
            elif path == "/health":
                self._handle_health()
            elif path == "/api/v1/formats":
                self._handle_formats()
            else:
                self._send_json({"success": False, "error": "Not found: %s" % path}, status=404)
        except Exception as e:  # defensive — never leak a stack trace as HTML
            self._send_json({"success": False, "error": "Internal error: %s" % e}, status=500)

    def do_POST(self) -> None:  # noqa: N802
        if self._rate_limited():
            return
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        try:
            if path == "/api/v1/convert":
                self._handle_convert()
            else:
                self._send_json({"success": False, "error": "Not found: %s" % path}, status=404)
        except Exception as e:  # defensive catch-all -> 500
            self._send_json({"success": False, "error": "Internal error: %s" % e}, status=500)

    # -- handlers ---------------------------------------------------------

    def _handle_root(self) -> None:
        self._send_json({
            "name": "ConfigForge API",
            "version": API_VERSION,
            "endpoints": [
                {"method": "POST", "path": "/api/v1/convert", "description": "Convert a config between formats"},
                {"method": "GET", "path": "/api/v1/formats", "description": "List supported formats"},
                {"method": "GET", "path": "/health", "description": "Health check"},
                {"method": "GET", "path": "/", "description": "This summary"},
            ],
        })

    def _handle_health(self) -> None:
        self._send_json({
            "status": "ok",
            "models_count": MODELS_COUNT,
            "tests_passing": TESTS_PASSING,
        })

    def _handle_formats(self) -> None:
        self._send_json({
            "success": True,
            "formats": list(cf.SUPPORTED_FORMATS),
            "count": len(cf.SUPPORTED_FORMATS),
        })

    def _handle_convert(self) -> None:
        data, err = self._read_json_body()
        if err is not None:
            self._send_json(self._convert_error(err, None), status=400)
            return

        source = data.get("source")
        to_format = data.get("to_format")
        from_format = data.get("from_format", "auto") or "auto"

        # Validate required fields.
        if not isinstance(source, str) or not source.strip():
            self._send_json(
                self._convert_error("Missing or empty required field: 'source'.", to_format),
                status=400,
            )
            return
        if not isinstance(to_format, str) or not to_format:
            self._send_json(
                self._convert_error("Missing required field: 'to_format'.", to_format),
                status=400,
            )
            return
        if to_format not in cf.SUPPORTED_FORMATS:
            self._send_json(
                self._convert_error(
                    "Unsupported target format: %r. Supported: %s"
                    % (to_format, ", ".join(cf.SUPPORTED_FORMATS)),
                    to_format,
                ),
                status=400,
            )
            return
        if from_format != "auto" and from_format not in cf.SUPPORTED_FORMATS:
            self._send_json(
                self._convert_error(
                    "Unsupported source format: %r. Supported: %s (or 'auto')."
                    % (from_format, ", ".join(cf.SUPPORTED_FORMATS)),
                    to_format,
                ),
                status=400,
            )
            return

        # Delegate to the engine. convert() traps its own exceptions and
        # returns {success: False, error: ...} on failure.
        result = cf.convert(source, to_format, from_format)

        payload = {
            "success": bool(result.get("success", False)),
            "output": result.get("output", ""),
            "input_format": result.get("input_format"),
            "output_format": result.get("output_format", to_format),
            "error": result.get("error"),
        }
        # A failed conversion (bad/garbage input) is a client error -> 400.
        status = 200 if payload["success"] else 400
        self._send_json(payload, status=status)

    @staticmethod
    def _convert_error(message: str, to_format) -> dict:
        return {
            "success": False,
            "output": "",
            "input_format": None,
            "output_format": to_format,
            "error": message,
        }


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------


def run_server(port: int = DEFAULT_PORT, host: str = "127.0.0.1") -> int:
    """Start the ConfigForge REST API server. Blocks until interrupted."""
    try:
        httpd = ThreadingHTTPServer((host, port), ConfigForgeAPIHandler)
    except OSError as e:
        print("Could not start API server on %s:%d — %s" % (host, port, e), file=sys.stderr)
        return 1

    # Start the periodic rate-limiter cleanup.
    ConfigForgeAPIHandler.rate_limiter.start_cleanup_thread()

    url = "http://%s:%d/" % (host, port)
    print("ConfigForge REST API running at %s" % url)
    print("  POST /api/v1/convert   GET /api/v1/formats   GET /health")
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

    ap = argparse.ArgumentParser(description="ConfigForge REST API")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port (default: 8081)")
    ap.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = ap.parse_args()
    raise SystemExit(run_server(args.port, args.host))
