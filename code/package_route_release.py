"""Shareable local-only bundle, preserving this complete optimization round."""
import csv
import hashlib
import json
from pathlib import Path
import zipfile

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'local_simulator';DEST=ROOT/'reports/optimization'
NAME='问题三路线优化实验包_20260912'


def main():
    summary=json.loads((DEST/'G_SUMMARY.json').read_text())
    assert summary['feedback_only_audited_runs']==100
    freeze=json.loads((DEST/'G_FREEZE.json').read_text())
    files=set()
    for folder in ('code','web','tests'):
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.log'))
    files.update(ROOT/name for name in ('simulator.py','start_local_simulator.cmd','README.md'))
    files.add(ROOT/'reports/RESULTS_REPORT.md')
    files.update(p for p in DEST.glob('G_*') if p.is_file())
    files.update(p for p in (ROOT/'figures').glob('G_*') if p.is_file())
    for name in ('F_FREEZE.json','F_RESULTS.md','F_SUMMARY.json','F_validation100_runs.csv','F_validation_paired.csv','F_feedback_only_audit.json'):
        files.add(DEST/name)
    run_ids=[]
    for phase in freeze['training_phases']+['G_validation100','G_stress']:
        run_ids.extend(row['run_id'] for row in csv.DictReader((DEST/(phase+'_runs.csv')).open(encoding='utf-8-sig')))
    assert len(run_ids)==summary['additional_local_runs']
    for run_id in run_ids:
        files.update(p for p in (ROOT/'runs'/run_id).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    for name in ('run_route_phase.py','freeze_route_candidate.py','audit_route_experiments.py','finalize_route_results.py'):
        files.add(PROJECT/'code'/name)
    destination=PROJECT/'release'/(NAME+'.zip')
    readme=f'''# 问题三路线优化实验包

先完整解压。无需 Python 即可直接打开 local_simulator/reports/optimization/G_replay.html，查看完整过程。
最新结论与局限见 local_simulator/reports/optimization/G_RESULTS.md。
运行本地模拟器需要 Python 3.10 或以上，核心只使用标准库：双击 local_simulator/start_local_simulator.cmd。

本轮 {len(run_ids)} 局全部原始日志与执行代码快照已包含。100 个新场景的配对均值：
F：{summary['mean_F_total_s']:.2f} 秒/局，{summary['mean_F_s_per_source']:.2f} 秒/源；
G：{summary['mean_G_total_s']:.2f} 秒/局，{summary['mean_G_s_per_source']:.2f} 秒/源。
推荐默认：{summary['recommended_default']}。是否达到采纳条件和最慢案例变化以完整报告为准。

命令行，在 local_simulator 目录运行：
python simulator.py run --strategy G --seed 10001
python simulator.py run --strategy F --seed 10001
python simulator.py test

G_FREEZE.json 保存本轮冻结版本，F 保持历史原算法不变。G 各轮配置、CSV、核验 JSON 均保留，包含未采用和负面结果。
历史 F 结果摘要和配对 CSV 随包提供；其更早完整日志见原“问题三结构改进实验包”。
重新生成 PDF 另外需要 reportlab 和 Windows 黑体字体，运行模拟和查看已有回放/PDF 不需要。

本包只含自建模拟器，不含官方程序、官方连接脚本、账号或官方日志。源真值仅在退出后用于评估和回放，不输入控制器。
FILE_MANIFEST.json 保存每个文件的 SHA-256。
'''
    entries=[]
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        archive.writestr(NAME+'/先读我.md',readme)
        for path in sorted(files):
            data=path.read_bytes();relative=path.relative_to(PROJECT).as_posix()
            if b'202617201735' in data or b'run_official_practice_' in data:
                raise ValueError('Official-only material: '+relative)
            archive.writestr(NAME+'/'+relative,data)
            entries.append(dict(path=relative,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        archive.writestr(NAME+'/FILE_MANIFEST.json',json.dumps(entries,indent=2,ensure_ascii=False))
    with zipfile.ZipFile(destination) as archive:assert archive.testzip() is None
    receipt=dict(zip=str(destination),bytes=destination.stat().st_size,files=len(entries)+2,
        sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),crc_verified=True,
        local_only=True,complete_current_round_runs=len(run_ids))
    (PROJECT/'release'/(NAME+'.verification.json')).write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(receipt,indent=2,ensure_ascii=False))


if __name__=='__main__':
    import sys
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
