"""Extract the validated incumbent, without changing or rerunning the policy."""
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract():
    incumbent = json.loads((ROOT / 'INCUMBENT.json').read_text(encoding='utf-8'))
    freeze = json.loads((ROOT / incumbent['freeze']).read_text(encoding='utf-8'))
    phase = 'reports/R2_S22_ML_val100'
    results = json.loads((ROOT / phase / 'summary.json').read_text(encoding='utf-8'))['s22_ml']
    comparison = json.loads((ROOT / phase / 'comparison_s22_s22_ml.json').read_text(encoding='utf-8'))
    assert incumbent['version'] == 'R2_S22_ML-validated-20260912'
    assert results['n'] == results['complete'] == 100 and comparison['gate_passed']
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    folder = ROOT / 'release' / ('Q4_best_S22ML_' + stamp)
    folder.mkdir(parents=True, exist_ok=False)
    selected = ['INCUMBENT.json', incumbent['freeze'], incumbent['configuration'],
                'q4.py', 'official_practice.py', 'start_practice.py', 'start_q4_practice.cmd',
                'practice_settings.json', 'Q4_PRACTICE_README.md',
                'code/verify_freeze.py', 'code/replay_html.py', 'code/replay_template.html',
                'code/practice_offline_check.py', 'tests/test_practice_entry.py',
                'reports/ACTIVE_ALGORITHM.md', 'reports/R2_RESULTS_REPORT.md']
    selected += [phase + '/' + name for name in ('summary.json', 'comparison_s22_s22_ml.json',
                'registration.json', 'paired_results.csv', 'action_diagnostics_summary.json',
                'independent_exit_report.json')]
    for name, expected in freeze['source_hashes'].items():
        relative = incumbent['code_directory'] + '/' + name
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
        selected.append(relative)
    for relative in selected:
        destination = folder / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    # Document paths referenced by the algorithm description stay usable.
    shutil.copy2(folder / 'reports/R2_RESULTS_REPORT.md', folder / 'RESULTS_REPORT.md')
    (folder / '当前最佳方案说明.md').write_bytes((folder / 'reports/ACTIVE_ALGORITHM.md').read_bytes())
    snapshot = dict(version=incumbent['version'], status='validated_not_final_holdout_accepted',
                    algorithm_commit=freeze['commit'], configuration=incumbent['configuration'],
                    code_directory=incumbent['code_directory'], freeze=incumbent['freeze'],
                    config_sha256=freeze['config_sha256'], validation=results, paired_comparison=comparison,
                    final_holdout='interrupted; not accepted as 200-scene final evidence',
                    current_extraction_official_requests=0, current_extraction_new_scenes=0,
                    source_bytes_unchanged=True)
    (folder / 'BEST_VERSION.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    roles = results['mean_role_cost']
    readme = f'''# 第四问：当前最佳方案独立提取包

固定版本 **{incumbent['version']}**。这里的“最佳”指目前已通过完整新验证、按预定门槛晋级并冻结的版本，不代表数学上的全局最优。提取过程没有更改算法，也没有启动官方测试或新增优化场景。

## 先看哪些文件

- `当前最佳方案说明.md`：完整算法、公式、实际启用模块与退出依据。
- `BEST_VERSION.json`：版本、完整配置路径、验证指标和适用限制。
- `{incumbent['configuration']}`：唯一默认配置。
- `{incumbent['code_directory']}/q4controller.py`：总控制器。
- 同目录 `adaptive_single.py`、`region_quadrature.py`、`directional_geometry.py`、`compact_optical.py`、`lookahead.py`、`routing.py`：补测、评分、定向证书、光学覆盖、有限前瞻与路线模块。
- `{incumbent['freeze']}`：71个实际执行源文件的逐文件哈希。
- `reports/R2_S22_ML_val100/paired_results.csv`：完整100场配对数据。

## 当前成绩

| 指标 | 当前最佳 |
|---|---:|
| 完整清除 | {results['complete']}/{results['n']} |
| 平均每源虚拟时间 | {results['mean_per_source']:.2f} 秒 |
| 平均总虚拟时间 | {results['mean_total']:.2f} 秒 |
| 总时间P95 | {results['p95']:.2f} 秒 |
| 最坏总时间 | {results['worst']:.2f} 秒 |
| 平均现实计算耗时 | {results['mean_wall']:.2f} 秒 |

来自100个全新本地验证场景，两方案使用相同场景和固定空间误差场；两方案的200次运行均通过完整清除、反馈重放及独立退出核验。相对同批S22平均每源改善 {comparison['improvement_percent']:.3f}%，95%配对改善区间 [{comparison['bootstrap_improvement_95_percent'][0]:.3f}%, {comparison['bootstrap_improvement_95_percent'][1]:.3f}%]。

最终200场三方案保留批次未完成，不能写成“最终200场通过”。以上是本地分布假设下的验证成绩，不是该版本的官方成绩。

## 实际算法主体

1. 原点＋995米内环8站＋1860米外环13站，共22个定向搜索后备站。
2. 正测向和1500米上限更新保守位置区域；单次无信号只记录。
3. 使用稳定区域取样，比较自适应单点补测、双侧探测和少量光学覆盖的预计行动成本。先执行一次有价值的测量，随后依据真实反馈重新规划。
4. 开放路线、顺路清除和真实站点共享测向共同减少移动；保留连续搜索推进护栏和有限光学后备。
5. 仅16个不同频道实际清除成功，或所有已知源清除且余下频道均由实际负反馈取得连续局部凸包证书后退出。

只使用合法历史动作与接口反馈，决策器不接收源数、种子、真实位置、半径、类型或朝向。光学失败、无信号和切频均计入完整任务时间。

## 总时间主要花在哪里

| 按行动类别统计 | 平均时间 | 占总时间 |
|---|---:|---:|
| 移动 | {results['mean_move_time']:.2f} 秒 | {100*results['mean_move_time']/results['mean_total']:.2f}% |
| RF检测 | {results['mean_RF_detection_time']:.2f} 秒 | {100*results['mean_RF_detection_time']/results['mean_total']:.2f}% |
| 切频 | {results['mean_channel_switch_time']:.2f} 秒 | {100*results['mean_channel_switch_time']/results['mean_total']:.2f}% |
| 光学检查 | {results['mean_optical_time']:.2f} 秒 | {100*results['mean_optical_time']/results['mean_total']:.2f}% |
| 成功清除 | {results['mean_clear_time']:.2f} 秒 | {100*results['mean_clear_time']/results['mean_total']:.2f}% |

按任务用途另行划分，搜索阶段平均 {roles['search']['total_time']:.2f} 秒，占 {100*roles['search']['total_time']/results['mean_total']:.2f}%。它已经包含相应移动、检测和切频，不能与上表再相加。后续优化应以完整任务时间评估，并保留本提取包作为比较基线。

## 运行

本地14源测试及离线回放：

```text
python q4.py --sources 14 --seed 1 --replay-check
```

打开输出目录中的 `replay.html` 查看路线。种子和源数只交给本地场景引擎。

官方演练入口：双击 `start_q4_practice.cmd`；队号已填为202617201735，必须先在官方界面选择问题4演练。详见 `Q4_PRACTICE_README.md`。制作本提取包没有启动演练。

所有默认入口都核对冻结配置和71个源码哈希。冻结目录保留实际快照的全部文件；未启用模块不会因存在于目录中而自动启用。请在单独副本中继续优化，保留本包作为可回退基线。第三问G未更改。
'''
    (folder / 'README.md').write_text(readme, encoding='utf-8')
    checks = []
    for name, args in [('frozen_preflight', ['official_practice.py', '--check-only', '--robot-id', '202617201735']),
                       ('local_entry_help', ['q4.py', '--help']),
                       ('offline_regression', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'])]:
        p = subprocess.run([sys.executable, '-X', 'utf8', *args], cwd=folder,
                           text=True, encoding='utf-8', capture_output=True, timeout=180,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        checks.append(dict(name=name, returncode=p.returncode))
        (folder / (name + '.txt')).write_text(p.stdout + '\n' + p.stderr, encoding='utf-8')
        if p.returncode:
            raise RuntimeError('Extraction check failed: ' + name + '\n' + p.stderr)
    qa = dict(valid=True, checks=checks, source_commit=freeze['commit'], source_count=71,
              source_bytes_unchanged=True, official_requests=0, new_performance_scenes=0)
    (folder / 'EXTRACTION_QA.json').write_text(json.dumps(qa, indent=2), encoding='utf-8')
    files = sorted(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    manifest = {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest_path = folder / 'FILE_SHA256.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = folder.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path in files + [manifest_path]:
            package.write(path, folder.name + '/' + path.relative_to(folder).as_posix())
    with zipfile.ZipFile(archive) as package:
        for name, digest in manifest.items():
            assert hashlib.sha256(package.read(folder.name + '/' + name)).hexdigest() == digest
    receipt = dict(directory=str(folder), archive=str(archive), bytes=archive.stat().st_size,
                   sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), **qa)
    (ROOT / 'reports/CURRENT_BEST_EXTRACTION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    archive.with_suffix('.QA.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return receipt


if __name__ == '__main__':
    print(json.dumps(extract(), ensure_ascii=False, indent=2))
