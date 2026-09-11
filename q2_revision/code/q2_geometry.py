"""Q2 geometry in the S1=(0,0), theta1=0 coordinate frame. No I/O or network."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))
from geometry import clip, minimum_circle, contains

ALPHA = math.pi / 180
RANGE = 1500.0


def sector_pair(alpha=ALPHA, radius=RANGE, segments=16):
    angles = [-alpha + 2 * alpha * k / segments for k in range(segments + 1)]
    inner = [(0.0, 0.0)] + [((radius - 1e-7) * math.cos(a),
                             (radius - 1e-7) * math.sin(a)) for a in angles]
    outer = [(0.0, 0.0), (radius * math.cos(-alpha), radius * math.sin(-alpha))]
    for a, b in zip(angles, angles[1:]):
        r = (radius + 1e-7) / math.cos((b - a) / 2)
        outer.append((r * math.cos((a + b) / 2), r * math.sin((a + b) / 2)))
    outer.append((radius * math.cos(alpha), radius * math.sin(alpha)))
    return inner, outer


def area(poly):
    return abs(sum(p[0] * q[1] - p[1] * q[0]
                   for p, q in zip(poly, poly[1:] + poly[:1]))) / 2 if poly else 0.0


def safe_slack(q, alpha=ALPHA):
    centers = [(0, 0), (1000 * math.cos(alpha), 1000 * math.sin(alpha)),
               (1000 * math.cos(alpha), -1000 * math.sin(alpha))]
    return min(1000 - math.dist(q, c) for c in centers)


def wedge(poly, q, beta, half=ALPHA, inner=False):
    if half <= 0:
        return []
    if half >= math.pi / 2:
        # Conservative outer bound for a nonconvex wide wedge.
        return [] if inner else list(poly)
    lo, hi = beta - half, beta + half
    for n in ((math.sin(lo), -math.cos(lo)), (-math.sin(hi), math.cos(hi))):
        b = n[0] * q[0] + n[1] * q[1] - (4e-8 if inner else 0)
        poly = clip(poly, n, b)
    return poly


def enclosing_radius(poly, lower=False):
    if not poly:
        return 0.0
    r = minimum_circle(poly)[1]
    return max(0.0, r - 1e-6) if lower else r + 1e-6


def nearest_operating_point(poly, p, radius=20.0):
    """Projection onto intersection of vertex-centered disks, with margin.

    A projection is p itself, a smooth circular boundary projection, or a
    circle-circle intersection. Enumerating these gives the polygon's exact K
    projection in real arithmetic, apart from the explicit safety margin.
    """
    r = radius - 1e-5
    if not poly:
        raise ValueError("empty source region")
    def feasible(q):
        return all(math.dist(q, v) <= r + 1e-8 for v in poly)
    if feasible(p):
        return p
    center, bound = minimum_circle(poly)
    if bound > r + 1e-7:
        return None
    candidates = [center] if feasible(center) else []
    for v in poly:
        d = math.dist(p, v)
        if d > 1e-12:
            q = (v[0] + r * (p[0] - v[0]) / d, v[1] + r * (p[1] - v[1]) / d)
            if feasible(q):
                candidates.append(q)
    for i, a in enumerate(poly):
        for b in poly[i + 1:]:
            d = math.dist(a, b)
            if not 1e-10 < d <= 2 * r:
                continue
            h = math.sqrt(max(0.0, r * r - d * d / 4))
            middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            for sign in (-1, 1):
                q = (middle[0] - sign * h * (b[1] - a[1]) / d,
                     middle[1] + sign * h * (b[0] - a[0]) / d)
                if feasible(q):
                    candidates.append(q)
    return min(candidates, key=lambda q: math.dist(p, q)) if candidates else None


def unwrap(angle, reference):
    return reference + (angle - reference + math.pi) % (2 * math.pi) - math.pi


def angular_span(poly, q):
    if contains(poly, q):
        return -math.pi, math.pi
    center = (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    ref = math.atan2(center[1] - q[1], center[0] - q[0])
    angles = [unwrap(math.atan2(p[1] - q[1], p[0] - q[0]), ref) for p in poly]
    return min(angles), max(angles)


def merge_intervals(intervals):
    result = []
    for lo, hi in sorted(intervals):
        if lo >= hi:
            continue
        if result and lo <= result[-1][1] + 1e-12:
            result[-1] = (result[-1][0], max(hi, result[-1][1]))
        else:
            result.append((lo, hi))
    return result


def angular_area(poly, q, intervals, span):
    total = 0.0
    # Intervals use one unwrapped angular frame and cannot overlap after merging.
    for lo, hi in merge_intervals(intervals):
        lo, hi = max(lo, span[0]), min(hi, span[1])
        if hi <= lo:
            continue
        n = max(1, math.ceil((hi - lo) / (math.pi / 2)))
        for i in range(n):
            a, b = lo + (hi - lo) * i / n, lo + (hi - lo) * (i + 1) / n
            total += area(wedge(poly, q, (a + b) / 2, (b - a) / 2, inner=True))
    return total


def clip_disk(poly, q, r, sides=96, inner=False):
    # Intersect with an inscribed/circumscribed regular disk approximation.
    bound_r = r * math.cos(math.pi / sides) - 1e-7 if inner else r + 1e-7
    for k in range(sides):
        a = 2 * math.pi * k / sides
        n = (math.cos(a), math.sin(a))
        poly = clip(poly, n, n[0] * q[0] + n[1] * q[1] + bound_r)
    return poly


def coverage_bounds(q, alpha=ALPHA, angle_tolerance=2e-4, radius_tolerance=3.0,
                    segments=16, max_nodes=12000, keep_intervals=False):
    """Bound P20 over continuous G and e2, using observation-space subdivision.

    At beta in [b-h,b+h], W(b,alpha-h) is contained in W(beta,alpha),
    which is contained in W(b,alpha+h). Inner/outer initial sector polygons
    make MEC bounds and area bounds conservative. near is a separate success.
    """
    if safe_slack(q, alpha) < -1e-6:
        raise ValueError("second station outside the proved safe region")
    inner, outer = sector_pair(alpha, segments=segments)
    span = angular_span(outer, q)
    todo = [(span[0] - alpha, span[1] + alpha)]
    leaves, nodes = [], 0
    while todo:
        lo, hi = todo.pop()
        mid, half = (lo + hi) / 2, (hi - lo) / 2
        small = wedge(inner, q, mid, alpha - half, inner=True)
        large = wedge(outer, q, mid, alpha + half)
        lower, upper = enclosing_radius(small, True), enclosing_radius(large)
        nodes += 1
        label = "good" if upper <= 20 else ("bad" if lower > 20 else "unknown")
        resolved = label != "unknown" and upper - lower <= radius_tolerance
        if resolved or hi - lo <= angle_tolerance or nodes + len(todo) >= max_nodes:
            leaves.append((lo, hi, label, lower, upper))
        else:
            todo.extend(((lo, mid), (mid, hi)))
    good_beta = merge_intervals((a, b) for a, b, label, _, _ in leaves if label == "good")
    good_phi = [(a + alpha, b - alpha) for a, b in good_beta if b - a > 2 * alpha]
    bad_phi = merge_intervals((a - alpha, b + alpha)
                              for a, b, label, _, _ in leaves if label == "bad")
    denominator = alpha * RANGE ** 2
    # The theoretical first-direction model keeps r=0 as a conservative closure.
    # The <=5m second-observation branch is always immediately clearable.
    near_inner = clip_disk(inner, q, 5, inner=True)
    near_outer = clip_disk(outer, q, 5)
    good_area = angular_area(inner, q, good_phi, span)
    bad_area = angular_area(inner, q, bad_phi, span)
    good_near_upper = angular_area(near_outer, q, good_phi, span) + 1e-5
    bad_near_upper = angular_area(near_outer, q, bad_phi, span) + 1e-5
    p_lower = max(0.0, (good_area + area(near_inner) - good_near_upper - 1e-4) / denominator)
    p_upper = min(1.0, 1 - max(0, bad_area - bad_near_upper - 1e-4) / denominator)
    result = {"x": q[0], "y": q[1], "p20_lower": p_lower, "p20_upper": p_upper,
              "p20_mid": (p_lower + p_upper) / 2,
              "j_radius_lower": max(row[3] for row in leaves),
              "j_radius_upper": max(row[4] for row in leaves),
              "first_move_time": math.hypot(*q) / 5,
              "safe_slack_m": safe_slack(q, alpha), "interval_nodes": nodes,
              "angle_tolerance_rad": angle_tolerance,
              "sector_segments": segments, "evidence": "offline_geometric_bounds"}
    if keep_intervals:
        result.update(observation_intervals=sorted(leaves), good_source_angles=good_phi,
                      bad_source_angles=bad_phi, source_angle_span=span)
    return result
