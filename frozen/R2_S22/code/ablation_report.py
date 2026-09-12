"""Report completed paired component studies without pooling reused seeds."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def build():
    comparisons=[
        ('放宽连续局部定位护栏','D8_validation100','H0','D8'),
        ('已有共享测向时，加入有限双RF前瞻','E_interaction_dev30','E_shared','E_combo'),
        ('已有有限前瞻时，加入实际站共享测向','E_interaction_dev30','E_pair','E_combo'),
        ('在组合框架上加入少量光学连续覆盖','D_COMPACT_validation100','E_combo','compact'),
    ]
    lines=['# 消融、结构比较与失败报告','','各行使用该行登记的同场景配对，不把不同种子批次的均值相减。共享测向和有限前瞻两行来自组件组合实验，相当于分别去掉组合框架的一项组件；并非对最终版本做完整全因子消融。','',
           '| 变化 | 批次 | 配对数 | 完整成功 | 每源改善 | P95变化 | 配对95%改善区间 |','|---|---|---:|---|---:|---:|---|']
    for label,phase,base,candidate in comparisons:
        p=ROOT/'reports'/phase/f'comparison_{base}_{candidate}.json'
        if not p.exists():continue
        r=json.loads(p.read_text(encoding='utf-8'));lo,hi=r['bootstrap_improvement_95_percent']
        lines.append(f"| {label} | {phase} | {r['pairs']} | {r['all_success']} | {r['improvement_percent']:+.3f}% | {r['p95_change_percent']:+.3f}% | [{lo:.3f}%, {hi:.3f}%] |")
    lines+=['','## 没有采用的结构候选','','下面列出完整任务证据中未达到预登记门槛的候选。平均每源改善为正才表示变快；不得只凭更好看的轨迹或某个局部指标晋级。','',
            '| 批次 | 对照 → 候选 | 完整成功 | 每源改善 | P95变化 |','|---|---|---|---:|---:|']
    for p in sorted((ROOT/'reports').glob('*/comparison_*.json')):
        r=json.loads(p.read_text(encoding='utf-8'))
        if r['gate_passed']:continue
        lines.append(f"| {r['phase']} | {r['baseline']} → {r['candidate']} | {r['all_success']} | {r['improvement_percent']:+.3f}% | {r['p95_change_percent']:+.3f}% |")
    lines+=['','## 几何与实现失败','','19站骨架和24个成组删站/邻站外移候选没有取得保守连续覆盖证书，因此没有进入完整任务成绩比较。未证明并不等价于数学上证明不可能。','',
            'C_task_routes_dev30初次运行中，两种路线候选分别0/30完整完成，原因是决策过程动态加载模块被隔离器拦截。完整失败日志仍保留，119秒中断时间不是有效成绩。修复模块预加载后，C_task_routes_fixed_dev30重新使用同30个开发场景；它们不算新增独立样本。','',
            '早期H0有限推进护栏、D8清单行尾字节差异及精确冻结进程包装器的修复过程见FAILURES.md。所有晋级之前均重新核验完整性；没有用漏清或错误退出换取速度。','',
            '本地分布是实验设定。最终保留测试只验收冻结版本，不再用于选参数；官方演练的单场结果单独报告，正式测试0次。']
    (ROOT/'reports/ABLATION_AND_FAILURES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':build()
