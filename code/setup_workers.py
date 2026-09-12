"""Prepare isolated Git worktrees for reproducing the paired experiments."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def git(directory,*args):
    return subprocess.check_output(['git','-c','safe.directory='+directory.as_posix(),'-C',str(directory),*args],text=True).strip()


def setup(count=4):
    if not (ROOT/'.git').exists():
        git(ROOT,'init','-b','codex/q4-reproduction')
        files=[n for n in ('code','configs','tests','q4.py','official_practice.py','.gitattributes','.gitignore') if (ROOT/n).exists()]
        git(ROOT,'add','--',*files)
        git(ROOT,'-c','user.name=Q4 local reproduction','-c','user.email=q4-local@localhost','commit','-m','Import exported Q4 source for isolated reproduction')
    if git(ROOT,'status','--porcelain','--','code','configs'):
        raise RuntimeError('Commit source/config changes before creating exact experiment worktrees')
    revision=git(ROOT,'rev-parse','HEAD');parent=ROOT.parent/(ROOT.name+'_workers');parent.mkdir(exist_ok=True)
    result=[]
    for i in range(count):
        worker=parent/f'w{i}'
        if not worker.resolve().is_relative_to(parent.resolve()):raise RuntimeError('Unexpected worker target')
        if not worker.exists():git(ROOT,'worktree','add','--detach',str(worker),revision)
        else:
            common=Path(git(worker,'rev-parse','--git-common-dir'))
            if not common.is_absolute():common=worker/common
            if common.resolve()!=(ROOT/'.git').resolve():raise RuntimeError('Existing directory belongs to another repository')
            if git(worker,'status','--porcelain'):raise RuntimeError('Worker contains changes: '+str(worker))
            git(worker,'checkout','--detach',revision)
        git(worker,'checkout-index','--force','--all')
        result.append(dict(worker=i,path=str(worker),commit=revision))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4,choices=range(1,9));a=p.parse_args()
    print(json.dumps(setup(a.workers),indent=2))
