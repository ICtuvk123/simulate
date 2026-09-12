"""Optional certified sequential optical terminal policy, preserving G+ fallback."""
import math

from geometry import minimum_circle
from local_geometry import nearest_operating_point
from optical_geometry import disk_coverage_fraction, sequential_optical_plan
from q3client import ProtocolError
from time_policy import TimePolicy


class OpticalPolicy(TimePolicy):
    def __init__(self, client, sequential_optical=True, optical_min_gain=.5,
                 optical_sequence_risk=.15, optical_sequence_radius=40.,
                 optical_tail_weight=0., optical_force=False, **options):
        super().__init__(client, **options)
        self.sequential_optical = bool(sequential_optical)
        self.optical_min_gain = float(optical_min_gain)
        self.optical_sequence_risk = float(optical_sequence_risk)
        self.optical_sequence_radius = float(optical_sequence_radius)
        self.optical_tail_weight = float(optical_tail_weight)
        self.optical_force = bool(optical_force)
        if not 0 <= self.optical_sequence_risk <= 1:
            raise ValueError('optical_sequence_risk must be in [0,1]')
        if not 0 <= self.optical_tail_weight <= 1:
            raise ValueError('optical_tail_weight must be in [0,1]')
        if self.optical_min_gain < 0 or self.optical_sequence_radius < 20:
            raise ValueError('optical_min_gain >= 0 and optical_sequence_radius >= 20 required')

    def _baseline_terminal_cost(self, ch, poly, pieces, current, tail):
        """Rank against the existing center trial + RF continuation heuristic."""
        center, radius = minimum_circle(poly)
        old = self.optical_attempts.get(ch)
        try_center = (20 < radius <= self.optical_trial
                      and (old is None or math.dist(center, old) > 10))
        rf_start = center if try_center else current
        previous = [q for q, _ in self.bearings[ch]]
        # Cooperative call allows CombinedPolicy to use FuturePolicy's station
        # ranking while keeping all of its reception and bearing checks intact.
        station = self.choose_station(ch, poly, rf_start, previous)
        if station is None:
            return None
        remaining = station['estimated_remaining_s']
        if tail is not None and self.optical_tail_weight:
            remaining += self.optical_tail_weight*math.dist(center, tail)/5
        if not try_center:
            return remaining
        fraction = disk_coverage_fraction(pieces, center)
        movement = math.dist(current, center)/5
        success = movement+5
        if tail is not None and self.optical_tail_weight:
            success += self.optical_tail_weight*math.dist(center, tail)/5
        failure = movement+3+remaining
        expected = fraction*success+(1-fraction)*failure
        return ((1-self.optical_sequence_risk)*expected
                + self.optical_sequence_risk*max(success, failure))

    def refine_and_clear(self, ch):
        if (not self.sequential_optical or ch in self.cleared
                or ch not in self.polygons):
            return super().refine_and_clear(ch)
        poly = self.polygons[ch]
        current = self.client.ledger.position
        _, radius = minimum_circle(poly)
        # The original one-stop operating-region and through-point decisions
        # remain in force wherever they already give a guaranteed clearance.
        if (radius > self.optical_sequence_radius
                or nearest_operating_point(poly, current) is not None):
            return super().refine_and_clear(ch)
        pieces = self.pieces.get(ch, [poly])
        tail = None
        if self.optical_tail_weight:
            tail_points = self.tail_points(ch)
            if tail_points:
                tail = min(tail_points, key=lambda point: math.dist(current, point))
        plan = sequential_optical_plan(pieces, current, risk=self.optical_sequence_risk,
                                      tail=tail, tail_weight=self.optical_tail_weight)
        if plan is None:
            return super().refine_and_clear(ch)
        baseline_cost = self._baseline_terminal_cost(ch, poly, pieces, current, tail)
        accepted = (self.optical_force or (baseline_cost is not None
                    and baseline_cost-plan['estimated_remaining_s'] >= self.optical_min_gain))
        self.record(reason='O_two_optical_comparison', channel=ch,
                    accepted_plan=accepted, baseline_estimated_remaining_s=baseline_cost,
                    optical_min_gain=self.optical_min_gain, optical_force=self.optical_force,
                    tail_point=tail, optical_tail_weight=self.optical_tail_weight,
                    **{key: value for key, value in plan.items() if key != 'residual'})
        if not accepted:
            return super().refine_and_clear(ch)
        first = plan['first']
        self.optical_attempts[ch] = first
        result = self.client.action('/clear', first, ch)
        if result['clear_result'] == 'success':
            self.record(reason='O_two_optical_first_success', channel=ch, point=first)
            return
        if result.get('accepted') is not True or result['clear_result'] != 'no_target_in_range':
            raise ProtocolError('Unexpected sequential optical feedback')
        # Install only after a real, accepted failure; prior plans are not facts.
        # The stored residual is an outer approximation of P \\ B(first,20).
        self.install_region(ch, plan['residual'], 'O_optical_negative_region')
        second = plan['second']
        maximum = max(math.dist(second, vertex)
                      for piece in self.pieces[ch] for vertex in piece)
        if maximum > 20-1e-6:
            raise ProtocolError('Sequential optical residual certificate failed')
        self.record(reason='O_two_optical_second_certificate', channel=ch, point=second,
                    second_max_distance=maximum, certificate=plan['certificate'],
                    exclusion_sides=plan['exclusion_sides'])
        if self.client.action('/clear', second, ch)['clear_result'] != 'success':
            raise ProtocolError('Certified second optical clearance failed')
