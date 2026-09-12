"""Frozen G+ on one UI-verified official Problem 3 practice case."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
POLICY=ROOT/'code'
sys.path.insert(0,str(POLICY))
from time_policy import TimePolicy
from g_policy_presets import FROZEN_G_OPTIONS
from q3client import Client, JsonlJournal, ProtocolError, canonical, parse_journal
sys.path.append(str(PROJECT/'code'))
from manual_official_practice import validate_case, claim_case
from run_official_practice_f import PracticeTransport

NAMES=('time_policy.py','route_search.py','structural.py','structural_geometry.py',
       'replanning.py','reception_geometry.py','optimized.py','local_geometry.py',
       'controller.py','geometry.py','coverage.py','q3client.py','g_policy_presets.py',
       'f_policy_presets.py','e_policy_presets.py','policy_presets.py')


def verify_policy():
    frozen=json.loads((ROOT/'FREEZE.json').read_text(encoding='utf-8'))
    candidate=json.loads((ROOT/'candidate.json').read_text(encoding='utf-8'))
    if candidate!=frozen['candidate']:
        raise ProtocolError('Candidate configuration differs from frozen validation')
    hashes={name:hashlib.sha256((POLICY/name).read_bytes()).hexdigest() for name in NAMES}
    for name,digest in hashes.items():
        if digest!=frozen['experiment_files_sha256'][name]:
            raise ProtocolError('Frozen candidate file changed: '+name)
        module=sys.modules.get(Path(name).stem)
        if module is not None and hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()!=digest:
            raise ProtocolError('Imported policy module differs: '+name)
    if 'engine' in sys.modules or 'runner' in sys.modules:
        raise ProtocolError('Local simulator must not be imported for official practice')
    options=dict(FROZEN_G_OPTIONS,**candidate['options'])
    return frozen,options,dict(candidate.get('extra',{})),hashes


def validate_proof(proof):
    validate_case(proof['robot_id'],proof['port'],proof['observed_text'],proof['case_code'])
    if (proof.get('mode')!='problem3_practice' or proof.get('interface_ready') is not True
            or proof.get('evidence_source') not in ('agent_observed_current_official_UI','human_read_current_official_UI')):
        raise ProtocolError('Fresh ready official practice UI evidence is required')
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(proof['observed_at_utc'])).total_seconds()
    if not 0<=age<=120:
        raise ProtocolError('Official UI evidence is stale')


def run(proof):
    frozen,options,extra,hashes=verify_policy()
    validate_proof(proof)
    claim_case(proof)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-official-practice-Gplus'
    directory=PROJECT/'training_logs'/run_id
    snapshot=directory/'source';snapshot.mkdir(parents=True,exist_ok=False)
    for name in NAMES:
        shutil.copy2(POLICY/name,snapshot/name)
    for source in (Path(__file__),PROJECT/'code/manual_official_practice.py',PROJECT/'code/run_official_practice_f.py'):
        shutil.copy2(source,snapshot/source.name)
    for name in ('FREEZE.json','candidate.json'):
        shutil.copy2(ROOT/name,directory/name)
    (directory/'ui_mode_proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    (directory/'frozen_policy_verification.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    policy_config=dict(strategy='Gplus',policy_options=options,policy_extra=extra)
    metadata=dict(run_id=run_id,mode='training',data_origin='official_problem3_practice',seed=None,
        case_code=proof['case_code'],strategy_version=frozen['version'],policy_configuration=policy_config,
        strategy_hash=hashlib.sha256(canonical(hashes).encode()).hexdigest(),
        parameter_hash=hashlib.sha256(canonical(policy_config).encode()).hexdigest(),
        authorization='User requested one official simulated practice with this frozen G+ strategy',
        mode_evidence_source=proof['evidence_source'],mode_verified_by_HTTP=False)
    journal=JsonlJournal(directory/'requests.jsonl',metadata)
    client=Client(proof['robot_id'],journal,transport=PracticeTransport(proof['port']))
    error=None;started=time.perf_counter()
    print(json.dumps(dict(starting_one_practice=True,case_code=proof['case_code'],strategy=frozen['version']),ensure_ascii=False),flush=True)
    try:
        TimePolicy(client,**options,**extra).run()
    except (Exception,KeyboardInterrupt) as exc:
        error=f'{type(exc).__name__}: {exc}'
        journal.append(dict(event='client_stop',error=error,pending_request=client.pending))
    finally:
        journal.close()
    metrics=parse_journal(directory/'requests.jsonl')
    metrics.update(client_error=error,program_wall_time_s=time.perf_counter()-started,
        true_source_count=None,average_localization_clear_time_s_per_source=(
            metrics['total_time']/metrics['clear_count'] if metrics['clear_count'] else None))
    (directory/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'reports/latest_official_practice.json').write_text(json.dumps(dict(run_id=run_id,directory=str(directory)),indent=2),encoding='utf-8')
    print(json.dumps({k:metrics.get(k) for k in ('run_id','clear_count','total_time',
        'average_localization_clear_time_s_per_source','completion_proved','accounting_warnings',
        'client_error','program_wall_time_s')},ensure_ascii=False,indent=2),flush=True)
    print(str(directory),flush=True)
    return int(bool(error) or not metrics['completion_proved'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');p.add_argument('--ui-proof',type=Path)
    a=p.parse_args();frozen,options,extra,hashes=verify_policy()
    if a.prepare_only:
        print(json.dumps(dict(ready=True,version=frozen['version'],verified_files=len(hashes),
            official_connection_made=False,source_generator_imported=False,extra=extra),indent=2))
        return 0
    if not a.ui_proof:p.error('--ui-proof is required')
    return run(json.loads(a.ui_proof.read_text(encoding='utf-8')))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
