"""Exercise the delivered local entry point from a different working directory."""
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    rows = list(csv.DictReader((ROOT / 'reports/validation100/runs.csv').open(encoding='utf-8-sig')))
    checks = []
    for baseline in (False, True):
        command = [sys.executable, str(ROOT / 'run_candidate.py'), '--seed', '22001']
        if baseline:
            command.append('--baseline')
        result = subprocess.run(command, cwd=ROOT.parent, capture_output=True, text=True,
                                encoding='utf-8', check=True, timeout=120)
        data = json.loads(result.stdout)
        recorded = next(r for r in rows if r['variant'] == data['variant'] and r['seed'] == '22001')
        assert abs(data['total_time'] - float(recorded['total_time'])) < 1e-6
        assert abs(data['seconds_per_source'] - float(recorded['average_localization_clear_time_s_per_source'])) < 1e-6
        assert data['cleared'] == data['count'] and data['completion_proved'] and not data['audit_errors']
        replay = Path(data['directory']) / 'replay.html'
        assert replay.exists()
        embedded = next(line for line in replay.read_text(encoding='utf-8').splitlines()
                        if line.startswith('const EMBEDDED = '))
        embedded_data = json.loads(embedded.removeprefix('const EMBEDDED = ').removesuffix(';'))
        assert embedded_data['metadata']['experimental_variant']['name'] == data['variant']
        assert abs(embedded_data['metrics']['total_time'] - data['total_time']) < 1e-6
        checks.append(dict(**data, agrees_with_frozen_validation=True, html_replay=str(replay)))
    recorded_ids = set()
    for table in (ROOT / 'reports').glob('*/runs.csv'):
        recorded_ids.update(r['run_id'] for r in csv.DictReader(table.open(encoding='utf-8-sig')))
    additional_ids = sorted(p.parent.name for p in (ROOT / 'runs').glob('*/result.json')
                            if p.parent.name not in recorded_ids)
    output = dict(all_pass=True, additional_local_runs=len(additional_ids), additional_run_ids=additional_ids,
                  successful_cli_checks=len(checks), working_directory=str(ROOT.parent), checks=checks)
    (ROOT / 'reports/entrypoint_check.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
