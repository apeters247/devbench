#!/usr/bin/env python3
"""
Convert YAML/JSON5 to JSON. Note: JSON does not support comments, so they are lost.
JSON5 is a superset of JSON that allows comments, trailing commas, and unquoted keys.
"""

import yaml
import json
import re
import sys
from pathlib import Path
import jmespath

try:
    import json5
except ImportError:
    json5 = None


def check_yaml_features(yaml_text):
    """
    Check for YAML features that might be relevant for users.
    Returns a dict with information about detected features.
    """
    features = {
        'has_merge_tags': bool(re.search(r'(^|\\s)<<\\s*:', yaml_text, re.MULTILINE)),
        'has_anchors': bool(re.search(r'(^|\\s)&\\w+', yaml_text, re.MULTILINE)),
        'has_aliases': bool(re.search(r'(^|\\s)\\*\\w+', yaml_text, re.MULTILINE)),
    }
    return features


def main():
    if len(sys.argv) < 3:
        print("Usage: python yaml_to_json.py <input.yaml|json5> <output.json> [--query|-q <jmespath_expression>]")
        print("       If query is provided, only the matched data is output.")
        print("       Example: python yaml_to_json.py config.yaml output.json -q 'array[?name==`test`]')")
        sys.exit(1)

    # Parse arguments
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    # Check for query argument
    query_expr = None
    arg_index = 3
    while arg_index < len(sys.argv):
        if sys.argv[arg_index] in ('--query', '-q'):
            if arg_index + 1 >= len(sys.argv):
                print("Error: --query/-q requires an expression")
                sys.exit(1)
            query_expr = sys.argv[arg_index + 1]
            arg_index += 2
        else:
            arg_index += 1

    text = input_path.read_text()

    # Try to parse as YAML first (which also handles JSON)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        # If YAML parsing fails, try JSON5 if available
        if json5 is not None:
            try:
                data = json5.loads(text)
            except json5.JSON5DecodeError as e2:
                print(f"Error parsing input as YAML: {e}")
                print(f"Error parsing input as JSON5: {e2}")
                sys.exit(1)
        else:
            print(f"Error parsing YAML: {e}")
            print("JSON5 support not available. Install json5 package to enable JSON5 support.")
            sys.exit(1)

    # Check for YAML features and report if found
    features = check_yaml_features(text)
    if any(features.values()):
        feature_list = [k.replace('has_', '') for k, v in features.items() if v]
        print(f"Info: Input contains {', '.join(feature_list)}")
        if features['has_merge_tags']:
            print("  Note: Merge tags (<<) will be resolved during YAML parsing.")

    # Apply query if provided
    if query_expr is not None:
        try:
            data = jmespath.search(query_expr, data)
            if data is None:
                print(f"Warning: query '{query_expr}' returned null")
        except Exception as e:
            print(f"Error applying query '{query_expr}': {e}")
            sys.exit(1)

    output_path.write_text(json.dumps(data, indent=2))

    if query_expr:
        print(f"Converted {input_path} to {output_path} using query: {query_expr}")
    else:
        print(f"Converted {input_path} to {output_path}. Note: comments are lost in JSON conversion.")


if __name__ == '__main__':
    main()