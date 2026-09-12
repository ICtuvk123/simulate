"""F structural candidates, using only accepted observations and public rules."""
import math

from controller import BaselineController
from replanning import ReplanningController, MaximumSourcesKnown, area_center
from optimized import open_route, route_length
from geometry import minimum_circle, diameter, clip_bearing
from local_geometry import nearest_operating_point
from reception_geometry import reception_safe
from structural_geometry import (positive_negative_clip,joint_reception_safe,
    convex_hull,exclude_inner_disk,bearing_strip_grid)
from coverage import coverage_partition
from q3client import ProtocolError


class ObservedClient:
    """Pass through unchanged requests; use only successful returned feedback."""
    def __init__(self,client,controller):
        self.raw=client;self.controller=controller
    def __getattr__(self,name):
        return getattr(self.raw,name)
    def action(self,path,position=None,channel=None):
        known=(channel in self.controller.polygons and channel not in self.raw.ledger.cleared)
        result=self.raw.action(path,position,channel)
        if (known and path=='/clear' and result.get('accepted') is True
                and result.get('clear_result')=='no_target_in_range'):
            self.controller.optical_failure(tuple(position),channel)
        return result


def greedy_tail(start,points):
    remaining=list(points);p=start;distance=0.
    while remaining:
        i=min(range(len(remaining)),key=lambda i:math.dist(p,remaining[i]))
        q=remaining.pop(i);distance+=math.dist(p,q);p=q
    return distance/5


class StructuralController(ReplanningController):
    def __init__(self,client,negative_halfplanes=True,joint_history=True,
                 task_search=False,tail_cost=False,optical_exclusions=False,
                 safe_shared=False,strip_fallback=True,**options):
        super().__init__(client,**options)
        self.negative_halfplanes=bool(negative_halfplanes)
        self.joint_history=bool(joint_history)
        self.task_search=bool(task_search)
        self.tail_cost=bool(tail_cost)
        self.optical_exclusions=bool(optical_exclusions)
        self.safe_shared=bool(safe_shared)
        self.strip_fallback=bool(strip_fallback)
        self.negatives={ch:[] for ch in range(1,21)}
        self.pieces={};self.exclusions={};self.remaining_sites=[]
        self.empty_proved=set();self.cover_cache={};self.mask_cache={}
        self.full_mask=(1<<len(self.area_points))-1
        self.client=ObservedClient(client,self)

    def install_region(self,ch,parts,reason):
        parts=[p for p in parts if p]
        if not parts:
            raise ProtocolError('F inconsistent public observations: empty region')
        self.pieces[ch]=parts
        self.polygons[ch]=parts[0] if len(parts)==1 else convex_hull([v for p in parts for v in p])
        c,r=minimum_circle(self.polygons[ch])
        self.record(reason=reason,channel=ch,polygon=self.polygons[ch],pieces=parts,
                    center=c,radius=r,virtual_time_s=self.client.ledger.virtual_time)

    def optical_failure(self,q,ch):
        self.exclusions.setdefault(ch,[]).append(q)
        if self.optical_exclusions:
            parts=exclude_inner_disk(self.pieces.get(ch,[self.polygons[ch]]),q)
            self.install_region(ch,parts,'F_optical_negative_region')

    def measure(self,point,channel):
        before=len(set(self.polygons)|self.cleared)
        parts=self.pieces.get(channel)
        response=BaselineController.measure(self,point,channel)
        kind=response['measure_result']
        if channel not in self.cleared:
            if kind=='no_signal':
                self.negatives[channel].append(tuple(point))
            if channel in self.polygons:
                if kind=='direction':
                    parts=([clip_bearing(p,point,response['svd_deg']) for p in parts]
                           if parts else [self.polygons[channel]])
                elif not parts:
                    parts=[self.polygons[channel]]
                if self.negative_halfplanes:
                    positives=[q for q,_ in self.bearings[channel]]
                    parts=[positive_negative_clip(p,positives,self.negatives[channel]) for p in parts]
                self.install_region(channel,parts,'F_feedback_region')
        if self.eager_count_stop and before<16 and len(set(self.polygons)|self.cleared)==16:
            self.search_complete=True
            self.record(reason='F_public_maximum_discovered_stop_unknown_scan')
            raise MaximumSourcesKnown()
        return response

    def reception_ok(self,poly,q,previous):
        return (joint_reception_safe if self.joint_history else reception_safe)(poly,q,previous)

    def tail_points(self,ch):
        sites=self.remaining_sites if self.task_search else [q for q in self.sites[1:]
              if all(math.dist(q,p)>1e-5 for p in self.search_stations)]
        if self.search_complete:
            sites=[]
        return list(sites)+[self.info(j)[0] for j in sorted(set(self.polygons)-self.cleared-{ch})]

    def choose_station(self,ch,poly,current,previous):
        center,radius=minimum_circle(poly);centroid=area_center(poly)
        _,a,b=diameter(poly);length=max(math.dist(a,b),1e-9)
        normal=(-(b[1]-a[1])/length,(b[0]-a[0])/length)
        candidates=[]
        for c in (center,centroid):
            for offset in sorted(set((15.,40.,80.,min(400.,max(100.,radius*self.lateral))))):
                for sign in (-1,1):
                    candidates.append((c[0]+sign*offset*normal[0],c[1]+sign*offset*normal[1]))
            travel=math.dist(current,c)
            if travel>1e-8:
                for distance in (40.,100.,200.,400.):
                    if distance<travel:
                        candidates.append(tuple(c[k]+(current[k]-c[k])*distance/travel for k in (0,1)))
        for fraction in (.25,.5,.75):
            c=tuple(current[k]+fraction*(center[k]-current[k]) for k in (0,1))
            for offset in (40.,100.,200.,400.):
                for sign in (-1,1):
                    candidates.append((c[0]+sign*offset*normal[0],c[1]+sign*offset*normal[1]))
        if self.joint_history:
            for i,s in enumerate(previous):
                for t in previous[i+1:]:
                    candidates.append(((s[0]+t[0])/2,(s[1]+t[1])/2))
        sources=[center]+[((v[0]+center[0])/2,(v[1]+center[1])/2)
                  for v in poly[::max(1,len(poly)//6)]]
        if self.optical_exclusions:
            from geometry import contains
            sources=[p for p in sources if any(contains(piece,p) for piece in self.pieces[ch])]
            if not sources:
                sources=[tuple(sum(v[k] for v in piece)/len(piece) for k in (0,1))
                         for piece in self.pieces[ch]][:12]
        tail=self.tail_points(ch) if self.tail_cost else []
        best=None
        for q in candidates:
            if any(math.dist(q,p)<.05 for p in previous) or not self.reception_ok(poly,q,previous):
                continue
            expected=0.;success=0.;rmaxall=0.
            for source in sources:
                if math.dist(q,source)<=5:
                    expected+=5+greedy_tail(q,tail);success+=1;continue
                worst=0.;rmax=0.
                for error in (-1.005,0.,1.005):
                    beta=math.degrees(math.atan2(source[1]-q[1],source[0]-q[0]))+error
                    updated=clip_bearing(poly,q,beta)
                    if self.optical_exclusions:
                        updated=convex_hull([v for piece in self.pieces[ch]
                                            for v in clip_bearing(piece,q,beta)])
                    if not updated:
                        continue
                    c,r=minimum_circle(updated)
                    cost=max(0.,math.dist(q,c)-max(0.,20-r))/5+5
                    if r>20:
                        cost+=6+min(160.,2*r)/5
                    cost+=greedy_tail(c,tail)
                    worst=max(worst,cost);rmax=max(rmax,r)
                expected+=worst;success+=int(rmax<=20);rmaxall=max(rmaxall,rmax)
            entry=(math.dist(current,q)/5+6+expected/len(sources),-success,rmaxall,q)
            if best is None or entry<best:
                best=entry
        if best is None:
            return None
        return dict(point=best[3],estimated_remaining_s=best[0],
                    geometric_success_fraction=-best[1]/len(sources),sampled_worst_radius=best[2],
                    tail_task_count=len(tail))

    def refine_and_clear(self,ch):
        if not self.joint_history and not self.tail_cost and not self.optical_exclusions:
            return super().refine_and_clear(ch)
        for _ in range(1 if self.replan_measurements else 8):
            if ch in self.cleared:
                return
            self.refinements[ch]=self.refinements.get(ch,0)+1
            if self.refinements[ch]>12:
                return super().refine_and_clear(ch)
            poly=self.polygons[ch];current=self.client.ledger.position
            safe=nearest_operating_point(poly,current)
            if safe is not None:
                if self.client.action('/clear',safe,ch)['clear_result']!='success':
                    raise ProtocolError('F operating-region certificate failed')
                return
            center,radius=minimum_circle(poly);old=self.optical_attempts.get(ch)
            if 20<radius<=self.optical_trial and (old is None or math.dist(center,old)>10):
                self.optical_attempts[ch]=center
                if self.client.action('/clear',center,ch)['clear_result']=='success':
                    return
                current=self.client.ledger.position;poly=self.polygons[ch]
            previous=[q for q,_ in self.bearings[ch]]
            choice=self.choose_station(ch,poly,current,previous)
            if choice is None:
                return super().refine_and_clear(ch)
            self.record(reason='F_global_tail_station' if self.tail_cost else 'F_information_station',channel=ch,**choice)
            self.measure(choice['point'],ch)
            if ch not in self.cleared and self.commit_radius>0 and self.info(ch)[1]<=self.commit_radius:
                return self.refine_and_clear(ch)

    def proves(self,points):
        key=tuple(sorted(set(tuple(p) for p in points)))
        if key not in self.cover_cache:
            mask=0
            for p in key:
                if p not in self.mask_cache:
                    self.mask_cache[p]=self.point_mask(p)
                mask|=self.mask_cache[p]
            self.cover_cache[key]=(mask==self.full_mask and coverage_partition(key,12)['complete'])
        return self.cover_cache[key]

    def unknown_channels(self):
        return sorted(set(range(1,21))-set(self.polygons)-self.cleared-self.empty_proved)

    def refresh_search(self):
        for ch in self.unknown_channels():
            if self.proves(self.negatives[ch]):
                self.empty_proved.add(ch)
        if len(set(self.polygons)|self.cleared)==16 or not self.unknown_channels():
            self.search_complete=True
            self.remaining_sites=[]

    def prune_with_actual_feedback(self):
        unknown=self.unknown_channels()
        for i in range(len(self.remaining_sites)-1,-1,-1):
            others=self.remaining_sites[:i]+self.remaining_sites[i+1:]
            if all(self.proves(self.negatives[ch]+others) for ch in unknown):
                removed=self.remaining_sites.pop(i)
                self.record(reason='F_planned_station_replaced_after_actual_feedback',point=removed,
                            actual_negative_counts={ch:len(self.negatives[ch]) for ch in unknown})

    def useful_shared(self,point):
        if not self.known_scan:
            return
        for ch in sorted(set(self.polygons)-self.cleared,key=lambda ch:(ch!=self.client.ledger.channel,ch)):
            center,radius=self.info(ch);history=self.bearings[ch]
            if radius<20 or math.dist(center,point)>self.shared_limit or any(math.dist(point,p)<120 for p,_ in history):
                continue
            now=math.atan2(point[1]-center[1],point[0]-center[0])
            sine=max(abs(math.sin(now-math.atan2(p[1]-center[1],p[0]-center[0]))) for p,_ in history)
            predicted=math.dist(center,point)*math.tan(math.radians(1.01))/max(sine,.02)
            if sine>.3 and (predicted<self.near_prediction or predicted<self.bearing_factor*radius):
                if self.safe_shared and not self.reception_ok(self.polygons[ch],point,[p for p,_ in history]):
                    self.record(reason='F_shared_unproved_reception_skipped',channel=ch);continue
                response=self.measure(point,ch)
                self.record(reason='F_shared_feedback',channel=ch,result=response['measure_result'])

    def scan_stop(self,point,force=False):
        if not self.task_search:
            if not self.safe_shared:
                return super().scan_stop(point,force)
            enabled=self.known_scan;self.known_scan=False
            super().scan_stop(point,force);self.known_scan=enabled
            return self.useful_shared(point)
        self.refresh_search();unknown=self.unknown_channels()
        channels=[];replaced=None
        if not self.search_complete:
            if force:
                channels=[ch for ch in unknown if not self.proves(self.negatives[ch]+self.remaining_sites)]
                # Origin is also needed for interior coverage; do not skip it
                # merely because uncertain future targets might be visited.
                if not self.search_stations:
                    channels=unknown
            else:
                # Completing even a tiny residual hole is worthwhile: transfer
                # an otherwise necessary future channel test to this stop.
                channels=[ch for ch in unknown if self.proves(self.negatives[ch]+[point])]
                choices=[]
                for i,site in enumerate(self.remaining_sites):
                    others=self.remaining_sites[:i]+self.remaining_sites[i+1:]
                    needed=[ch for ch in unknown if not self.proves(self.negatives[ch]+others)]
                    if needed and all(self.proves(self.negatives[ch]+[point]+others) for ch in needed):
                        pending=[self.info(ch)[0] for ch in sorted(set(self.polygons)-self.cleared)]
                        before=greedy_tail(point,self.remaining_sites+pending)
                        after=greedy_tail(point,others+pending)
                        # These same channel observations move from the removed
                        # station to the current stop: no additional RF count.
                        choices.append((before-after,-len(needed),i,needed))
                if choices:
                    gain,_,index,needed=max(choices)
                    if gain>0:
                        channels=sorted(set(channels)|set(needed));replaced=self.remaining_sites[index]
        channels.sort(key=lambda ch:(ch!=self.client.ledger.channel,ch))
        for ch in channels:
            if ch in self.cleared or ch in self.polygons:
                continue
            try:
                self.measure(point,ch)
            except MaximumSourcesKnown:
                break
        if force:
            self.search_stations.append(tuple(point))
        if channels:
            self.record(reason='F_channel_search_stop',point=point,channels=channels,
                        dedicated=force,proposed_replacement=replaced)
        self.refresh_search()
        self.prune_with_actual_feedback()
        self.useful_shared(point)

    def optical_fallback(self,ch):
        if not self.strip_fallback:
            return super().optical_fallback(ch)
        station,bearing=self.bearings[ch][0]
        points=bearing_strip_grid(station,bearing)
        self.record(reason='F_finite_bearing_strip_fallback',channel=ch,candidate_count=len(points))
        # Keep all 183 points; the public bearing gives an independent fallback
        # even if later numerical refinements were unhelpful. Budget is checked
        # by Client on every action, using enter's actual remaining duration.
        while points:
            i=min(range(len(points)),key=lambda i:math.dist(points[i],self.client.ledger.position))
            if self.client.action('/clear',points.pop(i),ch)['clear_result']=='success':
                return
        raise ProtocolError('F finite strip cover exhausted without success')

    def finish(self):
        if not self.task_search:
            return super().finish()
        self.refresh_search()
        if not 10<=len(self.cleared)<=16 or set(self.polygons)-self.cleared:
            raise ProtocolError('F incomplete known-source clearing')
        if len(self.cleared)==16:
            certificate={'kind':'sixteen_cleared_public_upper_bound'}
        else:
            if self.unknown_channels():
                raise ProtocolError('F unproved per-channel search gap')
            certificate={'kind':'adaptive_quadtree_square_containment','max_depth':12,
                         'actual_negative_counts':{ch:len(self.negatives[ch]) for ch in self.empty_proved}}
        certificate.update(cleared_channels=sorted(self.cleared),
                           empty_channels=sorted(set(range(1,21))-self.cleared),all_discovered_cleared=True)
        self.completion_certificate=certificate
        self.record(reason='completion_proved',certificate=certificate)
        self.client.action('/exit');return certificate

    def run(self):
        if not self.task_search:
            return super().run()
        self.client.action('/enter');self.remaining_sites=list(self.sites[1:])
        self.scan_stop((0.,0.),force=True)
        for decision in range(220):
            self.try_clear_here();self.refresh_search()
            pending=sorted(set(self.polygons)-self.cleared)
            if not self.remaining_sites and not pending:
                return self.finish()
            position=self.client.ledger.position
            eligible=[ch for ch in pending if not self.remaining_sites or self.info(ch)[1]<=self.max_region]
            actions=[('scan',i) for i in range(len(self.remaining_sites))]+[('clear',ch) for ch in eligible]
            points=list(self.remaining_sites)+[nearest_operating_point(self.polygons[ch],position) or self.info(ch)[0]
                                               for ch in eligible]
            if not actions:
                raise ProtocolError('F unresolved task without a feasible action')
            order=open_route(position,points);kind,index=actions[order[0]]
            self.record(reason='F_joint_remaining_route',first_action=(kind,index),
                        targets=len(eligible),search_stops=len(self.remaining_sites))
            if kind=='scan':
                point=self.remaining_sites.pop(index);self.scan_stop(point,force=True)
            else:
                self.refine_and_clear(index);self.scan_stop(self.client.ledger.position)
        raise ProtocolError('F planning guard reached')
