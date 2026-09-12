"""S22 and single-factor combinations, frozen as one full-scene development batch."""
import json
from pathlib import Path
from experiment import run_phase
ROOT=Path(__file__).resolve().parents[1]

VARIANTS={
    's22':'R2_S_outer13.json',
    's22_ml':'R2_S22_ML.json',
    's22_o':'R2_S22_O.json',
    's22_mlo':'R2_S22_MLO.json',
    's22_mln':'R2_S22_MLN.json',
    's21':'R2_S21_screen.json',
    's21_ml':'R2_S21_ML.json',
}

def prepare():
    base=json.loads((ROOT/'configs/R2_S_outer13.json').read_text())
    deltas={
        's22_ml':dict(adaptive_single=True,adaptive_single_gain_s=1.,stable_quadrature=True),
        's22_o':dict(scan_before_commit=True),
        's22_mlo':dict(adaptive_single=True,adaptive_single_gain_s=1.,stable_quadrature=True,scan_before_commit=True),
        's22_mln':dict(adaptive_single=True,adaptive_single_gain_s=1.,stable_quadrature=True,canonical_single_candidates=True),
        's21':dict(inner_radius=999.,outer_count=12,outer_radius=1869.),
        's21_ml':dict(inner_radius=999.,outer_count=12,outer_radius=1869.,adaptive_single=True,adaptive_single_gain_s=1.,stable_quadrature=True),
    }
    for name,changes in deltas.items():
        options={**base,**changes,'version':'R2-'+name}
        (ROOT/'configs'/VARIANTS[name]).write_text(json.dumps(options,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    import sys
    if '--prepare' in sys.argv:prepare()
    else:run_phase('R2_SML_dev30',VARIANTS,list(range(500001,500031)),role='development',replay=True)
