"""Paired local experimentation with immutable baseline and post-exit audits."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import hashlib
import json
import multiprocessing
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))


def execute(job):
    variant,case=job
    import runner
    from policy_factory import policy_class
    from g_policy_presets import FROZEN_G_OPTIONS
    from geometry import contains
    candidate=json.loads((ROOT/'BASELINE_candidate.json').read_text(encoding='utf-8'))
    options={**FROZEN_G_OPTIONS,**candidate['options'],**variant.get('options',{})}
    extra={**candidate['extra'],**variant.get('extra',{})}
    controller=policy_class(variant.get('kind','Gplus'))
    runner.RouteSearchController=lambda client,**kw:controller(client,**kw,**extra)
    directory,payload=runner.run_case(**case,strategy='G',policy_options=options,
                                      compute_oracle=False,update_latest=False)
    (directory/'experiment_variant.json').write_text(json.dumps(variant,indent=2),encoding='utf-8')
    m=payload['metrics'];ev=payload['evaluation']
    truth={s['channel']:(s['x'],s['y']) for s in ev.get('sources',[])}
    count=0;errors=[];reasons={};timed_fallbacks=0
    for line in (directory/'requests.jsonl').read_text(encoding='utf-8').splitlines():
        record=json.loads(line);reason=record.get('reason','')
        if record.get('future_fallback'):timed_fallbacks+=1
        if reason:reasons[reason]=reasons.get(reason,0)+1
        if reason in ('F_feedback_region','F_optical_negative_region','O_optical_negative_region'):
            count+=1;p=truth.get(record['channel'])
            if p is None or not contains(record['polygon'],p,tolerance=1e-3) or not any(
                    contains(piece,p,tolerance=1e-3) for piece in record['pieces']):
                errors.append('region_dropped_truth:'+str(record['channel']))
    accounted=sum(m.get(k,0) for k in ('move_time','RF_detection_time','channel_switch_time','optical_time','clear_time'))
    if abs(accounted-m['total_time'])>0.002:errors.append('accounting_difference')
    if m.get('accounting_warnings'):errors.append('accounting_warnings')
    if ev.get('ended_reason')!='user_exit':errors.append('not_user_exit')
    row=dict(variant=variant['name'],kind=variant.get('kind','Gplus'),**case)
    row.setdefault('scenario','uniform');row.setdefault('reception','mixed');row.setdefault('error_mode','fixed_hash')
    for k in ('run_id','strategy_hash','parameter_hash','clear_count','jammer_count','clear_ratio','total_time',
              'move_time','move_distance','RF_detection_count','RF_detection_time','channel_switch_time',
              'optical_time','clear_time','optical_failed_count','completion_proved','client_error',
              'measured_program_wall_time_s','average_localization_clear_time_s_per_source'):
        row[k]=m.get(k)
    row.update(variant_hash=hashlib.sha256(json.dumps(variant,sort_keys=True).encode()).hexdigest(),
        scene_hash=hashlib.sha256(json.dumps(ev.get('sources'),sort_keys=True).encode()).hexdigest(),
        region_checks=count,audit_errors=';'.join(errors),audit_pass=not errors,future_timed_fallbacks=timed_fallbacks,
        experimental_events=sum(v for k,v in reasons.items() if k.startswith(('N_','H_','O_','R_','OPT_','FUT_','next_'))))
    (directory/'next_audit.json').write_text(json.dumps(dict(region_checks=count,errors=errors,reasons=reasons),indent=2),encoding='utf-8')
    return row


def main():
    parser=argparse.ArgumentParser();parser.add_argument('config');args=parser.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    out=ROOT/'reports'/config['phase'];out.mkdir(parents=True,exist_ok=False)
    config['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'code').glob('*.py'))}
    (out/'manifest.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    jobs=[(v,c) for c in config['cases'] for v in config['variants']];rows=[]
    fields=None;started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=config.get('workers',6),mp_context=multiprocessing.get_context('spawn')) as pool:
        futures=[pool.submit(execute,job) for job in jobs]
        for future in as_completed(futures):
            row=future.result();rows.append(row)
            fields=sorted(set().union(*(r.keys() for r in rows)))
            with (out/'runs.csv').open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
            if len(rows)%8==0 or not row['audit_pass'] or row['client_error'] or row['clear_ratio']!=1:
                print(json.dumps(dict(done=len(rows),total=len(jobs),elapsed=round(time.perf_counter()-started,1),
                    variant=row['variant'],seed=row['seed'],mean=row['average_localization_clear_time_s_per_source'],
                    error=row['client_error'],audit=row['audit_errors'])),flush=True)
    summary=[]
    for variant in config['variants']:
        selected=[r for r in rows if r['variant']==variant['name']]
        good=all(r['audit_pass'] and r['clear_ratio']==1 and r['completion_proved'] and not r['client_error'] for r in selected)
        summary.append(dict(variant=variant['name'],n=len(selected),all_pass=good,
            **{'mean_'+k:statistics.mean(r[k] for r in selected if r[k] is not None) for k in (
                'total_time','move_time','RF_detection_time','channel_switch_time','optical_time','clear_time',
                'optical_failed_count','average_localization_clear_time_s_per_source','measured_program_wall_time_s')},
            worst=max(r['total_time'] for r in selected)))
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    multiprocessing.freeze_support();main()
