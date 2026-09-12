"""Pre-registered local paired smoke for the partial optical branch."""
import argparse,csv,hashlib,json,multiprocessing,statistics,time
from datetime import datetime,timezone
from pathlib import Path
from run_case import run_case
from experiment import summarize
from independent_exit import verify as verify_exit

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',default='R2_B_smoke10')
    p.add_argument('--variants',type=json.loads)
    args=p.parse_args();phase=ROOT/'reports'/args.phase;phase.mkdir(exist_ok=False)
    seeds=list(range(1101,1111));variants=args.variants or {'compact':'D_compact_optical.json','partial':'R2_B_partial.json'}
    registration=dict(utc=datetime.now(timezone.utc).isoformat(),purpose='smoke_development_not_validation',
                      seeds=seeds,variants=variants,source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted((ROOT/'code').glob('*.py'))},replay=True,
                      configurations={k:dict(options=json.loads((ROOT/'configs'/v).read_text()),
                      sha256=hashlib.sha256((ROOT/'configs'/v).read_bytes()).hexdigest()) for k,v in variants.items()})
    (phase/'registration.json').write_text(json.dumps(registration,indent=2),encoding='utf-8')
    with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        for seed in seeds:
            for variant in variants:w.writerow([args.phase,'smoke_development',seed,variant,'','registered_before_run'])
    rows=[];start=time.perf_counter()
    for seed in seeds:
        for variant,config in variants.items():
            directory,metrics=run_case(seed,ROOT/'configs'/config,output_root=ROOT/'runs',replay_check=True)
            independent=verify_exit(directory/'requests.jsonl')
            (directory/'independent_exit.json').write_text(json.dumps(independent,indent=2),encoding='utf-8')
            row=dict(task=dict(seed=seed,variant=variant),metrics=metrics,run_id=directory.name,
                     directory=str(directory),independent_exit=independent)
            rows.append(row)
            with (phase/'runs.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            print(json.dumps(dict(seed=seed,variant=variant,complete=metrics['all_success'],
                                 total=metrics['total_time'],wall=metrics['policy_wall_time_s'],
                                 error=metrics['client_error'])),flush=True)
    result=dict(summary=summarize(rows),wall_s=time.perf_counter()-start)
    (phase/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (phase/'paired_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['seed','variant','all_success','total_time','mean_time_per_source','policy_wall_time_s','optical_failed_count']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:r['task'].get(k,r['metrics'].get(k)) for k in fields})
    print(json.dumps(result,indent=2))


if __name__=='__main__':multiprocessing.freeze_support();main()
