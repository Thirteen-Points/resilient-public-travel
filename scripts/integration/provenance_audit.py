"""Read-only fixture provenance and seven C-Data review-item audit."""
from pathlib import Path
import hashlib
import json

def walk(value, path="$"):
    if isinstance(value, dict):
        yield path, value
        for key, item in value.items():
            yield from walk(item, path+"."+key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, f"{path}[{index}]")

def fixture_issues(value):
    labels = [(path, row["provenance"]) for path,row in walk(value) if "provenance" in row]
    if not labels:
        return [{"path":"$", "reason":"No simulated provenance in fixture"}]
    return [{"path":path, "reason":f"Fixture provenance is {label!r}, expected simulated"}
            for path,label in labels if label != "simulated"]

def audit_provenance(root):
    root = Path(root)
    fixture_paths = set()
    for directory in ("backend", "tests", "data/sim"):
        for path in (root / directory).rglob("*.json"):
            if "fixtures" in path.parts or "synthetic" in path.name or "simulated" in path.name or directory == "data/sim":
                fixture_paths.add(path)
    rows = []
    for path in sorted(fixture_paths):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            issues = fixture_issues(data)
        except (ValueError, OSError) as exc:
            issues = [{"path":"$", "reason":str(exc)}]
        rows.append({"file":path.relative_to(root).as_posix(),
                     "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                     "status":"FAIL" if issues else "PASS", "issues":issues})
    raw_seed_claims = []
    for path in sorted((root / "contracts/seed").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for pointer, row in walk(data):
            if row.get("provenance") == "real":
                notes = " ".join(str(v) for k,v in row.items() if "note" in k)
                raw_seed_claims.append({"file":path.relative_to(root).as_posix(), "path":pointer,
                    "id":row.get("id", row.get("route_id", row.get("line"))),
                    "status":"FAIL" if "待核实" in notes else "UNVERIFIED",
                    "reason":"Marked real despite pending verification" if "待核实" in notes else
                             "Field-level real claim needs human source verification; ledger presence alone is insufficient"})
    network = json.loads((root / "contracts/seed/network.seed.json").read_text(encoding="utf-8"))
    lines = {line["id"]:line for line in network["lines"]}
    seven = [
        {"item":"ERL train capacity", "local_ref":"network.lines[ERL].capacity_per_vehicle",
         "label":lines.get("ERL",{}).get("provenance"), "status":"FAIL" if lines.get("ERL",{}).get("provenance")=="real" else "UNVERIFIED"},
        {"item":"ETS-TST accessible walking link", "local_ref":"network.walk_links[ETS,TST]",
         "label":next((w.get("provenance") for w in network["walk_links"] if w["from"]=="ETS" and w["to"]=="TST"), None),
         "status":"UNVERIFIED"},
        {"item":"88K operational status", "local_ref":"routes.excluded_route_examples only; no active network line", "status":"UNVERIFIED"},
        {"item":"80M possible cancellation", "local_ref":"Absent from local C-Data payload", "status":"BLOCKED"},
        {"item":"BUS_170 complete stops", "local_ref":"network.missing_nodes_note only; no BUS_170 line", "status":"BLOCKED"},
        {"item":"GMB_481B complete stops", "local_ref":"network.lines[GMB_481B] references absent BS_TW",
         "label":lines.get("GMB_481B",{}).get("provenance"), "status":"FAIL" if lines.get("GMB_481B",{}).get("provenance")=="real" else "UNVERIFIED"},
        {"item":"Bus headways", "local_ref":"network.lines[BUS_*]",
         "labels":{k:v.get("provenance") for k,v in lines.items() if k.startswith("BUS_")}, "status":"UNVERIFIED"},
    ]
    checks = [
        {"name":"fixture.provenance", "status":"FAIL" if not rows or any(r["issues"] for r in rows) else "PASS",
         "detail":f"{len(rows)} JSON fixtures/results audited; inline negative-test mutations excluded"},
        {"name":"raw_seed.real_claims", "status":"FAIL" if any(r["status"]=="FAIL" for r in raw_seed_claims) else ("UNVERIFIED" if raw_seed_claims else "PASS"),
         "detail":f"{len(raw_seed_claims)} real labels need source verification; seed adapter relabelling does not repair raw files"},
        {"name":"C_Data.seven_item_ledger", "status":"UNVERIFIED" if (root/"data/DATA_QUALITY.md").is_file() else "BLOCKED",
         "detail":"Ledger present; seven field-level confirmations are not certified by file presence" if (root/"data/DATA_QUALITY.md").is_file() else "C-Data quality ledger is absent; local seeds only"},
    ]
    return {"checks":checks,"fixtures":rows,"raw_seed_real_claims":raw_seed_claims,"seven_review_items":seven}
