"""CPU-isolated paired local experiments; each policy has its own engine."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
import multiprocessing
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]/'local_simulator'
sys.path.insert(0,str(ROOT/'code'))
from runner import run_case
from benchmark import percentile


def execute(job):
    variant,case=job
    config={k:v for k,v in variant.items() if k!='name'}
    directory,payload=run_case(**case,**config,compute_oracle=False,update_latest=False)
    m=payload['metrics']
    return dict(variant=variant['name'],seed=case['seed'],**{k:m.get(k) for k in
        ('run_id','strategy_hash','parameter_hash','clear_count','jammer_count','clear_ratio',
         'total_time','move_time','move_distance','RF_detection_time','RF_detection_count',
         'channel_switch_time','optical_time','clear_time','optical_failed_count','completion_proved',
         'client_error','measured_program_wall_time_s','average_localization_clear_time_s_per_source')})


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--config',required=True)
    a=p.parse_args();setup=json.loads(Path(a.config).read_text(encoding='utf-8'))
    dest=ROOT/'reports/optimization';path=dest/(a.phase+'_manifest.json')
    if path.exists():raise FileExistsError(path)
    manifest=dict(name=a.phase,**setup,executor='independent_process_workers',
                  data_origin='self_written_simulator',physical_rules_changed=False)
    path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    jobs=[(variant,case) for variant in setup['variants'] for case in setup['cases']]
    rows=[]
    with ProcessPoolExecutor(max_workers=setup.get('workers',4),mp_context=multiprocessing.get_context('spawn')) as pool:
        for row in pool.map(execute,jobs):
            rows.append(row)
            with (dest/(a.phase+'_runs.csv')).open('w',encoding='utf-8-sig',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
            if len(rows)%10==0 or row['client_error'] or row['clear_ratio']!=1:
                print(json.dumps(dict(done=len(rows),total=len(jobs),**{k:row[k] for k in ('variant','seed','total_time','clear_ratio','client_error')})),flush=True)
    summary=[]
    for variant in setup['variants']:
        selected=[r for r in rows if r['variant']==variant['name']];times=[r['total_time'] for r in selected]
        summary.append(dict(variant=variant['name'],n=len(selected),mean_s=statistics.mean(times),
            median_s=statistics.median(times),p90_s=percentile(times,.9),
            mean_s_per_source=statistics.mean(r['total_time']/r['clear_count'] for r in selected if r['clear_count']),
            p95_s=percentile(times,.95),worst_s=max(times),
            all_pass=all(r['clear_ratio']==1 and r['completion_proved'] and not r['client_error'] for r in selected),
            **{'mean_'+k:statistics.mean(r[k] for r in selected) for k in
               ('move_time','RF_detection_time','channel_switch_time','optical_time','clear_time')}))
    summary.sort(key=lambda r:(not r['all_pass'],r['mean_s']))
    (dest/(a.phase+'_summary.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    multiprocessing.freeze_support();main()
