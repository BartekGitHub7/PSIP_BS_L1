"""IOP v2 (audited): deterministic model, read-only by default; test/QA Docker only."""
import argparse
import csv
import json
import math
import re
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
CONTAINER = 'remote-db-env-test-postgis-1'
DATABASE = 'psip'
PT = 'ptgn ptkm ptlz ptnz ptpl ptrk ptso pttr ptut ptwp ptwz ptzb'.split()

def psql(query):
    result = subprocess.run(['docker', 'exec', '-i', CONTAINER, 'psql', '-X', '-U', 'psip', '-d', DATABASE, '-At', '-v', 'ON_ERROR_STOP=1'], input=query, text=True, encoding='utf-8', capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout

def validate_config(c):
    if c.get('roads_mode', 'bipolar') not in ('bonus', 'bipolar'):
        raise ValueError('roads_mode: wymagane bonus albo bipolar')
    ditch = c.get('ditch_factor', 1.0)
    if isinstance(ditch, bool) or not isinstance(ditch, (int, float)) or not math.isfinite(ditch) or not 0 <= ditch <= 1:
        raise ValueError('ditch_factor: wymagane 0..1')
    w = c['weights']
    if len(w) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in w) or not math.isclose(sum(w), 4):
        raise ValueError('Cztery dodatnie wagi musza sumowac sie do 4')
    for key in ('water_fraction', 'wetland_fraction', 'water_lines_km_km2', 'roads_km_km2', 'buildings_fraction'):
        if isinstance(c[key], bool) or not isinstance(c[key], (int, float)) or not math.isfinite(c[key]) or c[key] <= 0:
            raise ValueError(key)
    for key in ('water_fraction', 'wetland_fraction', 'buildings_fraction'):
        if c[key] > 1:
            raise ValueError(key + ': udzial nie moze przekraczac 1')
    if not 0 < c['low_coverage'] <= 1 or not 0 <= c['pt_tolerance'] < 1:
        raise ValueError('Progi pokrycia')
    if set(c['land_scores']) != set(PT) or any(not math.isfinite(v) or not -1 <= v <= 1 for v in c['land_scores'].values()):
        raise ValueError('Oceny PT')
    if any(c['land_scores'][k] != 0 for k in ('ptwp', 'ptzb', 'ptkm', 'ptpl')):
        raise ValueError('Woda, zabudowa i komunikacja musza byc neutralne w K1')

def calculate(row, c):
    if row.get('h3_id') is None or not str(row['h3_id']).strip():
        raise ValueError('Brak ID H3')
    def number(key):
        v = row.get(key)
        if isinstance(v, bool) or v is None or not math.isfinite(float(v)) or float(v) < 0:
            raise ValueError('Brak lub niepoprawna wartosc: ' + key)
        return float(v)
    area = number('ot_adja_a_area_m2')
    full = number('hex_area')
    if not full or not area or area > full * (1 + c['pt_tolerance']):
        raise ValueError('Niepoprawna powierzchnia odniesienia')
    pt = {k: number('ot_' + k + '_a_area_m2') for k in PT}
    if abs(sum(pt.values()) - area) > max(2, area * c['pt_tolerance']):
        raise ValueError('Suma PT niezgodna z ADJA')
    land = max(-1, min(1, sum(pt[k] * c['land_scores'][k] for k in PT) / area))
    # Max instead of sum: conservative proxy; aggregate columns cannot resolve overlap.
    hydro_components = dict(water=pt['ptwp'] / area / c['water_fraction'],
        wetlands=number('ot_oimk_a_area_m2') / area / c['wetland_fraction'],
        reeds=number('ot_oisz_a_area_m2') / area / c['wetland_fraction'],
        lines=(number('ot_swrs_l_length_m') + number('ot_swkn_l_length_m') + c.get('ditch_factor', 1.0) * number('ot_swrm_l_length_m')) * 1000 / area / c['water_lines_km_km2'])
    hydro = -min(1, max(hydro_components.values()))
    road_density = min(1, number('ot_skdr_l_length_m') * 1000 / area / c['roads_km_km2'])
    roads = road_density if c.get('roads_mode', 'bipolar') == 'bonus' else 2 * road_density - 1
    buildings = -min(1, number('ot_bubd_a_area_m2') / area / c['buildings_fraction'])
    criteria = [land, hydro, roads, buildings]
    value = sum(w * k for w, k in zip(c['weights'], criteria)) / 4
    if not math.isfinite(value) or not -1 <= value <= 1:
        raise ValueError('IOP poza zakresem')
    return dict(h3_id=str(row['h3_id']), iop=value, k_land=land, k_hydro=hydro,
                k_roads=roads, k_buildings=buildings, coverage=area/full,
                low_coverage=area/full < c['low_coverage'],
                very_low_coverage=area/full < 0.01,
                hydro_driver=max(hydro_components, key=hydro_components.get),
                hydro_saturated=max(hydro_components.values()) >= 1,
                contribution_land=c['weights'][0]*land/4,
                contribution_hydro=c['weights'][1]*hydro/4,
                contribution_roads=c['weights'][2]*roads/4,
                contribution_buildings=c['weights'][3]*buildings/4, error='')

def main():
    global CONTAINER, DATABASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'iop_config.json')
    parser.add_argument('--output', type=Path, default=Path('output/iop'))
    parser.add_argument('--environment', choices=['env-test', 'env-qa'], default='env-test')
    parser.add_argument('--database', default='psip', help='psip albo odizolowana baza iop_rehearsal_*')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Tylko raporty; tryb domyslny')
    mode.add_argument('--write', action='store_true', help='Zapis wybranego srodowiska z kopia i rollback SQL')
    args = parser.parse_args()
    branch = subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip()
    if branch != args.environment:
        raise ValueError('Wymagana galaz ' + args.environment)
    if args.database != 'psip' and not re.fullmatch(r'iop_rehearsal_[a-z0-9_]+', args.database):
        raise ValueError('Dozwolona tylko psip albo iop_rehearsal_*')
    CONTAINER = 'remote-db-' + args.environment + '-postgis-1'
    DATABASE = args.database
    c = json.loads(args.config.read_text(encoding='utf-8'))
    validate_config(c)
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = {}
    all_results = {}
    fingerprints = {}
    for resolution in (6, 7, 8):
        table = f'h3_r{resolution}'
        fingerprints[table] = psql(f"SELECT md5(string_agg(to_jsonb(h)::text, '' ORDER BY h3_id)) FROM grid.{table} h;").strip()
        columns = json.loads(psql(f"SELECT json_agg(column_name) FROM information_schema.columns WHERE table_schema='grid' AND table_name='{table}';"))
        if sum(x.startswith('ot_') for x in columns) != 68 or not {'h3_id','geom','przejezdnosc'} <= set(columns):
            raise ValueError('Nieoczekiwany schemat ' + table)
        rows = [json.loads(line) for line in psql(f'SET default_transaction_read_only=on; SELECT (to_jsonb(h)-\'geom\') || jsonb_build_object(\'hex_area\',ST_Area(geom),\'srid\',ST_SRID(geom)) FROM grid.{table} h ORDER BY h3_id;').splitlines() if line.startswith('{')]
        if not rows or len({r['h3_id'] for r in rows}) != len(rows) or any(r['srid'] != 2180 for r in rows):
            raise ValueError('Pusta siatka, nieunikalne ID lub SRID: ' + table)
        results = []
        for row in rows:
            try:
                result = calculate(row, c)
            except (ValueError, TypeError, KeyError) as exc:
                result = dict(h3_id=str(row['h3_id']), iop=None, error=str(exc))
            results.append(result)
        fields = ['h3_id','iop','k_land','k_hydro','k_roads','k_buildings','coverage','low_coverage','very_low_coverage','hydro_driver','hydro_saturated','contribution_land','contribution_hydro','contribution_roads','contribution_buildings','error']
        with (args.output / (table + '.csv')).open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(results)
        valid = [r for r in results if r['iop'] is not None]
        summaries[table] = dict(count=len(rows), existing=sum(r['przejezdnosc'] is not None for r in rows), invalid=len(rows)-len(valid), low_coverage=sum(r['low_coverage'] for r in valid), minimum=min((r['iop'] for r in valid), default=None), maximum=max((r['iop'] for r in valid), default=None), min_coverage=min((r['coverage'] for r in valid), default=None))
        all_results[table] = results
    report = dict(model_version='2-audited', environment=args.environment, database=DATABASE, source_fingerprints=fingerprints, created_utc=datetime.now(timezone.utc).isoformat(), mode='write' if args.write else 'dry-run', config=c, tables=summaries)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report['tables'], indent=2))
    if any(s['invalid'] for s in summaries.values()):
        raise ValueError('Bledne wiersze w CSV; zapis zablokowany')
    if args.write:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        statements = ['BEGIN;', 'SET lock_timeout=\'10s\';']
        rollback = ['BEGIN;']
        for table, results in all_results.items():
            backup = f'iop_backup_{table}_{stamp}'
            expected = fingerprints[table]
            statements.append(f"LOCK TABLE grid.{table} IN SHARE ROW EXCLUSIVE MODE;")
            statements.append(f"DO $$$$ BEGIN IF (SELECT md5(string_agg(to_jsonb(h)::text, '' ORDER BY h3_id)) FROM grid.{table} h) IS DISTINCT FROM '{expected}' THEN RAISE EXCEPTION 'Dane zmienily sie od dry-run'; END IF; END $$$$;".replace('$$$$', '$$'))
            statements += [f'CREATE TABLE grid.{backup} AS SELECT h3_id, przejezdnosc FROM grid.{table};']
            for r in results:
                identifier = r['h3_id'].replace("'", "''")
                statements.append(f"UPDATE grid.{table} SET przejezdnosc={r['iop']!r} WHERE h3_id::text='{identifier}';")
            rollback.append(f'UPDATE grid.{table} h SET przejezdnosc=b.przejezdnosc FROM grid.{backup} b WHERE h.h3_id=b.h3_id;')
        rollback.append('COMMIT;')
        (args.output / f'rollback_{stamp}.sql').write_text('\n'.join(rollback), encoding='utf-8')
        statements.append('COMMIT;')
        psql('\n'.join(statements))
        print(f'Zapisano {args.environment}/{DATABASE}; kopie w grid.iop_backup_*, rollback w katalogu raportu.')

if __name__ == '__main__':
    main()

