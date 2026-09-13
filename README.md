# 第四问本地模拟与算法包

GitHub 新分支的下载、默认版本与当前开发状态见 [GITHUB_BRANCH.md](GITHUB_BRANCH.md)。

当前冻结：**R2_S22_ML-validated-20260912**，执行源码 `09eaa82dd8fca503ba79b72b544b124d221483f5`。

新验证集 100/100 场完整清除。平均每源 **439.29 秒**，平均总时间 **5672.74 秒**，P95 **6353.33 秒**，最坏 **6487.78 秒**。平均策略现实耗时 **12.17 秒**，批量并行环境下测量。

本轮200场×3方案的最终保留批次发生中断：304次运行已有记录、296次未完成，未通过整批最终验收。以上数字来自完整的新100场验证，不冒充最终200场成绩。中断记录和全部注册位置均保留。

这里是自建本地场景成绩，分布是假设；完整配对、失败与分项时间见 `reports/R2_S22_ML_val100/`。本轮没有运行官方演练或正式测试。第三问 G 和原目录 D_COMPACT 保持独立。

## 运行与回放

安装 Python 后，在解压目录运行：

```text
python q4.py --sources 14 --seed 1 --replay-check
```

单局运行仅使用 Python 标准库。`--sources` 为10至16，省略时由本地引擎生成；`--seed` 只交给引擎。`--scenario` 可取 uniform、boundary、clustered；`--source-mix` 可取 mixed、omni、directional。这些开关不是官方场景设置。

打开输出目录 `runs/编号/replay.html`，即可离线查看路线、逐步反馈和计时。真值默认隐藏，只供结束后评估。默认入口严格加载 `INCUMBENT.json` 中的冻结源码、配置与哈希；更改实验目录不会替换默认版本。

## 核验

```text
python code/verify_freeze.py
python -m unittest discover -s tests
python code/independent_exit.py runs/编号/requests.jsonl
python runs/编号/source/audit.py runs/编号/requests.jsonl
```

最后一条用该局实际源码做纯反馈重放；不能用后来改变过的控制器去要求旧日志动作相同。若只有压缩后的证据包，先恢复源码快照。退出核验只接受实际 accepted 响应，不接受预测点和计划站。

## 方案与结果

- `reports/ACTIVE_ALGORITHM.md`：与当前实际冻结开关一致的算法说明。
- `reports/R2_RESULTS_REPORT.md`：本轮完整结果、10至16源分层及压力测试；`R2_ACTION_ABLATIONS.md`、`R2_ACTION_FAILURES.md`保留拒绝方案和原因。
- `reports/R2_S22_ML_val100/paired_results.csv`：逐场完整指标；同目录比较文件包含配对区间。
- `examples/r2/`：真实路线对照，保留典型、最不利和最大改善案例。
- `GOAL.md`、`EXPERIMENTS.csv`、`SEEDS.csv`、`FAILURES.md`、`NEXT.md`：预算、假设、种子用途和未晋级候选。
- `frozen/R2_S22_ML/configs/R2_S22_ML.json`、`configs/R2_S22_ML_FREEZE.json`：冻结配置与全部源码哈希。
- `OFFICIAL_PRACTICE.md`：人工操作官方演练的独立说明；本地入口不会连接官方软件。

历史 D_COMPACT 曾在另行授权下完成一次官方问题4演练：13源全部清除、6813.20秒、每源524.09秒。该记录不能作为本轮版本的官方成绩。正式测试累计0次。

## 分享包与复现

日常运行只需 runtime.zip。需要复核原始记录时，将 evidence.zip 的 `jammer_search_q4` 目录合并到运行包同名目录，再执行：

```text
python code/restore_evidence.py --verify-only
python code/restore_evidence.py
```

第一条检查日志和去重源码对象的哈希；第二条恢复每局原始源码，不覆盖内容不同的文件。开发、验证和最终保留集按注册文件分别统计，重复使用的开发场景不计为独立验证。历史报告若没有随包原始记录，会在证据范围清单中明确列出。

要重新执行证据中的某一局，可运行 `python code/reproduce_run.py 原run_id`。它校验并使用该局的原始源码与本地场景配置，在独立目录执行，然后比较源场景、整条动作序列、反馈重放和退出证书。该操作明确登记为旧场景复现，不增加独立测试数量；场景参数只交给引擎。若只需核查动作逻辑，用上面的纯反馈重放命令即可。

批量实验需要 Git 和四个独立 worktree，见 `code/setup_workers.py`。历史实验必须使用注册的对应源码和配置；运行新批次时另取名称，禁止覆盖原始记录或用最终保留集继续选参数。
