"""Regression cases for OD tickets, fare boundaries and service-day prices."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from backend.app.engine import RouteEngine
from backend.app.engine.fares import path_fares
from backend.app.graph.adapter import DataUnavailable, fare_table
from backend.app.graph.build import timestamp, thaw

ROOT = Path(__file__).resolve().parents[4]
AT = timestamp('2026-09-22T08:20:00+08:00')


def step(line, origin, destination, start=0, end=60, boarding=True):
    from datetime import timedelta
    return SimpleNamespace(edge=SimpleNamespace(line=line, source=origin, target=destination,
                            mode='WALK' if line is None else 'MTR' if line in ('ERL','TML','KTL','TWL','ISL') else 'BUS'),
                           depart=AT+timedelta(seconds=start), arrive=AT+timedelta(seconds=end), boarding=boarding)


class FareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RouteEngine.from_seed()
        cls.network = cls.engine.snapshots.network

    def price(self, path):
        return path_fares(path, self.engine.fares, self.network)

    def test_distinct_od_queries_use_official_adult_octopus_fares(self):
        for origin, destination, expected in [('TAW','ADM',17.1), ('KOT','ADM',13.2),
                                             ('HUH','ADM',12.6), ('EXC','ADM',4.9), ('TAW','KOT',6.7)]:
            for a, b in [(origin,destination), (destination,origin)]:
                with self.subTest(origin=a, destination=b):
                    routes = self.engine.query(a, b, AT, modes=['MTR'])
                    self.assertTrue(routes)
                    for route in routes:
                        self.assertEqual(route['total']['fare_hkd'], expected)
                        self.assertAlmostEqual(sum(l['fare_hkd'] for l in route['legs']), expected)
                        price = next(s for s in route['score_breakdown'] if s['criterion']=='price')
                        self.assertEqual(price['raw'], expected)

    def test_paid_area_line_transfers_charge_one_entry_exit_ticket(self):
        self.assertEqual(self.price([step('ERL','TAW','KOT'), step('KTL','KOT','YMT',60,120),
                                     step('TWL','YMT','ADM',120,180)]), [17.1,0,0])

    def test_octopus_tst_interchange_merges_only_within_30_minutes(self):
        for delay, expected in [(1800,[17.1,0,0]), (1801,[10.1,0,10.6])]:
            path = [step('TML','TAW','ETS'), step(None,'ETS','TST',60,100,False),
                    step('TWL','TST','ADM',60+delay,120+delay)]
            self.assertEqual(self.price(path), expected)
        self.assertEqual(self.price([step('TWL','ADM','TST'), step(None,'TST','ETS',60,100,False),
                                     step('TML','ETS','TAW',100,160)]), [17.1,0,0])

    def test_unrelated_walk_requires_a_new_rail_ticket(self):
        self.assertEqual(self.price([step('ERL','TAW','HUH'), step(None,'HUH','CEN',60,100,False),
                                     step('TWL','CEN','ADM',100,160)]), [6.7,0,4.9])

    def test_bus_section_fares_depend_on_boarding_stop_and_direction(self):
        for origin, destination, expected in [('BS_TAW','BS_ADM_E',20.8),
                                             ('BS_HUH_TUNNEL','BS_ADM_E',12.2),
                                             ('BS_HUH_TUNNEL','BS_TAW',12.9)]:
            self.assertEqual(self.price([step('BUS_182',origin,destination)]), [expected])
        self.assertEqual(self.price([step('BUS_182','BS_TAW','BS_HUH_TUNNEL'),
                                     step('BUS_182','BS_HUH_TUNNEL','BS_ADM_E',60,120,False)]), [20.8,0])
        self.assertEqual(self.price([step('BUS_81C','BS_TAW','TST')]), [9.0])
        self.assertEqual(self.price([step('BUS_81C','TST','BS_TAW')]), [10.2])

    def test_ferry_weekend_holiday_and_wheelchair_deck(self):
        for at, upper, lower in [('2026-09-22T08:20:00+08:00',5.,4.),
                                 ('2026-09-26T08:20:00+08:00',6.5,5.6),
                                 ('2026-10-01T08:20:00+08:00',6.5,5.6)]:
            ferry = step('FERRY_TST_CEN','PIER_TST','PIER_CEN')
            ferry.depart = timestamp(at)
            self.assertEqual(path_fares([ferry],self.engine.fares,self.network), [upper])
            self.assertEqual(path_fares([ferry],self.engine.fares,self.network,{'mobility':'wheelchair'}), [lower])

    def test_missing_or_invalid_od_fare_fails_without_flat_fallback(self):
        fares = thaw(self.engine.fares)
        del fares['ERL']['od_fares']['TAW']['ADM']
        with self.assertRaises(DataUnavailable):
            path_fares([step('ERL','TAW','ADM')],fares,self.network)
        fares['ERL']['od_fares']['TAW']['ADM'] = float('nan')
        with self.assertRaises(DataUnavailable):
            fare_table(thaw(self.network.source), overrides=fares)

    def test_offline_cards_match_current_fares(self):
        bundle = json.loads((ROOT/'contracts/seed/routes.seed.json').read_text(encoding='utf-8'))
        expected = {'r_a3bb2d93a795746f':18.9, 'r_8d4bf8596c86646e':20.8,
                    'r_007c4e09879d19cc':20., 'r_a6162cc3a32c489b':18.9}
        for route in bundle['routes']:
            self.assertEqual(route['total']['fare_hkd'], expected.get(route['route_id'],17.1))
            self.assertAlmostEqual(route['total']['fare_hkd'],sum(l['fare_hkd'] for l in route['legs']))
            self.assertEqual(next(s['raw'] for s in route['score_breakdown'] if s['criterion']=='price'),route['total']['fare_hkd'])


if __name__ == '__main__':
    unittest.main()
