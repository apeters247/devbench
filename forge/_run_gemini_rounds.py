"""Run Gemini rounds 4, 5, 6 with full file context."""
import json, os, sys, urllib.request
from pathlib import Path

# ── API helper ──
def get_api_key():
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


def ask_gemini(prompt, model="gemini-2.5-flash", max_tokens=4096, timeout=60):
    key = get_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens}
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"ERROR: {e}"


# ── Read files ──
with open("/var/www/devbench/core/configforge.py") as f:
    cf = f.read()

with open("/var/www/devbench/tests/test_edge_cases.py") as f:
    te = f.read()

with open("/var/www/devbench/forge/user_complaints.md") as f:
    uc = f.read()

# ── ROUND 4 ──
prompt4 = (
    "Read the following ConfigForge source code line by line.\n"
    "Focus on: (1) CSV Dialect detection bugs, (2) TOML serializer unicode escaping,\n"
    "(3) XML namespace handling, (4) ENV parser edge cases with special chars.\n"
    "Give exact line numbers for every bug. Under 1000 words.\n\n"
    "CODE:\n```python\n" + cf + "\n```"
)

print("=== ROUND 4: Deep Read ===", flush=True)
r4 = ask_gemini(prompt4, timeout=120)
print(f"Got {len(r4)} chars", flush=True)
with open("/var/www/devbench/forge/gemini-deepread-4.md", "w") as f:
    f.write(r4)

# ── ROUND 5 ──
prompt5 = (
    "Read the following user complaints and ConfigForge source code.\n"
    "For each of the 15 pain points in the complaints, say whether ConfigForge addresses it.\n"
    "Rank the remaining gaps by user impact. Recommend the top 5 things to build.\n"
    "Under 800 words.\n\n"
    "USER COMPLAINTS:\n```markdown\n" + uc[:8000] + "\n```\n\n"
    "CONFIGFORGE CODE:\n```python\n" + cf[:10000] + "\n```"
)

print("=== ROUND 5: Priorities ===", flush=True)
r5 = ask_gemini(prompt5)
print(f"Got {len(r5)} chars", flush=True)
with open("/var/www/devbench/forge/gemini-priorities-5.md", "w") as f:
    f.write(r5)

# ── ROUND 6 ──
prompt6 = (
    "Read the following test file for a config converter that supports "
    "json, yaml, toml, xml, csv, ini, env formats.\n"
    "What conversion paths are NOT tested? List every missing (from_format, to_format) pair.\n"
    "Are there tests for: empty files, binary data, BOM, unicode RTL, NaN, Infinity,\n"
    "extremely deep nesting, 10K+ line files, concurrent access? Under 1000 words.\n\n"
    "TEST FILE:\n```python\n" + te[:12000] + "\n```"
)

print("=== ROUND 6: Coverage ===", flush=True)
r6 = ask_gemini(prompt6)
print(f"Got {len(r6)} chars", flush=True)
with open("/var/www/devbench/forge/gemini-coverage-6.md", "w") as f:
    f.write(r6)

print("ALL 3 GEMINI ROUNDS DONE", flush=True)