"""Append a complete comparison record without silently promoting a candidate."""
import argparse,csv,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def record(phase,baseline,candidate,hypothesis,change,decision):
    folder=ROOT/'reports'/phase
    comparison=json.loads((folder/f'comparison_{baseline}_{candidate}.json').read_text())
    registration=json.loads((folder/'registration.json').read_text())
    rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text().splitlines()]
    first=next(r for r in rows if r['task']['variant']==candidate and r.get('metrics'))
    config=registration['variants'][candidate]
    command=f'python code/experiment.py --phase {phase} --variants '+json.dumps(registration['variants'])+f" --start {min(registration['seeds'])} --count {len(registration['seeds'])} --role {registration['role']}"
    if first['task']['replay']:command+=' --replay'
    with (ROOT/'EXPERIMENTS.csv').open('a',newline='',encoding='utf-8') as f:
        csv.writer(f).writerow([phase+'_'+candidate,datetime.now(timezone.utc).isoformat(),hypothesis,change,
                               first['metrics']['code_hash'],config,registration['role'],
                               f"{min(registration['seeds'])}-{max(registration['seeds'])}",command,json.dumps(comparison),decision])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('phase','baseline','candidate','hypothesis','change','decision'):p.add_argument(name)
    a=p.parse_args();record(**vars(a))
