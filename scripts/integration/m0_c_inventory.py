"""Collect C-M0 seed inventory without asserting transport truth or changing inputs.

Use after audit_all; stdout is JSON. Exit 0 means inventory collected, not M0 passed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

from .provenance_audit import walk

ROOT = Path(__file__).resolve().parents[2]
CORE = ("TAW", "KOT", "MKK", "HUH", "EXC", "ADM")


def inventory():
    paths = {name: ROOT / f"contracts/seed/{name}.seed.json"
             for name in ("network", "event", "routes", "sim")}
    data = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    network, bundle, sim = (data[name] for name in ("network", "routes", "sim"))
    ledger_path = ROOT / "data/PROVENANCE.md"
    ledger = ledger_path.read_text(encoding="utf-8")
    nodes = {row["id"]: row for row in network["nodes"]}
    lines = {row["id"]: row for row in network["lines"]}
    routes = bundle["routes"]
    route_ids = {row["route_id"] for row in routes}
    source_rows = {parts[1].strip(): text for text in ledger.splitlines()
                   if len(parts := text.split("|")) > 2 and parts[1].strip().startswith("S")}
    # Ten field lookups, including explicitly unresolved fields. The ledger is
    # the evidence being inspected, not independent verification of its claims.
    started = time.perf_counter()
    samples = []
    for node in CORE:
        samples.append({"field": f"nodes[{node}].lat/lng", "value": [nodes[node]["lat"], nodes[node]["lng"]],
                        "provenance": nodes[node]["provenance"], "source_id": "S22",
                        "limitation": "Source supports station names/topology only; entrance coordinates unverified"})
    samples.extend([
        {"field": "lines[ERL].capacity_per_vehicle", "value": lines["ERL"]["capacity_per_vehicle"],
         "provenance": lines["ERL"]["provenance"], "source_id": "S5",
         "limitation": "No exact capacity evidence; ledger explicitly leaves ERL capacity pending"},
        {"field": "walk_links[ETS,TST].accessible",
         "value": next(row["accessible"] for row in network["walk_links"] if row["from"] == "ETS" and row["to"] == "TST"),
         "provenance": "real-derived", "source_id": "S5",
         "limitation": "Dataset family only; current continuous step-free path not verified"},
        {"field": "lines[BUS_982X].headway_s", "value": lines["BUS_982X"]["headway_s"],
         "provenance": lines["BUS_982X"]["provenance"], "source_id": "S20",
         "limitation": "Scheduled trips require service calendar join; null must not be replaced with invented frequency"},
        {"field": "lines[FERRY_TST_CEN].capacity_per_vehicle", "value": lines["FERRY_TST_CEN"]["capacity_per_vehicle"],
         "provenance": lines["FERRY_TST_CEN"]["provenance"], "source_id": "S15",
         "limitation": "Operator page did not publish vessel capacity; value remains pending"},
    ])
    for sample in samples:
        sample["ledger_row"] = source_rows.get(sample["source_id"])
        sample["verification"] = "UNVERIFIED"
    labels = {name: dict(Counter(row["provenance"] for _, row in walk(value) if "provenance" in row))
              for name, value in data.items()}
    hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in [*paths.values(), ledger_path, ROOT / "docs/plan/03-contracts.md"]}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": hashes,
        "scope": "Inventory only; no transport fact, official Schema or complete M0 acceptance asserted",
        "network": {"counts": {key: len(network[key]) for key in ("nodes", "lines", "walk_links")},
                    "modes": sorted({row["mode"] for row in network["lines"]}),
                    "core_nodes": [{"id": node, "kind": nodes[node]["kind"],
                                    "catchment_m": nodes[node].get("catchment_m"),
                                    "explicit_walk_links": [row for row in network["walk_links"] if node in (row["from"], row["to"])]}
                                   for node in CORE],
                    "entrance_records": [row for row in network["nodes"] if "entrance" in row.get("kind", "").lower()],
                    "gmb_481b_present": "GMB_481B" in lines,
                    "bs_tw_present": "BS_TW" in nodes,
                    "headways_pending": {key: lines[key]["headway_s"] for key in ("BUS_982X", "BUS_985B")}},
        "route_seed": {"cards": len(routes), "unique_ids": len(route_ids), "contract_target": 10,
                       "personas": [{"persona": row["persona"], "picks": len(row["top"]), "contract_target": 3,
                                     "unknown_refs": sorted(set(row["top"]) - route_ids)} for row in bundle["persona_top_picks"]]},
        "sim_seed": {"scenario_id": sim["scenario_id"], "placeholder": sim["meta"]["placeholder"],
                     "population": sim["population"],
                     "unknown_route_refs": sorted({row["route_id"] for section in ("baseline", "guided")
                                                   for key in ("route_load", "shares") for row in sim[section].get(key, [])} - route_ids),
                     "guided_assigned": sum(row["users"] for row in sim["guided"]["shares"]),
                     "guided_unmet": sim["guided"]["unstoppable_demand"]},
        "seed_provenance_labels": labels,
        "traceability_sample": {"count": len(samples), "local_lookup_s": time.perf_counter() - started,
                                "scope": "Local ledger lookup only; neither human timed review nor live source fetch", "rows": samples},
        "formal_schema_files": sorted(str(path.relative_to(ROOT)).replace("\\", "/") for path in (ROOT / "contracts/schemas").glob("*.json")),
        "data_access_files": sorted(str(path.relative_to(ROOT)).replace("\\", "/") for path in (ROOT / "data/access").glob("*.json")),
    }


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False, indent=2))
