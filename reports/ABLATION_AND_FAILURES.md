# 消融、结构比较与失败报告

各行使用该行登记的同场景配对，不把不同种子批次的均值相减。共享测向和有限前瞻两行来自组件组合实验，相当于分别去掉组合框架的一项组件；并非对最终版本做完整全因子消融。

| 变化 | 批次 | 配对数 | 完整成功 | 每源改善 | P95变化 | 配对95%改善区间 |
|---|---|---:|---|---:|---:|---|
| 放宽连续局部定位护栏 | D8_validation100 | 100 | True | +5.112% | -7.311% | [4.123%, 6.093%] |
| 已有共享测向时，加入有限双RF前瞻 | E_interaction_dev30 | 30 | True | +3.390% | -4.761% | [2.459%, 4.354%] |
| 已有有限前瞻时，加入实际站共享测向 | E_interaction_dev30 | 30 | True | +6.103% | -7.352% | [4.503%, 7.604%] |
| 在组合框架上加入少量光学连续覆盖 | D_COMPACT_validation100 | 100 | True | +1.237% | -1.532% | [1.072%, 1.414%] |

## 没有采用的结构候选

下面列出完整任务证据中未达到预登记门槛的候选。平均每源改善为正才表示变快；不得只凭更好看的轨迹或某个局部指标晋级。

| 批次 | 对照 → 候选 | 完整成功 | 每源改善 | P95变化 |
|---|---|---|---:|---:|
| A_22_dev30 | H0 → H1_22 | True | +1.266% | +4.795% |
| B_rotation_dev30 | H0 → B_rotation | True | -1.091% | +6.622% |
| B_search_stages_dev30 | E_combo → inner_first | True | -9.211% | +13.658% |
| B_search_stages_dev30 | E_combo → search_first | True | -11.567% | +11.529% |
| B_shape_dev30 | E_combo → A22 | True | -0.016% | -1.120% |
| B_shape_dev30 | E_combo → inner950 | True | -0.681% | +0.077% |
| B_shape_dev30 | E_combo → outer1860 | True | -1.306% | -1.465% |
| B_shape_dev30 | E_combo → outerphase | True | -2.491% | +0.739% |
| C_CENTROID_validation100 | compact → centroid | True | +0.518% | +1.185% |
| C_replacement_dev30 | H0 → C1 | True | +0.354% | -0.016% |
| C_replacement_dev30 | H0 → C2 | True | +0.354% | -0.016% |
| C_route_structure_dev30 | E_combo → forecast | True | -0.097% | +0.000% |
| C_route_structure_dev30 | E_combo → route_probe | True | -2.935% | +1.961% |
| C_route_structure_dev30 | E_combo → route_refine | True | +0.039% | -0.484% |
| C_task_routes_fixed_dev30 | compact → task | True | +0.093% | +2.037% |
| D40_validation100 | H0 → D40 | True | +0.669% | -0.857% |
| D_adaptive_optical_dev30 | compact → adaptive | True | +0.298% | -0.300% |
| D_local_decisions_dev30 | E_combo → history | True | +0.228% | -0.223% |
| D_local_decisions_dev30 | E_combo → opt40 | True | -0.492% | +1.045% |
| D_local_decisions_dev30 | E_combo → orders | True | -0.732% | +1.170% |
| D_local_decisions_dev30 | E_combo → replan | True | +0.710% | +1.145% |
| D_progress_dev30 | H0 → cap1 | True | -10.816% | +14.415% |
| D_spacing_dev30 | H0 → b120 | True | -1.693% | +3.108% |
| D_spacing_dev30 | H0 → b160 | True | -3.628% | +5.926% |
| E_all_stops_dev30 | E_combo → E_all_stops | True | -0.602% | -2.568% |

## 几何与实现失败

19站骨架和24个成组删站/邻站外移候选没有取得保守连续覆盖证书，因此没有进入完整任务成绩比较。未证明并不等价于数学上证明不可能。

C_task_routes_dev30初次运行中，两种路线候选分别0/30完整完成，原因是决策过程动态加载模块被隔离器拦截。完整失败日志仍保留，119秒中断时间不是有效成绩。修复模块预加载后，C_task_routes_fixed_dev30重新使用同30个开发场景；它们不算新增独立样本。

早期H0有限推进护栏、D8清单行尾字节差异及精确冻结进程包装器的修复过程见FAILURES.md。所有晋级之前均重新核验完整性；没有用漏清或错误退出换取速度。

本地分布是实验设定。最终保留测试只验收冻结版本，不再用于选参数；官方演练的单场结果单独报告，正式测试0次。
