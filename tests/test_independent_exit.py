import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from independent_exit import cell_certificate,boundary,orientation


class IndependentGeometryTests(unittest.TestCase):
    def test_25_sites_continuous_proof(self):
        stations=[(0,0)]+[(r*math.cos(2*math.pi*k/n),r*math.sin(2*math.pi*k/n))
                        for r,n in [(995,8),(1840,16)] for k in range(n)]
        result=cell_certificate(stations)
        self.assertTrue(result['complete']);self.assertGreater(result['accepted_cells'],0)
    def test_global_hull_is_insufficient(self):
        stations=[(0,0)]+[(1800*math.cos(k*math.pi/3),1800*math.sin(k*math.pi/3)) for k in range(6)]
        h=boundary(stations);self.assertTrue(all(orientation(a,b,(0,0))>=0 for a,b in zip(h,h[1:]+h[:1])))
        self.assertFalse(cell_certificate(stations)['complete'])
    def test_budget_exhaustion_never_becomes_proof(self):
        self.assertFalse(cell_certificate([(0,0)],max_cells=0)['complete'])


if __name__=='__main__':unittest.main()
