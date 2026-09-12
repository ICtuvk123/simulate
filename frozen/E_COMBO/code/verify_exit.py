"""Independently check exit and accounting from the actual response journal."""
import argparse,json
from q3client import parse_journal


def verify(path):
    m=parse_journal(path)
    legal=bool(m['run_status']=='exited' and m['completion_proved'] and not m['protocol_errors'] and not m['accounting_warnings'])
    return dict(valid=legal,clear_count=m['clear_count'],completion_audit=m.get('completion_audit'),
                certificate=m.get('completion_certificate'),protocol_errors=m['protocol_errors'],
                accounting_warnings=m['accounting_warnings'],total_time=m['total_time'],
                reconstructed_time=m['accounted_total_time'],truth_required=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('journal');a=p.parse_args()
    result=verify(a.journal);print(json.dumps(result,indent=2));raise SystemExit(0 if result['valid'] else 1)
