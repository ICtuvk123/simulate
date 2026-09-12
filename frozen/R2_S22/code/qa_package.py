"""Verify a ZIP's manifests; optionally test an extracted runtime package."""
import argparse,hashlib,json,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def digest_stream(stream):
    h=hashlib.sha256()
    while True:
        data=stream.read(1024*1024)
        if not data:return h.hexdigest()
        h.update(data)


def check(archive,extract=None,smoke_seed=15):
    started=time.monotonic();archive=Path(archive).resolve();prefix='jammer_search_q4/'
    result={'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP paths')
        for name in names:
            if not name.startswith(prefix) or '..' in Path(name).parts or '\\' in name:
                raise ValueError('Unsafe ZIP path '+name)
        if prefix+'PACKAGE_MANIFEST.json' in names:
            manifest=json.loads(z.read(prefix+'PACKAGE_MANIFEST.json'));files=manifest['files']
            result['kind']='runtime';result['incumbent']=manifest['incumbent']
            expected={prefix+n for n in files}|{prefix+'PACKAGE_MANIFEST.json'}
            if set(names)!=expected:raise ValueError('Runtime archive has unlisted files')
        else:
            manifest=json.loads(z.read(prefix+'EVIDENCE_MANIFEST.json'));files=dict(manifest['files'])
            files.update({'source_objects/'+d:d for d in manifest['source_objects']})
            result.update(kind='evidence',runs=len(manifest['runs']),source_objects=len(manifest['source_objects']))
            expected={prefix+n for n in files}|{prefix+'EVIDENCE_MANIFEST.json'}
            if set(names)!=expected:raise ValueError('Evidence archive has unlisted files')
        for name,digest in files.items():
            with z.open(prefix+name) as stream:
                if digest_stream(stream)!=digest:raise ValueError('ZIP hash mismatch '+name)
        result['verified_files']=len(files)
        if extract:
            destination=Path(extract).resolve()
            if destination.exists():raise FileExistsError(destination)
            destination.mkdir(parents=True)
            for name in names:
                if not (destination/name).resolve().is_relative_to(destination):raise ValueError(name)
            z.extractall(destination)
    if extract:
        package=destination/'jammer_search_q4';outputs={}
        commands={
            'freeze':[sys.executable,'code/verify_freeze.py'],
            'unit_tests':[sys.executable,'-m','unittest','discover','-s','tests'],
            'smoke':[sys.executable,'q4.py','--sources','14','--seed',str(smoke_seed),'--replay-check'],
        }
        for label,command in commands.items():
            proc=subprocess.run(command,cwd=package,capture_output=True,text=True,encoding='utf-8',
                                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            outputs[label]={'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}
            if proc.returncode:raise RuntimeError(label+': '+proc.stdout+proc.stderr)
        run=json.loads(outputs['smoke']['stdout']);folder=Path(run['directory'])
        result.update(extracted=str(package),checks=outputs,smoke=run,
                      feedback_replay=json.loads((folder/'feedback_replay.json').read_text()))
    result.update(valid=True,elapsed_s=time.monotonic()-started)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--extract');p.add_argument('--smoke-seed',type=int,default=15);p.add_argument('--output',required=True)
    a=p.parse_args();r=check(a.archive,a.extract,a.smoke_seed)
    Path(a.output).write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','incumbent')},indent=2))
