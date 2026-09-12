"""Check the user-facing entry point reproduces the frozen validation pair."""
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
rows=list(csv.DictReader((ROOT/'reports/validation100/runs.csv').open(encoding='utf-8-sig')))
checks=[]
for variant in ('Gplus','G'):
    args=[sys.executable,str(ROOT/'run_candidate.py'),'--seed','13001']
    if variant=='G':args.append('--baseline')
    process=subprocess.run(args,cwd=ROOT,check=True,capture_output=True,text=True)
    actual=json.loads(process.stdout)
    expected=next(r for r in rows if r['seed']=='13001' and r['variant']==variant)
    assert abs(actual['total_time']-float(expected['total_time']))<1e-6
    assert actual['cleared']==actual['count'] and actual['completion_proved']
    assert (Path(actual['directory'])/'replay.html').is_file()
    checks.append(dict(seed=13001,identical_time=True,**actual))
(ROOT/'reports/entrypoint_check.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print(json.dumps(dict(runs=2,all_pass=True,checks=checks),indent=2))
