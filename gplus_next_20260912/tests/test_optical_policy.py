import math
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'code'))

from geometry import contains
from optical_geometry import (certified_second_point, disk_coverage_fraction,
                              disk_intersection_area, sequential_optical_plan)
from optical_policy import OpticalPolicy
from time_policy import TimePolicy


def rectangle(length=60., width=4., angle=0., offset=(0., 0.)):
    c, s = math.cos(angle), math.sin(angle)
    return [(offset[0]+c*x-s*y, offset[1]+s*x+c*y)
            for x, y in ((-length/2, -width/2), (length/2, -width/2),
                         (length/2, width/2), (-length/2, width/2))]


class OpticalGeometryTests(unittest.TestCase):
    def test_analytic_disk_polygon_areas(self):
        square = rectangle(60, 60)
        self.assertAlmostEqual(disk_intersection_area(square, (0., 0.)), 400*math.pi, places=8)
        half = [(-30., -30.), (0., -30.), (0., 30.), (-30., 30.)]
        self.assertAlmostEqual(disk_intersection_area(half, (0., 0.)), 200*math.pi, places=8)
        small = rectangle(4., 6.)
        self.assertAlmostEqual(disk_intersection_area(small, (0., 0.)), 24., places=8)
        self.assertAlmostEqual(disk_intersection_area(small, (100., 0.)), 0., places=8)
        shifted = rectangle(4., 6., offset=(1600., -1300.))
        self.assertAlmostEqual(disk_coverage_fraction([shifted], (1600., -1300.)), 1.)

    def test_residual_contains_entire_failed_branch_grid(self):
        poly = rectangle()
        first = (-20., 0.)
        plan = certified_second_point([poly], first)
        self.assertIsNotNone(plan)
        for ix in range(241):
            for iy in range(17):
                point = (-30+ix/4, -2+iy/4)
                if math.dist(first, point) > 20+1e-7:
                    self.assertTrue(any(contains(part, point) for part in plan['residual']))
                    self.assertLess(math.dist(plan['second'], point), 20)
        self.assertLessEqual(max(math.dist(v, plan['second'])
                                 for part in plan['residual'] for v in part), 20-1e-6)

    def test_vertex_only_union_cannot_fake_interior_certificate(self):
        poly = rectangle(70., 30.)
        first, second = (-35., 0.), (35., 0.)
        self.assertTrue(all(min(math.dist(v, first), math.dist(v, second)) < 20 for v in poly))
        self.assertGreater(min(math.dist((0., 0.), first), math.dist((0., 0.), second)), 20)
        # Covering the four original vertices is insufficient for disk UNION.
        self.assertIsNone(certified_second_point([poly], first))

    def test_long_thin_regions_have_certified_sequential_plans(self):
        rng = random.Random(912)
        for length in (45., 60., 75.):
            for width in (1., 8.):
                angle = rng.uniform(-math.pi, math.pi)
                offset = (rng.uniform(-1000, 1000), rng.uniform(-1000, 1000))
                poly = rectangle(length, width, angle, offset)
                current = (offset[0]-100*math.cos(angle), offset[1]-100*math.sin(angle))
                plan = sequential_optical_plan([poly], current)
                self.assertIsNotNone(plan)
                self.assertLessEqual(plan['second_max_distance'], 20-1e-6)
                for _ in range(120):
                    x, y = rng.uniform(-length/2, length/2), rng.uniform(-width/2, width/2)
                    point = (offset[0]+math.cos(angle)*x-math.sin(angle)*y,
                             offset[1]+math.sin(angle)*x+math.cos(angle)*y)
                    self.assertLessEqual(min(math.dist(point, plan['first']),
                                             math.dist(point, plan['second'])), 20)
                    if math.dist(point, plan['first']) > 20:
                        self.assertTrue(any(contains(part, point) for part in plan['residual']))

    def test_region_too_large_retains_baseline(self):
        self.assertIsNone(sequential_optical_plan([rectangle(100., 100.)], (-120., 0.)))


class FakeClearClient:
    """Independent deterministic optical response fixture; policy sees responses only."""
    def __init__(self, target):
        self._target = target
        self.ledger = SimpleNamespace(position=(-100., 0.), channel=9,
                                      cleared=set(), virtual_time=0.)
        self.journal = []
        self.calls = []

    def action(self, path, position=None, channel=None):
        assert path == '/clear'
        point = tuple(position)
        successful = math.dist(point, self._target) <= 20
        self.ledger.virtual_time += math.dist(self.ledger.position, point)/5+3+2*successful
        self.ledger.position = point
        if successful:
            self.ledger.cleared.add(channel)
        self.calls.append((path, point, channel, successful))
        return dict(accepted=True, clear_result='success' if successful else 'no_target_in_range')


class OpticalPolicyTests(unittest.TestCase):
    def make_policy(self, target):
        client = FakeClearClient(target)
        policy = OpticalPolicy(client, optical_force=True)
        poly = rectangle()
        policy.polygons[1] = poly
        policy.pieces[1] = [poly]
        policy.bearings[1] = [((-100., 0.), 0.)]
        return client, policy

    def test_actual_failure_installs_outer_residual_then_clears(self):
        client, policy = self.make_policy((29., 0.))
        with patch.object(policy, '_baseline_terminal_cost', return_value=100.):
            policy.refine_and_clear(1)
        self.assertEqual(len(client.calls), 2)
        self.assertFalse(client.calls[0][3])
        self.assertTrue(client.calls[1][3])
        self.assertIn(1, client.ledger.cleared)
        self.assertEqual(client.ledger.channel, 9, '/clear must not switch RF channel')
        self.assertTrue(any(contains(part, (29., 0.)) for part in policy.pieces[1]))
        self.assertTrue(any(row.get('reason') == 'O_two_optical_second_certificate'
                            for row in client.journal))

    def test_first_success_never_installs_unobserved_exclusion(self):
        client, policy = self.make_policy((-29., 0.))
        with patch.object(policy, '_baseline_terminal_cost', return_value=100.):
            policy.refine_and_clear(1)
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(client.calls[0][3])
        self.assertEqual(policy.pieces[1], [rectangle()])
        self.assertFalse(any(row.get('reason') == 'O_optical_negative_region'
                             for row in client.journal))

    def test_disabled_mode_uses_cooperative_baseline_fallback(self):
        client, policy = self.make_policy((29., 0.))
        policy.sequential_optical = False
        with patch.object(TimePolicy, 'refine_and_clear', return_value='baseline') as baseline:
            self.assertEqual(policy.refine_and_clear(1), 'baseline')
            baseline.assert_called_once_with(1)
        self.assertFalse(client.calls)


if __name__ == '__main__':
    unittest.main()
