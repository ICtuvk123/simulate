"""Re-execute one recorded local scene using its exact archived policy bytes.

Scene configuration is passed only to the evaluator/engine; the policy gets
the same guarded feedback interface as normal frozen runs. This is an explicit
reproduction, never an additional independent experiment.
"""
import argparse,csv,hashlib,json,subprocess,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def safe_run(run_id):
    path=(ROOT/'runs'/run_id).resolve()
    if path.parent!=(ROOT/'runs').resolve():raise ValueError('Expected one local run identifier')
    return path


def signature(path):
    records=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    return [(r['path'],{k:v for k,v in r['payload'].items() if k not in ('request_id','robot_id')})
            for r in records if r['event']=='request']


def reproduce(run_id):
    original=safe_run(run_id);manifest=json.loads((original/'manifest.json').read_text())
    if not manifest.get('engine_configuration'):raise ValueError('Only self-written local scenes are supported')
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    destination=ROOT/'reproductions'/name;source=destination/'snapshot'/'code';source.mkdir(parents=True,exist_ok=False)
    for filename,digest in manifest['source_hashes'].items():
        if Path(filename).name!=filename or not filename.endswith('.py'):raise ValueError('Invalid archived source name')
        archived=original/'source'/filename
        if not archived.is_file():archived=ROOT/'source_objects'/digest
        data=archived.read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Archived source hash mismatch: '+filename)
        (source/filename).write_bytes(data)
    config=destination/'policy.json';config.write_text(json.dumps(manifest['policy_options']),encoding='utf-8')
    engine=dict(manifest['engine_configuration']);seed=engine.pop('seed')
    receipt=dict(original_run_id=run_id,role='reproduction',seed=seed,new_independent_scenes=0,
                 source_hashes=manifest['source_hashes'],utc=datetime.now(timezone.utc).isoformat())
    (destination/'registration.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as stream:
        csv.writer(stream).writerow(['reproduce_'+name,'reproduction',seed,manifest['policy_options']['version'],'','registered_original_scene'])
    output=destination/'result.json'
    command=[sys.executable,str(ROOT/'code/snapshot_case.py'),'--snapshot',str(source.parent),
             '--config',str(config),'--seed',str(seed),'--scene',json.dumps(engine),
             '--run-root',str(ROOT/'runs'),'--output',str(output)]
    process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if not output.is_file():raise RuntimeError(process.stderr[-8000:])
    result=json.loads(output.read_text());new=safe_run(result['run_id'])
    before=json.loads((original/'evaluation.json').read_text());after=json.loads((new/'evaluation.json').read_text())
    from independent_exit import verify
    independent=verify(new/'requests.jsonl')
    (new/'independent_exit.json').write_text(json.dumps(independent,indent=2),encoding='utf-8')
    replay=json.loads((new/'feedback_replay.json').read_text())
    answer=dict(**receipt,reproduced_run_id=result['run_id'],complete=result['metrics']['all_success'],
                same_sources=before['sources']==after['sources'],
                identical_actions=signature(original/'requests.jsonl')==signature(new/'requests.jsonl'),
                feedback_replay_valid=replay['valid'],independent_exit_valid=independent['valid'],
                total_time=result['metrics']['total_time'])
    answer['valid']=all(answer[k] for k in ('complete','same_sources','identical_actions','feedback_replay_valid','independent_exit_valid'))
    (destination/'comparison.json').write_text(json.dumps(answer,indent=2),encoding='utf-8')
    checks=ROOT/'reports'/'REPRODUCTION_CHECKS';checks.mkdir(exist_ok=True)
    (checks/(name+'.json')).write_text(json.dumps(answer,indent=2),encoding='utf-8')
    with (ROOT/'SEEDS.csv').open('a',newline='',encoding='utf-8') as stream:
        csv.writer(stream).writerow(['reproduce_'+name,'reproduction',seed,manifest['policy_options']['version'],result['run_id'],'complete' if answer['valid'] else 'failed'])
    return answer


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');args=p.parse_args()
    result=reproduce(args.run_id);print(json.dumps(result,indent=2));raise SystemExit(0 if result['valid'] else 1)
