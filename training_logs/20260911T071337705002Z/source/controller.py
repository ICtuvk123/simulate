"""Initial official-interface baselines. No hidden scene data is accepted."""
from __future__ import annotations

import math

from geometry import (clip, clip_bearing, contains, diameter, minimum_circle,
                      nearest_safe_point, open_held_karp, outer_disk, regular_fallback,
                      simple_intersection)
from q3client import ProtocolError


class BaselineController:
    def __init__(self, client, baseline="A", ring_radius=1300.0):
        if baseline not in ("A", "B"):
            raise ValueError("Only implemented baselines A and B may be selected")
        self.client = client
        self.baseline = baseline
        self.polygons = {}
        self.bearings = {}
        self.scan_history = {ch: [] for ch in range(1, 21)}
        self.sites, self.coverage_certificate = regular_fallback(ring_radius)
        self.completion_certificate = None
        self.initial_route = None

    @property
    def cleared(self):
        return self.client.ledger.cleared

    def record(self, **event):
        self.client.journal.append({"event": "policy", **event})

    def measure(self, point, channel):
        response = self.client.action("/measure", point, channel)
        result = response["measure_result"]
        self.scan_history[channel].append((point, result))
        if result == "near":
            clear = self.client.action("/clear", point, channel)
            if clear["clear_result"] != "success":
                raise ProtocolError("near did not imply successful same-position clearing")
            self.record(reason="strong_signal_shortcut", channel=channel)
        elif result == "direction":
            poly = clip_bearing(self.polygons.get(channel, outer_disk()), point,
                                response["svd_deg"])
            if not poly:
                raise ProtocolError("Legal bearings produced an empty conservative region")
            self.polygons[channel] = poly
            self.bearings.setdefault(channel, []).append((point, response["svd_deg"]))
        return response

    def estimate(self, channel):
        poly = self.polygons[channel]
        if self.baseline == "A":
            bearings = self.bearings[channel]
            # Use the widest baseline pair for simple center-line intersection.
            pairs = [(math.dist(a[0], b[0]), a, b) for i, a in enumerate(bearings)
                     for b in bearings[i + 1:]]
            for _, first, second in sorted(pairs, reverse=True):
                point = simple_intersection(first, second)
                if point is not None and contains(poly, point):
                    return point
        return minimum_circle(poly)[0]

    def scan_fixed_route(self):
        self.record(reason="fixed_scan_begin", certificate=self.coverage_certificate,
                    sites=self.sites)
        for point in self.sites:
            active = [ch for ch in range(1, 21) if ch not in self.cleared]
            # The receiver's current channel is free to begin with at the next station.
            active.sort(key=lambda ch: (ch != self.client.ledger.channel, ch))
            for channel in active:
                if channel in self.polygons:
                    # Once an existing target is sufficiently localized, more RF has no purpose.
                    if nearest_safe_point(self.polygons[channel], point) is not None:
                        continue
                self.measure(point, channel)

    def refine_and_clear(self, channel):
        for iteration in range(12):
            if channel in self.cleared:
                return
            poly = self.polygons[channel]
            if self.baseline == "A":
                point = self.estimate(channel)
                if max(math.dist(point, p) for p in poly) <= 20.0 - 1e-5:
                    safe = point
                else:
                    safe = None
            else:
                safe = nearest_safe_point(poly, self.client.ledger.position)
            if safe is not None:
                response = self.client.action("/clear", safe, channel)
                if response["clear_result"] != "success":
                    raise ProtocolError("A geometrically guaranteed clearing failed")
                self.record(reason="guaranteed_clear", channel=channel, point=safe,
                            region_vertices=poly)
                return
            center, radius = minimum_circle(poly)
            _, a, b = diameter(poly)
            length = math.dist(a, b)
            normal = (0.0, 1.0) if length < 1e-8 else (-(b[1] - a[1]) / length,
                                                       (b[0] - a[0]) / length)
            offset = min(100.0, max(25.0, 0.35 * radius))
            candidates = [(center[0] + sign * offset * normal[0],
                           center[1] + sign * offset * normal[1]) for sign in (-1, 1)]
            previous = [position for position, _ in self.bearings[channel]]
            candidates.sort(key=lambda q: (any(math.dist(q, p) < 0.01 for p in previous),
                                            math.dist(q, self.client.ledger.position)))
            point = candidates[0]
            self.record(reason="localization_refinement", channel=channel,
                        iteration=iteration, enclosing_radius=radius, point=point)
            response = self.measure(point, channel)
            if response["measure_result"] == "no_signal":
                # A conservative circle gives an independent check on minimum RF range.
                if max(math.dist(point, p) for p in poly) <= 1000 - 1e-5:
                    raise ProtocolError("No signal inside a proved minimum-radius reception region")
                break
        self.optical_fallback(channel)

    def optical_fallback(self, channel):
        """Finite 20m grid of cells intersecting the conservative feasible polygon.

        Every point of a cell is within sqrt(200)<20m of its center. This supplies
        a completion fallback without claiming it is fast or statistically optimal.
        """
        poly = self.polygons[channel]
        xmin, xmax = min(p[0] for p in poly), max(p[0] for p in poly)
        ymin, ymax = min(p[1] for p in poly), max(p[1] for p in poly)
        candidates = []
        for ix in range(math.floor(xmin / 20), math.floor(xmax / 20) + 1):
            for iy in range(math.floor(ymin / 20), math.floor(ymax / 20) + 1):
                cell = poly
                for normal, bound in [((1, 0), (ix + 1) * 20), ((-1, 0), -ix * 20),
                                      ((0, 1), (iy + 1) * 20), ((0, -1), -iy * 20)]:
                    cell = clip(cell, normal, bound)
                if cell:
                    candidates.append(((ix + 0.5) * 20, (iy + 0.5) * 20))
        self.record(reason="finite_optical_fallback", channel=channel,
                    candidate_count=len(candidates), cell_size=20)
        while candidates:
            index = min(range(len(candidates)), key=lambda i:
                        math.dist(candidates[i], self.client.ledger.position))
            point = candidates.pop(index)
            if self.client.action("/clear", point, channel)["clear_result"] == "success":
                return
        raise ProtocolError("Exhausted a complete optical cover without clearing known target")

    def run(self):
        self.client.action("/enter")
        self.scan_fixed_route()
        pending = sorted(set(self.polygons) - self.cleared)
        if self.baseline == "B":
            order, length = open_held_karp(self.client.ledger.position,
                                         [self.estimate(ch) for ch in pending])
            pending = [pending[i] for i in order]
            self.initial_route = {"order": pending.copy(), "fixed_center_distance": length}
            self.record(reason="held_karp_open_route", **self.initial_route)
        while pending:
            if self.baseline == "A":
                pending.sort(key=lambda ch: math.dist(self.client.ledger.position,
                                                      self.estimate(ch)))
            self.refine_and_clear(pending.pop(0))
        undiscovered = set(range(1, 21)) - self.cleared
        for channel in undiscovered:
            # No discovered source may remain, and all seven guaranteed sites must
            # have actually returned no_signal on every undiscovered channel.
            if channel in self.polygons:
                raise ProtocolError("Discovered source remains uncleared")
            for site in self.sites:
                if not any(result == "no_signal" and math.dist(point, site) < 1e-8
                           for point, result in self.scan_history[channel]):
                    raise ProtocolError("Missing a required per-channel coverage observation")
        self.completion_certificate = {**self.coverage_certificate,
                                       "cleared_channels": sorted(self.cleared),
                                       "empty_channels": sorted(undiscovered),
                                       "all_discovered_cleared": True}
        self.record(reason="completion_proved", certificate=self.completion_certificate)
        self.client.action("/exit")
        return self.completion_certificate
