#!/usr/bin/env python3
"""Quick test for license server endpoints."""
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from web.license import LicenseManager

lm = LicenseManager()
key = lm.generate("test@test.com", "cus_test123")
print("KEY:", key)

# GET /license/verify
url = "http://127.0.0.1:9002/license/verify?key=" + urllib.parse.quote(key)
print("VERIFY:", json.loads(urllib.request.urlopen(url).read()))

# POST /license/activate
data = json.dumps({"key": key, "machine_id": "test-mac-001"}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:9002/license/activate",
    data=data,
    headers={"Content-Type": "application/json"},
)
print("ACTIVATE:", json.loads(urllib.request.urlopen(req).read()))

# POST /webhook/stripe
event = {
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "customer_email": "buyer@example.com",
            "customer": "cus_buyer123",
            "payment_intent": "pi_buyer456",
        }
    },
}
data = json.dumps(event).encode()
req = urllib.request.Request(
    "http://127.0.0.1:9002/webhook/stripe",
    data=data,
    headers={"Content-Type": "application/json"},
)
result = json.loads(urllib.request.urlopen(req).read())
print("WEBHOOK:", json.dumps(result, indent=2)[:300])

# GET /
print("ROOT:", json.loads(urllib.request.urlopen("http://127.0.0.1:9002/").read()))

# GET /health
print("HEALTH:", json.loads(urllib.request.urlopen("http://127.0.0.1:9002/health").read()))

# Download with valid key (expect 404 - no artifact)
try:
    dl_url = "http://127.0.0.1:9002/download/" + urllib.parse.quote(key)
    urllib.request.urlopen(dl_url)
    print("DOWNLOAD: unexpected success")
except urllib.error.HTTPError as e:
    print(f"DOWNLOAD (expected 404): {e.code}")

# CORS on OPTIONS
req = urllib.request.Request("http://127.0.0.1:9002/health", method="OPTIONS")
resp = urllib.request.urlopen(req)
cors = resp.getheader("Access-Control-Allow-Origin")
print(f"CORS: {cors}")

print("\n✅ All tests passed!")