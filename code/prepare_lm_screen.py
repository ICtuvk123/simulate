"""Register the L/M factorial development screen without changing the incumbent."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def prepare():
    config=json.loads((ROOT/'configs/R2_M_adaptive_single.json').read_text())
    config.update(version='R2-ML-adaptive-single-stable-quadrature',stable_quadrature=True)
    (ROOT/'configs/R2_ML_single_stable.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    plan=json.loads((ROOT/'configs/R2_EXPERIMENT_PLAN.json').read_text())
    plan['smoke_seed_ranges']['integration_extension_LF']=[1400,1400]
    plan['smoke_seed_ranges']['global_scheduler']=[1411,1420]
    plan['smoke_seed_ranges']['single_risk_and_commitment']=[1421,1430]
    plan['hypotheses']['L']='Representation-invariant equal-area quadrature changes only candidate scoring.'
    plan['hypotheses']['M']='A single informative RF action with full original-pair recovery cost can avoid unnecessary paired RF travel.'
    (ROOT/'configs/R2_EXPERIMENT_PLAN.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':prepare()
