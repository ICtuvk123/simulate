import math,random,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from negative_cells import *
from geometry import outer_disk,clip_bearing,contains


class NegativeCellsTests(unittest.TestCase):
    def test_no_guaranteed_negative_keeps_omni(self):
        c=[(0,0),(10,0),(10,10),(0,10)]
        self.assertIsNone(reject_cell(c,[(0,100)],[(1500,1500)]))

    def test_joint_negative_contraction_has_independent_witness(self):
        poly=clip_bearing(outer_disk(),(0,0),0)
        positives=[((0.,0.),0.)];negatives=[(700.,60.),(830.,-40.)]
        result=contract(poly,positives,negatives)
        self.assertIsNotNone(result)
        self.assertLess(max(p[0] for p in result['polygon']),1100)
        self.assertTrue(contains(result['polygon'],(300,0)))
        self.assertTrue(verify_contraction(result['witness'],result['polygon'],positives,negatives))
        self.assertFalse(verify_contraction(result['witness'],result['polygon'],positives,negatives[:1]))

    def test_positive_radius_affine_bound(self):
        c=[(1450,-10),(1500,-10),(1500,10),(1450,10)]
        w=range_witness(c,(250,20),[(0,0)])
        self.assertEqual(w['kind'],'positive_radius')

    def test_conservative_boundary_headings_and_radius_extremes(self):
        rng=random.Random(719)
        retained=0
        for i in range(180):
            g=(rng.uniform(30,1490),rng.uniform(-.009,.009))
            heading=(math.pi/2 if i%3==0 else 3*math.pi/2 if i%3==1 else rng.uniform(math.pi/2,3*math.pi/2))
            a=(math.cos(heading),math.sin(heading));r=max(1000.,math.dist(g,(0,0))) if i%2 else 1500.
            emitting=lambda s:sum((s[k]-g[k])*a[k] for k in (0,1))>=-1e-10
            # Only use true positive premises, including exact angular bounds.
            if not emitting((0,0)):continue
            positives=[((0.,0.),math.degrees(math.atan2(g[1],g[0])))]
            negatives=[]
            for _ in range(12):
                s=(rng.uniform(-300,1900),rng.uniform(-500,500))
                if math.dist(s,g)>r or not emitting(s):negatives.append(s)
            poly=clip_bearing(outer_disk(),*positives[0]);result=contract(poly,positives,negatives,24)
            if result:
                retained+=1
                self.assertTrue(contains(result['polygon'],g,tolerance=1e-3),(i,g))
                self.assertTrue(verify_contraction(result['witness'],result['polygon'],positives,negatives))
        self.assertGreater(retained,20)

    def test_emission_boundary_is_not_strictly_removed(self):
        cell=[(300,-.01),(300.01,-.01),(300.01,.01),(300,.01)]
        # A north-facing source on y=0 can receive both collinear positive
        # stations and exclude the southern negative. Boundary is legal.
        self.assertIsNone(reject_cell(cell,[(0,0),(600,0)],[(300,-100)]))


if __name__=='__main__':unittest.main()
