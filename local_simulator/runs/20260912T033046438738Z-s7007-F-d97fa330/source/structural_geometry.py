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
