"""Debug CSV detection flow."""
from core.configforge import detect_format
import re

text = 'name,description,price\nWidget,"High quality, durable widget",19.99\n'
t = text.strip()

print("=== Detection debug ===")
print("Starts with { or [:", t.startswith('{') or t.startswith('['))

p1 = r'^\[[\w\-\"]+\]'
print("TOML section test:", bool(re.search(p1, t, re.MULTILINE)))

p2 = r'^[\w\-]+\s*=\s*(?:\"|\'|\d+|true|false|\[|\{)'
print("TOML bare test:", bool(re.search(p2, t, re.MULTILINE)))

print("INI section:", bool(re.search(r'^\[.*\]$', t, re.MULTILINE)))
print("INI key=:", bool(re.search(r'^[\w]+\s*=', t, re.MULTILINE)))
print("ENV test:", bool(re.search(r'^[A-Z_][A-Z0-9_]*=', t, re.MULTILINE)))
print("YAML colon:", ':' in t)
print("YAML key:value pattern:", bool(re.match(r'^[\w\-"]+:\s', t)))

# CSV detection
lines = t.split('\n')
non_empty = [l for l in lines if l.strip()]
print("Lines:", lines)
print("Non-empty:", non_empty)
print("Count non-empty:", len(non_empty))

for delim in [',', '\t', '|', ';']:
    if len(non_empty) >= 2:
        fc = non_empty[0].count(delim)
        rest = non_empty[1:3]
        rest_ok = all(l.count(delim) == fc for l in rest)
        d_repr = repr(delim)
        print("delim:", d_repr, "first_count:", fc, "rest:", rest, "ok:", rest_ok)

print("Final detect:", detect_format(text))