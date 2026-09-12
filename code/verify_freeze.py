"""Verify every frozen source byte and the frozen configuration."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def verify(freeze,code_directory,config):
    f=json.loads(Path(freeze).read_text(encoding='utf-8'));code=Path(code_directory)
    failures=[]
    for name,expected in f['source_hashes'].items():
        p=code/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:failures.append(name)
    expected_config=f.get('configuration')
    if expected_config!=json.loads(Path(config).read_text(encoding='utf-8')):failures.append('configuration')
    return dict(valid=not failures,version=f['version'],commit=f['commit'],source_count=len(f['source_hashes']),failures=failures)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--incumbent',default=str(ROOT/'INCUMBENT.json'));a=p.parse_args()
    i=json.loads(Path(a.incumbent).read_text());result=verify(ROOT/i['freeze'],ROOT/i['code_directory'],ROOT/i['configuration'])
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['valid'] else 1)
