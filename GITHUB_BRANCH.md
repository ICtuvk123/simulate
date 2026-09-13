# 第四问 GitHub 开发分支

分支：`codex/q4-current-20260913`。这是第四问独立代码库的上传快照。

## 默认运行的版本

默认入口 `q4.py` 和演练脚本读取 `INCUMBENT.json`，使用冻结的 **R2_S22_ML**。冻结算法提交为 `09eaa82dd8fca503ba79b72b544b124d221483f5`；配置与源码哈希见 `configs/R2_S22_ML_FREEZE.json`。

100 场完整本地验证：平均每源 439.29 秒，平均总时间 5672.74 秒，P95 6353.33 秒，全部清除。它们是自建模拟器结果，不是官方成绩；此前的最终 200 场批次未完整完成。

## 下载与运行

```text
git clone --branch codex/q4-current-20260913 --single-branch https://github.com/ICtuvk123/simulate.git q4
cd q4
python q4.py --sources 14 --seed 1 --replay-check
```

本地单局只需要 Python 3.10 或更新版本及标准库。输出位置会显示在终端；打开该次运行的 `replay.html` 查看过程。若 Windows 的 `python` 命令不可用，可使用已安装 Python 的完整路径。

人工运行官方演练可打开 `start_q4_practice.cmd`，队号已填为 `202617201735`。必须由操作者确认处于问题 4 的演练页面；详细步骤见 `Q4_PRACTICE_README.md`。本次上传本身没有启动任何官方测试。

## 当前开发状态

`code/`、`configs/` 包含历史候选和正在开展的 R3 搜索成本优化；不等同于冻结最佳版本。R3 初始上传包含实验计划、现实截止时间控制和候选快照工具；并行研发中尚未整合的候选不在此初始上传内。`configs/R3_EXPERIMENT_PLAN.json` 的时间是原研发轮的绝对截止时间，后来重新实验需另行登记预算和未消耗种子。

`frozen/R2_S22_ML/` 是可复现的默认版本。改变实验代码不会自动替换它。方案说明见 `reports/ACTIVE_ALGORITHM.md`，完整配对表见 `reports/R2_S22_ML_val100/paired_results.csv`。

日常新生成的 `runs/`、演练日志与发布 ZIP 不上传 Git；部分历史汇总记录已经在版本库中。需要逐局原始证据时使用另行保存的证据包。禁止把未包含的原始日志当作已经随仓库交付。
