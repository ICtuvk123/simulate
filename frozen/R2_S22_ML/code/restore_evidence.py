"""Verify raw local evidence and optionally restore deduplicated source files."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def restore(verify_only=False):
    manifest=json.loads((ROOT/'EVIDENCE_MANIFEST.json').read_text());count=0
    for name,digest in manifest['files'].items():
        p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT.resolve()) or sha(p)!=digest:raise ValueError(name)
    for digest in manifest['source_objects']:
        if sha(ROOT/'source_objects'/digest)!=digest:raise ValueError('source object '+digest)
    for run in manifest['runs']:
        folder=(ROOT/'runs'/run).resolve()
        if not folder.is_relative_to((ROOT/'runs').resolve()):raise ValueError(run)
        source=json.loads((folder/'manifest.json').read_text())['source_hashes']
        for name,digest in source.items():
            target=(folder/'source'/name).resolve()
            if not target.is_relative_to((folder/'source').resolve()):raise ValueError(name)
            if not verify_only:
                target.parent.mkdir(exist_ok=True)
                data=(ROOT/'source_objects'/digest).read_bytes()
                if target.exists() and target.read_bytes()!=data:raise ValueError('Existing source differs: '+str(target))
                if not target.exists():target.write_bytes(data)
            count+=1
    return dict(valid=True,runs=len(manifest['runs']),source_files=count,restored=not verify_only)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    print(json.dumps(restore(a.verify_only),indent=2))
