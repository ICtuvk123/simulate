# 第四问计算结果与证据索引

更新时间：2026-09-12T09:48:34.988803+00:00。持续开发任务尚未结束，以 INCUMBENT.json 指向的冻结版本为准。

## 当前已验证版本

版本：`E_COMBO-validated-20260912`；执行源码 commit：`3ab6def11e971722d87de76c498276000279cae3`。默认入口从 `frozen/E_COMBO/code` 加载，不使用正在编辑的实验候选。

| 场景集 | 完整成功 | 平均每源 / s | 平均总时间 / s | P95 总时间 / s | 最坏总时间 / s | 平均现实耗时 / s |
|---|---:|---:|---:|---:|---:|---:|
| E_COMBO_validation100 | 100/100 | 499.455 | 6167.640 | 6805.517 | 7141.174 | 6.711 |

平均每源时间定义为逐场 T/实际源数 的算术平均，不用平均总时间除以平均源数替代。源数只由结束后的评估器提供。P95 使用整场总时间的线性插值经验分位数。现实耗时来自本机并行 worker 中的策略进程，包含决策和日志写入；不同运行批次的系统负载可能不同。

## 当前验证集的实际时间分项

| 方案 | 移动 / s | RF / s | 切频 / s | 光学 / s | 清除 / s | 无信号次数 | 光学失败次数 | 后备次数 | 原始日志平均字节 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D8 | 5196.138 | 1407.100 | 247.820 | 38.100 | 25.400 | 241.610 | 0.000 | 0.000 | 310203 |
| E_combo | 4419.200 | 1420.850 | 264.030 | 38.160 | 25.400 | 244.420 | 0.020 | 0.010 | 327281 |
| H0 | 5600.356 | 1398.950 | 248.120 | 38.100 | 25.400 | 240.250 | 0.000 | 0.000 | 308603 |

严格逐动作记账：T = L/5 + 5 N_RF + N_switch + 3 N_optical + 2 N_success。按任务用途划分的 role_cost 是对这些相同秒数的另一种分组，不能与物理分项再次相加。

## 已完成配对比较

正的“每源改善”表示更快；正的“P95变化”表示尾部变慢。开发门槛通过只代表可进入验证，不能直接晋级。门槛在验证前确定：零漏清、零错误退出，平均每源至少改善1%，P95不恶化超过2%。

| 阶段 | 用途 | 基线 → 候选 | 配对数 | 全部完整 | 每源改善 | P95变化 | 配对95%区间 | 通过数值门槛 |
|---|---|---|---:|---|---:|---:|---|---|
| A_22_dev30 | development | H0 → H1_22 | 30 | True | +1.266% | +4.795% | [-2.400%, 4.436%] | False |
| B_rotation_dev30 | development | H0 → B_rotation | 30 | True | -1.091% | +6.622% | [-4.459%, 2.413%] | False |
| B_shape_dev30 | development | E_combo → A22 | 30 | True | -0.016% | -1.120% | [-2.771%, 2.312%] | False |
| B_shape_dev30 | development | E_combo → inner950 | 30 | True | -0.681% | +0.077% | [-2.912%, 1.346%] | False |
| B_shape_dev30 | development | E_combo → outer1860 | 30 | True | -1.306% | -1.465% | [-2.800%, -0.099%] | False |
| B_shape_dev30 | development | E_combo → outerphase | 30 | True | -2.491% | +0.739% | [-5.124%, -0.446%] | False |
| C_replacement_dev30 | development | H0 → C1 | 30 | True | +0.354% | -0.016% | [-0.249%, 1.357%] | False |
| C_replacement_dev30 | development | H0 → C2 | 30 | True | +0.354% | -0.016% | [-0.249%, 1.357%] | False |
| D40_validation100 | validation | H0 → D40 | 100 | True | +0.669% | -0.857% | [-0.440%, 1.801%] | False |
| D8_validation100 | validation | H0 → D8 | 100 | True | +5.112% | -7.311% | [4.123%, 6.093%] | True |
| D_progress_dev30 | development | H0 → cap1 | 30 | True | -10.816% | +14.415% | [-14.018%, -7.987%] | False |
| D_progress_dev30 | development | H0 → cap4 | 30 | True | +4.478% | -4.740% | [2.698%, 6.147%] | True |
| D_progress_dev30 | development | H0 → cap8 | 30 | True | +4.504% | -6.007% | [2.840%, 6.120%] | True |
| D_spacing_dev30 | development | H0 → b120 | 30 | True | -1.693% | +3.108% | [-2.814%, -0.454%] | False |
| D_spacing_dev30 | development | H0 → b160 | 30 | True | -3.628% | +5.926% | [-6.098%, -1.489%] | False |
| D_spacing_dev30 | development | H0 → b40 | 30 | True | +1.097% | +0.111% | [-1.201%, 3.298%] | True |
| E_COMBO_validation100 | validation | D8 → E_combo | 100 | True | +10.479% | -10.563% | [9.603%, 11.390%] | True |
| E_COMBO_validation100 | validation | H0 → E_combo | 100 | True | +15.243% | -23.242% | [13.903%, 16.624%] | True |
| E_interaction_dev30 | development | E_pair → E_combo | 30 | True | +6.103% | -7.352% | [4.503%, 7.604%] | True |
| E_interaction_dev30 | development | E_shared → E_combo | 30 | True | +3.390% | -4.761% | [2.459%, 4.354%] | True |
| E_pair_dev30 | development | D8 → E_pair | 30 | True | +4.429% | -0.996% | [2.749%, 6.305%] | True |
| E_shared_dev30 | development | D8 → E_shared | 30 | True | +7.113% | -3.689% | [6.002%, 8.191%] | True |

完整逐场数据在各阶段 paired_results.csv；EXPERIMENTS.csv 记录假设、代码哈希、配置、命令与采纳决定。开发场景有复用，不把重复运行计为新的独立场景。任何失败都保留；没有通过完整性检查的候选不能以速度晋级。

## 压力场景与几何检查

压力集包含边界向外辐射、发射角边界、1000/1500米半径、0/360度读数、聚集、10/16个源、近距离触发和空频道。全向-only、定向-only与混合场景分别报告，不合并成主随机分布成绩。

- reports/E_COMBO_pressure14/PRESSURE_REPORT.md
- reports/H0_D8_pressure14/PRESSURE_REPORT.md

连续覆盖检查不是抽样成功率：格子只能由所有角点的1000米近邻负站局部凸包证明；深度、时间或单元数预算耗尽均记为未证明。19站候选没有取得证书，未进入完整任务计时。

## 数据、隔离与可复现性

B题及两附件的路径、大小和哈希在 inputs/SOURCE_MANIFEST.json。题面和接口文本决定本地物理规则；场景生成的面积分布、源类型比例、半径分布和空间误差模型只是本地实验假设，不称为官方分布。

引擎、策略和结束后评估器分进程。策略入口移除继承的种子/任务命令行参数，运行时阻止文件读取、目录枚举、额外网络、子进程及引擎导入。输入仅为配置、合法历史动作和接口响应。纯反馈重放不读取真值，不导入场景引擎，必须重现动作序列。

同位置误差固定，不按检测调用次数重新抽取，也不把重复测量当作独立噪声平均。主集使用固定空间哈希场；压力集另含平滑误差和固定±1度误差。不同平台的浮点实现可能影响重新生成的精细坐标与哈希误差，原始日志重放提供直接的动作复现依据。

H0、D8及后续晋级快照都保留。D8早期清单的LF/CRLF差异已按真实运行快照纠正，原声明与核验记录仍保留；见 FAILURES.md。此后每轮先核验全部worker的commit、代码字节和配置字节，验证冻结直接读取实际worker。第三问G的15个冻结源码哈希、配置、报告和入口均已核对未变。

## 图表

图表为矢量PDF，数据清单与SHA-256见各图表目录的SOURCES.json。已渲染检查字体、坐标轴、图例及数据范围。
- figures/validation/paired_total_times.pdf
- figures/validation/per_source_distribution.pdf
- figures/validation/source_count_strata.pdf
- figures/validation/time_components.pdf

## 运行方法

```text
python q4.py --sources 14 --seed 1 --replay-check
python code/verify_freeze.py
python -m unittest discover -s tests -v
python code/verify_exit.py runs/本次目录/requests.jsonl
```

批量复现前运行 python code/setup_workers.py 准备独立Git worktree，然后使用EXPERIMENTS.csv记录的阶段命令（为新运行换一个phase名）。单局入口只需Python标准库；图表生成另外使用reportlab。

## 结果边界

数学推导、连续数值几何证书、本地完整任务时间、官方演练及正式成绩相互区分。本轮未运行官方演练或正式测试；官方适配器仅通过模拟连接单测，操作说明见OFFICIAL_PRACTICE.md。最终保留集的结果只有实际完成后才写入报告。当前有限模型与终值近似用于动作排序，不证明全局时间最优。
