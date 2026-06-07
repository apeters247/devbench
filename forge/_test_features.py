"""Verify comment preservation and type inference features."""
import json
import sys
sys.path.insert(0, "/var/www/devbench")
from core.configforge import convert

# YAML → JSON → YAML round-trip with comment preservation
yaml_src = "# Server configuration\nserver:\n  host: localhost  # Main hostname\n  port: 8080\n  tls: true\n"
r = convert(yaml_src, "json", preserve_comments=True)
assert r["success"], f"YAML→JSON failed: {r.get('error')}"

# Carry comments through to the next conversion
comments = r.get("_comments", [])
r2 = convert(r["output"], "yaml", _carry_comments=comments)
yaml_round = r2["output"]
print("YAML round-trip:")
print(yaml_round)
has_top = "# Server configuration" in yaml_round
has_inline = "# Main hostname" in yaml_round
if has_top:
    print("  ✓ Top comment preserved")
else:
    print("  ✗ Top comment MISSING")
if has_inline:
    print("  ✓ Inline comment preserved")
else:
    print("  ✗ Inline comment MISSING")

# INI → JSON → INI round-trip
ini_src = "# Database settings\n[db]\nhost = localhost  # Server host\nport = 5432\n"
r = convert(ini_src, "json", preserve_comments=True)
assert r["success"]
comments = r.get("_comments", [])
r2 = convert(r["output"], "ini", _carry_comments=comments)
ini_round = r2["output"]
print("\nINI round-trip:")
print(ini_round)
if "# Database settings" in ini_round:
    print("  ✓ Top INI comment preserved")
else:
    print("  ✗ Top INI comment MISSING")
if "# Server host" in ini_round:
    print("  ✓ INI inline comment preserved")
else:
    print("  ✗ INI inline comment MISSING")

# Type inference
src = "[types]\ncount=42\nratio=3.14\nenabled=true\nname=hello\n"
r = convert(src, "json")
data = json.loads(r["output"])
checks = []
checks.append(type(data["types"]["count"]) == int)
checks.append(type(data["types"]["ratio"]) == float)
checks.append(data["types"]["enabled"] is True)
checks.append(type(data["types"]["name"]) == str)
print(f"\nType inference: {sum(checks)}/4 correct")

# Summary
ok = all(checks) and has_top and has_inline
print(f"\n{'='*40}")
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")