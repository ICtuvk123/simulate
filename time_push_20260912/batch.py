"""Independent local pairs; scene data never enters the controller."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import hashlib
import json
import multiprocessing
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'code'))
from runner import run_case
from g_policy_presets import FROZEN_G_OPTIONS


def execute(job):
    variant, case = job
    import runner
    from route_search import RouteSearchController
    runner.RouteSearchController = RouteSearchController
    options = dict(FROZEN_G_OPTIONS, **variant.get('options', {}))
    extra = variant.get('extra', {})
    if extra:
        from time_policy import TimePolicy
        runner.RouteSearchController = lambda client, **kw: TimePolicy(client, **kw, **extra)
    directory, payload = run_case(**case, strategy='G', policy_options=options,
                                 compute_oracle=False, update_latest=False)
    (directory / 'experiment_variant.json').write_text(json.dumps(variant, indent=2), encoding='utf-8')
    m = payload['metrics']
    row = dict(variant=variant['name'], seed=case['seed'], scenario=case.get('scenario','uniform'),
               reception=case.get('reception','mixed'), error_mode=case.get('error_mode','fixed_hash'))
    row.update({k:m.get(k) for k in ('run_id','strategy_hash','parameter_hash','clear_count',
        'jammer_count','clear_ratio','total_time','move_time','move_distance','RF_detection_count',
        'RF_detection_time','channel_switch_time','optical_time','clear_time','optical_failed_count',
        'completion_proved','client_error','measured_program_wall_time_s',
        'average_localization_clear_time_s_per_source')})
    row['variant_hash'] = hashlib.sha256(json.dumps(variant,sort_keys=True).encode()).hexdigest()
    # Truth is read exclusively after run_case has exited, for paired audit.
    row['scene_hash'] = hashlib.sha256(json.dumps(payload['evaluation']['sources'],sort_keys=True).encode()).hexdigest()
    return row


def main():
    p=argparse.ArgumentParser();p.add_argument('config');a=p.parse_args()
    config=json.loads(Path(a.config).read_text(encoding='utf-8'))
    out=ROOT/'reports'/config['phase'];out.mkdir(exist_ok=False)
    (out/'manifest.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    jobs=[(v,c) for c in config['cases'] for v in config['variants']]
    rows=[]
    with ProcessPoolExecutor(max_workers=config.get('workers',8),mp_context=multiprocessing.get_context('spawn')) as pool:
        futures=[pool.submit(execute,j) for j in jobs]
        for future in as_completed(futures):
            row=future.result();rows.append(row)
            with (out/'runs.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerows(rows)
            if len(rows)%8==0 or row['client_error'] or row['clear_ratio']!=1:
                print(json.dumps(dict(done=len(rows),total=len(jobs),last=row['variant'],seed=row['seed'],
                    average=row['average_localization_clear_time_s_per_source'],error=row['client_error'])),flush=True)
    summary=[]
    for variant in config['variants']:
        selected=[r for r in rows if r['variant']==variant['name']]
        summary.append(dict(variant=variant['name'],n=len(selected),
            all_pass=all(r['clear_ratio']==1 and r['completion_proved'] and not r['client_error'] for r in selected),
            **{'mean_'+k:statistics.mean(r[k] for r in selected) for k in ('total_time','move_time',
                'RF_detection_time','channel_switch_time','optical_time','clear_time',
                'average_localization_clear_time_s_per_source','measured_program_wall_time_s')},
            worst=max(r['total_time'] for r in selected)))
    summary.sort(key=lambda r:(not r['all_pass'],r['mean_average_localization_clear_time_s_per_source']))
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    multiprocessing.freeze_support();main()
