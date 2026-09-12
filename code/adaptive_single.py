"""Optional one-RF replanning action competing with a complete Q4 pair.

Only geometric candidate locations are adapted from frozen G structural.py.
No G reception guarantee, negative disk, or bisector update is imported.
All failure branches pay for restoring the original, still unvisited pair.
"""
import math
from geometry import minimum_circle,diameter,clip_bearing
from task_routing import area_centroid
from candidate_geometry import canonical_candidate_polygon
from lookahead import hypotheses,predicted_feedback,predicted_region,pair_cost,remaining_cost


def candidate_points(poly,current,measured,pair_endpoints):
    center,radius=minimum_circle(poly);centroid=area_centroid(poly)
    _,a,b=diameter(poly);length=max(1e-9,math.dist(a,b))
    normal=(-(b[1]-a[1])/length,(b[0]-a[0])/length)
    candidates=[(tuple(current),'current')]
    for c in (center,centroid):
        for offset in sorted(set((15.,40.,80.,min(400.,max(100.,radius))))):
            for sign in (-1,1):
                candidates.append((tuple(c[k]+sign*offset*normal[k] for k in (0,1)),'G_center_lateral'))
        travel=math.dist(current,c)
        if travel>1e-8:
            for distance in (40.,100.,200.,400.):
                if distance<travel:
                    candidates.append((tuple(c[k]+(current[k]-c[k])*distance/travel for k in (0,1)),'G_approach'))
    for fraction in (.25,.5,.75):
        c=tuple(current[k]+fraction*(center[k]-current[k]) for k in (0,1))
        for offset in (40.,100.,200.,400.):
            for sign in (-1,1):
                candidates.append((tuple(c[k]+sign*offset*normal[k] for k in (0,1)),'G_travel_lateral'))
    accepted=[]
    for q,kind in candidates:
        # Keep the complete original recovery pair available without measuring
        # the same location again. Its endpoints remain ordinary pair actions.
        if not all(math.isfinite(v) for v in q):continue
        if any(math.dist(q,p)<.05 for p in list(measured)+list(pair_endpoints)):continue
        if any(math.dist(q,p)<.05 for p,_ in accepted):continue
        accepted.append((q,kind))
    return accepted


def one_action_cost(poly,current,q,models,pair,anchor=None,switch_cost=0,optical_threshold=0.,negative_recovery_base=None):
    total=0.;branches={'no_signal':0.,'direction':0.,'near':0.}
    recovery_cost={'no_signal':0.,'direction':0.};recovery_mass=0.
    full_range=all(math.dist(q,p)<=1500-1e-5 for p in poly)
    immediate=math.dist(current,q)/5+5+switch_cost
    first=pair['endpoints'][0]
    entry_delta=(math.dist(q,first)-math.dist(current,first))/5
    for index,model in enumerate(models):
        mass=model['weight'];kind,beta=predicted_feedback(model,q);branches[kind]+=mass
        if kind=='near':tail=5+(math.dist(q,anchor)/5 if anchor is not None else 0.)
        else:
            region=list(poly)
            if kind=='direction':
                region=(predicted_region(region,q,beta) if full_range else clip_bearing(region,q,beta))
            if not region:tail=10000.
            elif kind=='direction' and minimum_circle(region)[1]<=20:
                tail=remaining_cost(region,q,anchor)
            else:
                # This is a complete original-pair rollout, not the cheap
                # unresolved-radius terminal approximation at q. The current
                # single no_signal itself makes no positional cut.
                if kind=='no_signal' and negative_recovery_base is not None:
                    # The complete original rollout changes only in its first
                    # movement leg; optical failures remain inside the cache.
                    tail=negative_recovery_base[index]+entry_delta
                else:
                    singleton=dict(model,weight=1.)
                    tail,_=pair_cost(region,q,pair['probe'],pair['endpoints'],[singleton],anchor,optical_threshold)
                recovery_cost[kind]+=mass*tail;recovery_mass+=mass
        total+=mass*(immediate+tail)
    return dict(estimated_remaining_s=total,branches=branches,recovery_mass=recovery_mass,
                weighted_pair_recovery_cost_s=recovery_cost,immediate_action_cost_s=immediate)


def choose_adaptive_single(poly,current,positives,negatives,measured,options,pair,anchor=None,switch_cost=0,exclusions=()):
    if not pair or not pair['probe'].get('geometry_valid'):return None
    # A stale pair cannot serve as the fallback required by this candidate.
    if any(any(math.dist(q,p)<.05 for p in measured) for q in pair['endpoints']):return None
    models=hypotheses(poly,positives,negatives,options.get('lookahead_positions',9),exclusions,
                      joint=options.get('joint_model_weights',False),spatial_errors=options.get('planning_spatial_errors',False),
                      balanced_errors=options.get('planning_balanced_errors',False),stable=options.get('stable_quadrature',False))
    if not models:return None
    candidate_poly=(canonical_candidate_polygon(poly)
                    if options.get('canonical_single_candidates',False) else poly)
    candidates=candidate_points(candidate_poly,current,measured,pair['endpoints'])
    baseline=pair['estimated_remaining_s']+switch_cost;best=None
    optical_threshold=options.get('lookahead_optical',0.)
    negative_recovery_base=[pair_cost(poly,current,pair['probe'],pair['endpoints'],
                                     [dict(model,weight=1.)],anchor,optical_threshold)[0] for model in models]
    for point,kind in candidates:
        cost=one_action_cost(poly,current,point,models,pair,anchor,switch_cost,optical_threshold,negative_recovery_base)
        if cost['estimated_remaining_s']>=baseline-options.get('adaptive_single_gain_s',1.):continue
        if best is None or cost['estimated_remaining_s']<best['estimated_remaining_s']:
            best=dict(point=point,candidate_kind=kind,**cost)
    if best is None:return None
    best.update(original_pair_cost_s=baseline,recovery_probe=pair['probe'],
                recovery_endpoints=pair['endpoints'],model_count=len(models),candidate_count=len(candidates),
                no_signal_recovery='complete_original_unvisited_pair',assumptions_only_for_ranking=True)
    return best
