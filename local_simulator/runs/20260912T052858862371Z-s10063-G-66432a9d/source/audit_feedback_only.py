"""Replay decisions with public replies only; no engine, seed, or truth file.

This checks this controller's observed execution, not security against arbitrary
malicious Python introspection. Disk/network/process access is denied while the
controller runs; every requested action must match the original action exactly.
"""
import argparse
import array
import csv
import json
from pathlib import Path
import sys

from optimized import OptimizedController
from replanning import ReplanningController
from structural import StructuralController
from route_search import RouteSearchController
from q3client import Client

ROOT = Path(__file__).resolve().parents[1]
GUARDED = False


def audit_hook(event, args):
    if GUARDED and event in ('open','os.listdir','os.scandir','socket.connect',
                              'socket.getaddrinfo','subprocess.Popen'):
        raise RuntimeError('Controller attempted forbidden I/O: '+event)


sys.addaudithook(audit_hook)


class MemoryJournal:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)


def verify(run_id, journal_path=None):
    global GUARDED
    # Read only the original action/response journal; result/evaluation files
    # and source generation code are never imported or opened by this program.
    path = Path(journal_path) if journal_path is not None else ROOT/'runs'/run_id/'requests.jsonl'
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    metadata = next(r for r in records if r['event']=='metadata')
    options = metadata['policy_configuration']['policy_options']
    strategy=metadata['policy_configuration']['strategy']
    controller_type = RouteSearchController if strategy=='G' else StructuralController if strategy=='F' else ReplanningController if strategy=='E' else OptimizedController
    replies = [r for r in records if r['event']=='response']
    del metadata, records
    position = 0
    def transport(path,body,timeout):
        nonlocal position
        recorded = replies[position]
        requested = json.loads(body)
        def action(value):
            return {k:v for k,v in value.items() if k not in ('request_id','robot_id')}
        assert path==recorded['path'] and action(requested)==action(recorded['payload']), (
            'Decision differs at public-feedback step '+str(position))
        position += 1
        return recorded['http_status'],recorded['response_body']
    journal = MemoryJournal()
    client = Client('local-robot',journal,transport=transport)
    assert 'engine' not in sys.modules and 'runner' not in sys.modules
    GUARDED = True
    try:
        controller = controller_type(client,**options)
        controller.run()
    finally:
        GUARDED = False
    assert position==len(replies) and client.ledger.exited
    return dict(run_id=run_id,actions_checked=position,all_decisions_identical=True,
                engine_imported=False,truth_file_read=False,seed_passed_to_controller=False,
                disk_network_process_access_during_decisions='denied',
                clear_count=len(client.ledger.cleared),total_time=client.ledger.virtual_time)


if __name__=='__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--runs-csv',required=True)
    p.add_argument('--variant',required=True)
    p.add_argument('--output',default='feedback_only_audit.json')
    args = p.parse_args()
    with open(args.runs_csv,encoding='utf-8-sig') as stream:
        selected = [row for row in csv.DictReader(stream) if row['variant']==args.variant]
    results = [verify(row['run_id']) for row in selected]
    assert results
    destination = ROOT/'reports'/'optimization'/args.output
    destination.write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(dict(runs=len(results),actions=sum(r['actions_checked'] for r in results),
                         all_decisions_identical=True,engine_imported=False,truth_file_read=False),indent=2))
