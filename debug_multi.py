#!/usr/bin/env python3
"""Debug multi-doc YAML detection."""
import sys, json, re
sys.path.insert(0, '/var/www/devbench')
from core.configforge import HAS_YAML, detect_format

yaml_multi = '''---
apiVersion: v1
kind: Pod
metadata:
  name: pod-a
---
apiVersion: v1
kind: Service
metadata:
  name: svc-b
'''

print(f'HAS_YAML = {HAS_YAML}')
print(f'starts with ---: {yaml_multi.strip().startswith("---")}')
print(f'":" in text: {":" in yaml_multi}')

# Direct yaml.safe_load test
import yaml
try:
    result = yaml.safe_load(yaml_multi)
    print(f'yaml.safe_load result: {result}')
except Exception as e:
    print(f'yaml.safe_load error: {e}')

# What about safe_load_all?
try:
    docs = list(yaml.safe_load_all(yaml_multi))
    print(f'yaml.safe_load_all result ({len(docs)} docs): {docs}')
except Exception as e:
    print(f'yaml.safe_load_all error: {e}')

# Step by step in detect_format
text = yaml_multi.strip()
lines = text.strip().split("\n")
print(f'\nStep by step:')
for line in lines:
    ls = line.strip()
    m1 = bool(re.match(r"^[\w\-\"]+:\s", ls))
    m2 = (ls == "---")
    if m1 or m2:
        print(f'  MATCH: {repr(ls[:50])} key_pat={m1} sep={m2}')
        break

# Now manual detect
fmt = detect_format(yaml_multi)
print(f'\ndetect_format result: {fmt}')
