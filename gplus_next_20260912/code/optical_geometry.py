"""Certified two-stop optical covers and geometry-only cost estimates.

The coverage certificate is deterministic: remove an INSCRIBED polygon from
the first optical disk, and cover every vertex of every remaining convex piece
with the second disk.  Area fractions only rank plans; they never certify them.
No simulator, source coordinate, seed, or external I/O is used here.
"""
import math

from geometry import clip, diameter, minimum_circle
from local_geometry import nearest_operating_point
from structural_geometry import convex_hull, exclude_inner_disk


def polygon_area(poly):
    if len(poly) < 3:
        return 0.0
    # Translating first avoids cancellation for small polygons far from origin.
    origin = poly[0]
    return abs(sum((a[0]-origin[0])*(b[1]-origin[1])
                   - (a[1]-origin[1])*(b[0]-origin[0])
                   for a, b in zip(poly, poly[1:]+poly[:1]))) / 2


def disk_intersection_area(poly, center, radius=20.0):
    """Analytic polygon/disk intersection area (segments plus circular arcs)."""
    area = 0.0
    r2 = radius*radius
    for start, end in zip(poly, poly[1:]+poly[:1]):
        a = (start[0]-center[0], start[1]-center[1])
        b = (end[0]-center[0], end[1]-center[1])
        d = (b[0]-a[0], b[1]-a[1])
        aa = d[0]*d[0]+d[1]*d[1]
        cuts = [0.0, 1.0]
        if aa > 1e-24:
            bb = 2*(a[0]*d[0]+a[1]*d[1])
            cc = a[0]*a[0]+a[1]*a[1]-r2
            discriminant = bb*bb-4*aa*cc
            if discriminant > 0:
                root = math.sqrt(discriminant)
                cuts.extend(t for t in ((-bb-root)/(2*aa), (-bb+root)/(2*aa))
                            if 0 < t < 1)
        cuts.sort()
        for lo, hi in zip(cuts, cuts[1:]):
            u = (a[0]+lo*d[0], a[1]+lo*d[1])
            v = (a[0]+hi*d[0], a[1]+hi*d[1])
            middle = ((u[0]+v[0])/2, (u[1]+v[1])/2)
            cross = u[0]*v[1]-u[1]*v[0]
            if middle[0]**2+middle[1]**2 <= r2:
                area += cross/2
            else:
                area += r2*math.atan2(cross, u[0]*v[0]+u[1]*v[1])/2
    return max(0.0, min(polygon_area(poly), abs(area)))


def disk_coverage_fraction(pieces, center, radius=20.0):
    """Area fraction under a uniform-region ranking heuristic, not a posterior."""
    denominator = sum(polygon_area(piece) for piece in pieces)
    if denominator <= 1e-12:
        points = [p for piece in pieces for p in piece]
        return sum(math.dist(p, center) <= radius for p in points)/max(1, len(points))
    numerator = sum(disk_intersection_area(piece, center, radius) for piece in pieces)
    return max(0.0, min(1.0, numerator/denominator))


def certified_second_point(pieces, first, radius=20.0, sides=48):
    """Return a conservative residual and a guaranteed second clearing point.

    After accepted failure the true source lies outside the CLOSED first disk.
    exclude_inner_disk removes only an inscribed polygon strictly inside that
    disk.  Its returned pieces therefore contain the entire true residual.
    A disk is convex, so checking all their vertices proves full coverage.
    """
    residual = exclude_inner_disk(pieces, first, radius=radius, sides=sides)
    if not residual:
        return None
    vertices = [v for piece in residual for v in piece]
    hull = convex_hull(vertices)
    second = nearest_operating_point(hull, first, radius=radius)
    if second is None:
        return None
    maximum = max(math.dist(second, v) for v in vertices)
    if maximum > radius-1e-6:
        return None
    return dict(first=tuple(first), second=tuple(second), residual=residual,
                second_max_distance=maximum, exclusion_sides=sides,
                certificate='inscribed_first_disk_exclusion_then_all_residual_vertices')


def first_point_candidates(pieces, current, radius=20.0):
    """Generate optical points from certified end caps of the major axis."""
    hull = convex_hull([v for piece in pieces for v in piece])
    center, _ = minimum_circle(hull)
    points = [tuple(current), center]
    length, a, b = diameter(hull)
    if length <= 1e-10:
        return points
    direction = ((b[0]-a[0])/length, (b[1]-a[1])/length)
    projections = [direction[0]*v[0]+direction[1]*v[1] for v in hull]
    lower, upper = min(projections), max(projections)
    for fraction in (.25, .375, .5, .625, .75):
        threshold = lower+fraction*(upper-lower)
        for sign in (-1, 1):
            cap = clip(hull, (sign*direction[0], sign*direction[1]), sign*threshold)
            if not cap:
                continue
            nearest = nearest_operating_point(cap, current, radius=radius)
            if nearest is not None:
                points.append(nearest)
                cap_center, cap_radius = minimum_circle(cap)
                if cap_radius < radius-1e-5:
                    points.append(cap_center)
    unique = []
    for point in points:
        if not any(math.dist(point, old) < 1e-5 for old in unique):
            unique.append(point)
    return unique


def sequential_optical_plan(pieces, current, risk=.15, tail=None,
                            tail_weight=0.0, radius=20.0):
    """Select a certified plan by movement, success/failure cost, optional exit.

    For hit fraction h: expected = d(p,q1)/5 + 5 + (1-h)*(3+d(q1,q2)/5).
    The risk mix interpolates this area heuristic and the worst branch cost.
    Neither the hit fraction nor the risk mix is a completion guarantee.
    """
    best = None
    for first in first_point_candidates(pieces, current, radius):
        plan = certified_second_point(pieces, first, radius=radius)
        if plan is None:
            continue
        second = plan['second']
        fraction = disk_coverage_fraction(pieces, first, radius)
        common = math.dist(current, first)/5
        success = common+5
        failure = common+3+math.dist(first, second)/5+5
        if tail is not None and tail_weight:
            success += tail_weight*math.dist(first, tail)/5
            failure += tail_weight*math.dist(second, tail)/5
        expected = fraction*success+(1-fraction)*failure
        worst = max(success, failure)
        score = (1-risk)*expected+risk*worst
        if best is None or score < best['estimated_remaining_s']:
            best = dict(plan, estimated_remaining_s=score,
                        expected_area_cost_s=expected, worst_branch_cost_s=worst,
                        first_coverage_area_fraction=fraction,
                        area_fraction_is_ranking_only=True, optical_sequence_risk=risk)
    return best
