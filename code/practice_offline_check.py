"""Exercise the real frozen controller through an in-memory HTTP fixture.

No socket is opened. Sixteen co-located near responses test protocol integration,
not algorithm performance. The fixture's state is never passed to the policy.
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(case, output):
    def no_network(event, args):
        if event == 'socket.connect':
            raise AssertionError('Offline check must never open a network connection')
    sys.addaudithook(no_network)
    import official_practice as entry
    state = dict(requests=[], cache={}, cleared=set(), position=(0., 0.),
                 channel=1, virtual=0., dropped=False)

    class Response:
        status = 200
        def __init__(self, body, drop=False, status=200):
            self.body, self.drop, self.status = body, drop, status
        def read(self):
            if self.drop:
                raise OSError('offline fixture: reply lost after acceptance')
            return json.dumps(self.body).encode('utf-8')

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == '127.0.0.1' and port == 2026
        def request(self, method, path, body, headers):
            assert method == 'POST' and path in ('/enter', '/measure', '/clear', '/exit')
            payload = json.loads(body)
            assert payload['robot_id'] == '202617201735'
            assert set(payload) == ({'arena_id', 'robot_id', 'request_id'} |
                                    ({'channel', 'position'} if path in ('/measure', '/clear') else set()))
            state['requests'].append((path, body))
            self.path, self.payload, self.body = path, payload, body
        def getresponse(self):
            path, payload = self.path, self.payload
            if case == 'uncertain':
                raise OSError('offline fixture: no definitive response')
            if case == 'rejected':
                return Response(dict(accepted=False, real_timestamp_ms=0, virtual_time_s=0))
            if case == 'http_error':
                return Response(dict(accepted=True, real_timestamp_ms=0, virtual_time_s=0), status=500)
            rid = payload['request_id']
            if rid in state['cache']:
                original_path, original_body, reply = state['cache'][rid]
                assert (path, self.body) == (original_path, original_body)
                return Response(reply)
            reply = dict(accepted=True, real_timestamp_ms=0)
            if path == '/enter':
                reply.update(max_virtual_duration_s=360000, max_real_duration_s=1200,
                             remaining_real_duration_s=0 if case == 'budget' else 1200)
            elif path in ('/measure', '/clear'):
                p = payload['position']; point = (p['x'], p['y']); ch = payload['channel']
                state['virtual'] += math.dist(state['position'], point) / 5
                state['position'] = point
                if path == '/measure':
                    state['virtual'] += 5 + int(ch != state['channel']); state['channel'] = ch
                    assert math.hypot(*point) <= 5, 'Unexpected fixture station'
                    reply['measure_result'] = 'near' if ch <= 16 and ch not in state['cleared'] else 'no_signal'
                else:
                    success = ch <= 16 and ch not in state['cleared'] and math.hypot(*point) <= 20
                    state['virtual'] += 3 + 2 * success
                    if success:
                        state['cleared'].add(ch)
                    reply['clear_result'] = 'success' if success else 'no_target_in_range'
            else:
                reply['exit_reason'] = 'user_exit'
            reply['virtual_time_s'] = state['virtual']
            state['cache'][rid] = (path, self.body, reply)
            drop = case == 'lost_reply' and path == '/measure' and not state['dropped']
            state['dropped'] |= drop
            return Response(reply, drop)
        def close(self):
            pass

    def factory(url, confirmation):
        from practice_transport import PracticeTransport
        return PracticeTransport(url, confirmation, connection_factory=Connection)

    result, exit_code = entry.run_practice('202617201735', entry.CONFIRMATION,
                                          log_root=output, quiet=True, transport_factory=factory)
    assert result['mode'] == 'offline_http_fixture'
    if case in ('success', 'lost_reply'):
        assert exit_code == 0 and result['completion_proved']
        assert result['clear_count'] == 16 and abs(result['total_virtual_s'] - 175) < 1e-8
        assert result['independent_exit']['valid']
        assert result['network_retries'] == int(case == 'lost_reply')
        assert state['requests'][-1][0] == '/exit'
    else:
        assert exit_code == 1 and not result['completion_proved']
        assert result['mean_virtual_s_per_cleared_source'] is None
        assert not any(path == '/exit' for path, _ in state['requests'])
        assert len(state['requests']) == (3 if case == 'uncertain' else 1)
    if case == 'uncertain':
        assert len(set(state['requests'])) == 1, 'Uncertain retries must preserve path and exact bytes'
    if case == 'lost_reply':
        assert state['requests'][1] == state['requests'][2]
    import q4controller
    assert Path(q4controller.__file__).resolve().is_relative_to(ROOT / 'frozen/R2_S22_ML/code')
    result_file = Path(result['journal']).with_name('summary.json')
    assert json.loads(result_file.read_text(encoding='utf-8')) == json.loads(json.dumps(result))
    return dict(valid=True, case=case, actual_network_requests=0, fixture_requests=len(state['requests']),
                journal=result['journal'], completion_proved=result['completion_proved'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=['success', 'lost_reply', 'rejected', 'http_error', 'uncertain', 'budget'], required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.output), ensure_ascii=False, indent=2))
