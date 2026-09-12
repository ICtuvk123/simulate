"""Run frozen F once in a freshly UI-verified official Problem 3 PRACTICE.

The policy receives documented feedback only. No simulator engine, seed, hidden
source coordinates, or official internal files are imported or consulted.
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
POLICY_CODE = PROJECT / 'local_simulator' / 'code'
sys.path.insert(0, str(POLICY_CODE))
from structural import StructuralController
from f_policy_presets import FROZEN_F_OPTIONS, FROZEN_F_VERSION
from q3client import Client, JsonlJournal, ProtocolError, canonical, parse_journal

NAMES = ('structural.py', 'structural_geometry.py', 'replanning.py',
         'reception_geometry.py', 'optimized.py', 'local_geometry.py',
         'controller.py', 'geometry.py', 'coverage.py', 'q3client.py',
         'policy_presets.py', 'e_policy_presets.py', 'f_policy_presets.py')


def verify_frozen_policy():
    freeze = json.loads((PROJECT / 'local_simulator/reports/optimization/F_FREEZE.json').read_text(encoding='utf-8'))
    if freeze['version'] != FROZEN_F_VERSION or freeze['policy_options'] != FROZEN_F_OPTIONS:
        raise ProtocolError('Frozen F configuration differs; no request sent')
    verified = {}
    for name in NAMES:
        digest = hashlib.sha256((POLICY_CODE / name).read_bytes()).hexdigest()
        expected = freeze['policy_file_sha256'].get(name)
        if expected is not None and digest != expected:
            raise ProtocolError(f'Frozen policy file differs: {name}; no request sent')
        verified[name] = digest
    assert 'engine' not in sys.modules and 'runner' not in sys.modules
    return verified


class PracticeTransport:
    def __init__(self, port):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Invalid local port')
        self.port = port

    def __call__(self, path, body, timeout):
        if path not in ('/enter', '/measure', '/clear', '/exit'):
            raise ProtocolError('Only the four documented action paths are allowed')
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)
        try:
            connection.request('POST', path, body=body, headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            return response.status, response.read().decode('utf-8')
        finally:
            connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--robot-id')
    parser.add_argument('--ui-proof', type=Path)
    args = parser.parse_args()
    verified = verify_frozen_policy()
    if args.prepare_only:
        print(json.dumps(dict(ready=True, strategy=FROZEN_F_VERSION,
                             frozen_files_verified=len(verified),
                             network_connection_made=False, source_generator_imported=False), indent=2))
        return 0
    if not args.robot_id or not args.ui_proof:
        parser.error('A current robot ID and fresh official PRACTICE UI proof are required')
    proof = json.loads(args.ui_proof.read_text(encoding='utf-8'))
    if (proof.get('mode') != 'problem3_practice' or proof.get('interface_ready') is not True
            or not proof.get('case_code') or proof.get('robot_id') != args.robot_id
            or '演练' not in proof.get('observed_text', '')):
        raise ProtocolError('Missing ready Problem 3 practice UI evidence; no request sent')
    observed = datetime.fromisoformat(proof['observed_at_utc'])
    if not 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= 120:
        raise ProtocolError('Stale UI evidence; no request sent')
    # Claim the observed case locally before any network action. A rerun cannot
    # silently enter another case or send a second enter for this authorization.
    marker = args.ui_proof.with_suffix('.consumed')
    with marker.open('x', encoding='utf-8') as handle:
        handle.write(proof['case_code'])
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-official-practice-F'
    directory = PROJECT / 'training_logs' / run_id
    directory.mkdir(parents=True, exist_ok=False)
    snapshot = directory / 'source'
    snapshot.mkdir()
    fingerprint = hashlib.sha256()
    for name in NAMES:
        path = POLICY_CODE / name
        fingerprint.update(name.encode() + path.read_bytes())
        shutil.copy2(path, snapshot / name)
    shutil.copy2(Path(__file__), snapshot / Path(__file__).name)
    shutil.copy2(args.ui_proof, directory / 'ui_mode_proof.json')
    (directory / 'frozen_policy_verification.json').write_text(json.dumps(verified, indent=2), encoding='utf-8')
    config = dict(FROZEN_F_OPTIONS)
    metadata = dict(run_id=run_id, mode='training', data_origin='official_problem3_practice',
                    case_code=proof['case_code'], seed=None, strategy_version=FROZEN_F_VERSION,
                    strategy_hash=fingerprint.hexdigest(), parameters=config,
                    policy_configuration=dict(strategy='F', policy_options=config),
                    parameter_hash=hashlib.sha256(canonical(config).encode()).hexdigest(),
                    authorization='User requested one official practice on 2026-09-12; formal tests prohibited')
    journal = JsonlJournal(directory / 'requests.jsonl', metadata)
    client = Client(args.robot_id, journal, transport=PracticeTransport(proof['port']))
    controller = StructuralController(client, **config)
    error = None
    try:
        controller.run()
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        journal.append(dict(event='client_stop', error=error, pending_request=client.pending))
    finally:
        journal.close()
    metrics = parse_journal(directory / 'requests.jsonl')
    metrics['client_error'] = error
    metrics['true_source_count'] = 'Awaiting post-run official practice UI; never given to policy'
    metrics['average_localization_clear_time_s_per_source'] = (
        metrics['total_time'] / metrics['clear_count'] if metrics.get('clear_count') else None)
    (directory / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    keys = ('run_id', 'case_code', 'run_status', 'clear_count', 'total_time',
            'average_localization_clear_time_s_per_source', 'move_time', 'RF_detection_count',
            'optical_count', 'completion_proved', 'accounting_warnings', 'client_error')
    print(json.dumps({key: metrics.get(key) for key in keys}, ensure_ascii=False, indent=2))
    print(str(directory))
    return int(bool(error) or not metrics['completion_proved'])


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
