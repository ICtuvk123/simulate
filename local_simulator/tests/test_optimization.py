import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from geometry import regular_fallback, nearest_safe_point, clip_bearing, outer_disk
from coverage import coverage_partition, validate_completion
from local_geometry import nearest_operating_point, time_rollout_station
from reception_geometry import reception_safe
from replanning import polygon_quadrature, area_rollout_station


class OptimizationGeometryTests(unittest.TestCase):
    def test_previous_positive_reception_expands_safe_station_region(self):
        poly=clip_bearing(outer_disk(),(0.,0.),0.)
        q=(300.,300.)
        self.assertGreater(max(math.dist(q,v) for v in poly),1000)
        self.assertTrue(reception_safe(poly,q,[(0.,0.)]))
        self.assertFalse(reception_safe(poly,(-300.,300.),[(0.,0.)]))

    def test_reception_certificate_catches_interior_violation(self):
        # Endpoints can pass max(1000, distance-to-origin) while an interior
        # point fails: vertex-only testing of the variable radius is invalid.
        poly=[(0.,0.),(1500.,0.)]
        q=(350.,930.)
        self.assertTrue(all(math.dist(q,v)<=max(1000,math.hypot(*v)) for v in poly))
        self.assertFalse(reception_safe(poly,q,[(0.,0.)]))

    def test_area_weights_and_safe_expanded_choice(self):
        triangle=[(0.,0.),(6.,0.),(0.,3.)]
        weighted=polygon_quadrature(triangle)
        self.assertAlmostEqual(sum(w for _,w in weighted),1.)
        self.assertAlmostEqual(sum(q[0]*w for q,w in weighted),2.)
        self.assertAlmostEqual(sum(q[1]*w for q,w in weighted),1.)
        poly=clip_bearing(outer_disk(),(0.,0.),0.)
        selected=area_rollout_station(poly,(0.,0.),[(0.,0.)],adaptive_reception=True,use_area=False)
        self.assertTrue(reception_safe(poly,selected['point'],[(0.,0.)]))

    def test_compact_ring_certifies_entire_target(self):
        sites,_ = regular_fallback(1130)
        self.assertTrue(coverage_partition(sites,12)['complete'])
        self.assertFalse(coverage_partition(sites[:-1],9)['complete'])

    def test_operating_intersection_beats_mec_inner_disk(self):
        poly = [(0.,-19.),(0.,19.)]
        actual = nearest_operating_point(poly,(100.,0.))
        conservative = nearest_safe_point(poly,(100.,0.))
        self.assertGreater(actual[0],6.)
        self.assertLess(conservative[0],1.01)
        self.assertLess(max(math.dist(actual,v) for v in poly),20.)
        self.assertIsNone(nearest_operating_point([(0.,-21.),(0.,21.)],(0.,0.)))

    def test_rollout_candidate_is_reception_safe(self):
        poly = clip_bearing(outer_disk(),(0.,0.),0.)
        selected = time_rollout_station(poly,(0.,0.),[(0.,0.)])
        self.assertIsNotNone(selected)
        self.assertLess(max(math.dist(selected['point'],v) for v in poly),1000.)

    def test_future_plan_cannot_certify_actual_completion(self):
        certificate = dict(kind='adaptive_quadtree_square_containment',
                           cleared_channels=list(range(1,11)),empty_channels=list(range(11,21)))
        events = [dict(path='/clear',channel=ch,result='success') for ch in range(1,11)]
        events.append(dict(path='/exit',channel=None,result=None))
        self.assertFalse(validate_completion(events,certificate)[0])
