"""Reconstruct S22 route opportunities from accepted historical feedback only."""
import hashlib,json,math,statistics,sys,time
from pathlib import Path
from q3client import Ledger,decode_response
from directional_geometry import skeleton
from geometry import minimum_circle
from local_geometry import nearest_operating_point
from routing import open_route,route_length
from lookahead import shared_information_value

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent.parent/'jammer_search_q4_r2'


def inspect(journal):
    records=[json.loads(s) for s in journal.read_text().splitlines()]
    options=next(r for r in records if r.get('event')=='metadata')['policy_options']
    sites=skeleton(**{k:options[k] for k in ('inner_count','outer_count','inner_radius','outer_radius','inner_phase','outer_phase')})
    remaining=sites[1:];ledger=Ledger();poly={};positive={};negative={j:[] for j in range(1,21)}
    measured=set();since_search=0;out=[];roles={};role='other';last_clear=0.
    for i,row in enumerate(records):
        reason=row.get('reason')
        if reason=='q4_action_role':role=row['role']
        if row.get('event')=='response':
            result=decode_response(row['response_body']);fresh=ledger.apply(row['path'],row['payload'],row['http_status'],result)
            if fresh and row['path'] in ('/measure','/clear'):
                event=ledger.events[-1];cost=roles.setdefault(role,dict(actions=0,move=0.,rf=0.,switch=0.,optical=0.,success=0.))
                cost['actions']+=1
                for label,key in (('move','move_time'),('rf','RF_detection_time'),('switch','channel_switch_time'),('optical','optical_time'),('success','clear_time')):cost[label]+=event[key]
                ch=row['payload']['channel'];p=tuple(ledger.position)
                if row['path']=='/measure':
                    measured.add((ch,p));kind=result['measure_result']
                    if kind=='direction':positive.setdefault(ch,[]).append((p,result['svd_deg']))
                    elif kind=='no_signal':negative[ch].append(p)
                elif result['clear_result']=='success':last_clear=ledger.virtual_time
        if reason in ('q4_positive_region','q4_paired_negative_clip'):
            ch=row.get('channel',row.get('witness',{}).get('channel'));poly[ch]=row['polygon']
        if reason!='q4_route_decision':continue
        if len(set(poly)|ledger.cleared)==16:remaining=[]
        pending=sorted(set(poly)-ledger.cleared);p=tuple(ledger.position)
        tasks=[('scan',j) for j in range(len(remaining))];points=list(remaining)
        if not row['forced_search']:
            tasks.extend(('source',j) for j in pending)
            points.extend(nearest_operating_point(poly[j],p) or minimum_circle(poly[j])[0] for j in pending)
        order=open_route(p,points);chosen=tasks[order[0]]
        restored=chosen==(row['kind'],row['index'])
        entry=dict(record_index=i,kind=row['kind'],channel=row['index'] if row['kind']=='source' else None,
                   forced=row['forced_search'],pending=len(pending),remaining=len(remaining),since_search=since_search,
                   time=ledger.virtual_time,restored=restored,position=p)
        if row['kind']=='source':
            since_search+=1;ch=row['index'];center,radius=minimum_circle(poly[ch]);entry['radius']=radius
            entry['proxy_distance_m']=math.dist(p,points[order[0]])
            ahead=next((k for k in range(1,len(order)) if tasks[order[k]][0]=='scan'),None)
            if ahead is not None:
                site=points[order[ahead]];value=shared_information_value(poly[ch],site,positive[ch],negative[ch])
                first=order[0];scan=order[ahead]
                alternative=[scan]+[j for j in order if j!=scan]
                entry.update(first_scan_ahead=ahead,scan_point=site,scan_distance_m=math.dist(p,site),
                             planned_move_increase_s=(route_length(p,points,alternative)-route_length(p,points,order))/5,
                             target_shared_gain_s=value['estimated_gain_s'] if value else None,
                             target_models=value['model_count'] if value else 0,
                             target_already_measured=(ch,tuple(site)) in measured,
                             target_region=list(poly[ch]),positives=list(positive[ch]),negatives=list(negative[ch]))
        else:since_search=0;remaining.pop(row['index'])
        out.append(entry)
    return dict(nodes=out,roles=roles,total=ledger.virtual_time,last_clear=last_clear,tail=ledger.virtual_time-last_clear,
                all_restored=all(n['restored'] for n in out),source_count=len(ledger.cleared))


def main():
    phase=ROOT/'reports/R2_SCHEDULE_DIAGNOSTIC';phase.mkdir(exist_ok=True)
    metadata=[json.loads(s) for s in (PARENT/'reports/R2_S22_val100/runs.jsonl').read_text().splitlines()]
    selected=[r for r in metadata if r['task']['variant']=='outer13'];rows=[];start=time.perf_counter()
    for i,run in enumerate(selected):
        journal=PARENT/'runs'/run['run_id']/'requests.jsonl';result=inspect(journal)
        rows.append(dict(run_id=run['run_id'],journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest(),**result))
        if (i+1)%10==0:print(i+1,flush=True)
    nodes=[n for row in rows for n in row['nodes']];source=[n for n in nodes if n['kind']=='source']
    opportunities=[n for n in source if n.get('target_shared_gain_s') is not None and n['radius']>20
                   and not n['target_already_measured'] and n['target_shared_gain_s']>10]
    favorable=[n for n in opportunities if n['target_shared_gain_s']>n['planned_move_increase_s']+6]
    summary=dict(journals=len(rows),nodes=len(nodes),source_tasks=len(source),all_nodes_restored=all(r['all_restored'] for r in rows),
        forced_searches=sum(n['forced'] for n in nodes),mean_max_source_streak=statistics.mean(max((n['since_search'] for n in r['nodes']),default=0) for r in rows),
        mean_total=statistics.mean(r['total'] for r in rows),mean_tail=statistics.mean(r['tail'] for r in rows),
        large_uncertainty_tasks=sum(n['radius']>100 for n in source),shared_scan_opportunities=len(opportunities),
        favorable_scan_reorders=len(favorable),mean_favorable_gain_s=statistics.mean(n['target_shared_gain_s']-n['planned_move_increase_s']-6 for n in favorable) if favorable else 0.,
        wall_s=time.perf_counter()-start,engine_evaluation_files_read=False,engine_truth_used=False,
        interpretation='Shared-information heuristic minus movement increase is diagnostic, not measured counterfactual savings.')
    (phase/'nodes.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (phase/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
