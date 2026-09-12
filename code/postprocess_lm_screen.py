"""Analyze every registered complete L/M pair and record single-factor contrasts."""
import json
from compare_phase import compare
from compare_behavior import check as compare_behavior
from independent_phase import check
from record_experiment import record

if __name__=='__main__':
    phase='R2_LM_dev30'
    for baseline,candidate,hypothesis,change in (
        ('compact','stable','Stable region quadrature reduces representation-driven planning error','Enable stable_quadrature only'),
        ('compact','single','One RF with full pair recovery avoids unnecessary paired travel','Enable adaptive_single only'),
        ('single','single_stable','Stable quadrature improves adaptive single decisions','Enable stable_quadrature on M only'),
        ('stable','single_stable','One RF improves the stabilized baseline','Enable adaptive_single on L only'),
    ):
        result=compare(phase,baseline,candidate);print(json.dumps(result),flush=True)
        record(phase,baseline,candidate,hypothesis,change,'development_gate_passed_requires_new_validation' if result['gate_passed'] else 'not_promoted_development_gate_failed')
    print(compare_behavior('R2_BASELINE_dev30',phase),flush=True)
    check(phase)
