"""Reproducible [0,1] utility scores and template explanations."""
from copy import deepcopy
import math

CRITERIA = ("time", "transfers", "walk", "price", "comfort", "reliability", "carbon", "freshness")
PRESETS = {
    "fastest": (.45, .10, .10, .10, .05, .10, .05, .05),
    "most_stable": (.25, .10, .10, .05, .10, .35, .05, .05),
    "fewest_transfers": (.25, .35, .15, .05, .10, .05, .05, .05),
}


def clip(value):
    return max(0.0, min(1.0, value))


def score_routes(routes, profile, *, baseline_fare):
    if baseline_fare <= 0:
        raise ValueError("baseline_fare must be positive")
    preset = profile.get("preset", "fastest")
    if preset not in PRESETS:
        raise ValueError("Unknown preset")
    weights = profile.get("weights") or dict(zip(CRITERIA, PRESETS[preset]))
    if set(weights) - set(CRITERIA) or any(not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("Weights must be finite, nonnegative and use known criteria")
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        raise ValueError("Weights must have a positive sum")
    weights = {c: weights.get(c, 0) / weight_sum for c in CRITERIA}
    if not routes:
        return []
    tmin, tmax = min(r["total"]["time_s"] for r in routes), max(r["total"]["time_s"] for r in routes)
    co2max = max(r["total"]["co2_g"] for r in routes)
    walk_scale = profile.get("max_walk_m", max(1, max(r["total"]["walk_m"] for r in routes)))
    output = deepcopy(routes)
    for route in output:
        total = route["total"]
        model = route.get("_metrics")
        if model is None:
            previous = {row["criterion"]: row for row in route["score_breakdown"]}
            model = {"comfort": previous["comfort"]["raw"],
                     "freshness_score": previous["freshness"]["normalized"]}
        # Rescoring a public result must not duplicate previously generated notes.
        route["notes"] = []
        raw = {"time": total["time_s"], "transfers": total["transfers"], "walk": total["walk_m"],
               "price": total["fare_hkd"], "comfort": model["comfort"], "reliability": total["reliability"],
               "carbon": total["co2_g"], "freshness": total["freshness_s"]}
        normalized = {
            "time": 1 if tmin == tmax else 1 - (raw["time"] - tmin) / (tmax - tmin),
            "transfers": 1 / (1 + raw["transfers"]),
            "walk": 1 - raw["walk"] / walk_scale if walk_scale else 1,
            "price": 1 - raw["price"] / baseline_fare, "comfort": raw["comfort"],
            "reliability": raw["reliability"], "carbon": 1 - raw["carbon"] / co2max if co2max else 1,
            "freshness": model["freshness_score"],
        }
        route["score_breakdown"] = [{"criterion": c, "raw": raw[c], "normalized": clip(normalized[c]),
                                     "weight": weights[c], "contribution": weights[c] * clip(normalized[c])}
                                    for c in CRITERIA]
        route["score"] = sum(row["contribution"] for row in route["score_breakdown"])
        if total["walk_m"] > 500:
            route["notes"].append(f"Walking {total['walk_m']:g} m exceeds the 500 m soft preference.")
        if total["fare_hkd"] > baseline_fare * 1.3:
            route["notes"].append("Fare exceeds 1.3 times the configured baseline.")
        if raw["comfort"] < .3:
            route["notes"].append("Estimated comfort is low; prolonged standing may be required.")
        if any(leg["accessible"] is not True for leg in route["legs"]):
            route["notes"].append("Step-free access has not been confirmed for the entire journey.")
        route["explain"] = (f"{route['label']}: about {total['time_range_s'][0] / 60:.0f}–"
                            f"{total['time_range_s'][1] / 60:.0f} min, {total['transfers']} transfers, "
                            f"{total['walk_m']:g} m walking. Ranked with {preset} weights; carbon emissions and comfort are simulated estimates.")
    return sorted(output, key=lambda r: (-r["score"], r["total"]["time_s"], r["route_id"]))
