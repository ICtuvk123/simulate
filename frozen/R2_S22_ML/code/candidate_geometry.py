"""Canonical convex planning copy for optional M candidate generation.

The returned vertices are a subset of the input vertices. This only removes
representation-dependent ordering and redundant boundary subdivisions before
computing candidate centers and tied diameters. It does not update hard P.
"""
import math


def canonical_candidate_polygon(poly):
    if not poly:return []
    points=sorted(set((float(p[0]),float(p[1])) for p in poly))
    if not all(math.isfinite(v) for p in points for v in p):
        raise ValueError('Candidate polygon contains a non-finite coordinate')
    if len(points)<3:return points
    low=[min(p[k] for p in points) for k in (0,1)]
    high=[max(p[k] for p in points) for k in (0,1)]
    span=max(high[k]-low[k] for k in (0,1))
    if not math.isfinite(span):raise ValueError('Candidate polygon span overflows')
    if span==0:return points[:1]
    center=[low[k]+(high[k]-low[k])/2 for k in (0,1)]
    normalized={p:tuple((p[k]-center[k])/span for k in (0,1)) for p in points}
    def cross(a,b,c):
        a,b,c=normalized[a],normalized[b],normalized[c]
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def half(sequence):
        out=[]
        for p in sequence:
            while len(out)>1 and cross(out[-2],out[-1],p)<=1e-14:out.pop()
            out.append(p)
        return out
    return half(points)[:-1]+half(reversed(points))[:-1]
