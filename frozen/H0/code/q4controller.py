"""Feedback-only H family. Deliberately does not subclass any Q3 controller."""
import math
from geometry import outer_disk,clip_bearing,minimum_circle
from local_geometry import nearest_operating_point
from routing import open_route,through_operating_point
from directional_geometry import (DirectionalCoverage,skeleton,paired_probe,
                                  apply_paired_negative,optical_strip)
from q3client import ProtocolError


class Q4Controller:
    def __init__(self,client,options):
        self.client=client;self.options=dict(options)
        self.polygons={};self.positives={};self.negatives={j:[] for j in range(1,21)}
        self.empty=set();self.rounds={};self.optical_tried={};self.measured=set()
        self.coverage=DirectionalCoverage()
        names=['inner_count','outer_count','inner_radius','outer_radius','inner_phase','outer_phase']
        self.sites=skeleton(**{k:options[k] for k in names})
        if not self.coverage.prove(self.sites)['complete']:
            raise ProtocolError('Q4 skeleton lacks a directional coverage certificate')
        self.remaining=self.sites[1:];self.since_search=0;self.phase='initial'

    @property
    def cleared(self):return self.client.ledger.cleared

    def record(self,reason,**fields):
        self.client.journal.append(dict(event='policy',reason=reason,**fields))

    def unknown(self):
        return sorted(set(range(1,21))-set(self.polygons)-self.cleared-self.empty)

    def info(self,ch):return minimum_circle(self.polygons[ch])

    def measure(self,point,ch,role):
        point=tuple(point)
        self.record('q4_action_role',role=role,path='/measure',channel=ch,point=point)
        response=self.client.action('/measure',point,ch)
        self.measured.add((ch,point))
        kind=response['measure_result']
        if kind=='no_signal':
            if ch not in self.cleared:self.negatives[ch].append(point)
        elif kind=='near':
            self.clear(point,ch,'near')
        else:
            poly=clip_bearing(self.polygons.get(ch,outer_disk()),point,response['svd_deg'])
            if not poly:raise ProtocolError('Q4 positive observations produced empty region')
            self.polygons[ch]=poly
            self.positives.setdefault(ch,[]).append((point,response['svd_deg']))
            self.record('q4_positive_region',channel=ch,polygon=poly,
                        virtual_time_s=self.client.ledger.virtual_time)
        return kind

    def clear(self,point,ch,role):
        self.record('q4_action_role',role=role,path='/clear',channel=ch,point=point)
        return self.client.action('/clear',point,ch)['clear_result']=='success'

    def refresh(self):
        if len(set(self.polygons)|self.cleared)==16:
            self.remaining=[];return
        for ch in self.unknown():
            if self.coverage.prove(self.negatives[ch])['complete']:self.empty.add(ch)
        if not self.unknown():self.remaining=[]

    def scan(self,point):
        self.phase='search';self.since_search=0
        channels=self.unknown()
        channels.sort(key=lambda ch:(ch!=self.client.ledger.channel,ch))
        for ch in channels:
            if len(set(self.polygons)|self.cleared)==16:break
            if (ch,tuple(point)) not in self.measured:self.measure(point,ch,'search')
        self.refresh()

    def other_tasks(self,ch):
        return list(self.remaining)+[self.info(j)[0] for j in sorted(set(self.polygons)-self.cleared-{ch})]

    def guaranteed_clear(self,ch):
        if ch in self.cleared:return True
        p=self.client.ledger.position;poly=self.polygons[ch]
        q=nearest_operating_point(poly,p)
        if q is None:return False
        if self.options['through_clear']:
            other=self.other_tasks(ch)
            if other:q=through_operating_point(poly,p,other[open_route(q,other)[0]])
        if not self.clear(q,ch,'guaranteed'):
            raise ProtocolError('Q4 guaranteed clearing certificate failed')
        return True

    def fallback(self,ch):
        station,bearing=self.positives[ch][0];points=optical_strip(station,bearing)
        started=self.client.ledger.virtual_time;attempts=0
        self.record('q4_fallback_begin',channel=ch,points=len(points))
        while points:
            i=min(range(len(points)),key=lambda i:math.dist(points[i],self.client.ledger.position))
            attempts+=1
            if self.clear(points.pop(i),ch,'fallback'):
                self.record('q4_fallback_end',channel=ch,attempts=attempts,
                            virtual_cost=self.client.ledger.virtual_time-started)
                return
        raise ProtocolError('Q4 finite optical strip exhausted without success')

    def localize(self,ch):
        if self.guaranteed_clear(ch):return
        r=self.info(ch)[1]
        if 20<r<=self.options['optical_trial']:
            center=self.info(ch)[0];old=self.optical_tried.get(ch)
            if old is None or math.dist(old,center)>10:
                self.optical_tried[ch]=center
                if self.clear(center,ch,'optical_trial'):return
        self.rounds[ch]=self.rounds.get(ch,0)+1
        if self.rounds[ch]>self.options['max_local_rounds']:
            return self.fallback(ch)
        before=list(self.polygons[ch]);station,bearing=self.positives[ch][0]
        probe=paired_probe(before,station,bearing,self.options['probe_b'],self.options['probe_fraction'])
        if not probe['geometry_valid']:
            self.record('q4_pair_geometry_rejected',channel=ch,probe=probe)
            return self.fallback(ch)
        endpoints=[probe['plus'],probe['minus']]
        endpoints.sort(key=lambda q:math.dist(q,self.client.ledger.position))
        if all((ch,tuple(q)) in self.measured for q in endpoints):
            return self.fallback(ch)
        results=[];observed=[]
        for q in endpoints:
            kind=self.measure(q,ch,'paired_probe');results.append(kind);observed.append(q)
            if ch in self.cleared or self.guaranteed_clear(ch):return
        if results==['no_signal','no_signal']:
            witness={**probe,'results':results,'observed_order':observed,
                     'before_polygon':before,'channel':ch,'positive_station':station}
            updated=apply_paired_negative(self.polygons[ch],witness)
            if not updated:raise ProtocolError('Q4 paired witness produced empty region')
            self.polygons[ch]=updated
            self.record('q4_paired_negative_clip',witness=witness,polygon=updated,
                        virtual_time_s=self.client.ledger.virtual_time)
            self.guaranteed_clear(ch)

    def finish(self):
        self.refresh()
        if not 10<=len(self.cleared)<=16 or set(self.polygons)-self.cleared:
            raise ProtocolError('Q4 known sources remain or invalid clear count')
        if len(self.cleared)==16:kind='q4_sixteen_actual_successes'
        else:
            if self.unknown():raise ProtocolError('Q4 unproved unknown channel')
            kind='q4_actual_directional_local_hull'
        certificate=dict(kind=kind,cleared_channels=sorted(self.cleared),
                         empty_channels=sorted(set(range(1,21))-self.cleared))
        self.record('completion_proved',certificate=certificate)
        self.client.action('/exit')

    def run(self):
        self.client.action('/enter');self.scan((0.,0.))
        for decision in range(500):
            self.refresh()
            pending=sorted(set(self.polygons)-self.cleared)
            if not pending and not self.remaining:return self.finish()
            if not self.remaining and self.unknown() and len(set(self.polygons)|self.cleared)<16:
                raise ProtocolError('Q4 skeleton exhausted with unproved directional coverage')
            p=self.client.ledger.position
            force_search=self.remaining and self.since_search>=self.options['max_tasks_before_search']
            tasks=[('scan',i) for i in range(len(self.remaining))]
            points=list(self.remaining)
            if not force_search:
                tasks += [('source',ch) for ch in pending]
                points += [nearest_operating_point(self.polygons[ch],p) or self.info(ch)[0] for ch in pending]
            if not tasks:raise ProtocolError('Q4 no legal progress task')
            first=open_route(p,points)[0];kind,index=tasks[first]
            self.record('q4_route_decision',decision=decision,kind=kind,index=index,
                        sources=len(pending),search_stops=len(self.remaining),forced_search=bool(force_search))
            if kind=='scan':self.scan(self.remaining.pop(index))
            else:
                self.since_search+=1;self.phase='localization';self.localize(index)
        raise ProtocolError('Q4 finite planning guard reached')
