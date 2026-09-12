import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from geometry import contains,clip_bearing,outer_disk
from reception_geometry import reception_safe
from structural_geometry import (positive_negative_clip,joint_reception_safe,
    exclude_inner_disk,bearing_strip_grid,convex_hull,through_operating_point)
from coverage import validate_completion


class StructuralGeometryTests(unittest.TestCase):
    def test_positive_negative_orientation(self):
        poly=[(-200.,-200.),(1500.,-200.),(1500.,200.),(-200.,200.)]
        clipped=positive_negative_clip(poly,[(0.,0.)],[(2000.,0.)])
        self.assertTrue(contains(clipped,(500.,0.)))
        self.assertFalse(contains(clipped,(1200.,0.)))
        self.assertLess(max(v[0] for v in clipped),1000.0001)

    def test_positive_negative_preserves_actual_feasible_sources(self):
        rng=random.Random(82)
        for _ in range(100):
            g=(rng.uniform(-1000,1000),rng.uniform(-1000,1000));r=rng.uniform(1000,1500)
            angles=[rng.uniform(-math.pi,math.pi) for _ in range(2)]
            s=(g[0]+.8*r*math.cos(angles[0]),g[1]+.8*r*math.sin(angles[0]))
            n=(g[0]+1.1*r*math.cos(angles[1]),g[1]+1.1*r*math.sin(angles[1]))
            poly=positive_negative_clip(outer_disk(),[s],[n])
            self.assertTrue(contains(poly,g))

    def test_multiple_stations_can_jointly_certify(self):
        poly=[(-50.,-1200.),(50.,-1200.),(50.,1200.),(-50.,1200.)]
        old=[(0.,-300.),(0.,300.)];q=(0.,0.)
        self.assertFalse(reception_safe(poly,q,old))
        self.assertTrue(joint_reception_safe(poly,q,old))
        self.assertFalse(joint_reception_safe(poly,(1600.,0.),old))

    def test_joint_certificate_never_passes_sampled_violations(self):
        rng=random.Random(120)
        poly=[(-300.,-1000.),(300.,-1000.),(300.,1000.),(-300.,1000.)]
        old=[(-500.,0.),(500.,0.)]
        for _ in range(40):
            q=(rng.uniform(-1600,1600),rng.uniform(-1600,1600))
            if joint_reception_safe(poly,q,old):
                for _ in range(30):
                    g=(rng.uniform(-300,300),rng.uniform(-1000,1000))
                    self.assertLessEqual(math.dist(q,g),max(1000,*[math.dist(s,g) for s in old])+1e-6)

    def test_optical_hole_retained_and_exterior_preserved(self):
        square=[(-40.,-40.),(40.,-40.),(40.,40.),(-40.,40.)]
        pieces=exclude_inner_disk([square],(0.,0.))
        self.assertFalse(any(contains(p,(0.,0.)) for p in pieces))
        for i in range(72):
            a=i*math.pi/36;q=(20.00001*math.cos(a),20.00001*math.sin(a))
            self.assertTrue(any(contains(p,q) for p in pieces))
        self.assertTrue(contains(convex_hull([v for p in pieces for v in p]),(0.,0.)))

    def test_rf_exclusion_retains_minimum_radius_boundary(self):
        poly=[(-1200.,-40.),(1200.,-40.),(1200.,40.),(-1200.,40.)]
        pieces=exclude_inner_disk([poly],(0.,0.),1000.)
        self.assertFalse(any(contains(p,(500.,0.)) for p in pieces))
        for q in ((1000.0001,0.),(-1000.0001,0.),(1001.,35.)):
            self.assertTrue(any(contains(p,q) for p in pieces))

    def test_bearing_strip_fallback_has_strict_optical_margin(self):
        for bearing in (0,90,359.99,-180):
            s=(1800.,-1200.);points=bearing_strip_grid(s,bearing)
            self.assertEqual(len(points),183)
            for distance in (0,12.5,537.5,1499,1500):
                for error in (-1.01,0,1.01):
                    a=math.radians(bearing+error)
                    g=(s[0]+distance*math.cos(a),s[1]+distance*math.sin(a))
                    self.assertLess(min(math.dist(g,q) for q in points),20)

    def test_through_clear_point_keeps_feasibility_and_shortens_known_trip(self):
        from local_geometry import nearest_operating_point
        poly=[(-5.,-5.),(5.,-5.),(5.,5.),(-5.,5.)]
        p=(-100.,0.);b=(0.,100.)
        old=nearest_operating_point(poly,p);new=through_operating_point(poly,p,b)
        self.assertLess(max(math.dist(new,v) for v in poly),20.)
        self.assertLess(math.dist(p,new)+math.dist(new,b),math.dist(p,old)+math.dist(old,b)-1.)
        q=through_operating_point(poly,(-100.,0.),(100.,0.))
        self.assertAlmostEqual(math.dist((-100.,0.),q)+math.dist(q,(100.,0.)),200.)

    def test_channel_specific_missing_feedback_cannot_be_certified(self):
        from geometry import regular_fallback
        sites,_=regular_fallback(1130)
        events=[dict(path='/clear',channel=ch,result='success') for ch in range(1,11)]
        for ch in range(11,21):
            for q in sites[:(-1 if ch==20 else None)]:
                events.append(dict(path='/measure',channel=ch,result='no_signal',position=q))
        cert=dict(kind='adaptive_quadtree_square_containment',cleared_channels=list(range(1,11)),
                  empty_channels=list(range(11,21)))
        events.append(dict(path='/exit',channel=None,result=None))
        self.assertFalse(validate_completion(events,cert)[0])


if __name__=='__main__':
    unittest.main()
