"""Register an exact executed-worker candidate before a fresh validation set."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from experiment import ROOT,worker_provenance


def freeze(name,config,start,count):
    workers=worker_provenance({name:config});p=workers[0]
    result=dict(version=name,utc=datetime.now(timezone.utc).isoformat(),commit=p['commit'],
                configuration=p['configurations'][name]['options'],config_sha256=p['configurations'][name]['sha256'],
                source_hashes=p['source_hashes'],worker_directories=[w['directory'] for w in workers],
                validation_seeds=list(range(start,start+count)),
                gate=dict(min_improvement_percent=1,max_p95_increase_percent=2,failures_allowed=0),
                independent_before_results=True)
    path=ROOT/'configs'/f'{name}_VALIDATION_FREEZE.json'
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8');return path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('config');p.add_argument('--start',required=True,type=int);p.add_argument('--count',type=int,default=100)
    a=p.parse_args();print(freeze(a.name,a.config,a.start,a.count))
