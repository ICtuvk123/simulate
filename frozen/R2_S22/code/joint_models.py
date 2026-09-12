"""History-conditioned quadrature under an explicit local experimental prior.

Prior: uniform area within the positive bearing region; uniform reception
radius on [1000,1500]; half omni and half uniform directional heading. This is
only a planning assumption, not the official distribution or a certificate.
Real negative stations partition the radius integral at exact distances; on
each interval the admissible heading set is integrated by angular length.
Unlike equal per-position normalization, likelihood mass is retained across
positions, radius intervals and types. Hard geometry is never changed here.
"""
import math

TAU=2*math.pi


def intersect(left,right):
    return [(max(a,c),min(b,d)) for a,b in left for c,d in right if max(a,c)<min(b,d)]


def hemisphere(vector,positive=True):
    if math.hypot(*vector)<1e-9:return [(0.,TAU)] if positive else []
    center=(math.atan2(vector[1],vector[0])+(0 if positive else math.pi))%TAU
    lo,hi=center-math.pi/2,center+math.pi/2
    if lo<0:return [(0.,hi),(lo+TAU,TAU)]
    if hi>TAU:return [(lo,TAU),(0.,hi-TAU)]
    return [(lo,hi)]


def heading_intervals(g,positives,negatives_in_range):
    intervals=[(0.,TAU)]
    for station in positives:
        intervals=intersect(intervals,hemisphere((station[0]-g[0],station[1]-g[1])))
    for station in negatives_in_range:
        intervals=intersect(intervals,hemisphere((station[0]-g[0],station[1]-g[1]),False))
    return intervals


def build_joint_models(points,positives,negatives,exclusions=(),omni_prior=.5):
    models=[];omni_prior=max(0.,min(1.,float(omni_prior)))
    positive_stations=[p for p,_ in positives]
    for g in points:
        if any(math.dist(g,e['point'])<e['radius'] for e in exclusions):continue
        lower=max([1000.]+[math.dist(g,p) for p in positive_stations])
        if lower>=1500-1e-8:continue
        distances=[(math.dist(g,n),n) for n in negatives]
        cuts=sorted(set([lower,1500.]+[distance for distance,_ in distances if lower<distance<1500.]))
        for low,high in zip(cuts,cuts[1:]):
            if high-low<1e-8:continue
            radius=(low+high)/2
            in_range=[n for distance,n in distances if distance<=radius]
            radius_mass=(high-low)/500
            if not in_range and omni_prior>0:
                models.append(dict(g=g,r=radius,heading=None,weight=radius_mass*omni_prior))
            if omni_prior<1:
                arcs=heading_intervals(g,positive_stations,in_range)
                for a,b in arcs:
                    if b-a<1e-10:continue
                    # Two interior samples preserve each angular interval's
                    # likelihood mass; endpoints remain possible in hard P.
                    weight=(1-omni_prior)*radius_mass*(b-a)/TAU/2
                    for fraction in (.25,.75):
                        angle=a+fraction*(b-a)
                        models.append(dict(g=g,r=radius,heading=(math.cos(angle),math.sin(angle)),weight=weight))
    total=sum(model['weight'] for model in models)
    if total<=1e-15:return []
    for i,model in enumerate(models):
        model['weight']/=total
        model['error']=(-1.,0.,1.)[i%3]
    return models
