"""Time-oriented candidate expansion. Decisions use accepted public feedback only."""
import math
from route_search import RouteSearchController
from geometry import minimum_circle, diameter, clip_bearing
from replanning import area_center, polygon_quadrature
from replanning import MaximumSourcesKnown


class TimePolicy(RouteSearchController):
    def __init__(self, client, direct_candidates=True, error_risk=1.,
                 optical_cost=False, source_quadrature=False, explore_gain=0.,
                 intermediate_shared=False, **options):
        super().__init__(client, **options)
        self.direct_candidates=bool(direct_candidates)
        self.error_risk=float(error_risk)
        self.optical_cost=bool(optical_cost)
        self.source_quadrature=bool(source_quadrature)
        self.explore_gain=float(explore_gain)
        self.intermediate_shared=bool(intermediate_shared)
        self._in_shared=False
        if not 0 <= self.error_risk <= 1:
            raise ValueError('error_risk must be in [0,1]')

    def measure(self,point,channel):
        old=self.client.ledger.position
        response=super().measure(point,channel)
        if (self.intermediate_shared and not self._in_shared
                and math.dist(old,point)>120 and len(self.bearings.get(channel,[]))>1):
            self._in_shared=True
            try:
                self.useful_shared(point)
            finally:
                self._in_shared=False
        return response

    def scan_stop(self,point,force=False):
        result=super().scan_stop(point,force)
        if self.explore_gain<=0 or self.search_complete:
            return result
        here=self.point_mask(point)
        selected=[]
        for ch in self.unknown_channels():
            covered=0
            for q in self.negatives[ch]:
                if q not in self.mask_cache:
                    self.mask_cache[q]=self.point_mask(q)
                covered|=self.mask_cache[q]
            residual=self.full_mask & ~covered
            fraction=(residual & here).bit_count()/max(1,residual.bit_count())
            if fraction>=self.explore_gain:
                selected.append(ch)
        selected.sort(key=lambda ch:(ch!=self.client.ledger.channel,ch))
        for ch in selected:
            try:
                self.measure(point,ch)
            except MaximumSourcesKnown:
                break
        if selected:
            self.record(reason='H_early_discovery_scan',channels=selected,point=point,
                residual_fraction_threshold=self.explore_gain,quadrature_not_certificate=True)
            self.refresh_search();self.prune_with_actual_feedback()
        return result

    def choose_station(self,ch,poly,current,previous):
        center,radius=minimum_circle(poly);centroid=area_center(poly)
        _,a,b=diameter(poly);length=max(math.dist(a,b),1e-9)
        normal=(-(b[1]-a[1])/length,(b[0]-a[0])/length)
        candidates=[]
        for c in (center,centroid):
            offsets=sorted(set((15.,40.,80.,min(400.,max(100.,radius*self.lateral)))))
            if self.direct_candidates:
                offsets=sorted(set(offsets+[0.,8.,25.]))
            for offset in offsets:
                for sign in (-1,1):
                    candidates.append((c[0]+sign*offset*normal[0],c[1]+sign*offset*normal[1]))
            travel=math.dist(current,c)
            distances=(10.,20.,40.,100.,200.,400.) if self.direct_candidates else (40.,100.,200.,400.)
            if travel>1e-8:
                for distance in distances:
                    if distance<travel:
                        candidates.append(tuple(c[k]+(current[k]-c[k])*distance/travel for k in (0,1)))
        for fraction in (.25,.5,.75):
            c=tuple(current[k]+fraction*(center[k]-current[k]) for k in (0,1))
            for offset in (40.,100.,200.,400.):
                for sign in (-1,1):
                    candidates.append((c[0]+sign*offset*normal[0],c[1]+sign*offset*normal[1]))
        for i,s in enumerate(previous):
            for t in previous[i+1:]:
                candidates.append(((s[0]+t[0])/2,(s[1]+t[1])/2))
        if self.source_quadrature:
            quadrature=polygon_quadrature(poly)
            if len(quadrature)>8:
                sampled=[];accumulated=0.;i=0
                for k in range(8):
                    threshold=(k+.5)/8
                    while i<len(quadrature)-1 and accumulated+quadrature[i][1]<threshold:
                        accumulated+=quadrature[i][1];i+=1
                    sampled.append((quadrature[i][0],1/8))
                quadrature=sampled
        else:
            sources=[center]+[((v[0]+center[0])/2,(v[1]+center[1])/2)
                for v in poly[::max(1,len(poly)//6)]]
            quadrature=[(s,1/len(sources)) for s in sources]
        best=None
        for q in dict.fromkeys(candidates):
            if any(math.dist(q,p)<.05 for p in previous) or not self.reception_ok(poly,q,previous):
                continue
            expected=0.;success=0.;rmaxall=0.
            for source,weight in quadrature:
                if math.dist(q,source)<=5:
                    expected+=5*weight;success+=weight;continue
                costs=[];rmax=0.
                for error in (-1.005,0.,1.005):
                    beta=math.degrees(math.atan2(source[1]-q[1],source[0]-q[0]))+error
                    updated=clip_bearing(poly,q,beta)
                    if not updated:
                        continue
                    c,r=minimum_circle(updated)
                    cost=max(0.,math.dist(q,c)-max(0.,20-r))/5+5
                    if r>20:
                        extra=6+min(160.,2*r)/5
                        if self.optical_cost and r<=self.optical_trial:
                            # A heuristic expected optical success, never a
                            # certificate or permission to declare a source clear.
                            samples=polygon_quadrature(updated)
                            chance=sum(w for p,w in samples if math.dist(p,c)<=20)
                            extra=(1-chance)*(extra+3)
                        cost+=extra
                    costs.append(cost);rmax=max(rmax,r)
                if not costs:
                    costs=[1e6]
                expected+=weight*(self.error_risk*max(costs)+(1-self.error_risk)*sum(costs)/len(costs))
                success+=weight*int(rmax<=20);rmaxall=max(rmaxall,rmax)
            score=math.dist(current,q)/5+5+int(self.client.ledger.channel!=ch)+expected
            entry=(score,-success,rmaxall,q)
            if best is None or entry<best:
                best=entry
        if best is None:
            return None
        return dict(point=best[3],estimated_remaining_s=best[0],
            geometric_success_fraction=-best[1],sampled_worst_radius=best[2],
            error_risk=self.error_risk,direct_candidates=self.direct_candidates)
