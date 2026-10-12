"""Persistent fare catalogue; the route engine reads a versioned SQL snapshot."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import sqlite3
from collections import OrderedDict
from threading import RLock


def default_fare_path():
    if os.getenv('FARE_DB_PATH'):
        return Path(os.environ['FARE_DB_PATH'])
    if os.getenv('DB_PATH'):
        return Path(os.environ['DB_PATH']).parent / 'fares.sqlite3'
    return Path(__file__).resolve().parents[1] / 'data/fares.sqlite3'


def cents(value):
    try:
        amount = Decimal(str(value)) * 100
        if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
            raise ValueError('Fare must be a nonnegative amount with at most two decimal places')
        return int(amount)
    except InvalidOperation as exc:
        raise ValueError('Invalid fare amount') from exc


SCHEMA = """
CREATE TABLE IF NOT EXISTS fare_meta (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL);
INSERT OR IGNORE INTO fare_meta VALUES (1, 0);
CREATE TABLE IF NOT EXISTS fare_sources (
    source_id TEXT PRIMARY KEY, url TEXT NOT NULL, sha256 TEXT NOT NULL,
    retrieved_at TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fare_services (
    line_id TEXT PRIMARY KEY, mode TEXT NOT NULL, service_id TEXT NOT NULL,
    strategy TEXT NOT NULL CHECK(strategy IN ('od','flat','service_day')),
    group_id TEXT, passenger TEXT NOT NULL, payment TEXT NOT NULL, note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fare_catalog (
    service_id TEXT PRIMARY KEY, mode TEXT NOT NULL, name TEXT NOT NULL, operator TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES fare_sources(source_id)
);
CREATE TABLE IF NOT EXISTS fare_locations (
    location_key TEXT PRIMARY KEY, mode TEXT NOT NULL, name TEXT NOT NULL, external_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fare_stop_aliases (
    line_id TEXT NOT NULL REFERENCES fare_services(line_id), direction TEXT NOT NULL,
    node_id TEXT NOT NULL, external_id TEXT NOT NULL,
    PRIMARY KEY(line_id, direction, node_id)
);
CREATE TABLE IF NOT EXISTS fare_interchanges (
    group_id TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL,
    max_s INTEGER NOT NULL CHECK(max_s > 0), PRIMARY KEY(group_id, origin, destination)
);
CREATE TABLE IF NOT EXISTS fare_alias_evidence (
    line_id TEXT NOT NULL, direction TEXT NOT NULL, node_id TEXT NOT NULL, stop_id TEXT NOT NULL,
    PRIMARY KEY(line_id,direction,node_id)
);
CREATE TABLE IF NOT EXISTS fare_prices (
    service_id TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'all', day_type TEXT NOT NULL DEFAULT 'all',
    deck TEXT NOT NULL DEFAULT 'all', passenger TEXT NOT NULL DEFAULT 'adult',
    payment TEXT NOT NULL DEFAULT 'standard', valid_from TEXT NOT NULL DEFAULT '',
    valid_until TEXT, amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents >= 0),
    source_id TEXT NOT NULL REFERENCES fare_sources(source_id),
    PRIMARY KEY(service_id, origin, destination, direction, day_type, deck, passenger, payment, valid_from)
);
CREATE INDEX IF NOT EXISTS fare_lookup ON fare_prices(service_id, passenger, payment, valid_from);
"""


class FareStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_fare_path()
        self._snapshot_cache = OrderedDict()
        self._cache_lock = RLock()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, bootstrap_path=None, network=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.executescript(SCHEMA)
            for action in ('INSERT','UPDATE'):
                connection.execute(f'CREATE TRIGGER IF NOT EXISTS fare_prices_validate_{action.lower()} '
                    f'BEFORE {action} ON fare_prices WHEN typeof(NEW.amount_cents)!=\'integer\' OR NEW.amount_cents<0 '
                    "BEGIN SELECT RAISE(ABORT,'Fare must be integer cents'); END")
            # External SQL updates must also invalidate in-process route caches.
            for table in ('fare_prices','fare_services','fare_stop_aliases','fare_interchanges','fare_sources'):
                for action in ('INSERT','UPDATE','DELETE'):
                    connection.execute(f'CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_revision '
                                       f'AFTER {action} ON {table} BEGIN '
                                       'UPDATE fare_meta SET revision=revision+1 WHERE id=1; END')
            connection.execute('BEGIN IMMEDIATE')
            if bootstrap_path and not connection.execute('SELECT 1 FROM fare_services LIMIT 1').fetchone():
                self._bootstrap(connection, json.loads(Path(bootstrap_path).read_text(encoding='utf-8')), network)

    @staticmethod
    def source(connection, source_id, url, sha256, retrieved_at, description):
        connection.execute('INSERT INTO fare_sources VALUES(?,?,?,?,?) '
                           'ON CONFLICT(source_id) DO UPDATE SET url=excluded.url, sha256=excluded.sha256, '
                           'retrieved_at=excluded.retrieved_at, description=excluded.description',
                           (source_id,url,sha256,retrieved_at,description))

    @staticmethod
    def price(connection, service, origin, destination, amount, source, *, direction='all',
              day_type='all', deck='all', passenger='adult', payment='standard', valid_from='', valid_until=None):
        if valid_from:
            date.fromisoformat(valid_from)
        if valid_until:
            date.fromisoformat(valid_until)
            if valid_until <= valid_from:
                raise ValueError('Fare validity window is empty')
        connection.execute('INSERT INTO fare_prices VALUES(?,?,?,?,?,?,?,?,?,?,?,?) '
                           'ON CONFLICT(service_id,origin,destination,direction,day_type,deck,passenger,payment,valid_from) '
                           'DO UPDATE SET amount_cents=excluded.amount_cents, source_id=excluded.source_id, valid_until=excluded.valid_until',
                           (service,origin,destination,direction,day_type,deck,passenger,payment,
                            valid_from,valid_until,cents(amount),source))

    def _bootstrap(self, connection, data, network):
        checked = data['meta']['retrieved_at']
        hashes = data['meta']['source_hashes']
        self.source(connection,'mtr',data['mtr']['source_url'],hashes['mtr_lines_fares.csv'],checked,'MTR published adult Octopus ordinary-class fares')
        self.source(connection,'bus_section','https://static.data.gov.hk/td/routes-fares-xml/FARE_BUS.xml',hashes['FARE_BUS.xml'],checked,'TD bus section fares')
        self.source(connection,'bus_full','https://static.data.gov.hk/td/routes-fares-xml/ROUTE_BUS.xml',hashes['ROUTE_BUS.xml'],checked,'TD bus full fares')
        self.source(connection,'ferry',data['lines']['FERRY_TST_CEN']['source_url'],'',checked,'Star Ferry published adult deck/day fares')
        for origin, destinations in data['mtr']['od_fares'].items():
            for destination, amount in destinations.items():
                self.price(connection,'mtr:octopus',origin,destination,amount,'mtr',payment='octopus')
        for link in data['mtr']['interchanges']:
            connection.execute('INSERT INTO fare_interchanges VALUES(?,?,?,?)',('mtr_octopus',link['from'],link['to'],link['max_s']))
        for line in network['lines']:
            if line['mode']=='MTR':
                connection.execute('INSERT INTO fare_services VALUES(?,?,?,?,?,?,?,?)',
                    (line['id'],'MTR','mtr:octopus','od','mtr_octopus','adult','octopus',''))
                continue
            tariff = data['lines'][line['id']]
            mappings = tariff.get('stop_mapping',[])
            service = tariff.get('service_id') or ('bus:'+mappings[0]['route_id'] if mappings else line['id'])
            strategy = 'od' if 'od_fares' in tariff else 'service_day' if 'fares_by_service_day' in tariff else 'flat'
            connection.execute('INSERT INTO fare_services VALUES(?,?,?,?,?,?,?,?)',
                               (line['id'],line['mode'],service,strategy,None,'adult','standard',tariff['note']))
            if strategy=='od':
                for mapping in mappings:
                    stops = mapping['stops']
                    for node, external in stops.items():
                        connection.execute('INSERT INTO fare_stop_aliases VALUES(?,?,?,?)',
                                           (line['id'],mapping['route_seq'],node,'stop:'+external))
                    for i, origin in enumerate(stops):
                        for destination in list(stops)[i+1:]:
                            self.price(connection,service,'stop:'+stops[origin],'stop:'+stops[destination],
                                       tariff['od_fares'][origin][destination],'bus_section',direction=mapping['route_seq'])
            elif strategy=='service_day':
                for key, decks in tariff['fares_by_service_day'].items():
                    day = 'weekday' if key.startswith('weekday') else 'weekend'
                    for deck, amount in decks.items():
                        self.price(connection,service,'*','*',amount,'ferry',day_type=day,deck=deck)
            else:
                self.price(connection,service,'*','*',tariff['fare_hkd'],'bus_full')

    def snapshot(self, network, at):
        """Read prices and revision in one transaction, including validity dates."""
        from ..graph.adapter import DataUnavailable, fare_table
        from ..graph.build import timestamp
        at_date = timestamp(at).date().isoformat()
        node_ids = {node['id'] for node in network['nodes']}
        overrides = {}
        with self.connection() as connection:
            connection.execute('BEGIN')
            revision = connection.execute('SELECT revision FROM fare_meta WHERE id=1').fetchone()[0]
            schema = connection.execute('PRAGMA schema_version').fetchone()[0]
            key = (revision, schema, at_date, tuple(sorted(node_ids)), tuple(line['id'] for line in network['lines']))
            with self._cache_lock:
                cached = self._snapshot_cache.get(key)
                if cached is not None:
                    self._snapshot_cache.move_to_end(key)
                    return revision, cached
            for line in network['lines']:
                binding = connection.execute('SELECT * FROM fare_services WHERE line_id=?',(line['id'],)).fetchone()
                if not binding:
                    raise DataUnavailable(f"Missing fare database service for {line['id']}")
                rows = connection.execute('SELECT p.*,s.url FROM fare_prices p JOIN fare_sources s USING(source_id) '
                    'WHERE service_id=? AND passenger=? AND payment=? AND valid_from<=? '
                    'AND (valid_until IS NULL OR valid_until>?) ORDER BY valid_from',
                    (binding['service_id'],binding['passenger'],binding['payment'],at_date,at_date))
                # Existing databases can retain the old MTR policy text. It describes
                # fare calculation, not a journey-specific warning.
                tariff = {'group':binding['group_id'],'provenance':'simulated',
                          'note': '' if binding['mode']=='MTR' else binding['note']}
                amounts = []
                if binding['strategy']=='od':
                    matrix = {}
                    aliases = {(r['direction'],r['external_id']):r['node_id'] for r in connection.execute(
                        'SELECT * FROM fare_stop_aliases WHERE line_id=?',(line['id'],))}
                    for row in rows:
                        origin = aliases.get((row['direction'],row['origin']),row['origin'])
                        destination = aliases.get((row['direction'],row['destination']),row['destination'])
                        if origin not in node_ids or destination not in node_ids:
                            continue
                        matrix.setdefault(origin,{})[destination] = row['amount_cents']/100
                        amounts.append(row['amount_cents']/100)
                        tariff['source_url'] = row['url']
                    tariff['od_fares'] = matrix
                    tariff['interchanges'] = [{'from':r['origin'],'to':r['destination'],'max_s':r['max_s']}
                        for r in connection.execute('SELECT * FROM fare_interchanges WHERE group_id=?',(binding['group_id'],))]
                elif binding['strategy']=='service_day':
                    days = {}
                    for row in rows:
                        days.setdefault(row['day_type'],{})[row['deck']] = row['amount_cents']/100
                        amounts.append(row['amount_cents']/100)
                        tariff['source_url'] = row['url']
                    tariff['fares_by_service_day'] = {key:days.get(day,{}) for key,day in
                        [('weekday_peak','weekday'),('weekday_offpeak','weekday'),('saturday','weekend'),('sunday_ph','weekend')]}
                else:
                    for row in rows:
                        if row['origin']=='*' and row['destination']=='*':
                            amounts = [row['amount_cents']/100]
                            tariff['source_url'] = row['url']
                if not amounts:
                    raise DataUnavailable(f"No applicable fare in database for {line['id']} on {at_date}")
                tariff['fare_hkd'] = max(amounts)
                overrides[line['id']] = tariff
        fares = fare_table(network, overrides=overrides)
        with self._cache_lock:
            self._snapshot_cache[key] = fares
            self._snapshot_cache.move_to_end(key)
            while len(self._snapshot_cache) > 4:
                self._snapshot_cache.popitem(last=False)
        return revision, fares

    def status(self):
        with self.connection() as connection:
            connection.execute('BEGIN')
            return {'storage':'sqlite','revision':connection.execute('SELECT revision FROM fare_meta WHERE id=1').fetchone()[0],
                    'price_records':connection.execute('SELECT count(*) FROM fare_prices').fetchone()[0],
                    'services':[dict(row) for row in connection.execute('SELECT line_id,mode,service_id,strategy FROM fare_services ORDER BY line_id')],
                    'sources':[dict(row) for row in connection.execute('SELECT * FROM fare_sources ORDER BY source_id')],
                    'by_mode':{mode:connection.execute('SELECT count(*) FROM fare_prices WHERE service_id LIKE ?',(prefix,)).fetchone()[0]
                               for mode,prefix in [('MTR','mtr:%'),('BUS','bus:%'),('FERRY','FERRY_%')]},
                    'catalogue_services':connection.execute('SELECT count(*) FROM fare_catalog').fetchone()[0]}

    def lookup(self, service_id, origin, destination, at, *, direction='all', day_type='all', deck='all',
               passenger='adult', payment='standard'):
        from ..graph.build import timestamp
        day = timestamp(at).date().isoformat()
        with self.connection() as connection:
            row = connection.execute('SELECT p.*,s.url,s.retrieved_at FROM fare_prices p JOIN fare_sources s USING(source_id) '
                'WHERE service_id=? AND origin=? AND destination=? AND direction=? AND day_type=? AND deck=? '
                'AND passenger=? AND payment=? AND valid_from<=? AND (valid_until IS NULL OR valid_until>?) '
                'ORDER BY valid_from DESC LIMIT 1',
                (service_id,origin,destination,direction,day_type,deck,passenger,payment,day,day)).fetchone()
            if not row:
                return None
            result = dict(row)
            result['fare_hkd'] = result.pop('amount_cents')/100
            result['currency'] = 'HKD'
            return result
