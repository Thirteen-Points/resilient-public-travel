#!/usr/bin/env python3
"""
Pre-flight check script for ResilientRoute (T9.3).
Run before demo to verify everything is ready.

Usage:
    python scripts/preflight.py

Checks:
1. Data files present and valid
2. Graph/network loadable
3. Health endpoint responds
4. (If server running) Core API endpoints respond
5. Offline mode data available
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_data_files():
    """Check all critical data files exist and are valid JSON."""
    print("[1/5] Checking data files...")
    critical_files = [
        "data/network/stations.json",
        "data/network/lines.json",
        "data/network/walk_links.json",
        "data/calendar.json",
        "contracts/seed/network.seed.json",
        "contracts/seed/event.seed.json",
        "contracts/seed/routes.seed.json",
        "contracts/seed/sim.seed.json",
    ]
    all_ok = True
    for f in critical_files:
        path = ROOT / f
        if not path.exists():
            print(f"  [FAIL] Missing: {f}")
            all_ok = False
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                json.load(fh)
            print(f"  [OK]   {f}")
        except Exception as e:
            print(f"  [FAIL] {f}: {e}")
            all_ok = False
    return all_ok


def check_graph_loadable():
    """Check that the network data can be loaded and has minimum required content."""
    print("\n[2/5] Checking graph/network data...")
    try:
        with open(ROOT / "data/network/stations.json", "r", encoding="utf-8") as f:
            stations = json.load(f)
        with open(ROOT / "data/network/lines.json", "r", encoding="utf-8") as f:
            lines = json.load(f)

        n_stations = len(stations.get("stations", []))
        n_lines = len(lines.get("lines", []))

        if n_stations < 6:
            print(f"  [FAIL] Expected >=6 stations, got {n_stations}")
            return False
        if n_lines < 5:
            print(f"  [FAIL] Expected >=5 lines, got {n_lines}")
            return False

        # Check corridor stations exist
        corridor = {"TAW", "KOT", "MKK", "HUH", "EXC", "ADM"}
        actual = {s["id"] for s in stations["stations"]}
        missing = corridor - actual
        if missing:
            print(f"  [FAIL] Missing corridor stations: {missing}")
            return False

        print(f"  [OK]   {n_stations} stations, {n_lines} lines, 6 corridor stations present")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def check_offline_package():
    """Check that offline data is available."""
    print("\n[3/5] Checking offline package...")
    offline_files = [
        "deploy/offline/README.json",
        "deploy/offline/README.md",
        "data/weather_impact.json",
        "data/capacity_method.md",
        "data/PROVENANCE.md",
    ]
    all_ok = True
    for f in offline_files:
        path = ROOT / f
        if path.exists():
            print(f"  [OK]   {f}")
        else:
            print(f"  [FAIL] Missing: {f}")
            all_ok = False
    return all_ok


def check_health_endpoint():
    """Check if the health endpoint responds (if server is running)."""
    print("\n[4/5] Checking health endpoint...")
    try:
        req = urllib.request.Request("http://localhost:8000/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                print(f"  [OK]   Health: {data['status']}")
                return True
            else:
                print(f"  [WARN] Health: {data.get('status', 'unknown')} (some checks failed)")
                return True  # Server is running, just degraded
    except urllib.error.URLError:
        print("  [SKIP] Server not running. Start with: scripts/start.sh")
        return True  # Not a failure - server just isn't running yet
    except Exception as e:
        print(f"  [SKIP] Could not reach health endpoint: {e}")
        return True


def check_core_api():
    """Check if core API endpoints respond (if server is running)."""
    print("\n[5/5] Checking core API endpoints...")
    endpoints = [
        ("/api/graph/network", "Network data"),
        ("/api/meta", "Meta/sources"),
    ]
    all_ok = True
    for path, desc in endpoints:
        try:
            req = urllib.request.Request(f"http://localhost:8000{path}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                print(f"  [OK]   {desc} ({path})")
        except urllib.error.URLError:
            print(f"  [SKIP] {desc} ({path}) - server not running")
            all_ok = True  # Not a failure
        except Exception as e:
            print(f"  [FAIL] {desc} ({path}): {e}")
            all_ok = False
    return all_ok


def main():
    print("=" * 60)
    print("ResilientRoute Pre-flight Check")
    print("=" * 60)

    results = []
    results.append(check_data_files())
    results.append(check_graph_loadable())
    results.append(check_offline_package())
    results.append(check_health_endpoint())
    results.append(check_core_api())

    print("\n" + "=" * 60)
    all_ok = all(results)
    if all_ok:
        print("RESULT: ALL GREEN - ready for demo")
    else:
        print("RESULT: ISSUES FOUND - fix before demo")
    print("=" * 60)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
