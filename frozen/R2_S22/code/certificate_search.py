"""Per-channel future search requirements, separate from actual empty proofs.

The module never declares a channel empty. A planned station is admissible only
inside a route-feasibility witness; only the controller's actual negative history
can be used by its independent completion logic. All search budgets are integer
work limits so feedback replay does not depend on machine speed.
"""
import math
from itertools import combinations
from directional_geometry import DirectionalCoverage, hull, in_hull
from routing import route_length


class CertificateSearch:
    def __init__(self, sites, options):
        self.required = {ch: set(map(tuple, sites)) for ch in range(1, 21)}
        self.prover = DirectionalCoverage(max_depth=13, max_cells=18000,
                                          time_budget=float('inf'))
        self.options = options
        self.last_attempt = None
        self.active = False
        self.checked = {}
        # Samples can reject a plan only. Acceptance always needs the continuous
        # cell certificate below; no unproved hole is ignored.
        self.reject_points = [(0., 0.)] + [
            (r * math.cos(2 * math.pi * k / 64),
             r * math.sin(2 * math.pi * k / 64))
            for r in (900., 1799.99) for k in range(64)]

    def observe(self, ch, point):
        self.required[ch].discard(tuple(point))

    def needs(self, ch, point):
        return tuple(point) in self.required[ch]

    def prove(self, stations):
        key = frozenset(map(tuple, stations))
        if key in self.checked:
            return self.checked[key]
        points = sorted(key)
        for q in self.reject_points:
            near = [p for p in points if math.dist(p, q) <= 1000.]
            if not in_hull(hull(near), q):
                result = dict(complete=False, reason='uncovered_sample_rejection')
                self.checked[key] = result
                return result
        result = self.prover.prove(points)
        self.checked[key] = result
        return result

    def _plans(self, controller, p, unknown):
        remaining = list(map(tuple, controller.remaining))
        pending = [controller.info(ch)[0]
                   for ch in sorted(set(controller.polygons) - controller.cleared)]
        points = remaining + pending
        order = controller.plan_route(p, points)
        baseline = route_length(p, points, order) / 5.
        # Expensive detours and geometric proximity both contribute candidates.
        singleton = []
        for i in range(len(remaining)):
            after = [k for k in order if k != i]
            saving = baseline - route_length(p, points, after) / 5.
            singleton.append((saving, i))
        close = sorted(range(len(remaining)),
                       key=lambda i: (math.dist(p, remaining[i]), i))[:5]
        costly = [i for _, i in sorted(singleton, reverse=True)[:3]]
        candidates = sorted(set(close + costly))
        plans = []
        for count in range(1, 4):
            for indices in combinations(candidates, count):
                group = set(remaining[i] for i in indices)
                # No current point can replace a group that matters to nobody.
                debts = sum(len(self.required[ch] & group) for ch in unknown)
                if not debts:
                    continue
                after = [k for k in order if k not in indices]
                move_saved = baseline - route_length(p, points, after) / 5.
                ceiling = move_saved + 6. * debts
                plans.append((ceiling, move_saved, tuple(sorted(group))))
        budget = self.options.get('certificate_group_budget', 18)
        # A raw top-k by ceiling lets three-site groups starve every feasible
        # singleton. Reserve work for each cardinality before comparing gains.
        ranked = {size: sorted((plan for plan in plans if len(plan[2]) == size),
                               reverse=True) for size in (1, 2, 3)}
        chosen = ranked[1][:min(len(candidates), max(1, budget // 2))]
        rest = max(0, budget - len(chosen))
        chosen += ranked[2][:(rest + 1) // 2]
        chosen += ranked[3][:rest // 2]
        return sorted(chosen, reverse=True)

    def at_actual_stop(self, controller):
        if self.active or not controller.remaining:
            return
        controller.refresh()
        unknown = controller.unknown()
        if not unknown or not controller.remaining:
            return
        p = tuple(controller.client.ledger.position)
        # Adjacent optical/RF stops usually have nearly identical replacement
        # geometry; keep deterministic bounded work and revisit after discovery.
        state = (len(controller.polygons), len(controller.cleared))
        if self.last_attempt is not None:
            old_p, old_state = self.last_attempt
            if old_state == state and math.dist(old_p, p) < 160.:
                return
        self.last_attempt = (p, state)
        self.active = True
        try:
            plans = self._plans(controller, p, unknown)
            best = None
            partial = []
            for ceiling, move_saved, group_tuple in plans:
                if best is not None and ceiling <= best['gain']:
                    continue
                group = set(group_tuple)
                changes = {}
                needed = []
                for ch in unknown:
                    remove = self.required[ch] & group
                    if not remove:
                        continue
                    future = self.required[ch] - remove
                    actual = controller.negatives[ch]
                    proof = self.prove(list(future) + actual)
                    if proof['complete']:
                        changes[ch] = (remove, False)
                    elif (ch, p) not in controller.measured and self.prove(
                            list(future) + actual + [p])['complete']:
                        changes[ch] = (remove, True)
                        needed.append(ch)
                whole = all(not (self.required[ch] & group) or ch in changes
                            for ch in unknown)
                saved_scans = sum(len(remove) for remove, _ in changes.values())
                # 6 s is an upper bound for the new RF+switch cost. Whole-site
                # deletion earns movement savings; partial debts do not.
                gain = (move_saved if whole else 0.) + 6. * (saved_scans-len(needed))
                plan = dict(group=group_tuple, changes=changes, needed=needed,
                            whole=whole, move_saved=move_saved, gain=gain)
                if whole and gain > self.options.get('certificate_min_gain_s', 10.):
                    if best is None or gain > best['gain']:
                        best = plan
                elif gain > self.options.get('certificate_min_gain_s', 10.):
                    partial.append(plan)
            if best is None and partial:
                best = max(partial, key=lambda plan: (plan['gain'], plan['group']))
            controller.record('q4_certificate_scan_evaluation', point=p,
                              candidate_groups=len(plans),
                              chosen_predicted_gain_s=best['gain'] if best else None,
                              cached_station_sets=len(self.checked),
                              deterministic_geometry_budget=True)
            if best is None:
                return
            self._execute(controller, p, best)
        finally:
            self.active = False

    def _execute(self, controller, p, plan):
        if math.dist(p, controller.client.ledger.position) > 1e-8:
            raise ValueError('Certificate substitution requires the actual current stop')
        initial_unknown = controller.unknown()
        needed = plan['needed']
        controller.record('q4_certificate_replacement_plan', point=p,
                          proposed_removed_sites=plan['group'],
                          planned_channels=needed, predicted_saved_s=plan['gain'],
                          future_stations_only_in_plan=True)
        actual_scans = []
        for ch in sorted(needed, key=lambda ch: (ch != controller.client.ledger.channel, ch)):
            if len(set(controller.polygons) | controller.cleared) == 16:
                break
            if ch in controller.unknown() and (ch, p) not in controller.measured:
                result = controller.measure(p, ch, 'certificate_replacement_search')
                actual_scans.append(dict(channel=ch, result=result))
        # Re-prove using actual accepted negative responses. A planned no_signal
        # never enters requirements or an exit certificate.
        changed = {}
        for ch, (remove, _) in plan['changes'].items():
            if ch not in controller.unknown():
                continue
            future = self.required[ch] - remove
            proof = self.prove(list(future) + controller.negatives[ch])
            if proof['complete']:
                self.required[ch] = future
                changed[ch] = dict(removed_sites=sorted(remove),
                                   actual_negative_sites=controller.negatives[ch],
                                   remaining_planned_sites=sorted(future), proof=proof)
        unknown = controller.unknown()
        removed = [tuple(q) for q in controller.remaining
                   if not any(tuple(q) in self.required[ch] for ch in unknown)]
        if removed:
            controller.remaining = [q for q in controller.remaining if tuple(q) not in removed]
            controller.record('q4_certificate_sites_removed', point=p,
                              removed_sites=removed, actual_scanned_channels=actual_scans,
                              predicted_move_saved_s=plan['move_saved'] if plan['whole'] else 0.,
                              route_redundancy_witness=changed,
                              initial_unknown_channels=initial_unknown,
                              remaining_unknown_channels=unknown,
                              future_stations_only_in_plan=True)
        elif changed:
            controller.record('q4_certificate_channel_demands_removed', point=p,
                              actual_scanned_channels=actual_scans,
                              route_redundancy_witness=changed,
                              future_stations_only_in_plan=True)
        controller.refresh()
