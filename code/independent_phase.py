"""Run the second exit implementation over every registered result in a phase."""
import argparse,json,time
from pathlib import Path
from independent_exit import verify
ROOT=Path(__file__).resolve().parents[1]


def check(phase):
    folder=ROOT/'reports'/phase;start=time.monotonic();results=[]
    rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text().splitlines()]
    for i,r in enumerate(rows):
        directory=ROOT/'runs'/r['run_id'] if r.get('run_id') else None
        try:
            result=verify(directory/'requests.jsonl')
            (directory/'independent_exit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        except Exception as e:result=dict(valid=False,errors=[type(e).__name__+': '+str(e)])
        results.append(dict(seed=r['task']['seed'],variant=r['task']['variant'],run_id=r.get('run_id'),**result))
        if (i+1)%25==0:print(json.dumps(dict(phase=phase,verified=i+1,total=len(rows))),flush=True)
    report=dict(phase=phase,runs=len(rows),all_valid=all(r['valid'] for r in results),
                failures=[r for r in results if not r['valid']],elapsed_s=time.monotonic()-start,
                results=results,truth_read=False,controller_geometry_imported=False)
    (folder/'independent_exit_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');a=p.parse_args()
    raise SystemExit(0 if check(a.phase)['all_valid'] else 1)
