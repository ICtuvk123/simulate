"""Re-audit existing logs after verifier hardening; never fabricate new runs."""
import argparse,json,subprocess,sys,time,hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def one(run_id,output):
    from audit import postcheck,replay
    directory=ROOT/'runs'/run_id
    evaluation=json.loads((directory/'evaluation.json').read_text(encoding='utf-8'))
    audit=postcheck(directory/'requests.jsonl',evaluation)
    del evaluation
    result=dict(run_id=run_id,geometry=audit,feedback=replay(directory/'requests.jsonl'))
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return audit['valid'] and result['feedback']['valid']


def phase_check(phase):
    folder=ROOT/'reports'/phase;destination=folder/'reaudit';destination.mkdir(exist_ok=True)
    rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text(encoding='utf-8').splitlines()]
    code_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'code').glob('*.py')}
    (destination/'registration.json').write_text(json.dumps(dict(phase=phase,run_ids=[r.get('run_id') for r in rows],
         code_hashes=code_hashes,note='Existing feedback re-audit, not fresh scene evidence'),indent=2),encoding='utf-8')
    start=time.perf_counter()
    def job(row):
        rid=row.get('run_id');output=destination/(str(rid)+'.json')
        if not rid:return dict(valid=False,error='missing run_id')
        proc=subprocess.run([sys.executable,__file__,'--run',rid,'--output',str(output)],cwd=ROOT,
                            capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if not output.exists():return dict(run_id=rid,valid=False,error=proc.stderr[-4000:])
        result=json.loads(output.read_text(encoding='utf-8'))
        result['valid']=proc.returncode==0;return result
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(job,rows))
    report=dict(phase=phase,n=len(results),all_valid=all(r['valid'] for r in results),
                wall_s=time.perf_counter()-start,results=results,code_hashes=code_hashes)
    (folder/'hardened_reaudit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','code_hashes')}));return report['all_valid']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase');p.add_argument('--run');p.add_argument('--output');a=p.parse_args()
    raise SystemExit(0 if (one(a.run,a.output) if a.run else phase_check(a.phase)) else 1)
