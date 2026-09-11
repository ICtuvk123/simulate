# 问题三自动搜索与清除

当前使用独立自建模拟器：双击 `local_simulator/start_local_simulator.cmd`，或打开 `http://127.0.0.1:8768`。使用说明见 `local_simulator/README.md`。已完成19项规则测试及36次本地配对运行，支持过程可视化、固定种子、事后下界与离线回放。

用户最新要求完全不使用官方模拟器，包括演练；正式测试禁止。下文部署准备内容仅为历史记录。第二问新的覆盖率/剩余时间算法原型在 `q2_revision/`，尚未接入当前三种策略。

- [接口契约](simulator_contract.md)：12项真实接口规则及UNKNOWN。
- [部署步骤](simulator_setup.md)：用户下载登录步骤、连接演示运行方式。
- [材料审计](audit/material_audit.md)：材料清点与阻塞原因。
- [建模前置审计](reports/ANALYSIS_MODELING_REPORT.md)：物理、计时与几何完成条件。
- [验证结果](reports/RESULTS_REPORT.md)：21项本地测试通过，附件计时例199秒。
- [任务状态](todo.md)：仍未完成的真实演练、优化及三次正式测试。

使用附件1提供的网盘链接下载模拟器、完成注册/登录后，提供模拟器路径和参赛队号，即可继续真实部署验证。不要提供密码。
