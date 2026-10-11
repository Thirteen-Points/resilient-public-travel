"""GTFS service-day boarding; published departures are not constant headways."""
from datetime import timedelta
from math import ceil

def operates(service, day):
    key=day.strftime('%Y%m%d')
    exception=service.get('exceptions',{}).get(key)
    if exception is not None: return exception == 1
    return service['start_date']<=key<=service['end_date'] and bool(service['days'][day.weekday()])

def boarding(edge, at, factor):
    if factor<=0: return None
    candidates=[]
    offset=edge.data['gtfs_offset_s']+edge.offset_s
    midnight=at.replace(hour=0,minute=0,second=0,microsecond=0)
    # Previous service days contain departures beyond 24:00. A future day is
    # intentionally not used to turn an unavailable service into a 24h wait.
    for shift in (-2,-1,0):
        start=midnight+timedelta(days=shift)
        target=(at-start).total_seconds()-offset
        for service in edge.data['gtfs_services']:
            if not operates(service,start.date()): continue
            departures=service['departures']
            for index,value in enumerate(departures):
                if value>=target:
                    interval=(departures[index+1]-value if index+1<len(departures) else value-departures[index-1] if index else 600)
                    candidates.append((start+timedelta(seconds=value+offset),max(60,interval)/factor))
                    break
            for first,last,interval in service['frequency_bands']:
                effective=interval/factor
                value=first+max(0,ceil((target-first)/effective))*effective
                if value<last:
                    candidates.append((start+timedelta(seconds=value+offset),effective))
    return min(candidates,key=lambda item:item[0]) if candidates else None
