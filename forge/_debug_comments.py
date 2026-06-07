"""Debug comment preservation flow."""
import sys
sys.path.insert(0, "/var/www/devbench")
from core.configforge import _extract_yaml_comments, _reinsert_yaml_comments, _extract_ini_comments, _reinsert_ini_comments

# Test YAML comment extraction + reinsertion standalone
yaml_src = "# Server configuration\nserver:\n  host: localhost  # Main hostname\n  port: 8080\n  tls: true\n"
comments = _extract_yaml_comments(yaml_src)
print(f"Extracted {len(comments)} YAML comments:")
for c in comments:
    print(f"  key={c['key']!r}, text={c['text']!r}, inline={c['is_inline']}, indent={c.get('indent')}")

# Test re-insertion into clean YAML output
clean_yaml = "server:\n  host: localhost\n  port: 8080\n  tls: true\n"
result = _reinsert_yaml_comments(clean_yaml, comments)
print(f"\nRe-inserted YAML:\n{result}")
print(f"Has # Server configuration: {'# Server configuration' in result}")
print(f"Has # Main hostname: {'# Main hostname' in result}")

print()

# Test INI standalone  
ini_src = "# Database settings\n[db]\nhost = localhost  # Server host\nport = 5432\n"
comments = _extract_ini_comments(ini_src)
print(f"Extracted {len(comments)} INI comments:")
for c in comments:
    print(f"  key={c['key']!r}, text={c['text']!r}, inline={c['is_inline']}")

clean_ini = "[db]\nhost = localhost\nport = 5432\n\n"
result = _reinsert_ini_comments(clean_ini, comments)
print(f"\nRe-inserted INI:\n{result}")
print(f"Has # Database settings: {'# Database settings' in result}")
print(f"Has # Server host: {'# Server host' in result}")