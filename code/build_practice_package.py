"""Create and verify a small standalone practice package without official calls."""
import hashlib
import os
import json
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    archive = release / ('Q4_practice_202617201735_' + stamp + '.zip')
    incumbent = json.loads((ROOT / 'INCUMBENT.json').read_text(encoding='utf-8'))
    selected = ['official_practice.py', 'start_practice.py', 'start_q4_practice.cmd',
                'practice_settings.json', 'INCUMBENT.json', 'code/verify_freeze.py',
                'code/practice_offline_check.py', 'tests/test_practice_entry.py',
                'Q4_PRACTICE_README.md', 'reports/ACTIVE_ALGORITHM.md',
                incumbent['freeze'], incumbent['configuration']]
    selected += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / incumbent['code_directory']).glob('*.py'))]
    data = {name: (ROOT / name).read_bytes() for name in selected}
    data['README.md'] = data['Q4_PRACTICE_README.md']
    # Native Windows launcher uses CRLF; no shell command contains the team ID.
    data['start_q4_practice.cmd'] = data['start_q4_practice.cmd'].replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    manifest = dict(version=incumbent['version'], robot_id='202617201735',
                    official_requests_during_creation=0,
                    files={name: sha(value) for name, value in sorted(data.items())})
    prefix = 'Q4_practice/'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for name, value in sorted(data.items()):
            package.writestr(prefix + name, value)
        package.writestr(prefix + 'PACKAGE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    destination = ROOT / 'tmp' / ('演练脚本 解压核验_' + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as package:
        assert len(package.namelist()) == len(set(package.namelist()))
        for name in package.namelist():
            assert (destination / name).resolve().is_relative_to(destination.resolve())
        for name, expected in manifest['files'].items():
            assert sha(package.read(prefix + name)) == expected
        package.extractall(destination)
    unpacked = destination / 'Q4_practice'
    checks = []
    for name, args in [('preflight', ['official_practice.py', '--check-only', '--robot-id', '202617201735']),
                       ('regression', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'])]:
        result = subprocess.run([sys.executable, '-X', 'utf8', *args], cwd=unpacked,
                                capture_output=True, text=True, encoding='utf-8', timeout=180,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (destination / (name + '.txt')).write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
        checks.append(dict(name=name, returncode=result.returncode))
        if result.returncode:
            raise RuntimeError('Extracted check failed: ' + name + '\n' + result.stdout + result.stderr)
    if os.name == 'nt':
        # Reproduce the reported failure: no Python commands in PATH. Exercise
        # the real .cmd from a fresh Chinese/spaced extraction directory.
        env = os.environ.copy()
        env['PATH'] = ''
        system_root = next(value for key, value in env.items() if key.casefold() == 'systemroot')
        command = [str(Path(system_root) / 'System32/cmd.exe'), '/d', '/c',
                   'start_q4_practice.cmd', '--check-only']
        result = subprocess.run(command, cwd=unpacked, env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=90,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (destination / 'windows_no_python_path.txt').write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
        checks.append(dict(name='windows_launcher_without_python_in_path', returncode=result.returncode))
        if result.returncode or 'network_requests' not in result.stdout:
            raise RuntimeError('Windows launcher check failed: ' + result.stdout + result.stderr)
    report = dict(valid=True, archive=str(archive), bytes=archive.stat().st_size,
                  sha256=sha(archive.read_bytes()), packaged_files=len(data),
                  frozen_version=incumbent['version'], robot_id='202617201735',
                  official_requests=0, full_scene_performance_tests=0,
                  checks=checks, extracted_directory=str(unpacked),
                  notes='Only an offline synthetic HTTP fixture was executed. This does not start or certify an official practice session.')
    archive.with_suffix('.QA.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'reports/Q4_PRACTICE_PACKAGE_QA.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
