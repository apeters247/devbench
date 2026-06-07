# Deploy Web Demo — Checklist

## Overview

The ConfigForge web demo (`web/serve.py`) is a zero-dependency HTTP server that provides:
- An interactive config converter UI (paste → detect → convert → copy)
- JSON API endpoints at `/detect` and `/convert`
- CORS headers for cross-origin access
- A standalone `/demo/` route serving files from `demo/static/`

Two deployment modes: **standalone Python** (quick, for testing) and **nginx proxy** (production).

---

## Files to Deploy

| File | Purpose |
|------|---------|
| `web/serve.py` | Zero-dep HTTP server (the demo engine) |
| `demo/static/index.html` | Standalone HTML page (also served inline) |
| `demo/static/robots.txt` | Allows crawling of the demo |
| `web/robots.txt` | Allows crawling of web/ |
| `config/nginx-proxy-demo.conf` | Nginx proxy config snippet |
| `config/nginx.conf` | Nginx config for static landing page |

---

## Prerequisites

- Python 3.10+ (`python3` on PATH)
- nginx (for production proxy setup)
- Git (optional, for version tracking)

---

## Step 1 — Start the Web Demo

```bash
# Via the CLI (recommended)
cd /var/www/devbench
python3 -m core.cli cf --serve --port 8080

# Or standalone
python3 web/serve.py --port 8080
```

Expected output:
```
ConfigForge web UI running at http://127.0.0.1:8080/
Press Ctrl+C to stop.
```

## Step 2 — Verify Endpoints

```bash
# Interactive UI
curl -s http://127.0.0.1:8080/ | head -5
# → <!DOCTYPE html>...

# Health check
curl -s http://127.0.0.1:8080/health
# → {"ok": true}

# Format detection
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"source": "name: test\\nversion: 1"}' \
  http://127.0.0.1:8080/detect
# → {"format": "yaml"}

# Conversion
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"source": "name: test\\nversion: 1", "to_format": "json"}' \
  http://127.0.0.1:8080/convert
# → {"success": true, "output": "{\\n  \"name\": \"test\",\\n  \"version\": 1\\n}", ...}

# Demo page (standalone static file)
curl -s http://127.0.0.1:8080/demo/ | head -5
# → <!DOCTYPE html>...

# Robots.txt
curl -s http://127.0.0.1:8080/robots.txt
# → User-agent: *
# → Allow: /

# CORS headers present
curl -sI -X OPTIONS http://127.0.0.1:8080/ | grep -i access-control
# → Access-Control-Allow-Origin: *
```

## Step 3 — Nginx Proxy (Production)

Copy the proxy config into your naxiai.com nginx server block:

```bash
# Insert the contents of config/nginx-proxy-demo.conf before the catch-all
# location / block.

# Then test and reload:
sudo nginx -t
sudo systemctl reload nginx
```

This configures:
- `/tools/devbench/demo/` → proxied to `http://127.0.0.1:8080/demo/`
- `/tools/devbench/api/` → proxied to `http://127.0.0.1:8081/`

## Step 4 — Systemd Service (Auto-Start)

Create `/etc/systemd/system/configforge-demo.service`:

```ini
[Unit]
Description=ConfigForge Web Demo
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/devbench
ExecStart=/usr/bin/python3 /var/www/devbench/web/serve.py --port 8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now configforge-demo.service
sudo systemctl status configforge-demo.service
```

## Step 5 — Monitor

- Demo URL: `https://naxiai.com/tools/devbench/demo/`
- Check logs: `journalctl -u configforge-demo.service -f`

---

## Verification Command

```bash
# Full smoke test
echo "=== Demo UI ===" && curl -sI https://naxiai.com/tools/devbench/demo/ | head -5 && \
echo "=== API Health ===" && curl -s https://naxiai.com/tools/devbench/api/health && echo "" && \
echo "=== Formats ===" && curl -s https://naxiai.com/tools/devbench/api/api/v1/formats | python3 -m json.tool | head -10 && \
echo "=== Conversion ===" && curl -s -X POST https://naxiai.com/tools/devbench/api/api/v1/convert \
  -H 'Content-Type: application/json' \
  -d '{"source": "hello: world", "to_format": "json"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('success') else 'FAIL:', d.get('error',''))"
```

---

## Rollback

1. Remove the `location /tools/devbench/demo/` block from the nginx config
2. Stop: `sudo systemctl stop configforge-demo.service`
3. Disable: `sudo systemctl disable configforge-demo.service`