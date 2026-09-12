# 当前 G+ 方案提取包

版本：**q3-Gplus-20260912-v1**。团队号：**202617201735**。

本目录可以整体复制到其他位置。先将压缩包完整解压，再双击 **一键测试Gplus.cmd**，即可使用中文测试窗口。

- 阅读算法：[Gplus方案说明.md](Gplus方案说明.md)。
- 查看全部生效参数：[Gplus完整参数.json](Gplus完整参数.json)。
- 自行测试：[测试使用说明.md](测试使用说明.md)。
- 算法核心：[time_policy.py](time_push_20260912/code/time_policy.py)。
- 实测回放：[Gplus_replay.html](time_push_20260912/reports/Gplus_replay.html)。
- 提取后验证：[提取验证.json](提取验证.json)。

本包保留原有相对目录结构，包含 G+ 的继承依赖、本地模拟器、官方演练入口、中文窗口和必要证据。算法源文件与冻结版本逐字节一致。原 G 可作为本地对照；较早的基础模块也是 G+ 的运行依赖。

需要 Python 3.10 或以上，仅使用 Python 标准库；中文窗口使用 Windows PowerShell 和 WinForms。本机已有 Python 可直接运行。复制到其他电脑时，需要该电脑自备 Python；官方演练还需要另行打开官方模拟器并登录。

本包未包含官方模拟器安装程序、账号密码、全部历史调参记录。已有验证摘要与官方结束页证据放在 reports 与 evidence 中。FREEZE.json 中的 official_tests_run=false 是冻结当时的状态；后续那场官方演练见方案说明和 evidence。

新测试会在本包内部生成 user_tests、training_logs 和 runs。无需原项目目录，也无需更改算法参数。请勿只复制单个算法文件后按类的默认参数运行，因为完整 G+ 还依赖冻结参数的合并结果。
