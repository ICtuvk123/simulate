"""Bind completed final evidence to the policy selected before the holdout."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from promote_candidate import require_independent_exit
ROOT=Path(__file__).resolve().parents[1]


def finish():
    phase='R2_FINAL_holdout200';folder=ROOT/'reports'/phase
    selection=json.loads((ROOT/'configs/R2_FINAL_SELECTION_FREEZE.json').read_text())
    registration=json.loads((folder/'registration.json').read_text())
    result=json.loads((folder/'acceptance.json').read_text())
    incumbent=json.loads((ROOT/'INCUMBENT.json').read_text())
    if selection['seeds']!=list(range(520001,520201)) or registration['seeds']!=selection['seeds']:
        raise ValueError('Final seed registration changed')
    if not selection['selection_made_without_final_results'] or not registration['actual_frozen_execution']:
        raise ValueError('Final execution/selection provenance missing')
    for name in ('version','code_directory','configuration','freeze'):
        if incumbent[name]!=selection['incumbent'][name]:raise ValueError('Incumbent changed after final selection')
    variants=selection['variants']
    if set(variants)!={'H0','compact','best'} or registration['snapshots']!=variants:
        raise ValueError('Final snapshots differ from selected snapshots')
    hashes={}
    for variant,spec in variants.items():
        freeze_path=ROOT/spec['freeze']
        if hashlib.sha256(freeze_path.read_bytes()).hexdigest()!=selection['source_freeze_sha256'][variant]:
            raise ValueError('Selected source freeze changed')
        hashes[variant]=json.loads(freeze_path.read_text())['source_hashes']
    rows=[json.loads(line) for line in (folder/'runs.jsonl').read_text().splitlines()]
    seen=set();actions=0
    for row in rows:
        key=(row['task']['seed'],row['task']['variant'])
        if key in seen or not row['metrics']['all_success']:raise ValueError('Duplicate or incomplete final run')
        seen.add(key);directory=ROOT/'runs'/row['run_id']
        manifest=json.loads((directory/'manifest.json').read_text())
        if manifest['source_hashes']!=hashes[key[1]]:raise ValueError('Actual run differs from frozen source')
        require_independent_exit(directory)
        replay=json.loads((directory/'feedback_replay.json').read_text())
        if not replay['valid']:raise ValueError('Final feedback replay failed')
        actions+=replay['actions']
    if seen!={(seed,v) for seed in selection['seeds'] for v in variants}:raise ValueError('Final registered cases missing')
    if not result['independent_all_valid'] or not result['feedback_replay']['all_valid']:
        raise ValueError('Final acceptance checks failed')
    for comparison in result['comparisons']:
        if not (comparison['all_success'] and comparison['all_registered_pairs_present'] and comparison['identical_worlds_verified']==200):
            raise ValueError('Final comparison lacks complete same-world pairs')
    result.update(finalized_utc=datetime.now(timezone.utc).isoformat(),n_scenarios=200,n_runs=len(rows),
                  replayed_actions=actions,all_complete=True,exact_frozen_hashes_verified=True,
                  no_selection_after_holdout=True)
    (ROOT/'reports/R2_FINAL_ACCEPTANCE.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    incumbent.update(status='final_frozen',final_evidence='reports/'+phase,final_variant='best',
                     final_acceptance='reports/R2_FINAL_ACCEPTANCE.json')
    (ROOT/'INCUMBENT.json').write_text(json.dumps(incumbent,indent=2),encoding='utf-8')
    return dict(version=incumbent['version'],runs=len(rows),replayed_actions=actions,all_complete=True)


if __name__=='__main__':print(json.dumps(finish(),indent=2))
