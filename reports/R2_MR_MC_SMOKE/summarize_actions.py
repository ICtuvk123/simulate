"""Post-run evidence only; policy modules never import this report utility."""
import collections,csv,hashlib,json,random,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parent
rows=[json.loads(x) for x in (ROOT/'runs.jsonl').read_text().splitlines()]
registration=json.loads((ROOT/'registration.json').read_text())
assert len(rows)==30==len(registration['tasks'])
variants={};audits=[];hash_sets=[]
for row in rows:
    variant=row['task']['variant'];run=Path(row['directory'])
    counts=collections.Counter();feedback=collections.Counter();single_rows=[]
    rank=None;role=None;max_chain=0;chain=0;chain_ch=None
    for event in map(json.loads,(run/'requests.jsonl').read_text().splitlines()):
        reason=event.get('reason','')
        if reason.startswith('q4_single_recovery_'):counts[reason]+=1
        if reason=='q4_adaptive_single_rank':rank=event
        if reason=='q4_action_role':role=event['role']
        if event['event']!='response' or event.get('http_status')!=200:continue
        body=json.loads(event['response_body'])
        if not body.get('accepted') or event['path'] not in ('/measure','/clear'):continue
        result=body.get('measure_result',body.get('clear_result'))
        ch=event['payload']['channel']
        if role=='adaptive_single_probe' and event['path']=='/measure':
            feedback[result]+=1
            single_rows.append(dict(channel=ch,result=result,point=rank['point'],
              candidate_kind=rank['candidate_kind'],predicted_no_signal=rank['branches']['no_signal'],
              predicted_physical_cost_s=rank.get('expected_remaining_s',rank['estimated_remaining_s']),
              pair_cost_s=rank['original_pair_cost_s'],risk_premium_s=rank.get('risk_premium_s',0.)))
            if result=='no_signal':
                chain=chain+1 if chain_ch==ch else 1;chain_ch=ch;max_chain=max(max_chain,chain)
            else:chain=0;chain_ch=None
        else:chain=0;chain_ch=None
        if role=='committed_single_recovery':counts['actual_recovery_'+result]+=1
    audit=json.loads((run/'audit.json').read_text());audits.append(audit['valid'])
    manifest=json.loads((run/'manifest.json').read_text());hash_sets.append(manifest['source_hashes'])
    assert manifest['source_hashes']==registration['source_hashes']
    variants.setdefault(variant,[]).append(dict(seed=row['task']['seed'],run_id=row['run_id'],
        event_counts=dict(counts),single_feedback=dict(feedback),maximum_consecutive_negative_singles=max_chain,
        actual_singles=single_rows))
out=dict(all_postcheck_valid=all(audits),all_code_hashes_match_registration=True,variants={})
for variant,group in variants.items():
    counts=collections.Counter();feedback=collections.Counter()
    for case in group:counts.update(case['event_counts']);feedback.update(case['single_feedback'])
    out['variants'][variant]=dict(event_counts=dict(counts),single_feedback=dict(feedback),
        maximum_consecutive_negative_singles=max(c['maximum_consecutive_negative_singles'] for c in group),cases=group)
(ROOT/'action_diagnostic.json').write_text(json.dumps(out,indent=2))
by_seed={}
for r in rows:by_seed.setdefault(r['task']['seed'],{})[r['task']['variant']]=r['metrics']
paired=[];intervals={};rng=random.Random(819344)
for seed,cases in sorted(by_seed.items()):
    base=cases['M']
    for variant in ('MR','MC'):
        m=cases[variant]
        paired.append(dict(seed=seed,variant=variant,total_saved_s=base['total_time']-m['total_time'],
            per_source_saved_s=base['mean_time_per_source']-m['mean_time_per_source']))
for variant in ('MR','MC'):
    selected=[p for p in paired if p['variant']==variant];differences=[p['per_source_saved_s'] for p in selected]
    boot=sorted(statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(20000))
    intervals[variant]=dict(mean_per_source_saved_s=statistics.mean(differences),
        paired_smoke_bootstrap_95_interval_s=[boot[500],boot[19499]],
        wins=sum(p['total_saved_s']>1e-6 for p in selected),ties=sum(abs(p['total_saved_s'])<=1e-6 for p in selected),
        losses=sum(p['total_saved_s']< -1e-6 for p in selected),
        interpretation='Heterogeneous smoke only; not independent validation or official distribution')
(ROOT/'paired_difference_intervals.json').write_text(json.dumps(intervals,indent=2))
with (ROOT/'paired_differences.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
strata={}
for mix in ('mixed','directional','omni'):
    strata[mix]={}
    for variant in variants:
        ms=[r['metrics'] for r in rows if r['task']['variant']==variant and r['task']['scene'].get('source_mix','mixed')==mix]
        strata[mix][variant]=dict(n=len(ms),mean_per_source=statistics.mean(m['mean_time_per_source'] for m in ms),
                                   mean_total=statistics.mean(m['total_time'] for m in ms))
(ROOT/'strata_summary.json').write_text(json.dumps(strata,indent=2))
print(json.dumps(dict(intervals=intervals,counts={k:{x:v[x] for x in ('event_counts','single_feedback','maximum_consecutive_negative_singles')} for k,v in out['variants'].items()},strata=strata),indent=2))
