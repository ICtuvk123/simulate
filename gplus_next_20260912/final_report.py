"""Data-derived paired figures and a concise Chinese experiment report."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parent


def read(phase,name):
    return json.loads((ROOT/'reports'/phase/name).read_text(encoding='utf-8'))


def main():
    frozen=json.loads((ROOT/'FREEZE_NEXT.json').read_text())
    name=frozen['candidate']['name']
    for file,digest in frozen['code_sha256'].items():
        assert hashlib.sha256((ROOT/'code'/file).read_bytes()).hexdigest()==digest
    baseline_freeze=json.loads((ROOT/'BASELINE_FREEZE.json').read_text())
    for file,digest in baseline_freeze['experiment_files_sha256'].items():
        assert hashlib.sha256((ROOT.parent/'time_push_20260912/code'/file).read_bytes()).hexdigest()==digest
        assert hashlib.sha256((ROOT/'code'/file).read_bytes()).hexdigest()==digest
    assert (ROOT/'BASELINE_candidate.json').read_bytes()==(ROOT.parent/'time_push_20260912/candidate.json').read_bytes()
    comparison=read('validation100','comparison.json')[0]
    stress=read('stress24','comparison.json')[0]
    summaries={r['variant']:r for r in read('validation100','summary.json')}
    rows=list(csv.DictReader((ROOT/'reports/validation100/runs.csv').open(encoding='utf-8-sig')))
    groups={}
    for r in rows:groups.setdefault(r['variant'],{})[r['seed']]=r
    base,chosen=groups['Gplus'],groups[name]
    pairs=[]
    for seed in sorted(base,key=int):
        b,c=base[seed],chosen[seed]
        assert b['scene_hash']==c['scene_hash']
        pair=dict(seed=int(seed),count=int(c['clear_count']),baseline_run_id=b['run_id'],candidate_run_id=c['run_id'],
            baseline=float(b['average_localization_clear_time_s_per_source']),
            candidate=float(c['average_localization_clear_time_s_per_source']))
        pair['saved']=pair['baseline']-pair['candidate']
        for term in ('move_time','RF_detection_time','channel_switch_time','optical_time','clear_time','total_time'):
            pair['saved_'+term]=float(b[term])-float(c[term])
        assert abs(sum(pair['saved_'+t] for t in ('move_time','RF_detection_time','channel_switch_time','optical_time','clear_time'))
                   -pair['saved_total_time'])<.004
        pairs.append(pair)
    output=ROOT/'reports/validation_paired.csv'
    with output.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(pairs[0]));writer.writeheader();writer.writerows(pairs)
    from draw_results import draw
    draw(pairs,ROOT)
    audits=[read(p,'feedback_only_audit.json') for p in ('validation100','stress24')]
    assert [a['runs'] for a in audits]==[200,48]
    assert all(a['all_pass'] and a['actions']>0 for a in audits)
    assert len(pairs)==100 and comparison['n']==100 and stress['n']==24
    entry=json.loads((ROOT/'reports/entrypoint_check.json').read_text())
    assert entry['all_pass'] and entry['successful_cli_checks']==2
    passed=(comparison['all_pass'] and stress['all_pass'] and all(a['all_pass'] for a in audits)
            and all(r['all_pass'] for r in summaries.values())
            and comparison['saved_s_per_source_ci95'][0]>0 and comparison['saved_s_per_scene']>0)
    total=sum(len(list(csv.DictReader(p.open(encoding='utf-8-sig'))))
              for p in (ROOT/'reports').glob('*/runs.csv'))
    records=dict(version=frozen['version'],selected_candidate=name,promoted_locally=passed,
        total_local_runs=total+entry['additional_local_runs'],main_experiment_runs=total,
        additional_entrypoint_runs=entry['additional_local_runs'],comparison=comparison,stress_comparison=stress,
        local_summaries=summaries,feedback_replayed_runs=sum(a['runs'] for a in audits),
        feedback_replayed_actions=sum(a['actions'] for a in audits),original_Gplus_unchanged=True,
        official_tests_run=False,figure_data='reports/validation_paired.csv')
    (ROOT/'reports/SUMMARY.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    bsum,csum=summaries['Gplus'],summaries[name]
    screen=read('screen16','comparison.json');development=read('development40','comparison.json')
    lines=['# G+ 进一步优化：本地实测结果','',
        '## 结论','',
        ('新候选通过本轮本地晋级条件。' if passed else '当前候选未满足预登记的晋级条件，继续保留冻结 G+ 为推荐版本。'),
        f"本轮候选为 **{name}**，版本 `{frozen['version']}`。独立100对场景的平均时间由 **{comparison['baseline_s_per_source']:.6f} 变为 {comparison['candidate_s_per_source']:.6f} 秒/源**，本批样本平均节省 **{comparison['saved_s_per_source']:.6f} 秒/源（{comparison['saved_percent']:.3f}%）**。",
        f"配对bootstrap 10,000次的95%区间为 **[{comparison['saved_s_per_source_ci95'][0]:.6f}, {comparison['saved_s_per_source_ci95'][1]:.6f}] 秒/源**。{comparison['wins']}胜、{comparison['losses']}负、{comparison['ties']}平；最大单场退步 {comparison['worst_regression_s_per_source']:.6f} 秒/源。",'',
        ('独立验证的节省区间下界为正，达到本轮预登记阈值。' if passed else '独立验证的节省区间跨零：本批均值略快，但尚不能确认稳定提速，不能据此宣布优化成功。'),'',
        '## 实际改动与未采用方向','',
        '用户建议中的固定半径正负联立、全历史接收安全、保证清除区域及通过停靠点，原 G+ 已经实现。新代码分别研究序贯光学终端、补测后的剩余路线估计、较多任务时的路线次序邻域优化；模型细节见 [ANALYSIS_MODELING_REPORT.md](ANALYSIS_MODELING_REPORT.md)。',
        '序贯光学的第二次清除使用保守残余区域顶点证书。面积比例只给动作打分；只有收到真实失败后才更新区域。路线次序优化只保证当前固定锚点代理路长不增，不保证全场必快。未来路线补测评分保留原候选和接收证明。',
        '所有开发阶段结果（正值为节省，负值为变慢）：','',
        '|阶段|候选|场景数|平均节省/秒每源|完整通过|','|---|---|---:|---:|---|']
    for phase,data in [('初筛16',screen),('开发40',development)]:
        for row in data:lines.append(f"|{phase}|{row['variant']}|{row['n']}|{row['saved_s_per_source']:.6f}|{row['all_pass']}|")
    lines+=['','开发场景用于选型，其区间不能当最终独立证据。选型后冻结参数和所有源文件，再运行22001–22100的独立验证，未根据验证结果改参数。',
        '', '## 每局分项时间','', '|分项|G+ /秒|新候选/秒|节省/秒|','|---|---:|---:|---:|']
    for term,label in [('move_time','移动'),('RF_detection_time','RF'),('channel_switch_time','切频'),('optical_time','光学'),('clear_time','清除'),('total_time','总行动时间')]:
        bv,cv=bsum['mean_'+term],csum['mean_'+term]
        lines.append(f'|{label}|{bv:.6f}|{cv:.6f}|{bv-cv:.6f}|')
    lines+=['','本轮每局移动减少6.336秒，但射频、切频、光学分别增加0.900、0.410、1.830秒，净节省仅3.196秒。额外探测开销抵消了约一半移动收益。开发阶段的未来路线测站评分同样出现额外射频开销，未进入最终验证。',
        '继续争取大幅下降，需要让测站和清除动作的评分更准确地估计剩余任务的完整成本，尤其是失败光学后的代价与清除出口位置对后续路线的影响。本轮的有限后续路线近似没有证明这一方向能稳定改善；以上是后续研究方向，不是已取得的效果。']
    lines += ['',f"平均程序运行耗时（六进程实验负载下）：G+ {bsum['mean_measured_program_wall_time_s']:.3f} 秒，新候选 {csum['mean_measured_program_wall_time_s']:.3f} 秒；该耗时不计入行动时间。",'',
        '## 压力测试与审计','',
        f"24对压力场景：平均时间 {stress['baseline_s_per_source']:.6f} → {stress['candidate_s_per_source']:.6f} 秒/源，节省区间 [{stress['saved_s_per_source_ci95'][0]:.6f}, {stress['saved_s_per_source_ci95'][1]:.6f}] 秒/源；{stress['wins']}胜、{stress['losses']}负、{stress['ties']}平。完整通过：{stress['all_pass']}。压力集为异质极端场景，不代表官方场景分布。",
        f"主实验记录共 {total} 次本地运行（含环境复现），另有 {entry['additional_local_runs']} 次入口测试。最终独立验证和压力集共 {sum(a['runs'] for a in audits)} 次仅反馈重放、{sum(a['actions'] for a in audits)} 个动作逐个一致。重放期间不加载引擎或读取源真值，并禁止磁盘、网络与进程访问。",
        '每局核对同物理场景哈希、全部清除、退出证明、逐次记录的区域更新均保留真值，以及移动/RF/切频/光学/清除总账。区域真值仅由退出后的审计读取，控制器不读取真值。新增21项几何/决策测试通过。',
        '从其他工作目录运行新候选和 G+ 的本地入口，均复现 seed 22001 的独立验证结果，并验证离线 HTML 内嵌的是对应变体和结果。记录见 entrypoint_check.json。',
        '', '## 文件与复现','',
        '- [配对图表](../figures/Gplus_next_validation.pdf)：同场景散点、全量排序差异；计时分解见上表。',
        '- [图表对应逐场数据](validation_paired.csv)、[汇总JSON](SUMMARY.json)。',
        '- `validation100/`、`stress24/`：manifest、逐场表、配对统计与仅反馈审计。',
        '- `../candidate.json`、`../FREEZE_NEXT.json`：测试选择与冻结哈希；完整原始动作及源码快照在 `../runs/`。',
        '- `python run_candidate.py --seed 22001` 运行新候选；追加 `--baseline` 运行冻结 G+。',
        '', '本轮仅在独立本地模拟器测试，未运行新的官方演练或正式测试。结果支持的范围仅为所列本地场景与假设，不能承诺每场更快或达到全局最优。原 G+ 与先前提取包保持不变。']
    (ROOT/'reports/RESULTS_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in records.items() if k!='local_summaries'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
