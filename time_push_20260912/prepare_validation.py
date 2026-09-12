"""Freeze the candidate and register untouched validation and stress scenes."""
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
candidate={'name':'Gplus','options':{'commit_radius':0,'near_prediction':10,'bearing_factor':0.15},
           'extra':{'error_risk':0.5}}
for name in ('candidate.json','FREEZE.json','validation100.json','stress24.json'):
    if (ROOT/name).exists():
        raise FileExistsError(name)
original=ROOT.parent/'local_simulator'
prior=json.loads((original/'reports/optimization/G_FREEZE.json').read_text())
assert all(hashlib.sha256((original/'code'/n).read_bytes()).hexdigest()==h for n,h in prior['policy_file_sha256'].items())
assert (ROOT/'code/engine.py').read_bytes()==(original/'code/engine.py').read_bytes()
freeze=dict(version='q3-Gplus-20260912-v1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),
    selected_from='development40',selection_variant='combined',candidate=candidate,
    primary_metric='mean over scenes of total_time / cleared_source_count; require all sources cleared',
    validation_acceptance='all cases complete; paired mean T/n improves with bootstrap CI lower bound > 0; mean T improves; stress all complete; report regressions',
    baseline_files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((original/'code').glob('*.py'))},
    experiment_files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'code').glob('*.py'))},
    tested_seeds_before_freeze=[list(range(12001,12017)),list(range(12101,12141))],
    physical_rules_changed=False,official_tests_run=False)
(ROOT/'candidate.json').write_text(json.dumps(candidate,indent=2),encoding='utf-8')
(ROOT/'FREEZE.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
variants=[{'name':'G'},candidate]
validation=dict(phase='validation100',workers=8,cases=[{'seed':s} for s in range(13001,13101)],variants=variants)
stress=[]
for i,(scenario,reception,error) in enumerate(itertools.product(
    ('uniform','boundary','clustered'),('minimum','maximum'),('fixed_hash','smooth','plus_one','minus_one'))):
    stress.append(dict(seed=14001+i,scenario=scenario,reception=reception,error_mode=error,count=10 if i%2==0 else 16))
(ROOT/'validation100.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
(ROOT/'stress24.json').write_text(json.dumps(dict(phase='stress24',workers=8,cases=stress,variants=variants),indent=2),encoding='utf-8')
print('Frozen Gplus; registered 100 independent pairs and 24 stress pairs.')
