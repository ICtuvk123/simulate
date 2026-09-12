"""Execute untouched final scenes with immutable H0, D and selected policy.

Selection is read and sealed before any final-scene result. No promotion or
algorithm changes occur here. The seed set must not have been used previously.
"""
import csv,hashlib,json,time
from datetime import datetime,timezone
from pathlib import Path
from frozen_experiment import execute
from compare_phase import compare
from independent_phase import check
from record_experiment import record
from verify_freeze import verify
ROOT=Path(__file__).resolve().parents[1]


def main():
    seeds=list(range(520001,520201))
    with (ROOT/'SEEDS.csv').open(encoding='utf-8-sig',newline='') as stream:
        consumed={int(row['seed']) for row in csv.DictReader(stream) if row.get('seed','').isdigit()}
    if consumed.intersection(seeds):raise RuntimeError('Final seeds have already been consumed')
    incumbent=json.loads((ROOT/'INCUMBENT.json').read_text())
    if incumbent['status']!='validated':raise RuntimeError('Final testing requires a validated incumbent')
    best=dict(snapshot=str(Path(incumbent['code_directory']).parent).replace('\\','/'),
              config=incumbent['configuration'],freeze=incumbent['freeze'])
    variants={
        'H0':dict(snapshot='frozen/H0',config='frozen/H0/configs/H0.json',freeze='configs/H0_FREEZE.json'),
        'compact':dict(snapshot='frozen/D_COMPACT',config='frozen/D_COMPACT/configs/D_compact_optical.json',freeze='configs/D_COMPACT_FREEZE.json'),
        'best':best}
    for name,spec in variants.items():
        result=verify(ROOT/spec['freeze'],ROOT/spec['snapshot']/'code',ROOT/spec['config'])
        if not result['valid']:raise RuntimeError((name,result))
    phase='R2_FINAL_holdout200'
    receipt=dict(created_utc=datetime.now(timezone.utc).isoformat(),phase=phase,role='final',
                 seeds=seeds,incumbent=incumbent,variants=variants,
                 gate=json.loads((ROOT/'configs/R2_EXPERIMENT_PLAN.json').read_text())['gate'],
                 selection_made_without_final_results=True,
                 runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 prior_final_420001_420200_not_used_for_this_selection=True,
                 source_freeze_sha256={v:hashlib.sha256((ROOT/s['freeze']).read_bytes()).hexdigest() for v,s in variants.items()})
    target=ROOT/'configs/R2_FINAL_SELECTION_FREEZE.json'
    with target.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,indent=2)
    start=time.monotonic()
    summary=execute(phase,variants,seeds,'final')
    comparisons=[compare(phase,'H0','best'),compare(phase,'compact','best')]
    independent=check(phase)
    rows=[json.loads(line) for line in (ROOT/'reports'/phase/'runs.jsonl').read_text().splitlines()]
    replays=[json.loads((ROOT/'runs'/row['run_id']/'feedback_replay.json').read_text()) for row in rows]
    feedback=dict(runs=len(replays),all_valid=all(r.get('valid') for r in replays),
                  actions=sum(r.get('actions',0) for r in replays))
    for baseline in ('H0','compact'):
        record(phase,baseline,'best','Previously selected immutable policy generalizes to untouched final scenes',
               'No algorithm or configuration changes; exact frozen snapshots with identical scene engine',
               'final_evidence_only_no_post_holdout_tuning')
    result=dict(incumbent=incumbent,summary=summary,comparisons=comparisons,
                independent_all_valid=independent['all_valid'],
                feedback_replay=feedback,
                elapsed_with_postprocessing_s=time.monotonic()-start,
                algorithms_not_changed_after_final_results=True)
    (ROOT/'reports'/phase/'acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    return 0 if independent['all_valid'] and feedback['all_valid'] and all(s['all_success'] for s in summary.values()) else 1


if __name__=='__main__':raise SystemExit(main())
