"""Audited results, paired data, vector chart, and a representative replay."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics as st

ROOT=Path(__file__).resolve().parent


def rows(phase):
    return list(csv.DictReader((ROOT/'reports'/phase/'runs.csv').open(encoding='utf-8-sig')))


def percentile(values,p):
    a=sorted(values);i=(len(a)-1)*p;lo=int(i)
    return a[lo]+(a[min(lo+1,len(a)-1)]-a[lo])*(i-lo)


def draw(pairs):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import HexColor
    pdfmetrics.registerFont(TTFont('Chinese','C:/Windows/Fonts/simhei.ttf'))
    folder=ROOT/'figures';folder.mkdir(exist_ok=True)
    c=canvas.Canvas(str(folder/'Gplus_validation.pdf'),pagesize=(960,430))
    c.setTitle('G 与 G+ 的 100 场独立配对验证')
    low=20*math.floor(min(min(p['G_s_per_source'],p['Gplus_s_per_source']) for p in pairs)/20)-20
    high=20*math.ceil(max(max(p['G_s_per_source'],p['Gplus_s_per_source']) for p in pairs)/20)+20
    x0,y0,w,h=65,70,345,300
    def px(v):return x0+w*(v-low)/(high-low)
    def py(v):return y0+h*(v-low)/(high-low)
    for v in range(low,high+1,40):
        c.setStrokeColor(HexColor('#d8dee8'));c.line(px(v),y0,px(v),y0+h);c.line(x0,py(v),x0+w,py(v))
        c.setFillColor(HexColor('#475569'));c.setFont('Chinese',10)
        c.drawCentredString(px(v),y0-16,str(v));c.drawRightString(x0-8,py(v)-3,str(v))
    c.setStrokeColor(HexColor('#94a3b8'));c.setDash(3,3);c.line(px(low),py(low),px(high),py(high));c.setDash()
    for p in pairs:
        c.setFillColor(HexColor('#15806a' if p['saved_s_per_source']>=0 else '#cb6c26'))
        c.circle(px(p['G_s_per_source']),py(p['Gplus_s_per_source']),2.4,stroke=0,fill=1)
    c.setFillColor(HexColor('#172b45'));c.setFont('Chinese',12)
    c.drawCentredString(x0+w/2,25,'G 平均定位清除时间（秒/源）')
    c.saveState();c.translate(18,y0+h/2);c.rotate(90);c.drawCentredString(0,0,'G+ 平均定位清除时间（秒/源）');c.restoreState()
    x0,w=540,350
    ordered=sorted(p['saved_s_per_source'] for p in pairs)
    step=5;bottom=step*math.floor(min(0,min(ordered))/step)-step;top=step*math.ceil(max(0,max(ordered))/step)+step
    def y(v):return y0+h*(v-bottom)/(top-bottom)
    for v in range(bottom,top+1,step):
        c.setStrokeColor(HexColor('#d8dee8'));c.setFillColor(HexColor('#475569'));c.setFont('Chinese',10)
        c.line(x0,y(v),x0+w,y(v));c.drawRightString(x0-8,y(v)-3,str(v))
    c.setStrokeColor(HexColor('#475569'));c.line(x0,y(0),x0+w,y(0))
    for i,v in enumerate(ordered):
        c.setFillColor(HexColor('#15806a' if v>=0 else '#cb6c26'))
        c.rect(x0+i*w/len(ordered),y(min(v,0)),w/len(ordered)-.5,abs(y(v)-y(0)),fill=1,stroke=0)
    c.setFillColor(HexColor('#172b45'));c.setFont('Chinese',12)
    c.drawCentredString(x0+w/2,25,'按节省时间排序的 100 个配对场景')
    c.saveState();c.translate(485,y0+h/2);c.rotate(90);c.drawCentredString(0,0,'G 减 G+ 的时间（秒/源）');c.restoreState()
    c.setFont('Chinese',11);c.drawString(65,400,'每点是同一个场景；虚线为等时线')
    c.drawString(540,400,'绿色：G+ 更快；橙色：G+ 更慢')
    c.save()


def main():
    freeze=json.loads((ROOT/'FREEZE.json').read_text())
    for name,digest in freeze['experiment_files_sha256'].items():
        assert hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()==digest,name
    for name,digest in freeze['baseline_files_sha256'].items():
        assert hashlib.sha256((ROOT.parent/'local_simulator/code'/name).read_bytes()).hexdigest()==digest,name
    allrows=rows('validation100');assert len(allrows)==200
    groups={name:{r['seed']:r for r in allrows if r['variant']==name} for name in ('G','Gplus')}
    pairs=[]
    for seed in sorted(groups['G']):
        g,h=(groups[n][seed] for n in ('G','Gplus'))
        assert g['scene_hash']==h['scene_hash'] and g['clear_count']==h['clear_count']
        t,u=float(g['total_time']),float(h['total_time']);n=int(g['clear_count'])
        pairs.append(dict(seed=int(seed),count=n,G_run_id=g['run_id'],Gplus_run_id=h['run_id'],
            G_total_s=t,Gplus_total_s=u,G_s_per_source=t/n,Gplus_s_per_source=u/n,
            saved_total_s=t-u,saved_s_per_source=(t-u)/n))
    with (ROOT/'reports/validation_paired.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(pairs[0]));writer.writeheader();writer.writerows(pairs)
    comparison=json.loads((ROOT/'reports/validation100/comparison.json').read_text())[0]
    audit=json.loads((ROOT/'reports/validation100/audit.json').read_text())
    stress_audit=json.loads((ROOT/'reports/stress24/audit.json').read_text())
    stress=json.loads((ROOT/'reports/stress24/comparison.json').read_text())[0]
    summaries={r['variant']:r for r in json.loads((ROOT/'reports/validation100/summary.json').read_text())}
    adopt=(comparison['saved_s_per_source_ci95'][0]>0 and comparison['saved_s_per_scene']>0
           and audit['all_pass'] and stress_audit['all_pass'])
    phases=['screen1','screen2','screen3','development40','validation100','stress24']
    smoke=json.loads((ROOT/'reports/entrypoint_check.json').read_text())
    assert len(smoke)==2 and all(r['identical_time'] for r in smoke)
    result=dict(version=freeze['version'],recommendation='Gplus' if adopt else 'G',
        total_local_runs=sum(len(rows(p)) for p in phases)+len(smoke),independent_pairs=100,stress_pairs=24,
        entrypoint_reproduction_runs=len(smoke),
        comparison=comparison,stress_comparison=stress,audit_all_pass=audit['all_pass'] and stress_audit['all_pass'],
        source_region_checks=audit['regions_checked']+stress_audit['regions_checked'],
        feedback_replayed_runs=audit['replayed_runs']+stress_audit['replayed_runs'],
        feedback_replayed_actions=audit['replayed_actions']+stress_audit['replayed_actions'],
        baseline_G_files_unchanged=True,engine_unchanged=True,summaries=summaries)
    (ROOT/'reports/SUMMARY.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    parts=[]
    for label,key in [('移动','move_time'),('射频检测','RF_detection_time'),('频道切换','channel_switch_time'),('光学定位','optical_time'),('清除','clear_time')]:
        g,h=(summaries[n]['mean_'+key] for n in ('G','Gplus'))
        parts.append(f'| {label} | {g:.2f} | {h:.2f} | {g-h:.2f} |')
    tails=[]
    for name in ('G','Gplus'):
        values=[p[name+'_s_per_source'] for p in pairs]
        tails.append(f'| {name} | {st.mean(values):.3f} | {st.median(values):.3f} | {percentile(values,.9):.3f} | {max(values):.3f} |')
    candidate=json.loads((ROOT/'candidate.json').read_text())
    med=st.median(p['Gplus_s_per_source'] for p in pairs)
    selected=min(pairs,key=lambda p:abs(p['Gplus_s_per_source']-med))
    payload=json.loads((ROOT/'runs'/selected['Gplus_run_id']/'result.json').read_text(encoding='utf-8'))
    payload['metadata'].update(strategy_version='local-Gplus-20260912-v1',experimental_variant=candidate)
    template=(ROOT.parent/'local_simulator/web/index.html').read_text(encoding='utf-8')
    (ROOT/'reports/Gplus_replay.html').write_text(template.replace('const EMBEDDED = null;',
        'const EMBEDDED = '+json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')+';',1),encoding='utf-8')
    draw(pairs)
    report=f'''# 问题 3：继续压低平均定位清除时间的本地实测

日期：2026-09-12。全部实验使用独立本地模拟器。原 G 文件和物理规则保持一致；没有执行官方测试。

## 结论

本轮完成 **{result['total_local_runs']} 次本地运行**。冻结候选 G+ 在 **100 个从未用于调参的配对场景**中，平均定位清除时间由 **{comparison['baseline_s_per_source']:.3f} 降至 {comparison['candidate_s_per_source']:.3f} 秒/源**，下降 **{comparison['saved_percent']:.3f}%**。平均每局节省 **{comparison['saved_s_per_scene']:.2f} 秒**。

配对 bootstrap 10,000 次的平均节省 95% 区间为 **[{comparison['saved_s_per_source_ci95'][0]:.3f}, {comparison['saved_s_per_source_ci95'][1]:.3f}] 秒/源**。{comparison['wins']} 场更快、{comparison['losses']} 场更慢、{comparison['ties']} 场相同。单场最大退步 {comparison['worst_regression_s_per_source']:.3f} 秒/源。当前实验推荐：**{'G+' if adopt else '继续保留 G'}**。这是有限实验支持的平均改善，没有证明全局最优，也没有实现大幅压降。

| 策略 | 均值/秒每源 | 中位数 | P90 | 最大值 |
|---|---:|---:|---:|---:|
{chr(10).join(tails)}

题面指标按场计算 `T_i/n_i`，再跨场景求均值。总行动时间包含移动、检测、切频、光学定位和成功清除；程序运行耗时不进入该指标。清除不完整的运行不得作为更快的成绩。

## G+ 实际改动

1. **补测后重新比较全部任务。** 将 `commit_radius` 从 120 调为 0，取消因区域半径降到 120 米就递归处理当前源的启发式承诺。每次实际补测之后返回全局任务规划，并利用真实停靠点执行原有搜索与共享检测逻辑。
2. **扩大直接前进的测站候选。** 在原候选之外加入区域中心、重心、两侧 8 米和 25 米点，以及朝当前位置退回 10 米、20 米的点。每个定位测站仍需通过原有的全区域接收安全证明。
3. **评分同时考虑平均和较坏的后续耗时。** 对同一假设源、三个假设误差，使用 `0.5 × 最大后续成本 + 0.5 × 平均后续成本`，然后按假设源等权平均。它是动作排序的启发式，不是误差真实分布，也不是可靠性证明。位置区域更新仍保留 ±1.01° 的完整误差边界。
4. **更严格筛选顺路测向。** `near_prediction` 从 14 降至 10 米，`bearing_factor` 从 0.25 降至 0.15，减少不值得花 5-6 秒的附带测向。原 G 的光学尝试阈值 40 米、完成条件和逐频道覆盖证明均保留。

没有启用额外提前扫描未知频道、面积采样评分、途中共享补测或新增光学成功概率模型。代码保留这些失败实验的开关以供复现，冻结候选关闭它们。

## 分项时间：100 场独立验证的每局均值

| 分项 | G/秒 | G+/秒 | 节省/秒 |
|---|---:|---:|---:|
{chr(10).join(parts)}

G 与 G+ 平均整局行动时间分别为 {summaries['G']['mean_total_time']:.2f}、{summaries['Gplus']['mean_total_time']:.2f} 秒。并行实验时的平均程序耗时分别为 {summaries['G']['mean_measured_program_wall_time_s']:.2f}、{summaries['Gplus']['mean_measured_program_wall_time_s']:.2f} 秒；它受 CPU 负载影响，不能当行动时间。

## 筛选过程与失败方向

- 首轮：16 场 × 8 方案 = 128 次；光学阈值 80/120、连续处理阈值、提前/推迟清除、更多共享测向。光学阈值扩大没有明显收益；推迟定位到半径 120 米才进入任务队列使平均时间明显上升。
- 第二轮：同 16 场 × 8 方案 = 128 次；测试直接前进候选、误差评分、面积采样与光学成本近似。直接候选加混合误差评分有小幅收益，面积采样版本变慢。
- 第三轮：同 16 场 × 8 方案 = 128 次；提前扫描未知频道、途中共享、严格筛选共享测向和取消承诺。提前扫描虽缩短移动，却因检测数量增加而使总时间变长；最低 0.1 残余覆盖率门槛使均值增加约 7.46%。
- 开发复核：另外 40 场 × 6 方案 = 240 次。组合方案从 233.517 降至 231.315 秒/源，随后冻结。这 40 场用于选型，不能称最终独立验证。
- 最终独立验证：场景 13001-13100，100 对，共 200 次。冻结后不再调整参数。
- 压力测试：场景 14001-14024，24 对，共 48 次；三种分布、最小/最大接收半径、四种误差模型，源数交替取 10 和 16。

原 G 在第一、二轮相同的 16 个场景中逐场时间完全一致。候选选择、代码哈希、参数和验证集预登记在 `FREEZE.json`。

## 压力测试与可信边界

24 对压力场景全部完整清除。压力集均值由 {stress['baseline_s_per_source']:.3f} 到 {stress['candidate_s_per_source']:.3f} 秒/源，节省 {stress['saved_s_per_source']:.3f} 秒/源；{stress['wins']} 胜、{stress['losses']} 负、{stress['ties']} 平。压力集改善的 95% 区间为 [{stress['saved_s_per_source_ci95'][0]:.3f}, {stress['saved_s_per_source_ci95'][1]:.3f}] 秒/源，跨过零，不能声称在压力场景中也有显著提速。压力集由异质极端场景组成，只用于检查稳健性，不能当作官方分布的成绩估计。

独立验证与压力测试共核验 {result['source_region_checks']} 次保守区域包含性，逐场账本与实际无信号覆盖结束证书通过。纯反馈重放共 **{result['feedback_replayed_runs']} 场、{result['feedback_replayed_actions']} 个动作**；决策期间禁止文件、网络和子进程访问，只输入原动作返回值，重放请求与原记录一致。已有 38 项规则与几何测试通过。

本地误差场、源位置分布和接收半径分布是模拟器假设。控制器不读取种子、真实源数、坐标或半径；真值仅在退出后核验。程序复用 G 的隔离运行器，因此历史 `run_id` 与基础策略字段仍含 G；每局 `experiment_variant.json`、统计中的 `variant_hash` 和 `FREEZE.json` 一起标明实际候选，不能仅凭基础字段混淆 G 与 G+。

## 继续优化的判断

仍有空间，但本轮证据支持的是小幅平均改善。要进一步明显下降，应把后续搜索、当前定位和其他目标的路线变化纳入更准确的多步成本预测，尤其减少源位置仍不确定时的无效往返。简单提高扫描频率、扩大光学尝试阈值和一味增加交会测量，在本轮测试中未带来稳定好处。新的方向仍需另外开发与独立验证，不能把本轮收益外推成最终上限。

## 产物与复现

- `reports/validation_paired.csv`：100 个场景的源数、两条轨迹标识、总时间和秒/源。
- `reports/validation100/`、`reports/stress24/`：预登记、逐场结果、配对统计和详细审计。
- `figures/Gplus_validation.pdf`：逐场时间散点图与包括退步在内的差值分布；数据来自 `validation_paired.csv`。
- `reports/Gplus_replay.html`：独立验证中秒/源接近中位数的完整离线回放，场景 {selected['seed']}。
- `candidate.json`、`FREEZE.json`：冻结候选与可复核版本信息。
- `runs/`：所有本地原始动作/反馈、事后结果、逐局源码快照。

在本目录运行：

```text
python run_candidate.py --seed 13001
python run_candidate.py --seed 13001 --baseline
python run_candidate.py --seed 14001 --scenario boundary --reception minimum --error-mode plus_one
```

每次生成独立结果目录和 `replay.html`。当前主模拟器默认 G 保留原样，G+ 在本隔离实验目录运行。

另外完成 2 次交付入口复现，G 和 G+ 在场景 13001 的总时间与独立验证逐微秒一致，记录在 `reports/entrypoint_check.json`；这 2 次包含在本轮运行总数中。也可以双击本目录 `运行Gplus.cmd` 启动示例。
'''
    (ROOT/'reports/RESULTS_REPORT.md').write_text(report,encoding='utf-8')
    (ROOT/'README.md').write_text('# 问题三平均时间优化实验\n\n详见 [实测报告](reports/RESULTS_REPORT.md)。\n\n运行冻结候选：`python run_candidate.py --seed 13001`；配对 G：追加 `--baseline`。\n\n本地测试；保留原 G。\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='summaries'},indent=2))


if __name__=='__main__':main()
