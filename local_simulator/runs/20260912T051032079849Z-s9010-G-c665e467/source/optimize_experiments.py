"""Predeclared paired local policy experiments; never accesses official services."""
import argparse
import csv
import json
import statistics
from concurrent.futures import ThreadPoolExecutor

from benchmark import percentile
from runner import ROOT, run_case

DEST = ROOT / 'reports' / 'optimization'
TRAIN = [dict(seed=s, scenario='uniform', reception='mixed', error_mode='fixed_hash') for s in range(101,105)]
FRESH_VALIDATION = [dict(seed=s, scenario='uniform', reception='mixed', error_mode='fixed_hash')
                    for s in range(2001,2021)]
STRESS = [dict(seed=s, scenario=sc, reception='minimum', error_mode=err)
          for s, sc, err in [(901,'boundary','plus_one'),(902,'boundary','minus_one'),
                            (903,'clustered','smooth'),(904,'uniform','smooth')]]
ROUND1 = [
    dict(name='compact1130', strategy='D', policy_options=dict(mode='compact')),
    dict(name='joint1130', strategy='D', policy_options=dict(mode='joint')),
    dict(name='joint1300', strategy='D', policy_options=dict(mode='joint',ring_radius=1300)),
    dict(name='pruned_dynamic', strategy='D', policy_options=dict(mode='pruned_dynamic',max_region=1000)),
    dict(name='C_no_extra_bearing', strategy='C', opportunistic=False),
]


def run_phase(name, cases, variants, holdout_seeds=None,workers=1):
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = dict(name=name, cases=cases, variants=variants,
                    reserved_final_validation_seeds=holdout_seeds,independent_workers=workers,
                    objective='100 percent clear and full task virtual time',
                    data_origin='self_written_simulator', physical_rules_changed=False)
    path = DEST / (name+'_manifest.json')
    if path.exists():
        raise ValueError('Phase already exists; use a new name to preserve experiments')
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = []
    jobs=[]
    for variant in variants:
        config = {k:v for k,v in variant.items() if k != 'name'}
        for case in cases:
            jobs.append((variant,config,case))
    def execute(job):
            variant,config,case=job
            directory, payload = run_case(**case, **config, compute_oracle=False,update_latest=False)
            m = payload['metrics']
            row = dict(variant=variant['name'], seed=case['seed'],
                       **{k:m.get(k) for k in ('run_id','strategy_hash','parameter_hash','clear_count',
                           'jammer_count','clear_ratio','total_time','move_time','move_distance',
                           'RF_detection_time','RF_detection_count','channel_switch_time',
                           'optical_time','clear_time','optical_failed_count','completion_proved',
                           'client_error','measured_program_wall_time_s',
                           'average_localization_clear_time_s_per_source')})
            return row
    # Each run has a unique directory and a separate simulator process; neither
    # the physical scene nor controller observations are shared across workers.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(execute,jobs):
            rows.append(row)
            with (DEST/(name+'_runs.csv')).open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row))
                writer.writeheader()
                writer.writerows(rows)
            print(json.dumps({k:row[k] for k in ('variant','seed','total_time','clear_ratio',
                                                 'completion_proved','client_error')}), flush=True)
    summary = []
    for variant in variants:
        selected = [r for r in rows if r['variant']==variant['name']]
        times = [r['total_time'] for r in selected]
        summary.append(dict(variant=variant['name'], n=len(selected), mean_s=statistics.mean(times),
                            median_s=statistics.median(times), p90_s=percentile(times,.9),
                            mean_s_per_source=statistics.mean(r['total_time']/r['clear_count'] for r in selected if r['clear_count']),
                            p95_s=percentile(times,.95), worst_s=max(times),
                            all_pass=all(r['clear_ratio']==1 and r['completion_proved'] and
                                         not r['client_error'] for r in selected),
                            **{'mean_'+k:statistics.mean(r[k] for r in selected) for k in
                               ('move_time','RF_detection_time','channel_switch_time','optical_time','clear_time')}))
    summary.sort(key=lambda r:(not r['all_pass'],r['mean_s']))
    (DEST/(name+'_summary.json')).write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)
    return summary


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    p = argparse.ArgumentParser()
    p.add_argument('--phase',default='round1')
    p.add_argument('--config',help='JSON containing cases and variants; seeds never passed to policy')
    args = p.parse_args()
    setup = json.loads(open(args.config,encoding='utf-8').read()) if args.config else dict(cases=TRAIN,variants=ROUND1)
    run_phase(args.phase,**setup)
