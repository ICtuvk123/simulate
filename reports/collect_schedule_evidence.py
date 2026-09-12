"""Post-run schedule checks, forecast follow-through and paired evidence."""
import csv,json,math,statistics,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
from compare_phase import compare
from geometry import minimum_circle

phase='R2_SCAN_COMMIT10';folder=ROOT/'reports'/phase
rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text().splitlines()]
registration=json.loads((folder/'registration.json').read_text());checks=[];forecasts=[]
for run in rows:
    p=Path(run['directory']);manifest=json.loads((p/'manifest.json').read_text());valid={}
    for name in ('audit','feedback_replay','independent_exit'):
        file=p/(name+'.json');valid[name]=file.exists() and json.loads(file.read_text())['valid']
    checks.append(dict(seed=run['task']['seed'],variant=run['task']['variant'],run_id=run['run_id'],
                      all_success=run['metrics']['all_success'],source_hashes_match=manifest['source_hashes']==registration['source_hashes'],**valid))
    if run['task']['variant']!='scan_commit':continue
    records=[json.loads(s) for s in (p/'requests.jsonl').read_text().splitlines()];regions={}
    for i,row in enumerate(records):
        if row.get('reason') in ('q4_positive_region','q4_paired_negative_clip'):
            ch=row.get('channel',row.get('witness',{}).get('channel'));regions[ch]=row['polygon']
        if row.get('reason')!='q4_scan_before_commit':continue
        ch=row['target_channel'];point=row['scan_point'];before=minimum_circle(regions[ch])[1]
        end=next((j for j in range(i+2,len(records)) if records[j].get('reason')=='q4_route_decision'),len(records))
        observed=[];after=before
        for event in records[i+1:end]:
            if event.get('reason') in ('q4_positive_region','q4_paired_negative_clip'):
                k=event.get('channel',event.get('witness',{}).get('channel'))
                if k==ch:after=minimum_circle(event['polygon'])[1]
            if event.get('event')!='response' or event['path']!='/measure' or event['http_status']!=200:continue
            payload=event['payload'];response=json.loads(event['response_body'])
            if (response.get('accepted') and payload['channel']==ch and
                math.dist(point,(payload['position']['x'],payload['position']['y']))<1e-8):observed.append(response['measure_result'])
        forecasts.append(dict(seed=run['task']['seed'],run_id=run['run_id'],record_index=i,target=ch,
                              expected_net_gain_s=row['expected_net_gain_s'],
                              planned_move_change_s=row['planned_move_change_s'],
                              first_scan_order=row['original_scan_order_position'],
                              radius_before=before,radius_after=after,
                              actual_target_feedback=observed[0] if observed else 'not_measured',
                              **{k:row[k] for k in ('scan_point','predicted_shared_channels','predicted_target_branches')}))
result=dict(runs=len(rows),all_checks=all(all(r[k] for k in ('all_success','source_hashes_match','audit','feedback_replay','independent_exit')) for r in checks),
            overrides=len(forecasts),scenes_with_overrides=len({r['seed'] for r in forecasts}),
            actual_target_measured=sum(r['actual_target_feedback']!='not_measured' for r in forecasts),
            actual_direction=sum(r['actual_target_feedback']=='direction' for r in forecasts),
            actual_no_signal=sum(r['actual_target_feedback']=='no_signal' for r in forecasts),
            actual_near=sum(r['actual_target_feedback']=='near' for r in forecasts),
            expected_target_displaced=sum(r['actual_target_feedback']=='not_measured' for r in forecasts),
            average_radius_before=statistics.mean(r['radius_before'] for r in forecasts),
            average_radius_after=statistics.mean(r['radius_after'] for r in forecasts),checks=checks)
(folder/'checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(folder/'forecast_followthrough.json').write_text(json.dumps(forecasts,indent=2),encoding='utf-8')
comparison=compare(phase,'S22','scan_commit')
ledger=list(csv.reader((ROOT/'SEEDS.csv').open(encoding='utf-8')));seen={(r[0],r[2],r[3],r[4]) for r in ledger if len(r)>4}
with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as f:
    writer=csv.writer(f)
    for r in rows:
        key=(phase,str(r['task']['seed']),r['task']['variant'],r['run_id'])
        if key not in seen:writer.writerow([phase,'smoke_development',r['task']['seed'],r['task']['variant'],r['run_id'],'complete' if r['metrics']['all_success'] else 'failed'])
old=list(csv.reader((ROOT/'EXPERIMENTS.csv').open(encoding='utf-8')))
if not any(row[0]==phase for row in old):
    first=next(r for r in rows if r['task']['variant']=='scan_commit')
    command='python code/r2_b_smoke.py --phase R2_SCAN_COMMIT10 --start 1411 --count 10 --variants '+chr(39)+json.dumps(registration['variants'])+chr(39)
    with (ROOT/'EXPERIMENTS.csv').open('a',newline='',encoding='utf-8') as f:
        csv.writer(f).writerow([phase,datetime.now(timezone.utc).isoformat(),
            'An upcoming search stop can reduce premature travel to uncertain source proxies',
            'Advance one existing scan when shared-information gain exceeds full planned-route movement increment',
            first['metrics']['code_hash'],'R2_scan_commit.json','smoke_development_new','1411-1420',command,json.dumps(comparison),
            'screen_pass_await_larger_development_and_new_validation' if comparison['gate_passed'] else 'screen_rejected'])
print(json.dumps(dict(checks={k:v for k,v in result.items() if k!='checks'},comparison=comparison),indent=2))
