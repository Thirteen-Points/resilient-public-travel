"""T3.3/T3.4 deterministic simulated acceptance; no shared seed writes."""
import time
import unittest
from backend.app.graph import SnapshotStore, build_graph, next_departure
from backend.app.graph.build import timestamp
from backend.app.graph.adapter import MappingDataAdapter, DataUnavailable
from backend.app.engine import RouteEngine
from backend.app.engine.tests.test_c_route import network, line, event, make_engine, AT
from backend.app.engine.tests.test_contracts import provider


class TimingAcceptance(unittest.TestCase):
    def test_t33_all_service_days_and_public_holiday_override(self):
        schedule={'weekday_peak':180,'weekday_offpeak':360,'saturday':240,'sunday_ph':600}
        graph=build_graph(network([line(headway_s=schedule)]),holidays=['2026-09-23'])
        edge=graph.edges[0]
        for value,headway in [('2026-09-22T08:00:01+08:00',180),
                              ('2026-09-22T12:00:01+08:00',360),
                              ('2026-09-26T08:00:01+08:00',240),
                              ('2026-09-27T08:00:01+08:00',600),
                              ('2026-09-23T08:00:01+08:00',600)]:
            with self.subTest(at=value):
                at=timestamp(value); departure,actual=graph.boarding(edge,at)
                self.assertEqual(actual,headway)
                seconds=(at-at.replace(hour=0,minute=0,second=0,microsecond=0)).total_seconds()
                self.assertEqual((departure-at).total_seconds(),next_departure(seconds,headway)-seconds)
                self.assertGreaterEqual(departure,at)

    def test_t33_ceil_boundary_and_offset(self):
        for seconds,offset,expected in [(180,0,180),(180.01,0,360),(181,60,240),(240,60,240)]:
            self.assertEqual(next_departure(seconds,180,offset),expected)

    def test_t33_explicit_null_stops_service_but_missing_data_is_error(self):
        for headway in (None,{'weekday_peak':None,'weekday_offpeak':None,'saturday':None,'sunday_ph':None}):
            adapter=MappingDataAdapter(network([line(headway_s=headway)]),baseline_fare=5)
            engine=RouteEngine.from_adapter(adapter,load_provider=provider())
            self.assertEqual(engine.query('A','C',AT),[])
        data=network(); del data['lines'][0]['headway_s']
        with self.assertRaises(DataUnavailable):
            MappingDataAdapter(data,baseline_fare=5).load()

    def test_t33_walk_has_no_headway_and_no_boarding_wait(self):
        data=network([line(stops=['B','C'])],[{'from':'A','to':'B','walk_m':140,'accessible':True}])
        engine=make_engine(SnapshotStore(build_graph(data)))
        route=engine.query('A','C',AT)[0]
        walk=route['legs'][0]
        self.assertEqual(walk['mode'],'WALK')
        self.assertNotIn('headway_s',walk)
        self.assertEqual(walk['depart'],AT)
        self.assertEqual(walk['in_vehicle_s'],100)

    def test_t34_published_swap_under_two_seconds_and_closed_edges_blocked(self):
        engine=make_engine(SnapshotStore(build_graph(network())))
        self.assertTrue(engine.query('A','C',AT))  # prime route cache
        pinned=engine.snapshots.current
        start=time.perf_counter()
        changed=engine.snapshots.update_event(event())
        elapsed=time.perf_counter()-start
        self.assertLess(elapsed,2)
        self.assertNotEqual(pinned.snapshot_id,changed.snapshot_id)
        for a,b in [('A','C'),('C','A')]:
            self.assertEqual(engine.query(a,b,AT),[])
        for edge in changed.network.edges:
            if {edge.source,edge.target}=={'A','B'}:
                self.assertEqual(changed.impact(edge,timestamp(AT))[0],0)
                self.assertEqual(pinned.impact(edge,timestamp(AT))[0],1)
        # Reduced capacity is a new immutable snapshot, not permanent closure.
        start=time.perf_counter()
        reduced=engine.snapshots.update_event(event(version=2,affected_segments=[
            {'from_node':'A','to_node':'B','impact':'reduced_capacity','capacity_factor':.5}]))
        reduced_elapsed=time.perf_counter()-start
        self.assertLess(reduced_elapsed,2)
        self.assertNotEqual(changed.snapshot_id,reduced.snapshot_id)
        self.assertTrue(engine.query('A','C',AT))
        edge=next(e for e in reduced.network.edges if e.source=='A' and e.target=='B')
        self.assertEqual(reduced.impact(edge,timestamp(AT))[0],.5)
        print(f'T3.4 snapshot publish: closed={elapsed:.6f}s reduced={reduced_elapsed:.6f}s; both <2s')


if __name__=='__main__':
    unittest.main()
