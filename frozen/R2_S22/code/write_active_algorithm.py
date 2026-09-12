"""Render the active algorithm description from the actual frozen options."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def write():
    incumbent=json.loads((ROOT/'INCUMBENT.json').read_text());freeze=json.loads((ROOT/incumbent['freeze']).read_text())
    options=json.loads((ROOT/incumbent['configuration']).read_text());base=(ROOT/'reports/Q4_ALGORITHM.md').read_text(encoding='utf-8')
    if options.get('route_centroid'):
        base=base.replace('否则当前 E_COMBO 用最小包围圆中心作路线代理。',
                          '否则当前冻结版本用保守位置多边形的面积重心作全局路线代理。重心仅影响任务顺序，不是源位置结论；最小包围圆仍用于定位精度与保证清除判断。')
    header=['# 当前冻结第四问算法','',f"版本：**{incumbent['version']}**。执行控制器源码 commit：`{freeze['commit']}`。",'',
            f"配置：`{incumbent['configuration']}`；源码：`{incumbent['code_directory']}`；逐文件哈希：`{incumbent['freeze']}`。",'',
            '| 功能 | 当前设置 |','|---|---|',
            f"| 连续覆盖骨架 | 原点 + {options['inner_count']} 内环 + {options['outer_count']} 外环 |",
            f"| 内外环半径 | {options['inner_radius']} / {options['outer_radius']} 米 |",
            f"| 连续局部任务护栏 | {options['max_tasks_before_search']} 次后推进未知频道搜索 |",
            f"| 有限两RF前瞻 | {bool(options.get('lookahead'))} |",
            f"| 真实搜索站共享测向 | {bool(options.get('shared_bearing'))} |",
            f"| 少量光学点连续覆盖 | {bool(options.get('compact_optical'))} |",
            f"| 首端反馈后再比较光学覆盖 | {bool(options.get('compact_after_first'))} |",'',
            '以下完整保留主体规则、几何证明、评分模型与调度方法。末尾补充表中实际开启的光学覆盖模块；未开启的实验候选不属于默认算法。','']
    appendix=[]
    if options.get('route_centroid'):
        header.insert(-2,'全局源任务代理已启用面积重心；有限前瞻中的离开方向估计仍沿用原规则，没有把预测重心加入任何位置或退出证书。')
    if options.get('compact_optical'):
        appendix=['','## 当前启用的补充：有完整覆盖保证的少量光学点','',
                  '对已经缩小的保守位置多边形，尝试沿长轴及多边形边方向建立外包矩形。将矩形划分为不超过4个小矩形，在每格中心安排光学点；每格半对角线必须不超过20米减余量。多边形顶点全部位于外包矩形内，每格又完全位于对应光学圆内，因此这些光学点的并集连续覆盖整个保守区域。这是几何保证，不是对少量假设位置进行抽样检查。','',
                  '枚举这些点的访问顺序，按与历史相容的有限位置假设估计移动、失败光学3秒、成功清除额外2秒，以及离开至下一任务的时间。失败分支完整保留。只有预计完整剩余时间低于继续RF计划时才执行；成功立即停止，若走完全部有证书的光学点仍失败，则报告错误，禁止声称该源已清除。','',
                  '每个覆盖计划保存外包矩形、正交坐标轴、网格数量、半对角线、多边形与实际点集见证。独立事后审计重算几何关系，并核对区域仍包含本地真实源。清除动作始终以接口真实响应更新状态，不改变测向频道。','']
        if options.get('compact_after_first'):
            appendix+=['当前配置会在开始一组双侧RF之前，以及第一端真实反馈之后，重新比较光学完整覆盖与剩余RF动作。剩余RF评分包含第二端无信号、direction、near；如果第一端已经真实无信号，第二端预测无信号还必须计入合法双负截线带来的收益，不能把这个分支遗漏后人为抬高RF成本。预测只用于选择动作。','']
        else:appendix+=['当前配置只在开始一组双侧RF之前比较这套光学覆盖。第一端反馈后额外比较的候选尚未由此配置启用。','']
    destination=ROOT/'reports/ACTIVE_ALGORITHM.md';destination.write_text('\n'.join(header)+base+'\n'.join(appendix),encoding='utf-8')
    return destination


if __name__=='__main__':print(write())
