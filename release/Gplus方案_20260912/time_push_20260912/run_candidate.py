"""Run the frozen local candidate or the preserved G baseline."""
import argparse
import json
import multiprocessing
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))


def main():
    from runner import run_case
    import runner
    from time_policy import TimePolicy
    from g_policy_presets import FROZEN_G_OPTIONS
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=13001)
    p.add_argument('--baseline',action='store_true')
    p.add_argument('--scenario',choices=('uniform','boundary','clustered'),default='uniform')
    p.add_argument('--reception',choices=('mixed','minimum','maximum'),default='mixed')
    p.add_argument('--error-mode',choices=('fixed_hash','smooth','plus_one','minus_one'),default='fixed_hash')
    a=p.parse_args()
    variant={'name':'G'} if a.baseline else json.loads((ROOT/'candidate.json').read_text(encoding='utf-8'))
    options=dict(FROZEN_G_OPTIONS,**variant.get('options',{}));extra=variant.get('extra',{})
    if extra:
        runner.RouteSearchController=lambda client,**kw:TimePolicy(client,**kw,**extra)
    directory,payload=run_case(seed=a.seed,strategy='G',scenario=a.scenario,
        reception=a.reception,error_mode=a.error_mode,policy_options=options,
        compute_oracle=False,update_latest=False)
    (directory/'experiment_variant.json').write_text(json.dumps(variant,indent=2),encoding='utf-8')
    metrics=payload['metrics']
    template=ROOT.parent/'local_simulator/web/index.html'
    replay=dict(payload)
    replay['metadata']=dict(payload['metadata'],strategy_version='local-'+variant['name'],experimental_variant=variant)
    html=template.read_text(encoding='utf-8').replace('const EMBEDDED = null;',
        'const EMBEDDED = '+json.dumps(replay,ensure_ascii=False).replace('<','\\u003c')+';',1)
    (directory/'replay.html').write_text(html,encoding='utf-8')
    print(json.dumps(dict(variant=variant['name'],total_time=metrics['total_time'],
        seconds_per_source=metrics['average_localization_clear_time_s_per_source'],
        cleared=metrics['clear_count'],count=metrics['jammer_count'],
        completion_proved=metrics['completion_proved'],directory=str(directory)),indent=2))
    return int(bool(metrics['client_error']) or metrics['clear_ratio']!=1 or not metrics['completion_proved'])


if __name__=='__main__':
    multiprocessing.freeze_support();raise SystemExit(main())
