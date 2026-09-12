"""Geometry for structural F experiments; public observations only."""
import math
from geometry import clip, cross, sub


def convex_hull(points):
    points=sorted(set(tuple(p) for p in points))
    if len(points)<=2:
        return points
    def half(seq):
        out=[]
        for p in seq:
            while len(out)>1 and cross(sub(out[-1],out[-2]),sub(p,out[-1]))<=0:
                out.pop()
            out.append(p)
        return out
    return half(points)[:-1]+half(points[::-1])[:-1]


def positive_negative_clip(poly,positives,negatives):
    for s in positives:
        for n in negatives:
            normal=(2*(n[0]-s[0]),2*(n[1]-s[1]))
            bound=n[0]**2+n[1]**2-s[0]**2-s[1]**2
            poly=clip(poly,normal,bound)
            if not poly:
                return []
    return poly


def joint_reception_safe(poly,q,positives):
    if not poly:
        return False
    danger=poly
    for s in positives:
        normal=(2*(q[0]-s[0]),2*(q[1]-s[1]))
        bound=q[0]**2+q[1]**2-s[0]**2-s[1]**2
        danger=clip(danger,normal,bound)
        if not danger:
            return True
    return max(math.dist(q,v) for v in danger)<1000-1e-5


def exclude_inner_disk(pieces,center,radius=20.,sides=24):
    """Retain a union outside an INSCRIBED polygon, hence outer-approximate
    exclusion of the disk. Both sides of split keep outward numeric tolerance.
    An interior hole is retained in the pieces, never silently filled in state.
    """
    apothem=(radius-1e-5)*math.cos(math.pi/sides)
    result=[]
    for piece in pieces:
        if all(math.dist(center,v)<apothem-1e-6 for v in piece):
            continue
        # Cheap outside test before creating disjoint convex pieces.
        x0=min(p[0] for p in piece);x1=max(p[0] for p in piece)
        y0=min(p[1] for p in piece);y1=max(p[1] for p in piece)
        if math.hypot(max(x0-center[0],0,center[0]-x1),
                      max(y0-center[1],0,center[1]-y1))>radius:
            result.append(piece);continue
        remainder=piece
        for i in range(sides):
            angle=(i+.5)*2*math.pi/sides
            n=(math.cos(angle),math.sin(angle))
            b=n[0]*center[0]+n[1]*center[1]+apothem
            outside=clip(remainder,(-n[0],-n[1]),-b)
            if outside:
                result.append(outside)
            remainder=clip(remainder,n,b)
            if not remainder:
                break
    return result


def bearing_strip_grid(station,bearing_deg):
    """183 points cover the 1500 m / +/-1.01 degree positive-bearing strip."""
    angle=math.radians(bearing_deg);c=math.cos(angle);s=math.sin(angle)
    return [(station[0]+x*c-y*s,station[1]+x*s+y*c)
            for row,y in enumerate((-25.,0.,25.))
            for x in ([25.*k for k in range(61)] if row%2==0 else [25.*k for k in range(60,-1,-1)])]


def through_operating_point(poly,p,b):
    """Feasible convex projected search for entry+exit length; baseline included.
    A line segment intersecting all disks gives exact zero-detour positioning.
    Otherwise retain the best feasible iterate, without claiming exact SOCP.
    """
    from local_geometry import nearest_operating_point
    initial=nearest_operating_point(poly,p)
    if initial is None or b is None:
        return initial
    radius=20-1e-5;d=(b[0]-p[0],b[1]-p[1]);a=d[0]**2+d[1]**2
    if a>1e-14:
        lo,hi=0.,1.
        for v in poly:
            z=(p[0]-v[0],p[1]-v[1]);bd=2*(z[0]*d[0]+z[1]*d[1])
            c=z[0]**2+z[1]**2-radius**2;disc=bd**2-4*a*c
            if disc<0:
                lo,hi=1.,0.;break
            root=math.sqrt(disc);lo=max(lo,(-bd-root)/(2*a));hi=min(hi,(-bd+root)/(2*a))
        if lo<=hi:
            q=(p[0]+(lo+hi)/2*d[0],p[1]+(lo+hi)/2*d[1])
            if all(math.dist(q,v)<=radius+1e-8 for v in poly):
                return q
    def cost(q):return math.dist(p,q)+math.dist(q,b)
    q=initial;best=cost(q)
    for _ in range(18):
        dp=max(math.dist(p,q),1e-9);db=max(math.dist(b,q),1e-9)
        gradient=tuple((q[k]-p[k])/dp+(q[k]-b[k])/db for k in (0,1))
        improved=False
        for step in (20.,5.,1.):
            candidate=nearest_operating_point(poly,tuple(q[k]-step*gradient[k] for k in (0,1)))
            value=cost(candidate)
            if value<best-1e-7:
                q,best=candidate,value;improved=True;break
        if not improved:break
    return q
