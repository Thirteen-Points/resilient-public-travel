"""Hard constraints shared by search and integrations."""
import math


def normalize_profile(profile=None):
    p = dict(profile or {})
    mobility = p.setdefault("mobility", "standard")
    if mobility not in {"standard", "reduced", "wheelchair"}:
        raise ValueError("Unknown mobility")
    limited = mobility != "standard"
    p.setdefault("walking_speed_mps", 0.7 if limited else 1.4)
    if limited:
        p.setdefault("max_walk_m", 400)
    p.setdefault("max_transfers", 3)
    for key in ("walking_speed_mps", "max_transfers", *(["max_walk_m"] if "max_walk_m" in p else [])):
        if not isinstance(p[key], (int, float)) or not math.isfinite(p[key]) or p[key] < 0:
            raise ValueError(f"Invalid {key}")
    if p["walking_speed_mps"] == 0 or int(p["max_transfers"]) != p["max_transfers"]:
        raise ValueError("Speed must be positive; transfers must be an integer")
    # A personal walking limit is separate from the access-point search radius.
    if limited:
        p["max_walk_m"] = min(400, p["max_walk_m"])
    p["hard_flags"] = sorted(set(p.get("hard_flags", ())))
    return p


def edge_accessible(edge, network, mobility="standard"):
    """Return the effective accessibility used by route output and filtering.

    M0's wheelchair demo policy assumes rail and full-size bus service accessible
    when the source has no negative accessibility evidence. Explicit false or
    partial flags remain blocking; minibuses are rejected by ``allows_edge``.
    Walking/ferry legs still require affirmative accessibility data.
    """
    values = [edge.data.get("accessible"),
              *(network.nodes[n].get("accessible") for n in (edge.source, edge.target))]
    if mobility == "wheelchair" and edge.mode in {"MTR", "BUS"}:
        if any(value is False or value == "partial" for value in values):
            return False
        floor = edge.data.get("low_floor", edge.data.get("lowfloor"))
        return edge.mode != "BUS" or floor is not False and floor != "partial"
    return all(value is True for value in values)


def allows_edge(edge, network, profile):
    flags = set(profile["hard_flags"])
    limited = profile["mobility"] in {"reduced", "wheelchair"}
    if edge.mode == "MINIBUS" and (limited or "no_minibus" in flags):
        return False
    if (limited or "no_stairs" in flags) and any(
            item.get("stairs") or item.get("has_stairs")
            for item in (edge.data, network.nodes[edge.source], network.nodes[edge.target])):
        return False
    if profile["mobility"] == "wheelchair":
        if not edge_accessible(edge, network, "wheelchair"):
            return False
    elif limited and not edge_accessible(edge, network, profile["mobility"]):
        return False
    # Wheelchair M0 assumes full-size buses accessible by default. An explicit
    # no-non-low-floor constraint remains stricter than that profile default.
    if edge.mode == "BUS" and (profile["mobility"] == "reduced" or "no_non_lowfloor_bus" in flags):
        if edge.data.get("low_floor", edge.data.get("lowfloor")) is not True:
            return False
    return True
