"""Post-run only: aggregate paired smoke evidence and independently audit exits."""
import csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'code'))
from experiment import summarize
from independent_exit import verify

def main(folder,baseline='D24'):
    folder=Path(folder);rows=[json.loads(l) for l in (folder/'runs.jsonl').read_text(encoding='utf-8').splitlines()]
    tasks=json.loads((folder/'job.json').read_text(encoding='utf-8'))['tasks']
    assert len(rows)==len(tasks)
    checks=[];worlds={};replays=[];same=True;counts={}
    for r in rows:
        d=Path(r['directory']);check=verify(d/'requests.jsonl')
        (d/'independent_exit.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
        checks.append(dict(seed=r['task']['seed'],variant=r['task']['variant'],run_id=r['run_id'],**check))
        replays.append(json.loads((d/'feedback_replay.json').read_text(encoding='utf-8'))['valid'])
        evaluation=json.loads((d/'evaluation.json').read_text(encoding='utf-8'))
        manifest=json.loads((d/'manifest.json').read_text(encoding='utf-8'))
        fingerprint=(evaluation['sources'],manifest['engine_configuration'],manifest['source_hashes']['q4engine.py'])
        seed=r['task']['seed'];same &= seed not in worlds or worlds[seed]==fingerprint;worlds[seed]=fingerprint
        variant=r['task']['variant'];counts.setdefault(variant,{})
        for line in (d/'requests.jsonl').read_text(encoding='utf-8').splitlines():
            reason=json.loads(line).get('reason','')
            if reason.startswith('q4_') and reason.endswith('_clip'):counts[variant][reason]=counts[variant].get(reason,0)+1
    result=summarize(rows)
    result['comparison']=dict(all_complete=all(r['metrics']['all_success'] for r in rows),
                             all_independent_exit_valid=all(c['valid'] for c in checks),
                             all_feedback_replay_valid=all(replays),same_world_and_fixed_error_engine=same,
                             not_promotion_evidence=True,contraction_events=counts)
    for variant in result.keys()-{baseline,'comparison'}:
        result['comparison'][variant]={f'mean_per_source_improvement_over_{baseline}':1-result[variant]['mean_per_source']/result[baseline]['mean_per_source'],'p95_change':result[variant]['p95']/result[baseline]['p95']-1}
    (folder/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (folder/'independent_exit_report.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    fields=['seed','variant','run_id','all_success','engine_source_count','total_time','mean_time_per_source','no_signal_count','optical_failed_count','fallback_count','policy_wall_time_s','journal_bytes']
    with (folder/'paired_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in rows:writer.writerow({k:r['task']['seed'] if k=='seed' else r['task']['variant'] if k=='variant' else r['run_id'] if k=='run_id' else r['metrics'][k] for k in fields})
    print(json.dumps({k:{key:value for key,value in v.items() if key in ('n','complete','mean_per_source','mean_total','p95','worst','mean_wall','mean_journal_bytes')} if k!='comparison' else v for k,v in result.items()},indent=2))

if __name__=='__main__':main(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else 'D24')
