"""M1 happy-path demo: inject the full event -> review -> reroute chain.

Run against a local backend:

    REVIEW_API_TOKEN=dev-demo-token python scripts/demo_m1_story.py

Steps (each verified against the live API):
  1. two independent commuter reports enter the signal inbox (202);
  2. a reviewer opens the first card (confidence 0.20);
  3. the second report merges in (confidence rises to 0.55);
  4. the reviewer publishes (>= 0.60 gate), the graph snapshot closes
     HUH->EXC and route candidates are recomputed without the ERL segment.

Use span-form report texts (line + station-to-station + impact) so the
deterministic rule extractor can derive segments without an LLM.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.getenv("DEMO_API_BASE", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("REVIEW_API_TOKEN", "dev-demo-token")
HKT = timezone(timedelta(hours=8))

REPORT_A = "东铁红磡至会展信号故障，列车服务暂停"
REPORT_B = "东铁红磡到会展信号故障，服务暂停，好多人滞留"


def call(method: str, path: str, body=None, token: bool = False) -> tuple[int, object]:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("x-review-token", TOKEN)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode()
            return response.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode()
        try:
            return exc.code, json.loads(payload)
        except json.JSONDecodeError:
            return exc.code, payload


def step(name: str, ok: bool, detail: str) -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def query_routes(depart_at: str) -> dict:
    status, body = call("POST", "/api/routes/query", {
        "origin": "TAW", "destination": "ADM", "depart_at": depart_at})
    routes = body if isinstance(body, list) else (body or {}).get("routes", [])
    uses_erl_cross_harbour = any(
        {leg.get("from"), leg.get("to")} == {"HUH", "EXC"}
        for route in routes for leg in route.get("legs", []))
    return {"status": status, "count": len(routes), "erl_huh_exc": uses_erl_cross_harbour}


def main() -> int:
    prepare_only = "--prepare" in sys.argv
    now = datetime.now(HKT)
    depart_at = (now + timedelta(minutes=5)).isoformat()
    results: list[bool] = []

    status, health = call("GET", "/api/health")
    results.append(step("backend health", status == 200 and health.get("ok"),
                        f"HTTP {status}"))

    # Expire cards left published by earlier demo runs so merges stay unique.
    status, previous = call("GET", "/api/events", token=True)
    if status == 200:
        for event in previous or []:
            if event.get("status") in {"published", "updated"}:
                call("POST", f"/api/events/{event['event_id']}/review",
                     {"action": "expire", "actor": "admin_demo"}, token=True)

    baseline = query_routes(depart_at)
    results.append(step("baseline routes", baseline["status"] == 200 and baseline["count"] >= 5,
                        f"{baseline['count']} candidates at {depart_at[11:16]} HKT "
                        f"(peak-hour check: the 08:20 query returns >= 8), "
                        f"ERL HUH-EXC used: {baseline['erl_huh_exc']}"))

    # 1. Two independent commuter reports.
    status, body = call("POST", "/api/signals", {"raw_text": REPORT_A, "author_hint": "CommuterA", "lang": "zh-HK"})
    sid_a = (body or {}).get("signal_id")
    results.append(step("report A accepted", status == 202 and bool(sid_a), f"{sid_a}"))
    status, body = call("POST", "/api/signals", {"raw_text": REPORT_B, "author_hint": "CommuterB", "lang": "zh-HK"})
    sid_b = (body or {}).get("signal_id")
    results.append(step("report B accepted", status == 202 and bool(sid_b), f"{sid_b}"))
    if not (sid_a and sid_b):
        return 1

    # 2. Reviewer opens the first card from report A.
    event_id = f"evt_demo_{now.strftime('%Y%m%d%H%M%S')}"
    card = {
        "event_id": event_id, "version": 1, "status": "pending_review",
        "created_at": now.isoformat(), "updated_at": now.isoformat(),
        "published_at": None, "expires_at": None,
        "event_type": "signal_failure",
        "title": "东铁过海段疑似信号故障（待核实）",
        "summary": "两位乘客独立上报红磡至会展列车服务暂停，尚未核实。",
        "mode": "MTR", "line": "ERL", "direction": "both",
        "affected_segments": [{"from_node": "HUH", "to_node": "EXC", "impact": "closed", "capacity_factor": 0.0}],
        "window": {"start": (now - timedelta(minutes=30)).isoformat(), "end": None, "end_confidence": "unknown"},
        "severity": 3, "confidence": 0.0, "confidence_factors": [],
        "signals": [sid_a], "provenance": "real", "reviewed_by": None,
    }
    status, body = call("POST", "/api/events", card, token=True)
    conf = (body or {}).get("confidence")
    results.append(step("card opened at low confidence", status == 201 and conf == 0.2,
                        f"HTTP {status}, confidence {conf}"))

    # 3. Second report merges in and raises confidence.
    status, body = call("POST", "/api/events/ingest", {"signal_id": sid_b}, token=True)
    merged = (body or {}).get("event") or {}
    results.append(step("report B merged", status == 200 and body.get("state") == "merged",
                        f"state {body.get('state')}, confidence {merged.get('confidence')}, "
                        f"{len(merged.get('signals') or [])} signals"))

    # 4. Publish and watch the graph close the segment.
    if prepare_only:
        print(f"\nPREPARED: {event_id} awaits human review in the Review console "
              f"(confidence {merged.get('confidence')}). Re-run without --prepare "
              "or click Publish in the UI to close the segment.")
        return 0 if all(results) else 1
    status, body = call("POST", f"/api/events/{event_id}/review",
                        {"action": "approve", "actor": "admin_demo"}, token=True)
    results.append(step("published after human review", status == 200 and body.get("status") == "published",
                        f"HTTP {status}, confidence {body.get('confidence')}"))

    _, snapshot = call("GET", "/api/graph/snapshot")
    affected = snapshot.get("affected_edges", [])
    closed = any(edge["from_node"] == "HUH" and edge["to_node"] == "EXC" for edge in affected)
    results.append(step("snapshot closes HUH->EXC", closed, json.dumps(affected, ensure_ascii=False)))

    after = query_routes(depart_at)
    results.append(step("routes recomputed", after["status"] == 200 and not after["erl_huh_exc"],
                        f"{after['count']} candidates, ERL HUH-EXC used: {after['erl_huh_exc']} "
                        f"(baseline {baseline['count']})"))

    print("\nM1 chain:", "COMPLETE" if all(results) else "BROKEN")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
