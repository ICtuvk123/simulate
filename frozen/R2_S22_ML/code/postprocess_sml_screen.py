"""Prespecified one-factor comparisons for the seven-arm complete-scene screen."""
import json
from compare_phase import compare
from independent_phase import check
from record_experiment import record
from compare_behavior import check as behavior_check

CONTRASTS=[
    ('s22','s22_ml','M and stable quadrature transfer to S22','Enable the previously screened ML action model on S22'),
    ('s22','s22_o','An informative scheduled scan can precede source commitment','Enable scan_before_commit only'),
    ('s22_ml','s22_mlo','Scheduled scan promotion helps the ML action model','Enable scan_before_commit on S22ML only'),
    ('s22_ml','s22_mln','Canonical candidate geometry improves ML decisions','Enable canonical_single_candidates on S22ML only'),
    ('s22','s21','An independently proved 21-station plan improves full-scene cost','Replace the whole search skeleton by 8@999 plus 12@1869'),
    ('s21','s21_ml','ML actions improve the 21-station controller','Enable the previously screened ML model on S21'),
    ('s22_ml','s21_ml','The 21-station plan improves the ML controller','Change only the complete search skeleton'),
]

if __name__=='__main__':
    phase='R2_SML_dev30'
    for baseline,candidate,hypothesis,change in CONTRASTS:
        result=compare(phase,baseline,candidate);print(json.dumps(result),flush=True)
        record(phase,baseline,candidate,hypothesis,change,
               'development_gate_passed_requires_new_validation' if result['gate_passed'] else 'not_promoted_development_gate_failed')
    behavior_check('R2_ES_dev30',phase,'s22','outer13')
    check(phase)
