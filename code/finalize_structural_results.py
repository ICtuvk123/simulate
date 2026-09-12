"""Completed-case statistics and artifacts; never runs a simulator."""
import csv
import hashlib
import json
from pathlib import Path
import random
import statistics as stats
import sys

ROOT=Path(__file__).resolve().parents[1]/'local_simulator';DEST=ROOT/'reports'/'optimization'
sys.path.insert(0,str(ROOT/'code'))
from benchmark import percentile


def read_rows(name):
    return list(csv.DictReader((DEST/(name+'_runs.csv')).open(encoding='utf-8-sig')))


def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def bootstrap(pairs,key_e,key_f):
    rng=random.Random(20260912);values=[];n=len(pairs)
    for _ in range(10000):
        sample=[pairs[rng.randrange(n)] for _ in range(n)]
        e=sum(p[key_e] for p in sample);f=sum(p[key_f] for p in sample)
        values.append(100*(e-f)/e)
    return [percentile(values,.025),percentile(values,.975)]


def main():
    phases=['F_round1','F_round2','F_round3','F_validation100','F_stress']
    all_rows=[r for phase in phases for r in read_rows(phase)]
    rows=read_rows('F_validation100');stress=read_rows('F_stress')
    assert len(rows)==200 and len(stress)==16
    freeze=json.loads((DEST/'F_FREEZE.json').read_text())
    previous=json.loads((DEST/'E_FREEZE.json').read_text())
    for name,sha in previous['policy_file_sha256'].items():
        assert hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()==sha,('E changed',name)
    for name,sha in freeze['policy_file_sha256'].items():
        assert hashlib.sha256((ROOT/'code'/name).read_bytes()).hexdigest()==sha,name
    paired=[]
    for seed in range(8001,8101):
        group={r['variant']:r for r in rows if int(r['seed'])==seed};e=group['frozen_E'];f=group['frozen_F']
        pe=json.loads((ROOT/'runs'/e['run_id']/'result.json').read_text(encoding='utf-8'))
        pf=json.loads((ROOT/'runs'/f['run_id']/'result.json').read_text(encoding='utf-8'))
        assert pe['evaluation']['sources']==pf['evaluation']['sources']
        assert not pe['metrics']['accounting_warnings'] and not pf['metrics']['accounting_warnings']
        paired.append(dict(seed=seed,E_run_id=e['run_id'],F_run_id=f['run_id'],count=int(e['clear_count']),
            E_total_s=float(e['total_time']),F_total_s=float(f['total_time']),
            E_s_per_source=float(e['total_time'])/int(e['clear_count']),
            F_s_per_source=float(f['total_time'])/int(f['clear_count']),saved_s=float(e['total_time'])-float(f['total_time'])))
    summaries=json.loads((DEST/'F_validation100_summary.json').read_text())
    by={r['variant']:r for r in summaries};e=by['frozen_E'];f=by['frozen_F']
    interval=bootstrap(paired,'E_total_s','F_total_s');per_interval=bootstrap(paired,'E_s_per_source','F_s_per_source')
    all_pass=all(float(r['clear_ratio'])==1 and r['completion_proved']=='True' and not r['client_error'] for r in all_rows)
    stress_pass=all(float(r['clear_ratio'])==1 and r['completion_proved']=='True' and not r['client_error'] for r in stress)
    adopt=all_pass and stress_pass and f['mean_s']<e['mean_s'] and f['mean_s_per_source']<e['mean_s_per_source'] and interval[0]>0
    output=dict(additional_local_runs=len(all_rows),validation_pairs=100,all_runs_clear_and_proved=all_pass,
        stress_all_pass=stress_pass,mean_E_total_s=e['mean_s'],mean_F_total_s=f['mean_s'],
        mean_E_s_per_source=e['mean_s_per_source'],mean_F_s_per_source=f['mean_s_per_source'],
        saved_mean_s=e['mean_s']-f['mean_s'],improvement_percent=100*(e['mean_s']-f['mean_s'])/e['mean_s'],
        paired_bootstrap_95_percent_interval=interval,per_source_bootstrap_95_percent_interval=per_interval,
        F_faster_cases=sum(p['saved_s']>0 for p in paired),recommended_default='F' if adopt else 'E',
        original_engine_and_E_policy_unchanged=True,summaries=summaries)
    audit_path=DEST/'F_feedback_only_audit.json'
    audit=json.loads(audit_path.read_text()) if audit_path.exists() else []
    if audit:
        assert len(audit)==100 and all(r['all_decisions_identical'] for r in audit)
        output['feedback_only_audited_runs']=len(audit)
        output['feedback_only_audited_actions']=sum(r['actions_checked'] for r in audit)
    (DEST/'F_SUMMARY.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    write_csv(DEST/'F_validation_paired.csv',paired)
    leaderboard=[]
    for phase in phases:
        for row in json.loads((DEST/(phase+'_summary.json')).read_text()):
            leaderboard.append(dict(phase=phase,**row))
    write_csv(DEST/'F_leaderboard.csv',leaderboard)
    component_table='\n'.join(f"| {label} | {e['mean_'+key]:.2f} | {f['mean_'+key]:.2f} | {e['mean_'+key]-f['mean_'+key]:.2f} |"
        for key,label in [('move_time','移动'),('RF_detection_time','测向'),('channel_switch_time','切频'),('optical_time','光学'),('clear_time','清除')])
    result_table='\n'.join(f"| {label} | {r['mean_s']:.2f} | {r['mean_s_per_source']:.2f} | {r['median_s']:.2f} | {r['p90_s']:.2f} | {r['p95_s']:.2f} | {r['worst_s']:.2f} |"
                           for label,r in [('E',e),('F',f)])
    adoption='F 达到预先声明的采纳条件，可设为推荐默认。' if adopt else 'F 未达到预先声明的全部采纳条件，保留 E 为推荐默认；不以训练收益替代独立验证结论。'
    text=f'''# 按用户思路进行结构优化的结果

本轮共 {len(all_rows)} 次完整自建模拟运行：三轮训练 172 次，100 个新场景配对验证 200 次，8 个压力场景配对 16 次。全部运行全清并通过完成证书：{all_pass}。本轮没有启动官方程序、官方演练或正式测试。

## 先纠正指标口径

题面规定的“平均定位清除时间”是每场总行动时间除以该场实际清除数。此前 E 的原 100 场结果重新逐场计算为 **229.62 秒/源**，整局均值为 **3002.14 秒**。这两个量不同；此前以整局时间目标推导的下界不能否定 200–300 秒/源。原 E 按题面指标的均值已经落在该范围。原 D 同批为 237.98 秒/源。

这里报告的是场景比值的平均值 mean(T_i/n_i)，不是 mean(T_i)/mean(n_i)。后者原 E 为 225.22 秒/源，属于不同的加权口径，不能替代题面逐场统计。单局同样全清时，优化总时间与优化单源时间一致；跨场景平均时仍需分别比较。

## 冻结后的独立验证

| 策略 | 整局均值/秒 | 逐场均值/秒每源 | 整局中位数/秒 | P90/秒 | P95/秒 | 最坏/秒 |
|---|---:|---:|---:|---:|---:|---:|
{result_table}

F 平均每局节省 **{output['saved_mean_s']:.2f} 秒（{output['improvement_percent']:.2f}%）**，100 场中 {output['F_faster_cases']} 场更快。整局配对 bootstrap 10,000 次得到改善百分比 95% 区间 **[{interval[0]:.2f}%, {interval[1]:.2f}%]**。逐场秒/源改善区间为 [{per_interval[0]:.2f}%, {per_interval[1]:.2f}%]。{adoption}

| 分项平均时间 | E 秒 | F 秒 | E 减 F 秒 |
|---|---:|---:|---:|
{component_table}

统计只针对本地生成场景，不代表官方分布；100 场全清不等于所有可能输入的保证。F 的 P90/P95 略有改善，但最坏一场为 {f['worst_s']:.2f} 秒，高于 E 的 {e['worst_s']:.2f} 秒。因此只主张平均时间改善，不保证每个场景都更快。源码、参数和实际反馈均可追溯，未改变速度、误差界、计费或隐含读取真值。

## 哪些思路已实现、哪些最终启用

冻结 F 为 {freeze['version']}。启用正负观测半平面、联合历史测站接收保证、分频道覆盖、带新增扫描成本的有限搜索站替代、顺路清除点，以及首次示向的 183 点有限光学兜底。没有继续调整 1130 米骨架半径、120 米继续处理阈值或 1200 米共享筛选阈值。

还实现并比较了 RF 无信号圆与光学失败圆的多凸片排除、直接用未来清除点重建搜索计划、局部测站加入全体剩余任务的路线尾部估价、共享测向强制安全检查。这些备选开关没有进入本次冻结 F。

原因由消融数据决定：首轮单加半平面和联合接收在 8 场训练中未改变动作；扩大负反馈表示可减少某些补测，却在第二组增加了移动，整局均值 3006.12 秒，高于 E 的 3004.21 秒。未计入所有新增扫描的自适应搜索虽然减少约 63 秒移动，却增加约 218 秒测向与切频，整局升至 3159.35 秒。它不是已采用的改进。

第三轮把新增扫描成本加入比较后，搜索替代均值为 2996.83 秒；顺路清除为 2993.66 秒；组合为 2986.52 秒，对照 E 为 3004.21 秒。组合训练改善约 0.59%，之后才冻结并验证，未根据验证结果继续调参。

## 保证与近似

正负半平面由固定接收半径消元得到。圆形排除只删除真实排除圆的内接多边形；非凸部分以凸片保存。联合接收安全检查使用连续多边形包含，有限假设源点不承担安全证明。所有保留片在已结束训练/验证的事后检查中均保留真实源；事后真值只进入评估脚本。

搜索未来停靠只用于预测，不写入无信号历史。最终完成证书独立按每个未发现频道的实际无信号站验证，或使用已清除 16 个源的公开数量上界。光学失败只在已确认存在且未清除的目标上作为负观测，拒绝请求和重复清除不产生排除约束。

顺路清除比较进入和离开可操作区域的距离；直线穿过可操作区时得到零绕行点，否则用保守可行的投影下降，未声称精确解了连续 SOCP。搜索替代枚举少量目标组合并使用近似未来成本，仍不是整局最优控制。183 点覆盖提供有限几何兜底，但现实截止前必能完成仍取决于通信和计算预算。

## 复现与产物

训练为 7001–7008、7011–7022；最终验证为未参与选择的 8001–8100；压力为 8201–8208，覆盖边界/聚集、最小和最大接收半径、恒定极端与空间平滑误差。35 项规则及几何测试通过。压力全清并通过实际反馈证书：{stress_pass}。

F_FREEZE.json 固定策略文件摘要；F_round*_config.json 与 F_validation100_config.json 保存参数；F_leaderboard.csv、F_validation_paired.csv、各阶段 diagnostics.csv 保存均值、分项和逐场数据。runs/ 保留所有本轮原始日志和源码快照。各配对场景的源数组在退出后核对相同。

运行 `python simulator.py run --strategy F --seed 8001` 可复现冻结 F；`--strategy E` 保留原算法。F_replay.html 为 F 验证组整局时间中位附近的离线回放。图表位于 figures/F_validation_comparison.pdf，包含整局和秒/源两种口径。
'''
    if audit:
        text+=f"\n100 局 F 的 **{output['feedback_only_audited_actions']} 个动作**已在纯反馈重放中全部一致。重放不导入环境生成器，不读取真值或传递场景种子，决策期间禁止文件、网络与子进程访问。见 F_feedback_only_audit.json。\n"
    (DEST/'F_RESULTS.md').write_text(text,encoding='utf-8')
    selected=min((r for r in rows if r['variant']=='frozen_F'),key=lambda r:abs(float(r['total_time'])-f['median_s']))
    payload=json.loads((ROOT/'runs'/selected['run_id']/'result.json').read_text(encoding='utf-8'))
    html=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
    html=html.replace('const EMBEDDED = null;','const EMBEDDED = '+json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';',1)
    (DEST/'F_replay.html').write_text(html,encoding='utf-8')
    make_figure(paired,output)
    print(json.dumps(output,indent=2))


def make_figure(pairs,summary):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import HexColor
    pdfmetrics.registerFont(TTFont('F_CJK','C:/Windows/Fonts/simhei.ttf'))
    c=canvas.Canvas(str(ROOT/'figures'/'F_validation_comparison.pdf'),pagesize=(720,350))
    for panel,(ke,kf,label) in enumerate([('E_total_s','F_total_s','整局行动时间（秒）'),
                                        ('E_s_per_source','F_s_per_source','每场平均定位清除时间（秒/源）')]):
        x0=62+panel*350;y0=72;size=235
        values=[p[k] for p in pairs for k in (ke,kf)];lo=min(values);hi=max(values);pad=(hi-lo)*.06;lo-=pad;hi+=pad
        def axis(v):return (v-lo)/(hi-lo)*size
        for i in range(5):
            v=lo+(hi-lo)*i/4;x=x0+axis(v);y=y0+axis(v)
            c.setStrokeColor(HexColor('#e2e8ef'));c.line(x,y0,x,y0+size);c.line(x0,y,x0+size,y)
            c.setFillColor(HexColor('#607184'));c.setFont('F_CJK',8)
            c.drawCentredString(x,y0-13,f'{v:.0f}');c.drawRightString(x0-7,y-3,f'{v:.0f}')
        c.setStrokeColor(HexColor('#68798a'));c.setDash(3,3);c.line(x0,y0,x0+size,y0+size);c.setDash()
        for p in pairs:
            c.setFillColor(HexColor('#148d70' if p[kf]<p[ke] else '#e49731'))
            c.circle(x0+axis(p[ke]),y0+axis(p[kf]),2.3,fill=1,stroke=0)
        c.setFillColor(HexColor('#20394e'));c.setFont('F_CJK',10)
        c.drawCentredString(x0+size/2,y0-32,'E：'+label)
        c.saveState();c.translate(x0-41,y0+size/2);c.rotate(90);c.drawCentredString(0,0,'F：'+label);c.restoreState()
    c.setFont('F_CJK',9);c.setFillColor(HexColor('#42586d'))
    c.drawString(62,18,f"100 个新场景配对；绿色为 F 更快（{summary['F_faster_cases']} 场）；虚线为等时线。")
    c.save()


if __name__=='__main__':main()
