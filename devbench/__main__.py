"""``python3 -m devbench`` — delegates to the CLI entry point."""

from __future__ import annotations

import sys

from core.cli import entry_point

if __name__ == "__main__":
    sys.exit(entry_point())