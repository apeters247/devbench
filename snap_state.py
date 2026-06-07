#!/usr/bin/env python3
"""snap_state.py — Take a project state snapshot for the shared plan.

Usage: python3 snap_state.py
Writes to: snapshots/YYYY-MM-DD-HHMM-state.json
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path("/var/www/devbench")

def run(cmd, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kw)
        return r.stdout, r.stderr, r.returncode
    except Exception as e:
        return "", str(e), -1

def parse_test_summary(text):
    """Extract pass/fail/skip counts from pytest output."""
    passed = 0
    failed = 0
    skipped = 0
    m = re.search(r"(\d+) passed", text)
    if m: passed = int(m.group(1))
    m = re.search(r"(\d+) failed", text)
    if m: failed = int(m.group(1))
    m = re.search(r"(\d+) skipped", text)
    if m: skipped = int(m.group(1))
    return passed, failed, skipped

def snapshot():
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_short = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")

    # Test suites — auto-discover all test_*.py files
    suites = {}
    test_dir = PROJECT / "tests"
    test_files = sorted(test_dir.glob("test_*.py"))
    if not test_files:
        test_files = [test_dir / "test_configforge.py", test_dir / "test_core.py", test_dir / "test_edge_cases.py"]
    for f in test_files:
        out, err, rc = run(["python3", "-m", "pytest", str(f), "-q", "--tb=line"])
        p, fl, s = parse_test_summary(out)
        suites[os.path.basename(f)] = {"passed": p, "failed": fl, "skipped": s, "exit": rc}

    # File stats
    cf_size = (PROJECT / "core/configforge.py").stat().st_size
    tools_size = (PROJECT / "core/tools.py").stat().st_size
    total_lines = 0
    total_files = 0
    for py in PROJECT.rglob("*.py"):
        if "__pycache__" not in str(py):
            total_files += 1
            total_lines += len(py.read_text().splitlines())

    # LiteLLM status
    llm_out, llm_err, llm_rc = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:4000/models"], timeout=5)
    litellm_ok = llm_out.strip() == "200"

    # Failed tests detail
    all_failures = []
    for suite_name, data in suites.items():
        if data["failed"] > 0:
            # Re-run just failures to get names
            out2, _, _ = run(["python3", "-m", "pytest", f"tests/{suite_name}", "-q", "--tb=line", "--lf"])
            for line in out2.splitlines():
                if line.startswith("FAILED"):
                    all_failures.append(line.replace("FAILED ", ""))

    data = {
        "timestamp": timestamp,
        "suites": suites,
        "total": {
            "passed": sum(s["passed"] for s in suites.values()),
            "failed": sum(s["failed"] for s in suites.values()),
            "skipped": sum(s["skipped"] for s in suites.values()),
        },
        "failures": all_failures,
        "files": {
            "configforge_py_size": cf_size,
            "tools_py_size": tools_size,
            "total_py_files": total_files,
            "total_py_lines": total_lines,
        },
        "infra": {
            "litellm_running": litellm_ok,
        },
    }

    out_path = PROJECT / "snapshots" / f"{ts_short}-state.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(json.dumps(data, indent=2))
    return data

if __name__ == "__main__":
    snapshot()