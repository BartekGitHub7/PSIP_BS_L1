import copy
import json
from pathlib import Path
import unittest
from iop import calculate, validate_config, PT

C = json.loads(Path(__file__).with_name('iop_config.json').read_text())

def row():
    r = {'h3_id': 'test', 'hex_area': 1000000, 'ot_adja_a_area_m2': 1000000}
    r.update({'ot_' + k + '_a_area_m2': 0 for k in PT})
    r['ot_pttr_a_area_m2'] = 1000000
    for k in ['ot_oimk_a_area_m2','ot_oisz_a_area_m2','ot_skdr_l_length_m','ot_swrs_l_length_m','ot_swrm_l_length_m','ot_swkn_l_length_m','ot_bubd_a_area_m2']:
        r[k] = 0
    return r

class IOPTests(unittest.TestCase):
    def test_formula(self):
        v = calculate(row(), C)
        self.assertAlmostEqual(v['k_roads'], 0.0)
        self.assertAlmostEqual(v['iop'], (1.6*0.6)/4)
    def test_boundary_invariance(self):
        r = row()
        a = calculate(r, C)
        for k in r:
            if k not in ('h3_id','hex_area'):
                r[k] *= .001
        b = calculate(r,C)
        self.assertEqual(a['iop'],b['iop'])
        self.assertTrue(b['low_coverage'])
        self.assertAlmostEqual(b['coverage'], .001)
    def test_invalid_inputs(self):
        for key in ('ot_adja_a_area_m2','hex_area','ot_skdr_l_length_m','ot_pttr_a_area_m2'):
            for value in (None, -1, float('nan'), float('inf')):
                r = row(); r[key] = value
                with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                    calculate(r,C)
        r=row(); r['ot_adja_a_area_m2']=0
        with self.assertRaises(ValueError): calculate(r,C)
        r=row(); del r['ot_pttr_a_area_m2']
        with self.assertRaises(ValueError): calculate(r,C)
    def test_pt_mismatch(self):
        r=row(); r['ot_pttr_a_area_m2']=100
        with self.assertRaises(ValueError): calculate(r,C)
    def test_range_and_saturation(self):
        for pt in PT:
            for roads in (0, 10000, 1e10):
                r=row(); r['ot_pttr_a_area_m2']=0; r['ot_'+pt+'_a_area_m2']=1000000
                r['ot_skdr_l_length_m']=roads
                r['ot_bubd_a_area_m2']=1000000
                v=calculate(r,C)
                for key in ('iop','k_land','k_hydro','k_roads','k_buildings'):
                    self.assertTrue(-1<=v[key]<=1)
    def test_no_duplicate_road_building_water(self):
        r=row(); a=calculate(r,C)
        r.update(ot_skjz_l_length_m=1e10,ot_ptzb_a_area_m2=0)
        self.assertEqual(a,calculate(r,C))
        r['ot_ptwp_a_area_m2']=100000; r['ot_pttr_a_area_m2']=900000
        r['ot_oimk_a_area_m2']=100000
        self.assertEqual(calculate(r,C)['k_hydro'],-.5)
    def test_config(self):
        validate_config(C)
        for key,value in [('weights',[1,1,1,2]),('roads_km_km2',0),('low_coverage',2)]:
            c=copy.deepcopy(C); c[key]=value
            with self.assertRaises(ValueError): validate_config(c)

class AuditRegressionTests(unittest.TestCase):
    def test_new_parameters_rejected(self):
        for key,values in [('ditch_factor',[-1,1.01,float('nan'),float('inf'),True,'0.25']),('roads_mode',['typo','BONUS',None])]:
            for value in values:
                c=copy.deepcopy(C);c[key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError): validate_config(c)
    def test_fraction_thresholds(self):
        for key in ('water_fraction','wetland_fraction','buildings_fraction'):
            c=copy.deepcopy(C);c[key]=1.01
            with self.assertRaises(ValueError):validate_config(c)
    def test_bonus_and_bipolar_have_explicit_neutral_points(self):
        for mode,without,half in [('bonus',0,.5),('bipolar',-1,0)]:
            c=copy.deepcopy(C);c['roads_mode']=mode
            r=row();self.assertEqual(calculate(r,c)['k_roads'],without)
            r['ot_skdr_l_length_m']=5000;self.assertEqual(calculate(r,c)['k_roads'],half)
    def test_ditch_effect_monotone_and_bounded(self):
        r=row();r['ot_swrm_l_length_m']=10000
        hydro=[]
        for factor in (0,.25,.5,1):
            c=copy.deepcopy(C);c['ditch_factor']=factor
            hydro.append(calculate(r,c)['k_hydro'])
        self.assertEqual(hydro,[0,-.5,-1,-1])
    def test_hydrology_uses_max_not_sum(self):
        r=row();r.update(ot_pttr_a_area_m2=900000,ot_ptwp_a_area_m2=100000,ot_oimk_a_area_m2=100000,ot_oisz_a_area_m2=100000,ot_swrs_l_length_m=2500)
        self.assertEqual(calculate(r,C)['k_hydro'],-.5)
    def test_contributions_reconstruct_score(self):
        r=row();r.update(ot_skdr_l_length_m=3500,ot_bubd_a_area_m2=10000,ot_swrs_l_length_m=1000)
        score=calculate(r,C)
        self.assertAlmostEqual(score['iop'],sum(score['contribution_'+k] for k in ('land','hydro','roads','buildings')))
    def test_building_and_water_are_neutral_in_land(self):
        for pt in ('ptwp','ptzb','ptkm','ptpl'):
            r=row();r['ot_pttr_a_area_m2']=0;r['ot_'+pt+'_a_area_m2']=1000000
            self.assertEqual(calculate(r,C)['k_land'],0)
    def test_low_coverage_threshold_and_missing_id(self):
        r=row();r['hex_area']=10000000
        self.assertFalse(calculate(r,C)['low_coverage'])
        r['hex_area']=10000001;self.assertTrue(calculate(r,C)['low_coverage'])
        r['hex_area']=100000001;self.assertTrue(calculate(r,C)['very_low_coverage'])
        for value in (None,''):
            r['h3_id']=value
            with self.assertRaises(ValueError):calculate(r,C)
    def test_increasing_obstacles_never_improves_score(self):
        for key in ('ot_bubd_a_area_m2','ot_swrs_l_length_m','ot_oimk_a_area_m2','ot_oisz_a_area_m2'):
            scores=[]
            for v in (0,100,10000,1000000):
                r=row();r[key]=v;scores.append(calculate(r,C)['iop'])
            self.assertEqual(scores,sorted(scores,reverse=True))

class DryRunSafetyTests(unittest.TestCase):
    def test_default_path_only_reads_database(self):
        import tempfile
        from unittest.mock import patch
        import iop
        r=row();r.update(srid=2180,przejezdnosc=None)
        columns=['h3_id','geom','przejezdnosc']+['ot_field_'+str(i) for i in range(68)]
        queries=[]
        def database(query):
            queries.append(query)
            if 'md5(' in query:return 'source-fingerprint'
            if 'information_schema' in query:return json.dumps(columns)
            return json.dumps(r)
        with tempfile.TemporaryDirectory() as temp,patch('sys.argv',['iop.py','--dry-run','--output',temp]),patch.object(iop.subprocess,'check_output',return_value='env-test'),patch.object(iop,'psql',side_effect=database),patch('builtins.print'):
            iop.main()
            report=json.loads((Path(temp)/'report.json').read_text())
            self.assertEqual(report['mode'],'dry-run')
            self.assertEqual(sum(t['count'] for t in report['tables'].values()),3)
        for query in queries:
            self.assertNotRegex(query.upper(),r'\b(UPDATE|INSERT|DELETE|ALTER|CREATE|DROP|TRUNCATE)\b')

if __name__=='__main__': unittest.main()
