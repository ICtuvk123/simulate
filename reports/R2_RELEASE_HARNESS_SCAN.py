"""Read-only inspection of current release inputs; never calls a simulator."""
import csv,hashlib,json,re
from pathlib import Path
ROOT=Path('D:/computer_learning/jammer_search_q4_r2')
OUT=Path(__file__).resolve().with_suffix('.json')
results={'main_root':str(ROOT),'simulation_runs':0}
missing_columns=[]
for path in (ROOT/'reports').rglob('paired_results.csv'):
    with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    if not rows or 'run_id' in rows[0]:continue
    journal=path.parent/'runs.jsonl'
    ids=[r['run_id'] for r in map(json.loads,journal.read_text().splitlines()) if r.get('run_id')] if journal.exists() else []
    missing_columns.append(dict(phase=path.parent.relative_to(ROOT/'reports').as_posix(),
        jsonl_run_ids=len(ids),missing_manifests=sum(not(ROOT/'runs'/rid/'manifest.json').exists() for rid in ids)))
results['csv_scope_without_run_id']=missing_columns
files=[]
for folder in ('code','configs','frozen','tests','inputs','figures','reports','examples'):
    files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.log'))
suspect_names=[str(p.relative_to(ROOT)) for p in files if re.search(r'(credential|password|secret|token|cookie|account|\.pem$|\.key$|id_rsa)',p.name,re.I)]
official_log_candidates=[str(p.relative_to(ROOT)) for p in files if 'official_practice_logs' in p.parts]
results.update(selected_folder_files=len(files),suspect_file_names=suspect_names,official_raw_log_paths_in_selected_folders=official_log_candidates)
observed_ids=[];sensitive_keys=[]
for path in files:
    if path.suffix.lower() not in ('.json','.jsonl','.txt','.md','.csv','.py'):continue
    data=path.read_text(encoding='utf-8-sig',errors='replace')
    for value in re.findall(r'"robot_id"\s*:\s*"([^"\n]*)"',data):
        if value not in ('local-robot','r','team','t','test','robot','x','r1','demo','unit-test','test-robot'):
            observed_ids.append(dict(path=str(path.relative_to(ROOT)),value_redacted=True,length=len(value)))
    if re.search(r'"(?:access_token|refresh_token|password|cookie|api_key|private_key)"\s*:\s*"[^"\n]+"',data,re.I):
        sensitive_keys.append(str(path.relative_to(ROOT)))
results['nonallowlisted_robot_id_literals']=observed_ids
results['nonempty_sensitive_key_literals']=sensitive_keys
official_reports={}
for path in (ROOT/'reports').glob('OFFICIAL_PRACTICE*'):
    if path.is_file():official_reports[path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
results['official_summary_files']=official_reports
manifests=list((ROOT/'runs').glob('*/manifest.json'));nonlocal_manifests=[];nonlocal_journals=[];ids_checked=0
for path in manifests:
    if not json.loads(path.read_text()).get('engine_configuration'):nonlocal_manifests.append(path.parent.name)
    journal=path.parent/'requests.jsonl'
    if journal.is_file():
        values=re.findall(r'"robot_id"\s*:\s*"([^"\n]*)"',journal.read_text())
        ids_checked+=len(values)
        if any(value!='local-robot' for value in values):nonlocal_journals.append(path.parent.name)
results['evidence_run_scan']=dict(eligible_runs=len(manifests),nonlocal_manifests=nonlocal_manifests,
    robot_id_literals_checked=ids_checked,nonlocal_journals=nonlocal_journals,
    note='Read-only live-directory snapshot; final archive build must follow completion of active runs.')
files_to_hash=['code/reproduce_run.py','code/run_r2_final_holdout.py','code/package_release.py','code/evidence_scope.py','code/setup_workers.py','q4.py','official_practice.py','code/snapshot_case.py','code/frozen_policy_worker.py','code/frozen_experiment.py','code/practice_transport.py']
results['source_hashes']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files_to_hash}
OUT.write_bytes(json.dumps(results,indent=2).encode())
print(json.dumps({k:v for k,v in results.items() if k!='source_hashes'},indent=2))
