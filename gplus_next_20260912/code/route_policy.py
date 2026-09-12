"""Additional open-route neighborhoods for the frozen G+ controller.

The original route is always retained as a fallback.  The guarantee concerns
the current fixed routing anchors only; changed feedback can change the actual
future trajectory, so final action time still needs paired local evaluation.
"""
import math

from local_geometry import nearest_operating_point
from optimized import open_route, route_length
from q3client import ProtocolError
from time_policy import TimePolicy


def improve_route(start, points, original, rounds=4):
    """Improve a supplied open route with bounded Or-opt and 2-opt search.

    Single points or adjacent pairs can be reinserted anywhere, including the
    beginning and the open end.  A reversed pair is also considered.  No edge
    back to ``start`` is included.  Small routes retain the existing exact DP.
    """
    n = len(points)
    order = list(original)
    if n <= 9 or rounds <= 0:
        return order
    distance = [[math.dist(a, b) for b in points] for a in points]
    initial = [math.dist(start, p) for p in points]

    def length(candidate):
        return initial[candidate[0]] + sum(
            distance[a][b] for a, b in zip(candidate, candidate[1:]))

    original_length = length(order)
    current_length = original_length
    for _ in range(rounds):
        best_order, best_length = order, current_length
        for size in (1, 2):
            for first in range(n-size+1):
                block = order[first:first+size]
                rest = order[:first]+order[first+size:]
                blocks = (block,) if size == 1 else (block, block[::-1])
                for inserted in blocks:
                    for at in range(len(rest)+1):
                        candidate = rest[:at]+inserted+rest[at:]
                        value = length(candidate)
                        if value < best_length-1e-6:
                            best_order, best_length = candidate, value
        # Relocations can unlock reversals that the original 2-opt missed.
        for first in range(n-1):
            for last in range(first+1, n):
                candidate = order[:first]+order[first:last+1][::-1]+order[last+1:]
                value = length(candidate)
                if value < best_length-1e-6:
                    best_order, best_length = candidate, value
        if best_order is order:
            break
        order, current_length = best_order, best_length
    return order if current_length < original_length-1e-6 else list(original)


class RouteOrderPolicy(TimePolicy):
    def __init__(self, client, route_rounds=4, **options):
        if type(route_rounds) is not int or not 0 <= route_rounds <= 20:
            raise ValueError('route_rounds must be an integer in [0,20]')
        super().__init__(client, **options)
        self.route_rounds = route_rounds

    def run(self):
        # Keep StructuralController.run's action/state transitions unchanged.
        if not self.task_search:
            return super().run()
        self.client.action('/enter');self.remaining_sites=list(self.sites[1:])
        self.scan_stop((0.,0.),force=True)
        for decision in range(220):
            self.try_clear_here();self.refresh_search()
            if self.flexible_search:
                self.rebuild_flexible_search()
            pending=sorted(set(self.polygons)-self.cleared)
            if not self.remaining_sites and not pending:
                return self.finish()
            position=self.client.ledger.position
            eligible=[ch for ch in pending if not self.remaining_sites or self.info(ch)[1]<=self.max_region]
            actions=[('scan',i) for i in range(len(self.remaining_sites))]+[('clear',ch) for ch in eligible]
            points=list(self.remaining_sites)+[nearest_operating_point(self.polygons[ch],position) or self.info(ch)[0]
                                               for ch in eligible]
            if not actions:
                raise ProtocolError('F unresolved task without a feasible action')
            original=open_route(position,points)
            order=improve_route(position,points,original,self.route_rounds)
            if order != original:
                self.record(reason='H_or_opt_open_route',task_count=len(points),
                            predicted_saved_move_s=(route_length(position,points,original)
                                -route_length(position,points,order))/5,
                            fixed_anchors_only=True)
            kind,index=actions[order[0]]
            self.record(reason='F_joint_remaining_route',first_action=(kind,index),
                        targets=len(eligible),search_stops=len(self.remaining_sites))
            if kind=='scan':
                point=self.remaining_sites.pop(index);self.scan_stop(point,force=True)
            else:
                force=self.flexible_search and (not self.forecast_budget or index in self.forecast_targets)
                self.refine_and_clear(index);self.scan_stop(self.client.ledger.position,force=force)
        raise ProtocolError('F planning guard reached')
