"""Read-only comparison of persisted IOP with audited CSV, MVT and GUI click."""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gui'))
import main as gui
import psycopg

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--environment', choices=['env-test','env-qa'], default='env-test')
p.add_argument('--database', default='psip')
p.add_argument('--expected', type=Path, default=ROOT/'output/iop/audit_20261103')
a = p.parse_args()
container = 'remote-db-' + a.environment + '-postgis-1'
password = subprocess.check_output(['docker','exec',container,'printenv','POSTGRES_PASSWORD'], text=True).strip()
settings = dict(host='localhost', port=5444 if a.environment=='env-test' else 5445, dbname=a.database, user='psip', password=password, options='-c default_transaction_read_only=on')
checks = []
with psycopg.connect(**settings) as conn:
    for r in (6,7,8):
        table = f'h3_r{r}'
        with (a.expected/(table+'.csv')).open(encoding='utf-8') as f:
            expected = {v['h3_id']: float(v['iop']) for v in csv.DictReader(f)}
        actual = dict(conn.execute(gui.sql.SQL('SELECT h3_id::text,przejezdnosc FROM {}').format(gui.sql.Identifier('grid',table))).fetchall())
        assert actual.keys()==expected.keys()
        delta = max(abs(actual[k]-expected[k]) for k in expected)
        assert delta < 1e-12, delta
        for suffix,srid in [('',2180),('_2180',2180),('_3857',3857)]:
            layer=gui.describe_layer(conn,('grid',table+suffix,'geom',srid),settings)
            assert layer['table']==table and layer['has_passability']
        layer.update(key=r,color='#ffffff',visible=SimpleNamespace(get=lambda:True))
        hid,x,y=conn.execute(gui.sql.SQL('SELECT h3_id::text,ST_X(p),ST_Y(p) FROM (SELECT h3_id,ST_Transform(ST_PointOnSurface(geom),3857) p FROM {}) q LIMIT 1').format(gui.sql.Identifier('grid',table))).fetchone()
        state=SimpleNamespace(layers=[layer],busy=False,zoom_level=10,center=((x+gui.HALF_WORLD)/gui.WORLD,(gui.HALF_WORLD-y)/gui.WORLD),map=SimpleNamespace(winfo_width=lambda:400,winfo_height=lambda:400),cell_info=Mock(),draw_selected_hexagon=lambda:None)
        state.run_background=lambda work,finished:finished(work())
        gui.GISApp.inspect_cell(state,200,200)
        text=state.cell_info.set.call_args.args[0]
        assert hid in text and f'{expected[hid]:+.4f}' in text and 'PostGIS' in text
        z=10;tx=int((x+gui.HALF_WORLD)/gui.WORLD*2**z);ty=int((gui.HALF_WORLD-y)/gui.WORLD*2**z)
        blob=conn.execute(gui.tile_query(layer),(z,tx,ty,z,tx,ty,gui.WORLD/2**z/16,2180)).fetchone()[0]
        features=gui.mapbox_vector_tile.decode(bytes(blob))['features']['features']
        assert features
        for feature in features:
            props=feature['properties']
            assert abs(props['przejezdnosc']-expected[props['id']]) < 1e-12
        image,_,count=gui.fetch_tile(layer,z,tx,ty)
        assert image.size==(256,256) and count
        checks.append(dict(table=table,count=len(actual),max_delta=delta,gui_click=True,mvt=True,preview=False))
print(json.dumps(dict(environment=a.environment,database=a.database,checks=checks),indent=2))
