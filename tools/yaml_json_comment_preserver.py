#!/usr/bin/env python3
"""
YAML to JSON converter that attempts to preserve comments.
"""

import json
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq, CommentedMap

def yaml_to_json_with_comments(yaml_str):
    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(yaml_str)

    # TODO: Extract comments from data and store them in a separate structure.
    # For now, we just dump the data to JSON, which loses comments.
    json_str = json.dumps(data, indent=2)
    return json_str

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python yaml_to_json_with_comments.py <input.yaml>")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        yaml_str = f.read()

    json_str = yaml_to_json_with_comments(yaml_str)
    print(json_str)