"""Run the selected local candidate or frozen G+ and create an HTML replay."""
import argparse
import json
import multiprocessing
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    from batch import execute
    p=argparse.ArgumentParser();p.add_argument('--baseline',action='store_true')
    p.add_argument('--seed',type=int,default=22001)
    p.add_argument('--scenario',choices=('uniform','boundary','clustered'),default='uniform')
    p.add_argument('--reception',choices=('mixed','minimum','maximum'),default='mixed')
    p.add_argument('--error-mode',choices=('fixed_hash','smooth','plus_one','minus_one'),default='fixed_hash')
    a=p.parse_args()
    variant={'name':'Gplus','kind':'Gplus'} if a.baseline else json.loads((ROOT/'candidate.json').read_text(encoding='utf-8'))
    row=execute((variant,dict(seed=a.seed,scenario=a.scenario,reception=a.reception,error_mode=a.error_mode)))
    directory=ROOT/'runs'/row['run_id']
    payload=json.loads((directory/'result.json').read_text(encoding='utf-8'))
    payload['metadata']['strategy_version']=variant['name']
    payload['metadata']['experimental_variant']=variant
    template=(ROOT.parent/'local_simulator/web/index.html').read_text(encoding='utf-8')
    (directory/'replay.html').write_text(template.replace('const EMBEDDED = null;',
        'const EMBEDDED = '+json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')+';',1),encoding='utf-8')
    print(json.dumps(dict(variant=variant['name'],cleared=row['clear_count'],count=row['jammer_count'],
        total_time=row['total_time'],seconds_per_source=row['average_localization_clear_time_s_per_source'],
        completion_proved=row['completion_proved'],audit_errors=row['audit_errors'],directory=str(directory)),indent=2))
    return int(bool(row['client_error']) or not row['audit_pass'] or row['clear_ratio']!=1 or not row['completion_proved'])


if __name__=='__main__':
    multiprocessing.freeze_support();raise SystemExit(main())
