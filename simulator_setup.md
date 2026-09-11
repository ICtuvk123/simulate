# 模拟器部署状态与操作

当前已完成真实连接验证。用户随后将模拟器放入项目并登录；运行路径为 `D:\computer_learning\jammer_search_q3\Jammers-simulator-full-win64\Jammers-simulator-full\jammers-simulator-full.exe`，版本v1.1，端口2026。案例XQ5R-MQS2-M35M-PFKN已完成四端点演练，199秒计时一致。用户最新要求仅演练，禁止正式测试。以下下载/登录步骤保留为复现说明，无需重复执行。

## 需要用户完成的最小步骤

1. 按附件1 §4提供的[下载入口](https://pan.baidu.com/s/1P1yfVjY0RufU93XOdzhOLw?pwd=2026)手动下载，提取码2026。
2. 解压到一个固定目录并保留整个目录。推荐放在 `D:\computer_learning\jammer_search_q3\simulator`；不要只移动可执行文件，模拟器要在同目录保留运行数据。
3. 按附件1完成注册/登录。首次注册需要竞赛队号、队员1姓名、手机号及本人设置密码。不要把密码发给助手。
4. 提供模拟器目录、参赛队号和接口端口（默认2026）。若已有问题1/2代码，也提供其路径。
5. 连接验证时选择“问题3演练测试”，等待界面显示接口就绪。当前演示程序仅验证通信和计时，不用于正式测试。

所有后续运行都会消耗当前已启动测试；HTTP协议不返回演练/正式模式，因此必须在界面选择正确模块。

## 已准备的本地工具

使用已发现的捆绑Python，无需安装第三方依赖：

```powershell
$q3Python = 'C:\Users\12831\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
Set-Location -LiteralPath 'D:\computer_learning\jammer_search_q3'
& $q3Python -m unittest discover -s tests -v
& $q3Python code\experiment.py inspect-sample
```

真实演练开始并接口就绪后，通信演示命令如下；把YOUR_TEAM_ID替换为参赛队号：

```powershell
& $q3Python code\experiment.py smoke --robot-id YOUR_TEAM_ID --mode training --case-code CASE_FROM_UI
```

演示执行enter → (300,400)检测频道1 → 原地检测频道2 → (300,0)尝试清除频道3 → 原地检测频道2 → exit。这是附件的动作序列，真实清除反馈未必与附件的假定失败一致，总时间应为199秒或201秒。真实至少成功清除一个源仍需后续完整策略；该演示不保证清除成功。

解析自己的客户端日志：

```powershell
& $q3Python code\experiment.py parse --log training_logs\RUN_ID\requests.jsonl
```

只有该日志记录了成功exit后，才可将官方演练界面显示的总数补入评估：

```powershell
& $q3Python code\experiment.py parse --log training_logs\RUN_ID\requests.jsonl --jammer-count 12
```

这里12仅为命令格式示意，必须替换为该局真实界面显示的数量。程序运行期间不会读取评估总数。

## 尚未完成的验收

- 真实启动和端口验证。
- enter成功与真实时间预算读取。
- 真实动作耗时对账、成功清除、完整演练。
- 官方日志导出及文件名确认。
- seed/重置/重放能力实际核对。
- 三次正式测试。

契约测试只是离线协议逻辑验证，不是模拟器替代品，不产生清除率和策略性能成绩。
