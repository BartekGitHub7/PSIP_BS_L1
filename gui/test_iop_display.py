import csv
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from iop_display import passability_color,display_position,legend_value,load_preview,preview_value,NO_DATA_COLOR
from main import paint_tile

class DisplayAuditTests(unittest.TestCase):
    def test_contrast_keeps_zero_and_saturates_fixed_endpoints(self):
        self.assertEqual(passability_color(0,'contrast'),'#ffffff')
        self.assertEqual(passability_color(.5,'contrast'),passability_color(1))
        self.assertEqual(passability_color(-.8,'contrast'),passability_color(-1))
        self.assertNotEqual(passability_color(.1),passability_color(.1,'contrast'))
    def test_inverse_legend_and_monotonicity(self):
        for mode in ('reference','contrast'):
            positions=[]
            for i in range(101):
                p=-1+2*i/100;v=legend_value(p,mode)
                self.assertAlmostEqual(display_position(v,mode),p)
                positions.append(display_position(-1+2*i/100,mode))
            self.assertEqual(positions,sorted(positions))
    def test_contrast_invalid_values_remain_nodata(self):
        for value in (None,float('nan'),float('inf'),1.001,-1.001,'bad'):
            self.assertEqual(passability_color(value,'contrast'),NO_DATA_COLOR)
    def test_preview_never_falls_back_to_database_value(self):
        self.assertEqual(preview_value({'preview':{}},'missing',.9,.2),(None,.2))
        self.assertEqual(preview_value({},'id',.9,.2),(.9,.2))
        self.assertEqual(preview_value({'preview':{'id':dict(iop=.1,coverage=.001)}},'id',.9,.2),(.1,.001))
    def test_hatching_changes_render_without_changing_iop(self):
        feature={'geometry':{'type':'Polygon','coordinates':[[[100,100],[4000,100],[4000,4000],[100,4000],[100,100]]]},'properties':dict(przejezdnosc=.2,coverage=1)}
        a=np.asarray(paint_tile([feature],'white',True,'contrast'))
        feature['properties']['coverage']=.001
        b=np.asarray(paint_tile([feature],'white',True,'contrast'))
        self.assertFalse(np.array_equal(a,b));self.assertEqual(feature['properties']['przejezdnosc'],.2)
    def test_preview_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);report=dict(mode='dry-run',config=dict(low_coverage=.1,weights=[1.6,1.2,.8,.4]),tables={f'h3_r{r}':dict(count=1) for r in (6,7,8)})
            (folder/'report.json').write_text(json.dumps(report))
            def write(value,duplicate=False):
                for r in (6,7,8):
                    with (folder/f'h3_r{r}.csv').open('w',newline='') as f:
                        w=csv.DictWriter(f,fieldnames=['h3_id','iop','coverage','error','k_land','k_hydro','k_roads','k_buildings']);w.writeheader()
                        record=dict(h3_id='id',iop=value,coverage=.01,error='',k_land=.5,k_hydro=0,k_roads=0,k_buildings=0);w.writerow(record)
                        if duplicate:w.writerow(record)
            write(.2);data,low,_=load_preview(folder);self.assertEqual(data['h3_r7']['id']['iop'],.2);self.assertEqual(low,.1)
            for value in ('nan','inf','',1.01,.3):
                write(value)
                with self.assertRaises(ValueError):load_preview(folder)
            write(.2,True)
            with self.assertRaises(ValueError):load_preview(folder)

if __name__=='__main__':unittest.main()
