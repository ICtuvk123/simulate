"""Offline single-source counterfactuals, explicitly not official simulator runs."""
import hashlib
import math

from q2_geometry import (ALPHA, clip, minimum_circle, nearest_operating_point,
                         sector_pair, wedge)
from geometry import diameter


class GeometryScene:
    """Evaluator-owned synthetic source; policy receives only action feedback."""
    def __init__(self, source, field_seed, error_mode="field"):
        self._source = source
        self._radius = max(1000.0, math.hypot(*source))
        self._seed = field_seed
        self._error_mode = error_mode
        self.position = (0.0, 0.0)
        self.move_time = self.rf_time = self.optical_time = self.clear_time = 0.0
        self.rf_count = self.optical_count = 0
        self.cleared = False
        self.events = []

    def _move(self, q):
        distance = math.dist(q, self.position)
        self.move_time += distance / 5
        self.position = q

    def measure(self, q):
        self._move(q)
        self.rf_count += 1
        self.rf_time += 5
        d = math.dist(q, self._source)
        if d > self._radius + 1e-6:
            result = {"result": "no_signal"}
        elif d <= 5:
            result = {"result": "near"}
        else:
            if self._error_mode in ("minus", "plus"):
                error = -ALPHA if self._error_mode == "minus" else ALPHA
            else:
                # Same point/source/seed always has the same error. No fresh
                # independent draws are used to shrink uncertainty by repeating.
                text = f"{self._seed}|{q[0]:.7f}|{q[1]:.7f}"
                value = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
                error = (2 * value / (2 ** 64 - 1) - 1) * ALPHA
            result = {"result": "direction", "bearing_rad":
                      math.atan2(self._source[1] - q[1], self._source[0] - q[0]) + error}
        self.events.append({"action": "measure", "point": q, **result})
        return result

    def clear(self, q):
        self._move(q)
        self.optical_count += 1
        self.optical_time += 3
        success = math.dist(q, self._source) <= 20 + 1e-8
        if success:
            self.clear_time += 2
            self.cleared = True
        self.events.append({"action": "clear", "point": q, "success": success})
        return success

    def result(self):
        return {"success": self.cleared, "total_time": self.move_time + self.rf_time
                + self.optical_time + self.clear_time, "move_time": self.move_time,
                "RF_time": self.rf_time, "optical_time": self.optical_time,
                "clear_time": self.clear_time, "RF_count": self.rf_count,
                "optical_count": self.optical_count, "switch_time": 0.0,
                "evidence": "offline_public_rule_single_source_counterfactual"}


def optical_cover(poly, start, max_points=None):
    """Oriented 20x20 cells intersecting the entire conservative region."""
    _, a, b = diameter(poly)
    length = math.dist(a, b)
    u = (1, 0) if length < 1e-9 else ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
    v = (-u[1], u[0])
    local = [(p[0] * u[0] + p[1] * u[1], p[0] * v[0] + p[1] * v[1]) for p in poly]
    points = []
    for ix in range(math.floor(min(p[0] for p in local) / 20),
                    math.floor(max(p[0] for p in local) / 20) + 1):
        for iy in range(math.floor(min(p[1] for p in local) / 20),
                        math.floor(max(p[1] for p in local) / 20) + 1):
            cell = local
            for n, bound in [((1, 0), (ix + 1) * 20), ((-1, 0), -ix * 20),
                             ((0, 1), (iy + 1) * 20), ((0, -1), -iy * 20)]:
                cell = clip(cell, n, bound)
            if cell:
                x, y = (ix + .5) * 20, (iy + .5) * 20
                points.append((x * u[0] + y * v[0], x * u[1] + y * v[1]))
                if max_points is not None and len(points) > max_points:
                    return None
    order = []
    while points:
        q = min(points, key=lambda p: math.dist(start, p))
        points.remove(q)
        order.append(q)
        start = q
    return order


def follow_policy(observation_api, second_station, use_neighborhood=True, optical_choice=True):
    """Uses only feedback and conservative polygons; never accesses source data."""
    _, poly = sector_pair()
    point = second_station
    previous = []
    for iteration in range(10):
        response = observation_api.measure(point)
        previous.append(point)
        if response["result"] == "near":
            if not observation_api.clear(point):
                raise AssertionError("near must clear")
            return
        if response["result"] == "no_signal":
            raise AssertionError("robust reception certificate failed")
        poly = wedge(poly, point, response["bearing_rad"])
        if not poly:
            raise AssertionError("valid source excluded")
        center, radius = minimum_circle(poly)
        if use_neighborhood:
            terminal = nearest_operating_point(poly, point)
        else:
            terminal = center if radius <= 20 - 1e-5 else None
        if terminal is not None:
            if not observation_api.clear(terminal):
                raise AssertionError("certified terminal failed")
            return
        _, a, b = diameter(poly)
        length = math.dist(a, b)
        normal = (0, 1) if length < 1e-9 else (-(b[1] - a[1]) / length,
                                               (b[0] - a[0]) / length)
        offset = min(60, max(20, .3 * radius))
        candidates = [(center[0] + sign * offset * normal[0],
                       center[1] + sign * offset * normal[1]) for sign in (-1, 1)]
        candidates = [q for q in candidates if max(math.dist(q, g) for g in poly) < 1000 - 1e-4
                      and all(math.dist(q, old) > 1e-4 for old in previous)]
        if not candidates:
            break
        next_point = min(candidates, key=lambda q: math.dist(point, q))
        if optical_choice:
            checks = optical_cover(poly, point, max_points=3)
            if checks:
                travel = sum(math.dist(a, b) for a, b in zip([point] + checks, checks))
                worst_optical = travel / 5 + 3 * len(checks) + 2
                # This RF alternative is an estimate, not a bound. Safety is
                # supplied by a complete optical cover whichever action is chosen.
                estimated_rf = math.dist(point, next_point) / 5 + 5 + radius / 5 + 5
                if worst_optical <= estimated_rf:
                    for q in checks:
                        if observation_api.clear(q):
                            return
                    raise AssertionError("complete optical cover failed")
        point = next_point
    for q in optical_cover(poly, observation_api.position):
        if observation_api.clear(q):
            return
    raise AssertionError("complete fallback exhausted")


def evaluate_scene(q, source, seed, mode="field", use_neighborhood=True, optical_choice=True,
                   keep_events=False):
    scene = GeometryScene(source, seed, mode)
    follow_policy(scene, q, use_neighborhood, optical_choice)
    result = scene.result()
    if keep_events:
        result["events"] = scene.events
    return result


def source_grid(nr, na, shift=.5):
    # Equal-area strata in the *modelled* first sector. The origin is excluded
    # by positive stratum offsets; this is a quadrature rule, not an asserted prior.
    return [(1500 * math.sqrt((i + shift) / nr) * math.cos(-ALPHA + 2 * ALPHA * (j + shift) / na),
             1500 * math.sqrt((i + shift) / nr) * math.sin(-ALPHA + 2 * ALPHA * (j + shift) / na))
            for i in range(nr) for j in range(na)]
