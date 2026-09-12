"""Render the active algorithm description from the actual frozen options."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def write():
    incumbent=json.loads((ROOT/'INCUMBENT.json').read_text());freeze=json.loads((ROOT/incumbent['freeze']).read_text())
    options=json.loads((ROOT/incumbent['configuration']).read_text());base=(ROOT/'reports/Q4_ALGORITHM.md').read_text(encoding='utf-8')
    base=base.replace('本文说明已经实现并验证的 E_COMBO 主体。','本文说明当前冻结配置实际采用的算法主体。')
    base=base.replace('## 3. 25 站定向搜索与空频道证书','## 3. 定向搜索骨架与空频道证书')
    old='固定后备骨架由原点、995 米半径的 8 个等角内环点、1840 米半径的 16 个等角外环点组成，两环零相位一致。外环允许越出目标圆。当前验证版本保留这个 25 站骨架；22 站和多组半径、相位候选虽然部分具有连续几何证书，但没有在完整任务比较中证明更快，故未直接替换。'
    replacement=(f"当前后备骨架为原点、{options['inner_radius']:g} 米半径的 {options['inner_count']} 个等角内环点、"
                 f"{options['outer_radius']:g} 米半径的 {options['outer_count']} 个等角外环点，共 {1+options['inner_count']+options['outer_count']} 站。"
                 f"内外环相位分别为 {options['inner_phase']:g}、{options['outer_phase']:g} 度。外环允许越出目标圆。"
                 '这些位置是有限搜索后备计划；每个频道是否为空仍须由该频道真实负反馈独立证明，不能仅因全部计划站具有几何覆盖就提前退出。')
    if old not in base:raise RuntimeError('Historical search-skeleton paragraph changed; review active documentation')
    base=base.replace(old,replacement)
    base=base.replace('## 5. E_COMBO 的有限前瞻如何选择截线','## 5. 有限前瞻如何选择截线')
    base=base.replace('E_COMBO 在首次','当前方案在首次').replace('当前 E_COMBO 没有启用','当前配置没有启用')
    if options.get('route_centroid'):
        base=base.replace('否则当前 E_COMBO 用最小包围圆中心作路线代理。',
                          '否则当前冻结版本用保守位置多边形的面积重心作全局路线代理。重心仅影响任务顺序，不是源位置结论；最小包围圆仍用于定位精度与保证清除判断。')
    base=base.replace('否则当前 E_COMBO 用最小包围圆中心作路线代理。','否则当前方案用最小包围圆中心作路线代理。')
    base=base.replace('本文的 E_COMBO 框架以本地实验验证；后续 D_COMPACT 已完成一次另行授权的官方演练，见 OFFICIAL_PRACTICE_RESULT.md。正式测试0次。',
                      '本轮当前版本的证据是自建本地场景，未执行官方演练或正式测试。历史 D_COMPACT 曾完成另行授权的一次官方演练，该历史成绩不能当作当前版本的官方成绩，见 OFFICIAL_PRACTICE_RESULT.md。正式测试累计0次。')
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
    if options.get('adaptive_single'):
        appendix+=['','## 当前启用：先做一次 RF，再按反馈重规划','',
                   '原双侧截线仍是可靠后备。额外生成当前位置、区域中心两侧、接近区域的途中及侧向偏移点，剔除同频道真实测过的点和原后备对的端点。点位候选借鉴第三问 G 的几何选点，但不引入 G 的单负圆排除、距离二等分裁剪或全向接收保证。','',
                   '对候选 q 的每个有限假设，计入移动距离/5、5秒检测与真实切频成本。near 分支计入3秒光学和2秒成功清除；direction 分支以正测扇形更新评分副本，能保证清除则计入操作及离开成本；其余 direction 和全部 no_signal 分支计入从 q 出发恢复原来整对探测的完整预测成本，包括已启用光学候选的失败成本。只有其加权剩余成本比原对更低至少配置余量时才选择。','',
                   '实际只执行该点的一次测量，随后返回全局任务调度。实际单次 no_signal 只记录，不裁剪位置，也不假装已经执行后备探测。已有保证清除位置时立即处理；局部轮数护栏、有限光学后备、搜索推进及退出证书不变。对相同假设，no_signal 恢复对的后续路径不依赖新点，只替换到首端的移动距离，因此可以缓存此项减少现实计算量。该缓存已经通过逐动作反馈重放核验。','']
    if options.get('stable_quadrature'):
        appendix+=['','## 当前启用：与多边形顶点表示无关的区域取样','',
                   '评分专用副本先规范化凸包，沿较长包围盒轴计算分段线性截面宽度，精确积分梯形面积，再在等面积分位上选点，并用固定的交替截面分位选第二坐标。相同几何区域插入共线点、循环移动顶点或反向列举，不会改变评分取样。它只稳定有限假设的位置；保守区域、真实观测和退出证明均不因此改变。','']
    if options.get('route_centroid'):
        header.insert(-2,'全局源任务代理已启用面积重心；有限前瞻中的离开方向估计仍沿用原规则，没有把预测重心加入任何位置或退出证书。')
    if options.get('compact_optical'):
        appendix+=['','## 当前启用的补充：有完整覆盖保证的少量光学点','',
                  '对已经缩小的保守位置多边形，尝试沿长轴及多边形边方向建立外包矩形。将矩形划分为不超过4个小矩形，在每格中心安排光学点；每格半对角线必须不超过20米减余量。多边形顶点全部位于外包矩形内，每格又完全位于对应光学圆内，因此这些光学点的并集连续覆盖整个保守区域。这是几何保证，不是对少量假设位置进行抽样检查。','',
                  '枚举这些点的访问顺序，按与历史相容的有限位置假设估计移动、失败光学3秒、成功清除额外2秒，以及离开至下一任务的时间。失败分支完整保留。只有预计完整剩余时间低于继续RF计划时才执行；成功立即停止，若走完全部有证书的光学点仍失败，则报告错误，禁止声称该源已清除。','',
                  '每个覆盖计划保存外包矩形、正交坐标轴、网格数量、半对角线、多边形与实际点集见证。独立事后审计重算几何关系，并核对区域仍包含本地真实源。清除动作始终以接口真实响应更新状态，不改变测向频道。','']
        if options.get('compact_after_first'):
            appendix+=['当前配置会在开始一组双侧RF之前，以及第一端真实反馈之后，重新比较光学完整覆盖与剩余RF动作。剩余RF评分包含第二端无信号、direction、near；如果第一端已经真实无信号，第二端预测无信号还必须计入合法双负截线带来的收益，不能把这个分支遗漏后人为抬高RF成本。预测只用于选择动作。','']
        else:appendix+=['当前配置只在开始一组双侧RF之前比较这套光学覆盖。第一端反馈后额外比较的候选尚未由此配置启用。','']
    destination=ROOT/'reports/ACTIVE_ALGORITHM.md';destination.write_text('\n'.join(header)+base+'\n'.join(appendix),encoding='utf-8')
    return destination


if __name__=='__main__':print(write())
