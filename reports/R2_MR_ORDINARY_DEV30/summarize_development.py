"""Aggregate every registered ordinary development case, after both workers exit."""
import collections,csv,json,random,statistics,sys
from pathlib import Path

PHASE=Path(__file__).resolve().parent;ROOT=PHASE.parents[1]
sys.path.insert(0,str(ROOT/'code'))
from summarize_local_pair import main

reg=json.loads((PHASE/'registration.json').read_text())
rows=[json.loads(line) for p in sorted(PHASE.glob('worker*.jsonl')) for line in p.read_text().splitlines()]
assert len(rows)==len(reg['tasks'])==60
rows.sort(key=lambda r:(r['task']['seed'],r['task']['variant']))
assert {(r['task']['seed'],r['task']['variant']) for r in rows}=={(t['seed'],t['variant']) for t in reg['tasks']}
(PHASE/'runs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
main(PHASE,'M')
all_postchecks=[];hash_ok=True;counts={};by_seed={}
for row in rows:
    folder=Path(row['directory']);variant=row['task']['variant'];by_seed.setdefault(row['task']['seed'],{})[variant]=row['metrics']
    manifest=json.loads((folder/'manifest.json').read_text());hash_ok &= manifest['source_hashes']==reg['source_hashes']
    all_postchecks.append(json.loads((folder/'audit.json').read_text())['valid'])
    group=counts.setdefault(variant,collections.Counter());role=None
    for event in map(json.loads,(folder/'requests.jsonl').read_text().splitlines()):
        if event.get('reason')=='q4_action_role':role=event['role']
        if event['event']!='response' or event.get('http_status')!=200 or event['path']!='/measure':continue
        body=json.loads(event['response_body'])
        if body.get('accepted') and role=='adaptive_single_probe':group[body['measure_result']]+=1
paired=[dict(seed=s,total_saved_s=v['M']['total_time']-v['MR']['total_time'],
        per_source_saved_s=v['M']['mean_time_per_source']-v['MR']['mean_time_per_source']) for s,v in sorted(by_seed.items())]
diff=[p['per_source_saved_s'] for p in paired];rng=random.Random(819345)
boot=sorted(statistics.mean(rng.choices(diff,k=len(diff))) for _ in range(20000))
summary=json.loads((PHASE/'summary.json').read_text());comparison=summary['comparison']
gate=(comparison['all_complete'] and comparison['all_feedback_replay_valid'] and comparison['all_independent_exit_valid']
      and all(all_postchecks) and hash_ok and comparison['MR']['mean_per_source_improvement_over_M']>=.01
      and comparison['MR']['p95_change']<=.02)
diagnostic=dict(all_postchecks_valid=all(all_postchecks),all_hashes_match_registration=hash_ok,
    actual_single_feedback={v:dict(c) for v,c in counts.items()},paired_mean_saved_per_source_s=statistics.mean(diff),
    paired_bootstrap_95_interval_s=[boot[500],boot[19499]],
    wins=sum(p['total_saved_s']>1e-6 for p in paired),ties=sum(abs(p['total_saved_s'])<=1e-6 for p in paired),
    losses=sum(p['total_saved_s']< -1e-6 for p in paired),predeclared_engineering_screen_pass=gate,
    promotion_allowed=False,reason='Development reused seeds only; independent untouched validation mandatory even if screen passes')
(PHASE/'diagnostic.json').write_text(json.dumps(diagnostic,indent=2))
with (PHASE/'paired_differences.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
print(json.dumps(diagnostic,indent=2))
