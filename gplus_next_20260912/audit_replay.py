"""Replay the exact selected policy with action replies only and I/O denied."""
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


def replay(job):
    run_id,variant=job
    import audit_feedback_only
    from policy_factory import policy_class
    candidate=json.loads((ROOT/'BASELINE_candidate.json').read_text(encoding='utf-8'))
    extra={**candidate['extra'],**variant.get('extra',{})}
    controller=policy_class(variant.get('kind','Gplus'))
    audit_feedback_only.RouteSearchController=lambda client,**options:controller(client,**options,**extra)
    return audit_feedback_only.verify(run_id)


def main():
    p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();folder=ROOT/'reports'/a.phase
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['source_sha256'].items():
        assert hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()==digest, 'Code changed: '+name
    variants={v['name']:v for v in manifest['variants']}
    rows=list(csv.DictReader((folder/'runs.csv').open(encoding='utf-8-sig')))
    planned={(v['name'],str(c['seed'])) for v in manifest['variants'] for c in manifest['cases']}
    assert len(rows)==len(planned) and {(r['variant'],r['seed']) for r in rows}==planned, 'Incomplete planned batch'
    assert all(r['audit_pass']=='True' and r['clear_ratio']=='1.0' and r['completion_proved']=='True'
               and not r['client_error'] for r in rows), 'Only complete audited batches can pass replay'
    jobs=[]
    for row in rows:
        v=variants[row['variant']]
        assert row['variant_hash']==hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
        jobs.append((row['run_id'],v))
    results=[]
    with ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures=[pool.submit(replay,job) for job in jobs]
        for future in as_completed(futures):
            results.append(future.result())
            if len(results)%20==0:print(json.dumps(dict(replayed=len(results),total=len(jobs))),flush=True)
    data=dict(all_pass=True,runs=len(results),actions=sum(r['actions_checked'] for r in results),
        controller_selected_from_recorded_variant=True,engine_imported=False,truth_read=False,
        disk_network_process_access_during_decisions='denied',results=results)
    (folder/'feedback_only_audit.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in data.items() if k!='results'},indent=2))


if __name__=='__main__':
    multiprocessing.freeze_support();main()
