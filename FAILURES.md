# 失败、回退和限制

- 初始仓库路径上层为D盘级仓库且所有权不符；未修改全局Git信任设置，改建独立Q4仓库。
- 既有Poppler路径不存在，已改用已安装pypdf读取实际PDF；三个原文件路径、大小和SHA256记录在inputs/SOURCE_MANIFEST.json。

任何算法失败均保留原始运行，不从统计剔除。

## H0冒烟1：发现16个后误触发搜索耗尽护栏（已修复，未冻结）

运行20260912T081007157473Z-8c61ee5d，seed=1，发现16个但只清除12个时安全停止，没有错误exit。原因为“发现达到16可停止搜索”之后仍用unknown非空触发骨架耗尽错误。修复为只有已发现总数不足16时检查该护栏；16个已发现后继续清除剩余任务。保留失败原始日志，重跑同一冒烟检查，不计入30个开发集。

## A：22站单独替代，未晋级
30组全部清除，平均每源下降约1.27%，但P95上升约4.80%，超过2%门槛。少扫描的收益被更多定位移动部分抵消；保留候选及原始数据，不替换H0。

## D：更宽双侧间距未采纳
b=120与160米的30组均完整清除，但平均每源与P95都变差；保留b=80的H0。b=40仅开发筛选通过，冻结候选后进入新的100组验证，尚不替换当前最佳。

## D40独立验证未达到晋级门槛
100组全部完整清除与重放通过；平均每源下降0.669%，不足预登记1%门槛，95%配对区间[-0.440%,1.801%]，P95下降0.857%。不晋级，不改变INCUMBENT。验证种子410001–410100已消耗，不再用于新候选选择。
# 2026-09-12 08:49 UTC：C 实际停靠替换与 B 整环旋转

C1/C2 均 30/30 完成，平均每源只下降 0.3537%，未达 1% 门槛。C2 与 C1 的虚拟结果相同，现实平均耗时由约 5.79 秒增加至 7.78 秒。均不晋级。

B 根据初始已知目标旋转完整骨架，30/30 完成，但平均每源恶化 1.0907%，P95 恶化 6.6223%。初始路径预测下降不等于完整任务时间下降，不采纳。
# 2026-09-12 09:16 UTC：D8 哈希清单纠正

严格冻结核验发现 D8 预验证清单取自主目录，9 个文件与实际 worker 副本仅有 LF/CRLF 字节差异。检查了全部 200 个验证运行清单：实际运行代码哈希完全一致，且 frozen/D8 中逐文件字节与这些真实运行快照一致。原始清单保存在 reports/D8_FREEZE_ORIGINAL_MANIFEST.json；D8_FREEZE.json 现使用真实运行快照的哈希，并保留原声明字段与纠正说明。H0 的原冻结哈希一直通过。

这属于溯源记录缺陷，未改变算法或删除任何失败局。增加了运行前所有 worker 的 commit、代码字节和配置字节一致性检查；后续验证冻结直接读取实际 worker，而非主目录。默认 Q4 入口已确认从冻结源码目录加载，后续实验修改不会替换交付入口的核心算法。

## D_local_decisions_dev30
历史正测站候选仅改善0.2284%，首端direction后重规划改善0.7105%；双顺序和40米光学候选平均变慢。四项均未达到1%门槛，未晋级。全部150场成功且纯反馈重放通过。

## 冻结版本评估驱动隔离检查
最早H0冻结的进程包装器没有后来增加的命令行清理与I/O限制。源码核查未发现H0策略读取场景参数，后续主验证H0已使用相同的受限包装器。直接调用旧快照的驱动冒烟9–10发现这一隔离缺口后，未将其用作算法晋级依据。冻结评估驱动改为所有版本共用受限包装器，先清理参数，再加载未经修改的冻结控制器；包装器哈希单独登记。11–12的四次冒烟全部完整清除与重放通过。旧冻结源码保留不改。

## C_route_structure_dev30
单点/双点路线重插仅改善0.0392%；补测点作为路线代理使平均每源慢2.9352%且平均现实耗时由4.55秒增至12.65秒；预测停靠互补扫描慢0.0970%，计算耗时约翻倍。全部120场完整清除与重放通过，三项均未晋级。

## B_search_stages_dev30
优先内环使平均每源慢9.2110%、P95慢13.6579%；先搜完再集中清除慢11.5668%、P95慢11.5290%。全部90场完整清除和重放通过，两项回退。其结果支持继续联合搜索与清除，而非拆成顺序阶段。

## D_adaptive_optical_dev30 未晋级
首次RF后改选完整光学覆盖，30对全部成功；平均每源改善0.2982%，低于预登记1%门槛，保留D_COMPACT。

## C_task_routes_dev30：模块加载被隔离器拒绝
初始候选在决策循环内动态导入task_routing，触发禁止文件读取的运行时护栏。两个候选各30/30中断，原始日志与总表全部保留。它们未完成任务，119秒不是有效完整场景成绩。基线30/30正常。修复为控制器加载阶段预导入，不放宽隔离器；修复后以新阶段名重新运行同30个开发场景，不声称独立新样本。

## C_task_route 修复后仍未晋级
修复后30/30完整清除，但每源改善0.093%，P95恶化2.037%，未满足均值和P95门槛；现实成本约为基线2.4倍，回退。面积重心候选单独进入新验证。

## C_CENTROID 独立100场验证未晋级
开发30场改善3.039%，但100个新场景仅改善0.5176%，P95恶化1.1853%，配对95%区间[-0.6546%,1.6594%]。全部100/100完整清除，仍低于1%门槛，保留D_COMPACT。不能用开发成绩替代独立验证。

## 交付复现路径修复
配对分析原先读取日志登记的原机器绝对目录，搬到同学电脑可能找不到文件。现改为当前证据目录runs/run_id，并拒绝缺少整对注册场景或重复变体行。53项回归测试通过，最终200对统计重算完全一致；未修改策略或冻结配置。
# 第二轮新增记录

- R2_A_dev30：窄截线候选30/30完整，纯反馈重放与独立退出核验全部通过。平均每源464.502→463.720秒，仅改善0.168%，未达到1%门槛；P95下降0.384%，保留候选供消融，未替换D_COMPACT。原始60局均保留。增加可选动作并不自动产生显著完整场景收益。
# Round 2 development rejection log (2026-09-12)

- R2_D_dev30: continuous negative-history contraction cleared all 30 paired scenes, but mean per-source improvement was 0.6057%, below the pre-registered 1% gate; P95 total changed +0.0621%. Keep disabled in incumbent. Degenerate-polygon witness acceptance found during code review was fixed before promotion; all 60 original runs were independently re-audited and feedback-replayed with the hardened implementation. No new scenes are claimed by this re-audit.
- R2_AR_dev30: narrow probes plus reused negative station improved mean per-source time by 0.1022% on the same 30 development scenes, with a paired bootstrap interval spanning zero. All 60 runs complete with valid replay/exit. Do not promote.
- R2_B_dev30: before / after-first / both bounded partial-optical variants changed mean per-source time by -0.0124% / +0.0612% / -0.0086% improvement. All 120 runs complete and independently exit-verified; none passes the 1% gate. Added attempts sometimes replace RF yet add a longer optical detour. These are repeated development cases, not independent validation.
