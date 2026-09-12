"""G candidates: adapt covering stations to observed tasks, never hidden scenes.

Forecast coverage ranks plans only. StructuralController.finish independently
requires complete per-channel coverage from accepted negative feedback.
"""
import math

from structural import StructuralController
from optimized import open_route, route_length
from coverage import coverage_partition


def oriented_ring_plan(current, sites, targets):
    base = route_length(current, sites + targets, open_route(current, sites + targets))
    best = (base, 0., sites)
    angles = set(range(0, 60, 5))
    for p in targets:
        angles.add(math.degrees(math.atan2(p[1], p[0])) % 60)
    for angle in sorted(angles):
        a = math.radians(angle)
        rotated = [(x*math.cos(a)-y*math.sin(a), x*math.sin(a)+y*math.cos(a)) for x,y in sites]
        points = rotated + targets
        length = route_length(current, points, open_route(current, points))
        if length < best[0]-1e-6:
            # Continuous coverage certificate, independent of routing samples.
            if coverage_partition([(0.,0.)] + rotated, 12)['complete']:
                best = (length, angle, rotated)
    return best, base


def project_segment(p, a, b):
    length2 = sum((b[k]-a[k])**2 for k in (0,1))
    t = max(0., min(1., sum((p[k]-a[k])*(b[k]-a[k]) for k in (0,1))/length2)) if length2 else 0.
    return tuple(a[k]+t*(b[k]-a[k]) for k in (0,1))


class RouteSearchController(StructuralController):
    def __init__(self, client, rotate_search=False, bend_search=False, **options):
        super().__init__(client, **options)
        self.rotate_search = bool(rotate_search)
        self.bend_search = bool(bend_search)
        self.orientation_chosen = False

    def scan_stop(self, point, force=False):
        result = super().scan_stop(point, force)
        if self.rotate_search and not self.orientation_chosen:
            self.orientation_chosen = True
            if not self.search_complete:
                targets = [self.info(ch)[0] for ch in sorted(set(self.polygons)-self.cleared)]
                (length, angle, sites), base = oriented_ring_plan(point, self.sites[1:], targets)
                self.sites = [(0.,0.)] + sites
                self.remaining_sites = list(sites)
                self.record(reason='G_observed_tasks_rotate_cover', angle_deg=angle,
                            predicted_saved_move_s=(base-length)/5, source='accepted_bearings_only')
        return result

    def rebuild_budgeted_forecast(self):
        super().rebuild_budgeted_forecast()
        if not self.bend_search or not self.remaining_sites:
            return
        pending = sorted(set(self.polygons)-self.cleared)
        targets = [self.info(ch)[0] for ch in pending]
        current = self.client.ledger.position
        unknown = self.unknown_channels()
        anchors = [self.info(ch)[0] for ch in sorted(self.forecast_targets)]
        points = self.remaining_sites + targets
        order = open_route(current, points)
        selected = [points[i] for i in order if i < len(self.remaining_sites)][:2]
        for original in selected:
            i = self.remaining_sites.index(original)
            points = self.remaining_sites + targets
            order = open_route(current, points)
            j = order.index(i)
            before = current if j == 0 else points[order[j-1]]
            after = points[order[j+1]] if j+1 < len(order) else before
            goals = [before, after, project_segment(original,before,after)] + targets
            candidates = []
            for target in goals:
                for fraction in (.25,.5,.75,1.):
                    q = tuple(original[k]+fraction*(target[k]-original[k]) for k in (0,1))
                    if math.dist(q,original)>1 and q not in candidates:
                        candidates.append(q)
            others = self.remaining_sites[:i] + self.remaining_sites[i+1:]
            old_length = route_length(current,points,order)
            best = (old_length,original)
            for q in candidates:
                # Cheap route-screen; no coverage claim follows from this score.
                proposal = list(points); proposal[i] = q
                length = route_length(current,proposal,order)
                if length >= best[0]-1e-6:
                    continue
                if all(self.proves(self.negatives[ch]+others+anchors+[q]) for ch in unknown):
                    best = (length,q)
            if best[1] != original:
                self.remaining_sites[i] = best[1]
                self.record(reason='G_route_bent_search_station',original=original,point=best[1],
                            predicted_saved_move_s=(old_length-best[0])/5,
                            coverage_uses_forecast=bool(anchors),future_not_in_certificate=True)
