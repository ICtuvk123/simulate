"""Bounded remaining-route scoring on top of the frozen G+ station policy.

Only accepted controller regions and planned search stops are read.  Sampled
observations rank actions; all reception, region updates, clearing and exit
certificates remain those of TimePolicy.  The zero-weight ablation calls the
unchanged parent implementation directly.
"""
import math
import time

from geometry import minimum_circle, diameter, clip_bearing
from optimized import open_route, route_length
from replanning import area_center, polygon_quadrature
from structural_geometry import through_operating_point
from time_policy import TimePolicy


def remaining_route_plans(center, points, mode):
    """At most three fixed open routes, represented by first point + suffix.

    Planning is done once per decision, never for every quadrature branch.  A
    suffix contains every other currently forecast task exactly once and does
    not add a return-to-origin leg.  The route is a cost estimate, not proof
    that any future search station has actually been visited.
    """
    points = list(dict.fromkeys(tuple(p) for p in points))
    if not points:
        return []
    order = open_route(center, points)
    firsts = [order[0]]
    if mode == 'route':
        for i in sorted(range(len(points)), key=lambda j: (math.dist(center, points[j]), j)):
            if i not in firsts:
                firsts.append(i)
            if len(firsts) == 3:
                break
    plans = []
    for first in firsts:
        start = points[first]
        if first == order[0]:
            suffix = route_length(start, points, order[1:]) / 5
        else:
            rest = points[:first] + points[first + 1:]
            suffix = route_length(start, rest, open_route(start, rest)) / 5
        plans.append((start, suffix))
    return plans


def remaining_route_cost(point, plans):
    return min((math.dist(point, start) / 5 + suffix for start, suffix in plans), default=0.)


class FuturePolicy(TimePolicy):
    def __init__(self, client, future_weight=1., future_mode='anchor',
                 future_shortlist=6, future_budget_s=.30,
                 future_min_gain_s=.05, **options):
        super().__init__(client, **options)
        self.future_weight = float(future_weight)
        self.future_mode = future_mode
        self.future_shortlist = int(future_shortlist)
        self.future_budget_s = float(future_budget_s)
        self.future_min_gain_s = float(future_min_gain_s)
        if not math.isfinite(self.future_weight) or not 0 <= self.future_weight <= 2:
            raise ValueError('future_weight must be in [0, 2]')
        if future_mode not in ('anchor', 'route'):
            raise ValueError('future_mode must be anchor or route')
        if not 1 <= self.future_shortlist <= 16:
            raise ValueError('future_shortlist must be in [1, 16]')
        if not math.isfinite(self.future_budget_s) or self.future_budget_s < 0:
            raise ValueError('future_budget_s must be finite and nonnegative')
        if not math.isfinite(self.future_min_gain_s) or self.future_min_gain_s < 0:
            raise ValueError('future_min_gain_s must be finite and nonnegative')

    def _base_candidates(self, ch, poly, current, previous):
        """The original G+ candidate set and score, plus retained branch data.

        Deliberately retain its source weights, +/-1.005 ranking errors, 1.01
        degree geometric updates, all tie breaks and reception rejection.
        Only the cheapest bounded shortlist retains its branch polygons.
        """
        center, radius = minimum_circle(poly)
        centroid = area_center(poly)
        _, a, b = diameter(poly)
        length = max(math.dist(a, b), 1e-9)
        normal = (-(b[1] - a[1]) / length, (b[0] - a[0]) / length)
        candidates = []
        for c in (center, centroid):
            offsets = sorted(set((15., 40., 80., min(400., max(100., radius * self.lateral)))))
            if self.direct_candidates:
                offsets = sorted(set(offsets + [0., 8., 25.]))
            for offset in offsets:
                for sign in (-1, 1):
                    candidates.append((c[0] + sign * offset * normal[0], c[1] + sign * offset * normal[1]))
            travel = math.dist(current, c)
            distances = (10., 20., 40., 100., 200., 400.) if self.direct_candidates else (40., 100., 200., 400.)
            if travel > 1e-8:
                for distance in distances:
                    if distance < travel:
                        candidates.append(tuple(c[k] + (current[k] - c[k]) * distance / travel for k in (0, 1)))
        for fraction in (.25, .5, .75):
            c = tuple(current[k] + fraction * (center[k] - current[k]) for k in (0, 1))
            for offset in (40., 100., 200., 400.):
                for sign in (-1, 1):
                    candidates.append((c[0] + sign * offset * normal[0], c[1] + sign * offset * normal[1]))
        for i, s in enumerate(previous):
            for t in previous[i + 1:]:
                candidates.append(((s[0] + t[0]) / 2, (s[1] + t[1]) / 2))
        if self.source_quadrature:
            quadrature = polygon_quadrature(poly)
            if len(quadrature) > 8:
                sampled = []
                accumulated = 0.
                i = 0
                for k in range(8):
                    threshold = (k + .5) / 8
                    while i < len(quadrature) - 1 and accumulated + quadrature[i][1] < threshold:
                        accumulated += quadrature[i][1]
                        i += 1
                    sampled.append((quadrature[i][0], 1 / 8))
                quadrature = sampled
        else:
            sources = [center] + [((v[0] + center[0]) / 2, (v[1] + center[1]) / 2)
                                  for v in poly[::max(1, len(poly) // 6)]]
            quadrature = [(s, 1 / len(sources)) for s in sources]
        shortlisted = []
        for q in dict.fromkeys(candidates):
            if any(math.dist(q, p) < .05 for p in previous) or not self.reception_ok(poly, q, previous):
                continue
            expected = success = rmaxall = 0.
            branches = []
            for source, weight in quadrature:
                if math.dist(q, source) <= 5:
                    expected += 5 * weight
                    success += weight
                    branches.append((weight, [(5., q, 0., None)]))
                    continue
                costs = []
                scenarios = []
                rmax = 0.
                for error in (-1.005, 0., 1.005):
                    beta = math.degrees(math.atan2(source[1] - q[1], source[0] - q[0])) + error
                    updated = clip_bearing(poly, q, beta)
                    if not updated:
                        continue
                    c, r = minimum_circle(updated)
                    cost = max(0., math.dist(q, c) - max(0., 20 - r)) / 5 + 5
                    if r > 20:
                        extra = 6 + min(160., 2 * r) / 5
                        if self.optical_cost and r <= self.optical_trial:
                            samples = polygon_quadrature(updated)
                            chance = sum(w for p, w in samples if math.dist(p, c) <= 20)
                            extra = (1 - chance) * (extra + 3)
                        cost += extra
                    costs.append(cost)
                    scenarios.append((cost, c, r, updated))
                    rmax = max(rmax, r)
                if not costs:
                    costs = [1e6]
                expected += weight * (self.error_risk * max(costs) + (1 - self.error_risk) * sum(costs) / len(costs))
                success += weight * int(rmax <= 20)
                rmaxall = max(rmaxall, rmax)
                branches.append((weight, scenarios))
            score = math.dist(current, q) / 5 + 5 + int(self.client.ledger.channel != ch) + expected
            entry = (score, -success, rmaxall, q)
            if len(shortlisted) < self.future_shortlist or entry < shortlisted[-1][0]:
                shortlisted.append((entry, branches))
                shortlisted.sort(key=lambda item: item[0])
                del shortlisted[self.future_shortlist:]
        return center, shortlisted

    def _branch_cost(self, q, branch, plans, reference):
        original, center, radius, updated = branch
        end = center
        terminal = original
        if updated is not None and radius < 20 - 1e-5:
            # The same certified operating-region optimizer used by actual G+
            # clears, but only for shortlisted predicted states.  Select one
            # entrance before geometry optimization to bound per-branch work.
            anchor, _ = min(plans, key=lambda plan: math.dist(center, plan[0]) / 5 + plan[1])
            operating = through_operating_point(updated, q, anchor)
            if operating is not None:
                end = operating
                terminal = math.dist(q, operating) / 5 + 5
        correction = terminal - original + remaining_route_cost(end, plans) - reference
        return original + self.future_weight * correction

    def choose_station(self, ch, poly, current, previous):
        if self.future_weight == 0 or self.future_budget_s == 0:
            return super().choose_station(ch, poly, current, previous)
        # Time remaining is from accepted /enter feedback maintained by Client.
        deadline = getattr(self.client, 'deadline', None)
        if deadline is not None and deadline - time.monotonic() < 5:
            return super().choose_station(ch, poly, current, previous)
        tail = self.tail_points(ch)
        if not tail:
            return super().choose_station(ch, poly, current, previous)
        center, shortlist = self._base_candidates(ch, poly, current, previous)
        if not shortlist:
            return None
        baseline = shortlist[0][0]
        result = dict(point=baseline[3], estimated_remaining_s=baseline[0],
                      geometric_success_fraction=-baseline[1], sampled_worst_radius=baseline[2],
                      error_risk=self.error_risk, direct_candidates=self.direct_candidates)
        started = time.monotonic()
        plans = remaining_route_plans(center, tail, self.future_mode)
        reference = remaining_route_cost(center, plans)
        ranked = []
        for entry, branches in shortlist:
            q = entry[3]
            expected = 0.
            for weight, scenarios in branches:
                if time.monotonic() - started > self.future_budget_s:
                    result.update(future_fallback='time_budget', future_mode=self.future_mode)
                    return result
                costs = [self._branch_cost(q, scenario, plans, reference) for scenario in scenarios] or [1e6]
                expected += weight * (self.error_risk * max(costs) + (1 - self.error_risk) * sum(costs) / len(costs))
            score = math.dist(current, q) / 5 + 5 + int(self.client.ledger.channel != ch) + expected
            ranked.append(((score, entry[1], entry[2], q), entry))
        # Compare all candidates under the same estimator, including original
        # G+.  Small modeled advantages are discarded; this is not a claim of
        # guaranteed improvement under the unknown source/error distribution.
        original_score = ranked[0][0][0]
        chosen, chosen_base = min(ranked)
        predicted_gain = original_score - chosen[0]
        if predicted_gain <= self.future_min_gain_s:
            chosen, chosen_base = ranked[0]
            predicted_gain = 0.
        result.update(point=chosen[3], estimated_remaining_s=chosen[0],
                      geometric_success_fraction=-chosen[1], sampled_worst_radius=chosen[2],
                      baseline_point=baseline[3], baseline_local_s=baseline[0],
                      chosen_local_s=chosen_base[0], estimated_route_gain_s=predicted_gain,
                      future_mode=self.future_mode, future_weight=self.future_weight,
                      future_shortlist=len(shortlist), future_tail_tasks=len(tail),
                      future_route_anchors=len(plans), future_reference_s=reference,
                      future_compute_s=time.monotonic() - started,
                      quadrature_not_certificate=True)
        return result
