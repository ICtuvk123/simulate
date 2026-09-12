"""Bounded, possibly unsuccessful optical probes ranked against safe continuation.

The convex localization polygon is never reduced here. Actual failed optical
responses are represented separately by conservative exclusion disks. Finite
models affect ranking only; neither models nor proposed probes are certificates.
"""
import math
from lookahead import pair_cost,single_probe_cost,remaining_cost
from compact_optical import choose_cover
from geometry import minimum_circle

EXCLUSION_RADIUS = 20. - 1e-5


def outside_exclusions(point, exclusions):
    return all(math.dist(point, item['point']) >= item['radius']
               for item in exclusions)


def normalized(models):
    mass = sum(model['weight'] for model in models)
    return [dict(model, weight=model['weight']/mass) for model in models] if mass else []


def candidates(current, destination, models, exclusions, limit=9,poly=None,max_detour=0.):
    """Try current position and points on the already planned first RF leg.

    Equal-spaced positions make a fixed candidate set instead of centering a
    trial exactly on each quadrature hypothesis. Optional polygon-center and
    long-axis candidates obey an explicit detour bound, and the continuation
    estimate pays that detour and all subsequent movement.
    """
    proposed=[];out=[]
    for i in range(max(2, limit)):
        fraction=i/(max(2, limit)-1)
        q=tuple(current[k]+fraction*(destination[k]-current[k]) for k in (0,1))
        proposed.append(q)
    if poly and max_detour>0:
        center,_=minimum_circle(poly)
        a,b=max(((a,b) for a in poly for b in poly),key=lambda pair:math.dist(*pair))
        proposed += [center]+[tuple((1-f)*a[k]+f*b[k] for k in (0,1)) for f in (.25,.5,.75)]
    for q in proposed:
        if math.dist(current,q)+math.dist(q,destination)-math.dist(current,destination)>max_detour+1e-6:continue
        if any(math.dist(q,old)<1e-6 for old in out):continue
        # Avoid retrying a known failed point. Merely being in a failed disk is
        # insufficient to skip: the new 20 m disk may include a fresh crescent.
        if any(math.dist(q,item['point'])<.05 for item in exclusions):continue
        if any(math.dist(q,m['g'])<=20 for m in models):out.append(q)
    return out


def continuation_cost(poly, current, probe, endpoints, models, anchor, switch,
                      optical_threshold=0., compact_points=4,first_result=None):
    if first_result is not None:
        radio,_=single_probe_cost(poly,current,endpoints[0],models,anchor,first_result,probe)
    else:radio, _=pair_cost(poly,current,probe,endpoints,models,anchor,optical_threshold)
    radio+=switch
    cover=choose_cover(poly,current,models,anchor,compact_points) if compact_points else None
    if cover and cover['estimated_remaining_s']<radio:
        return cover['estimated_remaining_s'], 'certified_optical'
    return radio, 'paired_rf'


def choose_partial(poly,current,selected,models,exclusions,options,anchor=None,switch=0):
    """One optical action, then the existing reliable RF/optical continuation.

    Both hit and miss include movement, 3 s optical, successful 2 s surcharge,
    switch costs and the outgoing task leg. Failed synthetic probes do not
    mutate true history. This is a finite-model estimate, not a probability or
    an improvement guarantee under the unknown official scene distribution.
    """
    models=normalized([m for m in models if outside_exclusions(m['g'],exclusions)])
    if not models or not selected:return None
    probe=selected['probe'];ends=selected['endpoints']
    first_result=selected.get('first_result')
    compact=options.get('compact_optical_points',4) if options.get('compact_optical') else 0
    if first_result is not None and not options.get('compact_after_first'):compact=0
    threshold=options.get('lookahead_optical',0.)
    baseline,baseline_kind=continuation_cost(poly,current,probe,ends,models,anchor,
                                             switch,threshold,compact,first_result)
    best=None
    for q in candidates(current,ends[0],models,exclusions,
                        options.get('partial_optical_candidates',9),poly,
                        options.get('partial_optical_max_detour_m',0.)):
        hit=[m for m in models if math.dist(q,m['g'])<=20]
        miss=[m for m in models if math.dist(q,m['g'])>20]
        p=sum(m['weight'] for m in hit)
        if p<options.get('partial_optical_min_mass',.05):continue
        # A finite model set can put every sample in one disk even though a
        # thin unsampled crescent remains. Keep an explicit miss reserve. This
        # is a ranking safeguard, never a geometric deletion or probability.
        if not all(math.dist(q,v)<=20-1e-5 for v in poly):
            p=min(p,1-options.get('partial_optical_miss_reserve',.05))
        miss_cost,miss_kind=(continuation_cost(poly,q,probe,ends,normalized(miss),anchor,
                                               switch,threshold,compact,first_result) if miss else
                             (remaining_cost(poly,q,anchor)+6.,'conservative_terminal_unsampled_miss'))
        hit_cost=2.+(math.dist(q,anchor)/5 if anchor is not None else 0.)
        cost=math.dist(current,q)/5+3+p*hit_cost+(1-p)*miss_cost
        gain=baseline-cost
        if gain<=options.get('partial_optical_gain_s',2.):continue
        if best is None or cost<best['estimated_remaining_s']:
            best=dict(point=q,estimated_remaining_s=cost,baseline_remaining_s=baseline,
                      estimated_gain_s=gain,predicted_hit_mass=p,
                      predicted_miss_remaining_s=miss_cost,baseline_kind=baseline_kind,
                      miss_continuation_kind=miss_kind,model_count=len(models),
                      outgoing_anchor=anchor,exclusion_count=len(exclusions),
                      assumptions_only_for_ranking=True,full_coverage_claimed=False,
                      miss_continuation_included=True)
    return best
