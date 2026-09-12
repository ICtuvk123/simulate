import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from route_search import oriented_ring_plan,project_segment
from coverage import coverage_partition
from geometry import regular_fallback


class RouteSearchTests(unittest.TestCase):
    def test_rotation_keeps_continuous_cover_and_improves_predicted_route(self):
        sites,_=regular_fallback(1130)
        result,base=oriented_ring_plan((0.,0.),sites[1:],[(550.,220.),(-450.,620.)])
        length,angle,rotated=result
        self.assertLessEqual(length,base+1e-6)
        self.assertTrue(coverage_partition([(0.,0.)]+rotated,12)['complete'])
        self.assertEqual(len(rotated),6)
        self.assertTrue(all(abs(math.hypot(*p)-1130)<1e-6 for p in rotated))

    def test_bending_without_cover_is_rejected_by_certificate(self):
        sites,_=regular_fallback(1130)
        self.assertTrue(coverage_partition(sites,12)['complete'])
        proposal=sites[:];proposal[1]=(0.,0.)
        self.assertFalse(coverage_partition(proposal,12)['complete'])

    def test_projection_handles_endpoint_and_degenerate_segment(self):
        self.assertEqual(project_segment((3.,2.),(0.,0.),(1.,0.)),(1.,0.))
        self.assertEqual(project_segment((3.,2.),(1.,1.),(1.,1.)),(1.,1.))


if __name__=='__main__':
    unittest.main()
