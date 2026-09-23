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
        route['load_estimate'] = validate_load(provider(route, result['route_parameters'][route['route_id']]))
        route['evidence'].append({'source': provider.source, 'freshness_s': provider.freshness_s})
        if provider.provenance == 'simulated':
            route['provenance'] = 'simulated'
            route['warnings'].append('负载来自显式模拟场景，不代表真实客流')
    return result
