"""Portable local research bundle, limited to this round's evidence."""
import csv
import hashlib
import json
from pathlib import Path
import zipfile

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'local_simulator';DEST=ROOT/'reports'/'optimization'
NAME='问题三结构改进实验包_20260912'


def main():
    summary=json.loads((DEST/'F_SUMMARY.json').read_text())
    assert summary.get('feedback_only_audited_runs')==100
    files=set()
    for folder in ('code','web','tests'):
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.log'))
    files.update(ROOT/name for name in ('simulator.py','start_local_simulator.cmd','README.md'))
    files.update(p for p in DEST.glob('F_*') if p.is_file())
    files.update(p for p in (ROOT/'figures').glob('F_*') if p.is_file())
    files.add(DEST/'E_validation100_runs.csv')
    files.add(DEST/'E_FREEZE.json')
    phases=['F_round1','F_round2','F_round3','F_validation100','F_stress']
    run_ids=[]
    for phase in phases:
        rows=list(csv.DictReader((DEST/(phase+'_runs.csv')).open(encoding='utf-8-sig')))
        run_ids.extend(row['run_id'] for row in rows)
    assert len(run_ids)==summary['additional_local_runs']
    for run_id in run_ids:
        files.update(p for p in (ROOT/'runs'/run_id).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    for name in ('prepare_structural_experiments.py','prepare_structural_round2.py','prepare_structural_round3.py',
                 'freeze_structural_candidate.py','analyze_structural_phase.py','finalize_structural_results.py',
                 'audit_structural_parallel.py'):
        files.add(PROJECT/'code'/name)
    destination=PROJECT/'release'/(NAME+'.zip')
    if destination.exists():raise FileExistsError(destination)
    readme=f'''# 问题三结构改进实验包

请先完整解压，再双击 local_simulator/start_local_simulator.cmd 启动本地界面。
核心运行需要 Python 3.10 或以上，只使用标准库，不需要官方登录。

无需 Python 即可查看：local_simulator/reports/optimization/F_replay.html。
最新报告：local_simulator/reports/optimization/F_RESULTS.md。

当前推荐默认为 {summary['recommended_default']}。100 场新验证配对：
E 整局 {summary['mean_E_total_s']:.2f} 秒、{summary['mean_E_s_per_source']:.2f} 秒/源；
F 整局 {summary['mean_F_total_s']:.2f} 秒、{summary['mean_F_s_per_source']:.2f} 秒/源。
完整结果、可信范围与是否采纳请以 F_RESULTS.md 为准。

本包保留本轮 {len(run_ids)} 局原始日志及源码快照。历史 E 的逐场指标 CSV 用于核对
229.62 秒/源这一口径更正；更早的完整历史日志保留在原 E 分享包中，未在本包重复。
FILE_MANIFEST.json 保存文件 SHA-256。修改参数时请保留原冻结版本作对照。

命令行：python simulator.py run --strategy F --seed 8001
对照：python simulator.py run --strategy E --seed 8001
在 local_simulator 目录执行。报告 PDF 重新生成另外需要 reportlab 和 Windows 黑体字体，
正常模拟运行和查看已有 PDF、HTML 不需要 reportlab。

这里全部是自建本地环境，不包含官方模拟器、账号、官方日志或官方启动适配脚本。
不会进入官方演练或正式测试。真实源只在退出后的评估和回放中显示，不供控制器决策。
'''
    entries=[]
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        archive.writestr(NAME+'/先读我.md',readme)
        for path in sorted(files):
            data=path.read_bytes();relative=path.relative_to(PROJECT).as_posix()
            if b'202617201735' in data or b'run_official_practice_d.py' in data:
                raise ValueError('Official-only material: '+relative)
            archive.writestr(NAME+'/'+relative,data)
            entries.append(dict(path=relative,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        archive.writestr(NAME+'/FILE_MANIFEST.json',json.dumps(entries,indent=2,ensure_ascii=False))
    with zipfile.ZipFile(destination) as archive:assert archive.testzip() is None
    receipt=dict(zip=str(destination),bytes=destination.stat().st_size,files=len(entries)+2,
                 sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),crc_verified=True,
                 local_only=True,complete_current_round_runs=len(run_ids))
    (PROJECT/'release'/(NAME+'.verification.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
