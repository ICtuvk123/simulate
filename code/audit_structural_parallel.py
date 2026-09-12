"""Replay frozen policies in independent workers with feedback-only I/O guards."""
from concurrent.futures import ProcessPoolExecutor
import csv
import json
import multiprocessing
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]/'local_simulator';sys.path.insert(0,str(ROOT/'code'))
from audit_feedback_only import verify


def main():
    dest=ROOT/'reports'/'optimization'
    rows=list(csv.DictReader((dest/'F_validation100_runs.csv').open(encoding='utf-8-sig')))
    ids=[r['run_id'] for r in rows if r['variant']=='frozen_F'];assert len(ids)==100
    with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
        results=[]
        for result in pool.map(verify,ids):
            results.append(result)
            if len(results)%20==0:print(json.dumps({'verified_runs':len(results)}),flush=True)
    target=dest/'F_feedback_only_audit.json';target.write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(dict(runs=len(results),actions=sum(r['actions_checked'] for r in results),
                         all_decisions_identical=True,engine_imported=False,truth_file_read=False)),flush=True)


if __name__=='__main__':
    multiprocessing.freeze_support();main()
