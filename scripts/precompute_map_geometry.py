"""Build the frontend-only, offline map alignment snapshot from public GIS data.

This never changes the routing graph, journey time, fares, or accessibility. The
rail feature chains below are explicit reviewed line assignments: the official
1:50,000 layer does not carry an MTR service id. Disconnected source paths remain
separate; station symbols and missing survey geometry are never bridged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import heapq
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "map-geometry"
OUTPUT = ROOT / "frontend" / "src" / "map" / "geometry.snapshot.json"
BUS = "https://portal.csdi.gov.hk/server/rest/services/common/td_rcd_1638844988873_41214/MapServer/0"
RAIL = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637221775627_85634/MapServer/4"
PED = "https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637222018065_52265/MapServer/0"
TERMS = "https://static.csdi.gov.hk/csdi-webpage/doc/TNC"
WALK_ANCHOR_WEIGHT = 5

# Signed GRAPHICID: a negative sign reverses the source feature. Omitted model
# stops (Hin Keng, Kai Tak, etc.) still retain their complete intervening paths.
RAIL_CHAINS = {
    "ERL": [649582, 649623, 649624, 649566, 649730, 649731, -649567,
            649581, 649603, 649520, -649577, 649568, 649578, 21170998,
            21157754, 649719, 649713],
    "TML": [649841, 649702, 21141908, 649717, 649704, -649706,
            649718, -649708, 21157159, 21157754, -649745],
    "KTL": [-649724, -649627, -649626, -649625, 649618,
            -649617, -649616, 649689],
    "TWL": [649615, -649614, 649699, -649606],
    "ISL": [649605, 649607],
}
BUS_VARIANTS = {
    "BUS_182": [(1051, 1, "forward"), (1051, 2, "reverse")],
    "BUS_81C": [(1336, 1, "forward"), (1336, 2, "reverse")],
    "BUS_982X": [(8104, 1, "forward"), (8644, 1, "reverse")],
    "BUS_985B": [(8705, 1, "forward")],
}


def fetch(name: str, url: str, refresh: bool) -> tuple[dict, dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{name}.json"
    if refresh or not cache.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "ResilientRoute-AcademicMap/1.0"})
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read()
        parsed = json.loads(raw.decode("utf-8-sig"))
        if "error" in parsed:
            raise RuntimeError(f"{name}: {parsed['error']}")
        envelope = {"url": url, "capturedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(), "data": parsed}
        cache.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    envelope = json.loads(cache.read_text(encoding="utf-8"))
    return envelope["data"], {key: envelope[key] for key in ("url", "capturedAt", "sha256")}


def query_url(base: str, **params) -> str:
    defaults = {"f": "json", "returnGeometry": "true", "outSR": 4326, "outFields": "*"}
    return base + "/query?" + urllib.parse.urlencode(defaults | params)


def xy(point):
    return point[0] * 111320 * math.cos(math.radians(22.32)), point[1] * 111320


def distance(a, b):
    ax, ay = xy(a)
    bx, by = xy(b)
    return math.hypot(bx - ax, by - ay)


def clean_parts(paths):
    parts = []
    for path in paths:
        points = []
        for point in path:
            p = [round(point[0], 7), round(point[1], 7)]
            if not points or p != points[-1]:
                points.append(p)
        if len(points) >= 2:
            if parts and parts[-1][-1] == points[0]:
                parts[-1].extend(points[1:])
            else:
                parts.append(points)
    return parts


def project(parts, location):
    """Nearest projection plus position along a multipart source, without joins."""
    best = None
    cumulative = 0.0
    target = xy(location)
    for pi, part in enumerate(parts):
        for vi, (a, b) in enumerate(zip(part, part[1:])):
            ax, ay = xy(a)
            bx, by = xy(b)
            dx, dy = bx - ax, by - ay
            length = math.hypot(dx, dy)
            t = max(0, min(1, ((target[0] - ax) * dx + (target[1] - ay) * dy) / (length * length))) if length else 0
            p = [round(a[0] + (b[0] - a[0]) * t, 7), round(a[1] + (b[1] - a[1]) * t, 7)]
            candidate = (distance(location, p), cumulative + length * t, pi, vi, p)
            if best is None or candidate[0] < best[0]:
                best = candidate
            cumulative += length
    if best is None:
        raise ValueError("No usable geometry")
    return best


def clip(parts, origin, destination):
    start, end = project(parts, origin), project(parts, destination)
    if start[1] > end[1]:
        raise ValueError("Anchors run against the reviewed source direction")
    clipped = []
    for pi in range(start[2], end[2] + 1):
        part = parts[pi]
        first = start[3] + 1 if pi == start[2] else 0
        last = end[3] + 1 if pi == end[2] else len(part)
        piece = ([start[4]] if pi == start[2] else []) + part[first:last] + ([end[4]] if pi == end[2] else [])
        clipped.extend(clean_parts([piece]))
    return clipped, [round(start[0], 1), round(end[0], 1)]


def source(source_id, department, meta, feature_ids):
    return {"id": source_id, "label": department, "url": meta["url"],
            "capturedAt": meta["capturedAt"], "sha256": meta["sha256"],
            "featureIds": feature_ids, "captures": meta.get("captures", [meta]), "licenseUrl": TERMS,
            "attribution": f"Government of the Hong Kong SAR · CSDI Portal · {department}"}


def record(mode, line_id, start, end, parts, source_id, offsets, note=None):
    return {"mode": mode, "lineId": line_id, "from": start, "to": end,
            "geometry": {"type": "MultiLineString", "coordinates": parts},
            "quality": "official", "sourceIds": [source_id],
            "endpointOffsetM": offsets, **({"note": note} if note else {})}


def pedestrian_path(features, origin, destination):
    """Offline display geometry only; never a replacement journey planner.

    Z participates in junction identity, so crossing bridges and underground
    footways cannot become fictitious intersections. Paid and disabled paths
    are excluded. Exact exit/lift suitability remains unknown to the app.
    """
    graph, positions, edges = {}, {}, {}
    direct = None
    for feature in features:
        attrs = feature["attributes"]
        if attrs.get("Enabled") != 1 or attrs.get("Location") == 3:
            continue
        for path in feature["geometry"].get("paths", []):
            if len(path) < 2:
                continue
            def key(p):
                return (round(p[0], 7), round(p[1], 7), round(p[2], 2) if len(p) > 2 else 0)
            a, b = key(path[0]), key(path[-1])
            positions[a], positions[b] = path[0], path[-1]
            length = sum(distance(p, q) for p, q in zip(path, path[1:]))
            edge_id = len(edges)
            edges[edge_id] = (path, attrs["PedestrianRouteID"])
            direction = attrs.get("Direction", 0)
            # Short transfers can lie on the same source edge. Node-only
            # matching would snap both ends to one junction and erase the
            # actual intervening footway. Clip that edge at real projections.
            projected_a, projected_b = project([path], origin), project([path], destination)
            forward = projected_a[1] < projected_b[1]
            if max(projected_a[0], projected_b[0]) <= 160 and (direction != -1 if forward else direction != 1):
                ordered = [path] if forward else [list(reversed(path))]
                clipped, offsets = clip(ordered, origin, destination)
                along = abs(projected_a[1] - projected_b[1])
                # A tiny edge near the midpoint is not a transfer path. Require
                # the captured endpoints to cover at least half the modeled
                # transfer span, then favor close anchors over short detours.
                span = distance(clipped[0][0], clipped[-1][-1]) if clipped else 0
                if clipped and along >= 1 and span >= distance(origin, destination) * .5:
                    score = sum(offsets) * WALK_ANCHOR_WEIGHT + along
                    if direct is None or score < direct[0]:
                        direct = (score, clipped, [attrs["PedestrianRouteID"]], offsets)
            if direction != -1:
                graph.setdefault(a, []).append((b, length, edge_id, False))
            if direction != 1:
                graph.setdefault(b, []).append((a, length, edge_id, True))
    if not positions:
        return None
    # Multiple nearby endpoints are evaluated to avoid selecting an isolated
    # indoor floor solely because its XY is marginally closer to a seed point.
    starts = sorted(positions, key=lambda p: distance(p, origin))[:12]
    ends = set(sorted(positions, key=lambda p: distance(p, destination))[:12])
    starts = [p for p in starts if distance(p, origin) <= 160]
    ends = {p for p in ends if distance(p, destination) <= 160}
    queue, previous, costs = [], {}, {}
    for start in starts:
        costs[start] = distance(start, origin) * WALK_ANCHOR_WEIGHT
        previous[start] = None
        heapq.heappush(queue, (costs[start], start))
    winner, winning_cost = None, float("inf")
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != costs[node]:
            continue
        if cost > winning_cost:
            break
        if node in ends and previous[node] is not None and cost + distance(node, destination) * WALK_ANCHOR_WEIGHT < winning_cost:
            winner, winning_cost = node, cost + distance(node, destination) * WALK_ANCHOR_WEIGHT
        for neighbor, length, edge_id, reverse in graph.get(node, []):
            next_cost = cost + length
            if next_cost < costs.get(neighbor, float("inf")):
                costs[neighbor] = next_cost
                previous[neighbor] = (node, edge_id, reverse)
                heapq.heappush(queue, (next_cost, neighbor))
    if direct is not None and direct[0] < winning_cost:
        return direct[1:]
    if winner is None:
        return None
    links, node = [], winner
    while previous[node] is not None:
        before, edge_id, reverse = previous[node]
        path, feature_id = edges[edge_id]
        links.append((list(reversed(path)) if reverse else path, feature_id))
        node = before
    links.reverse()
    if not links:
        return None
    parts = clean_parts([path for path, _ in links])
    if not parts or distance(parts[0][0], parts[-1][-1]) < distance(origin, destination) * .5:
        return None
    return parts, sorted({fid for _, fid in links}), [round(distance(origin, parts[0][0]), 1), round(distance(destination, parts[-1][-1]), 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch fresh public source data instead of cached captures")
    parser.add_argument("--check", action="store_true", help="Verify the snapshot is identical without writing it")
    args = parser.parse_args()
    network = json.loads((ROOT / "contracts" / "seed" / "network.seed.json").read_text(encoding="utf-8"))
    nodes = {n["id"]: [n["lng"], n["lat"]] for n in network["nodes"]}
    lines = {line["id"]: line for line in network["lines"]}
    sources, records, missing = [], [], []
    rail, rail_meta = fetch("rail", query_url(RAIL, where="CLASS='RAI' AND TYPE='MTR' AND PHYSICALSTATUS=3",
                         geometry="114.15,22.27,114.21,22.38", geometryType="esriGeometryEnvelope", inSR=4326,
                         spatialRel="esriSpatialRelIntersects"), args.refresh)
    by_graphic = {f["attributes"]["GRAPHICID"]: f for f in rail["features"]}
    for line_id, chain in RAIL_CHAINS.items():
        paths = []
        for graphic_id in chain:
            feature = by_graphic[abs(graphic_id)]
            feature_paths = feature["geometry"]["paths"]
            paths.extend([list(reversed(p)) for p in reversed(feature_paths)] if graphic_id < 0 else feature_paths)
        parts = clean_parts(paths)
        source_id = f"landsd-rail-{line_id}"
        sources.append(source(source_id, "Lands Department", rail_meta, [abs(v) for v in chain]))
        stops = lines[line_id]["stops"]
        for a, b in zip(stops, stops[1:]):
            clipped, offsets = clip(parts, nodes[a], nodes[b])
            if not clipped or max(offsets) > 500:
                raise ValueError(f"Rail anchor mismatch: {line_id} {a}->{b}: {offsets}")
            note = "Official 1:50,000 railway alignment; station areas are generalized and source gaps remain separate."
            records.append(record("MTR", line_id, a, b, clipped, source_id, offsets, note))
            records.append(record("MTR", line_id, b, a, [list(reversed(p)) for p in reversed(clipped)], source_id, list(reversed(offsets)), note))
    bus, bus_meta = fetch("bus", query_url(BUS, where="ROUTE_ID IN (1051,1336,8104,8644,8705)"), args.refresh)
    for line_id, variants in BUS_VARIANTS.items():
        for route_id, seq, direction in variants:
            matches = [f for f in bus["features"] if f["attributes"]["ROUTE_ID"] == route_id and f["attributes"]["ROUTE_SEQ"] == seq]
            if len(matches) != 1:
                raise ValueError(f"Expected one official bus variant: {route_id}/{seq}")
            parts = clean_parts(matches[0]["geometry"]["paths"])
            source_id = f"td-bus-{route_id}-{seq}"
            sources.append(source(source_id, "Transport Department", bus_meta, [f"{route_id}/{seq}"]))
            stops = lines[line_id]["stops"]
            if direction == "reverse":
                stops = list(reversed(stops))
            for a, b in zip(stops, stops[1:]):
                clipped, offsets = clip(parts, nodes[a], nodes[b])
                if not clipped or max(offsets) > 500:
                    raise ValueError(f"Bus anchor mismatch: {line_id} {a}->{b}: {offsets}")
                item = record("BUS", line_id, a, b, clipped, source_id, offsets,
                              "Official directional service alignment; modeled stop locations may be approximate.")
                item["variant"] = f"{route_id}/{seq}"
                records.append(item)
    # The official 985B source has one direction. A reversed drawing must not
    # claim to represent a nonexistent verified return service.
    missing.append({"mode": "BUS", "lineId": "BUS_985B", "from": "BS_ADM_E", "to": "BS_TIN_SUM",
                    "reason": "No verified official return-direction geometry for route 8705."})
    for link in network["walk_links"]:
        a, b = link["from"], link["to"]
        x1, y1 = nodes[a]
        x2, y2 = nodes[b]
        bbox = f"{min(x1,x2)-.004},{min(y1,y2)-.004},{max(x1,x2)+.004},{max(y1,y2)+.004}"
        features, metadata, captures, offset = [], None, [], 0
        while True:
            data, meta = fetch(f"walk-{a}-{b}-{offset}", query_url(PED, where="Enabled=1 AND Location<>3", returnZ="true",
                              geometry=bbox, geometryType="esriGeometryEnvelope", inSR=4326,
                              spatialRel="esriSpatialRelIntersects", resultOffset=offset, resultRecordCount=3000), args.refresh)
            metadata = metadata or meta
            captures.append(meta)
            features.extend(data["features"])
            if not data.get("exceededTransferLimit"):
                break
            offset += len(data["features"])
        found = pedestrian_path(features, nodes[a], nodes[b])
        if found:
            parts, feature_ids, offsets = found
            source_id = f"landsd-walk-{a}-{b}"
            metadata = metadata | {"captures": captures}
            walk_source = source(source_id, "Lands Department", metadata, feature_ids)
            sources.append(walk_source)
            note = "Pedestrian-network display path. Exact station exits, lift operation and step-free continuity remain unverified."
            records.append(record("WALK", None, a, b, parts, source_id, offsets, note))
            # Only bidirectional source edges can truthfully support a reverse
            # display path; calculate the reverse independently.
            back = pedestrian_path(features, nodes[b], nodes[a])
            if back:
                reverse_parts, reverse_ids, reverse_offsets = back
                walk_source["featureIds"] = sorted(set(feature_ids) | set(reverse_ids))
                records.append(record("WALK", None, b, a, reverse_parts, source_id, reverse_offsets, note))
        else:
            for start, end in ((a,b),(b,a)):
                missing.append({"mode": "WALK", "lineId": None, "from": start, "to": end,
                                "reason": "No continuous verified path between the model's approximate transfer points."})
    missing.extend({"mode": "FERRY", "lineId": "FERRY_TST_CEN", "from": a, "to": b,
                    "reason": "Official TD route 7030 provides pier points only, no verified navigational track."}
                   for a, b in (("PIER_TST","PIER_CEN"),("PIER_CEN","PIER_TST")))
    snapshot = {"version": 1, "coordinateOrder": "longitude,latitude", "sources": sources, "segments": records, "missing": missing}
    # Keep coordinates on one line per segment. This avoids a 50,000-line
    # generated diff while source identities and capture metadata stay readable.
    encoded = '{\n  "version": 1,\n  "coordinateOrder": "longitude,latitude",\n  "sources": ' + json.dumps(sources, ensure_ascii=False, indent=2) + ',\n  "segments": [\n'
    encoded += ',\n'.join('    ' + json.dumps(item, ensure_ascii=False, separators=(',', ':')) for item in records)
    encoded += '\n  ],\n  "missing": ' + json.dumps(missing, ensure_ascii=False, indent=2) + '\n}\n'
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != encoded:
            raise SystemExit("Map geometry snapshot differs. Run precompute_map_geometry.py to regenerate.")
    else:
        OUTPUT.write_text(encoded, encoding="utf-8")
    print(json.dumps({"segments": len(records), "sources": len(sources), "missing": len(missing),
                      "vertices": sum(len(p) for r in records for p in r["geometry"]["coordinates"]),
                      "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
