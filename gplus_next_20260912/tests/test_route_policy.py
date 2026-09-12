"""Geometry-only checks; no simulator scenes or private source data."""
import random
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))

import optimized
from route_policy import RouteOrderPolicy, improve_route


class RoutePolicyTests(unittest.TestCase):
    def test_original_exact_solver_preserved_for_small_routes(self):
        rng = random.Random(2026091201)
        for n in range(10):
            points = [(rng.uniform(-50,50), rng.uniform(-50,50)) for _ in range(n)]
            original = optimized.open_route((3.,7.), points)
            self.assertEqual(improve_route((3.,7.), points, original), original)

    def test_fixed_anchor_distance_never_increases_and_visits_once(self):
        rng = random.Random(2026091202)
        saw_strict_improvement = False
        for n in (10, 12, 16, 22):
            for _ in range(5):
                points = [(rng.uniform(-1800,1800),rng.uniform(-1800,1800)) for _ in range(n)]
                start = (rng.uniform(-1800,1800),rng.uniform(-1800,1800))
                original = optimized.open_route(start, points)
                original_snapshot, points_snapshot = list(original), list(points)
                improved = improve_route(start, points, original)
                before = optimized.route_length(start, points, original)
                after = optimized.route_length(start, points, improved)
                self.assertEqual(sorted(improved), list(range(n)))
                self.assertLessEqual(after, before+1e-8)
                self.assertEqual(original, original_snapshot)
                self.assertEqual(points, points_snapshot)
                saw_strict_improvement |= after < before-1e-6
        self.assertTrue(saw_strict_improvement)

    def test_open_route_has_no_return_to_start(self):
        points = [(float(i),0.) for i in range(1,13)]
        original = optimized.open_route((0.,0.), points)
        improved = improve_route((0.,0.), points, original)
        self.assertEqual(improved, list(range(12)))
        self.assertEqual(optimized.route_length((0.,0.), points, improved), 12.)

    def test_duplicate_positions_and_disabled_search(self):
        points = [(0.,0.)]*4+[(1.,0.)]*4+[(2.,0.)]*4
        original = optimized.open_route((0.,0.), points)
        improved = improve_route((0.,0.), points, original)
        self.assertEqual(sorted(improved), list(range(12)))
        self.assertEqual(optimized.route_length((0.,0.),points,improved), 2.)
        self.assertEqual(improve_route((0.,0.),points,original,rounds=0), original)

    def test_no_global_solver_replacement_and_option_validation(self):
        self.assertEqual(optimized.open_route.__module__, 'optimized')
        for invalid in (-1, 21, 1.5, True):
            with self.assertRaises(ValueError):
                RouteOrderPolicy(None, route_rounds=invalid)


if __name__ == '__main__':
    unittest.main()
