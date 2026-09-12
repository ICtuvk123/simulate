"""Post-run action costs. Never imported by the feedback-only controller.

Discovery-to-clear distance is reported two ways: all robot travel during the
interval, and travel on actions addressed to that channel. Neither is a truth-
aware optimal-route distance. Removal savings are estimates logged at removal,
not counterfactual realized savings.
"""
import argparse,csv,json,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def diagnose(events,records):
    discovered={};cleared={};distance=0.;channel_distance={};last_clear=None
    per_source=[];removals=[];scans=[]
    for event in events:
        response=event['response']
        if not response.get('accepted'):continue
        ch=event.get('channel');movement=5*event.get('move_time',0.)
        distance+=movement
        if ch is not None:channel_distance[ch]=channel_distance.get(ch,0.)+movement
        virtual=response['virtual_time_s']
        if (event['path']=='/measure' and response.get('measure_result') in ('direction','near')
                and ch not in discovered):
            discovered[ch]=(virtual,distance,channel_distance[ch])
        if event['path']=='/clear' and response.get('clear_result')=='success' and ch not in cleared:
            cleared[ch]=virtual;last_clear=virtual
            if ch in discovered:
                t,d,attributed=discovered[ch]
                per_source.append(dict(channel=ch,discovered_s=t,cleared_s=virtual,
                                       discovery_to_clear_s=virtual-t,
                                       interval_travel_m=distance-d,
                                       channel_action_travel_m=channel_distance[ch]-attributed))
    for row in records:
        if row.get('reason')=='q4_certificate_sites_removed':
            removals.append(dict(count=len(row.get('removed_sites',[])),
                                 predicted_move_saved_s=row.get('predicted_move_saved_s',0.),
                                 witness=row))
        if row.get('reason')=='q4_action_role' and row.get('role') in ('certificate_scan','certificate_replacement_scan'):
            scans.append(row)
    final=next((e['response']['virtual_time_s'] for e in reversed(events) if e['response'].get('accepted')),0.)
    return dict(total_travel_m=distance,discovered_count=len(discovered),cleared_count=len(cleared),
                last_clear_s=last_clear,tail_after_last_clear_s=None if last_clear is None else final-last_clear,
                mean_discovery_to_clear_s=statistics.mean(p['discovery_to_clear_s'] for p in per_source) if per_source else None,
                mean_interval_travel_m=statistics.mean(p['interval_travel_m'] for p in per_source) if per_source else None,
                mean_channel_action_travel_m=statistics.mean(p['channel_action_travel_m'] for p in per_source) if per_source else None,
                cancelled_search_stations=sum(r['count'] for r in removals),
                predicted_cancelled_detour_s=sum(r['predicted_move_saved_s'] for r in removals),
                replacement_scan_actions=len(scans),per_source=per_source,removals=removals)


def run(phase):
    folder=ROOT/'reports'/phase
    rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text(encoding='utf-8').splitlines()]
    results=[]
    for row in rows:
        item=dict(seed=row['task']['seed'],variant=row['task']['variant'],run_id=row.get('run_id'))
        try:
            directory=ROOT/'runs'/row['run_id']
            evaluation=json.loads((directory/'evaluation.json').read_text(encoding='utf-8'))
            records=[json.loads(s) for s in (directory/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
            item.update(diagnose(evaluation['events'],records))
            item['complete']=row.get('metrics',{}).get('all_success',False)
            (directory/'action_diagnostics.json').write_text(json.dumps(item,indent=2),encoding='utf-8')
        except Exception as e:item.update(error=repr(e),complete=False)
        results.append(item)
    fields=['seed','variant','run_id','complete','total_travel_m','discovered_count','cleared_count',
            'last_clear_s','tail_after_last_clear_s','mean_discovery_to_clear_s','mean_interval_travel_m',
            'mean_channel_action_travel_m','cancelled_search_stations','predicted_cancelled_detour_s',
            'replacement_scan_actions','error']
    with (folder/'action_diagnostics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(results)
    summary={}
    for variant in sorted(set(r['variant'] for r in results)):
        selected=[r for r in results if r['variant']==variant]
        data=dict(n=len(selected),complete=sum(r['complete'] for r in selected),
                  missing_diagnostics=sum('error' in r for r in selected))
        for field in fields[4:-1]:
            values=[r[field] for r in selected if r.get(field) is not None]
            if values:data['mean_'+field]=statistics.mean(values)
        summary[variant]=data
    report=dict(phase=phase,summary=summary,truth_available_only_after_run=True,
                note='interval travel overlaps across sources; channel-action travel does not. Cancellation savings are planning estimates.')
    (folder/'action_diagnostics_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');run(p.parse_args().phase)
