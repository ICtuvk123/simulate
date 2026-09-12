"""Verify option-off actions against an unchanged frozen-policy phase."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def signature(run_id):
    records=[json.loads(s) for s in (ROOT/'runs'/run_id/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
    return [(r['path'],{k:v for k,v in r['payload'].items() if k not in ('request_id','robot_id')})
            for r in records if r['event']=='request']


def check(reference,phase,variant='compact'):
    def rows(name):
        return {r['task']['seed']:r for r in [json.loads(s) for s in (ROOT/'reports'/name/'runs.jsonl').read_text(encoding='utf-8').splitlines()]
                if r['task']['variant']==variant}
    a,b=rows(reference),rows(phase)
    same={s:signature(a[s]['run_id'])==signature(b[s]['run_id']) for s in sorted(set(a)&set(b))}
    report=dict(reference_phase=reference,phase=phase,variant=variant,paired_scenarios=len(same),
                identical_actions=bool(same) and set(a)==set(b) and all(same.values()),
                differing_seeds=[s for s,v in same.items() if not v])
    (ROOT/'reports'/phase/'disabled_baseline_behavior.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reference');p.add_argument('phase');p.add_argument('--variant',default='compact')
    a=p.parse_args();raise SystemExit(0 if check(a.reference,a.phase,a.variant)['identical_actions'] else 1)
