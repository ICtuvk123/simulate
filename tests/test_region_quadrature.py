import json,math,random,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from region_quadrature import stable_quadrature
from directional_geometry import hull,in_hull


def expanded(poly):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        out.extend([a,a]+[tuple((1-t)*a[k]+t*b[k] for k in (0,1)) for t in (.1,.25,.5,.77)])
    return out


class StableQuadratureTests(unittest.TestCase):
    def assert_points_close(self,a,b,tolerance=1e-9):
        self.assertEqual(len(a),len(b))
        self.assertLessEqual(max((math.dist(p,q) for p,q in zip(a,b)),default=0),tolerance)

    def test_polygon_encoding_invariance(self):
        poly=[(-510.,-12.),(780.,-9.),(632.,25.),(-492.,14.)]
        base=stable_quadrature(poly,17)
        subdivided=expanded(poly)
        for variant in (poly[::-1],poly[2:]+poly[:2],subdivided,subdivided[7:]+subdivided[:7],subdivided[::-1]):
            self.assert_points_close(base,stable_quadrature(variant,17))

    def test_exact_triangle_area_cdf(self):
        count=31;poly=[(0.,0.),(1.,0.),(0.,1.)]
        points=stable_quadrature(poly,count)
        for i,(x,y) in enumerate(points):
            self.assertAlmostEqual(2*x-x*x,(i+.5)/count,places=13)
            self.assertGreaterEqual(y,0);self.assertLessEqual(x+y,1)

    def test_exact_rectangle_area_cdf(self):
        points=stable_quadrature([(-4.,-1.),(4.,-1.),(4.,1.),(-4.,1.)],19)
        for i,p in enumerate(points):self.assertAlmostEqual((p[0]+4)/8,(i+.5)/19,places=14)

    def test_translation(self):
        poly=[(0.,0.),(1200.,0.),(700.,20.),(0.,10.)];shift=(1.e7,-2.e7)
        expected=[tuple(p[k]+shift[k] for k in (0,1)) for p in stable_quadrature(poly,13)]
        translated=[tuple(p[k]+shift[k] for k in (0,1)) for p in poly]
        self.assert_points_close(expected,stable_quadrature(translated,13),1e-7)

    def test_quarter_turns_with_axis_swap(self):
        poly=[(0.,0.),(8.,0.),(6.,1.),(0.,2.)];points=stable_quadrature(poly,13)
        for angle in (math.pi/2,math.pi,3*math.pi/2):
            c,s=math.cos(angle),math.sin(angle)
            rotate=lambda p:(c*p[0]-s*p[1],s*p[0]+c*p[1])
            actual=stable_quadrature([rotate(p) for p in poly],13)
            for q in map(rotate,points):self.assertLess(min(math.dist(q,p) for p in actual),1e-12)

    def test_rotated_representations_stay_identical(self):
        poly=[(-500.,-12.),(800.,-9.),(630.,25.),(-490.,14.)]
        for angle in (0.,.001,.37,1.19,2.72):
            c,s=math.cos(angle),math.sin(angle)
            rotated=[(c*x-s*y,s*x+c*y) for x,y in poly]
            self.assert_points_close(stable_quadrature(rotated,9),stable_quadrature(expanded(rotated)[::-1],9))

    def test_random_convex_containment_and_subdivision(self):
        rng=random.Random(7142)
        for _ in range(100):
            poly=hull([(rng.uniform(-1700,1700),rng.uniform(-30,30)) for _ in range(12)])
            points=stable_quadrature(poly,15)
            self.assertEqual(len(points),15)
            for p in points:self.assertTrue(in_hull(poly,p))
            self.assert_points_close(points,stable_quadrature(expanded(poly),15),1e-8)

    def test_degenerate_and_invalid(self):
        self.assertEqual(stable_quadrature([]),[])
        self.assertEqual(stable_quadrature([(1.,2.)]*4),[(1.,2.)])
        self.assertEqual(stable_quadrature([(math.nan,0.),(1.,1.)]),[])
        poly=[(0.,0.),(1.,0.),(4.,0.),(2.,0.)]
        expected=[((i+.5)*4/9,0.) for i in range(9)]
        self.assert_points_close(stable_quadrature(poly),expected)
        self.assertEqual(stable_quadrature(poly,0),[])

    def test_input_not_modified(self):
        poly=[(0.,0.),(4.,0.),(4.,2.),(0.,2.)];before=list(poly)
        stable_quadrature(poly);self.assertEqual(poly,before)

    def test_actual_1330_equivalent_regions(self):
        data=json.loads((Path(__file__).parent/'fixtures/quadrature_1330_equivalent.json').read_text())
        a,b=data['polygons'].values()
        self.assert_points_close(stable_quadrature(a),stable_quadrature(b),1e-10)


if __name__=='__main__':unittest.main()
