#!/usr/bin/env python3
"""ask_gemini.py — Call Google Gemini API directly. No proxy, no middleware.

Usage:
    python3 ask_gemini.py "Your prompt for Gemini"
    python3 ask_gemini.py "Review this code for bugs"

Returns response text to stdout. Exits 1 on error.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path


def get_api_key():
    """Get GOOGLE_API_KEY from env or .env file."""
    key = os.environ.get("GOOGLE_API_KEY", "")
    if key:
        return key
    for env_path in [Path("/var/www/herbalist/.env"), Path("/var/www/devbench/.env")]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if "GOOGLE_API_KEY" in line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) > 1:
                        key = parts[1].strip().strip("\"'")
                        if key:
                            return key
    print("ERROR: GOOGLE_API_KEY not found", file=sys.stderr)
    sys.exit(1)


def ask_gemini(prompt, model="gemini-2.5-flash"):
    """Send prompt to Gemini and return response text.
    Auto-retries with progressively simpler models on 429.
    """
    fallback_chain = [
        model,
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
    ]
    seen = set()
    for attempt_model in fallback_chain:
        if attempt_model in seen:
            continue
        seen.add(attempt_model)
        key = get_api_key()
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + attempt_model + ":generateContent?key=" + key
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 8192}
        }).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("Gemini 429 on " + attempt_model + " — trying simpler model", file=sys.stderr)
                continue
            err = e.read().decode()
            print("Gemini HTTP " + str(e.code) + " on " + attempt_model + ": " + err[:200], file=sys.stderr)
            continue
        except Exception as e:
            print("Gemini error on " + attempt_model + ": " + str(e), file=sys.stderr)
            continue
    print("All Gemini models exhausted (429 on all)", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ask_gemini.py <prompt>", file=sys.stderr)
        sys.exit(1)
    result = ask_gemini(" ".join(sys.argv[1:]))
    print(result)