"""Conservative adaptive coverage certificates; no sampled-point completion rule."""
import math


def box_distance(point, box):
    x0, y0, x1, y1 = box
    return math.hypot(max(x0 - point[0], 0, point[0] - x1),
                      max(y0 - point[1], 0, point[1] - y1))


def coverage_partition(stations, max_depth=10):
    """Every accepted square is contained in a 1000 m reception disk.

    A square is discarded outside the target disk only using its *minimum*
    distance. Any undecidable square remains a hole, including boundary slivers.
    This may fail to certify genuine coverage, but never certifies by sampling.
    """
    stations = list(stations)
    stack = [((-1800.0, -1800.0, 1800.0, 1800.0), 0)]
    holes, covered, outside = [], 0, 0
    while stack:
        box, depth = stack.pop()
        if box_distance((0, 0), box) > 1800.0 + 1e-6:
            outside += 1
            continue
        x0, y0, x1, y1 = box
        if any(max(abs(x0 - x), abs(x1 - x)) ** 2
               + max(abs(y0 - y), abs(y1 - y)) ** 2 < (1000.0 - 1e-5) ** 2
               for x, y in stations):
            covered += 1
            continue
        # A wholly uncovered box needs no further subdivision to witness a gap.
        if depth >= max_depth or all(box_distance(p, box) > 1000 for p in stations):
            holes.append(box)
            continue
        x, y = (x0 + x1) / 2, (y0 + y1) / 2
        stack.extend(((child, depth + 1) for child in
                      ((x0, y0, x, y), (x, y0, x1, y),
                       (x0, y, x, y1), (x, y, x1, y1))))
    return {"complete": not holes, "holes": holes, "certified_cells": covered,
            "outside_cells": outside, "max_depth": max_depth,
            "kind": "adaptive_quadtree_square_containment",
            "reception_radius": 1000, "target_radius": 1800}


def hole_candidates(partition, limit=12):
    result = []
    for x0, y0, x1, y1 in sorted(partition["holes"],
                                 key=lambda b: -(b[2] - b[0]) * (b[3] - b[1])):
        p = ((x0 + x1) / 2, (y0 + y1) / 2)
        r = math.hypot(*p)
        if r > 1750:
            p = (1750 * p[0] / r, 1750 * p[1] / r)
        if all(math.dist(p, old) > 300 for old in result):
            result.append(p)
        if len(result) >= limit:
            break
    return result


def validate_completion(events, certificate):
    """Reconstruct proof from accepted feedback, independently of policy claims."""
    if not certificate or not events or events[-1]["path"] != "/exit":
        return False, "no completed run with a certificate"
    cleared = {e["channel"] for e in events
               if e["path"] == "/clear" and e["result"] == "success"}
    if not 10 <= len(cleared) <= 16:
        return False, "cleared count outside public range"
    empty = set(range(1, 21)) - cleared
    if (set(certificate.get("cleared_channels", [])) != cleared
            or set(certificate.get("empty_channels", [])) != empty):
        return False, "certificate channel partition disagrees with accepted actions"
    points = {}
    for ch in empty:
        ch_events = [e for e in events if e["path"] == "/measure" and e["channel"] == ch]
        if any(e["result"] != "no_signal" for e in ch_events):
            return False, "observed source left uncleared"
        points[ch] = [e["position"] for e in ch_events]
    if certificate.get("kind") == "analytic_center_ring":
        from geometry import regular_fallback
        try:
            required, _ = regular_fallback(certificate["ring_radius"], certificate["ring_count"])
        except (ValueError, KeyError, TypeError):
            return False, "invalid analytic ring"
        valid = all(all(any(math.dist(p, q) < 1e-8 for p in points[ch])
                        for q in required) for ch in empty)
    elif certificate.get("kind") == "adaptive_quadtree_square_containment":
        # Recompute each channel's coverage from its actual no-signal replies.
        valid = all(coverage_partition(points[ch], 12)["complete"] for ch in empty)
    else:
        return False, "unknown proof kind"
    return valid, "verified_from_accepted_observations" if valid else "unproved search gap"
