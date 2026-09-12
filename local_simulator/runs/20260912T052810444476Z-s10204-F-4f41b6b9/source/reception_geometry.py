"""Continuous sufficient reception certificate from earlier positive bearings."""
import math

from geometry import clip


def reception_safe(poly,q,positive_stations):
    """Certify |q-g| <= max(1000, |s-g|) for every feasible g, for some s.

    On the half-plane where q is farther than s, the clipped polygon must be
    inside B(q,1000). Its vertex maximum certifies the whole convex intersection.
    Elsewhere prior positive reception at s suffices. No sampling is used.
    Testing each s separately is sufficient, potentially conservative for many s.
    """
    if not poly:
        return False
    if max(math.dist(q,v) for v in poly)<1000-1e-5:
        return True
    for s in positive_stations:
        normal=(2*(q[0]-s[0]),2*(q[1]-s[1]))
        bound=q[0]**2+q[1]**2-s[0]**2-s[1]**2
        # clip expands outward, conservatively including the equality boundary.
        dangerous=clip(poly,normal,bound)
        if not dangerous or max(math.dist(q,v) for v in dangerous)<1000-1e-5:
            return True
    return False
