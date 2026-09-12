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
    frozen=registration.get('actual_frozen_execution',False)
    runner='frozen_experiment.py' if frozen else 'experiment.py'
    variants=registration['snapshots'] if frozen else registration['variants']
    # Single quotes preserve JSON in PowerShell; registered values contain no
    # user-supplied shell fragments. Name the reproduction separately so an
    # existing evidence phase can never be overwritten by the suggested call.
    arguments=json.dumps(variants)
    if "'" in arguments:raise ValueError('Use structured runner for quotes in registered paths')
    command=f"python code/{runner} --phase {phase}_reproduction --variants '{arguments}'"+f" --start {min(registration['seeds'])} --count {len(registration['seeds'])} --role reproduction"
    if not frozen and first['task']['replay']:command+=' --replay'
    scenes={str(t['seed']):t['scene'] for t in registration['tasks'] if t.get('scene')}
    if scenes:
        scene_file=folder/'reproduction_scenes.json'
        scene_file.write_text(json.dumps(scenes,indent=2),encoding='utf-8')
        command+=' --scenes '+scene_file.relative_to(ROOT).as_posix()
    with (ROOT/'EXPERIMENTS.csv').open('a',newline='',encoding='utf-8') as f:
        csv.writer(f).writerow([phase+'_'+candidate,datetime.now(timezone.utc).isoformat(),hypothesis,change,
                               first['metrics']['code_hash'],config,registration['role'],
                               f"{min(registration['seeds'])}-{max(registration['seeds'])}",command,json.dumps(comparison),decision])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('phase','baseline','candidate','hypothesis','change','decision'):p.add_argument(name)
    a=p.parse_args();record(**vars(a))
