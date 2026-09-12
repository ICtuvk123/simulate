"""Copy completed worker evidence without rewriting or overwriting any record.

This does not run a scene or alter the active strategy. Original run source
snapshots are checked against their recorded SHA256 before being collected.
"""
import argparse,csv,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_verified(source,destination,source_root,destination_root):
    if not source.resolve().is_relative_to(source_root.resolve()):raise ValueError('Source escaped worker')
    if not destination.resolve().is_relative_to(destination_root.resolve()):raise ValueError('Target escaped evidence root')
    if source.is_symlink():raise ValueError('Symlink not accepted')
    if destination.exists():
        if digest(source)!=digest(destination):raise ValueError('Existing evidence differs: '+str(destination))
    else:
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    return digest(source)


def collect(worker,phases):
    worker=Path(worker).resolve();allowed=ROOT.parent/(ROOT.name+'_workers')
    if not worker.is_relative_to(allowed.resolve()):raise ValueError('Not an independent round-two worker')
    output=[]
    for phase in phases:
        if Path(phase).name!=phase or not phase.startswith('R2_'):raise ValueError('Unexpected phase name')
        folder=worker/'reports'/phase
        if not (folder/'summary.json').is_file():raise ValueError('Phase has no completed summary')
        rows=[json.loads(line) for line in (folder/'runs.jsonl').read_text(encoding='utf-8').splitlines()]
        if not rows:raise ValueError('No run records')
        hashes={};seen=set()
        for row in rows:
            run_id=row.get('run_id')
            if not run_id:continue # Preserve an explicit failed row, never delete it.
            if Path(run_id).name!=run_id:raise ValueError('Invalid run ID')
            origin=worker/'runs'/run_id
            manifest=json.loads((origin/'manifest.json').read_text(encoding='utf-8'))
            for name,expected in manifest['source_hashes'].items():
                code=origin/'source'/name
                if not code.resolve().is_relative_to((origin/'source').resolve()) or digest(code)!=expected:
                    raise ValueError('Executed code hash mismatch')
            for source in sorted(origin.rglob('*')):
                if source.is_file() and '__pycache__' not in source.parts and source.suffix!='.pyc':
                    target=ROOT/'runs'/run_id/source.relative_to(origin)
                    hashes[target.relative_to(ROOT).as_posix()]=copy_verified(source,target,worker,ROOT/'runs')
            seen.add(run_id)
        target_folder=ROOT/'reports'/phase
        for source in sorted(folder.rglob('*')):
            if source.is_file():
                target=target_folder/source.relative_to(folder)
                hashes[target.relative_to(ROOT).as_posix()]=copy_verified(source,target,worker,ROOT/'reports')
        report=dict(phase=phase,source_worker=str(worker),collected_utc=datetime.now(timezone.utc).isoformat(),
                    runs=len(seen),all_rows_retained=len(rows),files=hashes,new_scenes_executed=0,
                    note='Read original registration for experiment purpose; repeated seeds are not independent validation.')
        provenance=target_folder/'IMPORT_PROVENANCE.json'
        if provenance.exists():
            if json.loads(provenance.read_text())['files']!=hashes:raise ValueError('Imported phase has changed')
        else:
            provenance.write_text(json.dumps(report,indent=2),encoding='utf-8')
            with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as stream:
                writer=csv.writer(stream)
                for row in rows:writer.writerow([phase,'worker_development_import',row['task']['seed'],row['task']['variant'],
                                                 row.get('run_id'),'imported_original_evidence'])
        output.append(dict(phase=phase,runs=len(seen),files=len(hashes)))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('worker');parser.add_argument('phases',nargs='+')
    args=parser.parse_args();print(json.dumps(collect(args.worker,args.phases),indent=2))
