# 本地搜索模拟器：最新 G 结果

本轮完成 444 次本地模拟，包括 100 个新场景的 F/G 配对独立验证及 8 个压力场景配对，全部清除并通过完整性检查。本轮没有运行官方演练或正式测试。

当前推荐默认 **G**，保留 F 随时作对照。相同的 100 个新场景：

- F：平均总时间 3016.04 秒，236.71 秒/源。
- G：平均总时间 3011.72 秒，236.38 秒/源。
- 平均每局节省 4.32 秒（0.14%），改善区间约 0.04%–0.26%；收益很小。
- G 在 27 场更快、14 场更慢、59 场相同。最坏时间相同，不能声称每场都更快。

详细结果见 `reports/optimization/G_RESULTS.md`，模型和近似边界见 `G_MODEL_NOTES.md`。直接打开 `G_replay.html` 可离线查看完整过程。

运行：`python simulator.py run --strategy G --seed 10001`；对照将 G 改为 F。冻结参数位于 `code/g_policy_presets.py`，新增算法位于 `code/route_search.py`。

以下保留历史 F 及更早结果用于追溯，当前推荐与结论以上文和 G_RESULTS.md 为准。

# 问题三自建模拟器

这是独立的本地测试环境，不需要官方模拟器、不需要登录，也不会连接或启动官方演练与正式测试。

## 2026-09-12：结构改进与指标更正

当前推荐 **F**。本轮 388 次本地运行，100 个新场景的配对验证：
E 整局 3050.62 秒、228.89 秒/源；
F 整局 3033.65 秒、227.63 秒/源。
平均整局改善 0.56%，35 项规则和几何检查通过。
详细结果以 `reports/optimization/F_RESULTS.md` 为准；冻结参数在 `code/f_policy_presets.py`，
代码在 `code/structural.py` 与 `code/structural_geometry.py`。命令行 `--strategy F` 可运行候选；E 保留不变。

题面指标为逐场 `总时间/清除数`。原 E 的上一批 100 场实际为 **229.62 秒/源**，
已经处于 200–300 秒/源范围。此前“整局 200–300 秒不可达”的下界论证不能用于否定这个题面指标。
界面结束后同时显示整局时间和秒/源。`F_replay.html` 可直接打开，不需要 Python。

下方 E 说明和历史结果保留供追溯，默认策略与当前结论以本节和 F_RESULTS.md 为准。

## 打开可视化界面

双击 `start_local_simulator.cmd`。启动后打开 `http://127.0.0.1:8768`。

选择场景编号、策略、分布、接收半径与误差模型，点击“开始本地测试”。运行结束后可播放、暂停、逐步前进后退、拖动时间轴、按频道观察定位区域、缩放平移地图，以及导出包含全部数据的离线 HTML 回放。导出按钮直接保存到对应的 `runs/<run_id>/` 目录，页面显示保存位置和回放链接；复制HTML到别处即可独立查看。

同一编号、源数量、分布、接收半径配置和误差模型会产生相同场景。策略可切换 A/B/C/D/E；不同策略面对相同真实场景、同一固定误差场。当前默认 E：扩大有证明的安全测站范围，结合补测后的重规划、就近连续处理与检测收益筛选。100 个新场景的配对验证中，平均整局时间由 D 的 **3111.70 秒降至 E 的 3002.14 秒**，均全部清除；改善 **3.52%**，配对 95% 区间 **2.84%–4.24%**。最新报告为 `reports/optimization/CONTINUATION_RESULTS.md`；D 的历史结果仍保存在 `RESULTS_REPORT.md`。

“结束后查看真实位置”在回放到最后时才启用。真实坐标不通过机器人动作反馈传递。生成场景与执行反馈在独立进程，控制器只收到四类动作的 JSON 响应。

## 规则

| 项目 | 实现 |
| --- | --- |
| 目标区域 | 半径 1800 米的圆，源数 10–16，各频道互异 |
| 频道 | 1–20；初始测向频道为 1 |
| 初始位置 | (0,0)，东为 x 正向，北为 y 正向 |
| 信号 | 全向；每源接收半径 1000–1500 米 |
| 移动 | 直线 5 米/秒；允许域外检测 |
| 测向 | 停车 5 秒；换 RF 频道另加 1 秒 |
| 测向误差 | 同一位置、同一频道固定；量化前 ±1°，输出两位小数 |
| 强信号 | 距离 ≤5 米：near，无示向度，可直接 clear |
| 光学与清除 | ≤20 米成功，光学 3 秒 + 清除 2 秒；失败仅光学 3 秒 |
| clear 的频道 | 选择清除目标，不改变 RF 频道，不产生切頻时间 |
| 结束 | 主动 exit，无需返航；不会因清完自动提示算法 |
| 预算 | 就绪后 25 分钟窗口，enter 后最多 20 分钟，取较早者；虚拟时间 100 小时 |
| 请求 | enter、measure、clear、exit 四种；串行、幂等、参数与错误检查 |

自建环境省略官方账号登录、联网校时、准备倒计时、限次和加密日志上传。这些是官方平台流程，不影响第三问动作模型。本地界面只使用 8768 端口；机器人连接外部 HTTP 服务的实现已禁用。

题面没有公开实际随机分布、误差函数和浮点舍入细节。因此本地场景分布和误差场是明确的工作假设，不能声称复刻官方隐藏案例。本地日志与统计不能作为官方测试成绩或加密日志使用。

## 命令行

需要 Python 3.10 或以上；核心程序只依赖标准库。

```text
python simulator.py gui
python simulator.py run --seed 101 --strategy B
python simulator.py run --seed 2001 --strategy D
python simulator.py run --seed 6001 --strategy E
python simulator.py run --seed 901 --strategy C --scenario boundary --reception minimum --error-mode plus_one
python simulator.py run --seed 101 --strategy C --depth 3 --beam-width 8
python simulator.py compare
python simulator.py test
```

参数 `--count 10` 至 `--count 16` 可指定评估环境的源数量，算法不读取这个设置。默认按种子生成 10–16 个。

## 算法入口与输出

- `code/engine.py`：自建环境、物理反馈和计时。
- `code/controller.py`：A 固定覆盖/简单交会/最近邻；B 固定覆盖/保守定位多边形/最小包围圆/开放 Held–Karp 路线。
- `code/dynamic.py`：C 动态搜索、顺路测向、共享停靠点、逐频道覆盖证书；支持 1/2/3 步规划与有限宽度候选保留，其时间估计是启发式。
- `code/optimized.py`、`code/local_geometry.py`：D 联合路线、检测收益筛选、最近可清除位置与第二问局部剩余时间选测站。
- `code/policy_presets.py`：独立验证前冻结的 D 参数。算法没有种子或真实源数量参数。
- `code/replanning.py`、`code/reception_geometry.py`：E 重规划与连续鲁棒接收证明；`code/e_policy_presets.py` 是验证前冻结的 E 参数。
- `code/runner.py`：隔离进程运行、日志、事后评估、下界、代码快照。
- `code/coverage.py`：解析圆环覆盖与自适应正方形包含覆盖核验。
- `runs/<run_id>/requests.jsonl`：原始动作请求/响应。
- `runs/<run_id>/result.json`：回放、观测区域、事后真值与统计。
- `runs/<run_id>/source/`：该次运行的代码快照。
- `reports/paired_runs.csv`、`leaderboard.csv`：配对测试逐局数据与统计。

## 已完成验证

19 项单元测试通过；12 个预先列明场景 × 3 个策略的 36 次本地完整运行全部清除，并通过完成证书。训练、验证及压力测试分组见 `reports/benchmark_manifest.json`。

此前六轮优化及最终验证记录 296 次完整本地运行。本轮追加四轮训练、100 场独立配对验证与压力对照，共 **508 次运行**，全部清除并通过完成证明。当前 **26 项**规则与几何检查通过。纯反馈重放结果保存在 `reports/optimization/E_feedback_only_audit.json`，历史 D 审计保存在 `final_feedback_only_audit.json`；重放不加载场景生成器，不读取真值，决策期间禁止文件、网络与进程访问。

`reports/optimization/E_replay.html` 可直接用浏览器打开，不需要 Python。它展示 E 独立验证组时间中位附近的案例。运行新实验需要 Python 3.10 或以上。`E_validation_paired.csv` 可核对逐场差异，`E_leaderboard.csv` 保留所有追加训练方案的统计。

所有计时都是整局总行动时间，不能改称单源均值或电脑运算时间。此前本地验证案例的完美信息下界均值已为 1783.83 秒，不能在这些案例上实现整局平均 200–300 秒。E 尚非已证明的全局最快策略。
