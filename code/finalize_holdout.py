"""Freeze final evidence only after every preregistered run is accounted for."""
import csv,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def finish():
    folder=ROOT/'reports/FINAL_holdout200'
    reg=json.loads((folder/'registration.json').read_text())
    selection=json.loads((ROOT/'configs/FINAL_SELECTION_FREEZE.json').read_text())
    assert reg['seeds']==selection['seeds']==list(range(420001,420201))
    assert reg['actual_frozen_execution'] and selection['selection_finished_before_holdout']
    summary=json.loads((folder/'summary.json').read_text())
    independent=json.loads((folder/'independent_exit_report.json').read_text())
    comparison=json.loads((folder/'comparison_H0_compact.json').read_text())
    assert set(summary)=={'H0','compact'}
    assert all(m['n']==200 and m['complete']==200 and m['all_success'] for m in summary.values())
    assert independent['all_valid'] and independent['runs']==400
    assert comparison['all_success'] and comparison['all_registered_pairs_present'] and comparison['identical_worlds_verified']==200
    rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text().splitlines()]
    seen=set();actions=0;fallbacks={};hashes={}
    for variant,spec in reg['snapshots'].items():
        hashes[variant]=json.loads((ROOT/spec['freeze']).read_text())['source_hashes']
    for r in rows:
        key=(r['task']['seed'],r['task']['variant']);assert key not in seen;seen.add(key)
        directory=ROOT/'runs'/r['run_id'];manifest=json.loads((directory/'manifest.json').read_text())
        assert manifest['source_hashes']==hashes[key[1]]
        replay=json.loads((directory/'feedback_replay.json').read_text());assert replay['valid']
        actions+=replay['actions'];fallbacks[key[1]]=fallbacks.get(key[1],0)+r['metrics']['fallback_count']
    assert seen=={(s,v) for s in selection['seeds'] for v in ('H0','compact')}
    incumbent=json.loads((ROOT/'INCUMBENT.json').read_text())
    for key in ('configuration','code_directory','freeze','version'):
        assert incumbent[key]==selection['selected_incumbent'][key]
    result=dict(utc=datetime.now(timezone.utc).isoformat(),phase='FINAL_holdout200',n_scenarios=200,n_runs=400,
                all_complete=True,all_feedback_replays_valid=True,replayed_actions=actions,
                all_independent_exit_checks_valid=True,exact_frozen_hashes_verified=True,
                no_selection_after_holdout=True,fallbacks=fallbacks,summary=summary,comparison=comparison)
    (ROOT/'reports/FINAL_ACCEPTANCE.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    incumbent.update(status='final_frozen',final_evidence='reports/FINAL_holdout200',final_variant='compact',
                     final_acceptance='reports/FINAL_ACCEPTANCE.json')
    (ROOT/'INCUMBENT.json').write_text(json.dumps(incumbent,indent=2),encoding='utf-8')
    command='python code/frozen_experiment.py --phase FINAL_holdout200 --variants '+json.dumps(reg['snapshots'])+' --start 420001 --count 200 --role final'
    with (ROOT/'EXPERIMENTS.csv').open('a',newline='',encoding='utf-8') as f:
        csv.writer(f).writerow(['FINAL_holdout200',result['utc'],'Independent final evaluation of the preselected incumbent',
            'Execute exact immutable H0 and D_COMPACT snapshots',json.dumps({v:hashlib.sha256(json.dumps(h,sort_keys=True).encode()).hexdigest() for v,h in hashes.items()}),
            json.dumps(reg['variants']),'final','420001-420200',command,json.dumps(comparison),'final_acceptance_not_parameter_selection'])
    return {k:v for k,v in result.items() if k not in ('summary','comparison')}


if __name__=='__main__':print(json.dumps(finish(),indent=2))
