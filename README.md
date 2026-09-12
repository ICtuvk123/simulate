# 第四问本地模拟与算法研发包

默认入口始终加载 `INCUMBENT.json` 指向的冻结源码和配置。实验候选位于 `code/`、`configs/`；修改实验候选不会替换默认运行的冻结算法。第三问 G 保持独立，不由本包覆盖。

## 单局运行与回放

已在 Windows / Python 3.12 验证。单局模拟、策略、核验和离线回放仅使用 Python 标准库。

```text
python q4.py --sources 14 --seed 1 --replay-check
```

`--sources` 可取10至16，省略时由本地引擎生成。`--seed` 只交给引擎，不交给策略。`--scenario` 可取 `uniform`、`boundary`、`clustered`；`--source-mix` 可取 `mixed`、`omni`、`directional`。这些是自建分布，不是官方场景设置。

结果写入新建的 `runs/时间戳与随机编号/`。打开其中 `replay.html` 即可离线播放、逐步查看反馈、选择频道及检查时间分项。真值默认隐藏；仅可在结束后的回放中手动显示。

没有 `python` 命令时，可将上述命令的 `python` 替换为现有 Python 解释器的完整路径。

## 核验

```text
python code/verify_freeze.py
python -m unittest discover -s tests -v
python code/verify_exit.py runs/本次目录/requests.jsonl
python code/audit.py runs/本次目录/requests.jsonl
```

退出核验从实际 accepted 响应重建，不接受计划站和预测反馈。最后一条命令进行纯反馈动作重放。重放某个历史版本时，应使用对应运行的源码快照或对应冻结版本；默认 `--replay-check` 会随该版本一起运行。

## 批量配对复现

批量实验另需 Git。执行 `python code/setup_workers.py` 建立四个独立 worktree。若分享包不含Git记录，脚本会在本包目录创建用于复现的本地仓库。已有worker有改动时会停止，不覆盖它们。

用 `EXPERIMENTS.csv` 中记录的命令运行配对实验，并给 `--phase` 取一个新名字，避免覆盖历史结果。不要将最终保留测试集用于继续挑选参数。每局原始日志、实际执行源码快照、结束后真值、独立核验和指标保存在 `runs/`。

## 资料

- `reports/RESULTS_REPORT.md`：当前结果、比较、边界与证据索引。
- `reports/ANALYSIS_MODELING_REPORT.md`：规则迁移与几何模型。
- `GOAL.md`、`EXPERIMENTS.csv`、`INCUMBENT.json`、`FAILURES.md`、`NEXT.md`：持续研发记录。
- `frozen/`：经过验证的历史版本及当前版本。
- `figures/`：矢量图表和数据来源清单。
- `OFFICIAL_PRACTICE.md`：独立的人工演练操作说明。

本轮仅运行自建本地模拟器。`q4.py` 和实验脚本不会连接官方软件。官方演练入口是单独的 `official_practice.py`，需要操作人员先在官方界面选择“问题4演练测试”，再显式手动运行；它在本轮未执行官方连接。没有正式测试流程。
