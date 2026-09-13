"""Save an immutable research candidate; this never changes INCUMBENT.json."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def snapshot(name, configuration):
    if not re.fullmatch('[A-Za-z0-9_]+', name):
        raise ValueError('Invalid snapshot name')
    config = (ROOT / configuration).resolve()
    if not config.is_relative_to(ROOT):
        raise ValueError('Configuration leaves project')
    command = ['git', '-c', 'safe.directory=' + ROOT.as_posix(), '-C', str(ROOT)]
    if subprocess.check_output(command + ['status', '--porcelain', '--', 'code', 'configs'], text=True).strip():
        raise ValueError('Commit code and configuration before taking a snapshot')
    commit = subprocess.check_output(command + ['rev-parse', 'HEAD'], text=True).strip()
    destination = ROOT / 'frozen' / name
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'code').mkdir()
    (destination / 'configs').mkdir()
    hashes = {}
    for source in sorted((ROOT / 'code').glob('*.py')):
        hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        shutil.copy2(source, destination / 'code' / source.name)
    shutil.copy2(config, destination / 'configs' / config.name)
    result = dict(version=name, utc=datetime.now(timezone.utc).isoformat(), commit=commit,
                  status='research_snapshot_not_promoted', configuration=json.loads(config.read_text(encoding='utf-8')),
                  config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(), source_hashes=hashes)
    target = ROOT / 'configs' / (name + '_FREEZE.json')
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    return dict(snapshot=destination.relative_to(ROOT).as_posix(),
                config=(destination / 'configs' / config.name).relative_to(ROOT).as_posix(),
                freeze=target.relative_to(ROOT).as_posix())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('configuration')
    args = parser.parse_args()
    print(json.dumps(snapshot(args.name, args.configuration), indent=2))
