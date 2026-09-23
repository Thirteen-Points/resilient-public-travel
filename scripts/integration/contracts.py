"""Consumer contract checks from docs/plan/03-contracts.md; no production fields added.

These assertions complement, and do not replace, B's official JSON Schemas.
Unknown extension fields are preserved. All data values arrive through the adapter.
"""
from datetime import datetime
import math
from urllib.parse import urlsplit

from .checks import Finding

MODES = ["MTR", "BUS", "MINIBUS", "WALK", "FERRY"]
PROVENANCE = ["real", "real-derived", "simulated"]
CRITERIA = ["time", "transfers", "walk", "price", "comfort", "reliability", "carbon", "freshness"]


def spec(kind, **options):
    return dict(type=kind, **options)


def array(items, minimum=0):
    return spec("array", items=items, min_items=minimum)


def obj(properties, optional=()):
    return spec("object", properties=properties,
                required=[key for key in properties if key not in optional])


TEXT = spec("string", nonempty=True)
NUMBER = spec("number", minimum=0)
UNIT = spec("number", minimum=0, maximum=1)
INTEGER = spec("integer", minimum=0)
BOOL = spec("boolean")
TIME = spec("string", datetime=True)
NULL_TIME = spec(["string", "null"], datetime=True)
PROV = spec("string", enum=PROVENANCE)
MODE = spec("string", enum=MODES)
STRINGS = array(TEXT)
WEIGHTS = obj({key: UNIT for key in CRITERIA})
SEGMENT = obj({"from_node": TEXT, "to_node": TEXT,
               "impact": spec("string", enum=["closed", "reduced_capacity", "slow", "crowded"]),
               "capacity_factor": UNIT})
AUDIT = obj({"at": TIME, "actor": TEXT, "action": TEXT, "confidence_after": UNIT})
FACTOR = obj({"factor": TEXT, "weight": UNIT, "score": UNIT, "note": TEXT})
LEG = obj({"mode": MODE, "line": TEXT, "from": TEXT, "to": TEXT, "depart": TEXT, "arrive": TEXT,
           "headway_s": NUMBER, "in_vehicle_s": NUMBER,
           "walk_m": NUMBER, "fare_hkd": NUMBER, "accessible": BOOL, "provenance": PROV},
          optional=("line", "depart", "arrive", "headway_s", "fare_hkd"))
TOTAL = obj({"time_s": NUMBER, "time_range_s": spec("array", items=NUMBER, length=2),
             "transfers": INTEGER, "walk_m": NUMBER, "fare_hkd": NUMBER, "co2_g": NUMBER,
             "reliability": UNIT, "freshness_s": NUMBER})
SCORE_TERM = obj({"criterion": spec("string", enum=CRITERIA), "raw": NUMBER,
                  "normalized": UNIT, "weight": UNIT, "contribution": UNIT})
EVIDENCE = obj({"event_id": TEXT, "used": BOOL, "source": TEXT, "freshness_s": NUMBER},
               optional=("event_id", "used", "source", "freshness_s"))
LOAD = obj({"route_id": TEXT, "users_on_route": INTEGER, "capacity_per_hour": NUMBER,
            "load_factor": NUMBER, "expected_wait_s": NUMBER, "board_refusal_prob": UNIT,
            "overloaded": BOOL})
FAIRNESS = obj({"max_extra_delay_min": NUMBER, "protected_users": INTEGER, "note": TEXT})
METRIC = obj({"policy": TEXT, "total_delay_person_min": NUMBER, "p95_wait_min": NUMBER,
              "overloaded_routes": INTEGER, "served_rate": UNIT,
              "unstoppable_demand": INTEGER, "wheelchair_served_rate": UNIT},
             optional=("unstoppable_demand", "wheelchair_served_rate"))

CONTRACTS = {
    "Signal": obj({"signal_id": TEXT, "received_at": TIME, "source_type": TEXT,
                   "source_name": TEXT, "raw_text": TEXT, "lang": TEXT, "provenance": PROV}),
    "Event": obj({"event_id": TEXT, "version": spec("integer", minimum=1),
                  "status": spec("string", enum=["draft", "pending_review", "published", "updated", "expired", "rejected"]),
                  "created_at": TIME, "updated_at": TIME, "published_at": NULL_TIME, "expires_at": NULL_TIME,
                  "event_type": spec("string", enum=["signal_failure", "train_failure", "door_fault", "power_failure", "weather", "crowd", "road_incident", "other"]),
                  "title": TEXT, "summary": TEXT, "mode": MODE, "line": TEXT, "direction": TEXT,
                  "affected_segments": array(SEGMENT, 1),
                  "window": obj({"start": TIME, "end": NULL_TIME, "end_confidence": TEXT}),
                  "severity": INTEGER, "confidence": UNIT, "confidence_factors": array(FACTOR),
                  "signals": STRINGS, "reviewed_by": spec(["string", "null"]), "audit_log": array(AUDIT),
                  "provenance": PROV}),
    "UserProfile": obj({"user_id": TEXT,
                        "persona": spec("string", enum=["commuter", "student", "tourist", "elderly", "wheelchair"]),
                        "mobility": spec("string", enum=["standard", "reduced", "wheelchair"]),
                        "walking_speed_mps": spec("number", exclusive_minimum=0),
                        "max_walk_m": NUMBER, "max_transfers": INTEGER, "price_sensitive": UNIT,
                        "has_discount_card": BOOL, "urgency": TEXT,
                        "preset": spec("string", enum=["fastest", "most_stable", "fewest_transfers"]),
                        "weights": WEIGHTS, "hard_flags": STRINGS, "note": TEXT}),
    "RouteCandidate": obj({"route_id": TEXT, "label": TEXT, "legs": array(LEG, 1),
                           "total": TOTAL, "score": UNIT, "score_breakdown": array(SCORE_TERM, 3),
                           "warnings": STRINGS, "notes": STRINGS, "explain": TEXT,
                           "evidence": array(EVIDENCE, 1), "provenance": PROV,
                           "load_estimate": obj({key: value for key, value in LOAD["properties"].items()
                                                 if key not in ("route_id", "overloaded")})},
                          optional=("load_estimate",)),
    "LoadEstimate": LOAD,
    "DiversionPlan": obj({"plan_id": TEXT, "event_id": TEXT, "demand": INTEGER,
                          "window_min": spec("number", exclusive_minimum=0),
                          "shares": array(obj({"route_id": TEXT, "share": UNIT, "users": INTEGER,
                                               "capacity_per_hour": NUMBER, "load_factor": NUMBER})),
                          "unstoppable_demand": INTEGER, "advice": STRINGS, "fairness": FAIRNESS, "provenance": PROV}),
    "SimResult": obj({"scenario_id": TEXT, "population": INTEGER,
                      "time_range": spec("array", items=TEXT, length=2),
                      "baseline": METRIC, "guided": METRIC,
                      "delta": obj({"delay_reduction_pct": spec("number"),
                                    "p95_wait_reduction_pct": spec("number")}),
                      "assumptions": array(TEXT, 1), "provenance": PROV}),
    "Meta": obj({"generated_at": TIME, "graph_snapshot": TEXT,
                 "sources": array(obj({"name": TEXT, "last_ok": TIME, "provenance": PROV,
                                       "url": TEXT}, optional=("url",)), 1), "disclaimer": TEXT}),
    "Snapshot": obj({"snapshot_id": TEXT, "affected_edges": array(spec("any"))}),
    "Health": obj({"ok": BOOL, "sources": array(spec("any"))}),
    "Error": obj({"error": obj({"code": TEXT, "message": TEXT, "fallback": TEXT})}),
}


def _matches(value, kind):
    if kind == "any":
        return True
    if kind == "number":
        return type(value) in (int, float) and math.isfinite(value)
    if kind == "integer":
        return type(value) is int
    return {"object": isinstance(value, dict), "array": isinstance(value, list),
            "string": isinstance(value, str), "boolean": type(value) is bool,
            "null": value is None}.get(kind, False)


def _walk(value, rule, path, findings):
    kinds = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
    def fail(code, message):
        findings.append(Finding(code, path, message))
    if not any(_matches(value, kind) for kind in kinds):
        fail("TYPE", "Expected " + "/".join(kinds))
        return
    if value is None:
        return
    if "enum" in rule and value not in rule["enum"]:
        fail("ENUM", "Unknown contract enum")
    if isinstance(value, dict):
        for key in rule.get("required", []):
            if key not in value:
                findings.append(Finding("REQUIRED", path + "." + key, "Missing consumer contract field"))
        for key, child in rule.get("properties", {}).items():
            if key in value:
                _walk(value[key], child, path + "." + key, findings)
    elif isinstance(value, list):
        if len(value) < rule.get("min_items", 0) or ("length" in rule and len(value) != rule["length"]):
            fail("LENGTH", "Unexpected array length")
        for index, item in enumerate(value):
            _walk(item, rule.get("items", spec("any")), f"{path}[{index}]", findings)
    elif isinstance(value, str):
        if rule.get("nonempty") and not value.strip():
            fail("EMPTY", "Expected non-empty string")
        if rule.get("datetime"):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.utcoffset() is None:
                    raise ValueError("Missing timezone")
            except ValueError:
                fail("DATETIME", "Expected timezone-aware ISO date-time")
    elif type(value) in (int, float):
        if "minimum" in rule and value < rule["minimum"]:
            fail("RANGE", "Below minimum")
        if "exclusive_minimum" in rule and value <= rule["exclusive_minimum"]:
            fail("RANGE", "Must exceed minimum")
        if "maximum" in rule and value > rule["maximum"]:
            fail("RANGE", "Above maximum")


def validate_payload(kind, payload):
    if kind not in CONTRACTS:
        return [Finding("UNSUPPORTED", kind, "No registered consumer contract")]
    findings = []
    _walk(payload, CONTRACTS[kind], kind, findings)
    if not findings and kind == "RouteCandidate":
        for index, evidence in enumerate(payload["evidence"]):
            if not (evidence.get("event_id") or evidence.get("source")):
                findings.append(Finding("EVIDENCE", f"{kind}.evidence[{index}]", "Expected event or source reference"))
        for index, leg in enumerate(payload["legs"]):
            # Walking has no scheduled service; a zero headway is valid.
            # Preserve positive headway validation for actual transit legs.
            if leg["mode"] != "WALK" and "headway_s" in leg and leg["headway_s"] <= 0:
                findings.append(Finding("RANGE", f"{kind}.legs[{index}].headway_s", "Transit headway must exceed zero"))
            if leg["mode"] != "WALK" and not leg.get("line"):
                findings.append(Finding("REQUIRED", f"{kind}.legs[{index}].line", "Transit leg needs line"))
    return findings


RESPONSES = {
    ("GET", "/api/events"): ("Event", True),
    ("GET", "/api/events/published"): ("Event", True),
    ("POST", "/api/events/ingest"): ("Event", False),
    ("POST", "/api/routes/query"): ("RouteCandidate", True),
    ("POST", "/api/sim/load"): ("DiversionPlan", False),
    ("GET", "/api/sim/result"): ("SimResult", False),
    ("GET", "/api/personas"): ("UserProfile", True),
    ("GET", "/api/graph/snapshot"): ("Snapshot", False),
    ("GET", "/api/meta"): ("Meta", False),
    ("GET", "/api/health"): ("Health", False),
}


def validate_response(method, url, status, payload):
    """Check actual decoded response bodies; never rename keys or fix values."""
    if type(status) is not int or not 100 <= status <= 599:
        return [Finding("STATUS", "response", "Invalid HTTP status")]
    if status >= 400:
        return validate_payload("Error", payload)
    if not 200 <= status < 300:
        return [Finding("STATUS", "response", "Expected success or contracted error")]
    path = urlsplit(url).path
    endpoint = (method.upper(), path)
    if method.upper() == "POST" and path.startswith("/api/events/") and path.endswith("/review"):
        response = ("Event", False)
    else:
        response = RESPONSES.get(endpoint)
    if response is None:
        return [Finding("UNSUPPORTED", path, "Response contract not registered; do not assume PASS")]
    kind, many = response
    if not many:
        return validate_payload(kind, payload)
    if not isinstance(payload, list):
        return [Finding("TYPE", path, "Public response must be an array")]
    findings = []
    for index, item in enumerate(payload):
        for finding in validate_payload(kind, item):
            findings.append(Finding(finding.code, f"{path}[{index}].{finding.path}", finding.message))
    return findings
