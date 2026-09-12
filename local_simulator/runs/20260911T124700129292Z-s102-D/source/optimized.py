"""Feedback-only, joint search/localization/clearing policies.

Coverage samples rank optional scans; only exact conservative certificates end
search. There is deliberately no scenario seed, source count, or truth input.
"""
import math

from controller import BaselineController
from coverage import coverage_partition
from geometry import minimum_circle, nearest_safe_point, regular_fallback, open_held_karp
from q3client import ProtocolError


def route_length(start, points, order):
    return sum(math.dist(a, b) for a, b in zip([start]+[points[i] for i in order],
                                               [points[i] for i in order]))


def open_route(start, points):
    """Multiple-start nearest-neighbor and open 2-opt; heuristic for large n."""
    n = len(points)
    if n <= 9:
        return open_held_karp(start, points)[0]
    distance = [[math.dist(a, b) for b in points] for a in points]
    initial = [math.dist(start, p) for p in points]
    best = None
    for first in sorted(range(n), key=lambda i: initial[i])[:min(n, 5)]:
        order, left = [first], set(range(n)) - {first}
        while left:
            selected = min(left, key=lambda i: (distance[order[-1]][i], i))
            order.append(selected)
            left.remove(selected)
        for iteration in range(30):
            improvement, pair = 1e-6, None
            for i in range(n-1):
                for j in range(i+1, n):
                    old = initial[order[i]] if i == 0 else distance[order[i-1]][order[i]]
                    new = initial[order[j]] if i == 0 else distance[order[i-1]][order[j]]
                    if j+1 < n:
                        old += distance[order[j]][order[j+1]]
                        new += distance[order[i]][order[j+1]]
                    if old-new > improvement:
                        improvement, pair = old-new, (i, j)
            if pair is None:
                break
            i, j = pair
            order[i:j+1] = reversed(order[i:j+1])
        candidate = (route_length(start, points, order), order)
        if best is None or candidate < best:
            best = candidate
    return best[1]


class OptimizedController(BaselineController):
    def __init__(self, client, mode='joint', ring_radius=1130.0,
                 scan_gain=0.08, known_scan=True, max_region=120.0,
                 opportunistic_clear=True, optical_trial=0.0, ring_rotation=0.0,
                 prune_stations=False):
        super().__init__(client, 'B', ring_radius)
        if mode not in ('compact', 'joint', 'pruned_dynamic'):
            raise ValueError('Unknown optimized policy')
        self.mode = mode
        self.scan_gain = float(scan_gain)
        self.known_scan = bool(known_scan)
        self.max_region = float(max_region)
        self.opportunistic_clear = bool(opportunistic_clear)
        self.optical_trial = float(optical_trial)
        self.prune_stations = bool(prune_stations)
        angle = math.radians(ring_rotation)
        self.sites = [(x*math.cos(angle)-y*math.sin(angle), x*math.sin(angle)+y*math.cos(angle))
                      for x, y in self.sites]
        self.search_stations = []
        self.search_complete = False
        self.geometry_cache = {}
        # Deterministic area quadrature, for decision costs only, never completion.
        self.area_points = [(100*x, 100*y) for x in range(-18, 19) for y in range(-18, 19)
                            if x*x+y*y <= 18*18]
        self.uncovered = set(range(len(self.area_points)))

    def info(self, ch):
        poly = self.polygons[ch]
        entry = self.geometry_cache.get(ch)
        if entry is None or entry[0] is not poly:
            self.geometry_cache[ch] = (poly, minimum_circle(poly))
        return self.geometry_cache[ch][1]

    def measure(self, point, channel):
        return BaselineController.measure(self, point, channel)

    def scan_gain_at(self, point):
        return {i for i in self.uncovered if math.dist(point, self.area_points[i]) < 999.0}

    def scan_stop(self, point, force=False):
        if len(set(self.polygons) | self.cleared) == 16:
            self.search_complete = True
        unknown = [ch for ch in range(1, 21) if ch not in self.polygons and ch not in self.cleared]
        if len(self.cleared) == 16 or self.search_complete:
            unknown = []
        gain = self.scan_gain_at(point)
        do_search = force or (len(gain) >= max(1, self.scan_gain*len(self.area_points)))
        if unknown and do_search:
            unknown.sort(key=lambda ch: (ch != self.client.ledger.channel, ch))
            for ch in unknown:
                self.measure(point, ch)
            self.search_stations.append(point)
            self.uncovered.difference_update(gain)
            # A proof is checked at every potentially useful search stop.
            if not self.uncovered and coverage_partition(self.search_stations, 12)['complete']:
                self.search_complete = True
            self.record(reason='gain_filtered_search', point=point, unknown_channels=len(unknown),
                        added_area_cells=len(gain), coverage_proved=self.search_complete)
        if not self.known_scan:
            return
        known = sorted(set(self.polygons)-self.cleared,
                       key=lambda ch: (ch != self.client.ledger.channel, ch))
        for ch in known:
            center, radius = self.info(ch)
            if radius < 20 or math.dist(center, point) > 1400:
                continue
            history = self.bearings[ch]
            if any(math.dist(point, old) < 120 for old, _ in history):
                continue
            now = math.atan2(point[1]-center[1], point[0]-center[0])
            sine = max(abs(math.sin(now-math.atan2(old[1]-center[1], old[0]-center[0])))
                       for old, _ in history)
            # A 6 s RF must predict a material decrease in future positioning.
            predicted = math.dist(center, point)*math.tan(math.radians(1.01))/max(sine, .02)
            if sine > .3 and (predicted < 20 or predicted < .5*radius):
                self.record(reason='useful_shared_bearing', channel=ch, estimated_radius=predicted)
                self.measure(point, ch)

    def try_clear_here(self):
        if not self.opportunistic_clear:
            return
        position = self.client.ledger.position
        for ch in sorted(set(self.polygons)-self.cleared):
            if max(math.dist(position, p) for p in self.polygons[ch]) <= 20-1e-5:
                response = self.client.action('/clear', position, ch)
                if response['clear_result'] != 'success':
                    raise ProtocolError('Certified same-stop clear failed')
                self.record(reason='same_stop_guaranteed_clear', channel=ch)

    def refine_and_clear(self, channel):
        # A bounded optical trial is legal and charged even on failure. It never
        # substitutes for a proof: an unsuccessful trial falls back to robust RF.
        center, radius = self.info(channel)
        if 20 < radius <= self.optical_trial:
            self.record(reason='optical_before_rf', channel=channel, radius=radius)
            response = self.client.action('/clear', center, channel)
            if response['clear_result'] == 'success':
                return
        super().refine_and_clear(channel)

    def finish(self):
        if not 10 <= len(self.cleared) <= 16 or set(self.polygons)-self.cleared:
            raise ProtocolError('Incomplete clearing')
        if len(self.cleared) == 16:
            certificate = {'kind':'sixteen_cleared_public_upper_bound'}
        else:
            partition = coverage_partition(self.search_stations, 12)
            if not partition['complete']:
                raise ProtocolError('Unproved search gap')
            certificate = {k:v for k,v in partition.items() if k != 'holes'}
        certificate.update(cleared_channels=sorted(self.cleared),
                           empty_channels=sorted(set(range(1,21))-self.cleared),
                           all_discovered_cleared=True)
        self.completion_certificate = certificate
        self.record(reason='completion_proved', certificate=certificate)
        self.client.action('/exit')
        return certificate

    def run(self):
        self.client.action('/enter')
        self.scan_stop((0.0, 0.0), force=True)
        left = list(self.sites[1:])
        for decision in range(180):
            self.try_clear_here()
            pending = sorted(set(self.polygons)-self.cleared)
            if len(self.cleared) == 16 or self.search_complete:
                left = []
            if self.prune_stations and left:
                # A clear stop that was actually scanned can replace a future
                # dedicated station. Certify the union including planned stops;
                # final completion still requires actual accepted observations.
                for i in range(len(left)-1, -1, -1):
                    if coverage_partition(self.search_stations+left[:i]+left[i+1:], 9)['complete']:
                        self.record(reason='redundant_future_station_removed', point=left[i])
                        left.pop(i)
            if not left and not pending:
                return self.finish()
            position = self.client.ledger.position
            if self.mode == 'compact' and left:
                point = left.pop(0)
                self.scan_stop(point, force=True)
                continue
            eligible = [ch for ch in pending if not left or self.info(ch)[1] <= self.max_region]
            # Jointly route required coverage stations and sufficiently localized
            # clear stops. Replan after each stop using only observed polygons.
            actions = [('scan', i) for i in range(len(left))]+[('clear', ch) for ch in eligible]
            points = list(left)+[nearest_safe_point(self.polygons[ch], position) or self.info(ch)[0]
                                for ch in eligible]
            if self.mode == 'pruned_dynamic' and eligible:
                selected = min(range(len(eligible)), key=lambda i: math.dist(position, points[len(left)+i]))
                action = ('clear', eligible[selected])
            else:
                order = open_route(position, points)
                action = actions[order[0]]
                self.record(reason='joint_remaining_route', first_action=action, targets=len(eligible),
                            search_stops=len(left), proxy_move_s=route_length(position, points, order)/5)
            kind, index = action
            if kind == 'scan':
                self.scan_stop(left.pop(index), force=True)
            else:
                self.refine_and_clear(index)
                self.scan_stop(self.client.ledger.position)
        raise ProtocolError('Optimized decision guard reached')
