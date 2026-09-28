"""Six deterministic handlers injected into AI's existing registry.

One instance belongs to one conversation/query context. Route-id tools use only
the latest full search, reject stale snapshots, and never mix unrelated searches.
No transport observations are stored in the AI layer.
"""
from copy import deepcopy
from datetime import datetime
from functools import partial
from threading import RLock

from ..graph.adapter import DataUnavailable, positive
from ..graph.build import HK, thaw, timestamp
from ..graph.snapshot import active
from .constraints import normalize_profile
from .score import score_routes as compute_scores
from .service import RouteEngine
from .sim_adapter import CSimAdapter, MappingDemandAdapter, SimLoadProvider
from .walk import distance_m


def _output_age(rows):
    return max((max([row.get('total', {}).get('freshness_s', 0), row.get('freshness_s', 0)] +
                    [e.get('freshness_s', 0) for e in row.get('evidence', [])]) for row in rows), default=0)


class RouteHandlers:
    NAMES = ('geocode_place', 'find_access_points', 'search_transit_routes',
             'score_routes', 'estimate_load', 'get_diversion_plan')

    def __init__(self, adapter, *, demand_adapter=None, simulation_adapter=None, observed_at=None):
        self.engine = RouteEngine.from_adapter(adapter)
        if demand_adapter is None:
            fixture = self.engine.routing_data.fixture_load
            if fixture is None or fixture.get('users_on_route') != 0:
                raise DataUnavailable('Explicit demand adapter required for normalized data')
            demand_adapter = MappingDemandAdapter({}, source='c_route_zero_demand_fixture',
                                                  provenance='simulated', freshness_s=0, default_rate_per_hour=0)
        self.demand = demand_adapter
        self.simulation = simulation_adapter or CSimAdapter()
        self.engine.load_provider = SimLoadProvider(self.simulation, self.demand)
        self.observed_at = timestamp(observed_at or datetime.now(HK))
        self._context = None
        self._lock = RLock()

    def handlers(self):
        """AI tool envelopes; direct methods and public REST keep their shapes."""
        return {name: partial(self._tool_envelope, name) for name in self.NAMES}

    def _tool_envelope(self, name, **arguments):
        with self._lock:
            value = getattr(self, name)(**arguments)
            if name == 'geocode_place':
                return value
            if name == 'get_diversion_plan':
                records = self._context['details']['routes']
                return {**value, 'freshness_s': _output_age(records)}
            key = {'find_access_points': 'access_points', 'search_transit_routes': 'routes',
                   'score_routes': 'scores', 'estimate_load': 'loads'}[name]
            origins = {row.get('provenance', 'simulated') for row in value}
            provenance = ('simulated' if not origins or 'simulated' in origins else
                          'real-derived' if 'real-derived' in origins else 'real')
            age = _output_age(value)
            result = {key: value, 'provenance': provenance, 'freshness_s': age}
            if name == 'search_transit_routes':
                result['graph_snapshot'] = self._context['details']['graph_snapshot']
            return result

    def _freshness(self, record):
        updated = record.get('updated_at') or self.engine.snapshots.network.source.get('meta', {}).get('built_at')
        if updated:
            return max(0, (self.observed_at - timestamp(updated)).total_seconds())
        if 'freshness_s' in record:
            return positive(record['freshness_s'], 'freshness_s', zero=True)
        raise DataUnavailable('Lookup data needs updated_at, built_at or freshness_s')

    def geocode_place(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('query must be a nonempty place name or node id')
        needle = query.strip().casefold()
        found = []
        for node in self.engine.snapshots.network.nodes.values():
            names = [node['id'], node.get('name_zh', ''), node.get('name_en', ''), *node.get('aliases', ())]
            if needle in {str(name).strip().casefold() for name in names if name}:
                found.append(node)
        if len(found) != 1:
            raise DataUnavailable('Unknown or ambiguous place; provide a node id')
        node = found[0]
        return {'node_id': node['id'], 'lat': node['lat'], 'lng': node['lng'],
                'label': node.get('name_zh') or node.get('name_en') or node['id'],
                'provenance': node['provenance'], 'freshness_s': self._freshness(node)}

    def find_access_points(self, lat, lng, radius_m=800):
        positive(radius_m, 'radius_m', zero=True)
        radius_m = min(radius_m, 800)  # Origin/destination access radius, not route total.
        if (isinstance(lat, bool) or isinstance(lng, bool) or
                not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)) or
                not (-90 <= lat <= 90 and -180 <= lng <= 180)):
            raise ValueError('Invalid WGS84 coordinates')
        points = []
        for node in self.engine.snapshots.network.nodes.values():
            distance = distance_m({'lat': lat, 'lng': lng}, node)
            if distance <= radius_m:
                points.append({'node_id': node['id'], 'label': node.get('name_zh') or node['id'],
                               'kind': node['kind'], 'lat': node['lat'], 'lng': node['lng'],
                               'distance_m': distance, 'accessible': node.get('accessible') is True,
                               'provenance': 'simulated' if node['provenance'] == 'simulated' else 'real-derived',
                               'freshness_s': self._freshness(node)})
        return sorted(points, key=lambda row: (row['distance_m'], row['node_id']))

    def search_transit_routes(self, depart_at, modes=None, profile_id=None, **locations):
        if set(locations) != {'from', 'to'}:
            raise ValueError('Expected from and to')
        profiles = self.engine.routing_data.profiles or {}
        if profile_id is not None and profile_id not in profiles:
            raise DataUnavailable('Unknown profile_id')
        profile = normalize_profile(thaw(profiles[profile_id]) if profile_id is not None else None)
        origin = self.geocode_place(locations['from'])['node_id']
        destination = self.geocode_place(locations['to'])['node_id']
        with self._lock:
            result = self.engine.query_details(origin, destination, depart_at, profile, modes=modes)
            self._context = {'details': deepcopy(result), 'profile': profile, 'depart_at': timestamp(depart_at)}
            return deepcopy(result['routes'])

    def _resolve(self, route_ids):
        if self._context is None:
            raise DataUnavailable('Search routes first')
        details = self._context['details']
        if self.engine.snapshots.current.snapshot_id != details['graph_snapshot']:
            raise DataUnavailable('Graph changed; search routes again')
        if not isinstance(route_ids, list) or any(not isinstance(x, str) for x in route_ids):
            raise ValueError('route_ids must be a string array')
        if len(set(route_ids)) != len(route_ids):
            raise ValueError('Duplicate route_ids')
        routes = {r['route_id']: r for r in details['routes']}
        if any(rid not in routes for rid in route_ids):
            raise DataUnavailable('Unknown route_id in current query')
        return details, [routes[rid] for rid in route_ids]

    def score_routes(self, route_ids, weights=None):
        with self._lock:
            details, selected = self._resolve(route_ids)
            profile = deepcopy(self._context['profile'])
            if weights is not None:
                if not isinstance(weights, dict) or not weights:
                    raise ValueError('weights must be a nonempty object')
                profile['weights'] = weights
            scored = compute_scores(details['routes'], profile, baseline_fare=self.engine.baseline_fare)
            by_id = {r['route_id']: r for r in scored}
            return [{'route_id': r['route_id'], 'score': by_id[r['route_id']]['score'],
                     'score_breakdown': by_id[r['route_id']]['score_breakdown'],
                     'provenance': r['provenance'], 'freshness_s': r['total']['freshness_s']} for r in selected]

    def estimate_load(self, route_ids, horizon_min):
        if isinstance(horizon_min, bool) or not isinstance(horizon_min, int) or horizon_min <= 0:
            raise ValueError('horizon_min must be a positive integer')
        with self._lock:
            details, routes = self._resolve(route_ids)
            return [self.simulation.estimate_load(details['route_parameters'][r['route_id']],
                    self.demand.read(r['route_id'], horizon_min), horizon_min) for r in routes]

    def get_diversion_plan(self, event_id, demand):
        if isinstance(demand, bool) or not isinstance(demand, int) or demand < 0:
            raise ValueError('demand must be a nonnegative integer')
        with self._lock:
            details, _ = self._resolve([])
            if not any(e['event_id'] == event_id and active(e, self._context['depart_at'])
                       for e in self.engine.snapshots.current.events):
                raise DataUnavailable('A published event active at query departure is required')
            supplies = [deepcopy(details['route_parameters'][r['route_id']]) for r in details['routes']]
            return self.simulation.get_diversion_plan(event_id, demand, supplies)
