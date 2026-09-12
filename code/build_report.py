"""Refresh an evidence index from completed experiment files only."""
import csv,json,platform,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def build():
    incumbent=json.loads((ROOT/'INCUMBENT.json').read_text());freeze=json.loads((ROOT/incumbent['freeze']).read_text())
    phase=incumbent.get('final_evidence',incumbent['evidence'][-1]).split('/')[-1];folder=ROOT/'reports'/phase
    comparison=freeze.get('comparison',{});candidate=incumbent.get('final_variant',comparison.get('candidate','H0'))
    summary=json.loads((folder/'summary.json').read_text());current=summary[candidate]
    stage='本轮已完成最终验收与冻结' if incumbent.get('status')=='final_frozen' else '持续开发任务尚未结束'
    lines=['# 第四问计算结果与证据索引','',f"更新时间：{datetime.now(timezone.utc).isoformat()}。{stage}，以 INCUMBENT.json 指向的冻结版本为准。",'',
           '## 当前已验证版本','',f"版本：`{incumbent['version']}`；执行源码 commit：`{freeze['commit']}`。默认入口从 `{incumbent.get('code_directory','code')}` 加载，不使用正在编辑的实验候选。",'',
           '| 场景集 | 完整成功 | 平均每源 / s | 平均总时间 / s | P95 总时间 / s | 最坏总时间 / s | 平均现实耗时 / s |',
           '|---|---:|---:|---:|---:|---:|---:|',
           f"| {phase} | {current['complete']}/{current['n']} | {current['mean_per_source']:.3f} | {current['mean_total']:.3f} | {current['p95']:.3f} | {current['worst']:.3f} | {current['mean_wall']:.3f} |",'',
           '平均每源时间定义为逐场 T/实际源数 的算术平均，不用平均总时间除以平均源数替代。源数只由结束后的评估器提供。P95 使用整场总时间的线性插值经验分位数。现实耗时来自本机并行 worker 中的策略进程，包含决策和日志写入；不同运行批次的系统负载可能不同。','',
           '## 当前验证集的实际时间分项','',
           '| 方案 | 移动 / s | RF / s | 切频 / s | 光学 / s | 清除 / s | 无信号次数 | 光学失败次数 | 后备次数 | 原始日志平均字节 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,m in summary.items():
        lines.append(f"| {name} | {m['mean_move_time']:.3f} | {m['mean_RF_detection_time']:.3f} | {m['mean_channel_switch_time']:.3f} | {m['mean_optical_time']:.3f} | {m['mean_clear_time']:.3f} | {m['mean_no_signal_count']:.3f} | {m['mean_optical_failed_count']:.3f} | {m['mean_fallback_count']:.3f} | {m['mean_journal_bytes']:.0f} |")
    lines+=['','严格逐动作记账：T = L/5 + 5 N_RF + N_switch + 3 N_optical + 2 N_success。按任务用途划分的 role_cost 是对这些相同秒数的另一种分组，不能与物理分项再次相加。','',
            '## 已完成配对比较','',
            '正的“每源改善”表示更快；正的“P95变化”表示尾部变慢。开发门槛通过只代表可进入验证，不能直接晋级。门槛在验证前确定：零漏清、零错误退出，平均每源至少改善1%，P95不恶化超过2%。','',
            '| 阶段 | 用途 | 基线 → 候选 | 配对数 | 全部完整 | 每源改善 | P95变化 | 配对95%区间 | 通过数值门槛 |','|---|---|---|---:|---|---:|---:|---|---|']
    overview=[]
    for p in sorted((ROOT/'reports').glob('*/comparison_*.json')):
        r=json.loads(p.read_text());reg=json.loads((p.parent/'registration.json').read_text());role=reg['role'];ci=r['bootstrap_improvement_95_percent']
        lines.append(f"| {r['phase']} | {role} | {r['baseline']} → {r['candidate']} | {r['pairs']} | {r['all_success']} | {r['improvement_percent']:+.3f}% | {r['p95_change_percent']:+.3f}% | [{ci[0]:.3f}%, {ci[1]:.3f}%] | {r['gate_passed']} |")
        overview.append(dict(phase=r['phase'],role=role,baseline=r['baseline'],candidate=r['candidate'],pairs=r['pairs'],complete=r['all_success'],improvement_percent=r['improvement_percent'],p95_change_percent=r['p95_change_percent'],ci_low=ci[0],ci_high=ci[1],gate_passed=r['gate_passed']))
    lines+=['','完整逐场数据在各阶段 paired_results.csv；EXPERIMENTS.csv 记录假设、代码哈希、配置、命令与采纳决定。开发场景有复用，不把重复运行计为新的独立场景。任何失败都保留；没有通过完整性检查的候选不能以速度晋级。','',
            '## 压力场景与几何检查','',
            '压力集包含边界向外辐射、发射角边界、1000/1500米半径、0/360度读数、聚集、10/16个源、近距离触发和空频道。全向-only、定向-only与混合场景分别报告，不合并成主随机分布成绩。', '']
    for p in sorted((ROOT/'reports').glob('*/PRESSURE_REPORT.md')):lines.append('- '+str(p.relative_to(ROOT)).replace('\\','/'))
    lines+=['','连续覆盖检查不是抽样成功率：格子只能由所有角点的1000米近邻负站局部凸包证明；深度、时间或单元数预算耗尽均记为未证明。19站候选没有取得证书，未进入完整任务计时。','',
            '## 数据、隔离与可复现性','',
            'B题及两附件的路径、大小和哈希在 inputs/SOURCE_MANIFEST.json。题面和接口文本决定本地物理规则；场景生成的面积分布、源类型比例、半径分布和空间误差模型只是本地实验假设，不称为官方分布。', '',
            '引擎、策略和结束后评估器分进程。策略入口移除继承的种子/任务命令行参数，运行时阻止文件读取、目录枚举、额外网络、子进程及引擎导入。输入仅为配置、合法历史动作和接口响应。纯反馈重放不读取真值，不导入场景引擎，必须重现动作序列。','',
            '同位置误差固定，不按检测调用次数重新抽取，也不把重复测量当作独立噪声平均。主集使用固定空间哈希场；压力集另含平滑误差和固定±1度误差。不同平台的浮点实现可能影响重新生成的精细坐标与哈希误差，原始日志重放提供直接的动作复现依据。','',
            'H0、D8及后续晋级快照都保留。D8早期清单的LF/CRLF差异已按真实运行快照纠正，原声明与核验记录仍保留；见 FAILURES.md。此后每轮先核验全部worker的commit、代码字节和配置字节，验证冻结直接读取实际worker。第三问G的15个冻结源码哈希、配置、报告和入口均已核对未变。','',
            '## 图表','',
            '图表为矢量PDF，数据清单与SHA-256见各图表目录的SOURCES.json。已渲染检查字体、坐标轴、图例及数据范围。']
    for p in sorted((ROOT/'figures').glob('*/*.pdf')):lines.append('- '+str(p.relative_to(ROOT)).replace('\\','/'))
    lines+=['','## 运行方法','',
            '```text','python q4.py --sources 14 --seed 1 --replay-check','python code/verify_freeze.py','python -m unittest discover -s tests -v','python code/verify_exit.py runs/本次目录/requests.jsonl','```','',
            '批量复现前运行 python code/setup_workers.py 准备独立Git worktree，然后使用EXPERIMENTS.csv记录的阶段命令（为新运行换一个phase名）。单局入口只需Python标准库；图表生成另外使用reportlab。','',
            '## 结果边界','',
            '数学推导、连续数值几何证书、本地完整任务时间、官方演练及正式成绩相互区分。D_COMPACT 另经用户授权完成一次官方问题4演练，13源全部清除，6813.20秒，每源524.09秒；正式测试0次。详见reports/OFFICIAL_PRACTICE_RESULT.md及OFFICIAL_PRACTICE.md。最终保留集的结果只有实际完成后才写入报告。当前有限模型与终值近似用于动作排序，不证明全局时间最优。']
    (ROOT/'reports/RESULTS_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if overview:
        with (ROOT/'reports/EXPERIMENT_OVERVIEW.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(overview[0]));w.writeheader();w.writerows(overview)
    environment=dict(python=sys.version,system=platform.system(),release=platform.release(),machine=platform.machine(),float_mantissa_bits=sys.float_info.mant_dig)
    (ROOT/'reports/ENVIRONMENT.json').write_text(json.dumps(environment,indent=2),encoding='utf-8')


if __name__=='__main__':build()
