"""Area quadrature depending on a convex region, not its vertex encoding.

This module only supplies finite planning hypotheses. It never updates the
hard position region or certifies clearing, reception, or an empty channel.
CDF integration is exact for the piecewise-linear section lengths of the
canonical convex polygon; the finite along-section samples remain a heuristic.
"""
import math


def _cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _hull(points):
    """Canonical CCW hull in translated, unit-scale coordinates.

    Removing tiny outward collinear deviations drops vertices only from a
    planning copy. Its convex hull stays inside the convex hull of the input.
    """
    points=sorted(set(points))
    if len(points)<3:return points
    def half(seq):
        out=[]
        for p in seq:
            while len(out)>1 and _cross(out[-2],out[-1],p)<=1e-14:out.pop()
            out.append(p)
        return out
    return half(points)[:-1]+half(points[::-1])[:-1]


def _section(poly,u):
    values=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        lo,hi=sorted((a[0],b[0]))
        if u<lo-1e-14 or u>hi+1e-14:continue
        width=b[0]-a[0]
        if abs(width)<=1e-15:
            if abs(u-a[0])<=1e-14:values.extend((a[1],b[1]))
        else:
            fraction=max(0.,min(1.,(u-a[0])/width))
            values.append(a[1]+fraction*(b[1]-a[1]))
    return (min(values),max(values)) if values else None


def _section_fraction(i,count):
    """Antithetic golden-ratio sequence, compatible with reversing both axes."""
    if 2*i==count-1:return .5
    j=min(i,count-1-i)
    value=(.5+(j+1)*.6180339887498949)%1.
    return value if 2*i<count-1 else 1.-value


def stable_quadrature(poly,count=9):
    """Return deterministic area-stratified points within convex ``poly``.

    Cyclic/reversed vertices, duplicated vertices and collinear subdivisions
    do not change the integration. Translation is removed before arithmetic.
    The longer axis-aligned bounding-box side selects the integration axis;
    an almost-square box deterministically uses x. Rotations which carry this
    selected axis into the new selected axis preserve the point set (possibly
    reversing order); arbitrary rotations need not preserve a fixed-axis rule.

    Zero-area polygons use interior segment quantiles, a point uses itself,
    and invalid/empty inputs return no ranking models. No success is inferred
    from this finite set or from its degenerate fallback.
    """
    if count<=0 or not poly:return []
    points=[(float(p[0]),float(p[1])) for p in poly]
    if not all(math.isfinite(v) for p in points for v in p):return []
    lo=[min(p[k] for p in points) for k in (0,1)]
    hi=[max(p[k] for p in points) for k in (0,1)]
    span=[hi[k]-lo[k] for k in (0,1)]
    scale=max(span)
    if not math.isfinite(scale):return []
    if scale==0:return [points[0]]
    origin=tuple(lo[k]+span[k]/2 for k in (0,1))
    normalized=[tuple((p[k]-origin[k])/scale for k in (0,1)) for p in points]
    boundary=_hull(normalized)
    y_axis=span[1]>span[0]*(1.+2e-12)
    transformed=[(p[1],-p[0]) if y_axis else p for p in boundary]
    def restore(p):
        q=(-p[1],p[0]) if y_axis else p
        return tuple(origin[k]+scale*q[k] for k in (0,1))
    if len(boundary)<3:
        a,b=min(transformed),max(transformed)
        return [restore(tuple(a[k]+(b[k]-a[k])*(i+.5)/count for k in (0,1))) for i in range(count)]
    breaks=sorted(set(p[0] for p in transformed))
    segments=[]
    for a,b in zip(breaks,breaks[1:]):
        if b-a<=1e-15:continue
        sa,sb=_section(transformed,a),_section(transformed,b)
        if sa is None or sb is None:continue
        left=max(0.,sa[1]-sa[0]);right=max(0.,sb[1]-sb[0])
        area=(b-a)*(left+right)/2
        if area>0:segments.append((a,b,left,right,area))
    total=math.fsum(s[4] for s in segments)
    if total<=1e-26:
        a,b=min(transformed),max(transformed)
        return [restore(tuple(a[k]+(b[k]-a[k])*(i+.5)/count for k in (0,1))) for i in range(count)]
    ends=[];partial=[]
    for segment in segments:
        partial.append(segment[4]);ends.append(math.fsum(partial))
    out=[]
    for i in range(count):
        target=total*(i+.5)/count
        index=next((j for j,end in enumerate(ends) if end>=target),len(segments)-1)
        a,b,left,right,area=segments[index]
        delta=max(0.,min(area,target-(ends[index-1] if index else 0.)))
        reduced=delta/(b-a)
        root=math.sqrt(max(0.,left*left+2*(right-left)*reduced))
        denominator=left+root
        fraction=2*reduced/denominator if denominator>0 else .5
        u=a+(b-a)*max(0.,min(1.,fraction))
        section=_section(transformed,u)
        if section is None:return []
        v=section[0]+(section[1]-section[0])*_section_fraction(i,count)
        out.append(restore((u,v)))
    return out
