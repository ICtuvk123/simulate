"""After-exit truth checks and independent feedback-only decision replay."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))
from geometry import contains
from route_search import RouteSearchController
from time_policy import TimePolicy
import audit_feedback_only


def replay(job):
    run_id,extra=job
    audit_feedback_only.RouteSearchController=(
        (lambda client,**kw:TimePolicy(client,**kw,**extra)) if extra else RouteSearchController)
    return audit_feedback_only.verify(run_id)


def main():
    p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('--replay',action='store_true');a=p.parse_args()
    root=ROOT/'reports'/a.phase
    rows=list(csv.DictReader((root/'runs.csv').open(encoding='utf-8-sig')))
    manifest=json.loads((root/'manifest.json').read_text())
    variants={v['name']:v for v in manifest['variants']}
    scenes={};checks=[];jobs=[]
    for row in rows:
        folder=ROOT/'runs'/row['run_id']
        data=json.loads((folder/'result.json').read_text(encoding='utf-8'))
        m=data['metrics'];ev=data['evaluation'];key=(row['seed'],row['scenario'],row['reception'],row['error_mode'])
        assert ev['ended_reason']=='user_exit' and not m['accounting_warnings']
        assert m['clear_ratio']==1 and m['completion_proved'] and not m['client_error']
        assert m['clear_count']==m['jammer_count']
        if key in scenes:
            assert scenes[key]==ev['sources']
        scenes[key]=ev['sources']
        truth={s['channel']:(s['x'],s['y']) for s in ev['sources']}
        records=[json.loads(s) for s in (folder/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
        regions=[r for r in records if r.get('reason') in ('F_feedback_region','F_optical_negative_region')]
        for r in regions:
            assert contains(r['polygon'],truth[r['channel']],tolerance=1e-3)
            assert any(contains(poly,truth[r['channel']],tolerance=1e-3) for poly in r['pieces'])
        recorded=json.loads((folder/'experiment_variant.json').read_text())
        assert recorded==variants[row['variant']]
        assert hashlib.sha256(json.dumps(recorded,sort_keys=True).encode()).hexdigest()==row['variant_hash']
        checks.append(dict(run_id=row['run_id'],variant=row['variant'],regions=len(regions),all_pass=True))
        if a.replay:
            jobs.append((row['run_id'],recorded.get('extra',{})))
    replays=[]
    if jobs:
        with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:
            futures=[pool.submit(replay,j) for j in jobs]
            for f in as_completed(futures):
                replays.append(f.result())
                if len(replays)%20==0:
                    print(json.dumps(dict(replayed=len(replays),total=len(jobs))),flush=True)
    result=dict(all_pass=True,runs=len(rows),paired_scenes_identical=True,
        regions_checked=sum(c['regions'] for c in checks),checks=checks,
        replayed_runs=len(replays),replayed_actions=sum(r['actions_checked'] for r in replays),replays=replays)
    (root/'audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','replays')}),flush=True)


if __name__=='__main__':
    multiprocessing.freeze_support();main()
