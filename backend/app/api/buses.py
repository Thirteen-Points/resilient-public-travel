"""Public corridor bus catalogue and cached official arrival lookup."""
from functools import lru_cache
import json
from fastapi import APIRouter, HTTPException, Query
from ..graph.corridor_bus import CATALOG_PATH
from ..admin.collect import offline_mode, official_open
from ..services.ingest.bus_eta import BusEtaClient

router=APIRouter(prefix='/api/buses',tags=['official buses'])
client=BusEtaClient(opener=official_open)

@lru_cache(maxsize=1)
def catalog():
    with CATALOG_PATH.open(encoding='utf-8') as handle: return json.load(handle)

@router.get('/status')
def status():
    data=catalog()
    return {'catalogue':data['meta'],'official_apis':['KMB/LWB','Citybus'],
        'server_realtime_enabled':not offline_mode(),'browser_realtime_available':True,
        'realtime_note':'ETA is current observation, not a future-date timetable or confirmed disruption'}

@router.get('/services')
def services(station:str='TAW',q:str='',offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100)):
    if station not in catalog()['meta']['corridor_stations']: raise HTTPException(400,'Unknown corridor station')
    matches=[s for s in catalog()['services'] if station in s['stations'] and
        (not q or q.lower() in (s['route']+' '+s['name']).lower())]
    return {'total':len(matches),'services':[{'id':s['id'],'route':s['route'],'operators':s['operators'],'name':s['name'],
        'direction_label':s['stops'][0]['name']+' → '+s['stops'][-1]['name'],
        'stops':[p for p in s['stops'] if station in p['corridor_distances']]} for s in matches[offset:offset+limit]]}

@router.get('/eta')
def eta(service_id:str,td_stop_id:str):
    service=next((s for s in catalog()['services'] if s['id']==service_id),None)
    if not service: raise HTTPException(404,'Bus service not in corridor catalogue')
    stop=next((s for s in service['stops'] if s['td_stop_id']==td_stop_id and s['corridor_distances']),None)
    if not stop: raise HTTPException(404,'Stop not in corridor catchments for this service')
    request={'service':{'route':service['route'],'operators':service['operators'],'stops':[
        {'lat':s['lat'],'lng':s['lng'],'name':s['name']} for s in service['stops']]},'stop':stop}
    if offline_mode(): return {'status':'server_offline','browser_request':request,'operators':[]}
    return {'status':'checked','browser_request':request,**client.arrivals(service,stop)}
