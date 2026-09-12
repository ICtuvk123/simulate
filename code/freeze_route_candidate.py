"""Freeze a training-selected G policy before opening new validation cases."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'local_simulator';DEST=ROOT/'reports/optimization'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('variant');args=parser.parse_args()
    if (DEST/'G_FREEZE.json').exists():raise FileExistsError('G already frozen')
    config=json.loads((DEST/'G_round4_config.json').read_text())
    selected=next(v for v in config['variants'] if v['name']==args.variant)
    options=selected['policy_options'];version='route-G-'+args.variant+'-20260912'
    preset='"""Frozen local G candidate; historical F remains available."""\n'
    preset+='FROZEN_G_VERSION = '+repr(version)+'\nFROZEN_G_OPTIONS = '+repr(options)+'\n'
    (ROOT/'code/g_policy_presets.py').write_text(preset,encoding='utf-8')
    p=ROOT/'code/runner.py';s=p.read_text(encoding='utf-8')
    s=s.replace('from f_policy_presets import FROZEN_F_OPTIONS, FROZEN_F_VERSION',
                'from f_policy_presets import FROZEN_F_OPTIONS, FROZEN_F_VERSION\nfrom g_policy_presets import FROZEN_G_OPTIONS, FROZEN_G_VERSION')
    s=s.replace("if strategy in ('F','G') and policy_options is None:","if strategy == 'F' and policy_options is None:")
    s=s.replace('    policy_options = dict(policy_options or {})',"    if strategy == 'G' and policy_options is None:\n        policy_options = dict(FROZEN_G_OPTIONS)\n    policy_options = dict(policy_options or {})")
    s=s.replace("'local-G-route-search-candidates-20260912' if strategy=='G' else","'local-G-'+FROZEN_G_VERSION if strategy=='G' else")
    p.write_text(s,encoding='utf-8')
    previous=json.loads((DEST/'F_FREEZE.json').read_text())
    hashes=dict(previous['policy_file_sha256'])
    for name,expected in hashes.items():
        assert hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()==expected,('F changed',name)
    for name in ('route_search.py','g_policy_presets.py'):
        hashes[name]=hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()
    freeze=dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),selection_phase='G_round4',
        selection_variant=args.variant,version=version,policy_options=options,policy_file_sha256=hashes,
        training_phases=['G_round1','G_round2','G_round3','G_round4'],
        validation_seeds=list(range(10001,10101)),no_validation_cases_seen_before_freeze=True)
    (DEST/'G_FREEZE.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    variants=[dict(name='frozen_F',strategy='F'),dict(name='frozen_G',strategy='G',policy_options=options)]
    validation=dict(cases=[dict(seed=s,scenario='uniform',reception='mixed',error_mode='fixed_hash') for s in range(10001,10101)],variants=variants,workers=4)
    (DEST/'G_validation100_config.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
    pressure=json.loads((DEST/'F_stress_config.json').read_text())
    for c in pressure['cases']:c['seed']+=2000
    pressure['variants']=variants
    (DEST/'G_stress_config.json').write_text(json.dumps(pressure,indent=2),encoding='utf-8')
    print(json.dumps(dict(version=version,frozen_files=len(hashes),validation_pairs=100,stress_pairs=8),indent=2))


if __name__=='__main__':main()
