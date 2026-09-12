"""Separate manual practice entry. Never called by local experiments."""
import argparse,json,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))


def main():
    p=argparse.ArgumentParser(description='Manual official PRACTICE only. Select practice in the official UI first.')
    p.add_argument('--robot-id',required=True)
    p.add_argument('--confirm-practice',required=True,choices=['I_HAVE_SELECTED_PRACTICE'])
    p.add_argument('--url',default='http://127.0.0.1:2026')
    a=p.parse_args()
    incumbent=json.loads((ROOT/'INCUMBENT.json').read_text(encoding='utf-8'))
    from verify_freeze import verify as verify_integrity
    integrity=verify_integrity(ROOT/incumbent['freeze'],ROOT/incumbent['code_directory'],ROOT/incumbent['configuration'])
    if not integrity['valid']:raise RuntimeError('Frozen version integrity check failed before any connection')
    sys.path.insert(0,str(ROOT/incumbent.get('code_directory','code')))
    from q3client import Client,JsonlJournal
    from q4controller import Q4Controller
    from practice_transport import PracticeTransport
    from verify_exit import verify
    options=json.loads((ROOT/incumbent['configuration']).read_text(encoding='utf-8'))
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    path=ROOT/'official_practice_logs'/run_id/'requests.jsonl'
    journal=JsonlJournal(path,dict(mode='operator_declared_practice',version=incumbent['version'],policy_options=options))
    client=Client(a.robot_id,journal,transport=PracticeTransport(a.url,a.confirm_practice))
    error=None
    try:Q4Controller(client,options).run()
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}';journal.append(dict(event='client_stop',error=error))
    finally:journal.close()
    result=verify(path)
    print(json.dumps(dict(error=error,journal=str(path),verification=result),ensure_ascii=False,indent=2))
    return 0 if result['valid'] and error is None else 1


if __name__=='__main__':raise SystemExit(main())
