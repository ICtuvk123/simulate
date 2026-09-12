"""Isolated route and operating-region reuse; no Q3 controller import."""

import math

from geometry import open_held_karp

from local_geometry import nearest_operating_point

def route_length(start, points, order):
    return sum(math.dist(a, b) for a, b in zip([start]+[points[i] for i in order],
                                               [points[i] for i in order]))

def open_route(start, points):
    """Multiple-start nearest-neighbor and open 2-opt; heuristic for large n."""
    n = len(points)
    if n <= 9:
        return open_held_karp(start, points)[0]
    distance = [[math.dist(a, b) for b in points] for a in points]
    initial = [math.dist(start, p) for p in points]
    best = None
    for first in sorted(range(n), key=lambda i: initial[i])[:min(n, 5)]:
        order, left = [first], set(range(n)) - {first}
        while left:
            selected = min(left, key=lambda i: (distance[order[-1]][i], i))
            order.append(selected)
            left.remove(selected)
        for iteration in range(30):
            improvement, pair = 1e-6, None
            for i in range(n-1):
                for j in range(i+1, n):
                    old = initial[order[i]] if i == 0 else distance[order[i-1]][order[i]]
                    new = initial[order[j]] if i == 0 else distance[order[i-1]][order[j]]
                    if j+1 < n:
                        old += distance[order[j]][order[j+1]]
                        new += distance[order[i]][order[j+1]]
                    if old-new > improvement:
                        improvement, pair = old-new, (i, j)
            if pair is None:
                break
            i, j = pair
            order[i:j+1] = reversed(order[i:j+1])
        candidate = (route_length(start, points, order), order)
        if best is None or candidate < best:
            best = candidate
    return best[1]

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


def refined_open_route(start, points):
    """Improve the existing open route by relocating one or two adjacent stops.

    This only ranks planned stops. Every accepted change shortens the same
    full open route, and no return-to-origin edge is introduced.
    """
    order=list(open_route(start,points));n=len(order)
    if n<=9:return order
    for _ in range(12):
        old=route_length(start,points,order);best=(old,order)
        for width in (1,2):
            for i in range(n-width+1):
                block=order[i:i+width];rest=order[:i]+order[i+width:]
                for j in range(len(rest)+1):
                    proposed=rest[:j]+block+rest[j:]
                    cost=route_length(start,points,proposed)
                    if cost<best[0]-1e-6:best=(cost,proposed)
        if best[0]>=old-1e-6:break
        order=best[1]
    return order
