"""Import official MTR, bus and Star Ferry fare datasets into SQLite.

python -m scripts.refresh_fares --download
python -m scripts.refresh_fares --source-dir .cache
Downloads and imports complete datasets; no ticket amounts are defined here.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from itertools import islice
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from backend.app.graph.adapter import SeedDataAdapter
from backend.app.services.fare_store import FareStore, cents

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'mtr_lines_fares.csv':'https://opendata.mtr.com.hk/data/mtr_lines_fares.csv',
    'mtr_lines_and_stations.csv':'https://opendata.mtr.com.hk/data/mtr_lines_and_stations.csv',
    'FARE_BUS.xml':'https://static.data.gov.hk/td/routes-fares-xml/FARE_BUS.xml',
    'ROUTE_BUS.xml':'https://static.data.gov.hk/td/routes-fares-xml/ROUTE_BUS.xml',
    'RSTOP_BUS.xml':'https://static.data.gov.hk/td/routes-fares-xml/RSTOP_BUS.xml',
    'starferry_fares.xlsx':'https://www.starferry.com.hk/sites/default/files/upload/open_data/excel/ferry_sf_central_tsimshatsui_faretable_eng.xlsx'
}


def xml_rows(path, tag):
    events = ET.iterparse(path, events=('start','end'))
    _, root = next(events)
    for event, element in events:
        if event=='end' and element.tag==tag:
            yield {child.tag:child.text or '' for child in element}
            element.clear()
            root.clear()


def ferry_rates(path):
    """Read the operator's labelled sheet, rejecting unknown layouts."""
    ns = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as archive:
        strings = [''.join(item.itertext()) for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si',ns)]
        rows = []
        for row in ET.fromstring(archive.read('xl/worksheets/sheet1.xml')).findall('.//m:sheetData/m:row',ns):
            values = {}
            for cell in row:
                column = ''.join(c for c in cell.get('r') if c.isalpha())
                value = cell.findtext('m:v','',ns)
                if cell.get('t')=='s':
                    value = strings[int(value)]
                elif cell.get('t')=='inlineStr':
                    value = ''.join(cell.find('m:is',ns).itertext())
                values[column] = value.strip()
            rows.append(values)
    header = next((row for row in rows if any(value=='Passenger' for value in row.values())),None)
    adult = next((row for row in rows if any(value=='Adult' for value in row.values())),None)
    if not header or not adult:
        raise ValueError('Cannot identify adult fare table in Star Ferry source')
    rates = {}
    for column, label in header.items():
        text = label.lower()
        if 'fare' not in text:
            continue
        day = 'weekday' if 'mon' in text and 'fri' in text else 'weekend' if 'sat' in text and 'sun' in text else None
        deck = 'upper' if 'upper' in text else 'lower' if 'lower' in text else None
        if not day or not deck:
            raise ValueError('Unrecognized ferry fare column')
        rates[day,deck] = cents(adult[column])
    if set(rates) != {(day,deck) for day in ('weekday','weekend') for deck in ('upper','lower')}:
        raise ValueError('Ferry source is missing a day/deck rate')
    return rates


def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        yield from csv.DictReader(stream)


def import_official(store, directory):
    directory = Path(directory)
    for name in SOURCES:
        if not (directory/name).is_file():
            raise ValueError(f'Missing official source: {name}')
    checked = datetime.now(timezone.utc).isoformat()
    hashes = {}
    for name in SOURCES:
        with (directory/name).open('rb') as stream:
            hashes[name] = hashlib.file_digest(stream,'sha256').hexdigest()
    stations = {row['Station ID']:row['Station Code'] for row in csv_rows(directory/'mtr_lines_and_stations.csv')}
    stops = {}
    for row in xml_rows(directory/'RSTOP_BUS.xml','RSTOP'):
        stops.setdefault((row['ROUTE_ID'],row['ROUTE_SEQ'],row['STOP_ID']),[]).append(row['STOP_SEQ'])
    rates = ferry_rates(directory/'starferry_fares.xlsx')
    # One transaction: a malformed source must never replace a usable database.
    with store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        for source, name in [('mtr','mtr_lines_fares.csv'),('bus_section','FARE_BUS.xml'),
                             ('bus_full','ROUTE_BUS.xml'),('ferry','starferry_fares.xlsx')]:
            store.source(connection,source,SOURCES[name],hashes[name],checked,f'Official import: {name}')
            connection.execute('DELETE FROM fare_prices WHERE source_id=? AND valid_from=?',(source,''))
        for source,name in [('mtr_stations','mtr_lines_and_stations.csv'),('bus_stops','RSTOP_BUS.xml')]:
            store.source(connection,source,SOURCES[name],hashes[name],checked,f'Official import: {name}')
        connection.execute('INSERT OR REPLACE INTO fare_catalog VALUES(?,?,?,?,?)',
                           ('mtr:octopus','MTR','Adult Octopus ordinary class','MTR','mtr'))
        mtr_count = 0
        for row in csv_rows(directory/'mtr_lines_fares.csv'):
            origin = stations.get(row['SRC_STATION_ID'],'mtr_station:'+row['SRC_STATION_ID'])
            destination = stations.get(row['DEST_STATION_ID'],'mtr_station:'+row['DEST_STATION_ID'])
            for key, prefix in [(origin,'SRC'),(destination,'DEST')]:
                connection.execute('INSERT OR IGNORE INTO fare_locations VALUES(?,?,?,?)',
                                   (key,'MTR',row[prefix+'_STATION_NAME'],row[prefix+'_STATION_ID']))
            store.price(connection,'mtr:octopus',origin,destination,
                        row['OCT_ADT_FARE'],'mtr',payment='octopus')
            mtr_count += 1
        if not mtr_count:
            raise ValueError('MTR dataset is empty')
        for row in xml_rows(directory/'ROUTE_BUS.xml','ROUTE'):
            service = 'bus:'+row['ROUTE_ID']
            connection.execute('INSERT OR REPLACE INTO fare_catalog VALUES(?,?,?,?,?)',
                               (service,'BUS',row['ROUTE_NAMEE'],row['COMPANY_CODE'],'bus_full'))
            store.price(connection,service,'*','*',row['FULL_FARE'],'bus_full')
        # Store every directional ON_SEQ/OFF_SEQ section, including routes
        # outside today's planning graph. Batch inserts keep memory bounded.
        def prices():
            for row in xml_rows(directory/'FARE_BUS.xml','FARE'):
                yield ('bus:'+row['ROUTE_ID'],row['ON_SEQ'],row['OFF_SEQ'],row['ROUTE_SEQ'],
                       'all','all','adult','standard','',None,cents(row['PRICE']),'bus_section')
        iterator, bus_count = prices(), 0
        while batch := list(islice(iterator,5000)):
            connection.executemany('INSERT INTO fare_prices VALUES(?,?,?,?,?,?,?,?,?,?,?,?) '
                'ON CONFLICT(service_id,origin,destination,direction,day_type,deck,passenger,payment,valid_from) '
                'DO UPDATE SET amount_cents=excluded.amount_cents,source_id=excluded.source_id',batch)
            bus_count += len(batch)
        if not bus_count:
            raise ValueError('Bus section dataset is empty')
        for alias in connection.execute('SELECT a.*,s.service_id FROM fare_stop_aliases a JOIN fare_services s USING(line_id)').fetchall():
            # Bind by official stop ID, resolving its new sequence on refresh.
            old = alias['external_id']
            if old.startswith('stop:'):
                stop_id = old[5:]
            else:
                stop_id = connection.execute('SELECT stop_id FROM fare_alias_evidence WHERE line_id=? AND direction=? AND node_id=?',
                                             (alias['line_id'],alias['direction'],alias['node_id'])).fetchone()[0]
            route_id = alias['service_id'].split(':',1)[1]
            matches = stops.get((route_id,alias['direction'],stop_id),[])
            if len(matches)!=1:
                raise ValueError(f"Ambiguous or missing official stop: {alias['line_id']} {stop_id}")
            connection.execute('INSERT OR REPLACE INTO fare_alias_evidence VALUES(?,?,?,?)',
                               (alias['line_id'],alias['direction'],alias['node_id'],stop_id))
            connection.execute('UPDATE fare_stop_aliases SET external_id=? WHERE line_id=? AND direction=? AND node_id=?',
                               (matches[0],alias['line_id'],alias['direction'],alias['node_id']))
        service = 'FERRY_TST_CEN'
        connection.execute('INSERT OR REPLACE INTO fare_catalog VALUES(?,?,?,?,?)',
                           (service,'FERRY','Central - Tsim Sha Tsui','Star Ferry','ferry'))
        for (day,deck), amount_cents in rates.items():
            store.price(connection,service,'*','*',amount_cents/100,'ferry',day_type=day,deck=deck)
    return {'mtr_od_records':mtr_count,'bus_section_records':bus_count,'ferry_rates':len(rates)}


def download_sources(directory):
    directory.mkdir(parents=True,exist_ok=True)
    for name, url in SOURCES.items():
        target = directory/name
        temporary = target.with_suffix(target.suffix+'.download')
        with urllib.request.urlopen(url,timeout=60) as response, temporary.open('wb') as output:
            while chunk := response.read(1024*1024):
                output.write(chunk)
        temporary.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,help='Defaults to FARE_DB_PATH or the persistent backend data directory')
    parser.add_argument('--source-dir',type=Path,default=ROOT/'.cache/fare-sources')
    parser.add_argument('--download',action='store_true')
    args = parser.parse_args()
    if args.download:
        download_sources(args.source_dir)
    adapter = SeedDataAdapter(fare_db_path=args.database)
    data = adapter.load()
    import json
    print(json.dumps(import_official(data.fare_store,args.source_dir)))
    print(json.dumps(data.fare_store.status(),ensure_ascii=True))


if __name__ == '__main__':
    main()
