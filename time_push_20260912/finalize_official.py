"""Preserve the GUI-named encrypted log and reconcile post-exit official results."""
import hashlib
import json
from pathlib import Path
import official_practice as app

latest=json.loads((app.ROOT/'reports/latest_official_practice.json').read_text())
directory=Path(latest['directory'])
ui=json.loads((directory/'official_ui_result.json').read_text(encoding='utf-8'))
original=json.loads((directory/'metrics.json').read_text(encoding='utf-8'))
audit=json.loads((directory/'feedback_only_audit.json').read_text())
app.verify_policy()
assert ui['ended_normally'] and audit['all_decisions_identical']
assert ui['source_count']==original['clear_count'] and original['completion_proved']
assert abs(ui['displayed_virtual_time_s']-original['total_time'])<.00051
metrics=app.parse_journal(directory/'requests.jsonl',ui['source_count'])
metrics.update(true_source_count=ui['source_count'],source_count_origin='post-exit official GUI',
    average_localization_clear_time_s_per_source=metrics['total_time']/ui['source_count'],
    program_wall_time_s=original['program_wall_time_s'],client_error=original['client_error'])
assert metrics['clear_ratio']==1 and not metrics['accounting_warnings'] and not metrics['client_error']
(directory/'verified_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
filename=ui['official_log_filename'];assert Path(filename).name==filename and ui['case_code'] in filename
source=app.PROJECT/'Jammers-simulator-full-win64/Jammers-simulator-full/JammersSimulatorData/behavior-logs'/filename
target=directory/filename
data=source.read_bytes();digest=hashlib.sha256(data).hexdigest()
if not target.exists():
    with target.open('xb') as f:f.write(data)
assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
preservation=dict(filename=filename,size_bytes=len(data),sha256=digest,
    source=str(source),destination=str(target),unchanged_bytes=True,content_decrypted=False,
    method='Byte-identical preservation of the official GUI-named saved behavior log; folder chooser could not be completed while window was minimized')
(directory/'official_log_preservation.json').write_text(json.dumps(preservation,ensure_ascii=False,indent=2),encoding='utf-8')
report=f'''# G+ 官方问题 3 演练结果

- 案例：`{ui['case_code']}`。
- 策略：冻结 `q3-Gplus-20260912-v1`，与本地独立验证版本一致。
- 官方演练已正常退出；共 **11 个全向源，11/11 全部清除**。
- 总行动时间：**{metrics['total_time']:.6f} 秒**。
- 平均定位清除时间：**{metrics['average_localization_clear_time_s_per_source']:.6f} 秒/源**。
- 程序执行耗时：约 **{metrics['program_wall_time_s']:.2f} 秒**，不计入题面行动时间。
- RF 检测 {metrics['RF_detection_count']} 次，切频 {metrics['channel_switch_count']} 次，光学定位 {metrics['optical_count']} 次且全部成功；移动 {metrics['move_distance']:.2f} 米。
- 计时账本、实际负反馈覆盖完成证明通过；无拒绝、光学失败或网络重试。
- {audit['actions_checked']} 条动作通过仅使用官方接口反馈的离线重放，决策一致；重放期间禁止磁盘、网络和进程访问。

本次只运行了一场问题 3 演练，没有运行正式测试。源总数只在退出后从官方页面读入核验，没有提供给策略。

官方原始日志：[{filename}]({filename})，{len(data)} 字节。原文件名与加密内容保留；SHA256：`{digest}`。日志来自官方页面显示的已保存文件，未解密。导出文件夹窗口在操作中被最小化，已直接将该官方保存文件逐字节复制到本目录，校验完全一致。

详细动作见 [requests.jsonl](requests.jsonl)，核验统计见 [verified_metrics.json](verified_metrics.json)，结束界面证据见 [official_ui_result.json](official_ui_result.json)。

本案例为新的随机场景，不能直接把 266.99 秒/源与其他官方案例或本地多场均值作算法快慢比较。
'''
(directory/'RESULTS.md').write_text(report,encoding='utf-8')
(app.ROOT/'reports/OFFICIAL_PRACTICE_RESULT.md').write_text(report.replace('](',']('+str(directory).replace('\\','/')+'/'),encoding='utf-8')
with (app.ROOT/'README.md').open('a',encoding='utf-8') as f:
    f.write('\n已完成一场 G+ 官方演练，11/11 清除，266.988366 秒/源；见 [官方演练结果](reports/OFFICIAL_PRACTICE_RESULT.md)。\n')
print(json.dumps(dict(case_code=ui['case_code'],clear_count=11,source_count=11,
    average_s_per_source=metrics['average_localization_clear_time_s_per_source'],
    total_s=metrics['total_time'],official_log=filename,log_sha256=digest,
    feedback_replay_actions=audit['actions_checked'],all_checks_pass=True),ensure_ascii=False,indent=2))
