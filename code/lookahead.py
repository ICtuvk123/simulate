"""Finite feedback-conditioned hypotheses used ONLY to rank Q4 actions.

No simulator imports, random-world keys, or truth inputs. The returned probe
still needs actual observations before the controller changes its region.
This is a two-RF-action heuristic, not an exact stochastic value function.
"""
import math
from geometry import clip, clip_bearing, minimum_circle, cross, sub
from local_geometry import nearest_operating_point
from directional_geometry import paired_probe, apply_paired_negative, ALPHA, MARGIN


def quadrature(poly, count=9):
    c=tuple(sum(p[k] for p in poly)/len(poly) for k in (0,1))
    triangles=[];total=0.
    for a,b in zip(poly,poly[1:]+poly[:1]):
        area=abs(cross(sub(a,c),sub(b,c)))/2
        if area>1e-10:total+=area;triangles.append((total,a,b,area))
    if not triangles:return [c]
    out=[]
    for i in range(count):
        target=total*(i+.5)/count
        end,a,b,area=next(t for t in triangles if t[0]>=target)
        # Stratified triangle choice; deterministic interior barycentric points.
        u=math.sqrt(((i+.5)*.6180339887498949)%1)
        v=((i+.5)*.4142135623730951)%1
        q=tuple((1-u)*c[k]+u*(1-v)*a[k]+u*v*b[k] for k in (0,1))
        if math.hypot(*q)<=1800+1e-8:out.append(q)
    return out


def receives(g,r,heading,q):
    if math.dist(g,q)>r+1e-8:return False
    return heading is None or sum((q[k]-g[k])*heading[k] for k in (0,1))>=-1e-8


def hypotheses(poly, positives, negatives, count=9):
    models=[]
    for g in quadrature(poly,count):
        low=max([1000.]+[math.dist(g,s) for s,_ in positives])
        if low>1500+1e-6:continue
        radii=sorted(set((min(1500.,low),min(1500.,(low+1500)/2),1500.)))
        # Include angular boundary sectors induced by the actual stations.
        bounds=sorted(set((math.atan2(s[1]-g[1],s[0]-g[0])+sign*math.pi/2)%(2*math.pi)
                          for s in [p for p,_ in positives]+list(negatives) for sign in (-1,1)))
        angles=[k*math.pi/12 for k in range(24)]+bounds
        if bounds:
            angles += [(a+(b-a)%(2*math.pi)/2)%(2*math.pi) for a,b in zip(bounds,bounds[1:]+bounds[:1])]
        local=[]
        for r in radii:
            omni=all(not receives(g,r,None,s) for s in negatives)
            if omni:local.append(dict(g=g,r=r,heading=None,weight=1.))
            directional=[]
            for angle in sorted(set(angles)):
                u=(math.cos(angle),math.sin(angle))
                if (all(receives(g,r,u,s) for s,_ in positives)
                    and all(not receives(g,r,u,s) for s in negatives)):
                    directional.append(u)
            # Small deterministic quadrature of the surviving angular set.
            chosen=[directional[min(len(directional)-1,int((i+.5)*len(directional)/2))]
                    for i in range(2)] if directional else []
            for u in chosen:local.append(dict(g=g,r=r,heading=u,weight=.5 if omni else 1.))
        mass=sum(m['weight'] for m in local)
        for m in local:m['weight']/=mass;models.append(m)
    mass=sum(m['weight'] for m in models)
    for i,m in enumerate(models):
        m['weight']/=mass
        m['error']=(-1.,0.,1.)[i%3]
    return models


def predicted_feedback(model,q):
    g=model['g']
    if not receives(g,model['r'],model['heading'],q):return 'no_signal',None
    if math.dist(g,q)<=5:return 'near',None
    return 'direction',(math.degrees(math.atan2(g[1]-q[1],g[0]-q[0]))+model['error'])%360


def predicted_region(poly,q,beta):
    # Fast bearing-only update for candidates with an explicit range bound.
    lo,hi=map(math.radians,(beta-1.01,beta+1.01))
    for n in ((math.sin(lo),-math.cos(lo)),(-math.sin(hi),math.cos(hi))):
        poly=clip(poly,n,sum(n[k]*q[k] for k in (0,1)))
    return poly


def remaining_cost(poly,q,anchor=None):
    center,r=minimum_circle(poly)
    safe=nearest_operating_point(poly,q) if r<=20 else None
    destination=safe if safe is not None else center
    cost=math.dist(q,destination)/5+5
    if safe is None:
        # Explicit terminal approximation: additional radio + unresolved travel.
        cost+=12*math.ceil(math.log2(max(1.,r/20)))+.22*max(0.,r-20)
    if anchor is not None:cost+=math.dist(destination,anchor)/5
    return cost


def pair_cost(poly,current,probe,endpoints,models,anchor=None,optical_threshold=0.):
    expected=0.;branches={'no_signal':0.,'direction':0.,'near':0.,'optical_failure':0.,'optical_success':0.}
    needs_disk=(probe.get('radius_witness')=='positive_station_radius' and
                not all(math.dist(q,v)<=1500-MARGIN for q in endpoints for v in poly))
    for model in models:
        p=current;region=list(poly);cost=0.;results=[];done=False
        for q in endpoints:
            cost+=math.dist(p,q)/5+5;p=q
            kind,beta=predicted_feedback(model,q);results.append(kind);branches[kind]+=model['weight']
            if kind=='near':
                cost+=5+(math.dist(p,anchor)/5 if anchor is not None else 0)
                done=True;break
            if kind=='direction':
                region=(clip_bearing(region,q,beta) if needs_disk
                        else predicted_region(region,q,beta))
                if not region:cost+=1000;done=True;break
                center,r=minimum_circle(region)
                if r<=20:
                    cost+=remaining_cost(region,p,anchor);done=True;break
                if 20<r<=optical_threshold:
                    cost+=math.dist(p,center)/5+3;p=center
                    if math.dist(center,model['g'])<=20:
                        cost+=2+(math.dist(p,anchor)/5 if anchor is not None else 0)
                        branches['optical_success']+=model['weight'];done=True;break
                    branches['optical_failure']+=model['weight']
                    # A predicted optical failure does not delete real geometry.
        if not done:
            if results==['no_signal','no_signal']:
                region=apply_paired_negative(region,dict(probe,results=results))
            cost+=remaining_cost(region,p,anchor)
        expected+=model['weight']*cost
    # All plans share the same first channel-switch cost, so it cancels in rank.
    return expected,branches


def choose_pair(poly,current,positives,negatives,measured,options,anchor=None):
    models=hypotheses(poly,positives,negatives,options.get('lookahead_positions',9))
    if not models:return None
    candidates=[]
    for s,beta in (positives[:1] if not options.get('lookahead_history') else positives[-3:]):
        for fraction in options.get('lookahead_fractions',[.35,.5,.65]):
            spacings=list(options.get('lookahead_spacings',[40.,80.,120.]))
            narrow=options.get('narrow_probe',False)
            if narrow:
                midpoint=paired_probe(poly,s,beta,80.,fraction)
                lower=max(0.,midpoint['t']*math.tan(ALPHA)+MARGIN)
                spacings += [max(1.,float(math.ceil(lower))),max(1.,float(math.ceil(1.5*lower)))]
            for b in dict.fromkeys(spacings):
                probe=paired_probe(poly,s,beta,b,fraction,narrow_probe=narrow)
                if not probe['geometry_valid']:continue
                ends=[probe['plus'],probe['minus']]
                if any(any(math.dist(q,p)<.05 for p in measured) for q in ends):continue
                ends.sort(key=lambda q:math.dist(current,q))
                orders=[ends,ends[::-1]] if options.get('lookahead_both_orders') else [ends]
                for order in orders:
                    score,branches=pair_cost(poly,current,probe,order,models,anchor,options.get('lookahead_optical',0.))
                    candidates.append((score,probe,order,branches))
    if not candidates:return None
    score,probe,order,branches=min(candidates,key=lambda item:item[0])
    return dict(probe=probe,endpoints=order,estimated_remaining_s=score,
                model_count=len(models),candidate_count=len(candidates),branches=branches,
                assumptions_only_for_ranking=True)


def shared_information_value(poly,q,positives,negatives,count=7):
    """Expected local remainder reduction at an ALREADY reached station.

    No reception guarantee is inferred from distance. A failed reception keeps
    the complete polygon in the prediction, and pays the radio/switch cost.
    """
    models=hypotheses(poly,positives,negatives,count)
    if not models:return None
    baseline=remaining_cost(poly,q);after=0.;branches={'direction':0.,'near':0.,'no_signal':0.}
    distance_bounded=all(math.dist(q,p)<=1500-1e-5 for p in poly)
    for model in models:
        kind,beta=predicted_feedback(model,q);branches[kind]+=model['weight']
        if kind=='no_signal':cost=baseline
        elif kind=='near':cost=5.
        else:
            updated=predicted_region(poly,q,beta) if distance_bounded else clip_bearing(poly,q,beta)
            cost=remaining_cost(updated,q) if updated else baseline+1000
        after+=model['weight']*cost
    return dict(estimated_gain_s=baseline-after-6.,model_count=len(models),branches=branches,
                no_signal_branch_included=True,assumptions_only_for_ranking=True)


def single_probe_cost(poly,current,q,models,anchor=None,first_result=None,probe=None):
    """Cost of the remaining second RF, including a possible valid double-no cut."""
    total=0.;branches={'no_signal':0.,'direction':0.,'near':0.}
    needs_disk=(probe is not None and probe.get('radius_witness')=='positive_station_radius' and
                not all(math.dist(q,v)<=1500-MARGIN for v in poly))
    for model in models:
        region=list(poly);cost=math.dist(current,q)/5+5
        kind,beta=predicted_feedback(model,q);branches[kind]+=model['weight']
        if kind=='near':cost+=5+(math.dist(q,anchor)/5 if anchor is not None else 0.)
        else:
            if kind=='direction':
                region=(clip_bearing(region,q,beta) if needs_disk
                        else predicted_region(region,q,beta))
            elif first_result=='no_signal' and probe is not None:
                region=apply_paired_negative(region,dict(probe,results=['no_signal','no_signal']))
            cost+=remaining_cost(region,q,anchor) if region else 10000.
        total+=model['weight']*cost
    return total,branches
