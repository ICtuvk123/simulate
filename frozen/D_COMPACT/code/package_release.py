"""Create a portable runtime ZIP and a deduplicated local-evidence ZIP.

Only explicitly included Q4 paths are packaged. Official logs, Q3 reference
directories, temporary files, live worktrees and account data are excluded.
Original experiment journals remain byte-for-byte unchanged in the evidence.
"""
import argparse,hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def sha(data):return hashlib.sha256(data).hexdigest()


def safe_files(folder):
    for p in sorted(folder.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.log'):
            if not p.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Path leaves Q4 root')
            yield p


def build(tag,output,with_evidence=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    prefix='jammer_search_q4';runtime=output/f'Q4_{tag}_runtime.zip';evidence=output/f'Q4_{tag}_evidence.zip'
    files=[]
    for folder in ('code','configs','frozen','tests','inputs','figures','reports','examples'):
        if (ROOT/folder).exists():files.extend(safe_files(ROOT/folder))
    for name in ('README.md','OFFICIAL_PRACTICE.md','q4.py','official_practice.py','GOAL.md','NEXT.md','FAILURES.md',
                 'EXPERIMENTS.csv','INCUMBENT.json','SEEDS.csv','.gitignore','.gitattributes'):
        files.append(ROOT/name)
    # Full worker rows and repeated case files are available in evidence runs;
    # keep the portable runtime's report summaries, comparisons and paired CSVs.
    files=[p for p in files if not (p.is_relative_to(ROOT/'reports') and
           (p.name.startswith(('worker','case_','job')) or p.name=='runs.jsonl'))]
    index={}
    with zipfile.ZipFile(runtime,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(set(files)):
            name=p.relative_to(ROOT).as_posix();data=p.read_bytes();index[name]=sha(data)
            z.writestr(prefix+'/'+name,data)
        manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),files=index,
                      incumbent=json.loads((ROOT/'INCUMBENT.json').read_text()),official_tests_executed=0)
        z.writestr(prefix+'/PACKAGE_MANIFEST.json',json.dumps(manifest,indent=2))
    archives=[runtime];evidence_manifest=None
    if with_evidence:
        seen=set();runs=[];objects={};runfiles={}
        with zipfile.ZipFile(evidence,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for folder in sorted((ROOT/'runs').iterdir()):
                if not folder.is_dir() or not (folder/'manifest.json').is_file():continue
                manifest=json.loads((folder/'manifest.json').read_text());runs.append(folder.name)
                for name,digest in manifest['source_hashes'].items():
                    p=folder/'source'/name;data=p.read_bytes()
                    if sha(data)!=digest:raise ValueError('Executed source hash mismatch: '+str(p))
                    objects[digest]=len(data)
                    if digest not in seen:z.writestr(prefix+'/source_objects/'+digest,data);seen.add(digest)
                for p in sorted(folder.iterdir()):
                    if p.is_file() and p.suffix in ('.json','.jsonl'):
                        name='runs/'+folder.name+'/'+p.name;data=p.read_bytes()
                        runfiles[name]=sha(data);z.writestr(prefix+'/'+name,data)
            # Preserve full experiment records, including errors and registration.
            for p in safe_files(ROOT/'reports'):
                if p.suffix in ('.json','.jsonl','.csv'):
                    name=p.relative_to(ROOT).as_posix();data=p.read_bytes()
                    runfiles[name]=sha(data);z.writestr(prefix+'/'+name,data)
            for p in (ROOT/'EXPERIMENTS.csv',ROOT/'SEEDS.csv',ROOT/'code/restore_evidence.py'):
                z.writestr(prefix+'/'+p.relative_to(ROOT).as_posix(),p.read_bytes())
            evidence_manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),runs=runs,
                                   source_objects=objects,files=runfiles,
                                   restore_command='python code/restore_evidence.py --verify-only',
                                   truth_is_post_run_evaluation_only=True)
            z.writestr(prefix+'/EVIDENCE_MANIFEST.json',json.dumps(evidence_manifest,indent=2))
        archives.append(evidence)
    report=dict(tag=tag,utc=datetime.now(timezone.utc).isoformat(),runtime_files=len(index),
                evidence_runs=len(evidence_manifest['runs']) if evidence_manifest else 0,
                archives=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in archives])
    (output/f'Q4_{tag}_SHA256.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--output',default=str(ROOT/'release'))
    p.add_argument('--runtime-only',action='store_true');a=p.parse_args()
    print(json.dumps(build(a.tag,a.output,not a.runtime_only),indent=2))
