"""Read-only integration: PostGIS, MVT, dry-run GUI and click for every H3 resolution."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'app')]
import main as gui
from iop_display import load_preview
import psycopg


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',type=Path,default=ROOT/'output/iop/audit_20261103')
    args=parser.parse_args()
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='env-test':raise ValueError('env-test only')
    password=subprocess.check_output(['docker','exec','remote-db-env-test-postgis-1','printenv','POSTGRES_PASSWORD'],text=True).strip()
    settings=dict(host='localhost',port=5444,dbname='psip',user='psip',password=password,options='-c default_transaction_read_only=on -c statement_timeout=60000')
    datasets,low,report=load_preview(args.preview)
    all_layers=[];checks=[]
    with psycopg.connect(**settings) as conn:
        for resolution in (6,7,8):
            table=f'h3_r{resolution}'
            layers=[gui.describe_layer(conn,('grid',t,'geom',s),settings) for t,s in [(table,2180),(table+'_2180',2180),(table+'_3857',3857)]]
            assert all(l['table']==table and l['has_passability'] and l['has_coverage'] for l in layers)
            actual=conn.execute(gui.sql.SQL("SELECT md5(string_agg(to_jsonb(h)::text, '' ORDER BY h3_id)) FROM {} h").format(gui.sql.Identifier('grid',table))).fetchone()[0]
            assert actual==report['source_fingerprints'][table]
            layer=layers[0];layer.update(key=resolution,color='#ffffff',visible=SimpleNamespace(get=lambda:True),scale_mode='reference',low_threshold=low)
            all_layers.append(layer)
            h3id,x,y=conn.execute(gui.sql.SQL('SELECT h3_id::text,ST_X(p),ST_Y(p) FROM (SELECT h3_id,ot_adja_a_area_m2/ST_Area(geom) c, ST_Transform(ST_PointOnSurface(geom),3857) p FROM {}) q ORDER BY c LIMIT 1').format(gui.sql.Identifier('grid',table))).fetchone()
            # Actual click query with persisted NULL; then same query with local dry-run selected.
            state=SimpleNamespace(layers=[layer],busy=False,zoom_level=10,center=((x+gui.HALF_WORLD)/gui.WORLD,(gui.HALF_WORLD-y)/gui.WORLD),map=SimpleNamespace(winfo_width=lambda:400,winfo_height=lambda:400),cell_info=Mock(),draw_selected_hexagon=lambda:None)
            state.run_background=lambda work,finished:finished(work())
            gui.GISApp.inspect_cell(state,200,200)
            text=state.cell_info.set.call_args.args[0]
            persisted=conn.execute(gui.sql.SQL('SELECT przejezdnosc FROM {} WHERE h3_id::text=%s').format(gui.sql.Identifier('grid',table)),(h3id,)).fetchone()[0]
            assert h3id in text and ('NULL' if persisted is None else f'{persisted:+.4f}') in text and 'NISKIE' in text
            layer['preview']=datasets[table]
            gui.GISApp.inspect_cell(state,200,200)
            text=state.cell_info.set.call_args.args[0]
            assert f"{datasets[table][h3id]['iop']:+.4f}" in text and 'DRY-RUN' in text and 'K1/K2/K3/K4' in text
            # Actual MVT with IDs -> same local values as clicking; inspect decoded values and coverage.
            z=10;tx=int((x+gui.HALF_WORLD)/gui.WORLD*2**z);ty=int((gui.HALF_WORLD-y)/gui.WORLD*2**z)
            blob=conn.execute(gui.tile_query(layer),(z,tx,ty,z,tx,ty,gui.WORLD/2**z/16,2180)).fetchone()[0]
            features=gui.mapbox_vector_tile.decode(bytes(blob))['features']['features']
            assert features and any(f['properties']['id']==h3id for f in features)
            for f in features:
                p=f['properties'];value,coverage=gui.preview_value(layer,p['id'],p.get('przejezdnosc'),p.get('coverage'))
                assert value==datasets[table][p['id']]['iop']
                assert abs(coverage-datasets[table][p['id']]['coverage'])<1e-12
            reference,_,_=gui.fetch_tile(layer,z,tx,ty)
            layer['scale_mode']='contrast';contrast,_,_=gui.fetch_tile(layer,z,tx,ty)
            assert not np.array_equal(np.asarray(reference),np.asarray(contrast))
            layer['context']=True;context,_,_=gui.fetch_tile(layer,z,tx,ty)
            assert context.size==(256,256)
            context.save(args.preview/f'gui_tile_r{resolution}_context.png')
            assert conn.execute(gui.sql.SQL('SELECT count(przejezdnosc) FROM {}').format(gui.sql.Identifier('grid',table))).fetchone()[0]==report['tables'][table]['existing']
            checks.append(f'R{resolution}: aliases, fingerprint, actual click database/CSV/coverage, MVT, both scales, local BDOT context OK')
    # Real Tk initialization and controls: sources, legends, scale changes and queued callbacks.
    app=gui.GISApp();app.withdraw()
    try:
        app.run_background=lambda work,finished,failed=None:finished(work())
        for layer in all_layers:app.add_layer(dict(layer))
        with patch.object(gui.filedialog,'askdirectory',return_value=str(args.preview)):
            app.open_preview()
        assert app.preview_data is not None and 'DRY-RUN' in app.source_info.get()
        app.scale_mode.set('contrast')
        assert 'nasycone' in app.legend_note.get()
        assert all(l['scale_mode']=='contrast' for l in app.layers)
        app.context_map.set(True);app.change_display()
        assert all(l['context'] for l in app.layers)
        app.choose_resolution('h3_r7')
        assert sum(l['visible'].get() for l in app.layers)==1
        callback=Mock();app.events.put((callback,'event-test',None,None));app.process_events();callback.assert_called_once_with('event-test')
        # Old tile result must not enter a new-style cache.
        key=(app.layers[0]['key'],10,1,1,app.style_revision-1)
        app.pending.add(key);app.tile_events.put((key,(gui.Image.new('RGBA',(256,256)),1,1),None));app.process_tiles()
        assert key not in app.cache
        app.use_database_scores();assert all(l.get('preview') is None for l in app.layers)
        assert 'PostGIS' in app.source_info.get()
        app.update_idletasks()
        checks.append('Tk controls: load validated CSV, source switch, legend, context, one resolution, async callback, stale tile rejection OK')
    finally:app.close_app()
    result=dict(checks=checks,postgis_writes=False,preview=str(args.preview))
    (args.preview/'gui_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('\n'.join(checks))

if __name__=='__main__':main()
