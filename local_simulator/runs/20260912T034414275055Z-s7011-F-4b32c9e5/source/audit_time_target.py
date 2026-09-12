"""Read completed local experiments only and audit a requested time target."""
import csv
import json
import math
import statistics

from runner import ROOT, oracle_bound


def audit():
    destination = ROOT / 'reports' / 'optimization'
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    with (ROOT / 'reports' / 'paired_runs.csv').open(encoding='utf-8-sig') as stream:
        cases = [r for r in csv.DictReader(stream) if r['strategy'] == 'B']
    for row in cases:
        result = json.loads((ROOT / 'runs' / row['run_id'] / 'result.json').read_text(encoding='utf-8'))
        evaluation = result['evaluation']
        assert evaluation['events'][-1]['path'] == '/exit', 'Post-run evaluation only'
        bound = oracle_bound(evaluation)
        sources = evaluation['sources']
        farthest = max(math.hypot(s['x'], s['y']) for s in sources)
        rows.append(dict(seed=int(row['seed']), split=row['split'], count=len(sources),
                         baseline_B_time=float(row['total_time']),
                         farthest_source_m=farthest,
                         farthest_and_service_lower_bound=max(0, farthest-20)/5+5*len(sources),
                         oracle_lower_bound_s=bound['lower_bound_time'],
                         completed_local_run=row['run_id']))
    with (destination / 'physical_lower_bounds.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(cases=len(rows), mean_B_s=statistics.mean(r['baseline_B_time'] for r in rows),
                   mean_oracle_lower_bound_s=statistics.mean(r['oracle_lower_bound_s'] for r in rows),
                   minimum_oracle_lower_bound_s=min(r['oracle_lower_bound_s'] for r in rows),
                   mean_farthest_service_lower_bound_s=statistics.mean(r['farthest_and_service_lower_bound'] for r in rows),
                   all_cases_impossible_under_300_s=all(r['oracle_lower_bound_s'] > 300 for r in rows),
                   uniform_iid_n10_expected_lower_bound_s=(1800*20/21-20)/5+50,
                   scope='Local completed cases only. Hidden coordinates are never supplied to a controller.')
    (destination / 'feasibility.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


if __name__ == '__main__':
    audit()
