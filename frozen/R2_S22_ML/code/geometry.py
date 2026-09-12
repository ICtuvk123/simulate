"""Conservative geometry using public rules and legal observations only."""
from __future__ import annotations

import math
import random

EPS = 1e-8


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def clip(poly, normal, bound):
    """Intersect a convex polygon with normal dot x <= bound, outward tolerance."""
    if not poly:
        return []
    bound += EPS * max(1.0, math.hypot(*normal))
    result = []
    previous = poly[-1]
    previous_value = normal[0] * previous[0] + normal[1] * previous[1] - bound
    for current in poly:
        value = normal[0] * current[0] + normal[1] * current[1] - bound
        if (value <= 0) != (previous_value <= 0):
            fraction = previous_value / (previous_value - value)
            result.append((previous[0] + fraction * (current[0] - previous[0]),
                           previous[1] + fraction * (current[1] - previous[1])))
        if value <= 0:
            result.append(current)
        previous, previous_value = current, value
    cleaned = []
    for p in result:
        if not cleaned or math.dist(p, cleaned[-1]) > 1e-9:
            cleaned.append(p)
    if len(cleaned) > 1 and math.dist(cleaned[0], cleaned[-1]) <= 1e-9:
        cleaned.pop()
    return cleaned


def outer_disk(center=(0.0, 0.0), radius=1800.0, sides=96):
    radius = (radius + EPS) / math.cos(math.pi / sides)
    return [(center[0] + radius * math.cos((2 * k + 1) * math.pi / sides),
             center[1] + radius * math.sin((2 * k + 1) * math.pi / sides))
            for k in range(sides)]


def clip_disk_outer(poly, center, radius, sides=64):
    for k in range(sides):
        theta = 2 * math.pi * k / sides
        n = (math.cos(theta), math.sin(theta))
        poly = clip(poly, n, n[0] * center[0] + n[1] * center[1] + radius)
    return poly


def clip_bearing(poly, position, bearing_deg, error_deg=1.01):
    lo, hi = map(math.radians, (bearing_deg - error_deg, bearing_deg + error_deg))
    for n in ((math.sin(lo), -math.cos(lo)), (-math.sin(hi), math.cos(hi))):
        poly = clip(poly, n, n[0] * position[0] + n[1] * position[1])
    return clip_disk_outer(poly, position, 1500.0)


def contains(poly, point, tolerance=1e-5):
    if len(poly) < 3:
        return any(math.dist(p, point) <= tolerance for p in poly)
    return all(cross(sub(poly[(i + 1) % len(poly)], a), sub(point, a)) >= -tolerance
               for i, a in enumerate(poly))


def diameter(poly):
    if not poly:
        raise ValueError("Empty localization region")
    best = (0.0, poly[0], poly[0])
    for i, p in enumerate(poly):
        for q in poly[i + 1:]:
            distance = math.dist(p, q)
            if distance > best[0]:
                best = (distance, p, q)
    return best


def _circle(boundary):
    if not boundary:
        return ((0.0, 0.0), -1.0)
    if len(boundary) == 1:
        return (boundary[0], 0.0)
    if len(boundary) == 2:
        a, b = boundary
        center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        return (center, math.dist(a, b) / 2)
    a, b, c = boundary
    bx, by = sub(b, a)
    cx, cy = sub(c, a)
    denominator = 2 * (bx * cy - by * cx)
    if abs(denominator) < 1e-14:
        _, p, q = diameter(boundary)
        return _circle([p, q])
    b2, c2 = bx * bx + by * by, cx * cx + cy * cy
    center = (a[0] + (cy * b2 - by * c2) / denominator,
              a[1] + (bx * c2 - cx * b2) / denominator)
    return (center, math.dist(center, a))


def minimum_circle(points):
    """Welzl with fixed internal permutation, then outward radius verification."""
    if not points:
        raise ValueError("Empty localization region")
    points = list(points)
    random.Random(731).shuffle(points)

    def solve(n, boundary):
        if n == 0 or len(boundary) == 3:
            return _circle(boundary)
        p = points[n - 1]
        center, radius = solve(n - 1, boundary)
        if radius >= 0 and math.dist(p, center) <= radius + 1e-9:
            return center, radius
        return solve(n - 1, boundary + [p])

    center, _ = solve(len(points), [])
    radius = max(math.dist(center, p) for p in points) + 1e-7
    return center, radius


def simple_intersection(first, second):
    p, theta = first
    q, phi = second
    d = (math.cos(math.radians(theta)), math.sin(math.radians(theta)))
    e = (math.cos(math.radians(phi)), math.sin(math.radians(phi)))
    denominator = cross(d, e)
    if abs(denominator) < 1e-8:
        return None
    t = cross(sub(q, p), e) / denominator
    s = cross(sub(q, p), d) / denominator
    if t < 0 or s < 0:
        return None
    return (p[0] + t * d[0], p[1] + t * d[1])


def nearest_safe_point(poly, position, clearing_radius=20.0):
    center, radius = minimum_circle(poly)
    margin = clearing_radius - radius - 1e-5
    if margin < 0:
        return None
    distance = math.dist(position, center)
    if distance <= margin:
        candidate = position
    else:
        candidate = (center[0] + (position[0] - center[0]) * margin / distance,
                     center[1] + (position[1] - center[1]) * margin / distance)
    if max(math.dist(candidate, p) for p in poly) > clearing_radius - 1e-6:
        raise ValueError("Safe clearing point failed vertex verification")
    return candidate




def open_held_karp(start, points, edge_distances=None, start_distances=None):
    """Exact open fixed-point route; it does not claim exact TSPN optimality."""
    from array import array
    n = len(points)
    if not n:
        return [], 0.0
    if n > 16:
        raise ValueError("The documented target count is at most sixteen")
    size = (1 << n) * n
    costs = array("d", [math.inf]) * size
    parents = array("b", [-1]) * size
    distances = edge_distances if edge_distances is not None else [[math.dist(a, b) for b in points] for a in points]
    for j, point in enumerate(points):
        costs[(1 << j) * n + j] = start_distances[j] if start_distances is not None else math.dist(start, point)
    full = (1 << n) - 1
    for mask in range(1, full + 1):
        available = full ^ mask
        active = mask
        while active:
            bit = active & -active
            j = bit.bit_length() - 1
            cost = costs[mask * n + j]
            remaining = available
            while remaining:
                nxt = remaining & -remaining
                k = nxt.bit_length() - 1
                idx = (mask | nxt) * n + k
                value = cost + distances[j][k]
                if value < costs[idx]:
                    costs[idx], parents[idx] = value, j
                remaining ^= nxt
            active ^= bit
    last = min(range(n), key=lambda j: costs[full * n + j])
    length = costs[full * n + last]
    order, mask = [], full
    while last >= 0:
        order.append(last)
        previous = parents[mask * n + last]
        mask ^= 1 << last
        last = previous
    return list(reversed(order)), length
