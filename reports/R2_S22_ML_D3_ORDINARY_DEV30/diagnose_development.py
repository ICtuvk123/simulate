"""Post-run only: no scene data is supplied to the decision maker."""
import collections,csv,json,random,statistics
from pathlib import Path
PHASE=Path(__file__).resolve().parent
reg=json.loads((PHASE/'registration.json').read_text());rows=[json.loads(l) for l in (PHASE/'runs.jsonl').read_text().splitlines()]
assert len(rows)==60==len(reg['tasks'])
stats={};all_valid=[];same_hash=True;by_seed={}
for row in rows:
    folder=Path(row['directory']);variant=row['task']['variant'];by_seed.setdefault(row['task']['seed'],{})[variant]=row['metrics']
    manifest=json.loads((folder/'manifest.json').read_text());same_hash &= manifest['source_hashes']==reg['source_hashes']
    config=reg['configurations'][Path(row['task']['config']).name]['options'];assert manifest['policy_options']==config
    audit=json.loads((folder/'audit.json').read_text());all_valid.append(audit['valid'])
    data=stats.setdefault(variant,dict(actual_contractions=0,area_removed_m2=0.,cases=[]))
    clips=[e for e in map(json.loads,(folder/'requests.jsonl').read_text().splitlines()) if e.get('reason')=='q4_negative_chord_clip']
    assert len(clips)==audit['chord_contractions']
    data['actual_contractions']+=len(clips);data['area_removed_m2']+=sum(e['area_removed_m2'] for e in clips)
    data['cases'].append(dict(seed=row['task']['seed'],contractions=len(clips),run_id=row['run_id']))
paired=[dict(seed=s,total_saved_s=x['S22ML']['total_time']-x['S22MLD3']['total_time'],
    per_source_saved_s=x['S22ML']['mean_time_per_source']-x['S22MLD3']['mean_time_per_source']) for s,x in sorted(by_seed.items())]
diff=[p['per_source_saved_s'] for p in paired];rng=random.Random(819347)
boot=sorted(statistics.mean(rng.choices(diff,k=len(diff))) for _ in range(20000))
result=dict(all_postchecks_valid=all(all_valid),all_source_hashes_match=same_hash,contractions=stats,
    mean_per_source_saved_s=statistics.mean(diff),paired_development_bootstrap_95_interval_s=[boot[500],boot[19499]],
    wins=sum(p['total_saved_s']>1e-6 for p in paired),ties=sum(abs(p['total_saved_s'])<=1e-6 for p in paired),
    losses=sum(p['total_saved_s']< -1e-6 for p in paired),not_independent_validation=True)
(PHASE/'diagnostic.json').write_text(json.dumps(result,indent=2))
with (PHASE/'paired_differences.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
strata={}
for mix in ('mixed',):
    strata[mix]={}
    for v in stats:
        ms=[r['metrics'] for r in rows if r['task']['variant']==v and r['task']['scene'].get('source_mix','mixed')==mix]
        strata[mix][v]=dict(n=len(ms),mean_per_source=statistics.mean(m['mean_time_per_source'] for m in ms))
(PHASE/'strata_summary.json').write_text(json.dumps(strata,indent=2))
print(json.dumps(dict(result=result,strata=strata),indent=2))
