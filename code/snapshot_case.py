"""Launch a case from a named immutable snapshot, preserving that exact source."""
import argparse,json,multiprocessing,sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--config',required=True)
    p.add_argument('--run-root',required=True);p.add_argument('--seed',required=True,type=int)
    p.add_argument('--scene',type=json.loads,default={});p.add_argument('--output',required=True)
    a=p.parse_args();sys.path.insert(0,str(Path(a.snapshot)/'code'))
    # The oldest immutable H0 wrapper predates command-line scrubbing. Keep
    # its algorithm bytes intact, but isolate ALL snapshots with the same
    # audited modern process wrapper and remove evaluator arguments early.
    sys.argv=['q4-frozen-runner']
    import run_case
    from frozen_policy_worker import policy_main
    run_case.policy_main=policy_main
    directory,m=run_case.run_case(a.seed,a.config,a.scene,output_root=a.run_root,replay_check=True)
    result=dict(run_id=directory.name,directory=str(directory),metrics=m)
    Path(a.output).write_text(json.dumps(result),encoding='utf-8')
    return 0 if m['all_success'] else 1


if __name__=='__main__':
    multiprocessing.freeze_support();raise SystemExit(main())
