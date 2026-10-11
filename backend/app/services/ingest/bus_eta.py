"""Official KMB/LWB and Citybus ETA client, with verified stop matching."""
import json, math, threading, time
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

KMB='https://data.etabus.gov.hk/v1/transport/kmb'
CTB='https://rt.data.gov.hk/v2/transport/citybus'

def metres(a,b):
    lat1,lat2=math.radians(float(a['lat'])),math.radians(float(b['lat']))
    d=math.radians(float(b.get('long',b.get('lng')))-float(a.get('long',a.get('lng'))))
    h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(d/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(h)))

def parse_eta(payload,operator,mapping,now=None):
    now=now or datetime.now(timezone.utc)
    data=payload.get('data')
    if not isinstance(data,list): raise ValueError('Malformed bus ETA response')
    arrivals=[]
    observed=payload.get('generated_timestamp')
    fresh=False
    def recent(value):
        try:
            stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
            return stamp.tzinfo is not None and -60 <= (now-stamp).total_seconds() <= 180
        except (ValueError,TypeError,AttributeError): return False
    for row in data:
        if str(row.get('route'))!=mapping['route'] or row.get('dir')!=mapping['bound']: continue
        if operator!='CTB' and str(row.get('service_type'))!=str(mapping['service_type']): continue
        if str(row.get('seq'))!=str(mapping['sequence']): continue
        stamp=row.get('data_timestamp') or payload.get('generated_timestamp')
        if not recent(stamp): continue
        observed=stamp
        fresh=True
        eta=row.get('eta')
        if not eta: continue
        try: at=datetime.fromisoformat(eta.replace('Z','+00:00'))
        except (TypeError,ValueError): continue
        if at.tzinfo is None or at<now: continue
        arrivals.append({'at':at.isoformat(),'minutes':max(0,math.ceil((at-now).total_seconds()/60)),
            'remark':row.get('rmk_en') or row.get('remark_en') or ''})
    if not fresh and not (not data and recent(observed)):
        return {'status':'stale','arrivals':[],'observed_at':observed}
    unique={a['at']:a for a in arrivals}
    return {'status':'live' if unique else 'no_arrivals','arrivals':sorted(unique.values(),key=lambda a:a['at'])[:3],
        'observed_at':observed}

class BusEtaClient:
    def __init__(self,opener=urlopen,timeout=8):
        self.opener,self.timeout=opener,timeout
        self.cache={}
        self.lock=threading.Lock()
    def get(self,url,ttl=60):
        now=time.monotonic()
        with self.lock:
            old=self.cache.get(url)
            if old and now-old[0]<ttl: return old[1]
        request=Request(url,headers={'Accept':'application/json','User-Agent':'ResilientRoute/1.0'})
        with self.opener(request,timeout=self.timeout) as response:
            payload=json.loads(response.read().decode('utf-8'))
        if not isinstance(payload,dict) or 'data' not in payload: raise ValueError('Malformed official bus response')
        with self.lock: self.cache[url]=(now,payload)
        return payload
    def kmb_mapping(self,service,target):
        stops={s['stop']:s for s in self.get(KMB+'/stop',86400)['data']}
        variants=[r for r in self.get(KMB+'/route',86400)['data'] if r['route']==service['route']]
        candidates=[]
        points=service['stops']
        for variant in variants:
            bound='outbound' if variant['bound']=='O' else 'inbound'
            route_stops=self.get(f"{KMB}/route-stop/{quote(service['route'])}/{bound}/{variant['service_type']}",86400)['data']
            known=[(r,stops[r['stop']]) for r in route_stops if r['stop'] in stops]
            if not known: continue
            first=min(metres(points[0],point) for _,point in known[:3])
            last=min(metres(points[-1],point) for _,point in known[-3:])
            row,point=min(known,key=lambda item:metres(target,item[1]))
            separation=metres(target,point)
            if separation>40 or first+last>300: continue
            candidates.append((first+last+separation,{'operator':'KMB','route':service['route'],'bound':variant['bound'],
                'service_type':variant['service_type'],'stop_id':row['stop'],'sequence':row['seq'],
                'stop_name':point['name_en'],'match_metres':round(separation,1)}))
        if not candidates: raise ValueError('No verified official stop match')
        return min(candidates,key=lambda item:item[0])[1]
    def citybus_mapping(self,service,target):
        candidates=[]
        for direction,bound in [('outbound','O'),('inbound','I')]:
            rows=self.get(f"{CTB}/route-stop/CTB/{quote(service['route'])}/{direction}",86400)['data']
            if not rows: continue
            # Sequence is only a lookup hint. Verify actual coordinates and
            # termini, rather than assuming TD and Citybus IDs are equivalent.
            position=max(0,min(len(rows)-1,int(target['sequence'])-1))
            indices=sorted({0,len(rows)-1,*range(max(0,position-2),min(len(rows),position+3))})
            points=[(rows[i],self.get(CTB+'/stop/'+rows[i]['stop'],86400)['data']) for i in indices]
            row,point=min(points,key=lambda item:metres(target,item[1]))
            separation=metres(target,point)
            if separation>40: continue
            score=metres(service['stops'][0],points[0][1])+metres(service['stops'][-1],points[-1][1])+separation
            if score>340: continue
            candidates.append((score,{'operator':'CTB','route':service['route'],'bound':bound,'service_type':'1',
                'stop_id':row['stop'],'sequence':row['seq'],'stop_name':point['name_en'],'match_metres':round(separation,1)}))
        if not candidates: raise ValueError('No verified official stop match')
        return min(candidates,key=lambda item:item[0])[1]
    def arrivals(self,service,target):
        outcomes=[]
        for operator in (['KMB'] if any(o in service['operators'] for o in ('KMB','LWB')) else [])+(['CTB'] if 'CTB' in service['operators'] else []):
            try:
                mapping=self.kmb_mapping(service,target) if operator=='KMB' else self.citybus_mapping(service,target)
                url=(f"{KMB}/eta/{mapping['stop_id']}/{quote(service['route'])}/{mapping['service_type']}" if operator=='KMB'
                     else f"{CTB}/eta/CTB/{mapping['stop_id']}/{quote(service['route'])}")
                result=parse_eta(self.get(url),operator,mapping)
                outcomes.append({**result,**mapping,'source_url':url})
            except Exception:
                outcomes.append({'operator':operator,'status':'unavailable','arrivals':[],'observed_at':None})
        return {'checked_at':datetime.now(timezone.utc).isoformat(),'operators':outcomes}
