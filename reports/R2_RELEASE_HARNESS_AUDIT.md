# 发布入口、归档复现与证据范围只读审计

审计时间：2026-09-12 15:15--15:24 UTC。读取主工作树 `D:/computer_learning/jammer_search_q4_r2`，初始提交 `ce14993fecf32fda17398b55dad59833d1072914`，后续主工具/文档继续更新；本次实际读取文件的 SHA-256 见 `R2_RELEASE_HARNESS_SCAN.json`。没有修改主文件、运行模拟、执行官方动作、创建归档或使用最终场景选择参数。

逐项读过本轮指定的 `code/reproduce_run.py`、`code/run_r2_final_holdout.py`、`code/package_release.py`、`code/evidence_scope.py`、`code/setup_workers.py`、`q4.py`、`official_practice.py`；为追踪实际调用链，还读了 `snapshot_case.py`、`frozen_policy_worker.py`、`frozen_experiment.py`、`practice_transport.py` 及 `replay_html.py` 的入口导入。结论不扩展成对未读工具的审查。

## 实际发现：证据范围检查漏掉无 run_id 列的 CSV 阶段

**P2，发布完整性检查漏洞，当前原始材料未因此缺失。** `evidence_scope.py:8`--`:17` 仅从 `paired_results.csv` 的 `run_id` 列收集引用。实际存在十个当前轮次阶段，其 CSV 没有该列，而同目录 `runs.jsonl` 明确包含 run_id：

- `R2_B_ablation10`：30 个；
- `R2_B_local10`、`R2_B_smoke10`、`R2_B_strip10`、`R2_B_strip_minimal10`、`R2_F_rollout10`、`R2_F_rollout12_10`、`R2_LF_integration10`、`R2_MD_smoke10`、`R2_SCAN_COMMIT10`：各 20 个。

共 210 个引用会被原检查漏数为零。只读核对发现这 210 个 `runs/<id>/manifest.json` 当前全部存在，故没有观察到这些记录已经丢失；但若其中一个缺失，原检查依然可能把该阶段视为完整。

**修复已独立回验。** 主任务在 `bcd8a87ffd2f42c74f484edc1c0e2a7909c20a8e` 修复此问题；我再次只读检查 `evidence_scope.py:12`--`:19`，确认按阶段对 CSV、`runs.jsonl` 与 `worker*.jsonl` 的 run_id 取并集，`:24`--`:26` 分别记录 CSV/JSONL 引用数。修复后文件 SHA-256 为 `26b289fa0ae10718eb7b0fb6117873dd51a7b5d9f8d6d16483dad3d1029d8f41`。现有生成结果包含 67 个阶段，当前 R2 原始记录完整；其中 MD 阶段已由原来的零引用变为 CSV=0、JSONL=20、包含原始记录=20、缺失=0。主任务报告三个对应回归测试通过；本审计未重复运行测试，没有修改主代码。

原扫描 JSON 保留修复前源码快照，以上哈希标明修复后的差异。此检查器仍以存在 `paired_results.csv` 的阶段为枚举范围，不应把它解释为任意目录下全部实验文件的自动发现器；本次没有识别出已完成却无 CSV、因而被漏掉的实际阶段。最终保留集正在运行，不在此快照中提前宣称其证据已齐全。

## 归档复现只走本地隔离引擎

`reproduce_run.py:13` 要求单个 ROOT/runs 下的 run_id，拒绝路径越界；`:26`--`:36` 要求本地 engine_configuration，对逐个 Python 源文件验证 basename 与 SHA-256，可从原 source 目录或按内容哈希去重的 source_objects 恢复。它复制归档源码到独立 reproduction/snapshot/code，不覆盖原记录。

`:38`--`:47` 把原场景配置交给 `snapshot_case.py` 作为评估/引擎输入，同时将用途明确登记为 reproduction、独立新场景数量为零。`:52`--`:62` 只在结束后比较源场景、完整请求序列、纯反馈重放和独立退出。没有实际执行原场景的测试在本审计发生。

`snapshot_case.py:10` 优先导入指定归档 code 的 run_case；`:14` 清除场景 CLI，并为运行绑定隔离 wrapper。`frozen_policy_worker.py:12`--`:26` 再清 CLI、不给决策器场景配置，使用进程管道作为 Client 的显式 transport，DecisionGuard 内执行归档 Q4Controller；其 engine_main 只调用本地 q4engine。文件中不存在调用 official_practice 入口的路径。该工具是用既有本地场景复现，不宣称它增加独立验证样本。

## 最终保留集与并发边界

`run_r2_final_holdout.py:18`--`:41` 先检查指定 200 个最终种子是否已经消耗、要求 incumbent 已验证、逐版本验证冻结哈希，再以独占创建方式封存选择记录。执行后只比较/记账，不晋级参数，也不修改算法。

`frozen_experiment.py:16` 起核对四个 worker 的冻结源码/配置一致性以及各算法 q4engine 哈希相同；登记 wrapper 哈希与任务分配。它并行的是独立完整场景，每个场景内部仍经单个同步 pipe 逐次动作，没有把不同新动作并发发送到同一局。

`setup_workers.py:11`--`:34` 只做本地 Git init/commit/worktree/checkout：没有 clone、fetch、remote 或网络依赖。现有 worker 必须属于同一个 Git common directory 且干净；工作目录限制在规定的 worker 父目录内。导出包首次初始化使用本地说明性 Git identity，不读取账号。`checkout-index --force` 在脏工作树检查之后执行。本审计没有调用 setup。

## 默认入口与手动官方入口分离

`q4.py:18`--`:29` 默认读取 INCUMBENT 指向的冻结配置和源码，通过完整性核验后加载本地 run_case。开头加载的 replay_html 仅导入 argparse/json/pathlib，没有在选择冻结路径前预加载控制器或网络 transport。即使显式选择自定义配置，入口依然调用本地 run_case。没有官方 URL 参数，也不导入 official_practice。

`official_practice.py` 是单独执行入口，需要同时提供 robot-id 和精确的 `--confirm-practice I_HAVE_SELECTED_PRACTICE`（`:11`--`:14`），任何连接前先核验冻结文件。`practice_transport.py:14`--`:20` 只接受数字回环 HTTP origin，不允许用户名、密码、路径、查询串或 fragment；`:23`--`:34` 只访问四个公开接口。官方原始日志写到独立 `official_practice_logs`。

必须保留的边界：这是一项人工确认，公开 API 没有模式查询，因此程序不能验证官方 UI 实际选中了演练；它不能被描述为从技术上绝不可能连接错误模式。文档 `OFFICIAL_PRACTICE.md:6` 已明确要求人工核对。默认本地入口不会执行它，本轮审计没有任何官方连接。

## 打包选择与账号/官方原日志检查

`package_release.py:29`--`:37` 使用明确的 Q4 目录与根文件列表，不枚举用户 HOME、账号配置、.git、官方原始日志目录或其他 worktree；safe_files 还检查解析后的路径留在 Q4 根内。runtime 中删除批次 worker/case/job 大记录；证据包在 `:53`--`:64` 只收 ROOT/runs 中有 manifest 的目录，逐源文件验证 hash，原 JSON/JSONL 按原字节写入，源码按 hash 去重。官方摘要可以保留，官方原始 `requests.jsonl` 不在目录选择范围。

我没有执行打包函数，因为它会写主目录证据范围文件和归档。本次另行只读扫描了当前被选择的 1571 个目录文件：没有账号/密钥/密码/cookie/token 可疑文件名，没有非空敏感键字面量，没有被选中的 official_practice_logs 路径。仅有附件2四个 robot_id 字面量触发非本地 ID 检查，已读周围内容确认其属于公开协议的“请求示例”，并非本队账号；报告和扫描输出不记录其值。根文件中的账号相关内容仅命中手动演练说明的占位队号。

另独立扫描了此时符合 evidence 选择条件的 **1946 个 run manifest**：全部有本地 engine_configuration；其 requests 日志中检查了 **1,076,528 个 robot_id 字面量，全部为 local-robot**，未发现官方账号或非本地请求记录。报告保留的官方历史摘要只有结果、原日志相对路径、大小/哈希等出处信息，未包含官方原始请求正文。

这是运行目录和打包输入在审计时的快照；最终保留测试仍可能继续产生新文件。它不能替代主任务在全部运行结束后对最终 ZIP 的条目和哈希验收，也不能把未生成的 ZIP 写成已检查。

## 历史缺失记录的披露

现有 `reports/EVIDENCE_SCOPE.json` 明确列出历史阶段 missing_run_ids 并说明“缺少原始记录的历史报告仅作上下文”。只读快照中有 30 个非 R2 历史阶段、合计 3242 条缺失引用（不是去重后的场景数）。`README.md:45`--`:56` 说明 runtime/evidence 的分别用途、源码恢复、历史缺原始记录与旧场景复现不计新样本。当前轮次无 run_id CSV 的漏检已按上述方式修复；正在执行的最终测试与最终 ZIP 仍须在结束后另行验收。

审计产物：本报告、只读扫描脚本 `R2_RELEASE_HARNESS_SCAN.py` 与结果 `.json`。没有导入或调用任何模拟执行入口；只读脚本只检查文件/元数据并写自身独立工作树的结果。
