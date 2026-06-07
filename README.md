# Devbench

> A macOS utility for developers who build, test, and ship Python tools with a native Mac UI.

Devbench is a **Python‑core + SwiftUI‑shell** application that lets you run Python scripts, manage virtual environments, and serve local web UIs — all from a polished macOS menu-bar app. No terminal juggling, no half-baked Electron wrappers.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  SwiftUI Shell                   │
│  Menu bar app · Preferences · Process mgmt      │
│  (macOS 14+, native Cocoa runtime)               │
├─────────────────────────────────────────────────┤
│                Python Core (CPython)             │
│  CLI backend · venv manager · HTTP server        │
│  (runs as a child process, communicates via IPC) │
└─────────────────────────────────────────────────┘
```

**Why two layers?**
- The **Python core** handles all the heavy lifting: spawning subprocesses, managing virtual environments, running an embedded HTTP server for the web UI, and exposing a JSON‑over‑stdin/stdout API.
- The **SwiftUI shell** provides a native macOS experience — dock icon, menu bar extras, system notifications, accessibility, and App Store compliance — without forcing Python into a GUI framework it was never designed for.

**IPC** is done via a simple request/response protocol over the process's stdin/stdout. The shell sends JSON commands; the core replies with JSON results. This keeps the two layers decoupled and testable in isolation.

---

## Project Structure

```
devbench/
├── core/                   # Python backend (runs on any OS)
│   ├── devbench/           # Main Python package
│   │   ├── __init__.py
│   │   ├── __main__.py     # Entry point: `python -m devbench`
│   │   ├── cli.py          # CLI argument parser (argparse/click)
│   │   ├── server.py       # Embedded HTTP server (web UI host)
│   │   ├── venv.py         # Virtual environment lifecycle
│   │   └── ipc.py          # JSON IPC protocol (stdin/stdout)
│   ├── tests/              # Pytest test suite
│   ├── requirements.txt    # Python dependencies
│   └── pyproject.toml      # Build config (PEP 621)
├── shell/                  # SwiftUI macOS app
│   ├── Devbench.xcodeproj  # Xcode project
│   ├── Sources/            # Swift source files
│   │   ├── App.swift
│   │   ├── MenuBarManager.swift
│   │   ├── IPCClient.swift # Talks to the Python core
│   │   └── ...
│   ├── Resources/          # Asset catalog, icons, etc.
│   └── Info.plist
├── web/                    # Landing / dashboard served at /tools/devbench/
│   ├── index.html
│   ├── styles.css
│   └── assets/
├── config/                 # Nginx, CI, and deployment configs
│   └── nginx.conf          # toxscreen.ai snippet for /tools/devbench/
├── TODO.md                 # Remaining tasks checklist
├── README.md               # This file
└── LICENSE
```

---

## How to Run the Core Locally (No Mac Needed)

The Python core is fully cross-platform and can be developed on Linux, macOS, or Windows.

### Prerequisites

- Python 3.11+
- `pip`

### Setup

```bash
cd devbench/core
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Run the CLI

```bash
python -m devbench --help
python -m devbench venv create my-project
python -m devbench serve --port 8080
```

The `serve` command starts the embedded HTTP server. Open `http://localhost:8080` in any browser to see the dashboard.

---

## How to Run Tests

```bash
cd devbench/core
source .venv/bin/activate
pytest tests/              # Unit + integration tests
pytest tests/ -v           # Verbose output
pytest tests/ --coverage   # Coverage report (requires pytest-cov)
```

Tests use `pytest` with `pytest-mock` and `pytest-asyncio` for async IPC tests. No macOS or Xcode dependencies required.

---

## How to Build for macOS (When Mac Mini Available)

### Prerequisites

- macOS 14+ (Sonoma or later)
- Xcode 15+
- A valid Apple Developer account

### Build the Python core (standalone executable)

```bash
cd devbench/core
pip install -r requirements.txt
pip install py2app
python setup.py py2app     # Produces dist/DevbenchCore.app
```

### Build the SwiftUI shell in Xcode

```bash
cd devbench/shell
xcodebuild -project Devbench.xcodeproj -scheme Devbench -configuration Release build
```

The resulting `.app` bundle embeds the Python core inside the `Contents/Resources/` directory.

### Sign & Notarize

See `TODO.md` — these steps require access to an Apple Developer ID certificate and are gated on acquiring a Mac Mini CI runner.

---

## Distribution Channels

| Channel          | URL / Details                                               |
|------------------|-------------------------------------------------------------|
| **Gumroad**      | `https://gumroad.com/l/devbench` *(coming soon)*            |
| **Mac App Store**| *(submission in progress — see TODO.md)*                    |
| **Stripe checkout (direct)** | `https://buy.stripe.com/...` *(direct license purchase)* |
| **Landing page** | [toxscreen.ai/tools/devbench/](https://toxscreen.ai/tools/devbench/) |
| **Source**       | Private repository (contact for access)                     |

---

## Links

- **Landing page:** https://toxscreen.ai/tools/devbench/
- **Gumroad listing:** *(coming soon — see TODO.md)*
- **Stripe checkout:** https://buy.stripe.com/... *(set up after launch)*
- **Product Hunt:** *(coming soon — see TODO.md)*
- **Hacker News:** *(coming soon — see TODO.md)*

---

## License

Proprietary. All rights reserved. See `LICENSE` file for terms.

---

*Built with Python, SwiftUI, and a borderline‑unhealthy number of espresso shots.*