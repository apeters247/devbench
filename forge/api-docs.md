# ConfigForge REST API — Developer Documentation

## Overview

ConfigForge exposes a zero-dependency REST API (stdlib only — no Flask, no FastAPI) for programmatic config file conversion. The server runs on a separate port from the web demo and serves JSON exclusively.

**Base URL (local):** `http://127.0.0.1:8081/`
**Base URL (production via nginx):** `https://naxiai.com/tools/devbench/api/`

---

## Endpoints

### `GET /`

API summary — lists all available endpoints.

```bash
curl http://127.0.0.1:8081/
```

Response:
```json
{
  "name": "ConfigForge API",
  "version": "0.1.0",
  "endpoints": [
    {"method": "POST", "path": "/api/v1/convert", "description": "Convert a config between formats"},
    {"method": "GET",  "path": "/api/v1/formats", "description": "List supported formats"},
    {"method": "GET",  "path": "/health",         "description": "Health check"},
    {"method": "GET",  "path": "/",               "description": "This summary"}
  ]
}
```

### `GET /health`

Liveness probe for monitoring and load balancers.

```bash
curl http://127.0.0.1:8081/health
```

Response:
```json
{
  "status": "ok",
  "models_count": 7,
  "tests_passing": 868
}
```

### `GET /api/v1/formats`

List all supported config formats.

```bash
curl http://127.0.0.1:8081/api/v1/formats
```

Response:
```json
{
  "success": true,
  "formats": ["json", "yaml", "toml", "xml", "csv", "ini", "env", "hcl", "properties"],
  "count": 9
}
```

### `POST /api/v1/convert`

Convert config content between formats.

**Request Body:** JSON object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | The config content to convert |
| `to_format` | string | Yes | Target format (one of: json, yaml, toml, xml, csv, ini, env, hcl, properties) |
| `from_format` | string | No | Source format (default: `auto` — auto-detect). Can be any supported format. |

**Success Response (200):**

```json
{
  "success": true,
  "output": "{\n  \"name\": \"test\",\n  \"version\": 1\n}",
  "input_format": "yaml",
  "output_format": "json",
  "error": null
}
```

**Error Response (400):** Missing/invalid fields, unsupported formats, or conversion failure.

```json
{
  "success": false,
  "output": "",
  "input_format": null,
  "output_format": "json",
  "error": "Missing required field: 'to_format'."
}
```

**Rate Limit Response (429):**

```json
{
  "success": false,
  "error": "Rate limit exceeded — max 60 requests per 60 seconds."
}
```

#### Examples

```bash
# YAML → JSON
curl -X POST http://127.0.0.1:8081/api/v1/convert \
  -H 'Content-Type: application/json' \
  -d '{"source": "server:\n  host: example.com\n  port: 443", "to_format": "json"}'

# JSON → TOML
curl -X POST http://127.0.0.1:8081/api/v1/convert \
  -H 'Content-Type: application/json' \
  -d '{"source": "{\"database\": {\"host\": \"localhost\", \"port\": 5432}}", "to_format": "toml"}'

# INI → YAML (explicit from_format)
curl -X POST http://127.0.0.1:8081/api/v1/convert \
  -H 'Content-Type: application/json' \
  -d '{"source": "[server]\nhost = example.com\nport = 8080", "to_format": "yaml", "from_format": "ini"}'
```

---

## CORS

All endpoints include CORS headers:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`
- `Access-Control-Max-Age: 86400`

Preflight requests (`OPTIONS`) return `204 No Content` with the above headers.

---

## Rate Limiting

- **Limit:** 60 requests per IP per 60-second rolling window
- **Scope:** Per-client IP (not global)
- **When exceeded:** Returns HTTP 429 with a JSON error body
- **Cleanup:** Background thread evicts stale IP entries every 60 seconds

---

## Error Codes

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad request (missing/invalid fields, unsupported format, conversion failure) |
| 404 | Unknown endpoint |
| 429 | Rate limit exceeded |
| 500 | Internal server error (should not happen) |

---

## Running the API

### Quick start

```bash
# Via CLI
python3 -m core.cli cf --api --api-port 8081

# Or standalone
python3 web/api.py --port 8081
```

### Systemd service (production)

Create `/etc/systemd/system/configforge-api.service`:

```ini
[Unit]
Description=ConfigForge REST API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/devbench
ExecStart=/usr/bin/python3 /var/www/devbench/web/api.py --port 8081
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now configforge-api.service
sudo systemctl status configforge-api.service
```

---

## Client Libraries (Example)

### Python

```python
import requests

def convert_config(source_text, to_format, from_format="auto"):
    resp = requests.post("http://127.0.0.1:8081/api/v1/convert", json={
        "source": source_text,
        "to_format": to_format,
        "from_format": from_format,
    })
    resp.raise_for_status()
    return resp.json()

result = convert_config("name: test", "toml")
print(result["output"])  # name = "test"
```

### cURL (shell script)

```bash
convert() {
    curl -s -X POST "http://127.0.0.1:8081/api/v1/convert" \
        -H 'Content-Type: application/json' \
        -d "{\"source\": $(printf '%s' "$1" | jq -Rs .), \"to_format\": \"$2\"}"
}
convert 'name: test' 'json'
```

### JavaScript (browser)

```javascript
async function convertConfig(source, toFormat) {
  const res = await fetch('https://naxiai.com/tools/devbench/api/api/v1/convert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, to_format: toFormat }),
  });
  return res.json();
}

convertConfig('name: test', 'json').then(r => console.log(r.output));
```

---

## Testing

```bash
# Full smoke test
curl -s http://127.0.0.1:8081/ | python3 -m json.tool | head -5
curl -s http://127.0.0.1:8081/health | python3 -m json.tool
curl http://127.0.0.1:8081/api/v1/formats   # → 9 formats
curl -s -X POST http://127.0.0.1:8081/api/v1/convert \
  -H 'Content-Type: application/json' \
  -d '{"source": "hello: world", "to_format": "json"}' | python3 -m json.tool
```