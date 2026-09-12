"""Q2 operating regions and limited one-step time rollouts, no environment I/O."""
import math

from geometry import minimum_circle


def nearest_operating_point(poly, p, radius=20.0):
    """Project onto the intersection of vertex-centered clearing disks.

    Candidate boundaries are a single circle or two circles' intersections.
    Every returned point is rechecked against all polygon vertices.
    """
    r = radius-1e-5
    def feasible(q):
        return all(math.dist(q,v) <= r+1e-8 for v in poly)
    if feasible(p):
        return p
    center, bound = minimum_circle(poly)
    if bound > r+1e-7:
        return None
    candidates = [center] if feasible(center) else []
    for v in poly:
        d = math.dist(p,v)
        if d > 1e-12:
            q = (v[0]+r*(p[0]-v[0])/d,v[1]+r*(p[1]-v[1])/d)
            if feasible(q):
                candidates.append(q)
    for i,a in enumerate(poly):
        for b in poly[i+1:]:
            d = math.dist(a,b)
            if not 1e-10 < d <= 2*r:
                continue
            h = math.sqrt(max(0.0,r*r-d*d/4))
            mid = ((a[0]+b[0])/2,(a[1]+b[1])/2)
            for sign in (-1,1):
                q = (mid[0]-sign*h*(b[1]-a[1])/d,mid[1]+sign*h*(b[0]-a[0])/d)
                if feasible(q):
                    candidates.append(q)
    return min(candidates,key=lambda q:math.dist(p,q)) if candidates else None


