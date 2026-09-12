"""Experimental E: feedback-driven replanning; immutable D remains the control.

No source generator, true coordinates, seed, source count, network or file reads.
Hypothetical positions are quadrature points inside the current feasible region.
"""
import math

from optimized import OptimizedController, open_route, route_length
from local_geometry import nearest_operating_point, time_rollout_station
from geometry import minimum_circle, diameter, clip_bearing
from q3client import ProtocolError
from reception_geometry import reception_safe
from coverage import coverage_partition


def polygon_quadrature(poly):
    """Area-weighted triangle quadrature, used for cost prediction only."""
    anchor = (sum(v[0] for v in poly)/len(poly), sum(v[1] for v in poly)/len(poly))
    weighted = []
    for a,b in zip(poly,poly[1:]+poly[:1]):
        area = abs((a[0]-anchor[0])*(b[1]-anchor[1])-(a[1]-anchor[1])*(b[0]-anchor[0]))/2
        if area < 1e-9:
            continue
        # Three positive barycentric points integrate quadratics on each triangle.
        for weights in ((2/3,1/6,1/6),(1/6,2/3,1/6),(1/6,1/6,2/3)):
            q = tuple(weights[0]*anchor[k]+weights[1]*a[k]+weights[2]*b[k] for k in (0,1))
            weighted.append((q,area/3))
    total = sum(w for _,w in weighted)
    if total < 1e-12:
        return [(minimum_circle(poly)[0],1.0)]
    return [(p,w/total) for p,w in weighted]


def area_center(poly):
    points=polygon_quadrature(poly)
    return tuple(sum(p[k]*w for p,w in points) for k in (0,1))


def area_rollout_station(poly,current,previous,lateral=1.0,adaptive_reception=False,use_area=True):
    """Reception-safe stations, weighted hypothetical sources and worst error."""
    center,radius=minimum_circle(poly)
    centroid=area_center(poly)
    _,a,b=diameter(poly)
    length=max(math.dist(a,b),1e-9)
    normal=(-(b[1]-a[1])/length,(b[0]-a[0])/length)
    candidates=[]
    for c in (center,centroid):
        offsets=sorted(set((15.,40.,80.,min(400.,max(100.,radius*lateral)))))
        for offset in offsets:
            for sign in (-1,1):
                candidates.append((c[0]+sign*offset*normal[0],c[1]+sign*offset*normal[1]))
        travel=math.dist(current,c)
        if travel>1e-8:
            for distance in (40.,100.,200.,400.):
                if distance<travel:
                    candidates.append(tuple(c[k]+(current[k]-c[k])*distance/travel for k in (0,1)))
    # Bound expensive quadrature by a deterministic weighted resampling, keeping
    # it separate from geometric safety and termination certificates.
    if adaptive_reception:
        for fraction in (.25,.5,.75):
            c=tuple(current[k]+fraction*(center[k]-current[k]) for k in (0,1))
            for offset in (40.,100.,200.,400.):
                for sign in (-1,1):
                    candidates.append((c[0]+sign*offset*normal[0],c[1]+sign*offset*normal[1]))
    quadrature=polygon_quadrature(poly)
    if not use_area:
        points=[center]+[((v[0]+center[0])/2,(v[1]+center[1])/2)
                         for v in poly[::max(1,len(poly)//6)]]
        quadrature=[(p,1/len(points)) for p in points]
    if len(quadrature)>12:
        sampled=[]
        accumulated=0.;i=0
        for k in range(12):
            threshold=(k+.5)/12
            while i<len(quadrature)-1 and accumulated+quadrature[i][1]<threshold:
                accumulated+=quadrature[i][1];i+=1
            sampled.append((quadrature[i][0],1/12))
        quadrature=sampled
    best=None
    for q in candidates:
        safe=(reception_safe(poly,q,previous) if adaptive_reception else
              max(math.dist(q,v) for v in poly)<=1000-1e-4)
        if any(math.dist(q,p)<.05 for p in previous) or not safe:
            continue
        expected=0.;success=0.;worst_radius=0.
        for source,weight in quadrature:
            if math.dist(q,source)<=5:
                expected+=5*weight;success+=weight;continue
            worst=0.;rmax=0.
            for error in (-1.005,0.,1.005):
                beta=math.degrees(math.atan2(source[1]-q[1],source[0]-q[0]))+error
                updated=clip_bearing(poly,q,beta)
                if not updated:
                    continue
                c,r=minimum_circle(updated)
                cost=max(0.,math.dist(q,c)-max(0.,20-r))/5+5
                if r>20:
                    cost+=6+min(160.,2*r)/5
                worst=max(worst,cost);rmax=max(rmax,r)
            expected+=weight*worst;success+=weight*int(rmax<=20)
            worst_radius=max(worst_radius,rmax)
        entry=(math.dist(current,q)/5+6+expected,-success,worst_radius,q)
        if best is None or entry<best:
            best=entry
    if best is None:
        return None
    return dict(point=best[3],estimated_remaining_s=best[0],geometric_success_fraction=-best[1],
                sampled_worst_radius=best[2])


class ReplanningController(OptimizedController):
    def __init__(self,client,replan_measurements=True,adaptive_rotation=False,
                 route_centroid=False,area_rollout=False,lateral=1.0,
                 replacement_scan=False,adaptive_reception=False,shared_limit=1400.,
                 commit_radius=0.,route_hysteresis=0.,**options):
        super().__init__(client,**options)
        self.replan_measurements=bool(replan_measurements)
        self.adaptive_rotation=bool(adaptive_rotation)
        self.route_centroid=bool(route_centroid)
        self.area_rollout=bool(area_rollout)
        self.lateral=float(lateral)
        self.replacement_scan=bool(replacement_scan)
        self.adaptive_reception=bool(adaptive_reception)
        self.shared_limit=float(shared_limit)
        self.commit_radius=float(commit_radius)
        self.route_hysteresis=float(route_hysteresis)
        self.rotation_selected=False
        self.refinements={}
        self.optical_attempts={}

    def scan_stop(self,point,force=False):
        if self.replacement_scan and not force and not self.search_complete:
            remaining=[q for q in self.sites[1:] if all(math.dist(q,p)>1e-5 for p in self.search_stations)]
            for index,site in enumerate(remaining):
                if math.dist(site,point)>650:
                    continue
                if coverage_partition(self.search_stations+[point]+remaining[:index]+remaining[index+1:],9)['complete']:
                    force=True
                    self.prune_stations=True
                    self.record(reason='E_scan_clear_point_to_replace_station',point=point,old_site=site)
                    break
        original_known=self.known_scan
        if self.shared_limit<1400:
            self.known_scan=False
        super().scan_stop(point,force)
        self.known_scan=original_known
        if original_known and self.shared_limit<1400:
            known=sorted(set(self.polygons)-self.cleared,key=lambda ch:(ch!=self.client.ledger.channel,ch))
            for ch in known:
                center,radius=self.info(ch)
                history=self.bearings[ch]
                if radius<20 or math.dist(center,point)>self.shared_limit or any(math.dist(point,p)<120 for p,_ in history):
                    continue
                angle=math.atan2(point[1]-center[1],point[0]-center[0])
                sine=max(abs(math.sin(angle-math.atan2(p[1]-center[1],p[0]-center[0]))) for p,_ in history)
                predicted=math.dist(center,point)*math.tan(math.radians(1.01))/max(sine,.02)
                if sine>.3 and (predicted<self.near_prediction or predicted<self.bearing_factor*radius):
                    self.measure(point,ch)
        if self.adaptive_rotation and not self.rotation_selected:
            self.rotation_selected=True
            targets=[area_center(self.polygons[ch]) if self.route_centroid else self.info(ch)[0]
                     for ch in sorted(set(self.polygons)-self.cleared)]
            scored=[]
            original=self.sites[1:]
            for angle in range(0,60,10):
                a=math.radians(angle)
                sites=[(x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a)) for x,y in original]
                points=sites+targets
                order=open_route(point,points)
                scored.append((route_length(point,points,order),angle,sites))
            _,angle,sites=min(scored)
            self.sites=[(0.,0.)]+sites
            self.record(reason='observed_targets_choose_ring_rotation',angle_deg=angle)

    def info(self,ch):
        center,radius=super().info(ch)
        if self.route_centroid and radius>40:
            # Routing/scan heuristic only; robust operating regions and station
            # reception checks use all vertices independently.
            c=area_center(self.polygons[ch])
            return c,max(math.dist(c,v) for v in self.polygons[ch])
        return center,radius

    def refine_and_clear(self,ch):
        if not self.replan_measurements and not self.area_rollout and not self.adaptive_reception:
            return super().refine_and_clear(ch)
        iterations=1 if self.replan_measurements else 8
        for _ in range(iterations):
            if ch in self.cleared:
                return
            self.refinements[ch]=self.refinements.get(ch,0)+1
            if self.refinements[ch]>12:
                return super().refine_and_clear(ch)
            poly=self.polygons[ch]
            current=self.client.ledger.position
            safe=nearest_operating_point(poly,current)
            if safe is not None:
                if self.client.action('/clear',safe,ch)['clear_result']!='success':
                    raise ProtocolError('E operating-region certificate failed')
                self.record(reason='E_operating_region_clear',channel=ch,point=safe)
                return
            center,radius=minimum_circle(poly)
            old=self.optical_attempts.get(ch)
            if 20<radius<=self.optical_trial and (old is None or math.dist(center,old)>10):
                self.optical_attempts[ch]=center
                if self.client.action('/clear',center,ch)['clear_result']=='success':
                    return
                current=self.client.ledger.position
            previous=[q for q,_ in self.bearings[ch]]
            choice=(area_rollout_station(poly,current,previous,self.lateral,self.adaptive_reception,self.area_rollout)
                    if self.area_rollout or self.adaptive_reception
                    else time_rollout_station(poly,current,previous))
            if choice is None:
                return super().refine_and_clear(ch)
            self.record(reason='E_replan_after_measurement',channel=ch,**choice)
            self.measure(choice['point'],ch)
            if self.replan_measurements and ch not in self.cleared and self.commit_radius>0:
                if minimum_circle(self.polygons[ch])[1]<=self.commit_radius:
                    return self.refine_and_clear(ch)
        # Parent's main loop now considers all targets and remaining search sites,
        # instead of committing to finish the current source before replanning.

    def run(self):
        if self.route_hysteresis<=0:
            return super().run()
        self.client.action('/enter')
        self.scan_stop((0.,0.),force=True)
        left=list(self.sites[1:])
        previous=[]
        for decision in range(180):
            self.try_clear_here()
            pending=sorted(set(self.polygons)-self.cleared)
            if self.search_complete or len(self.cleared)==16:
                left=[]
            if self.prune_stations:
                for i in range(len(left)-1,-1,-1):
                    if coverage_partition(self.search_stations+left[:i]+left[i+1:],9)['complete']:
                        left.pop(i)
            if not left and not pending:
                return self.finish()
            position=self.client.ledger.position
            eligible=[ch for ch in pending if not left or self.info(ch)[1]<=self.max_region]
            keys=[('scan',tuple(q)) for q in left]+[('clear',ch) for ch in eligible]
            points=list(left)+[nearest_operating_point(self.polygons[ch],position) or self.info(ch)[0]
                               for ch in eligible]
            proposal=open_route(position,points)
            retained=[keys.index(k) for k in previous if k in keys]
            for i in proposal:
                if i not in retained:
                    alternatives=[retained[:j]+[i]+retained[j:] for j in range(len(retained)+1)]
                    retained=min(alternatives,key=lambda order:route_length(position,points,order))
            new_cost=route_length(position,points,proposal)
            old_cost=route_length(position,points,retained)
            order=retained if old_cost<=new_cost+5*self.route_hysteresis else proposal
            previous=[keys[i] for i in order]
            action=keys[order[0]]
            self.record(reason='E_route_hysteresis',predicted_move_s=route_length(position,points,order)/5,
                        alternative_move_s=new_cost/5,first_action=action)
            if action[0]=='scan':
                left.remove(action[1])
                self.scan_stop(action[1],force=True)
            else:
                self.refine_and_clear(action[1])
                self.scan_stop(self.client.ledger.position)
        raise ProtocolError('E planning guard reached')
