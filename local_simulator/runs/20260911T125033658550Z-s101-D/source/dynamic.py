"""Dynamic baseline C: shared stops, opportunistic bearings and proved coverage."""
import math

from controller import BaselineController
from coverage import coverage_partition, hole_candidates
from geometry import minimum_circle, nearest_safe_point
from q3client import ProtocolError


class DynamicController(BaselineController):
    def __init__(self, client, depth=2, beam_width=8, opportunistic=True):
        super().__init__(client, "B")
        self.depth, self.beam_width = depth, beam_width
        self.opportunistic = opportunistic
        self.search_stations = []

    def measure(self, point, channel):
        response = super().measure(point, channel)
        self.scan_at_stop(point, primary=channel)
        return response

    def scan_at_stop(self, point, primary=None, force=False):
        if len(self.cleared) == 16:
            return
        useful = force or all(math.dist(point, old) > 100 for old in self.search_stations)
        unknown = [ch for ch in range(1, 21) if ch not in self.polygons and ch not in self.cleared]
        if useful:
            unknown.sort(key=lambda ch: (ch != self.client.ledger.channel, ch))
            for channel in unknown:
                # Bypass the override to avoid recursive scans.
                BaselineController.measure(self, point, channel)
            self.search_stations.append(point)
            self.record(reason="shared_search_stop", point=point, unknown_channel_count=len(unknown))
        if not self.opportunistic:
            return
        known = sorted(set(self.polygons) - self.cleared - ({primary} if primary else set()))
        known.sort(key=lambda ch: (ch != self.client.ledger.channel, ch))
        for channel in known:
            poly = self.polygons[channel]
            if nearest_safe_point(poly, point) is not None:
                continue
            center, _ = minimum_circle(poly)
            history = self.bearings[channel]
            if any(math.dist(point, old) < 150 for old, _ in history):
                continue
            now = math.atan2(point[1] - center[1], point[0] - center[0])
            diversity = max(abs(math.sin(now - math.atan2(old[1] - center[1], old[0] - center[0])))
                            for old, _ in history)
            if math.dist(center, point) < 1200 and diversity > .35:
                self.record(reason="opportunistic_bearing", channel=channel,
                            point=point, extra_move_distance=0, geometry_score=diversity)
                BaselineController.measure(self, point, channel)

    def choose_known(self, channels):
        position = self.client.ledger.position
        centers = {ch: minimum_circle(self.polygons[ch]) for ch in channels}
        service = {ch: 5 + (6 + min(100, r) / 5 if r > 20 else 0)
                   for ch, (_, r) in centers.items()}
        def tail_bound(p, remaining):
            if not remaining:
                return 0.0
            # Travel/service surrogate, never a physical optimality certificate.
            return min(math.dist(p, centers[ch][0]) / 5 for ch in remaining) + sum(service[ch] for ch in remaining)
        beam = [(0.0, [], position)]
        for step in range(min(self.depth, len(channels))):
            expanded = []
            for cost, order, p in beam:
                for ch in channels:
                    if ch in order:
                        continue
                    q = nearest_safe_point(self.polygons[ch], p) or centers[ch][0]
                    new_cost = cost + math.dist(p, q) / 5 + service[ch]
                    new_order = order + [ch]
                    remaining = [c for c in channels if c not in new_order]
                    expanded.append((new_cost + tail_bound(q, remaining), new_cost, new_order, q))
            expanded.sort(key=lambda row: (row[0], row[2]))
            beam = [(cost, order, point) for _, cost, order, point in expanded[:self.beam_width]]
        selected = min(beam, key=lambda row: row[0] + tail_bound(row[2], [c for c in channels if c not in row[1]]))
        self.record(reason="rolling_time_proxy", depth=self.depth, beam_width=self.beam_width,
                    planned_channels=selected[1], prefix_estimated_seconds=selected[0])
        return selected[1][0]

    def run(self):
        self.client.action("/enter")
        self.scan_at_stop((0.0, 0.0), force=True)
        fallback_index = 0
        for decision in range(160):
            if len(self.cleared) == 16:
                certificate = {"kind": "sixteen_cleared_public_upper_bound"}
                break
            pending = sorted(set(self.polygons) - self.cleared)
            if pending:
                channel = self.choose_known(pending)
                super().refine_and_clear(channel)
                self.scan_at_stop(self.client.ledger.position)
                continue
            partition = coverage_partition(self.search_stations, 12)
            if partition["complete"]:
                certificate = {key: value for key, value in partition.items() if key != "holes"}
                break
            if len(self.search_stations) >= 30:
                if fallback_index >= len(self.sites):
                    raise ProtocolError("complete fallback did not prove coverage")
                point = self.sites[fallback_index]
                fallback_index += 1
            else:
                current = self.client.ledger.position
                coarse = coverage_partition(self.search_stations, 6)
                candidates = hole_candidates(coarse, 8) + self.sites[1:]
                unknown_count = 20 - len(self.cleared)
                def score(q):
                    left = coverage_partition(self.search_stations + [q], 6)
                    before = sum((b[2] - b[0]) * (b[3] - b[1]) for b in coarse["holes"])
                    after = sum((b[2] - b[0]) * (b[3] - b[1]) for b in left["holes"])
                    return max(0, before - after) / (math.dist(current, q) / 5 + 6 * unknown_count)
                point = max(candidates, key=score)
                if any(math.dist(point, old) < 1e-6 for old in self.search_stations):
                    point = hole_candidates(partition, 1)[0]
            self.record(reason="adaptive_coverage_gap", point=point,
                        unresolved_cells=len(partition["holes"]))
            self.scan_at_stop(point, force=True)
        else:
            raise ProtocolError("dynamic decision guard reached")
        if not 10 <= len(self.cleared) <= 16:
            raise ProtocolError("cleared count contradicts Q3")
        certificate.update(cleared_channels=sorted(self.cleared),
                           empty_channels=sorted(set(range(1, 21)) - self.cleared),
                           all_discovered_cleared=True)
        self.completion_certificate = certificate
        self.record(reason="completion_proved", certificate=certificate)
        self.client.action("/exit")
        return certificate
