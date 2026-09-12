"""One new RF combined with one earlier actual negative on the same channel.

Finite hypotheses rank actions only. The asymmetric line witness is checked
again with actual feedback before any position is deleted.
"""
import math
from geometry import clip,clip_bearing
from directional_geometry import ALPHA,MARGIN,sector_consistent
from lookahead import hypotheses,predicted_feedback,predicted_region,remaining_cost


def make_reuse_probe(poly,station,bearing,historical_negative,b):
    angle=math.radians(bearing);d=(math.cos(angle),math.sin(angle));n=(-d[1],d[0])
    h=tuple(historical_negative)
    t=sum((h[k]-station[k])*d[k] for k in (0,1))
    c=sum((h[k]-station[k])*n[k] for k in (0,1))
    signed_b=-math.copysign(b,c)
    q=tuple(station[k]+t*d[k]+signed_b*n[k] for k in (0,1))
    gap_old=t*t-c*c-2*t*abs(c)*math.tan(ALPHA)
    gap_new=t*t-b*b-2*t*b*math.tan(ALPHA)
    valid=(t>0 and b>0 and min(abs(c),b)>=t*math.tan(ALPHA)+MARGIN
           and min(gap_old,gap_new)>=MARGIN and sector_consistent(poly,station,d,n))
    return dict(kind='positive_station_asymmetric_pair',station=tuple(station),bearing=bearing,
                d=d,n=n,t=t,b=b,historical_height=c,new_height=signed_b,
                historical_negative=h,new_station=q,geometry_valid=valid,
                old_radius_gap_sq_m2=gap_old,new_radius_gap_sq_m2=gap_new,
                alpha_rad=ALPHA,geometry_margin=MARGIN)


def verify_reused_geometry(poly,w):
    try:
        s=w['station'];h=w['historical_negative'];a=math.radians(w['bearing']);b=w['b']
        if not all(math.isfinite(v) for v in [*s,*h,a,b]):return False
        d=(math.cos(a),math.sin(a));n=(-d[1],d[0])
        t=sum((h[k]-s[k])*d[k] for k in (0,1));c=sum((h[k]-s[k])*n[k] for k in (0,1))
        signed_b=-math.copysign(b,c)
        q=tuple(s[k]+t*d[k]+signed_b*n[k] for k in (0,1))
        return (w.get('kind')=='positive_station_asymmetric_pair' and t>0 and b>0
                and min(abs(c),b)>=t*math.tan(ALPHA)+MARGIN
                and min(t*t-c*c-2*t*abs(c)*math.tan(ALPHA),t*t-b*b-2*t*b*math.tan(ALPHA))>=MARGIN
                and abs(w['t']-t)<1e-8 and abs(w['historical_height']-c)<1e-8
                and abs(w['new_height']-signed_b)<1e-8
                and math.dist(w['d'],d)<1e-9 and math.dist(w['n'],n)<1e-9
                and math.dist(w['new_station'],q)<1e-8 and math.dist(q,h)>MARGIN
                and sector_consistent(poly,s,d,n))
    except (KeyError,ValueError,TypeError,OverflowError):return False


def apply_reused_negative(poly,w):
    if w.get('results')!=['no_signal','no_signal'] or not verify_reused_geometry(poly,w):
        raise ValueError('Actual historical/new negatives and valid asymmetric geometry required')
    d=w['d'];s=w['station']
    return clip(poly,d,sum(d[k]*s[k] for k in (0,1))+w['t'])


def reused_cost(poly,current,probe,models,anchor=None):
    q=probe['new_station'];total=0.;branches={'no_signal':0.,'direction':0.,'near':0.}
    range_bounded=all(math.dist(q,v)<=1500-MARGIN for v in poly)
    for model in models:
        cost=math.dist(current,q)/5+5
        kind,beta=predicted_feedback(model,q);branches[kind]+=model['weight']
        if kind=='near':cost+=5+(math.dist(q,anchor)/5 if anchor is not None else 0.)
        else:
            if kind=='no_signal':region=apply_reused_negative(poly,dict(probe,results=['no_signal','no_signal']))
            else:region=predicted_region(poly,q,beta) if range_bounded else clip_bearing(poly,q,beta)
            cost+=remaining_cost(region,q,anchor) if region else 10000.
        total+=model['weight']*cost
    return total,branches


def choose_reused_probe(poly,current,positives,negatives,measured,options,anchor=None):
    if not negatives:return None
    candidates=[];seen=set()
    for s,beta in (positives[-3:] if options.get('lookahead_history') else positives[:1]):
        a=math.radians(beta);d=(math.cos(a),math.sin(a));n=(-d[1],d[0]);tau=math.tan(ALPHA)
        projections=[sum((v[k]-s[k])*d[k] for k in (0,1)) for v in poly]
        low,high=min(projections),max(projections)
        for h in negatives:
            t=sum((h[k]-s[k])*d[k] for k in (0,1));c=sum((h[k]-s[k])*n[k] for k in (0,1))
            if not (low+MARGIN<t<high-MARGIN and t>0 and abs(c)>=t*tau+MARGIN
                    and t*t-c*c-2*t*abs(c)*tau>=MARGIN):continue
            lower=t*tau+MARGIN
            spacings=list(options.get('lookahead_spacings',[40.,80.,120.]))
            spacings += [max(1.,float(math.ceil(lower))),max(1.,float(math.ceil(1.5*lower)))]
            for b in dict.fromkeys(spacings):
                probe=make_reuse_probe(poly,s,beta,h,b);q=probe['new_station']
                if not probe['geometry_valid'] or q in seen or any(math.dist(q,p)<.05 for p in measured):continue
                seen.add(q)
                # Cheap deterministic screen; scoring itself still includes all outcomes.
                proxy=math.dist(current,q)/5+abs(t-(low+high)/2)/5
                candidates.append((proxy,probe))
    if not candidates:return None
    models=hypotheses(poly,positives,negatives,options.get('lookahead_positions',9),
                      joint=options.get('joint_model_weights',False),spatial_errors=options.get('planning_spatial_errors',False),
                      balanced_errors=options.get('planning_balanced_errors',False))
    if not models:return None
    count=len(candidates);evaluated=[]
    candidates.sort(key=lambda item:(item[0],item[1]['new_station']))
    for _,probe in candidates[:options.get('reuse_negative_max_candidates',12)]:
        score,branches=reused_cost(poly,current,probe,models,anchor)
        evaluated.append((score,probe,branches))
    score,probe,branches=min(evaluated,key=lambda item:item[0])
    return dict(probe=probe,point=probe['new_station'],estimated_remaining_s=score,
                model_count=len(models),candidate_count=count,evaluated_candidates=len(evaluated),
                branches=branches,new_rf_actions=1,historical_rf_cost_s=0.,
                assumptions_only_for_ranking=True)
