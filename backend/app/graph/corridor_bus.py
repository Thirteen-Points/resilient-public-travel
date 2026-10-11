"""Compose official corridor bus schedules/fares with the existing rail model."""
from copy import deepcopy
from dataclasses import replace
import json, os
from pathlib import Path
from .adapter import fare_table
from .build import thaw

CATALOG_PATH=Path(__file__).resolve().parents[3]/'data/network/corridor_bus.json'

def enabled():
    # Static GTFS data needs no external access. Render serves the public graph;
    # offline packages/tests retain their explicitly frozen demonstration graph.
    default='true' if os.getenv('RENDER_GIT_COMMIT') else 'false'
    return os.getenv('BUS_NETWORK_ENABLED',default).lower() in {'true','1','yes','on'}

class CorridorFareStore:
    def __init__(self,base,base_network,tariffs,catalog):
        self.base,self.base_network,self.tariffs,self.catalog_meta=base,base_network,tariffs,catalog['meta']
    def snapshot(self,network,at):
        revision,fares=self.base.snapshot(self.base_network,at)
        return f"{revision}:gtfs:{self.catalog_meta['archive_sha256'][:12]}",fare_table(network,overrides={**thaw(fares),**self.tariffs})
    def status(self):
        return {**self.base.status(),'corridor_gtfs':self.catalog_meta,'imported_bus_services':len(self.tariffs)}
    def lookup(self,*args,**kwargs): return self.base.lookup(*args,**kwargs)

class CorridorBusAdapter:
    def __init__(self,base,catalog_path=CATALOG_PATH): self.base,self.path=base,Path(catalog_path)
    def load(self):
        data=self.base.load()
        catalog=json.loads(self.path.read_text(encoding='utf-8'))
        network=deepcopy(data.network)
        base_network=deepcopy(network)
        network['lines']=[line for line in network['lines'] if line['mode']!='BUS']
        node_ids={n['id'] for n in network['nodes']}
        tariffs={}
        links=set()
        for service in catalog['services']:
            if len(service['stations'])<2 or len(service['routing_indices'])<2: continue
            selected=[service['stops'][i] for i in service['routing_indices']]
            selected=[stop for stop in selected if stop['pickup'] or stop['drop_off']]
            if len(selected)<2: continue
            matrix={}
            for a in selected:
                for b in selected:
                    price=service['fares'].get(a['td_stop_id'],{}).get(b['td_stop_id'])
                    if price is not None:
                        matrix.setdefault('TD_STOP_'+a['td_stop_id'],{})['TD_STOP_'+b['td_stop_id']]=price
            # A partial tariff cannot be replaced by an invented flat fare.
            if any('TD_STOP_'+b['td_stop_id'] not in matrix.get('TD_STOP_'+a['td_stop_id'],{})
                   for i,a in enumerate(selected) for b in selected[i+1:]): continue
            line_id=service['id']
            for stop in selected:
                nid='TD_STOP_'+stop['td_stop_id']
                if nid not in node_ids:
                    network['nodes'].append({'id':nid,'name_en':stop['name'],'name_zh':stop['name'],'kind':'bus_stop',
                        'lat':stop['lat'],'lng':stop['lng'],'lines':[],'accessible':None,'provenance':'real-derived'})
                    node_ids.add(nid)
                node=next(n for n in network['nodes'] if n['id']==nid)
                node['lines'].append(line_id)
                for station,metres in stop['corridor_distances'].items():
                    if (station,nid) not in links:
                        links.add((station,nid))
                        network.setdefault('walk_links',[]).append({'from':station,'to':nid,'walk_m':max(1,metres),
                            'bidirectional':True,'accessible':None,'provenance':'real-derived',
                            'note':'Station-to-bus connection uses straight-line distance; walkable/step-free path not verified'})
            stops=['TD_STOP_'+s['td_stop_id'] for s in selected]
            times=[b['offset_s']-a['offset_s'] for a,b in zip(selected,selected[1:])]
            if any(t<=0 for t in times): continue
            network['lines'].append({'id':line_id,'name_en':f"Bus {service['route']} · {service['name']}",
                'name_zh':f"巴士 {service['route']}",'mode':'BUS','operator':service['operators'],
                'bidirectional':False,'stops':stops,'seg_time_s':times,'headway_s':None,
                'capacity_per_vehicle':137,'accessible':None,'provenance':'real-derived',
                'gtfs_services':service['schedule'],'gtfs_offset_s':selected[0]['offset_s'],
                'gtfs_pickup':{('TD_STOP_'+s['td_stop_id']):s['pickup'] for s in selected},
                'gtfs_drop_off':{('TD_STOP_'+s['td_stop_id']):s['drop_off'] for s in selected},
                'route_number':service['route'],'td_route_id':service['td_route_id'],'td_direction':service['td_direction'],
                'eta_stops':{('TD_STOP_'+s['td_stop_id']):{'td_stop_id':s['td_stop_id'],'sequence':s['sequence'],
                    'lat':s['lat'],'lng':s['lng'],'name':s['name']} for s in selected},
                'updated_at':catalog['meta']['retrieved_at'],
                'fare_hkd':service['full_fare_hkd'],'source_url':catalog['meta']['source_url'],
                'note':'Official GTFS route, service calendar and fares. Intermediate travel times and 137-person vehicle capacity are model estimates; accessibility unverified.'})
            tariffs[line_id]={'fare_hkd':service['full_fare_hkd'],'group':None,'od_fares':matrix,
                'provenance':'real-derived','source_url':catalog['meta']['source_url'],
                'note':'TD GTFS adult fare for the boarding/alighting stop pair; concessions and interchange discounts excluded'}
        network['meta']['corridor_bus']={**catalog['meta'],'routing_patterns':len(tariffs)}
        network['meta']['note']+='; official corridor GTFS bus schedules/fare pairs; intermediate times and walking links estimated'
        store=CorridorFareStore(data.fare_store,base_network,tariffs,catalog)
        _,fares=store.snapshot(network,'2026-10-12T08:20:00+08:00')
        return replace(data,network=network,fares=fares,fare_store=store)
