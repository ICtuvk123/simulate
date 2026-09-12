"""Paired comparisons using all registered cases; verify identical post-run worlds."""
import argparse,hashlib,json,random,statistics
from pathlib import Path
from experiment import percentile

ROOT=Path(__file__).resolve().parents[1]


def compare(phase,baseline,candidate):
    folder=ROOT/'reports'/phase
    rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text().splitlines()]
    registration=json.loads((folder/'registration.json').read_text())
    data={};duplicates=False
    for r in rows:
        if r['task']['variant'] in (baseline,candidate):
            entry=data.setdefault(r['task']['seed'],{})
            duplicates|=r['task']['variant'] in entry
            entry[r['task']['variant']]=r
    pair_ok=set(data)==set(registration['seeds']) and not duplicates
    all_success=True;pairs=[];worlds=0
    for seed,pair in sorted(data.items()):
        if set(pair)!={baseline,candidate} or any('metrics' not in r for r in pair.values()):pair_ok=False;continue
        a,b=(pair[k] for k in (baseline,candidate));ma,mb=a['metrics'],b['metrics']
        all_success &= ma['all_success'] and mb['all_success']
        da=ROOT/'runs'/a['run_id'];db=ROOT/'runs'/b['run_id']
        for directory in (da,db):
            if not directory.resolve().is_relative_to((ROOT/'runs').resolve()):raise ValueError('Run path leaves evidence root')
        ea=json.loads((da/'evaluation.json').read_text());eb=json.loads((db/'evaluation.json').read_text())
        ca=json.loads((da/'manifest.json').read_text())['engine_configuration'];cb=json.loads((db/'manifest.json').read_text())['engine_configuration']
        if ea['sources']!=eb['sources'] or ca!=cb:raise AssertionError('Paired worlds or fixed error configuration differ')
        worlds+=1;pairs.append((ma['mean_time_per_source'],mb['mean_time_per_source'],ma['total_time'],mb['total_time']))
    if not pairs:raise ValueError('No comparable metrics')
    mean_a=statistics.mean(p[0] for p in pairs);mean_b=statistics.mean(p[1] for p in pairs)
    pa=percentile([p[2] for p in pairs],.95);pb=percentile([p[3] for p in pairs],.95)
    rng=random.Random(824191);samples=[];n=len(pairs)
    for _ in range(5000):
        selected=[pairs[rng.randrange(n)] for _ in range(n)]
        samples.append(100*(sum(p[0]-p[1] for p in selected)/sum(p[0] for p in selected)))
    improve=100*(mean_a-mean_b)/mean_a
    result=dict(phase=phase,baseline=baseline,candidate=candidate,pairs=n,all_registered_pairs_present=pair_ok,
                all_success=all_success,identical_worlds_verified=worlds,mean_per_source_baseline=mean_a,
                mean_per_source_candidate=mean_b,improvement_percent=improve,p95_baseline=pa,p95_candidate=pb,
                p95_change_percent=100*(pb/pa-1),bootstrap_improvement_95_percent=[percentile(samples,.025),percentile(samples,.975)],
                faster=sum(p[1]<p[0]-1e-8 for p in pairs),slower=sum(p[1]>p[0]+1e-8 for p in pairs),
                gate_passed=bool(pair_ok and all_success and improve>=1 and pb<=pa*1.02))
    (folder/f'comparison_{baseline}_{candidate}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('baseline');p.add_argument('candidate');a=p.parse_args()
    print(json.dumps(compare(a.phase,a.baseline,a.candidate),indent=2))
