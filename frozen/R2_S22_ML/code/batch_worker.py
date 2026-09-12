"""One experiment worker, run from its own detached worktree."""
import argparse,csv,json,sys,traceback
from pathlib import Path
from run_case import run_case


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args()
    job=json.loads(Path(a.job).read_text(encoding='utf-8'));out=Path(job['output'])
    with out.open('x',encoding='utf-8') as f:
        for task in job['tasks']:
            try:
                directory,m=run_case(task['seed'],task['config'],task.get('scene'),job['run_root'],task.get('replay',False))
                row=dict(task=task,run_id=directory.name,directory=str(directory),metrics={k:v for k,v in m.items() if k not in ('trajectory','per_channel_events')})
            except Exception as e:
                row=dict(task=task,run_id=None,error=f'{type(e).__name__}: {e}',traceback=traceback.format_exc())
            f.write(json.dumps(row)+'\n');f.flush()
            print(json.dumps({'seed':task['seed'],'variant':task['variant'],'success':row.get('metrics',{}).get('all_success',False),'time':row.get('metrics',{}).get('total_time'),'error':row.get('error')}),flush=True)


if __name__=='__main__':main()
