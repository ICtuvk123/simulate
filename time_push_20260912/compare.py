"""Paired statistics on per-scene T/n, with a fixed bootstrap seed."""
import argparse
import csv
import json
from pathlib import Path
import random
import statistics

ROOT=Path(__file__).resolve().parent


def compare(phase):
    folder=ROOT/'reports'/phase
    rows=list(csv.DictReader((folder/'runs.csv').open(encoding='utf-8-sig')))
    groups={}
    for r in rows:
        groups.setdefault(r['variant'],{})[r['seed']]=r
    base=groups['G'];result=[]
    metric='average_localization_clear_time_s_per_source'
    for name,group in groups.items():
        if name=='G':continue
        assert set(base)==set(group)
        keys=sorted(base)
        diffs=[float(base[s][metric])-float(group[s][metric]) for s in keys]
        dt=[float(base[s]['total_time'])-float(group[s]['total_time']) for s in keys]
        rng=random.Random(20260912)
        boot=sorted(statistics.mean(rng.choices(diffs,k=len(diffs))) for _ in range(10000))
        b=statistics.mean(float(base[s][metric]) for s in keys)
        result.append(dict(variant=name,n=len(keys),baseline_s_per_source=b,
            candidate_s_per_source=statistics.mean(float(group[s][metric]) for s in keys),
            saved_s_per_source=statistics.mean(diffs),saved_percent=100*statistics.mean(diffs)/b,
            saved_s_per_source_ci95=[boot[249],boot[9749]],saved_s_per_scene=statistics.mean(dt),
            wins=sum(d>1e-6 for d in diffs),ties=sum(abs(d)<=1e-6 for d in diffs),
            losses=sum(d< -1e-6 for d in diffs),worst_regression_s_per_source=-min(diffs),
            all_pass=all(r['clear_ratio']=='1.0' and r['completion_proved']=='True' and not r['client_error'] for r in group.values())))
    result.sort(key=lambda r:-r['saved_s_per_source'])
    (folder/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');a=p.parse_args();compare(a.phase)
