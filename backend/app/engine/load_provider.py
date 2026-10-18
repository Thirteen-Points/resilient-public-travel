"""Injection boundary for C-Sim. This module does not own queue/load algorithms."""
from copy import deepcopy
import math

from ..graph.adapter import DataUnavailable

LOAD_FIELDS = {'users_on_route', 'capacity_per_hour', 'load_factor', 'expected_wait_s', 'board_refusal_prob'}


def validate_load(value):
    if not isinstance(value, dict) or not LOAD_FIELDS <= set(value):
        raise DataUnavailable('Load provider must return all documented load fields')
    result = {key: value[key] for key in LOAD_FIELDS}
    for key, number in result.items():
        if isinstance(number, bool) or not isinstance(number, (float, int)) or not math.isfinite(number) or number < 0:
            raise DataUnavailable(f'Invalid load field: {key}')
    if result['board_refusal_prob'] > 1:
        raise DataUnavailable('Invalid board_refusal_prob')
    return result


class FixtureLoadProvider:
    """Explicit zero-demand scenario; never used by the verified-data adapter."""
    provenance = 'simulated'
    source = 'c_route_zero_demand_fixture'
    freshness_s = 0

    def __init__(self, scenario):
        self.scenario = dict(scenario)
        if self.scenario != {'users_on_route': 0, 'load_factor': 0, 'board_refusal_prob': 0}:
            raise ValueError('This fixture models zero demand only; use C-Sim for nonzero demand')

    def __call__(self, route, parameters):
        return {**self.scenario, 'capacity_per_hour': parameters['capacity_per_hour'],
                'expected_wait_s': parameters['headway_s'] / 2}


def attach_load(details, provider):
    """Add bottleneck queueing above the zero-demand half-headway baseline.

    Scheduled boarding waits are already in the path ETA. Only the increase
    above normal waiting is added, once per route rather than per stop.
    """
    result = deepcopy(details)
    if result['routes'] and provider is None:
        raise DataUnavailable('C-Sim load provider required; no implicit demand assumption')
    if provider is not None and getattr(provider, 'provenance', None) not in {'real', 'real-derived', 'simulated'}:
        raise DataUnavailable('Load provider requires provenance')
    if provider is not None:
        if not isinstance(getattr(provider, 'source', None), str) or not provider.source:
            raise DataUnavailable('Load provider requires a source')
        age = getattr(provider, 'freshness_s', None)
        if not isinstance(age, (float, int)) or not math.isfinite(age) or age < 0:
            raise DataUnavailable('Load provider requires finite nonnegative freshness_s')
    for route in result['routes']:
        parameters = result['route_parameters'][route['route_id']]
        route['load_estimate'] = validate_load(provider(route, parameters))
        headway_s = parameters['headway_s']
        wait_s = route['load_estimate']['expected_wait_s']
        delay_s = max(0.0, wait_s - headway_s / 2) if headway_s > 0 else 0.0
        total = route['total']
        total['queue_delay_s'] = delay_s
        total['time_s'] += delay_s
        total['time_range_s'] = [bound + delay_s for bound in total['time_range_s']]
        if headway_s > 0 and wait_s >= 2 * headway_s:
            route['warnings'].append('Queue estimate has reached the two-headway cap; actual waiting may be longer in severe crowding.')
        refusal = route['load_estimate']['board_refusal_prob']
        if refusal > 0:
            route['warnings'].append(f'Boarding may be refused (model probability {refusal:.0%}); allow extra time.')
        route['evidence'].append({'source': provider.source, 'freshness_s': provider.freshness_s})
        if provider.provenance == 'simulated':
            route['provenance'] = 'simulated'
            route['warnings'].append('Load comes from an explicitly simulated scenario and does not represent real passenger demand.')
    return result
