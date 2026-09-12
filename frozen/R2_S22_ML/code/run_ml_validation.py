"""Fresh pre-registered 100-scene validation of S22ML against S22."""
import csv,json
from pathlib import Path
from freeze_candidate import freeze
from experiment import run_phase
from compare_phase import compare
from independent_phase import check
from record_experiment import record
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    seeds=list(range(510101,510201))
    with (ROOT/'SEEDS.csv').open(encoding='utf-8-sig',newline='') as f:
        consumed={int(row['seed']) for row in csv.DictReader(f) if row.get('seed','').isdigit()}
    if consumed.intersection(seeds):raise RuntimeError('Fresh validation seeds already consumed')
    freeze('R2_S22_ML','R2_S22_ML.json',510101,100)
    phase='R2_S22_ML_val100'
    run_phase(phase,{'s22':'R2_S_outer13.json','s22_ml':'R2_S22_ML.json'},seeds,role='validation',replay=True)
    result=compare(phase,'s22','s22_ml');print(json.dumps(result),flush=True)
    independent=check(phase)
    record(phase,'s22','s22_ml','ML action model reduces complete-scene cost on fresh scenes',
           'Enable one-RF adaptive probing and stable quadrature on validated S22',
           'eligible_for_promotion_after_review' if result['gate_passed'] and independent['all_valid'] else 'not_promoted_validation_gate_failed')
