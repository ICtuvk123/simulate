"""Audit existing Q4 evidence and write a separate round-two results report.

Standard library only. Does not run a simulator, replay a policy, contact an
official endpoint, or overwrite the historical RESULTS_REPORT.md.
"""
import argparse,csv,hashlib,json,math,statistics,time
from datetime import datetime,timezone
from pathlib import Path

METRICS=['total_time','mean_time_per_source','policy_wall_time_s','move_time','RF_detection_time',
         'channel_switch_time','optical_time','clear_time','no_signal_count','optical_failed_count',
         'fallback_count','journal_bytes']
SUMMARY_MAP={'total_time':'mean_total','mean_time_per_source':'mean_per_source','policy_wall_time_s':'mean_wall',
             **{k:'mean_'+k for k in METRICS[3:]}}
ROLES={'development':'开发集','validation':'独立验证集','final':'最终保留测试集','holdout':'最终保留测试集',
       'final_holdout':'最终保留测试集','pressure':'压力测试集'}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def close(a,b,label,tol=1e-3):require(math.isfinite(a) and math.isfinite(b) and abs(a-b)<=tol,f'{label}: {a} != {b}')
def quantile(values,p=.95):
    values=sorted(values);i=(len(values)-1)*p;lo=int(i);hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(i-lo)
def stats(metrics):
    if not metrics:return dict(n=0,complete=0)
    result=dict(n=len(metrics),complete=sum(bool(m['all_success']) for m in metrics),
                p95=quantile([m['total_time'] for m in metrics]),worst=max(m['total_time'] for m in metrics))
    result.update({dest:statistics.mean(m[src] for m in metrics) for src,dest in SUMMARY_MAP.items()})
    return result


def registered_versions(reg):
    result={};provenance=reg['worker_provenance']
    for v in reg['variants']:
        workers=provenance[v] if isinstance(provenance,dict) else provenance
        require(bool(workers),f'No worker provenance for {v}')
        hashes=workers[0]['source_hashes']
        require(all(w['source_hashes']==hashes for w in workers),f'Worker code differs for {v}')
        configs=([dict(options=w['configuration'],sha256=w['config_sha256']) for w in workers]
                 if isinstance(provenance,dict) else [w['configurations'][v] for w in workers])
        require(all(c==configs[0] for c in configs),f'Worker configurations differ for {v}')
        result[v]=dict(hashes=hashes,options=configs[0]['options'],config_sha256=configs[0]['sha256'])
    return result


def audit_phase(root,phase,freeze,inc_options,variant=None):
    folder=(root/'reports'/phase).resolve();reg=read(folder/'registration.json');summary=read(folder/'summary.json')
    summary=summary.get('summary',summary);versions=registered_versions(reg)
    if variant is None:
        candidates=[v for v,s in versions.items() if s['hashes']==freeze['source_hashes'] and s['options']==inc_options]
        require(len(candidates)==1,f'Cannot uniquely identify incumbent variant in {phase}; pass --variant')
        variant=candidates[0]
    require(variant in versions,f'Unknown selected variant {variant}')
    require(versions[variant]['hashes']==freeze['source_hashes'],f'{phase}/{variant}: code is not current incumbent')
    require(versions[variant]['options']==inc_options and versions[variant]['config_sha256']==freeze['config_sha256'],
            f'{phase}/{variant}: configuration is not current incumbent')
    tasks=reg['tasks'];expected={(int(t['seed']),t['variant']) for t in tasks}
    require(len(expected)==len(tasks),'Duplicate registered tasks')
    seeds=list(reg['seeds']);require(len(seeds)==len(set(seeds)),'Duplicate registered seeds')
    require(expected=={(s,v) for s in seeds for v in reg['variants']},'Registration is not a complete paired design')
    rows=[json.loads(x) for x in (folder/'runs.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    require(len(rows)==len(expected),'Missing registered runs; refusing success-only report')
    independent=read(folder/'independent_exit_report.json')
    require(independent['runs']==len(expected),'Independent report has wrong run count')
    seen=set();by_variant={v:[] for v in reg['variants']};audits=[];indexed={};actions=0
    for row in rows:
        task=row['task'];key=(int(task['seed']),task['variant']);v=key[1]
        require(key in expected and key not in seen,'Unexpected or duplicate actual run');seen.add(key)
        require('metrics' in row,f'Missing metrics for {key}; cannot omit the run')
        m=row['metrics'];require(all(k in m for k in METRICS),f'Missing full-scene metrics for {key}')
        require(m.get('data_origin')=='local_q4',f'{key}: evidence is not the local Q4 distribution')
        for k in METRICS:require(isinstance(m[k],(int,float)) and math.isfinite(m[k]) and m[k]>=0,f'Invalid {key}/{k}')
        count=m.get('engine_source_count');require(type(count) is int and count>0,f'Missing post-run source count {key}')
        close(m['total_time']/count,m['mean_time_per_source'],f'{key}/per source')
        close(sum(m[k] for k in ('move_time','RF_detection_time','channel_switch_time','optical_time','clear_time')),m['total_time'],f'{key}/time accounting')
        directory=Path(row.get('directory') or Path(m['raw_log_path']).parent)
        if not directory.exists():directory=root/'runs'/row['run_id']
        manifest=read(directory/'manifest.json');expected_hashes=versions[v]['hashes']
        require(manifest['run_id']==row['run_id']==m['run_id'],f'{key}: run identity mismatch')
        require(manifest['source_hashes']==expected_hashes,f'{key}: actual source manifest differs from registration')
        require(manifest['policy_options']==versions[v]['options'],f'{key}: actual options differ')
        files={p.name:p for p in (directory/'source').glob('*.py')}
        require(set(files)==set(expected_hashes),f'{key}: actual source file list differs')
        for name,expected_hash in expected_hashes.items():require(sha(files[name])==expected_hash,f'{key}: changed source file {name}')
        journal=directory/'requests.jsonl';exit_check=read(directory/'independent_exit.json');replay=read(directory/'feedback_replay.json')
        require(exit_check.get('journal_sha256')==sha(journal),f'{key}: independent exit does not bind this journal')
        accepted={};clear_channels=set();last_time=0.
        for event in (json.loads(x) for x in journal.read_text(encoding='utf-8').splitlines() if x.strip()):
            if event.get('event')!='response' or event.get('http_status')!=200:continue
            response=json.loads(event['response_body'])
            if not response.get('accepted'):continue
            rid=event['payload']['request_id']
            if rid in accepted:continue
            accepted[rid]=response;last_time=response['virtual_time_s']
            if event['path']=='/clear' and response.get('clear_result')=='success':clear_channels.add(event['payload']['channel'])
        close(last_time,m['total_time'],f'{key}/last accepted time')
        require(len(clear_channels)==m['clear_count'],f'{key}/actual clear count mismatch')
        require(replay.get('actions')==len(accepted),f'{key}/replay action count mismatch')
        if m['all_success']:require(len(clear_channels)==count,f'{key}/success hides uncleared source')
        actions+=len(accepted);by_variant[v].append(m);indexed[key]=dict(metrics=m,task=task)
        audits.append(dict(seed=key[0],variant=v,run_id=row['run_id'],source_files_checked=len(files),
                           source_hash_match=True,source_matches_incumbent=(v==variant),
                           replay_valid=replay.get('valid') is True,independent_exit_valid=exit_check.get('valid') is True,
                           all_success=bool(m['all_success']),journal_sha256=exit_check['journal_sha256']))
    require(seen==expected,'Actual tasks differ from registration')
    require(independent['all_valid']==all(a['independent_exit_valid'] for a in audits),'Aggregate independent status differs from per-run checks')
    computed={v:stats(ms) for v,ms in by_variant.items()}
    for v,s in computed.items():
        require(summary[v]['n']==s['n'] and summary[v]['complete']==s['complete'],f'{v}/aggregate count mismatch')
        for k,value in s.items():
            if k not in ('n','complete'):close(value,summary[v][k],f'{v}/summary/{k}')
    # Reconcile the compact tabulation too; no row may disappear between files.
    with (folder/'paired_results.csv').open(encoding='utf-8-sig',newline='') as f:csv_rows=list(csv.DictReader(f))
    require(len(csv_rows)==len(expected),'CSV omits registered runs');csv_seen=set()
    for r in csv_rows:
        key=(int(r['seed']),r['variant']);require(key in indexed and key not in csv_seen,'Duplicate/unregistered CSV run');csv_seen.add(key)
        m=indexed[key]['metrics'];close(float(r['total_time']),m['total_time'],'CSV total');close(float(r['mean_time_per_source']),m['mean_time_per_source'],'CSV per source')
        if r.get('engine_source_count'):require(int(r['engine_source_count'])==m['engine_source_count'],'CSV source-count mismatch')
        require(r['all_success'].lower()==str(bool(m['all_success'])).lower(),'CSV success mismatch')
    comparisons=[]
    for file in sorted(folder.glob('comparison*.json')):
        c=read(file);a,b=c.get('baseline'),c.get('candidate')
        if a not in by_variant or b not in by_variant:continue
        require(c['pairs']==len(seeds) and c['all_registered_pairs_present'] is True,'Incomplete reported pairs')
        require(type(c['identical_worlds_verified']) is int and c['identical_worlds_verified']==len(seeds),'Pair world identity not verified')
        close(c['mean_per_source_baseline'],computed[a]['mean_per_source'],'comparison baseline')
        close(c['mean_per_source_candidate'],computed[b]['mean_per_source'],'comparison candidate')
        close(c['improvement_percent'],100*(1-computed[b]['mean_per_source']/computed[a]['mean_per_source']),'comparison improvement')
        close(c['p95_baseline'],computed[a]['p95'],'comparison baseline P95')
        close(c['p95_candidate'],computed[b]['p95'],'comparison candidate P95')
        require(c['all_success']==all(m['all_success'] for v in (a,b) for m in by_variant[v]),'Comparison success mismatch')
        comparisons.append(c)
    require(comparisons,'No completed paired comparisons')
    return dict(phase=phase,folder=folder,registration=reg,variant=variant,summary=computed,rows=indexed,
                audits=audits,comparisons=comparisons,actions=actions,
                all_verified=all(a['all_success'] and a['replay_valid'] and a['independent_exit_valid'] for a in audits))


def number(value):return '—' if value is None else f'{value:.3f}'
def summary_table(summary):
    lines=['| 方案 | 完整成功 | 成功率 | 平均每源 / s | 平均总时间 / s | 总时间 P95 / s | 最坏总时间 / s | 平均现实 / s |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for v,s in summary.items():lines.append(f'| {v} | {s["complete"]}/{s["n"]} | {100*s["complete"]/s["n"]:.1f}% | '+' | '.join(number(s[k]) for k in ('mean_per_source','mean_total','p95','worst','mean_wall'))+' |')
    return lines


def source_strata(phase):
    rows=[]
    for v in phase['summary']:
        counts=set(range(10,17))|{r['metrics']['engine_source_count'] for key,r in phase['rows'].items() if key[1]==v}
        for count in sorted(counts):
            group=[r['metrics'] for key,r in phase['rows'].items() if key[1]==v and r['metrics']['engine_source_count']==count]
            s=stats(group);rows.append(dict(phase=phase['phase'],variant=v,source_count=count,**s))
    return rows


def build(root,out,phase_name=None,variant=None,pressure_names=None):
    root=Path(root).resolve();out=Path(out).resolve();start=time.monotonic();generator_digest=sha(__file__)
    require(out.name!='RESULTS_REPORT.md','Historical RESULTS_REPORT.md may not be overwritten')
    inc=read(root/'INCUMBENT.json');freeze=read(root/inc['freeze']);options=read(root/inc['configuration'])
    require(sha(root/inc['configuration'])==freeze['config_sha256'],'Current frozen configuration hash mismatch')
    code=root/inc['code_directory'];files={p.name:p for p in code.glob('*.py')}
    require(set(files)==set(freeze['source_hashes']),'Current frozen source file list mismatch')
    for name,digest in freeze['source_hashes'].items():require(sha(files[name])==digest,'Current frozen source hash mismatch: '+name)
    selected=phase_name or Path(inc.get('final_evidence') or inc['evidence'][-1]).name
    selected_variant=variant or (inc.get('final_variant') if not phase_name and inc.get('final_evidence') else None)
    phase=audit_phase(root,selected,freeze,options,selected_variant)
    if pressure_names is None:
        prefix=Path(inc['code_directory']).parent.name
        pressure_names=[p.name for p in sorted((root/'reports').glob(prefix+'_pressure*')) if (p/'summary.json').exists()]
    pressure=[audit_phase(root,name,freeze,options) for name in pressure_names]
    role=phase['registration']['role'];is_final=role in ('final','holdout','final_holdout')
    lines=['# 第四问第二轮计算结果','',f'生成时间：{datetime.now(timezone.utc).isoformat()}。仅汇总已有实验，不执行模拟或官方接口。',
           '',f'当前冻结：**{inc["version"]}**；实际源码 `{freeze["commit"]}`；选中方案 `{phase["variant"]}`。',
           f'配置 `{inc["configuration"]}`，源码 `{inc["code_directory"]}`，逐文件哈希 `{inc["freeze"]}`。',
           '',f'当前证据：`reports/{selected}`，注册用途为 **{ROLES.get(role,role)}**，每方案注册 **{len(phase["registration"]["seeds"])}** 场。',
           ('本报告使用已实际完成的最终保留测试；不把此前开发结果合并进保留集。' if is_final else
            '当前报告使用已完成验证/开发证据，尚未以本报告声明本轮最终保留测试通过。'),
           '',f'逐局核验：{len(phase["audits"])} 局，{phase["actions"]} 个实际accepted动作；所有源文件实际字节与注册/冻结匹配。完整清除、反馈重放和独立退出全部通过：**{phase["all_verified"]}**。',
           '', '## 完整场景主结果','']+summary_table(phase['summary'])
    lines+=['','每源指标先在每场计算 T/实际源数，再对场景求算术平均；源数仅来自结束后的评估，不提供给策略。P95对整场总时间作线性插值。现实耗时为本机策略进程耗时，受并行负载影响；不等于行动时间或开发预算。',
            '', '## 行动时间与失败代价','',
            '| 方案 | 移动 / s | RF / s | 切频 / s | 光学 / s | 成功清除 / s | 无信号次数 | 光学失败次数 | 后备次数 | 平均日志字节 |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for v,s in phase['summary'].items():lines.append('| '+v+' | '+' | '.join(number(s['mean_'+k]) for k in METRICS[3:])+' |')
    lines+=['','严格记账 T=L/5+5N_RF+N_switch+3N_optical+2N_success。光学失败也付移动和3秒；清除不改变测向频道。按用途统计的成本是同一批秒数的另一种分类，不能再加一次。所有注册局均保留；失败的有效时间仍进入均值，不输出只含成功局的速度。若原始结果缺失，生成器报错而不静默略去。',
            '', '## 同世界配对比较','',
            '| 基线 → 候选 | 配对数 | 每源改善 | 总时间P95变化 | 配对95%改善区间 | 完整清除 | 数值门槛 |',
            '|---|---:|---:|---:|---|---|---|']
    for c in phase['comparisons']:
        ci=c['bootstrap_improvement_95_percent'];lines.append(f'| {c["baseline"]} → {c["candidate"]} | {c["pairs"]} | {c["improvement_percent"]:+.3f}% | {c["p95_change_percent"]:+.3f}% | [{ci[0]:+.3f}%, {ci[1]:+.3f}%] | {c["all_success"]} | {c["gate_passed"]} |')
    lines+=['','正的每源改善表示更快，正的P95变化表示尾部变慢。门槛为先完整正确，再平均每源至少改善1%、P95不恶化超过2%。比较报告的每个配对数和相同世界核验数均与注册一致；不能把不同种子集的均值称为配对。',
            '', '## 源数10–16分层（14个源可直接查行）','',
            '| 方案 | 源数 | 完整/场数 | 平均每源 / s | 平均总时间 / s | 总时间P95 / s | 最坏总时间 / s |',
            '|---|---:|---:|---:|---:|---:|---:|']
    strata=source_strata(phase)
    for s in strata:lines.append(f'| {s["variant"]} | {s["source_count"]} | {s["complete"]}/{s["n"]} | '+' | '.join(number(s.get(k)) for k in ('mean_per_source','mean_total','p95','worst'))+' |')
    lines+=['','该表来自主证据集结束后的实际源数，不新增场景，也不将源数反馈给决策器。各层样本数较小，尤其不能把14源子样本的均值当作稳定官方成绩；0场标为“—”，不填造数值。',
            '', '## 压力测试：混合、定向、全向分别报告','']
    if not pressure:lines.append('未发现与当前冻结源码和配置匹配的已完成压力阶段；不沿用旧版本压力成绩冒充当前成绩。')
    for p in pressure:
        lines += [f'### {p["phase"]}', '',f'注册 {len(p["registration"]["seeds"])} 场/方案，{len(p["audits"])} 次运行；逐局完整、重放、退出全部通过：{p["all_verified"]}。','']
        for mix,label in [('mixed','混合'),('directional','定向-only'),('omni','全向-only')]:
            group={v:stats([r['metrics'] for key,r in p['rows'].items() if key[1]==v and r['task'].get('scene',{}).get('source_mix','mixed')==mix]) for v in p['summary']}
            group={v:s for v,s in group.items() if s['n']}
            lines += [f'**{label}压力子集**','']+(summary_table(group) if group else ['无注册场景。'])+['']
        lines+=['压力场景包含边界向外辐射、发射角边界、1000/1500m半径、0/360度、聚集、10/16源、near、空频道等预设情况，精确组成见该阶段registration。该人工压力比例不称为官方分布，也不混入主验证均值。','']
    lines += ['## 隔离、分布假设与复用边界','',
              '主结果为自建本地场景分布假设，包含本地生成的位置、半径、源类型/朝向及固定空间误差；不是官方分布估计。引擎与策略隔离，有限假设仅用于候选排序，不能删除真实位置或证明空频道。相同位置反馈固定，不按调用次数重新抽取，不将重复测量当作独立噪声。',
              '普通开发500001–500030在LM、SML、IJ及其他消融中反复使用，运行次数不能累计为独立场景数；多次选择后的开发自举区间也不是独立验证。开发、验证、最终保留和压力结果分别报告。原始日志和快照应保留，下一轮不用本轮保留集做参数选择。',
              '', '## 官方记录与当前轮次','',
              '历史D_COMPACT曾在另行授权后完成一次官方问题4演练：13源，6813.204548s，每源524.092658s；原记录见reports/OFFICIAL_PRACTICE_RESULT.md。该记录不属于当前冻结版本的官方成绩，也不是官方平均水平。' if (root/'reports/OFFICIAL_PRACTICE_RESULT.md').exists() else '未找到可引用的历史官方演练记录。',
              '本轮当前算法证据中的官方演练0次、正式测试0次；本生成器没有网络接口或发起测试的功能，未消耗正式机会。',
              '', '## 下一轮边界与未证明事项','',
              '当前方案是有限模型、有限前瞻、启发式开放路线的已验证实现，不证明全局时间最优。更小定位域、更少RF、更少无信号或更少搜索站都不能替代完整场景时间；O、MR、MD等反例见R2_ACTION_FAILURES.md。新结构须独立登记开发、验证和保留种子，保留全部退步与失败局，先完整正确后谈速度。',
              '数学推导、连续数值覆盖证明、本地完整任务、官方演练及正式成绩分别陈述。当前数据不证明所有可能场景的成功概率为100%，观察到的完整率只适用于实际注册运行。',
              '', '## 证据与复现','',
              f'主来源：`reports/{selected}/registration.json`、`runs.jsonl`、`paired_results.csv`、`summary.json`、`comparison*.json`、`independent_exit_report.json`；每条原run的source/manifest/requests/feedback_replay/independent_exit均检查。',
              f'源数分层CSV：`{out.stem}_source_counts.csv`。逐局哈希和核验记录：`{out.stem}_audit.json`。',
              '本报告只重新计算和核对既有证据，不运行模拟；使用 python code/write_r2_results.py --root <仓库> --out <报告路径>，可用 --phase 和 --variant 指定已完成证据。最终阶段可选择best/H0/compact，其中best必须匹配当前incumbent冻结；其他臂逐条匹配其自己的注册源码，不能要求历史H0等于新版本源码。']
    require(sha(__file__)==generator_digest,'Generator changed during audit; rerun with fixed source')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    columns=['phase','variant','source_count','n','complete','mean_per_source','mean_total','p95','worst','mean_wall']
    with out.with_name(out.stem+'_source_counts.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,columns,extrasaction='ignore');writer.writeheader();writer.writerows(strata)
    record=dict(generated_utc=datetime.now(timezone.utc).isoformat(),root=str(root),incumbent=inc,
                phase=selected,variant=phase['variant'],registered_role=role,final_results=is_final,
                report_sha256=sha(out),generator_sha256=generator_digest,elapsed_s=time.monotonic()-start,
                phase_source_sha256={str(p):sha(p) for p in [phase['folder']/n for n in ('registration.json','runs.jsonl','paired_results.csv','summary.json','independent_exit_report.json')]},
                main_audits=phase['audits'],pressure_audits={p['phase']:p['audits'] for p in pressure})
    out.with_name(out.stem+'_audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(report=str(out),phase=selected,variant=phase['variant'],all_verified=phase['all_verified'],
                main_runs=len(phase['audits']),pressure_runs=sum(len(p['audits']) for p in pressure),elapsed_s=record['elapsed_s'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out',type=Path);parser.add_argument('--phase');parser.add_argument('--variant')
    parser.add_argument('--pressure-phase',action='append',dest='pressure');args=parser.parse_args()
    out=args.out or args.root/'reports/R2_RESULTS_REPORT.md'
    print(json.dumps(build(args.root,out,args.phase,args.variant,args.pressure),ensure_ascii=False))


if __name__=='__main__':main()
