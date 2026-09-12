"""Summarize completed local D/E trials; never controls any simulator."""
import csv
import hashlib
import json
from pathlib import Path
import random
import statistics as stats
import sys

PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT/'local_simulator'
DEST=ROOT/'reports'/'optimization'
sys.path.insert(0,str(ROOT/'code'))
from benchmark import percentile


def rows(name):
    return list(csv.DictReader((DEST/(name+'_runs.csv')).open(encoding='utf-8-sig')))


def write_csv(name,items):
    with (DEST/name).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(items[0]))
        writer.writeheader();writer.writerows(items)


def main():
    validation=rows('E_validation100')
    assert len(validation)==200
    freeze=json.loads((DEST/'E_FREEZE.json').read_text())
    for name,expected in freeze['policy_file_sha256'].items():
        assert hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()==expected,name
    paired=[];records={};diagnostics=[]
    for seed in range(6001,6101):
        matches={r['variant']:r for r in validation if int(r['seed'])==seed}
        assert set(matches)=={'frozen_D','frozen_E'}
        pair={}
        for letter in ('D','E'):
            row=matches['frozen_'+letter]
            record=json.loads((ROOT/'runs'/row['run_id']/'result.json').read_text(encoding='utf-8'))
            assert record['evaluation']['events'][-1]['path']=='/exit'
            m=record['metrics']
            assert m['clear_ratio']==1 and m['completion_proved'] and not m['accounting_warnings'] and not m['client_error']
            pair[letter]=record;records[(seed,letter)]=record
            events=record['evaluation']['events']
            diagnostics.append(dict(seed=seed,strategy=letter,no_signal_count=sum(e['response'].get('measure_result')=='no_signal' for e in events),
                                    optical_failed_count=m['optical_failed_count'],move_distance=m['move_distance'],
                                    RF_count=m['RF_detection_count'],switch_count=m['channel_switch_count']))
        assert pair['D']['evaluation']['sources']==pair['E']['evaluation']['sources']
        d,e=(pair[k]['metrics']['total_time'] for k in ('D','E'))
        paired.append(dict(seed=seed,D_s=d,E_s=e,saved_s=d-e,
                           D_run_id=matches['frozen_D']['run_id'],E_run_id=matches['frozen_E']['run_id']))
    d=[r['D_s'] for r in paired];e=[r['E_s'] for r in paired]
    rng=random.Random(20260911);boot=[]
    for _ in range(10000):
        idx=[rng.randrange(100) for _ in range(100)]
        boot.append(100*(1-sum(e[i] for i in idx)/sum(d[i] for i in idx)))
    interval=[percentile(boot,.025),percentile(boot,.975)]
    summaries=json.loads((DEST/'E_validation100_summary.json').read_text())
    stresses=json.loads((DEST/'E_stress_summary.json').read_text())
    summary=dict(validation_pairs=100,mean_D_s=stats.mean(d),mean_E_s=stats.mean(e),
                 saved_mean_s=stats.mean(d)-stats.mean(e),improvement_percent=100*(1-stats.mean(e)/stats.mean(d)),
                 paired_bootstrap_95_percent_interval=interval,E_faster_cases=sum(a>b for a,b in zip(d,e)),
                 all_validation_clear_and_proved=True,all_stress_pass=all(r['all_pass'] for r in stresses),
                 recommended_default='E' if stats.mean(e)<stats.mean(d) and interval[0]>0 and all(r['all_pass'] for r in stresses) else 'D',
                 original_D_unchanged=True,summaries=summaries,stress=stresses)
    all_rows=[];board=[]
    for phase in ('round7','round8','round9','round10','E_validation100','E_stress'):
        phase_rows=rows(phase)
        all_rows.extend(phase_rows)
        for item in json.loads((DEST/(phase+'_summary.json')).read_text()):
            board.append(dict(phase=phase,**item))
    summary['additional_local_runs']=len(all_rows)
    summary['all_additional_runs_clear_and_proved']=all(r['clear_ratio']=='1.0' and r['completion_proved']=='True' and not r['client_error'] for r in all_rows)
    (DEST/'CONTINUATION_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    write_csv('E_validation_paired.csv',paired);write_csv('E_action_diagnostics.csv',diagnostics)
    write_csv('E_leaderboard.csv',board)
    selected=min(paired,key=lambda r:abs(r['E_s']-stats.median(e)))
    demo=records[(selected['seed'],'E')]
    html=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
    data=json.dumps(demo,ensure_ascii=False).replace('<','\\u003c')
    (DEST/'E_replay.html').write_text(html.replace('const EMBEDDED = null;','const EMBEDDED = '+data+';',1),encoding='utf-8')
    (ROOT/'reports'/'demo_replay.html').write_text((DEST/'E_replay.html').read_text(encoding='utf-8'),encoding='utf-8')
    audit_path=DEST/'E_feedback_only_audit.json'
    if audit_path.exists():
        audits=json.loads(audit_path.read_text())
        assert len(audits)==100 and all(a['all_decisions_identical'] for a in audits)
        audit_text=f"100 局 E 的 {sum(a['actions_checked'] for a in audits)} 个动作在纯反馈离线重放中全部一致，详见 E_feedback_only_audit.json。重放不加载模拟器或真值文件，决策期间禁止文件、网络与进程访问。"
    else:
        audit_text='纯反馈离线重放尚未运行。'
    table='\n'.join('| '+r['variant'].replace('frozen_','')+' | '+' | '.join(f"{r[k]:.2f}" for k in ('mean_s','median_s','p90_s','p95_s','worst_s'))+' |' for r in summaries)
    by={r['variant'][-1]:r for r in summaries}
    components=[]
    for key,label in [('move_time','移动'),('RF_detection_time','测向'),('channel_switch_time','切频'),('optical_time','光学'),('clear_time','清除')]:
        a,b=by['D']['mean_'+key],by['E']['mean_'+key]
        components.append(f'| {label} | {a:.2f} | {b:.2f} | {a-b:.2f} |')
    conclusion=('E 满足预先约定的采纳标准，作为本地推荐默认。' if summary['recommended_default']=='E' else
                'E 未满足预先约定的采纳标准，因此继续保留 D 为默认；保留 E 代码和结果供后续研究，不声称已经获得可靠提升。')
    report=f'''# 追加本地优化结果

本轮追加 {len(all_rows)} 局自建模拟实验，含 300 局训练、100 个场景的 D/E 配对验证（200 局）、4 个压力场景的配对验证（8 局）。本轮所有记录全清并通过完成证明：{'全部通过' if summary['all_additional_runs_clear_and_proved'] else '存在未通过记录'}。用户授权的一次官方演练已单独结束，此后没有再次启动官方演练或正式测试。

## 独立验证结果

E 在 100 个新场景上的平均整局行动时间为 **{stats.mean(e):.2f} 秒**，D 为 **{stats.mean(d):.2f} 秒**，平均节省 **{summary['saved_mean_s']:.2f} 秒（{summary['improvement_percent']:.2f}%）**。E 在 {summary['E_faster_cases']}/100 个配对场景更快。两种策略均 100/100 全清，动作记账与逐频道覆盖证明全部通过。

| 策略 | 平均 | 中位数 | P90 | P95 | 最坏 |
| --- | ---: | ---: | ---: | ---: | ---: |
{table}

配对 bootstrap 10,000 次，平均改善百分比的 95% 区间为 **[{interval[0]:.2f}%, {interval[1]:.2f}%]**。区间仅针对这些本地生成场景，不代表官方分布。{conclusion}

| 分项平均时间 | D 秒 | E 秒 | 减少秒数 |
| --- | ---: | ---: | ---: |
{chr(10).join(components)}

## 改了什么

保留 D 的联合开放路线、保守定位区域、完整动作费用与严格终止证书。E 扩大有几何证明的安全测站范围；每次补测后允许重排任务，但半径已小于 120 米时继续处理当前源；仅在估计距离不超过 1200 米且预期有足够定位收益时做共享测向；发现满 16 个不同源后立即停止未知频道扫描。光学尝试仍需计费，失败也完整记录。

控制器既没有实际源坐标，也没有场景种子或真实源总数参数。假设位置来自当前观测多边形。接收范围判定通过半平面裁剪后的顶点最大距离证明，详见 E_MODEL_NOTES.md。重规划、预测时间和有限求积是启发式，不是全局最优保证。

120 米是是否继续补测的策略阈值；清除范围仍为 20 米。{audit_text}

## 哪些尝试没有采用

第 7 轮 56 局中，单次补测后无条件重排、面积重心代替路线中心、自动转动覆盖圆环、面积加权选测站都没有超过 D。第 8 轮加入连续鲁棒接收约束，组合重规划在原训练组约减少 1%，但个别场景走出较长折返。第 9 轮在 501–512 扩展训练上比较保持路线顺序、局部继续清除及共享测向距离。第 10 轮继续比较数量上界停止和光学阈值，最终训练胜出配置为 shared1200，均值 3087.18 秒；同场景 D 为 3131.15 秒。

省去部分测量可能增加后续路程；保持旧路线过于严格也会阻止利用新信息。是否采纳以完整总时间和全清结果判断。训练筛选收益不能冒充独立验证收益。

## 实验与复现

训练 301–308、501–512。在任何新验证场景运行前固定参数与代码摘要 E_FREEZE.json，并把预留验证扩展为 6001–6100；验证中没有调参。压力 6101–6104，源数均为 16，包含边界、聚集、1000 米最小接收半径及极端误差。压力配对结果：{'全部通过' if summary['all_stress_pass'] else '存在未通过记录'}。

原引擎未改变，移动为 5 米/秒，全部费用以虚拟行动时间相加。计算机执行秒数不是此处优化指标。源真值只在场景退出后用于评估与可视化。D/E 的每个配对场景的真值数组已在退出后核对一致。

运行 `python simulator.py run --strategy E --seed 6001` 可复现冻结 E；策略 D 仍可用。E_validation100_config.json、各 round*_config.json 保存实验配置；E_leaderboard.csv 汇总每轮，E_validation_paired.csv 保留逐场差异；runs/ 中保留各局原始日志、指标与代码快照。E_replay.html 为验证中位数附近案例的离线回放，未挑选最快案例。

## 时间目标的限制

尚未达到 200–300 秒的整局目标。此前独立本地案例即使事先知道所有位置，乐观路径时间下界平均也达 1783.83 秒。这里不把整局时间除以源数后冒称达标，也不以修改速度或省略费用获得提升。本报告不声称已全局最优。
'''
    (DEST/'CONTINUATION_RESULTS.md').write_text(report,encoding='utf-8')
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont('cn','C:/Windows/Fonts/simhei.ttf'))
    out=ROOT/'figures'/'E_validation_comparison.pdf'
    c=canvas.Canvas(str(out),pagesize=(660,440));c.setFont('cn',18)
    c.drawString(42,405,'100 个独立场景：D 与 E 的整局时间')
    c.setFont('cn',10);c.drawString(42,384,f'全清：D 100/100，E 100/100；平均差异 {summary["saved_mean_s"]:.2f} 秒')
    import math
    low=math.floor(min(d+e)/500)*500;high=math.ceil(max(d+e)/500)*500
    def xy(a,b):return 70+(a-low)/(high-low)*310,65+(b-low)/(high-low)*310
    c.setStrokeColorRGB(.84,.88,.92)
    for v in range(int(low),int(high)+1,500):
        x,y=xy(v,v);c.line(70,y,380,y);c.line(x,65,x,375)
        c.setFillColorRGB(.35,.4,.45);c.drawRightString(63,y-3,str(v));c.drawCentredString(x,50,str(v))
    c.setStrokeColorRGB(.4,.45,.5);c.setDash(4,3);c.line(*xy(low,low),*xy(high,high));c.setDash()
    for a,b in zip(d,e):
        c.setFillColorRGB(*((.08,.6,.43) if b<a else (.85,.43,.2)))
        c.circle(*xy(a,b),2.6,stroke=0,fill=1)
    c.setFillColorRGB(.2,.25,.3);c.drawCentredString(225,28,'D 的整局时间（秒）')
    c.saveState();c.translate(21,220);c.rotate(90);c.drawCentredString(0,0,'E 的整局时间（秒）');c.restoreState()
    c.drawString(407,340,'每个点对应同一个场景')
    c.drawString(407,319,'虚线下方：E 更快')
    c.setFillColorRGB(.2,.4,.8);c.drawString(407,283,f'D 平均：{stats.mean(d):.2f} 秒')
    c.setFillColorRGB(.08,.6,.43);c.drawString(407,260,f'E 平均：{stats.mean(e):.2f} 秒')
    c.setFillColorRGB(.2,.25,.3);c.drawString(407,222,f'E 更快：{summary["E_faster_cases"]}/100 场景')
    c.drawString(407,199,f'平均改善：{summary["improvement_percent"]:.2f}%')
    c.drawString(407,172,'配对 bootstrap 95% 区间')
    c.drawString(407,152,f'[{interval[0]:.2f}%, {interval[1]:.2f}%]')
    c.drawString(407,100,'冻结参数后验证；仅自建环境')
    c.save()
    print(json.dumps({k:v for k,v in summary.items() if k not in ('summaries','stress')},indent=2))


if __name__=='__main__':main()
