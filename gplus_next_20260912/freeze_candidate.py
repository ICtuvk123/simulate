"""Freeze one development-selected candidate before opening validation scenes."""
import argparse
from datetime import datetime,timezone
import hashlib
import inspect
import itertools
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))


def main():
    p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args()
    manifest=json.loads((ROOT/'reports/development40/manifest.json').read_text())
    chosen=next(v for v in manifest['variants'] if v['name']==a.name)
    candidate=dict(chosen)
    # Store constructor defaults explicitly, including inherited G+ extras.
    from policy_factory import policy_class
    cls=policy_class(chosen['kind']);defaults={}
    extras_mro=[]
    for ancestor in cls.__mro__:
        extras_mro.append(ancestor)
        if ancestor.__name__=='TimePolicy':break
    for ancestor in reversed(extras_mro):
        init=ancestor.__dict__.get('__init__')
        if init:
            for name,param in inspect.signature(init).parameters.items():
                if param.default is not inspect.Parameter.empty and name not in ('client','options'):
                    defaults[name]=param.default
    original=json.loads((ROOT/'BASELINE_candidate.json').read_text())
    from g_policy_presets import FROZEN_G_OPTIONS
    base_options={**FROZEN_G_OPTIONS,**original['options'],**chosen.get('options',{})}
    selected_extra={k:v for k,v in defaults.items() if k not in base_options}
    selected_extra.update(original['extra']);selected_extra.update(chosen.get('extra',{}))
    # Preserve the exact tested variant dictionary for reproducible run selection.
    frozen=dict(version='q3-GplusNext-20260912-'+a.name,selected_from='development40',
        selected_at_utc=datetime.now(timezone.utc).isoformat(),candidate=candidate,
        effective_policy_options=base_options,effective_extra_options=selected_extra,
        code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'code').glob('*.py'))},
        development_seeds=[list(range(21001,21017)),list(range(21101,21141))],
        validation_seeds=list(range(22001,22101)),stress_seeds=list(range(23001,23025)),
        acceptance='all complete and audited; paired mean T/n and mean T improve; bootstrap CI lower bound >0; stress all complete',
        official_connection_made=False)
    baseline_freeze=json.loads((ROOT/'BASELINE_FREEZE.json').read_text())
    assert all(hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()==digest
               for name,digest in baseline_freeze['experiment_files_sha256'].items())
    variants=[dict(name='Gplus',kind='Gplus'),candidate]
    stress=[dict(seed=23001+i,scenario=s,reception=r,error_mode=e,count=10 if i%2==0 else 16)
            for i,(s,r,e) in enumerate(itertools.product(('uniform','boundary','clustered'),
                                  ('minimum','maximum'),('fixed_hash','smooth','plus_one','minus_one')))]
    values={'candidate.json':candidate,'FREEZE_NEXT.json':frozen,
            'validation100.json':dict(phase='validation100',workers=6,variants=variants,
                                      cases=[dict(seed=s) for s in range(22001,22101)]),
            'stress24.json':dict(phase='stress24',workers=6,variants=variants,cases=stress)}
    for name,value in values.items():
        with (ROOT/name).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)
    print(json.dumps(dict(frozen=frozen['version'],candidate=candidate),indent=2))


if __name__=='__main__':main()
