"""Post-exit diagnostics only. Never imported by the controller."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]/'local_simulator'
DEST=ROOT/'reports'/'optimization'
sys.path.insert(0,str(ROOT/'code'))
from geometry import contains,regular_fallback


def analyze(phase):
    rows=list(csv.DictReader((DEST/(phase+'_runs.csv')).open(encoding='utf-8-sig')))
    diagnostics=[];sources_by_seed={}
    for row in rows:
        directory=ROOT/'runs'/row['run_id']
        result=json.loads((directory/'result.json').read_text(encoding='utf-8'))
        assert result['evaluation']['ended_reason']=='user_exit',row['run_id']
        sources=result['evaluation']['sources']
        key=int(row['seed'])
        if key in sources_by_seed:
            assert sources==sources_by_seed[key],key
        sources_by_seed[key]=sources
        truth={s['channel']:(s['x'],s['y']) for s in sources}
        records=[json.loads(line) for line in (directory/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
        policy=[r for r in records if r.get('event')=='policy']
        regions=[r for r in policy if r.get('reason') in ('F_feedback_region','F_optical_negative_region')]
        for region in regions:
            point=truth[region['channel']]
            assert contains(region['polygon'],point,tolerance=1e-3),(row['run_id'],'hull excluded truth')
            assert any(contains(p,point,tolerance=1e-3) for p in region['pieces']),(row['run_id'],'pieces excluded truth')
        events=result['evaluation']['events']
        clears=[e for e in events if e['path']=='/clear' and e['response']['clear_result']=='success']
        last=max(e['response']['virtual_time_s'] for e in clears)
        searches=[r for r in policy if r.get('reason') in ('F_channel_search_stop','gain_filtered_search')]
        shared=[r for r in policy if r.get('reason')=='F_shared_feedback']
        sites,_=regular_fallback(1130)
        known=set();search_time=0.;empty_channel_rf=0
        for event in events:
            ch=event['channel']
            if event['path']=='/measure':
                if ch not in known:
                    search_time+=sum(event.get(k,0) for k in ('move_time','RF_time','switch_time'))
                if ch not in truth:empty_channel_rf+=1
                if event['response']['measure_result']!='no_signal':known.add(ch)
            if event['path']=='/clear' and event['response']['clear_result']=='success':known.add(ch)
        d=dict(variant=row['variant'],seed=key,run_id=row['run_id'],
               total_s=float(row['total_time']),s_per_source=float(row['total_time'])/int(row['clear_count']),
               tail_after_last_clear_s=float(row['total_time'])-last,
               final_source_count=len(sources),accepted_RF_count=len([e for e in events if e['path']=='/measure']),
               RF_no_signal_count=sum(e['path']=='/measure' and e['response'].get('measure_result')=='no_signal' for e in events),
               search_dedicated_stops=sum(any(sum((a-b)**2 for a,b in zip(r['point'],q))<1e-8 for q in sites) for r in searches),
               search_opportunistic_stops=sum(not any(sum((a-b)**2 for a,b in zip(r['point'],q))<1e-8 for q in sites) for r in searches),
               search_channel_measurements=sum(len(r['channels']) if 'channels' in r else r['unknown_channels'] for r in searches),
               unknown_channel_action_s=search_time,RF_on_absent_channels=empty_channel_rf,
               replaced_planned_stations=sum(r.get('reason')=='F_planned_station_replaced_after_actual_feedback' for r in policy),
               shared_tests=len(shared),shared_positive=sum(r['result']!='no_signal' for r in shared),
               optical_exclusions=sum(r.get('reason')=='F_optical_negative_region' for r in policy),
               strip_fallbacks=sum(r.get('reason')=='F_finite_bearing_strip_fallback' for r in policy),
               feasible_region_checks=len(regions),all_regions_keep_actual_source=True,
               wall_s=float(row['measured_program_wall_time_s']))
        diagnostics.append(d)
    with (DEST/(phase+'_diagnostics.csv')).open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(diagnostics[0]));writer.writeheader();writer.writerows(diagnostics)
    summary=[]
    for name in dict.fromkeys(d['variant'] for d in diagnostics):
        group=[d for d in diagnostics if d['variant']==name]
        summary.append(dict(variant=name,n=len(group),**{k:statistics.mean(d[k] for d in group) for k in
            ('total_s','s_per_source','tail_after_last_clear_s','RF_no_signal_count','search_dedicated_stops',
             'search_opportunistic_stops','replaced_planned_stations','shared_tests','shared_positive','optical_exclusions','wall_s')}))
    (DEST/(phase+'_diagnostics_summary.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');args=p.parse_args();analyze(args.phase)
