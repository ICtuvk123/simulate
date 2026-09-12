import math,random,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from candidate_geometry import canonical_candidate_polygon
from directional_geometry import hull,in_hull
from geometry import diameter


def subdivide(poly):
    return [tuple((1-t)*a[k]+t*b[k] for k in (0,1))
            for a,b in zip(poly,poly[1:]+poly[:1]) for t in (0.,.1,.25,.5,.77)]


class CanonicalCandidateGeometryTests(unittest.TestCase):
    def test_tied_rectangle_diameter_is_start_invariant(self):
        p=[(0.,-10.),(1000.,-10.),(1000.,10.),(0.,10.)]
        base=diameter(canonical_candidate_polygon(p))
        for variant in (p[1:]+p[:1],p[::-1],subdivide(p)):
            self.assertEqual(diameter(canonical_candidate_polygon(variant)),base)

    def test_canonical_copy_drops_only_planning_vertices(self):
        p=[(0.,0.),(3.,0.),(3.,2.),(0.,2.)];variant=subdivide(p);before=list(variant)
        result=canonical_candidate_polygon(variant)
        self.assertEqual(result,p);self.assertEqual(variant,before)
        self.assertTrue(set(result)<=set(variant))

    def test_random_convex_subdivision(self):
        rng=random.Random(31751)
        for _ in range(100):
            p=hull([(rng.uniform(-1500,1500),rng.uniform(-20,20)) for _ in range(12)])
            baseline=canonical_candidate_polygon(p)
            self.assertEqual(canonical_candidate_polygon(subdivide(p)[::-1]),baseline)
            self.assertEqual(canonical_candidate_polygon(p[2:]+p[:2]),baseline)

    def test_degenerate_and_invalid(self):
        self.assertEqual(canonical_candidate_polygon([]),[])
        self.assertEqual(canonical_candidate_polygon([(1.,2.)]*3),[(1.,2.)])
        self.assertEqual(canonical_candidate_polygon([(0.,0.),(2.,0.),(1.,0.)]),[(0.,0.),(2.,0.)])
        with self.assertRaises(ValueError):canonical_candidate_polygon([(math.nan,0.)])
        with self.assertRaises(ValueError):canonical_candidate_polygon([(-1e308,0.),(1e308,0.),(0.,1.)])


if __name__=='__main__':unittest.main()
