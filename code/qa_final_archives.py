"""Final archive integrity and extracted regression checks; no new simulation."""
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path

def digest(data):return hashlib.sha256(data).hexdigest()

def check(receipt_path,destination):
    receipt=json.loads(Path(receipt_path).read_text());destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Use a new QA directory')
    destination.mkdir(parents=True);answers=[];runtime_root=None
    for entry in receipt['archives']:
        archive=Path(entry['path'])
        if digest(archive.read_bytes())!=entry['sha256']:raise ValueError('ZIP digest differs')
        with zipfile.ZipFile(archive) as package:
            names=package.namelist()
            if len(names)!=len(set(names)):raise ValueError('Duplicate archive path')
            for name in names:
                if not (destination/name).resolve().is_relative_to(destination):raise ValueError('Unsafe archive path')
            prefix='jammer_search_q4/'
            runtime=prefix+'PACKAGE_MANIFEST.json' in names
            manifest=json.loads(package.read(prefix+('PACKAGE_MANIFEST.json' if runtime else 'EVIDENCE_MANIFEST.json')))
            for name,expected in manifest['files'].items():
                if digest(package.read(prefix+name))!=expected:raise ValueError('Entry differs: '+name)
            if runtime:
                package.extractall(destination);runtime_root=destination/'jammer_search_q4'
            else:
                for expected in manifest['source_objects']:
                    if digest(package.read(prefix+'source_objects/'+expected))!=expected:raise ValueError('Source object differs')
                for run_id in manifest['runs']:
                    run=json.loads(package.read(prefix+'runs/'+run_id+'/manifest.json'))
                    if any(value not in manifest['source_objects'] for value in run['source_hashes'].values()):
                        raise ValueError('Archived run has missing source objects')
            answers.append(dict(path=str(archive),sha256=entry['sha256'],files=len(manifest['files']),
                                raw_runs=len(manifest.get('runs',[])),valid=True))
    if runtime_root is None:raise ValueError('Runtime ZIP missing')
    steps=[]
    for name,args in [('freeze',['code/verify_freeze.py']),('regression',['-m','unittest','discover','-s','tests','-q'])]:
        result=subprocess.run([sys.executable,*args],cwd=runtime_root,capture_output=True,text=True,timeout=180,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (destination/(name+'.txt')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        steps.append(dict(name=name,returncode=result.returncode))
        if result.returncode:raise RuntimeError('Extracted check failed: '+name)
    result=dict(valid=True,archives=answers,extracted_checks=steps,new_simulations=0,
                final_holdout_status='interrupted_not_accepted',
                prior_14_source_smoke='reports/R2_PACKAGE_PREFLIGHT_QA.json',
                note='Final extraction verifies the frozen policy and regression suite. The already completed preflight provides the local 14-source smoke; no new simulation is run after the budget stop.')
    (destination/'QA.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('receipt');p.add_argument('destination');a=p.parse_args()
    print(json.dumps(check(a.receipt,a.destination),indent=2))
