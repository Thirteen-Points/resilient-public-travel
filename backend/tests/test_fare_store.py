"""SQL-backed fares: durability, cache invalidation and import rollback."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager

from fastapi.testclient import TestClient
from backend.app.engine import RouteEngine
from backend.app.engine.api import create_app
from backend.app.graph.adapter import DataUnavailable
from backend.app.services.fare_store import FareStore
from scripts.refresh_fares import import_official, ferry_rates

ROOT = Path(__file__).resolve().parents[2]
AT = '2026-10-12T08:20:00+08:00'


class FareStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)/'fares.sqlite3'
        self.engine = RouteEngine.from_seed(fare_db_path=self.path)
        self.store = self.engine.fare_store

    def test_sql_update_changes_prices_and_invalidates_cached_routes_without_restart(self):
        first = self.engine.query('TAW','ADM',AT,modes=['MTR'])
        self.assertEqual(first[0]['total']['fare_hkd'],17.1)
        self.engine.query('TAW','ADM',AT,modes=['MTR'])
        self.assertEqual(self.engine.cache.hits,1)
        with self.store.connection() as connection:
            connection.execute('UPDATE fare_prices SET amount_cents=1800 '
                'WHERE service_id=? AND origin=? AND destination=?',('mtr:octopus','TAW','ADM'))
        updated = self.engine.query('TAW','ADM',AT,modes=['MTR'])
        self.assertEqual(updated[0]['total']['fare_hkd'],18.)
        self.assertEqual(self.engine.cache.hits,1)
        self.assertEqual(next(row['raw'] for row in updated[0]['score_breakdown'] if row['criterion']=='price'),18.)
        self.assertNotEqual(first[0]['evidence'],updated[0]['evidence'])

    def test_unchanged_fare_revision_avoids_rescanning_prices_but_reads_updates(self):
        statements=[]
        original=self.store.connection
        @contextmanager
        def traced():
            with original() as connection:
                connection.set_trace_callback(statements.append)
                yield connection
        self.store.connection=traced
        graph=self.engine.snapshots.network.source
        first_revision,first=self.store.snapshot(graph,AT)
        statements.clear()
        revision,cached=self.store.snapshot(graph,AT)
        self.assertEqual(revision,first_revision)
        self.assertIs(cached,first)
        self.assertTrue(any('SELECT revision' in query for query in statements))
        self.assertFalse(any('SELECT p.*' in query for query in statements))
        with original() as connection:
            connection.execute('UPDATE fare_prices SET amount_cents=1800 WHERE service_id=? AND origin=? AND destination=?',('mtr:octopus','TAW','ADM'))
        statements.clear()
        revision,changed=self.store.snapshot(graph,AT)
        self.assertGreater(revision,first_revision)
        self.assertTrue(any('SELECT p.*' in query for query in statements))
        self.assertEqual(changed['ERL']['od_fares']['TAW']['ADM'],18)

    def test_restart_does_not_overwrite_persisted_fare_changes_with_bootstrap(self):
        with self.store.connection() as connection:
            connection.execute('UPDATE fare_prices SET amount_cents=550 WHERE service_id=? AND origin=? AND destination=?',
                               ('mtr:octopus','EXC','ADM'))
        restarted = RouteEngine.from_seed(fare_db_path=self.path)
        self.assertEqual(restarted.query('EXC','ADM',AT,modes=['MTR'])[0]['total']['fare_hkd'],5.5)

    def test_mtr_fare_policy_is_not_repeated_as_route_warning(self):
        old_note = ('港铁成人八达通普通车厢：按入站/出站票价计费，站内换线不重复收费；'
                    '尖东/尖沙咀30分钟内换乘合并计费')
        with self.store.connection() as connection:
            connection.execute('UPDATE fare_services SET note=? WHERE mode=?', (old_note, 'MTR'))
        routes = self.engine.query('TAW','ADM',AT,modes=['MTR'])
        self.assertTrue(routes)
        self.assertFalse(any(old_note in warning for route in routes for warning in route['warnings']))
        self.assertEqual(routes[0]['total']['fare_hkd'],17.1)

    def test_new_effective_date_does_not_change_old_journeys(self):
        with self.store.connection() as connection:
            self.store.price(connection,'mtr:octopus','TAW','ADM',18.2,'mtr',payment='octopus',valid_from='2026-11-01')
        self.assertEqual(self.engine.query('TAW','ADM',AT,modes=['MTR'])[0]['total']['fare_hkd'],17.1)
        self.assertEqual(self.engine.query('TAW','ADM','2026-11-02T08:20:00+08:00',modes=['MTR'])[0]['total']['fare_hkd'],18.2)

    def test_database_covers_every_mode_and_retains_source_evidence(self):
        status = self.store.status()
        self.assertEqual(status['by_mode'],{'MTR':256,'BUS':10,'FERRY':4})
        self.assertTrue(all(row['url'].startswith('https://') for row in status['sources']))
        self.assertEqual(len(status['services']),10)
        with self.store.connection() as connection:
            for value in (-1,1.001,float('nan'),True):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    self.store.price(connection,'mtr:octopus','TAW','ADM',value,'mtr')
            for value in (-1,1.01):
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute('UPDATE fare_prices SET amount_cents=? WHERE service_id=? AND origin=? AND destination=?',
                                       (value,'mtr:octopus','TAW','ADM'))

    def test_missing_database_price_returns_unavailable_instead_of_flat_price(self):
        with self.store.connection() as connection:
            connection.execute('DELETE FROM fare_prices WHERE origin=? AND destination=?',('TAW','ADM'))
        with self.assertRaises(DataUnavailable):
            self.engine.query('TAW','ADM',AT,modes=['MTR'])

    def test_public_status_and_lookup_read_actual_database(self):
        client = TestClient(create_app(self.engine))
        self.assertEqual(client.get('/api/fares/status').json()['storage'],'sqlite')
        parameters = {'service_id':'mtr:octopus','origin':'TAW','destination':'ADM','at':AT,'payment':'octopus'}
        value = client.get('/api/fares/lookup',params=parameters)
        self.assertEqual(value.status_code,200)
        self.assertEqual(value.json()['fare_hkd'],17.1)
        self.assertEqual(value.json()['source_id'],'mtr')
        self.assertEqual(client.get('/api/fares/lookup',params={**parameters,'destination':'UNKNOWN'}).status_code,404)

    def test_malformed_import_rolls_back_after_starting_to_replace_prices(self):
        directory = Path(self.temporary.name)/'sources'
        directory.mkdir()
        (directory/'mtr_lines_and_stations.csv').write_text('Station ID,Station Code\n1,CEN\n2,ADM\n',encoding='utf-8')
        (directory/'mtr_lines_fares.csv').write_text('SRC_STATION_ID,DEST_STATION_ID,SRC_STATION_NAME,DEST_STATION_NAME,OCT_ADT_FARE\n1,2,Central,Admiralty,INVALID\n',encoding='utf-8')
        for name, root in [('FARE_BUS.xml','FARE'),('RSTOP_BUS.xml','RSTOP'),('ROUTE_BUS.xml','ROUTE')]:
            (directory/name).write_text(f'<dataroot></dataroot>',encoding='utf-8')
        self._ferry_sheet(directory/'starferry_fares.xlsx')
        before = self.store.status()
        with self.assertRaises(ValueError):
            import_official(self.store,directory)
        self.assertEqual(self.store.status(),before)
        self.assertEqual(self.engine.query('TAW','ADM',AT,modes=['MTR'])[0]['total']['fare_hkd'],17.1)

    @staticmethod
    def _ferry_sheet(path):
        import zipfile
        ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        labels = ['Passenger','Mon Fri Upper Deck Fare','Mon Fri Lower Deck Fare',
                  'Sat Sun Upper Deck Fare','Sat Sun Lower Deck Fare','Adult']
        shared = f'<sst xmlns="{ns}">'+''.join(f'<si><t>{label}</t></si>' for label in labels)+'</sst>'
        header = ''.join(f'<c r="{column}1" t="s"><v>{index}</v></c>' for index,column in enumerate('ABCDE'))
        prices = ''.join(f'<c r="{column}2"><v>{value}</v></c>' for column,value in zip('BCDE',[5,4,6.5,5.6]))
        sheet = f'<worksheet xmlns="{ns}"><sheetData><row>{header}</row><row><c r="A2" t="s"><v>5</v></c>{prices}</row></sheetData></worksheet>'
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('xl/sharedStrings.xml',shared)
            archive.writestr('xl/worksheets/sheet1.xml',sheet)

    def test_ferry_import_reads_prices_from_sheet(self):
        path = Path(self.temporary.name)/'ferry.xlsx'
        self._ferry_sheet(path)
        self.assertEqual(ferry_rates(path),{('weekday','upper'):500,('weekday','lower'):400,
                                          ('weekend','upper'):650,('weekend','lower'):560})


if __name__ == '__main__':
    unittest.main()
