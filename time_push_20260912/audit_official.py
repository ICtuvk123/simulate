"""Replay an official G+ run from public replies only; never reconnect."""
import json
from pathlib import Path
import sys
import official_practice as app
import audit_feedback_only as guard


def main():
    latest=json.loads((app.ROOT/'reports/latest_official_practice.json').read_text())
    directory=Path(latest['directory'])
    records=[json.loads(s) for s in (directory/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
    metadata=next(r for r in records if r['event']=='metadata')
    frozen,options,extra,hashes=app.verify_policy()
    assert metadata['strategy_version']==frozen['version']
    assert metadata['policy_configuration']==dict(strategy='Gplus',policy_options=options,policy_extra=extra)
    replies=[r for r in records if r['event']=='response']
    del records,metadata
    position=0
    def transport(path,body,timeout):
        nonlocal position
        row=replies[position];requested=json.loads(body)
        def action(d):return {k:v for k,v in d.items() if k not in ('request_id','robot_id')}
        assert path==row['path'] and action(requested)==action(row['payload']),position
        position+=1
        return row['http_status'],row['response_body']
    journal=guard.MemoryJournal();client=app.Client('replay-robot',journal,transport=transport)
    assert 'engine' not in sys.modules and 'runner' not in sys.modules
    guard.GUARDED=True
    try:
        app.TimePolicy(client,**options,**extra).run()
    finally:
        guard.GUARDED=False
    assert position==len(replies) and client.ledger.exited
    result=dict(run_id=latest['run_id'],actions_checked=position,all_decisions_identical=True,
        clear_count=len(client.ledger.cleared),total_time=client.ledger.virtual_time,
        engine_imported=False,hidden_source_information_used=False,
        disk_network_process_access_during_decisions='denied')
    (directory/'feedback_only_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
