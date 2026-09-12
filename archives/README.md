# 原始实验记录归档

源码、冻结参数、场景配置、逐场CSV和报告直接保存在项目目录中。原始动作日志、运行结果和每次运行的源码快照完整存放于以下归档，便于历史复核：

- `time_push_20260912_runs.tar.gz`：G+ 选型及验证阶段。
- `gplus_next_20260912_runs.tar.gz`：后续优化候选及验证阶段。

`MANIFEST.json` 记录归档SHA256、文件数、运行数和原始大小。打包时逐项核对归档内每个文件与本地原件的SHA256；本地原文件保留。重复源码快照一并保存，没有仅保留有利场景。

新克隆的项目可以直接运行算法、自助测试和已有的统计分析。若要按旧run_id逐动作重放历史实验，先在**项目根目录**恢复对应归档（目录内应尚无同名历史运行文件）：

```powershell
tar -xzf archives/time_push_20260912_runs.tar.gz
tar -xzf archives/gplus_next_20260912_runs.tar.gz
```

恢复后，原有 `runs/<run_id>/` 相对路径与报告一致。文件字节与原件一致，归档不保留操作系统文件时间或所有者。两个冻结源码目录设置为禁止Git行尾转换，避免Windows的自动转换破坏冻结哈希。

后续候选的历史审计入口为：

```powershell
cd gplus_next_20260912
python audit_replay.py validation100
python audit_replay.py stress24
```

重新生成实验请使用新的phase目录，避免覆盖已有报告。独立发布包 `release/Gplus方案_20260912.zip` 已包含运行G+所需的代码与入口，普通使用无需解压本页中的历史记录归档。
