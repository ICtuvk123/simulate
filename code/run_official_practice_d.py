"""Run frozen D once in a UI-verified official PROBLEM 3 PRACTICE session.

This is an explicit adapter authorized by the user's latest request. The local
simulator's disabled default HTTP transport stays disabled. No source generator,
seed, hidden source file, official database, or oracle is imported/read here.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import sys

PROJECT = Path(__file__).resolve().parents[1]
POLICY_CODE = PROJECT/'local_simulator'/'code'
sys.path.insert(0,str(POLICY_CODE))
from optimized import OptimizedController
from policy_presets import FROZEN_D_OPTIONS, FROZEN_D_VERSION
from q3client import Client, JsonlJournal, ProtocolError, canonical, parse_journal


class PracticeTransport:
    def __init__(self, port):
        if type(port) is not int or not 1<=port<=65535:
            raise ValueError('Invalid local port')
        self.port=port

    def __call__(self,path,body,timeout):
        if path not in ('/enter','/measure','/clear','/exit'):
            raise ProtocolError('Only documented four action paths allowed')
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=timeout)
        try:
            connection.request('POST',path,body=body,headers={'Content-Type':'application/json'})
            response=connection.getresponse()
            return response.status,response.read().decode('utf-8')
        finally:
            connection.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--robot-id')
    parser.add_argument('--ui-proof',type=Path)
    args=parser.parse_args()
    if args.prepare_only:
        assert 'engine' not in sys.modules and 'runner' not in sys.modules
        print(json.dumps(dict(ready=True,strategy=FROZEN_D_VERSION,options=FROZEN_D_OPTIONS,
                              network_connection_made=False,source_generator_imported=False),indent=2))
        return 0
    if not args.robot_id or not args.ui_proof:
        parser.error('A current robot ID and fresh official PRACTICE UI proof are required')
    proof=json.loads(args.ui_proof.read_text(encoding='utf-8'))
    if (proof.get('mode')!='problem3_practice' or proof.get('interface_ready') is not True
            or not proof.get('case_code') or proof.get('robot_id')!=args.robot_id
            or '演练' not in proof.get('observed_text','')):
        raise ProtocolError('Missing UI evidence of ready Problem 3 practice; no request sent')
    observed=datetime.fromisoformat(proof['observed_at_utc'])
    age=(datetime.now(timezone.utc)-observed).total_seconds()
    if not 0<=age<=120:
        raise ProtocolError('UI observation is stale; recheck practice mode before connecting')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-official-practice-D'
    directory=PROJECT/'training_logs'/run_id
    directory.mkdir(parents=True,exist_ok=False)
    snapshot=directory/'source';snapshot.mkdir()
    names=('optimized.py','local_geometry.py','controller.py','geometry.py','coverage.py',
           'q3client.py','policy_presets.py')
    fingerprint=hashlib.sha256()
    for name in names:
        path=POLICY_CODE/name
        fingerprint.update(name.encode()+path.read_bytes())
        shutil.copy2(path,snapshot/name)
    shutil.copy2(Path(__file__),snapshot/Path(__file__).name)
    shutil.copy2(args.ui_proof,directory/'ui_mode_proof.json')
    config=dict(FROZEN_D_OPTIONS)
    metadata=dict(run_id=run_id,mode='training',data_origin='official_problem3_practice',
                  case_code=proof['case_code'],seed=None,strategy_version=FROZEN_D_VERSION,
                  strategy_hash=fingerprint.hexdigest(),parameters=config,
                  policy_configuration=dict(strategy='D',policy_options=config),
                  parameter_hash=hashlib.sha256(canonical(config).encode()).hexdigest(),
                  authorization='User requested one real simulator run; formal tests remain prohibited')
    journal=JsonlJournal(directory/'requests.jsonl',metadata)
    client=Client(args.robot_id,journal,transport=PracticeTransport(proof['port']))
    controller=OptimizedController(client,**config)
    error=None
    try:
        controller.run()
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        journal.append(dict(event='client_stop',error=error,pending_request=client.pending))
    finally:
        journal.close()
    metrics=parse_journal(directory/'requests.jsonl')
    metrics['client_error']=error
    metrics['true_source_count']='Awaiting post-run official practice UI; never given to policy'
    (directory/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:metrics.get(key) for key in ('run_id','case_code','run_status','clear_count',
                     'total_time','move_time','RF_detection_count','optical_count',
                     'completion_proved','accounting_warnings','client_error')},ensure_ascii=False,indent=2))
    print(str(directory))
    return int(bool(error) or not metrics['completion_proved'])


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
