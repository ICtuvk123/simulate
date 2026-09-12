"""Local-only Q4 runner with separate engine and feedback-only decision processes."""
import argparse
from datetime import datetime,timezone
import hashlib,json,multiprocessing,shutil,time,uuid
from pathlib import Path
from workers import engine_main,policy_main

ROOT=Path(__file__).resolve().parents[1]


def run_case(seed,config_path='configs/H0.json',scene=None,output_root=None,replay_check=False):
    config_path=Path(config_path)
    if not config_path.is_absolute():config_path=ROOT/config_path
    options=json.loads(config_path.read_text(encoding='utf-8'))
    config=dict(seed=seed,count=None,scenario='uniform',reception='mixed',error_mode='fixed_hash',source_mix='mixed',orientation='random')
    config.update(scene or {})
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]
    directory=Path(output_root or ROOT/'runs')/run_id;directory.mkdir(parents=True)
    source=directory/'source';source.mkdir();hashes={}
    for path in sorted((ROOT/'code').glob('*.py')):
        hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest();shutil.copy2(path,source/path.name)
    code_hash=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    manifest=dict(run_id=run_id,engine_configuration=config,policy_options=options,code_hash=code_hash,source_hashes=hashes)
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    context=multiprocessing.get_context('spawn');ep,ec=context.Pipe();pp,pc=context.Pipe()
    metadata=dict(run_id=run_id,mode='training',data_origin='local_q4',policy_options=options,code_hash=code_hash)
    engine=context.Process(target=engine_main,args=(ec,config));policy=context.Process(target=policy_main,args=(pc,options,str(directory/'requests.jsonl'),metadata))
    start=time.perf_counter();engine.start();ec.close();policy.start();pc.close()
    outcome=dict(error='no_policy_result',exited=False,wall_time=None);evaluation=None
    try:
        while True:
            if not pp.poll(5):
                if not policy.is_alive():raise RuntimeError('policy process stopped without summary')
                if time.perf_counter()-start>1210:raise TimeoutError('local runner wall limit')
                continue
            command=pp.recv()
            if command[0]=='action':
                ep.send(command)
                if not ep.poll(5):raise TimeoutError('engine response timeout')
                pp.send(ep.recv())
            elif command[0]=='done':outcome=command[1];break
        ep.send(('evaluation' if outcome['exited'] else 'abort',))
        if not ep.poll(10):raise TimeoutError('post-run evaluation timeout')
        evaluation=ep.recv()
    finally:
        if engine.is_alive():ep.send(('close',))
        for process in (policy,engine):
            process.join(5)
            if process.is_alive():process.terminate();process.join()
        pp.close();ep.close()
    from q3client import parse_journal
    from audit import postcheck,replay
    metrics=parse_journal(directory/'requests.jsonl',evaluation['jammer_count'] if outcome['exited'] else None)
    audit=postcheck(directory/'requests.jsonl',evaluation)
    events=evaluation['events'];no_signal=sum(e['response'].get('measure_result')=='no_signal' for e in events)
    roles={};fallbacks=0;current_role='other';seen=set()
    for line in (directory/'requests.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row.get('reason')=='q4_action_role':current_role=row['role']
        if row.get('reason')=='q4_fallback_begin':fallbacks+=1
        if row['event']=='response':
            response=json.loads(row['response_body']);rid=row['payload']['request_id']
            if response.get('accepted') and rid not in seen:
                seen.add(rid);roles[rid]=current_role
    role_cost={}
    for ev in [ev for es in metrics['per_channel_events'].values() for ev in es]:
        role=roles.get(ev['request_id'],'other');d=role_cost.setdefault(role,dict(actions=0,total_time=0.,move_time=0.,rf_time=0.,switch_time=0.,optical_time=0.,clear_time=0.))
        d['actions']+=1
        for a,b in [('move_time','move_time'),('rf_time','RF_detection_time'),('switch_time','channel_switch_time'),('optical_time','optical_time'),('clear_time','clear_time')]:d[a]+=ev[b];d['total_time']+=ev[b]
    metrics.update(seed=seed,version=options['version'],client_error=outcome['error'],engine_source_count=evaluation['jammer_count'],
                   evaluated_clear_ratio=evaluation['clear_ratio'],all_success=bool(outcome['exited'] and not outcome['error'] and metrics['completion_proved'] and audit['valid'] and evaluation['clear_ratio']==1),
                   mean_time_per_source=metrics['total_time']/evaluation['jammer_count'],no_signal_count=no_signal,
                   fallback_count=fallbacks,policy_wall_time_s=outcome['wall_time'],runner_wall_time_s=time.perf_counter()-start,
                   journal_bytes=(directory/'requests.jsonl').stat().st_size,role_cost=role_cost)
    (directory/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    (directory/'evaluation.json').write_text(json.dumps(evaluation,indent=2),encoding='utf-8')
    (directory/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    if replay_check and metrics['all_success']:
        replay_audit=replay(directory/'requests.jsonl')
        (directory/'feedback_replay.json').write_text(json.dumps(replay_audit,indent=2),encoding='utf-8')
    return directory,metrics


def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=1);p.add_argument('--config',default='configs/H0.json')
    p.add_argument('--scene',type=json.loads,default={});p.add_argument('--replay',action='store_true');args=p.parse_args()
    directory,m=run_case(args.seed,args.config,args.scene,replay_check=args.replay)
    print(json.dumps({k:m[k] for k in ['run_id','version','all_success','clear_count','engine_source_count','total_time','mean_time_per_source','no_signal_count','fallback_count','policy_wall_time_s','client_error']}))
    print(directory)
    return int(not m['all_success'])


if __name__=='__main__':
    multiprocessing.freeze_support();raise SystemExit(main())
