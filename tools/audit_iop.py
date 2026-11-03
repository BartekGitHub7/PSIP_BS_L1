"""Reproducible read-only model audit, sensitivity study and H3 map exports."""
import argparse
import copy
import csv
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib.patches import Polygon, Patch
from matplotlib.collections import PatchCollection

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT/'gui')]
from iop import calculate, validate_config, psql
from iop_display import passability_color

FIELDS=['h3_id','iop','k_land','k_hydro','k_roads','k_buildings','coverage','low_coverage','very_low_coverage','hydro_driver','hydro_saturated','contribution_land','contribution_hydro','contribution_roads','contribution_buildings','error']

def write_csv(path,rows,fields=None):
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields or list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def scenarios(config):
    values={'audited':copy.deepcopy(config)}
    for name,road,ditch in [('original_v1','bipolar',1),('roads_bonus_only','bonus',1),('ditch_only','bipolar',.25)]:
        c=copy.deepcopy(config);c.update(roads_mode=road,ditch_factor=ditch);values[name]=c
    for key,params in [('ditch_factor',[0,.5,1]),('roads_km_km2',[7.5,12.5]),('water_lines_km_km2',[3.75,6.25]),('water_fraction',[.15,.25]),('wetland_fraction',[.15,.25]),('buildings_fraction',[.15,.25])]:
        for value in params:
            c=copy.deepcopy(config);c[key]=value;values[f'{key}_{value}']=c
    for key,params in [('ptlz',[-1,-.6]),('pttr',[.4,.8])]:
        for value in params:
            c=copy.deepcopy(config);c['land_scores'][key]=value;values[f'{key}_{value}']=c
    for i in range(4):
        for factor in (.75,1.25):
            c=copy.deepcopy(config);c['weights'][i]*=factor
            c['weights']=[4*w/sum(c['weights']) for w in c['weights']]
            values[f'weight_{i+1}_{factor}']=c
    for c in values.values():validate_config(c)
    return values

def rank(values):
    values=np.asarray(values);ordered=np.argsort(values);ranks=np.empty(len(values),float)
    start=0
    while start<len(values):
        end=start+1
        while end<len(values) and values[ordered[end]]==values[ordered[start]]:end+=1
        ranks[ordered[start:end]]=(start+end-1)/2;start=end
    return ranks

def draw_map(rows,results,resolution,mode,destination,context,low_threshold=0.1):
    patches=[];colors=[];low=[]
    for row,r in zip(rows,results):
        geo=row['geometry'];polygons=geo['coordinates'] if geo['type']=='MultiPolygon' else [geo['coordinates']]
        for polygon in polygons:
            # H3 cells have no holes; fail rather than silently filling any unexpected interior.
            if len(polygon)!=1: raise ValueError('Unexpected H3 polygon hole')
            patch=Polygon(polygon[0]);patches.append(patch);colors.append(passability_color(r['iop'],mode))
            if r['low_coverage']:low.append(Polygon(polygon[0]))
    fig,ax=plt.subplots(figsize=(10.5,9),layout='constrained')
    ax.set_facecolor('#f7f8fa')
    ax.add_collection(PatchCollection(patches,facecolors=colors,edgecolors='#3d4855',linewidths=.55 if resolution<8 else .23))
    if low:ax.add_collection(PatchCollection(low,facecolors='none',edgecolors='#444444',linewidths=.45,hatch='///'))
    from matplotlib.lines import Line2D
    from shapely.geometry import shape
    for geo,color,width in context:
        geometry=shape(geo)
        parts=list(geometry.geoms) if geometry.geom_type=='MultiLineString' else [geometry]
        for line in parts:
            if line.geom_type=='LineString':
                xy=np.asarray(line.coords);ax.plot(xy[:,0],xy[:,1],color=color,lw=width,alpha=.65)
    ax.autoscale();ax.set_aspect('equal');ax.set_axis_off()
    scores=np.array([r['iop'] for r in results]);nlow=sum(r['low_coverage'] for r in results)
    ax.set_title(f'IOP • H3 R{resolution} • '+('skala referencyjna' if mode=='reference' else 'zwiększony kontrast'),fontsize=17,fontweight='bold',loc='left',pad=22)
    ax.text(0,1.012,f'Dry-run | {len(rows)} heksagonów | IOP {scores.min():+.3f}…{scores.max():+.3f} | EPSG:2180',transform=ax.transAxes,fontsize=10,color='#475569')
    limit=1 if mode=='reference' else .5
    ticks=[-limit,-limit/2,0,limit/2,limit]
    cmap=LinearSegmentedColormap.from_list(mode,[passability_color(v,mode) for v in np.linspace(-limit,limit,1025)],N=1025)
    cb=fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(-limit,limit),cmap=cmap),ax=ax,shrink=.7,pad=.015,extend='neither' if mode=='reference' else 'both',ticks=ticks)
    cb.set_label('IOP — rzeczywista wartość',fontsize=11)
    from matplotlib.ticker import FuncFormatter
    cb.ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:+.2f}'))
    labels=[Patch(facecolor='white',edgecolor='#444444',hatch='///',label=f'Pokrycie <{low_threshold:.0%}: {nlow} heksagonów')]
    if context:labels += [Line2D([0],[0],color='#303030',lw=1,label='Drogi BDOT'),Line2D([0],[0],color='#1467b1',lw=1,label='Cieki BDOT')]
    ax.legend(handles=labels,loc='lower left',frameon=True,fontsize=9)
    saturation=int(np.count_nonzero(abs(scores)>.5))
    note='Stała skala liniowa −1…+1. Bez dopasowania min–max.' if mode=='reference' else f'Stały zakres barw −0,50…+0,50; gamma 0,65. Nasycenie poza zakresem: {saturation} heksagonów. IOP bez zmian.'
    fig.supxlabel(note+'\nModel przybliżony; kolor nie jest gwarancją przejazdu. Kreskowanie oznacza małe pokrycie, nie niskie IOP.',fontsize=9,color='#334155')
    fig.savefig(destination,dpi=170,facecolor='white');plt.close(fig)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output/iop/audit_20261103')
    args=parser.parse_args()
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='env-test':raise ValueError('env-test only')
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'app/iop_config.json').read_text());variants=scenarios(config)
    summaries={};details={};comparison=[];fingerprints={};before={}
    for resolution in (6,7,8):
        table=f'h3_r{resolution}'
        # One read-only repeatable-read snapshot for attributes, geometry and fingerprint.
        query=f"BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT json_build_object('fingerprint',(SELECT md5(string_agg(to_jsonb(h)::text, '' ORDER BY h3_id)) FROM grid.{table} h),'columns',(SELECT json_agg(column_name) FROM information_schema.columns WHERE table_schema='grid' AND table_name='{table}'),'rows',(SELECT json_agg(r ORDER BY h3_id) FROM (SELECT (to_jsonb(h)-'geom') || jsonb_build_object('hex_area',ST_Area(geom),'srid',ST_SRID(geom),'geometry',ST_AsGeoJSON(geom)::json) r,h3_id FROM grid.{table} h) q)); COMMIT;"
        source=json.loads(next(line for line in psql(query).splitlines() if line.startswith('{')))
        if sum(x.startswith('ot_') for x in source['columns'])!=68:raise ValueError('68 ot_* required')
        rows=source['rows'];fingerprints[table]=source['fingerprint'];before[table]=source['fingerprint']
        if len({r['h3_id'] for r in rows})!=len(rows) or any(r['srid']!=2180 for r in rows):raise ValueError('IDs / SRID')
        (out/(table+'_inputs.json')).write_text(json.dumps(source),encoding='utf-8')
        runs={name:[calculate(r,c) for r in rows] for name,c in variants.items()}
        base=np.array([r['iop'] for r in runs['audited']]);original=np.array([r['iop'] for r in runs['original_v1']])
        for name,result in runs.items():
            vals=np.array([r['iop'] for r in result]);delta=vals-base
            rank_correlation=float(np.corrcoef(rank(vals),rank(base))[0,1])
            comparison.append(dict(table=table,scenario=name,count=len(vals),minimum=float(vals.min()),p05=float(np.quantile(vals,.05)),median=float(np.median(vals)),p95=float(np.quantile(vals,.95)),maximum=float(vals.max()),mean=float(vals.mean()),mean_abs_delta=float(abs(delta).mean()),p95_abs_delta=float(np.quantile(abs(delta),.95)),max_abs_delta=float(abs(delta).max()),sign_changes=int(np.count_nonzero(vals*base<0)),spearman_vs_audited=rank_correlation,below_minus005=int(np.count_nonzero(vals<-.05)),near_zero=int(np.count_nonzero(abs(vals)<=.05)),above_plus005=int(np.count_nonzero(vals>.05))))
        result=runs['audited'];valid=len(result)
        previous_path=ROOT/'output/iop'/(table+'.csv')
        if previous_path.exists():
            with previous_path.open(encoding='utf-8-sig') as previous_file:
                previous={r['h3_id']:float(r['iop']) for r in csv.DictReader(previous_file)}
            previous_delta=max(abs(r['iop']-previous[r['h3_id']]) for r in result)
        else: previous_delta=None
        plausible=[v for k,v in runs.items() if k not in ('original_v1','ditch_only')]
        envelope=[]
        for i,r in enumerate(result):
            vals=[v[i]['iop'] for v in plausible]
            envelope.append(dict(h3_id=r['h3_id'],audited=r['iop'],scenario_min=min(vals),scenario_max=max(vals),sign_unstable=min(vals)<0<max(vals),coverage=r['coverage']))
        write_csv(out/(table+'_sensitivity_envelope.csv'),envelope)
        write_csv(out/(table+'.csv'),result,FIELDS)
        write_csv(out/(table+'_original_v1.csv'),runs['original_v1'],FIELDS)
        write_csv(out/(table+'_before_after.csv'),[dict(h3_id=r['h3_id'],old=float(old),new=float(new),delta=float(new-old)) for r,old,new in zip(rows,original,base)])
        summaries[table]=dict(count=valid,existing=sum(r['przejezdnosc'] is not None for r in rows),invalid=0,low_coverage=sum(r['low_coverage'] for r in result),very_low_coverage=sum(r['very_low_coverage'] for r in result),minimum=float(base.min()),maximum=float(base.max()),min_coverage=min(r['coverage'] for r in result))
        details[table]=dict(max_delta_vs_previous_experiment=previous_delta,sign_unstable_across_scenarios=sum(e['sign_unstable'] for e in envelope),hydro_driver={key:sum(r['hydro_driver']==key for r in result) for key in ('water','wetlands','reeds','lines')},hydro_saturated=sum(r['hydro_saturated'] for r in result),contribution_mean={key:float(np.mean([r['contribution_'+key] for r in result])) for key in ('land','hydro','roads','buildings')},groups={group:dict(count=len(v),minimum=min((r['iop'] for r in v),default=None),maximum=max((r['iop'] for r in v),default=None)) for group,v in [('coverage_below_10',[r for r in result if r['low_coverage']]),('coverage_at_least_10',[r for r in result if not r['low_coverage']])]})
        for mode in ('reference','contrast'):draw_map(rows,result,resolution,mode,out/f'preview_r{resolution}_{mode}.png',[],config['low_coverage'])
        if resolution==7:
            context=[]
            for table_name,color in [('ot_skdr_l','#303030'),('ot_swrs_l','#1467b1')]:
                for line in psql(f"BEGIN READ ONLY; SELECT ST_AsGeoJSON(ST_Simplify(geom,10)) FROM bdot.{table_name} WHERE NOT ST_IsEmpty(geom); COMMIT;").splitlines():
                    if line.startswith('{'):context.append((json.loads(line),color,.3))
            draw_map(rows,result,resolution,'contrast',out/'preview_r7_context.png',context,config['low_coverage'])
    # Assert the entire audit has not changed any base table, including scores.
    for table,expected in before.items():
        actual=psql(f"BEGIN READ ONLY; SELECT md5(string_agg(to_jsonb(h)::text, '' ORDER BY h3_id)) FROM grid.{table} h; COMMIT;").splitlines()
        if expected not in actual:raise ValueError('Source changed during audit')
    report=dict(model_version='2-audited',mode='dry-run',created_utc=datetime.now(timezone.utc).isoformat(),source_fingerprints=fingerprints,config=config,tables=summaries,diagnostics=details,source_unchanged=True,scenario_configs=variants)
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    write_csv(out/'sensitivity.csv',comparison)
    fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
    values=[r for r in comparison if r['table']=='h3_r7' and r['scenario']!='audited']
    values.sort(key=lambda r:r['mean_abs_delta'],reverse=True)
    ax.barh([v['scenario'] for v in values],[v['mean_abs_delta'] for v in values],color='#256d85');ax.invert_yaxis();ax.set_xlabel('Średnia bezwzględna zmiana IOP względem wariantu audited');ax.set_title('R7 • analiza wrażliwości • te same dane wejściowe');ax.grid(axis='x',alpha=.2)
    fig.set_size_inches(11,10);fig.savefig(out/'sensitivity_r7.png',dpi=150);plt.close(fig)
    print(json.dumps(summaries,indent=2));print(f'{len(variants)} scenarios; source fingerprints unchanged; reports: {out}')

if __name__=='__main__':main()
