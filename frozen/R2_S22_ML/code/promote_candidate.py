"""Freeze a validated candidate from the exact execution snapshot, not the editor."""
import argparse,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def require_independent_exit(directory):
    journal=directory/'requests.jsonl';proof=directory/'independent_exit.json'
    if not proof.is_file():raise ValueError('Second independent exit audit is missing')
    result=json.loads(proof.read_text(encoding='utf-8'))
    if not result.get('valid') or result.get('truth_read') is not False or result.get('controller_geometry_imported') is not False:
        raise ValueError('Second exit audit failed or was not independent')
    if result.get('journal_sha256')!=hashlib.sha256(journal.read_bytes()).hexdigest():
        raise ValueError('Second exit audit belongs to a different journal')


def promote(name,phase,baseline,candidate,config):
    folder=ROOT/'reports'/phase
    comparison=json.loads((folder/f'comparison_{baseline}_{candidate}.json').read_text())
    if not comparison['gate_passed']:raise ValueError('Predeclared promotion gate did not pass')
    freeze=json.loads((ROOT/'configs'/f'{name}_VALIDATION_FREEZE.json').read_text())
    rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text().splitlines()]
    selected=[r for r in rows if r['task']['variant']==candidate]
    if sorted(r['task']['seed'] for r in selected)!=freeze['validation_seeds']:raise ValueError('Validation seed registration differs')
    actions=0
    for r in rows:
        if not r.get('metrics',{}).get('all_success'):raise ValueError('Failure or missing result in validation')
        directory=Path(r['directory']);m=json.loads((directory/'manifest.json').read_text())
        require_independent_exit(directory)
        if m['source_hashes']!=freeze['source_hashes']:raise ValueError('Executed code differs from the prevalidation freeze')
        if r['task']['variant']==candidate and m['policy_options']!=freeze['configuration']:raise ValueError('Candidate configuration differs')
        replay=json.loads((directory/'feedback_replay.json').read_text())
        if not replay['valid']:raise ValueError('Feedback replay failed')
        actions+=replay['actions']
    directory=Path(selected[0]['directory']);destination=ROOT/'frozen'/name
    destination.mkdir(parents=True,exist_ok=False);shutil.copytree(directory/'source',destination/'code');(destination/'configs').mkdir()
    config_path=destination/'configs'/config;shutil.copy2(ROOT/'configs'/config,config_path)
    if json.loads(config_path.read_text())!=freeze['configuration']:raise ValueError('Local configuration differs')
    for filename,expected in freeze['source_hashes'].items():
        if hashlib.sha256((destination/'code'/filename).read_bytes()).hexdigest()!=expected:raise ValueError(filename)
    previous=json.loads((ROOT/'INCUMBENT.json').read_text())
    freeze.update(version=name+'-validated-20260912',frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                  comparison=comparison,validation_replays=len(rows),validation_replay_actions=actions,
                  snapshot_run_id=selected[0]['run_id'])
    freeze_path=ROOT/'configs'/f'{name}_FREEZE.json';freeze_path.write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    incumbent=dict(status='validated',version=freeze['version'],configuration=str(config_path.relative_to(ROOT)).replace('\\','/'),
                   code_directory=str((destination/'code').relative_to(ROOT)).replace('\\','/'),
                   freeze=str(freeze_path.relative_to(ROOT)).replace('\\','/'),evidence=[str(folder.relative_to(ROOT)).replace('\\','/')],
                   previous=previous['version'])
    (ROOT/'INCUMBENT.json').write_text(json.dumps(incumbent,indent=2),encoding='utf-8');return incumbent


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('name','phase','baseline','candidate','config'):p.add_argument(n)
    a=p.parse_args();print(json.dumps(promote(**vars(a)),indent=2))
