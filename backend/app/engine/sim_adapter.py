"""C-Route integration boundary; all queue/bucket algorithms remain owned by C-Sim."""
from copy import deepcopy
from math import floor

from ..graph.adapter import DataUnavailable, positive
from .load import RouteSupply
from .queue import estimate_queue


class MappingDemandAdapter:
    """Explicit demand rates (people/hour), never inferred from transport capacity."""
    def __init__(self, rates_per_hour, *, source, provenance, freshness_s, default_rate_per_hour=None):
        if provenance not in {'real', 'real-derived', 'simulated'} or not source:
            raise ValueError('Demand requires source and provenance')
        positive(freshness_s, 'demand freshness', zero=True)
        for value in rates_per_hour.values():
            positive(value, 'demand rate', zero=True)
        if default_rate_per_hour is not None:
            positive(default_rate_per_hour, 'default demand rate', zero=True)
        self.rates = deepcopy(rates_per_hour)
        self.default = default_rate_per_hour
        self.source, self.provenance, self.freshness_s = source, provenance, freshness_s

    def read(self, route_id, horizon_min):
        positive(horizon_min, 'horizon_min')
        rate = self.rates.get(route_id, self.default)
        if rate is None:
            raise DataUnavailable(f'Missing demand for {route_id}')
        return {'users_on_route': floor(rate * horizon_min / 60), 'source': self.source,
                'provenance': self.provenance, 'freshness_s': self.freshness_s}


class CSimAdapter:
    def estimate_load(self, supply, demand, horizon_min):
        if supply['headway_s'] <= 0:
            raise DataUnavailable('Walking-only route has no transit capacity model')
        route = RouteSupply.from_route_output(supply)
        users = demand['users_on_route']
        queue = estimate_queue(demand_per_hour=users * 60 / horizon_min,
                               service_capacity_per_hour=route.service_capacity_per_hour,
                               headway_s=route.headway_s)
        result = queue.to_contract(route.route_id, users, route.capacity_per_hour)
        result.update(provenance='simulated', freshness_s=max(supply['freshness_s'], demand['freshness_s']))
        return result

    def get_diversion_plan(self, event_id, demand, supplies):
        from ..sim.service import build_diversion_plan
        if any(supply['headway_s'] <= 0 for supply in supplies):
            raise DataUnavailable('Walking-only capacity must be explicitly modelled before diversion')
        return build_diversion_plan({'event_id': event_id, 'demand': demand, 'window_min': 60, 'routes': supplies})


class SimLoadProvider:
    """One-hour route-card view; tool estimate_load can request another horizon."""
    provenance = 'simulated'

    def __init__(self, simulation, demand):
        self.simulation, self.demand = simulation, demand

    @property
    def source(self):
        return self.demand.source

    @property
    def freshness_s(self):
        return self.demand.freshness_s

    def __call__(self, route, parameters):
        return self.simulation.estimate_load(parameters, self.demand.read(route['route_id'], 60), 60)
