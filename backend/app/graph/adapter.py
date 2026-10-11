"""Data-only boundary. Verified adapters implement load() without changing search.

Fare tables are INTERNAL configuration, not additions to the public contract.
Seed input is copied and conservatively relabelled simulated at every record.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Protocol

from .build import freeze


class DataUnavailable(ValueError):
    pass


def positive(value, name, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DataUnavailable(f"Missing or invalid {name}")
    if value < 0 or (not zero and value == 0):
        raise DataUnavailable(f"Invalid {name}")
    return value


def mark_simulated(value):
    if isinstance(value, dict):
        result = {k: mark_simulated(v) for k, v in value.items()}
        if 'provenance' in result:
            result['provenance'] = 'simulated'
        return result
    if isinstance(value, list):
        return [mark_simulated(v) for v in value]
    return value


@dataclass(frozen=True)
class RoutingData:
    network: dict
    events: tuple
    fares: object
    baseline_fare: float
    holidays: tuple = ()
    fixture_load: object = None
    profiles: object = None
    weather_policy: object = None
    fare_store: object = None


class DataAdapter(Protocol):
    def load(self) -> RoutingData: ...


def validate_network(network):
    for record in [*network['nodes'], *network['lines'], *network.get('walk_links', [])]:
        if record.get('provenance') not in {'real', 'real-derived', 'simulated'}:
            raise DataUnavailable('Every network record requires provenance')
    for line in network['lines']:
        positive(line.get('capacity_per_vehicle'), f"capacity for {line['id']}")
        schedule = line.get('headway_s')
        if 'headway_s' not in line or schedule == {}:
            raise DataUnavailable(f"Missing headway for {line['id']}")
        for value in schedule.values() if isinstance(schedule, dict) else [schedule]:
            if value is not None:
                positive(value, f"headway for {line['id']}")


def fare_table(network, *, overrides=None):
    """No implicit price or line-specific behavior; incomplete verified data fails."""
    overrides = overrides or {}
    table = {}
    for line in network['lines']:
        row = dict(overrides.get(line['id'], {}))
        amount = row.get('fare_hkd', line.get('fare_hkd'))
        positive(amount, f"fare for {line['id']}", zero=True)
        provenance = row.get('provenance', line.get('provenance'))
        if provenance not in {'real', 'real-derived', 'simulated'}:
            raise DataUnavailable(f"Missing fare provenance for {line['id']}")
        table[line['id']] = {'fare_hkd': amount, 'group': row.get('group'),
                              'provenance': provenance, 'note': row.get('note', '')}
        if row.get('source_url'):
            table[line['id']]['source_url'] = row['source_url']
        if 'od_fares' in row:
            matrix = row['od_fares']
            if not isinstance(matrix, dict) or not matrix:
                raise DataUnavailable(f"Missing OD fares for {line['id']}")
            for origin, destinations in matrix.items():
                if not isinstance(destinations, dict) or not destinations:
                    raise DataUnavailable(f'Missing fare destinations for {origin}')
                for destination, value in destinations.items():
                    positive(value, f'fare for {origin} -> {destination}', zero=True)
            table[line['id']]['od_fares'] = matrix
            table[line['id']]['interchanges'] = row.get('interchanges', [])
            for link in table[line['id']]['interchanges']:
                positive(link.get('max_s'), 'fare interchange time limit')
        if 'fares_by_service_day' in row:
            schedule = row['fares_by_service_day']
            for key in ('weekday_peak', 'weekday_offpeak', 'saturday', 'sunday_ph'):
                for deck in ('upper', 'lower'):
                    positive(schedule.get(key, {}).get(deck), f'{key} {deck} fare', zero=True)
            table[line['id']]['fares_by_service_day'] = schedule
    return freeze(table)


class MappingDataAdapter:
    """C-Data supplies normalized network, exact fares, calendar and published events.

    No fallback capacity/headway/fare, no auto-certification, no fixture provider.
    Fare groups are explicit fare-policy input; None charges each new boarding.
    """
    def __init__(self, network, *, baseline_fare, fares=None, events=(), holidays=(), profiles=None, weather_policy=None):
        self.network = deepcopy(network)
        self.baseline = baseline_fare
        self.fares = deepcopy(fares or {})
        self.events = deepcopy(events)
        self.holidays = tuple(holidays)
        self.profiles = deepcopy(profiles or {})
        self.weather_policy = deepcopy(weather_policy)

    def load(self):
        network = deepcopy(self.network)
        if self.weather_policy is not None:
            from ..engine.environment import validate_weather_policy
            validate_weather_policy(self.weather_policy)
        overrides = deepcopy(self.fares)
        if network.get('meta', {}).get('provenance') == 'simulated':
            network = mark_simulated(network)
            overrides = mark_simulated(overrides)
        validate_network(network)
        positive(self.baseline, 'baseline_fare')
        return RoutingData(network, tuple(deepcopy(self.events)), fare_table(network, overrides=overrides),
                           self.baseline, self.holidays, profiles=freeze(self.profiles), weather_policy=freeze(self.weather_policy))


class SeedDataAdapter:
    def __init__(self, network_path=None, events_path=None, policy_path=None, *, calendar_path=None, weather_path=None, fare_db_path=None):
        root = Path(__file__).resolve().parents[3]
        self.network_path = Path(network_path or root / 'contracts/seed/network.seed.json')
        self.events_path = Path(events_path) if events_path else None
        self.policy_path = Path(policy_path or Path(__file__).parent.parent / 'engine/fixtures/seed_policy.json')
        self.calendar_path = Path(calendar_path or root / 'data/calendar.json')
        self.weather_path = Path(weather_path or root / 'data/weather_impact.json')
        self.fare_db_path = fare_db_path

    def load(self):
        from ..engine.environment import calendar_holidays, validate_weather_policy
        holidays = calendar_holidays(json.loads(self.calendar_path.read_text(encoding='utf-8')))
        weather = validate_weather_policy(json.loads(self.weather_path.read_text(encoding='utf-8')))
        policy = json.loads(self.policy_path.read_text(encoding='utf-8'))
        if policy['provenance'] != 'simulated':
            raise DataUnavailable('Seed policy must be simulated')
        network = mark_simulated(json.loads(self.network_path.read_text(encoding='utf-8')))
        network.setdefault('meta', {})['provenance'] = 'simulated'
        for record in [*network['nodes'], *network['lines'], *network.get('walk_links', [])]:
            record['provenance'] = 'simulated'
        validate_network(network)
        synthetic_fixture = Path(__file__).parent.parent / 'engine/fixtures/network.synthetic.json'
        if self.network_path.resolve() == synthetic_fixture.resolve():
            # The built-in artificial O/D graph has explicit simulated prices;
            # it must not initialize or bind to the Hong Kong fare catalogue.
            fare_store, fares = None, fare_table(network)
        else:
            from ..services.fare_store import FareStore
            fare_store = FareStore(self.fare_db_path)
            fare_store.initialize(self.policy_path.parent / policy['fare_bootstrap'], network)
            _, fares = fare_store.snapshot(network, policy['query']['depart_at'])
        events = []
        if self.events_path:
            content = json.loads(self.events_path.read_text(encoding='utf-8'))
            events = mark_simulated(content['events'] if isinstance(content, dict) else content)
            for event in events:
                event['provenance'] = 'simulated'
        positive(policy['baseline_fare_hkd'], 'baseline fare')
        return RoutingData(network, tuple(events), fares,
                           policy['baseline_fare_hkd'], holidays=holidays, fixture_load=freeze(policy['load']),
                           profiles=freeze(policy.get('profiles', {})), weather_policy=freeze(weather), fare_store=fare_store)



class JsonDataAdapter:
    """Read normalized C-Data network JSON and explicit routing policy JSON.

    Network shape is nodes/lines/walk_links as in the public seed. Policy is an
    internal adapter input containing baseline_fare, fares, holidays, profiles.
    It supplies no fallback headway, capacity or price and never upgrades origin.
    """
    def __init__(self, network_path, policy_path, events_path=None):
        self.network_path = Path(network_path)
        self.policy_path = Path(policy_path)
        self.events_path = Path(events_path) if events_path else None

    def load(self):
        network = json.loads(self.network_path.read_text(encoding='utf-8'))
        policy = json.loads(self.policy_path.read_text(encoding='utf-8'))
        events = []
        if self.events_path:
            content = json.loads(self.events_path.read_text(encoding='utf-8'))
            events = content['events'] if isinstance(content, dict) else content
        return MappingDataAdapter(network, baseline_fare=policy['baseline_fare'],
                                  fares=policy.get('fares'), events=events,
                                  holidays=policy.get('holidays', ()), profiles=policy.get('profiles'),
                                  weather_policy=policy.get('weather_policy')).load()
