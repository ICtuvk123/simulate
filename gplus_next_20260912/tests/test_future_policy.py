import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))

from future_policy import FuturePolicy, remaining_route_plans, remaining_route_cost
from g_policy_presets import FROZEN_G_OPTIONS
from geometry import minimum_circle
from q3client import Ledger
from time_policy import TimePolicy


def make_policy(cls=FuturePolicy, **extras):
    options = dict(FROZEN_G_OPTIONS)
    options.update(commit_radius=0, near_prediction=10, bearing_factor=.15,
                   error_risk=.5)
    options.update(extras)
    client = SimpleNamespace(ledger=Ledger(), deadline=None)
    return cls(client, **options)


CASES = [
    ([(250., -5.), (900., -12.), (900., 12.), (250., 5.)],
     (0., 0.), [(0., 0.)]),
    ([(300., 100.), (700., 90.), (700., 110.), (300., 108.)],
     (80., -50.), [(80., -50.), (0., 20.)]),
    ([(-35., -1.), (35., -1.), (35., 1.), (-35., 1.)],
     (-90., -90.), [(-90., -90.)]),
]


class FuturePolicyTests(unittest.TestCase):
    def test_zero_weight_is_exact_frozen_policy_ablation(self):
        baseline = make_policy(TimePolicy)
        candidate = make_policy(future_weight=0)
        for poly, current, previous in CASES:
            self.assertEqual(candidate.choose_station(1, poly, current, previous),
                             baseline.choose_station(1, poly, current, previous))

    def test_shortlist_reproduces_original_optimum_and_score(self):
        for source_quadrature in (False, True):
            baseline = make_policy(TimePolicy, source_quadrature=source_quadrature)
            candidate = make_policy(source_quadrature=source_quadrature)
            for poly, current, previous in CASES:
                original = baseline.choose_station(1, poly, current, previous)
                _, shortlist = candidate._base_candidates(1, poly, current, previous)
                best = shortlist[0][0]
                self.assertEqual(best[3], original['point'])
                self.assertEqual(best[0], original['estimated_remaining_s'])
                self.assertEqual(-best[1], original['geometric_success_fraction'])
                self.assertEqual(best[2], original['sampled_worst_radius'])
                self.assertLessEqual(len(shortlist), candidate.future_shortlist)

    def test_open_routes_do_not_charge_a_return_leg(self):
        tasks = [(10., 0.), (20., 0.), (30., 0.)]
        plans = remaining_route_plans((0., 0.), tasks, 'route')
        self.assertEqual(len(plans), 3)
        self.assertAlmostEqual(remaining_route_cost((0., 0.), plans), 6.)
        self.assertAlmostEqual(remaining_route_cost((30., 0.), plans), 4.)
        self.assertEqual(remaining_route_cost((0., 0.), []), 0.)

    def test_forecast_changes_no_observation_state_and_keeps_reception(self):
        policy = make_policy(future_mode='route', future_budget_s=5.)
        poly, current, previous = CASES[0]
        policy.polygons[1] = poly
        policy.polygons[2] = [(950., 500.), (960., 500.), (960., 510.), (950., 510.)]
        policy.remaining_sites = [(0., 1130.), (-1130., 0.)]
        ledger_before = vars(policy.client.ledger).copy()
        polygons_before = {ch: list(region) for ch, region in policy.polygons.items()}
        negatives_before = {ch: list(points) for ch, points in policy.negatives.items()}
        choice = policy.choose_station(1, poly, current, previous)
        self.assertEqual(policy.client.ledger.__dict__, ledger_before)
        self.assertEqual(policy.polygons, polygons_before)
        self.assertEqual(policy.negatives, negatives_before)
        self.assertTrue(policy.reception_ok(poly, choice['point'], previous))
        self.assertFalse(any(math.dist(choice['point'], p) < .05 for p in previous))
        self.assertIn('future_reference_s', choice)
        self.assertEqual(policy.error_risk, .5)

    def test_budget_exhaustion_returns_original_candidate(self):
        candidate = make_policy(future_budget_s=1e-15)
        baseline = make_policy(TimePolicy)
        candidate.remaining_sites = [(1000., 0.)]
        poly, current, previous = CASES[0]
        expected = baseline.choose_station(1, poly, current, previous)
        actual = candidate.choose_station(1, poly, current, previous)
        self.assertEqual(actual['point'], expected['point'])
        self.assertEqual(actual['estimated_remaining_s'], expected['estimated_remaining_s'])
        self.assertEqual(actual['future_fallback'], 'time_budget')

    def test_tight_official_deadline_skips_extra_planning(self):
        candidate = make_policy()
        baseline = make_policy(TimePolicy)
        candidate.client.raw.deadline = time.monotonic() + 1.
        candidate.remaining_sites = [(1000., 0.)]
        poly, current, previous = CASES[0]
        self.assertEqual(candidate.choose_station(1, poly, current, previous),
                         baseline.choose_station(1, poly, current, previous))

    def test_terminal_scoring_counts_entry_and_exit_once(self):
        policy = make_policy()
        poly = [(-5., -5.), (5., -5.), (5., 5.), (-5., 5.)]
        center, radius = minimum_circle(poly)
        current = (-100., 0.)
        plans = [((100., 0.), 0.)]
        reference = remaining_route_cost(center, plans)
        original = max(0., math.dist(current, center) - (20 - radius)) / 5 + 5
        value = policy._branch_cost(current, (original, center, radius, poly), plans, reference)
        # Entry + exit follows the straight 200 m segment; subtract the common
        # 100 m tail reference used only to keep reported scores comparable.
        self.assertAlmostEqual(value, 200 / 5 + 5 - 100 / 5)

    def test_invalid_new_options_are_rejected(self):
        for option in ({'future_weight': float('nan')}, {'future_mode': 'hidden'},
                       {'future_shortlist': 0}, {'future_budget_s': -1}):
            with self.assertRaises(ValueError):
                make_policy(**option)


if __name__ == '__main__':
    unittest.main()
