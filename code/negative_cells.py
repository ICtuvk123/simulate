"""Continuous conservative position-cell rejection using all real RF history.

For a cell C, some negative stations are in range for every g in C, either
within the guaranteed 1000 m radius or no farther than a real positive station.
For any possible directional heading a, each positive requires
  max_{v in vertices(C)} a dot (s-v) >= 0,
and each in-range negative requires
  min_{v in vertices(C)} a dot (n-v) <= 0.
These are relaxations allowing a different position vertex per constraint.
If even these relaxed heading sets have empty intersection, the entire cell
is impossible. Closed negative halfplanes and expanded angular intervals keep
emission-boundary positions. Without an in-range negative the omni branch is
retained. No finite position samples are used as a rejection proof.
"""
import math
from geometry import clip
from directional_geometry import hull

TAU=2*math.pi
ANGLE_PAD=1e-9
DISTANCE_PAD=1e-5


def valid_convex_polygon(poly):
    try:
        if len(poly)<3 or len(set(tuple(p) for p in poly))<3:return False
        if any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in poly):return False
        origin=poly[0]
        area2=sum((a[0]-origin[0])*(b[1]-origin[1])-(a[1]-origin[1])*(b[0]-origin[0])
                  for a,b in zip(poly,poly[1:]+poly[:1]))
        if area2<=1e-12:return False
        for a,b in zip(poly,poly[1:]+poly[:1]):
            ex,ey=b[0]-a[0],b[1]-a[1];length=math.hypot(ex,ey)
            if length<=1e-10:return False
            if any(ex*(v[1]-a[1])-ey*(v[0]-a[0])<-1e-8*max(1.,length) for v in poly):return False
        return True
    except (TypeError,ValueError,IndexError):return False


def merge(intervals):
    out=[]
    for lo,hi in sorted(intervals):
        if out and lo<=out[-1][1]+1e-12:out[-1]=(out[-1][0],max(hi,out[-1][1]))
        else:out.append((lo,hi))
    return out


def heading_union(cell,station,negative=False):
    arcs=[]
    for v in cell:
        dx,dy=station[0]-v[0],station[1]-v[1]
        if math.hypot(dx,dy)<1e-7:return [(0.,TAU)]
        center=(math.atan2(dy,dx)+(math.pi if negative else 0.))%TAU
        lo,hi=center-math.pi/2-ANGLE_PAD,center+math.pi/2+ANGLE_PAD
        if lo<0:arcs.extend([(0.,hi),(lo+TAU,TAU)])
        elif hi>TAU:arcs.extend([(lo,TAU),(0.,hi-TAU)])
        else:arcs.append((lo,hi))
    return merge(arcs)


def intersect(left,right):
    return merge([(max(a,c),max(max(a,c),min(b,d))) for a,b in left for c,d in right
                  if max(a,c)<=min(b,d)+1e-12])


def range_witness(cell,negative,positive_stations):
    if max(math.dist(negative,v) for v in cell)<=1000-DISTANCE_PAD:
        return dict(kind='minimum_radius',negative=negative)
    for s in positive_stations:
        # Squared distance difference is affine in the unknown source g.
        worst=max(sum((negative[k]-v[k])**2-(s[k]-v[k])**2 for k in (0,1)) for v in cell)
        if worst<=-DISTANCE_PAD:
            return dict(kind='positive_radius',negative=negative,positive=s)
    return None


def reject_cell(cell,positive_stations,negative_stations):
    witnesses=[w for n in negative_stations if (w:=range_witness(cell,n,positive_stations))]
    if not witnesses:return None  # An omnidirectional source is still possible.
    allowed=[(0.,TAU)]
    for s in positive_stations:
        allowed=intersect(allowed,heading_union(cell,s))
    used=[]
    for w in witnesses:
        used.append(w)
        allowed=intersect(allowed,heading_union(cell,w['negative'],True))
        if not allowed:return dict(range_witnesses=used)
    return None


def partition(poly,axis,count):
    projections=[sum(p[k]*axis[k] for k in (0,1)) for p in poly]
    lo,hi=min(projections),max(projections)
    if hi-lo<1e-7:return [list(poly)]
    cells=[]
    for i in range(count):
        left=lo+(hi-lo)*i/count;right=lo+(hi-lo)*(i+1)/count
        cell=clip(clip(poly,axis,right),tuple(-v for v in axis),-left)
        if cell:cells.append(cell)
    return cells


def contract(poly,positives,negatives,count=24):
    if not poly or not positives or not negatives:return None
    if not valid_convex_polygon(poly):return None
    count=max(1,min(64,int(count)))
    angle=math.radians(positives[0][1]);axis=(math.cos(angle),math.sin(angle))
    positive_stations=[tuple(p) for p,_ in positives]
    negative_stations=sorted(set(tuple(p) for p in negatives))
    cells=partition(poly,axis,count);kept=[];removed=[]
    for index,cell in enumerate(cells):
        proof=reject_cell(cell,positive_stations,negative_stations)
        if proof is None:kept.extend(cell)
        else:removed.append(dict(index=index,cell=cell,**proof))
    if not removed:return None
    if not kept:raise ValueError('All position cells contradicted legal history')
    result=hull(kept)
    if not valid_convex_polygon(result):return None
    # Taking an outer convex hull is safe. Interior holes may be deliberately
    # reintroduced here; unlike optical exclusions these are not marked absent.
    return dict(polygon=result,witness=dict(before_polygon=poly,positives=positives,
                negatives=negative_stations,axis=axis,count=count,removed=removed,
                method='continuous_heading_relaxation_v1',angle_pad=ANGLE_PAD,
                distance_pad=DISTANCE_PAD))


def independently_rejected(cell,positive_stations,range_witnesses):
    """Second heading check via exact sign-change intervals, not grid sampling.

    Each constraint is an OR of homogeneous linear inequalities on the unit
    circle. Its truth value changes only at a vertex-vector perpendicular.
    Test every such boundary and every intervening interval. Added numerical
    slack can only make rejection more difficult.
    """
    negatives=[]
    for w in range_witnesses:
        n=w['negative'];negatives.append(n)
        if w['kind']=='minimum_radius':
            if any(math.dist(n,v)>1000-DISTANCE_PAD+1e-8 for v in cell):return False
        elif w['kind']=='positive_radius':
            s=w['positive']
            if not any(math.dist(s,p)<1e-9 for p in positive_stations):return False
            if any(math.dist(n,v)**2-math.dist(s,v)**2>-DISTANCE_PAD+1e-7 for v in cell):return False
        else:return False
    if not negatives:return False
    constraints=[(False,[(s[0]-v[0],s[1]-v[1]) for v in cell]) for s in positive_stations]
    constraints += [(True,[(n[0]-v[0],n[1]-v[1]) for v in cell]) for n in negatives]
    boundaries={0.}
    for _,vectors in constraints:
        for x,y in vectors:
            if math.hypot(x,y)>1e-12:
                boundaries.update(((math.atan2(y,x)+sign*math.pi/2)%TAU for sign in (-1,1)))
    boundaries=sorted(boundaries)
    candidates=boundaries+[(a+(b-a)%TAU/2)%TAU for a,b in zip(boundaries,boundaries[1:]+boundaries[:1])]
    for angle in candidates:
        a=(math.cos(angle),math.sin(angle));possible=True
        for negative,vectors in constraints:
            dots=[a[0]*x+a[1]*y for x,y in vectors]
            if (min(dots)>1e-6 if negative else max(dots)<-1e-6):
                possible=False;break
        if possible:return False
    return True


def verify_contraction(witness,polygon,positive_history,negative_history):
    try:
        if witness['method']!='continuous_heading_relaxation_v1':return False
        if not valid_convex_polygon(witness['before_polygon']) or not valid_convex_polygon(polygon):return False
        positives=witness['positives'];negatives=witness['negatives']
        if not positives or not negatives:return False
        for s,beta in positives:
            if not any(math.dist(s,p)<1e-9 and beta==b for p,b in positive_history):return False
        for n in negatives:
            if not any(math.dist(n,p)<1e-9 for p in negative_history):return False
        axis=witness['axis']
        if abs(math.hypot(*axis)-1)>1e-10 or not 1<=witness['count']<=64:return False
        cells=partition(witness['before_polygon'],axis,witness['count'])
        removed={r['index']:r for r in witness['removed']}
        if len(removed)!=len(witness['removed']) or any(i<0 or i>=len(cells) for i in removed):return False
        retained=[]
        for index,cell in enumerate(cells):
            if index not in removed:retained.extend(cell);continue
            proof=removed[index]
            if len(proof['cell'])!=len(cell) or any(math.dist(a,b)>1e-7 for a,b in zip(proof['cell'],cell)):return False
            for w in proof['range_witnesses']:
                if not any(math.dist(w['negative'],n)<1e-9 for n in negatives):return False
            if not independently_rejected(cell,[s for s,_ in positives],proof['range_witnesses']):return False
        if not retained:return False
        # Check every retained vertex lies in the reported convex output;
        # numerical slack is in length units, normalized per polygon edge.
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            ex,ey=b[0]-a[0],b[1]-a[1]
            if any(ex*(v[1]-a[1])-ey*(v[0]-a[0])<-1e-6*max(1.,math.hypot(ex,ey)) for v in retained):return False
        return len(polygon)>=3
    except (KeyError,TypeError,ValueError,ZeroDivisionError):return False
