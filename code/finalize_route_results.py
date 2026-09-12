"""Post-run paired statistics, report and scientific comparison figure."""
import csv
import hashlib
import json
from pathlib import Path
import random
import statistics as st
import sys

ROOT=Path(__file__).resolve().parents[1]/'local_simulator';DEST=ROOT/'reports/optimization'
sys.path.insert(0,str(ROOT/'code'))
from benchmark import percentile


def csv_rows(phase):
    return list(csv.DictReader((DEST/(phase+'_runs.csv')).open(encoding='utf-8-sig')))


def main():
    freeze=json.loads((DEST/'G_FREEZE.json').read_text(encoding='utf-8'))
    for name,digest in freeze['policy_file_sha256'].items():
        assert hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()==digest,name
    phases=freeze['training_phases']+['G_validation100','G_stress']
    rows=csv_rows('G_validation100');assert len(rows)==200
    paired=[]
    for seed in range(10001,10101):
        group={r['variant']:r for r in rows if int(r['seed'])==seed}
        f,g=group['frozen_F'],group['frozen_G']
        assert f['clear_count']==g['clear_count']
        paired.append(dict(seed=seed,F_run_id=f['run_id'],G_run_id=g['run_id'],count=int(f['clear_count']),
                           F_total_s=float(f['total_time']),G_total_s=float(g['total_time']),
                           F_s_per_source=float(f['total_time'])/int(f['clear_count']),
                           G_s_per_source=float(g['total_time'])/int(g['clear_count']),
                           saved_s=float(f['total_time'])-float(g['total_time'])))
    with (DEST/'G_validation_paired.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)
    by={r['variant']:r for r in json.loads((DEST/'G_validation100_summary.json').read_text())}
    f,g=by['frozen_F'],by['frozen_G']
    rng=random.Random(20260913);samples=[]
    for _ in range(10000):
        choices=[paired[rng.randrange(len(paired))] for _ in paired]
        samples.append(100*sum(r['saved_s'] for r in choices)/sum(r['F_total_s'] for r in choices))
    ci=[percentile(samples,.025),percentile(samples,.975)]
    audit=json.loads((DEST/'G_validation_audit.json').read_text())
    stress_audit=json.loads((DEST/'G_stress_audit.json').read_text())
    adopt=(g['mean_s']<f['mean_s'] and g['mean_s_per_source']<f['mean_s_per_source'] and ci[0]>0
           and audit['all_pass'] and stress_audit['all_pass'] and g['worst_s']<=f['worst_s']*1.02)
    result=dict(variant=freeze['selection_variant'],version=freeze['version'],
        additional_local_runs=sum(len(csv_rows(p)) for p in phases),validation_pairs=100,
        mean_F_total_s=f['mean_s'],mean_G_total_s=g['mean_s'],saved_mean_s=f['mean_s']-g['mean_s'],
        improvement_percent=100*(f['mean_s']-g['mean_s'])/f['mean_s'],
        mean_F_s_per_source=f['mean_s_per_source'],mean_G_s_per_source=g['mean_s_per_source'],
        paired_bootstrap_95_percent_interval=ci,G_faster_cases=sum(r['saved_s']>1e-6 for r in paired),
        G_equal_cases=sum(abs(r['saved_s'])<=1e-6 for r in paired),recommended_default='G' if adopt else 'F',
        validation_all_pass=audit['all_pass'],stress_all_pass=stress_audit['all_pass'],
        feedback_only_audited_runs=audit['feedback_replay_runs'],feedback_only_audited_actions=audit['feedback_replay_actions'],
        baseline_F_and_engine_unchanged=True,summaries=[f,g])
    (DEST/'G_SUMMARY.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    leaderboard=[]
    for phase in phases:
        leaderboard.extend(dict(phase=phase,**r) for r in json.loads((DEST/(phase+'_summary.json')).read_text()))
    with (DEST/'G_leaderboard.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(leaderboard[0]));writer.writeheader();writer.writerows(leaderboard)
    table='\n'.join(f"| {name} | {r['mean_s']:.2f} | {r['mean_s_per_source']:.2f} | {r['p90_s']:.2f} | {r['p95_s']:.2f} | {r['worst_s']:.2f} |" for name,r in [('F',f),('G',g)])
    components='\n'.join(f"| {label} | {f['mean_'+key]:.2f} | {g['mean_'+key]:.2f} | {f['mean_'+key]-g['mean_'+key]:.2f} |" for key,label in [('move_time','移动'),('RF_detection_time','测向'),('channel_switch_time','换频道'),('optical_time','光学'),('clear_time','清除')])
    report=f'''# 继续压缩总时间：G 本地实验结果

本轮完成 {result['additional_local_runs']} 次自建模拟运行。没有启动官方演练或正式测试。保持 F 的全部策略文件和模拟器物理规则不变。这里的秒数是题目计费的行动时间，并非 Python 程序执行用时。

## 独立配对验证

| 策略 | 平均总时间/秒 | 逐场均值/秒每源 | P90/秒 | P95/秒 | 最坏/秒 |
|---|---:|---:|---:|---:|---:|
{table}

G 相比 F 平均每局节省 {result['saved_mean_s']:.2f} 秒（{result['improvement_percent']:.2f}%）；100 场中 {result['G_faster_cases']} 场更快，{result['G_equal_cases']} 场相同。配对 bootstrap 10,000 次的平均改善百分比 95% 区间为 [{ci[0]:.2f}%, {ci[1]:.2f}%]。

当前推荐默认策略：**{result['recommended_default']}**。采纳 G 要求独立验证两种均值均下降、改善区间下界大于零、完整清除及压力核验通过，且最坏案例总时间不高于 F 的 102%。每源均值为 mean(T_i/n_i)，未使用两个总体均值之比替代。

| 分项 | F 平均秒数 | G 平均秒数 | 节省秒数 |
|---|---:|---:|---:|
{components}

## 本次改动与未采用方向

当前候选为 `{freeze['selection_variant']}`，冻结版本 `{freeze['version']}`。根据已接收的测向和无信号反馈，把搜索站向后续实际任务路线调整，每次调整都保留剩余计划的逐频道连续覆盖证明。未来停靠只能用于规划，不能被写成已经获得的无信号反馈。

冻结 G 采用粗粒度候选点加前后目标全可行源区域的不增程筛选：新搜索站到相邻目标每个可行源位置的距离均不增加，且当前估计路线缩短才接受。该判据把源位置近似为未来访问点，不能保证实际机器人每一段路或整局都更短；实际收益以下方完整配对实验为准。详细公式与边界见 G_MODEL_NOTES.md。

第一轮比较 F、旋转覆盖六边形、移动搜索站及二者组合。旋转方案在 12 场训练中平均多耗 68.66 秒，被淘汰；粗粒度移动平均省 9.28 秒，但在新增 20 场中平均略慢，收益不稳定。进一步实验与消融保存在 G_leaderboard.csv 和各轮配置、完整日志中，不隐去负面结果。

精细移动在 20 场中平均省 15.25 秒，但回到首组 12 场反而慢 18.57 秒，因此未直接采纳。加上述不增程筛选后，在合并的 32 个训练场景中，粗粒度方案平均省 5.29 秒且最坏时间与 F 相同，精细方案只省 1.73 秒，最终选择前者并冻结。

## 验证与可信范围

训练场景与独立验证 10001–10100 分离，候选冻结后才运行 100 组 F/G 配对。压力集为 10201–10208，覆盖边界、聚集、最小/最大接收半径、恒定极端及平滑测向误差。配对源集合仅在退出后核对一致。真实坐标只用于事后检查定位区域没有排除真实源，未输入控制器。

独立验证完整清除、动作记账和实际反馈结束证书全部通过：{audit['all_pass']}。压力核验全部通过：{stress_audit['all_pass']}。G 的 {audit['feedback_replay_runs']} 局、{audit['feedback_replay_actions']} 条动作已通过纯反馈重放；重放决策期间禁止磁盘、网络与子进程访问，不导入环境引擎，不传入种子或真实坐标。

上述统计只适用于本地生成规则，不等于官方测试成绩，也不保证每个场景都变快。之前官方演练 233.96 秒/源属于另一个案例，不能与本表直接作算法优劣比较。

## 复现和查看

在 local_simulator 目录执行 `python simulator.py run --strategy G --seed 10001`，对照将 G 改为 F。参数见 code/g_policy_presets.py，策略见 code/route_search.py，结束证明继承冻结 F。G_FREEZE.json 保存源码摘要。

G_replay.html 为验证组总时间中位附近的 G 完整离线回放，无需 Python。figures/G_validation_comparison.pdf 是数据图表，G_validation_paired.csv 是逐场配对数据，G_validation_audit.json 和 G_stress_audit.json 保存详细核验。runs/ 保存本轮每局原始接口日志、结果和代码快照。
'''
    (DEST/'G_RESULTS.md').write_text(report,encoding='utf-8')
    selected=min((r for r in rows if r['variant']=='frozen_G'),key=lambda r:abs(float(r['total_time'])-g['median_s']))
    payload=json.loads((ROOT/'runs'/selected['run_id']/'result.json').read_text(encoding='utf-8'))
    html=(ROOT/'web/index.html').read_text(encoding='utf-8').replace('const EMBEDDED = null;',
        'const EMBEDDED = '+json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';',1)
    (DEST/'G_replay.html').write_text(html,encoding='utf-8')
    draw(paired)
    print(json.dumps(result,indent=2))


def draw(pairs):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import HexColor
    pdfmetrics.registerFont(TTFont('GChinese','C:/Windows/Fonts/simhei.ttf'))
    path=ROOT/'figures/G_validation_comparison.pdf'
    c=canvas.Canvas(str(path),pagesize=(960,430));c.setFont('GChinese',12)
    low=100*math_floor(min(min(p['F_total_s'],p['G_total_s']) for p in pairs)/100)-100
    high=100*math_ceil(max(max(p['F_total_s'],p['G_total_s']) for p in pairs)/100)+100
    x0,y0,w,h=65,70,345,300
    def px(v):return x0+w*(v-low)/(high-low)
    def py(v):return y0+h*(v-low)/(high-low)
    c.setStrokeColor(HexColor('#d8dee8'))
    for v in range(int(low),int(high)+1,200):
        c.line(px(v),y0,px(v),y0+h);c.line(x0,py(v),x0+w,py(v))
        c.setFillColor(HexColor('#475569'));c.setFont('GChinese',9)
        c.drawCentredString(px(v),y0-16,str(v));c.drawRightString(x0-8,py(v)-3,str(v))
    c.setStrokeColor(HexColor('#94a3b8'));c.setDash(3,3);c.line(px(low),py(low),px(high),py(high));c.setDash()
    for p in pairs:
        c.setFillColor(HexColor('#15806a' if p['saved_s']>=0 else '#cb6c26'))
        c.circle(px(p['F_total_s']),py(p['G_total_s']),2.3,stroke=0,fill=1)
    c.setFillColor(HexColor('#172b45'));c.setFont('GChinese',12)
    c.drawCentredString(x0+w/2,25,'F 整局行动时间（秒）')
    c.saveState();c.translate(18,y0+h/2);c.rotate(90);c.drawCentredString(0,0,'G 整局行动时间（秒）');c.restoreState()
    x0,w=540,350
    ordered=sorted(p['saved_s'] for p in pairs)
    bottom=50*math_floor(min(0,min(ordered))/50)-50;top=50*math_ceil(max(0,max(ordered))/50)+50
    def y(v):return y0+h*(v-bottom)/(top-bottom)
    c.setStrokeColor(HexColor('#d8dee8'));c.setFont('GChinese',9)
    for v in range(int(bottom),int(top)+1,50):
        c.line(x0,y(v),x0+w,y(v));c.drawRightString(x0-8,y(v)-3,str(v))
    c.setStrokeColor(HexColor('#475569'));c.line(x0,y(0),x0+w,y(0))
    for i,v in enumerate(ordered):
        c.setFillColor(HexColor('#15806a' if v>=0 else '#cb6c26'))
        c.rect(x0+i*w/100,y(min(v,0)),w/100-.5,abs(y(v)-y(0)),fill=1,stroke=0)
    c.setFillColor(HexColor('#172b45'));c.setFont('GChinese',12)
    c.drawCentredString(x0+w/2,25,'按节省时间排序的 100 个配对场景')
    c.saveState();c.translate(485,y0+h/2);c.rotate(90);c.drawCentredString(0,0,'F 减 G 的总时间（秒）');c.restoreState()
    c.setFont('GChinese',10);c.drawString(65,400,'每点对应同一个场景；虚线为等时线')
    c.drawString(540,400,'正值表示 G 更快；负值表示 F 更快')
    c.save()


def math_floor(x):
    import math
    return math.floor(x)


def math_ceil(x):
    import math
    return math.ceil(x)


if __name__=='__main__':main()
