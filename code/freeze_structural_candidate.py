"""Freeze a selected TRAINING candidate before touching reserved validation."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import pprint
import sys

ROOT=Path(__file__).resolve().parents[1]/'local_simulator';DEST=ROOT/'reports'/'optimization'


def main():
    if len(sys.argv)!=2:raise SystemExit('Specify a variant from F_round3 training')
    name=sys.argv[1]
    config=json.loads((DEST/'F_round3_config.json').read_text())
    selected=next(v for v in config['variants'] if v['name']==name)
    if selected['strategy']!='F':raise ValueError('Candidate must be F')
    if (DEST/'F_FREEZE.json').exists():raise FileExistsError('F already frozen')
    parameters=selected['policy_options']
    version='structural-F-'+name+'-20260912'
    content='"""F frozen before the independent 8001-8100 validation."""\n\n'
    content+='FROZEN_F_VERSION = '+repr(version)+'\nFROZEN_F_OPTIONS = '+pprint.pformat(parameters,sort_dicts=True)+'\n'
    (ROOT/'code'/'f_policy_presets.py').write_text(content,encoding='utf-8')
    files=['controller.py','geometry.py','optimized.py','local_geometry.py','replanning.py',
           'reception_geometry.py','structural.py','structural_geometry.py','e_policy_presets.py',
           'f_policy_presets.py','coverage.py','q3client.py','engine.py']
    freeze=dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),selection_phase='F_round3',
                selection_variant=name,policy_options=parameters,version=version,
                validation_seeds=list(range(8001,8101)),policy_file_sha256={
                    file:hashlib.sha256((ROOT/'code'/file).read_bytes()).hexdigest() for file in files},
                no_validation_cases_seen_before_freeze=True)
    (DEST/'F_FREEZE.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    variants=[dict(name='frozen_E',strategy='E'),dict(name='frozen_F',strategy='F')]
    validation=dict(cases=[dict(seed=s,scenario='uniform',reception='mixed',error_mode='fixed_hash') for s in range(8001,8101)],
                    variants=variants,workers=4)
    stress=[]
    for i,(scenario,reception,error,count) in enumerate([
        ('boundary','minimum','plus_one',16),('boundary','minimum','minus_one',16),
        ('clustered','minimum','smooth',16),('uniform','minimum','smooth',16),
        ('boundary','maximum','fixed_hash',10),('uniform','minimum','fixed_hash',10),
        ('clustered','mixed','plus_one',10),('boundary','mixed','smooth',16)]):
        stress.append(dict(seed=8201+i,scenario=scenario,reception=reception,error_mode=error,count=count))
    for name,setup in [('F_validation100',validation),('F_stress',dict(cases=stress,variants=variants,workers=4))]:
        (DEST/(name+'_config.json')).write_text(json.dumps(setup,indent=2),encoding='utf-8')
    print(json.dumps(freeze,indent=2))


if __name__=='__main__':main()
