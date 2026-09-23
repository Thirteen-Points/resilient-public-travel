"""Lightweight HTTP smoke coverage for the six-node directed OD matrix.

This is an operational probe, not a performance test. It keeps one JSON result
in stdout and does not write one file per OD.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_NODES = ("TAW", "KOT", "MKK", "HUH", "EXC", "ADM")
DEFAULT_DEPART_AT = "2026-09-22T08:20:00+08:00"


def build_od_pairs(nodes: list[str] | tuple[str, ...]) -> list[tuple[str, str]]:
    unique = list(dict.fromkeys(node.strip() for node in nodes if node.strip()))
    if len(unique) < 2:
        raise ValueError("at least two OD nodes are required")
    return [(origin, destination) for origin in unique for destination in unique if origin != destination]


def summarize_response(status: int, body: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"http_status": status, "candidate_count": 0,
                           "provenance": [], "error": None}
    if status != 200:
        if isinstance(body, dict):
            error = body.get("error", body.get("detail", body))
        else:
            error = body
        row["error"] = str(error)
        return row
    if not isinstance(body, list):
        row["error"] = "route response is not an array"
        return row
    row["candidate_count"] = len(body)
    row["provenance"] = sorted({str(item.get("provenance")) for item in body
                                 if isinstance(item, dict) and item.get("provenance")})
    if not body:
        row["error"] = "no candidates returned"
    return row


def request_route(base_url: str, origin: str, destination: str, depart_at: str, timeout: float) -> dict[str, Any]:
    payload = json.dumps({"origin": origin, "destination": destination, "depart_at": depart_at}).encode()
    request = Request(base_url.rstrip("/") + "/api/routes/query", data=payload,
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return summarize_response(response.status, body)
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (OSError, ValueError):
            body = exc.reason
        return summarize_response(exc.code, body)
    except (OSError, URLError, ValueError) as exc:
        return {"http_status": None, "candidate_count": 0, "provenance": [],
                "error": f"{type(exc).__name__}: {exc}"}


def run(base_url: str, nodes: list[str], depart_at: str, timeout: float) -> dict[str, Any]:
    rows = []
    for origin, destination in build_od_pairs(nodes):
        result = request_route(base_url, origin, destination, depart_at, timeout)
        rows.append({"origin": origin, "destination": destination, **result})
    failures = [row for row in rows if row["http_status"] != 200]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "nodes": nodes,
        "od_count": len(rows),
        "failed_http_count": len(failures),
        "rows": rows,
        "scope": "simulated/offline smoke only; not a performance or real-data claim",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe each directed OD once; emit one JSON report")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--nodes", default=os.getenv("SMOKE_OD_NODES", ",".join(DEFAULT_NODES)),
                        help="comma-separated core node IDs; six defaults produce 30 directed ODs")
    parser.add_argument("--depart-at", default=os.getenv("SMOKE_DEPART_AT", DEFAULT_DEPART_AT))
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--output", type=Path, help="optional single JSON output path")
    args = parser.parse_args(argv)
    try:
        report = run(args.base_url, args.nodes.split(","), args.depart_at, args.timeout)
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["failed_http_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
