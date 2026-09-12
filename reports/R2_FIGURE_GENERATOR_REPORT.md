# 第四问实验结果矢量图生成器

独立入口：`reports/plot_phase_results.py`。只读取已结束实验的结果文件，不导入模拟器或决策器、不运行场景、不修改冻结版本。采用 ReportLab 矢量绘图，同一 Drawing 同时导出 PDF 和 SVG；有 pypdfium2 时另外生成 PNG 作版式检查。遵循 `3coding-visual/SKILL.md` 的中文图例、PDF 矢量输出、图内不放大标题和保存来源记录要求。

## 运行方式

在仓库目录执行（替换阶段和一个尚为空的输出目录）：

```powershell
& 'C:\Users\12831\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' reports/plot_phase_results.py --phase-dir reports/R2_LM_dev30 --out figures/r2_lm
```

不指定策略时，堆叠柱和表格展示注册的全部策略，为目录中每个已经通过配对核验的 `comparison*.json` 生成一张差值图。只展示一对时：

```powershell
& 'C:\Users\12831\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' reports/plot_phase_results.py --phase-dir reports/R2_LM_dev30 --out figures/r2_lm_selected --baseline single --candidate single_stable
```

最终冻结后，将 `--phase-dir` 换为实际最终保留测试阶段即可，不需要再运行场景。若需显示自定义方案名称，使用 `--labels labels.json`，内容为 `{"baseline_id":"基线名称","candidate_id":"候选名称"}`。默认读取 Windows `simhei.ttf`；其他环境使用 `--font` 指向中文 TTF。PDF 嵌入所用字体，SVG 保留可编辑文字，阅读或编辑 SVG 需安装 SimHei。依赖 ReportLab；PNG 预览额外依赖 pypdfium2。

## 输入和校验

- `registration.json` 决定阶段用途、策略、注册种子和任务数；角色未识别时拒绝推断用途。
- `paired_results.csv` 提供逐场总时间、每源时间、现实耗时、成功状态。种子缺失、重复或不同于注册集均报错，禁止静默删除失败局。
- `summary.json` 提供五项行动时间；图前从 CSV 重新计算均值、P95、最坏值和成功数，并核对五项时间之和。
- `comparison*.json` 必须包含完整配对及相同世界核验数量，且与注册 n 相符；不能仅凭两列等长数据就称为配对。

存在有效时间但未完整清除的场景会保留，表格完整率下降，配对差图显示叉号。结果或时间缺失时停止出图，不能把缺失场景从均值中略去。本工具核对已有相同世界核验报告，不读取场景真值重新实施世界核验。

## 产物与图注

- `time_components.pdf/.svg`：平均完整场景总时间，移动、无线检测、切频、光学、成功清除五项堆叠。
- `paired_difference_基线_候选.pdf/.svg`：候选减基线的逐场总时间差；负值更快，退步与失败均保留，种子顺序遵循注册顺序。
- `metrics_table.pdf/.svg`：完整率、平均每源、平均整场、整场 P95、最坏整场、平均现实策略耗时。
- `paired_differences.csv`、`table_data.csv`：图表数值和场景序号到种子的映射。
- `SOURCES.json`：输入及生成器 SHA256、注册角色与 n、实际采用的策略和配对证据数量。
- `CAPTIONS.md`：可供论文使用的图注和指标定义。

所有图都标记开发、验证或最终保留测试，以及“自建本地场景假设，非官方分布”。平均每源为“每场总时间除该场源数，再对场景取均值”；不与“所有总时间除所有源数”的加权比率混用。P95 取总时间的线性插值分位数。

## 已完成验证

以父仓库 `reports/R2_LM_dev30` 原始数据生成 `figures/r2_lm`，对应 30 个注册场景、4 个方案、120 局；4 组既有配对核验各 30 对。未重新运行场景。M+L 对 M 保留 22 个加快和 8 个退步场景，平均整场差为 -181.52 s。

9 个独立数据校验测试通过：正常配对、保留失败、拒绝缺失、重复、不同种子、相同世界证据不足、账目不平、未知阶段和汇总分位数错误。6 份 PDF 均为单页、含嵌入中文 TTF，6 份 SVG 通过 XML 解析。已渲染并目视检查堆叠柱、M+L 对 M 差值图和指标表；修正了原中文字体不包含的数学减号，使用中文“减”。

测试命令：

```powershell
& 'C:\Users\12831\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -p test_plot_phase_results.py
```
