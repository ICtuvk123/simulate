"""Paired evaluation that executes each variant's actual immutable snapshot.

Unlike ordinary candidate screening, H0 and incumbent can use different frozen
controller files. Their engine definitions must have identical hashes; full
world identity is also checked after execution by compare_phase.py.
"""
import argparse,csv,hashlib,json,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from experiment import ROOT,WORKERS,summarize
from verify_freeze import verify


def execute(phase,variants,seeds,role,scenes=None):
    provenance={};engine_hashes=set()
    for variant,spec in variants.items():
        provenance[variant]=[]
        for i in range(4):
            worker=WORKERS/f'w{i}';snapshot=worker/spec['snapshot']
            config=worker/spec['config'];freeze=worker/spec['freeze']
            result=verify(freeze,snapshot/'code',config)
            if not result['valid']:raise ValueError((variant,i,result))
            hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((snapshot/'code').glob('*.py'))}
            engine_hashes.add(hashes['q4engine.py'])
            entry=dict(worker=i,directory=str(worker),snapshot=str(snapshot),source_hashes=hashes,
                       configuration=json.loads(config.read_text()),config_sha256=hashlib.sha256(config.read_bytes()).hexdigest())
            if provenance[variant] and (hashes!=provenance[variant][0]['source_hashes'] or
                                       entry['config_sha256']!=provenance[variant][0]['config_sha256']):
                raise ValueError('Workers do not contain identical frozen bytes')
            provenance[variant].append(entry)
    if len(engine_hashes)!=1:raise ValueError('Frozen engine versions differ; paired generation is not justified')
    folder=ROOT/'reports'/phase;folder.mkdir(exist_ok=False)
    tasks=[dict(seed=seed,variant=variant,config=spec['config'],snapshot=spec['snapshot'],
                scene=(scenes or {}).get(str(seed),{}),replay=True)
           for seed in seeds for variant,spec in variants.items()]
    registration=dict(phase=phase,utc=datetime.now(timezone.utc).isoformat(),role=role,seeds=seeds,
                      variants={v:s['config'] for v,s in variants.items()},snapshots=variants,
                      tasks=tasks,worker_provenance=provenance,actual_frozen_execution=True,
                      isolation_wrapper='frozen_policy_worker.policy_main',
                      harness_hashes={n:hashlib.sha256((ROOT/'code'/n).read_bytes()).hexdigest()
                                      for n in ['frozen_experiment.py','snapshot_case.py','frozen_policy_worker.py','decision_guard.py']})
    (folder/'registration.json').write_text(json.dumps(registration,indent=2),encoding='utf-8')
    with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        for t in tasks:w.writerow([phase,role,t['seed'],t['variant'],'','registered_before_run'])
    start=time.monotonic()
    def batch(i):
        worker=WORKERS/f'w{i}';returned=[]
        for index,t in list(enumerate(tasks))[i::4]:
            output=folder/f'case_{index}.json'
            command=[sys.executable,str(ROOT/'code/snapshot_case.py'),'--snapshot',str(worker/t['snapshot']),
                     '--config',str(worker/t['config']),'--seed',str(t['seed']),'--scene',json.dumps(t['scene']),
                     '--run-root',str(ROOT/'runs'),'--output',str(output)]
            proc=subprocess.run(command,cwd=worker,capture_output=True,text=True,
                                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if output.exists():r=json.loads(output.read_text())
            else:r=dict(error=proc.stderr[-8000:],run_id=None)
            r['task']=t;returned.append(r)
            with (folder/f'worker{i}.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(r)+'\n')
        return returned
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(batch,i) for i in range(4)]):
            rows.extend(future.result());print(json.dumps(dict(phase=phase,completed=len(rows),total=len(tasks))),flush=True)
    rows.sort(key=lambda r:(r['task']['seed'],r['task']['variant']))
    (folder/'runs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    fields=['seed','variant','run_id','all_success','clear_count','engine_source_count','total_time','mean_time_per_source','no_signal_count','optical_failed_count','fallback_count','policy_wall_time_s','client_error']
    with (folder/'paired_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:
            m=r.get('metrics',{});w.writerow({k:r['task']['seed'] if k=='seed' else r['task']['variant'] if k=='variant' else r.get('run_id') if k=='run_id' else m.get(k,r.get('error') if k=='client_error' else None) for k in fields})
    summary=summarize(rows);(folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        for r in rows:w.writerow([phase,role,r['task']['seed'],r['task']['variant'],r.get('run_id'),'complete' if r.get('metrics',{}).get('all_success') else 'failed'])
    (folder/'elapsed.json').write_text(json.dumps(dict(wall_s=time.monotonic()-start)),encoding='utf-8')
    print(json.dumps(dict(phase=phase,summary=summary),indent=2));return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--variants',type=json.loads,required=True)
    p.add_argument('--start',required=True,type=int);p.add_argument('--count',required=True,type=int);p.add_argument('--role',required=True)
    p.add_argument('--scenes');a=p.parse_args()
    result=execute(a.phase,a.variants,list(range(a.start,a.start+a.count)),a.role,
                   json.loads(Path(a.scenes).read_text()) if a.scenes else None)
    raise SystemExit(0 if all(r['all_success'] for r in result.values()) else 1)
