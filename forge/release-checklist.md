# Release Checklist — Devbench / ConfigForge

## Overview

Checklist for publishing a new release of the `devbench` Python package to PyPI. The project uses `pyproject.toml` (PEP 621) with setuptools as the build backend.

---

## Step 1 — Version Bump

1. Update `pyproject.toml`:
   ```bash
   # Example: bump from 0.1.0 to 0.2.0
   sed -i 's/version = "0.1.0"/version = "0.2.0"/' pyproject.toml
   ```

2. Update version in `web/api.py`:
   ```bash
   sed -i 's/API_VERSION = "0.1.0"/API_VERSION = "0.2.0"/' web/api.py
   ```

3. Update version in `setup.py` (if present):
   ```bash
   sed -i 's/version="0.1.0"/version="0.2.0"/' setup.py
   ```

## Step 2 — Update Changelog

Create/edit `CHANGELOG.md`:

```markdown
# Changelog

## [0.2.0] - 2026-06-07

### Added
- ConfigForge web demo with interactive config converter UI
- REST API server (`--api` mode) with CORS, rate limiting
- CLI installer via pip/PyPI
- Support for 9 config formats (+HCL, +.properties)

### Fixed
- ... (list any fixes)
```

## Step 3 — Test the Package

```bash
# Full test suite
cd /var/www/devbench
python3 -m pytest tests/ -q --tb=line

# Build and install locally
python3 -m pip install -e .
python3 -m devbench --list

# Test from a clean temp directory
cd /tmp
python3 -m devbench cf --to json '{"test": 1}' 2>/dev/null || \
  echo '{"test": 1}' | python3 -m devbench cf --to json

# Test the API starts correctly
python3 -m core.cli cf --api --api-port 8083 &
sleep 1
curl -s http://127.0.0.1:8083/health | grep -q '"ok"'
kill %1 2>/dev/null

# Test the web demo starts correctly
python3 -m core.cli cf --serve --port 8093 &
sleep 1
curl -s http://127.0.0.1:8093/health | grep -q '"ok"'
kill %1 2>/dev/null
```

## Step 4 — Verify Pip Install

```bash
# From the project root
cd /var/www/devbench
python3 -m pip install -e .

# From a different directory
cd /tmp
python3 -m devbench --list
python3 -m devbench cf --help

# Clean install test (virtualenv)
cd /tmp
python3 -m venv /tmp/devbench_test
/tmp/devbench_test/bin/pip install -e /var/www/devbench
/tmp/devbench_test/bin/devbench --list
rm -rf /tmp/devbench_test
```

## Step 5 — Build the Package

```bash
cd /var/www/devbench

# Install build tools
python3 -m pip install --upgrade build twine

# Build wheel + source distribution
python3 -m build

# Check the package
python3 -m twine check dist/*

# Verify contents
tar tzf dist/devbench-*.tar.gz | head -20
```

## Step 6 — Upload to Test PyPI (optional)

```bash
python3 -m twine upload --repository testpypi dist/*

# Test install from Test PyPI
python3 -m pip install --index-url https://test.pypi.org/simple/ devbench
```

## Step 7 — Upload to PyPI

```bash
python3 -m twine upload dist/*
```

## Step 8 — Git Tag

```bash
cd /var/www/devbench
git tag -a "v$(grep '^version' pyproject.toml | head -1 | grep -oP '\d+\.\d+\.\d+')" -m "Release $(grep '^version' pyproject.toml | head -1 | grep -oP '\d+\.\d+\.\d+')"
git push origin --tags
```

## Step 9 — Update Install Script

The `scripts/install.sh` script can install from PyPI directly:

```bash
# Direct pip install (once on PyPI)
python3 -m pip install devbench

# Or from GitHub (current approach)
curl -sSL https://raw.githubusercontent.com/apeters247/devbench/master/scripts/install.sh | bash
```

## Step 10 — Deployment

After PyPI publish:

1. **Web demo:** `python3 web/serve.py --port 8080` (or systemd)
2. **REST API:** `python3 web/api.py --port 8081` (or systemd)
3. **Nginx:** Insert proxy config from `config/nginx-proxy-demo.conf`
4. **Verify:** Run the smoke tests from `forge/deploy-web-demo.md`

---

## Rollback

```bash
# Downgrade pip package
python3 -m pip install devbench==0.1.0

# Revert git tag
git tag -d v0.2.0
git push --delete origin v0.2.0

# Revert nginx config
sudo cp /etc/nginx/sites-available/naxiai.com.bak /etc/nginx/sites-available/naxiai.com
sudo nginx -t && sudo systemctl reload nginx
```