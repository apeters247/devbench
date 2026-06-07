"""
Devbench — Developer tools library.

This is a re-export wrapper that makes ``python3 -m devbench`` and
``import devbench`` work.  All actual implementation lives in
the ``core`` package — this module shadows the PyPI project name
so the import path matches ``pip install devbench``.

Usage::

    $ devbench cf --help              # console_scripts entry point
    $ python3 -m devbench cf --help   # module entry (this wrapper)
"""

from __future__ import annotations

import core as _core

# Re-export everything from core so that ``from devbench import ...`` works
# the same as ``from core import ...``.
from core import *  # noqa: F401,F403
from core import __version__, cli, detector, models, tools

__all__ = _core.__all__ + ["cli", "detector", "models", "tools"]