"""Q4 geometry. A single negative never excludes a disk or a halfplane."""
import math
import time
from geometry import clip, cross, sub

ALPHA = math.radians(1.01)
MARGIN = 1e-5


def hull(points):
    points = sorted(set(tuple(p) for p in points))
    if len(points) < 3:
        return points
    def half(seq):
        out = []
        for p in seq:
            while len(out) > 1 and cross(sub(out[-1], out[-2]), sub(p, out[-1])) <= 0:
                out.pop()
            out.append(p)
        return out
    return half(points)[:-1] + half(points[::-1])[:-1]


def in_hull(poly, point, margin=0.):
    if len(poly) == 0:
        return False
    if len(poly) == 1:
        return math.dist(poly[0], point) <= 1e-10 and margin == 0
    if len(poly) == 2:
        a,b = poly
        return (margin == 0 and abs(cross(sub(b,a), sub(point,a))) <= 1e-9
                and sum((point[k]-a[k])*(point[k]-b[k]) for k in (0,1)) <= 0)
    return all(cross(sub(b,a), sub(point,a)) >= margin*math.dist(a,b)
               for a,b in zip(poly,poly[1:]+poly[:1]))


def skeleton(inner_count=8, outer_count=16, inner_radius=995., outer_radius=1840.,
             inner_phase=0., outer_phase=0.):
    return [(0.,0.)] + [(r*math.cos(phase+2*math.pi*k/n),r*math.sin(phase+2*math.pi*k/n))
                        for r,n,phase in [(inner_radius,inner_count,math.radians(inner_phase)),
                                          (outer_radius,outer_count,math.radians(outer_phase))]
                        for k in range(n)]


def corners(box):
    x0,y0,x1,y1=box
    return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]


def box_distance(p,box):
    x0,y0,x1,y1=box
    return math.hypot(max(x0-p[0],0,p[0]-x1),max(y0-p[1],0,p[1]-y1))


class DirectionalCoverage:
    """Memoized continuous local-hull certificate with monotone leaf reuse.

    Every accepted cell uses ONLY stations within 1000-margin of ALL corners.
    A prior negative result stores pending cells; a superset resumes these cells.
    Budgets or uncertain cells never count as covered.
    """
    def __init__(self, max_depth=13, max_cells=250000, time_budget=3.):
        self.max_depth=max_depth;self.max_cells=max_cells;self.time_budget=time_budget
        self.cache={};self.calls=0;self.hits=0

    def prove(self, stations):
        key=frozenset(tuple(p) for p in stations)
        self.calls+=1
        if key in self.cache:
            self.hits+=1
            return self.cache[key]['result']
        inherited=None
        for old,entry in self.cache.items():
            if old < key and (inherited is None or len(old)>inherited[0]):
                if entry['result']['complete']:
                    result=dict(entry['result'],station_count=len(key),inherited=True)
                    self.cache[key]={'result':result,'pending':[]}
                    return result
                inherited=(len(old),entry)
        pending=(list(inherited[1]['pending']) if inherited else [((-1800.,-1800.,1800.,1800.),0)])
        points=sorted(key);visited=0;certified=0;left=[];start=time.monotonic();cause=None
        while pending:
            box,depth=pending.pop();visited+=1
            if visited>self.max_cells or time.monotonic()-start>self.time_budget:
                left.append((box,depth));left.extend(pending);cause='budget';break
            if box_distance((0,0),box)>1800+MARGIN:
                continue
            cs=corners(box)
            near=[p for p in points if max((p[0]-x)**2+(p[1]-y)**2 for x,y in cs)<=(1000-MARGIN)**2]
            h=hull(near)
            if len(h)>=3 and all(in_hull(h,p,1e-8) for p in cs):
                certified+=1;continue
            x0,y0,x1,y1=box;mid=((x0+x1)/2,(y0+y1)/2)
            # An actual uncovered interior point is an early rejection, not acceptance.
            if math.hypot(*mid)<=1800 and not in_hull(hull([p for p in points if math.dist(p,mid)<=1000]),mid):
                left.append((box,depth));left.extend(pending);cause='uncovered_witness';break
            if depth>=self.max_depth:
                left.append((box,depth));left.extend(pending);cause='depth';break
            x,y=mid
            pending.extend((child,depth+1) for child in [(x0,y0,x,y),(x,y0,x1,y),(x,y,x1,y1),(x0,y,x,y1)])
        result=dict(complete=not left,station_count=len(key),visited_cells=visited,
                    certified_cells=certified,unresolved_cells=len(left),reason=cause,
                    max_depth=self.max_depth,margin=MARGIN,kind='q4_local_hull_cells')
        self.cache[key]={'result':result,'pending':left}
        return result


def paired_probe(poly, station, bearing, b=80., fraction=.5, narrow_probe=False):
    a=math.radians(bearing);d=(math.cos(a),math.sin(a));n=(-d[1],d[0])
    projections=[sum((v[k]-station[k])*d[k] for k in (0,1)) for v in poly]
    l,u=min(projections),max(projections);t=l+fraction*(u-l)
    q=[tuple(station[k]+t*d[k]+sign*b*n[k] for k in (0,1)) for sign in (1,-1)]
    tau=math.tan(ALPHA)
    spanning=(t>=0 and b>=t*tau+MARGIN)
    uniform_radius=(spanning and all(math.dist(p,v)<=1000-MARGIN for p in q for v in poly))
    # The first real positive proves R >= |g-station|. For x>=t in that
    # bearing sector, each endpoint is closer whenever this squared gap is
    # positive. Only the far side needs this bound; near-side range may fail.
    gap=t*t-b*b-2*t*b*tau
    positive_radius=(narrow_probe and spanning and t>0 and gap>=MARGIN)
    valid=uniform_radius or positive_radius
    return dict(station=tuple(station),bearing=bearing,d=d,n=n,l=l,u=u,t=t,b=b,
                plus=q[0],minus=q[1],geometry_valid=valid,
                radius_witness=('positive_station_radius' if positive_radius else 'minimum_radius_all_region'),
                positive_radius_gap_sq_m2=gap,alpha_rad=ALPHA,geometry_margin=MARGIN)


def verify_paired_geometry(poly,witness):
    """Recompute a geometry witness; the serialized valid flag is not proof.

    This checks geometry only. Actual positive/two negative response provenance
    is enforced by the controller and independently checked after the run.
    """
    try:
        s=witness['station'];a=math.radians(witness['bearing'])
        d=(math.cos(a),math.sin(a));n=(-d[1],d[0]);t=witness['t'];b=witness['b']
        if not poly or not all(math.isfinite(v) for v in [*s,a,t,b]):return False
        if not (t>=0 and b>=t*math.tan(ALPHA)+MARGIN):return False
        if any(math.dist(witness[k],v)>1e-9 for k,v in [('d',d),('n',n)]):return False
        ends=[tuple(s[k]+t*d[k]+sign*b*n[k] for k in (0,1)) for sign in (1,-1)]
        if any(math.dist(witness[k],v)>1e-8 for k,v in zip(('plus','minus'),ends)):return False
        kind=witness.get('radius_witness','minimum_radius_all_region')
        if kind=='positive_station_radius':
            return t>0 and t*t-b*b-2*t*b*math.tan(ALPHA)>=MARGIN
        if kind=='minimum_radius_all_region':
            return all(math.dist(q,v)<=1000-MARGIN for q in ends for v in poly)
        return False
    except (KeyError,ValueError,TypeError,OverflowError):return False


def apply_paired_negative(poly,witness):
    if (not witness.get('geometry_valid') or witness.get('results')!=['no_signal','no_signal']
        or not verify_paired_geometry(poly,witness)):
        raise ValueError('Two actual negative responses and valid geometry required')
    d=witness['d'];s=witness['station'];t=witness['t']
    return clip(poly,d,sum(d[k]*s[k] for k in (0,1))+t)


def positive_hull_reception(q, positive_stations):
    # Fixed radius and emitting halfplane are convex in station position.
    return in_hull(hull(positive_stations),q)


def optical_strip(station,bearing):
    a=math.radians(bearing);c,s=math.cos(a),math.sin(a)
    return [(station[0]+x*c-y*s,station[1]+x*s+y*c)
            for y in (-25.,0.,25.) for x in (25.*k for k in range(61))]
