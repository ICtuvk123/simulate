"""Convenient entry point. Local simulator only; no network transport."""
import argparse,json,multiprocessing,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))


def main():
    from run_case import run_case
    from replay_html import create_replay
    p=argparse.ArgumentParser(description='Q4 local simulator and feedback-only controller')
    p.add_argument('--seed',type=int,default=1,help='Local engine seed, never given to the controller')
    p.add_argument('--sources',type=int,choices=range(10,17))
    p.add_argument('--source-mix',choices=['mixed','omni','directional'],default='mixed')
    p.add_argument('--scenario',choices=['uniform','boundary','clustered'],default='uniform')
    p.add_argument('--config',help='Default: frozen incumbent configuration')
    p.add_argument('--replay-check',action='store_true',help='Reproduce actions using only recorded responses')
    a=p.parse_args()
    config=a.config or json.loads((ROOT/'INCUMBENT.json').read_text(encoding='utf-8'))['configuration']
    directory,m=run_case(a.seed,config,dict(count=a.sources,source_mix=a.source_mix,scenario=a.scenario),replay_check=a.replay_check)
    replay=create_replay(directory)
    print(json.dumps(dict(complete=m['all_success'],cleared=m['clear_count'],total_virtual_s=m['total_time'],
                         mean_per_source_s=m['mean_time_per_source'],real_runtime_s=m['policy_wall_time_s'],
                         error=m['client_error'],directory=str(directory),replay=str(replay)),ensure_ascii=False,indent=2))
    return 0 if m['all_success'] else 1


if __name__=='__main__':
    multiprocessing.freeze_support();raise SystemExit(main())
