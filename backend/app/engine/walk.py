"""Offline walking estimates. Distances are metres, durations seconds."""
import math


def distance_m(a, b):
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat, dlon = lat2 - lat1, math.radians(b["lng"] - a["lng"])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def walking_seconds(distance, speed_mps=1.4):
    if not math.isfinite(speed_mps) or speed_mps <= 0 or distance < 0:
        raise ValueError("Walking speed must be positive and distance nonnegative")
    return distance / speed_mps


def walking_matrix(nodes, *, radius_m=800, detour_factor=1.3, speed_mps=1.4):
    """Estimates only: these pairs are NOT automatically traversable graph links."""
    if detour_factor < 1:
        raise ValueError("detour_factor must be >= 1")
    return [{"from": a["id"], "to": b["id"], "walk_m": round(d, 2),
             "walk_s": round(walking_seconds(d, speed_mps), 2), "provenance": "simulated" if any(n.get("provenance", "simulated") == "simulated" for n in (a, b)) else "real-derived",
             "note": "Straight-line distance multiplied by a detour factor; walking links and accessibility are unverified."}
            for a in nodes for b in nodes if a["id"] != b["id"]
            if (d := distance_m(a, b) * detour_factor) <= radius_m]
