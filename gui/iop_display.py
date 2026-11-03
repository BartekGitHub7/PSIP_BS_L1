"""Shared, fixed IOP display scales and validated local dry-run data.
Display transforms never change numeric IOP. No per-map min/max fitting.
"""
import csv
import json
import math
from pathlib import Path
from matplotlib.colors import to_hex, to_rgb

NO_DATA_COLOR = '#bdbdbd'
RAMP = ('#d73027', '#ffffff', '#1a9850')
CONTRAST_LIMIT = 0.5
CONTRAST_GAMMA = 0.65

def display_position(value, mode='reference'):
    if mode not in ('reference', 'contrast'):
        raise ValueError('Unknown display scale')
    if mode == 'reference':
        return value
    return math.copysign(min(1.0, abs(value)/CONTRAST_LIMIT)**CONTRAST_GAMMA, value)

def passability_color(value, mode='reference'):
    try:
        value = float(value)
    except (ValueError, TypeError):
        return NO_DATA_COLOR
    if not math.isfinite(value) or not -1 <= value <= 1:
        return NO_DATA_COLOR
    t = display_position(value, mode)
    a,b = (RAMP[0], RAMP[1]) if t <= 0 else (RAMP[1], RAMP[2])
    fraction=t+1 if t <= 0 else t
    return to_hex(tuple(x+(y-x)*fraction for x,y in zip(to_rgb(a),to_rgb(b))))

def legend_value(position, mode):
    """Inverse display transform: numeric labels for evenly spaced bar positions."""
    return position if mode == 'reference' else math.copysign(CONTRAST_LIMIT*abs(position)**(1/CONTRAST_GAMMA), position)

def preview_value(layer, identifier, stored_value, coverage=None):
    data=layer.get('preview')
    if data is None:
        return stored_value, coverage
    record=data.get(str(identifier))
    if record is None:
        return None, coverage  # Never silently mix a dry-run with persisted scores.
    return record['iop'], record['coverage']

def load_preview(folder):
    folder=Path(folder)
    report=json.loads((folder/'report.json').read_text(encoding='utf-8-sig'))
    if report.get('mode') != 'dry-run':
        raise ValueError('Wymagany raport dry-run')
    low=float(report['config']['low_coverage'])
    if not math.isfinite(low) or not 0<low<=1:
        raise ValueError('Niepoprawny prog pokrycia')
    weights=report['config']['weights']
    if len(weights)!=4 or any(not math.isfinite(w) or w<=0 for w in weights) or not math.isclose(sum(weights),4):
        raise ValueError('Niepoprawne wagi raportu')
    datasets={}
    for resolution in (6,7,8):
        table=f'h3_r{resolution}'
        records={}
        with (folder/(table+'.csv')).open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                identifier=row['h3_id']
                if not identifier or identifier in records or row.get('error'):
                    raise ValueError('Brak/duplikat ID lub blad obliczen')
                score=float(row['iop']); coverage=float(row['coverage'])
                if not math.isfinite(score) or not -1<=score<=1 or not math.isfinite(coverage) or not 0<coverage<=1.01:
                    raise ValueError('Wynik lub pokrycie poza zakresem')
                criteria=[float(row[k]) for k in ('k_land','k_hydro','k_roads','k_buildings')]
                if any(not math.isfinite(k) or not -1<=k<=1 for k in criteria):
                    raise ValueError('Kryterium poza zakresem')
                if not math.isclose(score,sum(w*k for w,k in zip(weights,criteria))/4,abs_tol=1e-9):
                    raise ValueError('IOP niezgodny z kryteriami i wagami')
                records[identifier]=dict(row, iop=score, coverage=coverage)
        if len(records)!=report['tables'][table]['count'] or not records:
            raise ValueError('Liczba wierszy niezgodna z raportem')
        datasets[table]=records
    return datasets, low, report
