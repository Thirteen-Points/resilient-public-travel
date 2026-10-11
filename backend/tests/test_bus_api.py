"""Official response fixtures and imported schedules; no external test calls."""
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.services.ingest.bus_eta import parse_eta
from backend.app.graph.bus_schedule import boarding,operates
from backend.app.graph.corridor_bus import CorridorBusAdapter
from backend.app.graph.adapter import SeedDataAdapter
from backend.app.engine.service import RouteEngine
from backend.app.api.buses import router,catalog

NOW=datetime(2026,10,12,0,20,tzinfo=timezone.utc)
MAPPING={'route':'182','bound':'O','service_type':'1','sequence':'11'}

def test_eta_filters_direction_variant_sequence_past_and_stale():
    base={'route':'182','dir':'O','service_type':1,'seq':11,'data_timestamp':'2026-10-12T08:20:00+08:00','eta':'2026-10-12T08:24:00+08:00'}
    payload={'data':[base,{**base,'dir':'I'},{**base,'service_type':2},{**base,'seq':12},
        {**base,'eta':'2026-10-12T08:19:00+08:00'}]}
    result=parse_eta(payload,'KMB',MAPPING,NOW)
    assert result['status']=='live'
    assert len(result['arrivals'])==1
    assert result['arrivals'][0]['minutes']==4
    old={**payload,'data':[{**base,'data_timestamp':'2026-10-12T08:10:00+08:00'}]}
    assert parse_eta(old,'KMB',MAPPING,NOW)['status']=='stale'
    assert parse_eta({'data':[],'generated_timestamp':NOW.isoformat()},'CTB',MAPPING,NOW)['status']=='no_arrivals'
    mixed={'data':[{**base,'data_timestamp':'2026-10-12T08:10:00+08:00'},
        {**base,'eta':'2026-10-12T08:25:00+08:00'}]}
    assert [a['minutes'] for a in parse_eta(mixed,'KMB',MAPPING,NOW)['arrivals']]==[5]

def test_gtfs_calendar_exceptions_exact_trips_and_overnight():
    service={'start_date':'20260101','end_date':'20261231','days':[1,0,0,0,0,0,0],
        'exceptions':{'20261012':2,'20261013':1},'departures':[3600,90000],'frequency_bands':[]}
    assert not operates(service,datetime(2026,10,12).date())
    assert operates(service,datetime(2026,10,13).date())
    service['exceptions']={}
    edge=SimpleNamespace(data={'gtfs_offset_s':60,'gtfs_services':[service]},offset_s=0)
    at=datetime.fromisoformat('2026-10-13T00:59:00+08:00')
    departure,_=boarding(edge,at,1)
    assert departure.isoformat()=='2026-10-13T01:01:00+08:00'
    assert boarding(edge,datetime.fromisoformat('2026-10-14T08:00:00+08:00'),1) is None

def test_catalogue_offline_lookup_has_no_external_access(monkeypatch):
    monkeypatch.setenv('OFFLINE_MODE','true')
    app=FastAPI();app.include_router(router)
    data=catalog()
    assert data['meta']['route_records']>1000
    assert all(set(s['operators'])<={'KMB','CTB','LWB'} for s in data['services'])
    service=next(s for s in data['services'] if s['route']=='182' and 'TAW' in s['stations'])
    stop=next(p for p in service['stops'] if 'TAW' in p['corridor_distances'])
    with TestClient(app) as client:
        assert client.get('/api/buses/services?station=TAW&q=182').json()['total']>=2
        assert client.get('/api/buses/services?station=UNKNOWN').status_code==400
        reply=client.get('/api/buses/eta',params={'service_id':service['id'],'td_stop_id':stop['td_stop_id']}).json()
        assert reply['status']=='server_offline' and reply['operators']==[]
        assert reply['browser_request']['stop']['td_stop_id']==stop['td_stop_id']
        assert client.get('/api/buses/eta?service_id=https://evil.invalid&td_stop_id=1').status_code==404

@pytest.fixture(scope='module')
def imported_engine(): return RouteEngine.from_adapter(CorridorBusAdapter(SeedDataAdapter()))

@pytest.mark.parametrize('origin,destination',[('TAW','ADM'),('ADM','TAW')])
def test_imported_bus_routes_have_real_stop_pair_fares_and_direction(imported_engine,origin,destination):
    engine=imported_engine
    network=engine.snapshots.network.source
    assert network['meta']['corridor_bus']['routing_patterns']>400
    assert not any(l['mode']=='BUS' and l['id'].startswith('BUS_') for l in network['lines'])
    result=engine.query_details(origin,destination,'2026-10-12T08:20:00+08:00',modes=['BUS'],required_modes=['BUS'])
    assert result['routes']
    assert all(set(l['mode'] for l in r['legs'])<={'WALK','BUS'} for r in result['routes'])
    assert all(r['total']['fare_hkd']>0 for r in result['routes'])
    assert any('182' in next(l['route_number'] for l in network['lines'] if l['id']==leg['line'])
        for r in result['routes'] for leg in r['legs'] if leg['mode']=='BUS')
    wheelchair=engine.query_details('TAW','ADM','2026-10-12T08:20:00+08:00',
        profile={'mobility':'wheelchair'},modes=['BUS'],required_modes=['BUS'])
    assert wheelchair['routes']==[]

def test_gtfs_schedule_has_no_weekend_fabricated_peak_service(imported_engine):
    lines=imported_engine.snapshots.network.source['lines']
    weekday_only=[l for l in lines if l.get('route_number')=='985B']
    assert weekday_only
    for line in weekday_only:
        assert not any(operates(s,datetime(2026,10,11).date()) for s in line['gtfs_services'])

def test_reviewed_bus_closure_applies_to_imported_route_number(imported_engine):
    from backend.app.graph.snapshot import SnapshotStore
    store=SnapshotStore(imported_engine.snapshots.network)
    edge=next(e for e in store.network.edges if e.data.get('route_number')=='182')
    at=datetime.fromisoformat('2026-10-12T08:20:00+08:00')
    event={'event_id':'bus-closure','status':'pending','mode':'BUS','line':'BUS_182',
        'affected_segments':[{'from_node':edge.source,'to_node':edge.target,'impact':'closed','capacity_factor':0}]}
    assert store.update_event(event).impact(edge,at)[0]==1
    assert store.update_event({**event,'status':'published'}).impact(edge,at)[0]==0
    assert store.update_event({**event,'status':'expired'}).impact(edge,at)[0]==1
