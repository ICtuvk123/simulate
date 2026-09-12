"""Summarize frozen-policy, completed local trials; generate auditable figures."""
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

from benchmark import percentile
from runner import ROOT, oracle_bound
from geometry import open_held_karp

DEST = ROOT/'reports'/'optimization'


def read_csv(path):
    with path.open(encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_record(row):
    record = json.loads((ROOT/'runs'/row['run_id']/'result.json').read_text(encoding='utf-8'))
    assert record['evaluation']['events'][-1]['path']=='/exit'
    assert record['metrics']['clear_ratio']==1 and record['metrics']['completion_proved']
    assert not record['metrics']['accounting_warnings']
    return record


def diagnose(record):
    events = record['evaluation']['events']
    known,cleared,seen = set(),set(),set()
    counts = dict(search_RF=0,localization_RF=0,no_signal_RF=0,duplicate_same_point_RF=0,
                  optical_failures=0,RF_after_clear=0)
    clear_points = []
    for e in events:
        ch,p,response = e['channel'],e['position'],e['response']
        if e['path']=='/measure':
            counts['localization_RF' if ch in known else 'search_RF']+=1
            counts['RF_after_clear']+=int(ch in cleared)
            key = (ch,tuple(p))
            counts['duplicate_same_point_RF']+=int(key in seen)
            seen.add(key)
            if response['measure_result']=='no_signal':
                counts['no_signal_RF']+=1
            else:
                known.add(ch)
        elif e['path']=='/clear':
            if response['clear_result']=='success':
                cleared.add(ch)
                clear_points.append(p)
            else:
                counts['optical_failures']+=1
    direct = sum(math.dist(a,b) for a,b in zip([(0,0)]+clear_points,clear_points))
    _,best_fixed = open_held_karp((0,0),clear_points)
    counts.update(movement_outside_direct_clear_sequence_m=record['metrics']['move_distance']-direct,
                  hindsight_fixed_clear_order_excess_m=direct-best_fixed)
    return counts


def figures(summary, paired):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import HexColor
    pdfmetrics.registerFont(TTFont('OptimCJK','C:/Windows/Fonts/simhei.ttf'))
    folder = ROOT/'figures'
    c = canvas.Canvas(str(folder/'optimization_time_components.pdf'),pagesize=(560,280))
    c.setFont('OptimCJK',10)
    parts = [('move_time','移动','#2464eb'),('RF_detection_time','测向','#83a6ec'),
             ('channel_switch_time','切频','#b9a2df'),('optical_time','光学','#e6ab60'),
             ('clear_time','清除','#159977')]
    scale = 5000
    for tick in range(0,5001,1000):
        x=90+tick/scale*400
        c.setStrokeColor(HexColor('#e6eaf0'));c.line(x,65,x,207)
        c.setFillColor(HexColor('#425268'));c.drawCentredString(x,47,str(tick))
    for i,row in enumerate(summary):
        x,y=90,166-i*68
        c.setFillColor(HexColor('#24384e'));c.drawString(28,y+9,'旧策略 B' if i==0 else '优化策略 D')
        for key,_,color in parts:
            width=row['mean_'+key]/scale*400
            c.setFillColor(HexColor(color));c.rect(x,y,width,29,stroke=0,fill=1);x+=width
        c.setFillColor(HexColor('#24384e'));c.drawString(x+6,y+10,f"{row['mean_s']:.1f}")
    for i,(_,label,color) in enumerate(parts):
        x=90+i*78;c.setFillColor(HexColor(color));c.rect(x,238,9,7,stroke=0,fill=1)
        c.setFillColor(HexColor('#24384e'));c.drawString(x+14,236,label)
    c.drawCentredString(290,20,'独立验证：平均整局总行动时间（秒）');c.save()
    c=canvas.Canvas(str(folder/'optimization_paired_times.pdf'),pagesize=(520,370))
    c.setFont('OptimCJK',10)
    def xy(x,y):return 70+(x-1800)/3600*380,65+(y-1800)/3600*245
    c.setStrokeColor(HexColor('#acb7c4'));c.setDash(4,3);c.line(*xy(1800,1800),*xy(5400,5400));c.setDash()
    for tick in (2000,3000,4000,5000):
        x,y=xy(tick,tick);c.setFillColor(HexColor('#4b5c70'))
        c.drawCentredString(x,45,str(tick));c.drawRightString(58,y-3,str(tick))
    c.setFillColor(HexColor('#159977'))
    for row in paired:
        x,y=xy(row['B_s'],row['D_s']);c.circle(x,y,3.4,stroke=0,fill=1)
    c.setFillColor(HexColor('#24384e'));c.drawCentredString(265,20,'旧策略 B 总时间（秒）')
    c.saveState();c.translate(18,190);c.rotate(90);c.drawCentredString(0,0,'优化策略 D 总时间（秒）');c.restoreState()
    c.drawString(72,335,'20 个相同场景配对；虚线下方表示 D 更快');c.save()


def main():
    rows=read_csv(DEST/'final_validation_runs.csv')
    frozen=json.loads((DEST/'frozen_policy.json').read_text(encoding='utf-8'))
    first=next(r for r in rows if r['variant']=='frozen_D')
    frozen['validation_source_snapshot_hash']=first['strategy_hash']
    frozen['validation_parameter_hash']=first['parameter_hash']
    snapshot=ROOT/'runs'/first['run_id']/'source'
    frozen['policy_file_sha256']={name:hashlib.sha256((snapshot/name).read_bytes()).hexdigest()
                                 for name in ('optimized.py','local_geometry.py','policy_presets.py')}
    (DEST/'frozen_policy.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    paired,diagnostics=[],[]
    for seed in sorted({int(r['seed']) for r in rows}):
        selected={r['variant']:r for r in rows if int(r['seed'])==seed}
        b,d=load_record(selected['baseline_B']),load_record(selected['frozen_D'])
        assert b['evaluation']['sources']==d['evaluation']['sources'],'Paired worlds differ'
        bound=oracle_bound(d['evaluation'])['lower_bound_time']
        bt,dt=b['metrics']['total_time'],d['metrics']['total_time']
        paired.append(dict(seed=seed,B_s=bt,D_s=dt,saved_s=bt-dt,saved_percent=100*(bt-dt)/bt,
                           oracle_lower_bound_s=bound,gap_to_lower_bound=(dt-bound)/bound,
                           clear_count=d['metrics']['clear_count'],B_run_id=selected['baseline_B']['run_id'],
                           D_run_id=selected['frozen_D']['run_id']))
        for label,record in [('B',b),('D',d)]:
            diagnostics.append(dict(seed=seed,strategy=label,**diagnose(record)))
    write_csv(DEST/'validation_paired.csv',paired)
    write_csv(DEST/'action_diagnostics.csv',diagnostics)
    raw_summary=json.loads((DEST/'final_validation_summary.json').read_text(encoding='utf-8'))
    summary=sorted(raw_summary,key=lambda r:r['variant'])
    b,d=summary
    rng=random.Random(48761)
    bootstrap=[]
    for _ in range(10000):
        sampled=rng.choices(paired,k=len(paired))
        bootstrap.append(100*(sum(r['B_s'] for r in sampled)-sum(r['D_s'] for r in sampled))/sum(r['B_s'] for r in sampled))
    all_trials=[r for path in sorted(DEST.glob('round*_runs.csv')) for r in read_csv(path)]+rows+read_csv(DEST/'final_stress_runs.csv')
    summary_result=dict(validation_cases=len(paired),mean_B_s=b['mean_s'],mean_D_s=d['mean_s'],
                        improvement_percent=100*(b['mean_s']-d['mean_s'])/b['mean_s'],
                        paired_bootstrap_95_percent_interval=[percentile(bootstrap,.025),percentile(bootstrap,.975)],
                        cases_faster=sum(r['D_s']<r['B_s'] for r in paired),all_cases_cleared=True,
                        mean_oracle_lower_bound_s=statistics.mean(r['oracle_lower_bound_s'] for r in paired),
                        tested_runs=len(all_trials),all_recorded_runs_pass=all(r['clear_ratio']=='1.0' and r['completion_proved']=='True' and not r['client_error'] for r in all_trials))
    (DEST/'FINAL_SUMMARY.json').write_text(json.dumps(summary_result,indent=2),encoding='utf-8')
    history=[]
    for path in sorted(DEST.glob('round*_summary.json')):
        for item in json.loads(path.read_text(encoding='utf-8')):
            history.append(dict(phase=path.stem.replace('_summary',''),**item))
    write_csv(DEST/'leaderboard.csv',history)
    figures(summary,paired)
    # A median final-validation case is chosen for illustration, not the fastest.
    demo=sorted(paired,key=lambda r:r['D_s'])[len(paired)//2]
    record=json.loads((ROOT/'runs'/demo['D_run_id']/'result.json').read_text(encoding='utf-8'))
    html=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
    encoded=json.dumps(record,ensure_ascii=False).replace('<','\\u003c')
    (DEST/'optimized_replay.html').write_text(html.replace('const EMBEDDED = null;','const EMBEDDED = '+encoded+';',1),encoding='utf-8')
    table='\n'.join(f"| {'B' if r['variant']=='baseline_B' else 'D'} | {r['mean_s']:.2f} | {r['median_s']:.2f} | {r['p90_s']:.2f} | {r['p95_s']:.2f} | {r['worst_s']:.2f} |" for r in summary)
    components='\n'.join(f"| {label} | {b['mean_'+key]:.2f} | {d['mean_'+key]:.2f} | {b['mean_'+key]-d['mean_'+key]:.2f} |" for key,label in [('move_time','移动'),('RF_detection_time','测向'),('channel_switch_time','切频'),('optical_time','光学'),('clear_time','清除')])
    diag={label:{key:statistics.mean(r[key] for r in diagnostics if r['strategy']==label) for key in diagnostics[0] if key not in ('seed','strategy')} for label in ('B','D')}
    (DEST/'diagnostics_summary.json').write_text(json.dumps(diag,indent=2),encoding='utf-8')
    stress=json.loads((DEST/'final_stress_summary.json').read_text(encoding='utf-8'))
    feasibility=json.loads((DEST/'feasibility.json').read_text(encoding='utf-8'))
    report=f'''# 第三问本地优化结果

本报告只统计自建模拟器实验。另行授权的一次官方问题 3 演练已完成：案例 2FAG-SXMQ-WU2S-CXJF，12/12 清除，3219.820373 秒，日志独立保存在项目 training_logs，不混入本报告统计。没有进行正式测试。环境物理、源数量、移动速度和动作费用没有改变。所有时间为完成整局任务的虚拟秒数，含移动、测向、换频道、失败光学尝试和成功清除；不是电脑计算时间或单源分摊时间。

## 可达性与停止原因

原 12 个已结束案例的完美信息下界平均 {feasibility['mean_oracle_lower_bound_s']:.2f} 秒，最小 {feasibility['minimum_oracle_lower_bound_s']:.2f} 秒。因此这些案例的平均 200–300 秒不可达。本次独立验证的相应下界均值为 {summary_result['mean_oracle_lower_bound_s']:.2f} 秒。下界是在运行结束后用自建真值计算，未进入控制器。

下界计算：起点边权 max(0,‖gᵢ‖−20)，源间边权 max(0,‖gᵢ−gⱼ‖−40)，对这些边权求开放 Held–Karp 最小路长，除以 5 后加每源 5 秒。独立边的最小值可能不能同时实现，所以这是乐观松弛下界，不能声称已经走出了这条真实路线。

对于本地采用的独立面积均匀分布，固定 n 个源时 E[max‖gᵢ‖]=1800·2n/(2n+1)。仅到达最远源并加必要光学/清除费用，n=10 时平均已至少 388.86 秒。该分布论证不适用于所有任意聚集场景，也没有把本地分布说成官方分布。

本轮交付经过多轮比较的训练胜出配置和独立验证结果。目标时间低于下界，不能通过继续调参实现。D 仍高于完美信息下界，尚未证明全局最优，也没有把有限参数搜索当成统计平台期证明。

## 决策采用的信息

控制器只接收 enter、measure、clear、exit 的合法响应。真实源存在环境子进程，评估器只在控制器结束后读取。种子仅交给环境生成器；控制器没有种子或真实源总数参数。当前定位区域由目标圆、1500 米接收上界和 ±1.01°保守扇区交集得到。

局部选测站时使用当前多边形构造假设位置，枚举 −1.005°、0、+1.005°测向误差，比较移动+RF+估计剩余费用。这是有限求积的时间启发式，不是连续 P20/J∞ 全局优化证明，也不是读取真值。实际清除必须通过几何条件或得到已计费的成功光学反馈。

纯反馈重放见 `feedback_only_audit.json` 与 `final_feedback_only_audit.json`：重放时没有加载场景生成器或真值文件，决策期间禁止文件、网络及新进程访问，逐个核对动作。该审计核验当前代码行为，不声称 Python 是防恶意反射的安全沙箱。

## 冻结与独立验证

101–104 为初步训练，301–308 为扩展训练。各轮清单在运行前保存。2001–2020 在参数冻结后用于最终配对验证，未根据结果调参。压力案例 901–904 包含边界、聚集、1000 米接收半径和极端误差。

20 个独立案例中 B、D 均全部清除且通过独立完成证书。D 在 {summary_result['cases_faster']} 个案例中更快，平均减少 {summary_result['improvement_percent']:.2f}%；配对重采样的 95% 区间为 {summary_result['paired_bootstrap_95_percent_interval'][0]:.2f}%–{summary_result['paired_bootstrap_95_percent_interval'][1]:.2f}%，只描述此本地抽样实验。

| 策略 | 均值 | 中位数 | P90 | P95 | 最坏 |
| --- | ---: | ---: | ---: | ---: | ---: |
{table}

| 时间组成 | B | D | 减少秒数 |
| --- | ---: | ---: | ---: |
{components}

压力案例：{json.dumps(stress,ensure_ascii=False)}。

## 多余动作与改进判断

固定覆盖全部结束后再清除，会让搜索路径与清除路径分离。D 把已发现目标和待完成的覆盖站共同规划，并在每次反馈后重排。扫描圆环从 1300 米缩至经过几何验证的 1130 米，减少专门搜索路程。无需返航。

完全删除顺路测向会增加后面的定位移动，实验中反而变慢。因此使用信息收益筛选，只在有足够角度差异、预计区域明显缩小时测量；一旦可保证清除就不继续追求更小半径。

可清除集合为 K=∩ᵥ B(v,20)，v 遍历保守多边形顶点。进入 K 的最近可行点即可，不必访问估计中心。局部补测使用候选测站的剩余时间比较；小区域可先尝试一次光学，失败费用仍计入总时间，随后回到保守定位流程。

独立验证中，相同频道、完全相同位置的重复 RF 均值为 B={diag['B']['duplicate_same_point_RF']:.2f}、D={diag['D']['duplicate_same_point_RF']:.2f}；D 已清频道重复 RF 均值 {diag['D']['RF_after_clear']:.2f}。失败光学均值 {diag['D']['optical_failures']:.2f} 次，未从费用中删除。

`action_diagnostics.csv` 还记录了搜索/定位 RF 分类，以及事后固定清除位置的路径差。事后路径差不能直接称为当时可避免的路程：在线算法当时并不知道未来源位置，搜索与定位本身必须移动。

## 产物与复现

- `leaderboard.csv`：全部训练候选及时间分解，慢方案仍保留。
- `round*_manifest.json`、`round*_runs.csv`：逐轮参数与运行索引。
- `frozen_policy.json`：最终参数与代码指纹；通过标准界面选择 D 可复现。
- `validation_paired.csv`：相同场景的 B/D 时间、改进、事后下界和日志位置。
- `action_diagnostics.csv`：逐局动作诊断。
- `optimized_replay.html`：验证组时间中位附近的示例全过程，未挑最快案例。
- `../../figures/optimization_time_components.pdf`、`optimization_paired_times.pdf`：验证分项柱图与配对散点图，数据来自上述 CSV。
- 全部动作原始日志、独立代码快照在 `runs/<run_id>/`。

当前报告纳入 {summary_result['tested_runs']} 次完整本地运行；全部记录通过：{summary_result['all_recorded_runs_pass']}。核心模拟器只依赖 Python 标准库，图表生成额外使用 reportlab。运行 `python simulator.py run --strategy D --seed 2001` 可执行最终配置；`python simulator.py test` 检查物理与几何规则。
'''
    (DEST/'RESULTS_REPORT.md').write_text(report,encoding='utf-8')
    print(json.dumps(summary_result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
