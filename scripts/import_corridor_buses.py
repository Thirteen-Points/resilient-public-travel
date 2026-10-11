"""Compile TD GTFS buses serving the six East Rail corridor catchments.

No runtime download. Official schedules/fares are retained; intermediate stop
times absent from the feed are explicitly estimated from its timed endpoints.
"""
from __future__ import annotations
import argparse, csv, hashlib, html, io, json, math, re, zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORRIDOR = ('TAW','KOT','MKK','HUH','EXC','ADM')
SOURCE = 'https://static.data.gov.hk/td/pt-headway-en/gtfs.zip'

def distance(a,b):
    lat1,lat2 = math.radians(float(a['lat'])),math.radians(float(b['lat']))
    dlat,dlon = lat2-lat1,math.radians(float(b['lng'])-float(a['lng']))
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(h)))

def clock(text):
    values=list(map(int,text.split(':')))
    return values[0]*3600+values[1]*60+(values[2] if len(values)>2 else 0)

def clean_name(text,agency):
    options=text.split('|')
    preferred=next((s for s in options if s.startswith('['+agency+']')),options[0])
    return html.unescape(re.sub(r'<[^>]+>|\[[^\]]+\]',' ',preferred)).strip().replace('  ',' ')

def compile_feed(archive, base_network, radius=800):
    stations={n['id']:n for n in base_network['nodes'] if n['id'] in CORRIDOR}
    with zipfile.ZipFile(archive) as z:
        def rows(name): return csv.DictReader(io.TextIOWrapper(z.open(name+'.txt'),encoding='utf-8-sig'))
        routes={r['route_id']:r for r in rows('routes') if r['route_type']=='3' and set(r['agency_id'].split('+')) <= {'KMB','CTB','LWB'}}
        stops={s['stop_id']:{'id':s['stop_id'],'raw_name':s['stop_name'],'lat':float(s['stop_lat']),'lng':float(s['stop_lon'])} for s in rows('stops')}
        near={sid:{station:round(distance(s,node)) for station,node in stations.items() if distance(s,node)<=radius} for sid,s in stops.items()}
        near={sid:matches for sid,matches in near.items() if matches}
        trips={t['trip_id']:t for t in rows('trips') if t['route_id'] in routes}
        representative={}
        for t in trips.values(): representative.setdefault((t['route_id'],t['trip_id'].split('-')[1]),t['trip_id'])
        patterns={tid:[] for tid in representative.values()}
        signatures={tid:hashlib.sha256() for tid in trips}
        endpoints={}
        for s in rows('stop_times'):
            tid=s['trip_id']
            if tid not in trips: continue
            signatures[tid].update('|'.join(s[k] for k in ('stop_id','stop_sequence','pickup_type','drop_off_type')).encode())
            if tid in patterns: patterns[tid].append(s)
            if s['departure_time']: endpoints.setdefault(tid,[]).append(clock(s['departure_time']))
        frequencies=defaultdict(list)
        for f in rows('frequencies'):
            if f['trip_id'] in trips:
                frequencies[f['trip_id']].append([clock(f['start_time']),clock(f['end_time']),int(f['headway_secs'])])
        calendars={s['service_id']:s for s in rows('calendar')}
        exceptions=defaultdict(dict)
        for s in rows('calendar_dates'): exceptions[s['service_id']][s['date']]=int(s['exception_type'])
        grouped=defaultdict(list)
        for tid,t in trips.items(): grouped[(t['route_id'],tid.split('-')[1])].append(t)
        for key,group in grouped.items():
            if len({signatures[t['trip_id']].hexdigest() for t in group})!=1:
                raise ValueError(f'GTFS stop patterns differ for {key}; split those patterns before importing their schedules')
        services={}
        for key,tid in representative.items():
            ordered=sorted(patterns[tid],key=lambda s:int(s['stop_sequence']))
            covered={sid:[] for sid in stations}
            for index,s in enumerate(ordered):
                for station,metres in near.get(s['stop_id'],{}).items():
                    covered[station].append((metres,index))
            covered={station:matches for station,matches in covered.items() if matches}
            if not covered: continue
            r=routes[key[0]]
            selected=sorted({min(matches)[1] for matches in covered.values()})
            timetable=defaultdict(lambda:{'departures':[],'frequency_bands':[]})
            for t in grouped[key]:
                ttid=t['trip_id']
                if ttid not in endpoints: continue
                entry=timetable[t['service_id']]
                if frequencies[ttid]: entry['frequency_bands'].extend(frequencies[ttid])
                else: entry['departures'].append(endpoints[ttid][0])
            schedules=[]
            for sid,schedule in timetable.items():
                cal=calendars.get(sid)
                if not cal: continue
                schedules.append({'service_id':sid,'days':[int(cal[d]) for d in ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')],
                    'start_date':cal['start_date'],'end_date':cal['end_date'],'exceptions':exceptions[sid],
                    'departures':sorted(set(schedule['departures'])),
                    'frequency_bands':sorted({tuple(b) for b in schedule['frequency_bands']})})
            times=endpoints[tid]
            duration=times[-1]-times[0] if len(times)>=2 else 0
            if duration<=0: continue
            positions=[0.0]
            for a,b in zip(ordered,ordered[1:]): positions.append(positions[-1]+max(20,distance(stops[a['stop_id']],stops[b['stop_id']])))
            offsets=[round(p/positions[-1]*duration,2) for p in positions]
            service_key=f"TD_{key[0]}_{key[1]}"
            services[service_key]={'id':service_key,'td_route_id':key[0],'td_direction':key[1],
                'route':r['route_short_name'],'operators':r['agency_id'].split('+'),'name':r['route_long_name'],
                'route_url':r['route_url'],'stations':list(covered),
                'stops':[{'td_stop_id':s['stop_id'],'name':clean_name(stops[s['stop_id']]['raw_name'],r['agency_id']),
                    'lat':stops[s['stop_id']]['lat'],'lng':stops[s['stop_id']]['lng'],'sequence':int(s['stop_sequence']),
                    'pickup':s['pickup_type']!='1','drop_off':s['drop_off_type']!='1',
                    'corridor_distances':near.get(s['stop_id'],{}),'offset_s':offsets[i]} for i,s in enumerate(ordered)],
                'routing_indices':selected,'schedule':schedules,'fares':{},
                'time_basis':'GTFS timed endpoints; intermediate times estimated by distance',
                'accessibility':None,'capacity_basis':'No official vehicle capacity or step-free evidence in this feed'}
        wanted={s['td_route_id'] for s in services.values()}
        fare_ids={f['fare_id'] for f in rows('fare_rules') if f['route_id'] in wanted}
        prices={f['fare_id']:float(f['price']) for f in rows('fare_attributes') if f['fare_id'] in fare_ids and f['currency_type']=='HKD'}
        fare_rules=defaultdict(dict)
        for f in rows('fare_rules'):
            if f['route_id'] in wanted and f['fare_id'] in prices:
                direction=f['fare_id'].split('-')[1]
                fare_rules[(f['route_id'],direction)][(f['origin_id'],f['destination_id'])]=prices[f['fare_id']]
        for s in services.values():
            tariff=fare_rules[(s['td_route_id'],s['td_direction'])]
            kept={s['stops'][i]['td_stop_id'] for i in s['routing_indices']}
            s['fares']={a:{b:price for (origin,b),price in tariff.items() if origin==a and b in kept} for a in kept}
            s['full_fare_hkd']=max(tariff.values(),default=None)
    return {'meta':{'source_url':SOURCE,'archive_sha256':hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
        'retrieved_at':datetime.fromtimestamp(Path(archive).stat().st_mtime,timezone.utc).isoformat(),
        'catchment_m':radius,'corridor_stations':list(stations),'selection':'All KMB/LWB/Citybus patterns with a stop within the corridor station catchments',
        'route_records':len(services),'route_numbers':len({(s['route'],tuple(s['operators'])) for s in services.values()})},
        'services':list(services.values())}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'data/network/corridor_bus.json')
    args=parser.parse_args()
    base=json.loads((ROOT/'contracts/seed/network.seed.json').read_text(encoding='utf-8'))
    result=compile_feed(args.archive,base)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({**result['meta'],'routing_patterns':sum(len(s['routing_indices'])>=2 and len(s['stations'])>=2 for s in result['services']),
        'operators':sorted({o for s in result['services'] for o in s['operators']})},ensure_ascii=False))
