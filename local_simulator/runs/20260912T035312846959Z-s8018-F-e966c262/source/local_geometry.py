"""Q2 operating regions and limited one-step time rollouts, no environment I/O."""
import math

from geometry import minimum_circle, diameter, clip_bearing


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


def time_rollout_station(poly, current, previous):
    """Finite Q/G/error quadrature for ranking actions, NOT a probability/proof.

    The real observation always updates the full conservative polygon; sampled
    success never authorizes clearing. All stations preserve robust reception.
    """
    center, radius = minimum_circle(poly)
    _, a, b = diameter(poly)
    d = max(math.dist(a,b),1e-10)
    normal = (-(b[1]-a[1])/d,(b[0]-a[0])/d)
    candidates = []
    for offset in (15,30,60,100):
        for sign in (-1,1):
            candidates.append((center[0]+sign*offset*normal[0],center[1]+sign*offset*normal[1]))
    travel = math.dist(current,center)
    if travel > 1e-8:
        for distance in (40,100,200,400):
            if distance < travel:
                candidates.append((center[0]+(current[0]-center[0])*distance/travel,
                                   center[1]+(current[1]-center[1])*distance/travel))
    vertices = poly[::max(1,len(poly)//6)]
    scenarios = [center]+[((p[0]+center[0])/2,(p[1]+center[1])/2) for p in vertices]
    best = None
    for q in candidates:
        if any(math.dist(q,p)<.05 for p in previous):
            continue
        if max(math.dist(q,p) for p in poly) > 1000-1e-4:
            continue
        totals, radii, successes = [], [], 0
        for source in scenarios:
            if math.dist(q,source)<=5:
                totals.append(5)
                radii.append(0)
                successes += 1
                continue
            worst, worst_radius = 0, 0
            for error in (-1.005,0,1.005):
                beta = math.degrees(math.atan2(source[1]-q[1],source[0]-q[0]))+error
                updated = clip_bearing(poly,q,beta)
                if not updated:
                    continue
                c, r = minimum_circle(updated)
                remainder = math.dist(q,c)/5+5
                if r>20:
                    remainder += 6+min(160,2*r)/5
                worst = max(worst,remainder)
                worst_radius = max(worst_radius,r)
            totals.append(worst)
            radii.append(worst_radius)
            successes += int(worst_radius<=20)
        score = math.dist(current,q)/5+6+sum(totals)/len(totals)
        entry = (score,-successes,max(radii),q)
        if best is None or entry<best:
            best = entry
    if best is None:
        return None
    return dict(point=best[3],estimated_remaining_s=best[0],
                geometric_success_fraction=-best[1]/len(scenarios),sampled_worst_radius=best[2])
