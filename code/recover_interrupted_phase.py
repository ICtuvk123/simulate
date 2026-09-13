"""Preserve every registered slot after an externally interrupted batch.

Does not run policies, impute missing times, select successful pairs, or claim
that an incomplete final holdout has passed.
"""
import csv,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def recover(phase):
    folder=ROOT/'reports'/phase;reg=json.loads((folder/'registration.json').read_text())
    if (folder/'acceptance.json').exists():raise ValueError('Completed phase should not be marked interrupted')
    indexed={}
    for path in folder.glob('worker*.jsonl'):
        for line in path.read_text().splitlines():
            if line.strip():
                row=json.loads(line);indexed[(row['task']['seed'],row['task']['variant'])]=row
    rows=[];counts={v:dict(registered=0,recorded_runs=0,recorded_complete=0,recorded_failed=0,unfinished=0) for v in reg['variants']}
    for index,task in enumerate(reg['tasks']):
        key=(task['seed'],task['variant']);path=folder/f'case_{index}.json'
        row=indexed.get(key)
        if row is None and path.exists():row=dict(json.loads(path.read_text()),task=task)
        if row is None:row=dict(task=task,run_id=None,error='Interrupted after observed real deadline; no completed result')
        m=row.get('metrics');count=counts[task['variant']];count['registered']+=1
        if row.get('run_id'):
            count['recorded_runs']+=1;count['recorded_complete' if m and m.get('all_success') else 'recorded_failed']+=1
        else:count['unfinished']+=1
        rows.append(row)
    (folder/'runs.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
    fields=['seed','variant','run_id','status','all_success','total_time','mean_time_per_source','clear_count','engine_source_count','error']
    with (folder/'paired_results.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fields);writer.writeheader()
        for row in rows:
            m=row.get('metrics',{});writer.writerow(dict(seed=row['task']['seed'],variant=row['task']['variant'],run_id=row.get('run_id'),
                status='recorded' if row.get('run_id') else 'unfinished',error=row.get('error') or m.get('client_error'),
                **{key:m.get(key) for key in ('all_success','total_time','mean_time_per_source','clear_count','engine_source_count')}))
    report=dict(phase=phase,recorded_utc=datetime.now(timezone.utc).isoformat(),status='interrupted_not_accepted',
                development_deadline_utc='2026-09-12T16:35:00Z',counts=counts,
                no_summary_over_success_only_subset=True,no_final_200_success_claim=True,
                incumbent_remains='R2_S22_ML validated on 100 fresh paired validation scenes',
                note='A long wall-clock gap was observed while tools were pending. The precise cause was not established. The batch was interrupted when control returned after the deadline. Missing slots remain explicit, and all recorded runs are retained.')
    (folder/'INTERRUPTED.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream)
        for row in rows:writer.writerow([phase,'final',row['task']['seed'],row['task']['variant'],row.get('run_id'),
                                         'recorded_before_interruption' if row.get('run_id') else 'registered_but_unfinished'])
    return report


if __name__=='__main__':print(json.dumps(recover('R2_FINAL_holdout200'),indent=2))
