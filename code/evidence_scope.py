"""Distinguish included raw runs from historical reports retained for context."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build():
    phases=[]
    for path in sorted((ROOT/'reports').rglob('paired_results.csv')):
        with path.open(encoding='utf-8-sig',newline='') as f:
            csv_references={row['run_id'] for row in csv.DictReader(f) if row.get('run_id')}
        raw_references=set()
        record_files=[path.parent/'runs.jsonl',*sorted(path.parent.glob('worker*.jsonl'))]
        for records in record_files:
            if not records.is_file():continue
            for line in records.read_text(encoding='utf-8-sig').splitlines():
                if line.strip():
                    row=json.loads(line)
                    if row.get('run_id'):raw_references.add(row['run_id'])
        references=sorted(csv_references|raw_references)
        included=[run for run in references if (ROOT/'runs'/run/'manifest.json').is_file()]
        missing=sorted(set(references)-set(included))
        registration=path.parent/'registration.json'
        role=json.loads(registration.read_text()).get('role') if registration.is_file() else 'historical_report'
        phases.append(dict(phase=path.parent.relative_to(ROOT/'reports').as_posix(),purpose=role,
                           referenced_runs=len(references),csv_run_references=len(csv_references),
                           journal_run_references=len(raw_references),raw_runs_included=len(included),missing_run_ids=missing))
    result=dict(phases=phases,current_round_raw_complete=all(not p['missing_run_ids'] for p in phases if p['phase'].startswith('R2_')),
                note='Historical reports with missing raw runs are context only. The current round retains every referenced run; repeated development seeds are not fresh validation.')
    if not result['current_round_raw_complete']:
        raise ValueError('Current-round reports reference raw runs not yet collected: '+str([p['phase'] for p in phases if p['phase'].startswith('R2_') and p['missing_run_ids']]))
    (ROOT/'reports/EVIDENCE_SCOPE.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    result=build();print(json.dumps(dict(phases=len(result['phases']),current_round_raw_complete=result['current_round_raw_complete'])))
