"""Registered paired local experiments in independent read-only code worktrees."""
import argparse,csv,hashlib,json,math,os,statistics,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKERS=ROOT.parent/(ROOT.name+'_workers')


def worker_provenance(variants,workers=4):
    entries=[]
    for i in range(workers):
        directory=WORKERS/f'w{i}'
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((directory/'code').glob('*.py'))}
        commit=subprocess.check_output(['git','-c','safe.directory='+directory.as_posix(),'-C',str(directory),'rev-parse','HEAD'],text=True).strip()
        configs={name:dict(sha256=hashlib.sha256((directory/'configs'/filename).read_bytes()).hexdigest(),
                           options=json.loads((directory/'configs'/filename).read_text())) for name,filename in variants.items()}
        entries.append(dict(worker=i,directory=str(directory),commit=commit,source_hashes=hashes,configurations=configs))
    for row in entries[1:]:
        if any(row[k]!=entries[0][k] for k in ('commit','source_hashes','configurations')):
            raise RuntimeError('Worker code/config bytes differ before experiment; resynchronize worktrees')
    return entries


def percentile(x,q):
    x=sorted(x);p=(len(x)-1)*q;i=int(p)
    return x[i]+(x[min(i+1,len(x)-1)]-x[i])*(p-i)


def summarize(rows):
    out={}
    for variant in sorted(set(r['task']['variant'] for r in rows)):
        selected=[r for r in rows if r['task']['variant']==variant];metrics=[r['metrics'] for r in selected if 'metrics' in r]
        valid=all(m['all_success'] for m in metrics) and len(metrics)==len(selected)
        result=dict(n=len(selected),complete=sum(m['all_success'] for m in metrics),all_success=valid,
                    missing_metrics=len(selected)-len(metrics))
        if metrics:
            result.update(mean_total=statistics.mean(m['total_time'] for m in metrics),
                          mean_per_source=statistics.mean(m['mean_time_per_source'] for m in metrics),
                          p95=percentile([m['total_time'] for m in metrics],.95),
                          worst=max(m['total_time'] for m in metrics),
                          mean_wall=statistics.mean(m['policy_wall_time_s'] for m in metrics),
                          worst_wall=max(m['policy_wall_time_s'] for m in metrics))
            for field in ['move_time','RF_detection_time','channel_switch_time','optical_time','clear_time','no_signal_count','optical_failed_count','fallback_count','journal_bytes']:
                result['mean_'+field]=statistics.mean(m[field] for m in metrics)
            roles={}
            for m in metrics:
                for role,values in m['role_cost'].items():
                    for field,value in values.items():roles.setdefault(role,{}).setdefault(field,[]).append(value)
            result['mean_role_cost']={role:{k:sum(v)/len(metrics) for k,v in fields.items()} for role,fields in roles.items()}
        out[variant]=result
    return out


def run_phase(phase,variants,seeds,role='development',scenes=None,replay=False,workers=4):
    provenance=worker_provenance(variants,workers)
    directory=ROOT/'reports'/phase;directory.mkdir(exist_ok=False)
    tasks=[dict(seed=seed,variant=variant,config='configs/'+filename,scene=(scenes or {}).get(str(seed),{}),replay=replay)
           for seed in seeds for variant,filename in variants.items()]
    registration=dict(phase=phase,utc=datetime.now(timezone.utc).isoformat(),role=role,
                      variants=variants,seeds=seeds,tasks=tasks,workers=workers,worker_provenance=provenance)
    (directory/'registration.json').write_text(json.dumps(registration,indent=2),encoding='utf-8')
    with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        for task in tasks:writer.writerow([phase,role,task['seed'],task['variant'],'','registered_before_run'])
    processes=[]
    for i in range(workers):
        worktree=WORKERS/f'w{i}';log=(directory/f'worker{i}.log').open('w',encoding='utf-8')
        job=dict(tasks=tasks[i::workers],output=str(directory/f'worker{i}.jsonl'),run_root=str(ROOT/'runs'))
        job_path=directory/f'job{i}.json';job_path.write_text(json.dumps(job,indent=2),encoding='utf-8')
        proc=subprocess.Popen([sys.executable,str(worktree/'code/batch_worker.py'),'--job',str(job_path)],cwd=worktree,stdout=log,stderr=subprocess.STDOUT,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        processes.append((proc,log))
    started=time.monotonic();last=-1
    while any(proc.poll() is None for proc,_ in processes):
        completed=sum(len(p.read_text(encoding='utf-8').splitlines()) for p in directory.glob('worker*.jsonl'))
        if completed!=last:
            print(json.dumps(dict(phase=phase,completed=completed,total=len(tasks),wall_s=round(time.monotonic()-started,1))),flush=True);last=completed
        time.sleep(1)
    for proc,log in processes:log.close()
    rows=[json.loads(line) for p in sorted(directory.glob('worker*.jsonl')) for line in p.read_text(encoding='utf-8').splitlines()]
    rows.sort(key=lambda r:(r['task']['seed'],r['task']['variant']))
    present={(r['task']['seed'],r['task']['variant']) for r in rows}
    for task in tasks:
        if (task['seed'],task['variant']) not in present:rows.append(dict(task=task,error='worker_did_not_return',run_id=None))
    with (directory/'runs.jsonl').open('w',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row)+'\n')
    fields=['seed','variant','run_id','all_success','clear_count','engine_source_count','total_time','mean_time_per_source','no_signal_count','optical_failed_count','fallback_count','policy_wall_time_s','client_error']
    with (directory/'paired_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:
            m=row.get('metrics',{});writer.writerow({k:row['task']['seed'] if k=='seed' else row['task']['variant'] if k=='variant' else row.get('run_id') if k=='run_id' else m.get(k,row.get('error') if k=='client_error' else None) for k in fields})
    result=summarize(rows);(directory/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        for row in rows:writer.writerow([phase,role,row['task']['seed'],row['task']['variant'],row.get('run_id'),'complete' if row.get('metrics',{}).get('all_success') else 'failed'])
    print(json.dumps(dict(phase=phase,summary=result),indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--variants',type=json.loads,required=True)
    p.add_argument('--start',type=int,required=True);p.add_argument('--count',type=int,default=30);p.add_argument('--role',default='development');p.add_argument('--replay',action='store_true')
    p.add_argument('--scenes',type=Path)
    a=p.parse_args();run_phase(a.phase,a.variants,list(range(a.start,a.start+a.count)),a.role,json.loads(a.scenes.read_text()) if a.scenes else None,a.replay)
