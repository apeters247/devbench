#!/usr/bin/env python3
"""ask_gemini_lite.py — Call Gemini with a lite model to avoid quota limits."""
import json, os, sys, urllib.request
from pathlib import Path

def get_key():
    key = os.environ.get("GOOGLE_API_KEY", "")
    if key:
        return key
    for ep in [Path("/var/www/herbalist/.env"), Path("/var/www/devbench/.env")]:
        if ep.exists():
            for line in ep.read_text().splitlines():
                line = line.strip()
                if "GOOGLE_API_KEY" in line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) > 1:
                        key = parts[1].strip().strip("\"'")
                        if key:
                            return key
    return ""

models_to_try = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-3.1-flash-lite-preview"]

def ask(prompt, model):
    key = get_key()
    if not key:
        print("ERROR: No API key", file=sys.stderr)
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 8192}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200]
        print(f"  {model}: HTTP {e.code} - {err}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  {model}: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read().strip()
    if not prompt:
        print("ERROR: No prompt", file=sys.stderr)
        sys.exit(1)
    for model in models_to_try:
        print(f"Trying {model}...", file=sys.stderr)
        result = ask(prompt, model)
        if result:
            print(result)
            sys.exit(0)
    print("ERROR: All Gemini models failed", file=sys.stderr)
    sys.exit(1)
