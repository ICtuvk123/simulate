"""Repeat four already-consumed development scenes to verify balanced dispatch."""
from frozen_experiment import execute
from compare_behavior import check
from independent_phase import check as check_exit

if __name__=='__main__':
    phase='R2_BALANCED_HARNESS_RECHECK'
    execute(phase,{
        'compact':dict(snapshot='frozen/D_COMPACT',config='frozen/D_COMPACT/configs/D_compact_optical.json',freeze='configs/D_COMPACT_FREEZE.json'),
        's22':dict(snapshot='frozen/R2_S22',config='frozen/R2_S22/configs/R2_S_outer13.json',freeze='configs/R2_S22_FREEZE.json'),
    },list(range(500001,500005)),role='harness_recheck_reused_development')
    # The original phase has 30 seeds; compare the repeated subset explicitly.
    import json
    from pathlib import Path
    from compare_behavior import signature
    root=Path(__file__).resolve().parents[1]
    def data(name,variant):
        return {r['task']['seed']:r for r in map(json.loads,(root/'reports'/name/'runs.jsonl').read_text().splitlines()) if r['task']['variant']==variant}
    result={}
    for variant,old_phase,old_variant in [('compact','R2_BASELINE_dev30','compact'),('s22','R2_ES_dev30','outer13')]:
        old,new=data(old_phase,old_variant),data(phase,variant)
        result[variant]={s:signature(new[s]['run_id'])==signature(old[s]['run_id']) for s in new}
    (root/'reports'/phase/'original_actions_identical.json').write_text(json.dumps(result,indent=2))
    if not all(all(row.values()) for row in result.values()):raise AssertionError('Dispatch changed actions')
    check_exit(phase)
