"""Public synchronous facade for API, simulation and AI tool adapters."""
import json

from ..graph import SnapshotStore, build_graph
from ..graph.build import MODES, timestamp, thaw, freeze
from ..graph.adapter import SeedDataAdapter, fare_table, positive
from .load_provider import FixtureLoadProvider, attach_load
from .cache import QueryCache
from .candidates import route_from_path, search_paths, select_diverse, intermediate_nodes, jaccard, transfer_nodes
from .constraints import normalize_profile
from .score import score_routes


class RouteEngine:
    def __init__(self, snapshots, *, cache_size=128, baseline_fare=None, fares=None, load_provider=None, max_expansions=30000):
        self.snapshots = snapshots
        self.cache = QueryCache(cache_size)
        self.fares = freeze(thaw(fares)) if fares is not None else fare_table(thaw(snapshots.network.source))
        if baseline_fare is None:
            baseline_fare = max((row['fare_hkd'] for row in self.fares.values()), default=0)
        positive(baseline_fare, 'baseline_fare')
        self.baseline_fare = baseline_fare
        self.load_provider = load_provider
        self.max_expansions = max_expansions

    @classmethod
    def from_seed(cls, network_path=None, events_path=None, **kwargs):
        return cls.from_adapter(SeedDataAdapter(network_path, events_path), **kwargs)

    @classmethod
    def from_adapter(cls, adapter, **kwargs):
        data = adapter.load()
        store = SnapshotStore(build_graph(data.network, holidays=data.holidays), weather_policy=data.weather_policy)
        store.replace_events(data.events)
        if data.fixture_load is not None and 'load_provider' not in kwargs:
            kwargs['load_provider'] = FixtureLoadProvider(data.fixture_load)
        engine = cls(store, baseline_fare=data.baseline_fare, fares=data.fares, **kwargs)
        engine.routing_data = data
        return engine

    def query(self, origin, destination, depart_at, profile=None, *, event_ids=None, modes=None, required_modes=None, limit=10):
        """RouteCandidate[]; already personalized and score sorted (UI may take [:3])."""
        return self.query_details(origin, destination, depart_at, profile, event_ids=event_ids,
                                  modes=modes, required_modes=required_modes, limit=limit)["routes"]

    def query_details(self, origin, destination, depart_at, profile=None, *, event_ids=None, modes=None, required_modes=None, limit=10):
        if not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("limit must be an integer in [1,50]")
        if modes is not None and (not modes or set(modes) - MODES):
            raise ValueError("modes must contain known transit modes")
        if required_modes is not None and (not required_modes or set(required_modes) - (MODES - {'WALK'})):
            raise ValueError("required_modes must contain known transit modes excluding WALK")
        at, profile = timestamp(depart_at), normalize_profile(profile)
        snapshot = self.snapshots.current
        # event_ids identifies the disruption context; it cannot disable other published closures.
        unknown = set(event_ids or ()) - {e["event_id"] for e in snapshot.events}
        if unknown:
            raise ValueError(f"Unknown event_ids: {sorted(unknown)}")
        key = json.dumps([snapshot.snapshot_id, origin, destination, at.isoformat(), profile,
                          sorted(event_ids or ()), sorted(modes or ()), sorted(required_modes or ()), limit, self.baseline_fare], sort_keys=True)
        cached = self.cache.get(key)
        if cached is not None:
            return attach_load(cached, self.load_provider)
        found = search_paths(snapshot, origin, destination, at, profile, modes=modes, required_modes=required_modes,
                             max_expansions=self.max_expansions)
        paths = select_diverse(found.paths, limit)
        fallback = {}
        # Local wheelchair top3 fallback: relax ONLY the two soft diversity rules.
        # Search has already enforced accessibility, closures and user limits.
        if profile['mobility'] == 'wheelchair' and len(paths) < min(3, limit):
            for candidate in found.paths:
                if len(paths) >= min(3, limit):
                    break
                if candidate in paths:
                    continue
                if sum(step.edge.walk_m for step in candidate) > min(400, profile['max_walk_m']):
                    continue
                if max(0, sum(step.boarding for step in candidate) - 1) > min(2, profile['max_transfers']):
                    continue
                overlap = max((jaccard(intermediate_nodes(candidate), intermediate_nodes(p))
                               for p in paths), default=0)
                reused = sorted(n for n in transfer_nodes(candidate)
                                if sum(n in transfer_nodes(p) for p in paths) >= 2)
                if not reused and overlap < .7:
                    continue
                fallback[tuple(step.edge.id for step in candidate)] = (reused, overlap)
                paths.append(candidate)
        raw = []
        for path in paths:
            route = route_from_path(path, snapshot, at, fares=self.fares, profile=profile)
            relaxed = fallback.get(tuple(step.edge.id for step in path))
            if relaxed:
                reused, overlap = relaxed
                route['warnings'].append('轮椅 top3 局部回退：共用换乘点 ' + (', '.join(reused) or '无')
                                         + f'；与已有方案最高节点重合度 {overlap:.3f}'
                                         + ('，高度重合，不能视为独立替代走廊' if overlap >= .7 else '')
                                         + '；仅回退多样性软规则，无障碍、步行和换乘次数硬约束不变')
            raw.append(route)
        routes = score_routes(raw, profile, baseline_fare=self.baseline_fare)
        diagnostics = list(snapshot.network.diagnostics)
        if len(routes) < limit:
            diagnostics.append(f"Only {len(routes)} feasible diverse routes; target {limit} cannot be guaranteed by this network/profile")
        transit_modes = {leg["mode"] for route in routes for leg in route["legs"] if leg["mode"] != "WALK"}
        if len(transit_modes) < 2:
            diagnostics.append("Fewer than two transit modes remain feasible")
        if found.truncated:
            diagnostics.append("Search bounded by path/expansion budget; result is not exhaustive")
        # Keep simulation parameters outside the public RouteCandidate contract.
        parameters = {r["route_id"]: r.pop("_metrics") for r in routes}
        for route in routes:
            parameters[route['route_id']].update(route_id=route['route_id'],
                                                 freshness_s=route['total']['freshness_s'])
        for route in routes:
            route.pop("load_estimate")  # demand belongs to C-Sim; never invent zero demand
            route["warnings"].extend(diagnostics)
        result = {"routes": routes, "graph_snapshot": snapshot.snapshot_id, "diagnostics": diagnostics,
                  "route_parameters": parameters, "expanded": found.expanded,
                  "search_statistics": {"target": limit, "feasible_paths": len(found.paths),
                                        "selected": len(routes), "shortfall": max(0, limit - len(routes)),
                                        "diversity_filtered": len(found.paths) > len(paths),
                                        "bounded": found.truncated}}
        self.cache.put(key, result)
        return attach_load(result, self.load_provider)
