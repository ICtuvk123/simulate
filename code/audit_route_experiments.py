"""Offline post-run checks and feedback-only replay for G experiments."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
import multiprocessing
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]/'local_simulator'
DEST=ROOT/'reports/optimization'
sys.path.insert(0,str(ROOT/'code'))
from audit_feedback_only import verify
from geometry import contains


def main():
    p=argparse.ArgumentParser()
    p.add_argument('phases',nargs='+')
    p.add_argument('--replay-variant')
    p.add_argument('--output',default='G_audit.json')
    args=p.parse_args()
    checks=[];replay_ids=[]
    for phase in args.phases:
        scenes={}
        rows=list(csv.DictReader((DEST/(phase+'_runs.csv')).open(encoding='utf-8-sig')))
        for row in rows:
            folder=ROOT/'runs'/row['run_id']
            data=json.loads((folder/'result.json').read_text(encoding='utf-8'))
            m=data['metrics'];ev=data['evaluation'];seed=row['seed']
            assert ev['ended_reason']=='user_exit',row['run_id']
            assert not m['accounting_warnings'] and m['clear_ratio']==1 and m['completion_proved'],row['run_id']
            if seed in scenes:assert scenes[seed]==ev['sources'],('different paired scene',seed)
            scenes[seed]=ev['sources']
            truth={s['channel']:(s['x'],s['y']) for s in ev['sources']}
            events=[json.loads(line) for line in (folder/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
            policy=[r for r in events if r['event']=='policy']
            regions=[r for r in policy if r.get('reason') in ('F_feedback_region','F_optical_negative_region')]
            for region in regions:
                assert contains(region['polygon'],truth[region['channel']],tolerance=1e-3)
                assert any(contains(p,truth[region['channel']],tolerance=1e-3) for p in region['pieces'])
            moved=[r for r in policy if r.get('reason')=='G_route_bent_search_station']
            checks.append(dict(phase=phase,variant=row['variant'],seed=int(seed),run_id=row['run_id'],
                clear_and_accounting_pass=True,regions_keep_actual_source=len(regions),
                bent_station_decisions=len(moved),predicted_bend_saved_s=sum(r['predicted_saved_move_s'] for r in moved),
                dedicated_scans=sum(r.get('reason')=='F_channel_search_stop' and r.get('dedicated',False) for r in policy)))
            if args.replay_variant and row['variant']==args.replay_variant:replay_ids.append(row['run_id'])
    replays=[]
    if replay_ids:
        with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
            for result in pool.map(verify,replay_ids):
                replays.append(result)
                if len(replays)%20==0:print(json.dumps(dict(replayed=len(replays),total=len(replay_ids))),flush=True)
    result=dict(runs_checked=len(checks),all_pass=True,paired_sources_identical=True,
                region_checks=sum(c['regions_keep_actual_source'] for c in checks),checks=checks,
                feedback_replay_runs=len(replays),feedback_replay_actions=sum(r['actions_checked'] for r in replays),
                replays=replays)
    (DEST/args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','replays')},indent=2),flush=True)


if __name__=='__main__':
    multiprocessing.freeze_support();main()
