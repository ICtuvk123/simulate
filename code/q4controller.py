"""Feedback-only H family. Deliberately does not subclass any Q3 controller."""
import math
from geometry import outer_disk,clip_bearing,minimum_circle
from local_geometry import nearest_operating_point
from routing import open_route,refined_open_route,route_length,through_operating_point
from itertools import combinations
from directional_geometry import (DirectionalCoverage,skeleton,paired_probe,
                                  apply_paired_negative,optical_strip)
from q3client import ProtocolError
from lookahead import choose_pair,shared_information_value,hypotheses,single_probe_cost
from compact_optical import choose_cover,verify_cover
from task_routing import area_centroid,open_task_route
from negative_cells import contract as contract_negative_history
from reused_negative import choose_reused_probe,apply_reused_negative
from partial_optical import choose_partial,EXCLUSION_RADIUS
from certificate_search import CertificateSearch


class Q4Controller:
    def __init__(self,client,options):
        self.client=client;self.options=dict(options)
        self.polygons={};self.positives={};self.negatives={j:[] for j in range(1,21)}
        self.empty=set();self.rounds={};self.optical_tried={};self.measured=set()
        self.optical_exclusions={};self.partial_counts={};self.partial_versions={}
        self.coverage=DirectionalCoverage()
        names=['inner_count','outer_count','inner_radius','outer_radius','inner_phase','outer_phase']
        self.sites=skeleton(**{k:options[k] for k in names})
        if not self.coverage.prove(self.sites)['complete']:
            raise ProtocolError('Q4 skeleton lacks a directional coverage certificate')
        self.remaining=self.sites[1:];self.since_search=0;self.phase='initial'
        self.certificate_search=(CertificateSearch(self.sites,self.options)
                                 if self.options.get('certificate_replace') else None)

    @property
    def cleared(self):return self.client.ledger.cleared

    def record(self,reason,**fields):
        self.client.journal.append(dict(event='policy',reason=reason,**fields))

    def unknown(self):
        return sorted(set(range(1,21))-set(self.polygons)-self.cleared-self.empty)

    def info(self,ch):return minimum_circle(self.polygons[ch])

    def plan_route(self,p,points):
        solver=refined_open_route if self.options.get('route_refine') else open_route
        return solver(p,points)

    def route_source_point(self,ch,p):
        safe=nearest_operating_point(self.polygons[ch],p)
        if safe is not None:return safe
        if self.options.get('route_probe') or self.options.get('task_route'):
            other=self.other_tasks(ch)
            anchor=min(other,key=lambda q:math.dist(q,self.info(ch)[0])) if other else None
            selected=choose_pair(self.polygons[ch],p,self.positives[ch],self.negatives[ch],
                                 [q for j,q in self.measured if j==ch],self.options,anchor,
                                 self.optical_exclusions.get(ch,[]))
            if selected:return selected['endpoints'][0]
        if self.options.get('route_centroid'):
            return area_centroid(self.polygons[ch])
        return self.info(ch)[0]

    def scan_for_forecast_complement(self):
        """Invest an actual scan when known future stops could jointly save a site.

        Forecast centers never remove fallback stations and never enter the
        negative history. Only later real observations can justify removal.
        """
        if not self.options.get('forecast_search') or not self.remaining:return
        self.refresh();unknown=self.unknown()
        if not unknown or not self.remaining:return
        p=tuple(self.client.ledger.position)
        forecasts=[self.info(ch)[0] for ch in sorted(set(self.polygons)-self.cleared)
                   if self.info(ch)[1]<=self.options.get('forecast_radius',120.)]
        forecasts=sorted(forecasts,key=lambda q:math.dist(p,q))[:3]
        if not forecasts:return
        points=self.remaining+forecasts
        before=route_length(p,points,self.plan_route(p,points))/5
        needed=[ch for ch in unknown if (ch,p) not in self.measured]
        if not needed:return
        near=sorted(range(len(self.remaining)),key=lambda i:math.dist(p,self.remaining[i]))[:4]
        selected=None
        for count in (1,2):
            for indices in combinations(near,count):
                others=[q for i,q in enumerate(self.remaining) if i not in indices]
                proposed=others+forecasts
                gain=before-route_length(p,proposed,self.plan_route(p,proposed))/5
                # Pay for scans at current AND all proposed future stops. The
                # saved dedicated scans also count; this is planning only.
                gain+=6*(len(unknown)*count-len(needed)-len(unknown)*len(forecasts))
                if gain<=0 or (selected is not None and gain<=selected[0]):continue
                if all(self.coverage.prove(self.negatives[ch]+others+[p]+forecasts)['complete']
                       for ch in unknown):selected=(gain,indices)
        if selected is None:return
        self.record('q4_forecast_scan_plan',point=p,forecasts=forecasts,
                    tentative_removed=[self.remaining[i] for i in selected[1]],
                    predicted_saved_s=selected[0],fallback_stations_retained=True)
        for ch in sorted(needed,key=lambda ch:(ch!=self.client.ledger.channel,ch)):
            if len(set(self.polygons)|self.cleared)==16:break
            if ch in self.unknown():self.measure(p,ch,'forecast_investment_scan')
        self.refresh()

    def orient_initial_skeleton(self):
        if not self.options.get('adapt_rotation') or not self.remaining:return
        p=self.client.ledger.position
        targets=[self.info(ch)[0] for ch in sorted(set(self.polygons)-self.cleared)]
        period=360/self.options['inner_count'];step=self.options.get('rotation_step',5.)
        angles=[k*step for k in range(math.ceil(period/step)) if k*step<period]
        angles+= [math.degrees(math.atan2(q[1],q[0]))%period for q in targets]
        points=self.remaining+targets
        baseline=route_length(p,points,self.plan_route(p,points));best=(baseline,0.,self.remaining)
        for angle in sorted(set(angles)):
            a=math.radians(angle);c,s=math.cos(a),math.sin(a)
            proposal=[(x*c-y*s,x*s+y*c) for x,y in self.remaining]
            combined=proposal+targets;length=route_length(p,combined,self.plan_route(p,combined))
            if length<best[0]-1e-6 and all(self.coverage.prove(self.negatives[ch]+proposal)['complete'] for ch in self.unknown()):
                best=(length,angle,proposal)
        self.remaining=list(best[2])
        self.record('q4_observed_tasks_ring_rotation',angle=best[1],predicted_move_saved_s=(baseline-best[0])/5,
                    future_not_in_exit_certificate=True)

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
        if (self.options.get('negative_cells') and ch in self.polygons and ch not in self.cleared):
            contraction=contract_negative_history(self.polygons[ch],self.positives[ch],self.negatives[ch],
                                                   self.options.get('negative_cell_count',24))
            if contraction:
                self.polygons[ch]=contraction['polygon']
                self.record('q4_negative_history_clip',channel=ch,**contraction,
                            virtual_time_s=self.client.ledger.virtual_time)
        if self.certificate_search:
            self.certificate_search.observe(ch,point)
            if role=='paired_probe':self.certificate_search.at_actual_stop(self)
        return kind

    def clear(self,point,ch,role):
        self.record('q4_action_role',role=role,path='/clear',channel=ch,point=point)
        success=self.client.action('/clear',point,ch)['clear_result']=='success'
        if not success and self.options.get('partial_optical') and ch in self.polygons and ch not in self.cleared:
            # action() only returns after HTTP and accepted validation. Keep
            # holes separately; the reliable convex outer region is unchanged.
            event=self.client.ledger.events[-1]
            exclusion=dict(point=tuple(point),radius=EXCLUSION_RADIUS,
                           request_id=event['request_id'])
            self.optical_exclusions.setdefault(ch,[]).append(exclusion)
            self.record('q4_actual_optical_exclusion',channel=ch,role=role,
                        positive_version=len(self.positives.get(ch,[])),
                        convex_outer_region_unchanged=True,**exclusion)
        if self.certificate_search and role in ('guaranteed','compact_optical','optical_trial','lookahead_optical'):
            self.certificate_search.at_actual_stop(self)
        return success

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
            if self.certificate_search and not self.certificate_search.needs(ch,point):
                self.record('q4_certificate_search_scan_skipped',channel=ch,point=point,
                            future_stations_only_in_plan=True)
                continue
            if (ch,tuple(point)) not in self.measured:self.measure(point,ch,'search')
        self.share_at_actual_station(point)
        self.refresh()

    def share_at_actual_station(self,point):
        if not self.options.get('shared_bearing'):return
        # Unknown-channel scanning leaves us at this actual station. Never use
        # a forecast stop as an observation or a certificate station.
        if math.dist(point,self.client.ledger.position)>1e-8:return
        for _ in range(self.options.get('shared_limit_per_stop',3)):
            candidates=[]
            for ch in sorted(set(self.polygons)-self.cleared):
                if (ch,tuple(point)) in self.measured or self.info(ch)[1]<=20:continue
                value=shared_information_value(self.polygons[ch],point,self.positives[ch],self.negatives[ch],
                                               exclusions=self.optical_exclusions.get(ch,[]))
                if value and value['estimated_gain_s']>self.options.get('shared_gain_s',10.):
                    candidates.append((value['estimated_gain_s'],ch,value))
            if not candidates:break
            _,ch,value=max(candidates,key=lambda item:(item[0],-item[1]))
            self.record('q4_shared_information_rank',channel=ch,point=point,**value)
            self.measure(point,ch,'shared_bearing')
            if ch not in self.cleared and all(math.dist(point,v)<=20-1e-5 for v in self.polygons[ch]):
                if not self.clear(point,ch,'shared_in_place'):
                    raise ProtocolError('Q4 shared in-place guarantee failed')

    def other_tasks(self,ch):
        return list(self.remaining)+[self.info(j)[0] for j in sorted(set(self.polygons)-self.cleared-{ch})]

    def replace_from_actual_stop(self):
        """Transfer required unknown-channel scans to the actual current stop.

        Geometry with future stations only ranks a plan. A station group is
        removed only after the actual responses preserve remaining feasibility.
        """
        if not self.options.get('replace_search') or not self.remaining:return
        self.refresh();unknown=self.unknown()
        if not unknown or not self.remaining:return
        p=tuple(self.client.ledger.position)
        pending=[self.info(ch)[0] for ch in sorted(set(self.polygons)-self.cleared)]
        points=self.remaining+pending
        baseline=route_length(p,points,self.plan_route(p,points))/5+6*len(unknown)*len(self.remaining)
        near=sorted(range(len(self.remaining)),key=lambda i:math.dist(p,self.remaining[i]))[:self.options.get('replacement_candidates',4)]
        best=None
        for count in range(1,self.options.get('replacement_group',1)+1):
            for indices in combinations(near,count):
                others=[q for i,q in enumerate(self.remaining) if i not in indices]
                needed=[];valid=True
                for ch in unknown:
                    if not self.coverage.prove(self.negatives[ch]+others)['complete']:
                        needed.append(ch)
                        if not self.coverage.prove(self.negatives[ch]+others+[p])['complete']:
                            valid=False;break
                if not valid:continue
                proposed=others+pending
                cost=route_length(p,proposed,self.plan_route(p,proposed))/5+6*(len(unknown)*len(others)+len(needed))
                if cost<baseline-1e-6 and (best is None or cost<best[0]):best=(cost,indices,others,needed)
        if best is None:return
        _,indices,others,needed=best
        removed=[self.remaining[i] for i in indices]
        for ch in sorted(needed,key=lambda ch:(ch!=self.client.ledger.channel,ch)):
            if len(set(self.polygons)|self.cleared)==16:break
            if ch in self.unknown() and (ch,p) not in self.measured:self.measure(p,ch,'replacement_search')
        self.refresh()
        if not self.remaining:return
        if all(self.coverage.prove(self.negatives[ch]+others)['complete'] for ch in self.unknown()):
            self.remaining=others
            self.record('q4_actual_stop_replaced_station_group',point=p,removed=removed,channels=needed,
                        predicted_saved_s=baseline-best[0],actual_negative_counts={ch:len(self.negatives[ch]) for ch in self.unknown()},
                        future_stations_only_in_plan=True)

    def guaranteed_clear(self,ch):
        if ch in self.cleared:return True
        p=self.client.ledger.position;poly=self.polygons[ch]
        q=nearest_operating_point(poly,p)
        if q is None:return False
        if self.options['through_clear']:
            other=self.other_tasks(ch)
            if other:q=through_operating_point(poly,p,other[self.plan_route(q,other)[0]])
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

    def try_compact_optical(self,ch,models,anchor,radio_cost,context):
        cover=choose_cover(self.polygons[ch],self.client.ledger.position,models,anchor,
                           self.options.get('compact_optical_points',4))
        if not cover or cover['estimated_remaining_s']>=radio_cost:return False
        if not verify_cover(cover['witness'],cover['points']):raise ProtocolError('Invalid compact optical cover')
        self.record('q4_compact_optical_cover',channel=ch,radio_alternative_s=radio_cost,context=context,**cover)
        for point in cover['points']:
            if self.clear(point,ch,'compact_optical'):return True
        raise ProtocolError('Certified compact optical cover exhausted without success')

    def execute_reused_probe(self,ch,selected,before):
        """Pay for one new RF; an earlier same-channel negative supplies its mate."""
        if ch in self.cleared:raise ProtocolError('Cannot reuse history after successful clearing')
        probe=selected['probe'];h=probe['historical_negative']
        if not any(math.dist(h,p)<1e-8 for p in self.negatives[ch]):
            raise ProtocolError('Historical endpoint lacks an actual same-channel negative')
        if not any(math.dist(probe['station'],s)<1e-8 and probe['bearing']==beta
                   for s,beta in self.positives[ch]):
            raise ProtocolError('Reused pair lacks an actual positive reception premise')
        kind=self.measure(selected['point'],ch,'reused_negative_probe')
        if ch in self.cleared:return
        if kind=='no_signal':
            witness=dict(probe,channel=ch,before_polygon=before,results=['no_signal','no_signal'],
                         historical_result='no_signal',new_result=kind)
            updated=apply_reused_negative(self.polygons[ch],witness)
            if not updated:raise ProtocolError('Asymmetric negative pair produced empty region')
            self.polygons[ch]=updated
            self.record('q4_reused_negative_clip',witness=witness,polygon=updated,
                        virtual_time_s=self.client.ledger.virtual_time)
        self.guaranteed_clear(ch)

    def partial_allowed(self,ch):
        version=len(self.positives.get(ch,[]))
        return (self.options.get('partial_optical',False)
                and self.partial_counts.get(ch,0)<self.options.get('partial_optical_total',4)
                and self.partial_versions.get((ch,version),0)<self.options.get('partial_optical_per_version',1))

    def try_partial_optical(self,ch,selected,anchor,context='before_pair'):
        if not self.partial_allowed(ch):return False
        exclusions=self.optical_exclusions.get(ch,[])
        models=hypotheses(self.polygons[ch],self.positives[ch],self.negatives[ch],
                          self.options.get('partial_optical_positions',25),exclusions)
        plan=choose_partial(self.polygons[ch],self.client.ledger.position,selected,models,
                            exclusions,self.options,anchor,int(ch!=self.client.ledger.channel))
        if plan is None:return False
        version=len(self.positives[ch]);key=(ch,version)
        self.partial_counts[ch]=self.partial_counts.get(ch,0)+1
        self.partial_versions[key]=self.partial_versions.get(key,0)+1
        self.record('q4_partial_optical_plan',channel=ch,positive_version=version,
                    trial_number=self.partial_counts[ch],context=context,**plan)
        self.clear(plan['point'],ch,'partial_optical')
        return True

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
        probe=paired_probe(before,station,bearing,self.options['probe_b'],self.options['probe_fraction'],
                           narrow_probe=self.options.get('narrow_probe',False))
        selected=None
        if self.options.get('lookahead'):
            other=self.other_tasks(ch)
            anchor=min(other,key=lambda q:math.dist(q,self.info(ch)[0])) if other else None
            selected=choose_pair(before,self.client.ledger.position,self.positives[ch],self.negatives[ch],
                                 [q for j,q in self.measured if j==ch],self.options,anchor,
                                 self.optical_exclusions.get(ch,[]))
            if selected:
                probe=selected['probe'];station=probe['station'];bearing=probe['bearing']
                self.record('q4_finite_lookahead_rank',channel=ch,**selected)
        reused=None
        if self.options.get('reuse_negative',False):
            other=self.other_tasks(ch)
            anchor=min(other,key=lambda q:math.dist(q,self.info(ch)[0])) if other else None
            reused=choose_reused_probe(before,self.client.ledger.position,self.positives[ch],self.negatives[ch],
                                       [q for j,q in self.measured if j==ch],self.options,anchor)
            if reused and selected and reused['estimated_remaining_s']>=selected['estimated_remaining_s']:
                reused=None
            if reused:self.record('q4_reused_negative_rank',channel=ch,**reused)
        if selected and not reused and self.options.get('partial_before_pair',True) and self.try_partial_optical(ch,selected,anchor):
            if ch in self.cleared:return
            # An actual miss changes the current point and exclusion history.
            # Re-rank the original reliable baseline, without a second trial.
            reranked=choose_pair(before,self.client.ledger.position,self.positives[ch],self.negatives[ch],
                                 [q for j,q in self.measured if j==ch],self.options,anchor,
                                 self.optical_exclusions.get(ch,[]))
            if reranked:
                selected=reranked;probe=selected['probe'];station=probe['station'];bearing=probe['bearing']
                self.record('q4_finite_lookahead_after_optical_miss',channel=ch,**selected)
        if self.options.get('compact_optical') and (selected or reused):
            models=hypotheses(before,self.positives[ch],self.negatives[ch],self.options.get('lookahead_positions',9),
                              self.optical_exclusions.get(ch,[]))
            rf_cost=(reused or selected)['estimated_remaining_s']+int(ch!=self.client.ledger.channel)
            if self.try_compact_optical(ch,models,anchor,rf_cost,'before_pair'):return
        if reused:return self.execute_reused_probe(ch,reused,before)
        if not probe['geometry_valid']:
            self.record('q4_pair_geometry_rejected',channel=ch,probe=probe)
            return self.fallback(ch)
        endpoints=[probe['plus'],probe['minus']]
        endpoints.sort(key=lambda q:math.dist(q,self.client.ledger.position))
        if selected:endpoints=selected['endpoints']
        if all((ch,tuple(q)) in self.measured for q in endpoints):
            return self.fallback(ch)
        results=[];observed=[]
        for q in endpoints:
            kind=self.measure(q,ch,'paired_probe');results.append(kind);observed.append(q)
            if ch in self.cleared or self.guaranteed_clear(ch):return
            if len(results)==1 and self.options.get('partial_after_first'):
                other=self.other_tasks(ch)
                anchor=min(other,key=lambda p:math.dist(p,self.info(ch)[0])) if other else None
                second=dict(probe=probe,endpoints=[endpoints[1]],first_result=kind)
                self.try_partial_optical(ch,second,anchor,'after_first_'+kind)
                if ch in self.cleared:return
            if len(results)==1 and self.options.get('compact_after_first'):
                other=self.other_tasks(ch)
                anchor=min(other,key=lambda p:math.dist(p,self.info(ch)[0])) if other else None
                models=hypotheses(self.polygons[ch],self.positives[ch],self.negatives[ch],self.options.get('lookahead_positions',9),
                                  self.optical_exclusions.get(ch,[]))
                if models:
                    radio_cost,branches=single_probe_cost(self.polygons[ch],self.client.ledger.position,
                                                          endpoints[1],models,anchor,kind,probe)
                    if self.try_compact_optical(ch,models,anchor,radio_cost,'after_first_'+kind):return
            if self.options.get('lookahead_optical',0)>20 and kind=='direction':
                center,radius=self.info(ch)
                if 20<radius<=self.options['lookahead_optical']:
                    old=self.optical_tried.get(ch)
                    if old is None or math.dist(old,center)>10:
                        self.optical_tried[ch]=center
                        if self.clear(center,ch,'lookahead_optical'):return
            if kind=='direction' and len(results)==1 and self.options.get('replan_after_direction'):
                self.record('q4_replan_after_first_direction',channel=ch,
                            unvisited_endpoint=endpoints[1],remaining_radius=self.info(ch)[1])
                return
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
        self.orient_initial_skeleton()
        for decision in range(500):
            self.refresh()
            pending=sorted(set(self.polygons)-self.cleared)
            if not pending and not self.remaining:return self.finish()
            if not self.remaining and self.unknown() and len(set(self.polygons)|self.cleared)<16:
                raise ProtocolError('Q4 skeleton exhausted with unproved directional coverage')
            p=self.client.ledger.position
            force_search=self.remaining and self.since_search>=self.options['max_tasks_before_search']
            indices=list(range(len(self.remaining)))
            if self.options.get('search_stage')=='inner_first':
                inner=[i for i in indices if math.hypot(*self.remaining[i])<1500]
                if inner:indices=inner
            tasks=[('scan',i) for i in indices]
            points=[self.remaining[i] for i in indices]
            allow_sources=not (self.options.get('search_stage')=='search_first' and self.remaining)
            if not force_search and allow_sources:
                tasks += [('source',ch) for ch in pending]
                points += [self.route_source_point(ch,p) for ch in pending]
            if not tasks:raise ProtocolError('Q4 no legal progress task')
            if self.options.get('task_route'):
                exits=[point if kind=='scan' or nearest_operating_point(self.polygons[index],p) is not None
                       else area_centroid(self.polygons[index])
                       for (kind,index),point in zip(tasks,points)]
                first=open_task_route(p,points,exits)[0]
            else:first=self.plan_route(p,points)[0]
            kind,index=tasks[first]
            self.record('q4_route_decision',decision=decision,kind=kind,index=index,
                        sources=len(pending),search_stops=len(self.remaining),forced_search=bool(force_search))
            if kind=='scan':self.scan(self.remaining.pop(index))
            else:
                self.since_search+=1;self.phase='localization';self.localize(index)
                if self.options.get('shared_after_localize'):
                    self.share_at_actual_station(tuple(self.client.ledger.position))
                self.scan_for_forecast_complement()
                self.replace_from_actual_stop()
                if self.certificate_search:self.certificate_search.at_actual_stop(self)
        raise ProtocolError('Q4 finite planning guard reached')
