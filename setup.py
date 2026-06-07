"""Compatibility shim for `pip install` / `pip install -e .`.

All real metadata lives in pyproject.toml (PEP 621). This file exists so that
older tooling and editable installs that still shell out to setup.py keep
working. setup() with no arguments reads everything from pyproject.toml.
"""

from setuptools import setup

setup()
