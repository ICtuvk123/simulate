"""Regression on the registered pressure layouts; no fresh-distribution claim."""
import json
from pathlib import Path
from frozen_experiment import execute
from compare_phase import compare
from independent_phase import check
from record_experiment import record
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    variants={
        's22':dict(snapshot='frozen/R2_S22',config='frozen/R2_S22/configs/R2_S_outer13.json',freeze='configs/R2_S22_FREEZE.json'),
        's22_ml':dict(snapshot='frozen/R2_S22_ML',config='frozen/R2_S22_ML/configs/R2_S22_ML.json',freeze='configs/R2_S22_ML_FREEZE.json')}
    phase='R2_S22_ML_pressure22'
    scenes=json.loads((ROOT/'configs/R2_PRESSURE_SCENES.json').read_text())
    execute(phase,variants,list(range(530001,530023)),'pressure',scenes)
    compare(phase,'s22','s22_ml');result=check(phase)
    record(phase,'s22','s22_ml','Frozen ML policy remains correct on registered directional edge cases',
           'Exact frozen policy execution on existing pressure layouts; no parameter changes',
           'pressure_regression_pass' if result['all_valid'] else 'pressure_regression_failed')
    raise SystemExit(0 if result['all_valid'] else 1)
