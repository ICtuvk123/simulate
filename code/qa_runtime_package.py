"""Verify, freshly extract and exercise a portable runtime ZIP offline."""
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path


def check(archive,destination):
    archive=Path(archive).resolve();destination=Path(destination).resolve()
    if destination.exists():raise ValueError('QA output must be a fresh directory')
    destination.mkdir(parents=True);root=destination/'jammer_search_q4'
    with zipfile.ZipFile(archive) as package:
        names=package.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP members')
        manifest=json.loads(package.read('jammer_search_q4/PACKAGE_MANIFEST.json'))
        for name,digest in manifest['files'].items():
            if hashlib.sha256(package.read('jammer_search_q4/'+name)).hexdigest()!=digest:
                raise ValueError('Package hash mismatch: '+name)
        for name in names:
            if not (destination/name).resolve().is_relative_to(destination):raise ValueError('ZIP path leaves output root')
        package.extractall(destination)
    steps=[]
    def run(name,args):
        result=subprocess.run([sys.executable,*args],cwd=root,capture_output=True,text=True,timeout=180,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (destination/(name+'.txt')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        item=dict(step=name,exit_code=result.returncode);steps.append(item)
        if result.returncode:raise RuntimeError('Extracted runtime QA failed: '+name)
    run('freeze',['code/verify_freeze.py'])
    run('regression',['-m','unittest','discover','-s','tests','-q'])
    run('local_14_source_smoke',['q4.py','--sources','14','--seed','1','--replay-check'])
    runs=list((root/'runs').iterdir())
    if len(runs)!=1:raise ValueError('Expected exactly one fresh smoke run')
    journal=runs[0]/'requests.jsonl';run('independent_exit',['code/independent_exit.py',str(journal)])
    metrics=json.loads((runs[0]/'metrics.json').read_text())
    replay=json.loads((runs[0]/'feedback_replay.json').read_text())
    result=dict(valid=metrics['all_success'] and replay['valid'],archive=str(archive),
                archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                checked_files=len(manifest['files']),version=manifest['incumbent']['version'],steps=steps,
                smoke=dict(seed=1,sources=14,new_independent_scenes=0,run_id=runs[0].name,
                           total_time_s=metrics['total_time'],complete=metrics['all_success'],replay_valid=replay['valid']),
                official_interfaces_called=False)
    (destination/'QA.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive');parser.add_argument('destination');args=parser.parse_args()
    result=check(args.archive,args.destination);print(json.dumps(result,indent=2));raise SystemExit(0 if result['valid'] else 1)
