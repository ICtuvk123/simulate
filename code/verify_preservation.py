"""Read-only recheck of original Q3 G and original Q4 frozen D artifacts."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from verify_freeze import verify
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    prior=json.loads((ROOT/'reports/G_PRESERVATION_FINAL.json').read_text())
    checks=[]
    for item in prior['policy_files']:
        path=Path(item['file']);actual=sha(path)
        checks.append(dict(path=str(path),expected=item['expected'],actual=actual,valid=actual==item['expected']))
    for item in prior['configuration_reports']:
        path=Path(item['file']);actual=sha(path)
        checks.append(dict(path=str(path),expected=item['sha256'],actual=actual,valid=actual==item['sha256']))
    runner=ROOT.parent/'jammer_search_q3/local_simulator/code/runner.py'
    checks.append(dict(path=str(runner),expected=sha(ROOT/'reference_g/runner.py'),actual=sha(runner),
                       valid=runner.read_bytes()==(ROOT/'reference_g/runner.py').read_bytes()))
    old=ROOT.parent/'jammer_search_q4'
    original=json.loads((old/'INCUMBENT.json').read_text())
    if original['version']!='D_COMPACT-validated-20260912':raise ValueError('Original Q4 incumbent was replaced')
    frozen=verify(ROOT/'configs/D_COMPACT_FREEZE.json',old/'frozen/D_COMPACT/code',old/'frozen/D_COMPACT/configs/D_compact_optical.json')
    report=dict(checked_utc=datetime.now(timezone.utc).isoformat(),q3_g=checks,
                original_q4_version=original['version'],original_q4_frozen=frozen,
                original_q4_freeze_matches=(old/'configs/D_COMPACT_FREEZE.json').read_bytes()==(ROOT/'configs/D_COMPACT_FREEZE.json').read_bytes(),
                checked_items_only=True)
    report['valid']=all(item['valid'] for item in checks) and frozen['valid'] and report['original_q4_freeze_matches']
    (ROOT/'reports/R2_ORIGINAL_ARTIFACT_PRESERVATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(valid=report['valid'],q3_g_items=len(checks),q4_source_files=frozen['source_count'])))
    return 0 if report['valid'] else 1

if __name__=='__main__':raise SystemExit(main())
