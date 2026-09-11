import itertools
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from geometry import (_circle, clip_bearing, contains, minimum_circle, nearest_safe_point,
                      open_held_karp, outer_disk, regular_fallback)


class GeometryTests(unittest.TestCase):
    def test_outer_target_polygon_contains_boundary(self):
        poly = outer_disk()
        for k in range(720):
            angle = k * math.pi / 360
            self.assertTrue(contains(poly, (1800 * math.cos(angle), 1800 * math.sin(angle))))

    def test_bearing_error_and_zero_wrap_are_conservative(self):
        source = (1000.0, -0.1)
        poly = outer_disk()
        for station, delta in [((0, 0), 1.005), ((800, 100), -1.005), ((600, -300), 0.8)]:
            bearing = (math.degrees(math.atan2(source[1] - station[1],
                                              source[0] - station[0])) + delta) % 360
            poly = clip_bearing(poly, station, bearing)
            self.assertTrue(contains(poly, source))

    def test_mec_matches_exhaustive_small_supports(self):
        rng = random.Random(1942)
        for _ in range(25):
            points = [(rng.uniform(-50, 50), rng.uniform(-50, 50)) for _ in range(7)]
            best = math.inf
            for count in (1, 2, 3):
                for support in itertools.combinations(points, count):
                    center, radius = _circle(support)
                    if all(math.dist(center, p) <= radius + 1e-7 for p in points):
                        best = min(best, radius)
            center, radius = minimum_circle(points)
            self.assertAlmostEqual(radius, best, places=5)
            self.assertTrue(all(math.dist(center, p) <= radius for p in points))

    def test_mec_collinear_duplicate_and_acute_cases(self):
        for points, radius in [([(0, 0), (0, 0)], 0), ([(-3, 0), (0, 0), (3, 0)], 3),
                               ([(0, 0), (2, 0), (1, math.sqrt(3))], 2 / math.sqrt(3))]:
            self.assertAlmostEqual(minimum_circle(points)[1], radius, places=6)

    def test_safe_clear_point_covers_every_vertex(self):
        points = [(0, 0), (10, 0), (10, 10), (0, 10)]
        safe = nearest_safe_point(points, (100, 100))
        self.assertIsNotNone(safe)
        self.assertTrue(all(math.dist(safe, p) < 20 for p in points))
        self.assertIsNone(nearest_safe_point([(0, 0), (100, 0)], (0, 0)))

    def test_ring_certificate_rejects_uncovered_boundary(self):
        sites, certificate = regular_fallback()
        self.assertEqual(len(sites), 7)
        self.assertLess(certificate["max_annulus_distance"], 1000)
        with self.assertRaises(ValueError):
            regular_fallback(radius=1000)
        with self.assertRaises(ValueError):
            regular_fallback(radius=1450, count=5)

    def test_held_karp_matches_exhaustive_open_paths(self):
        points = [(100, 400), (500, -300), (-600, 50), (5, 5), (100, -700)]
        start = (0, 0)
        order, length = open_held_karp(start, points)
        brute = min(sum(math.dist(a, b) for a, b in
                        zip([start] + [points[i] for i in p], [points[i] for i in p]))
                    for p in itertools.permutations(range(len(points))))
        self.assertEqual(sorted(order), list(range(len(points))))
        self.assertAlmostEqual(length, brute)


if __name__ == "__main__":
    unittest.main()
