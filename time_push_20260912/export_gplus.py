"""Extract the frozen G+ solution and verify the relocated, self-contained bundle."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    frozen = json.loads((ROOT / 'FREEZE.json').read_text(encoding='utf-8'))
    candidate = json.loads((ROOT / 'candidate.json').read_text(encoding='utf-8'))
    assert candidate == frozen['candidate']
    official_ast = ast.parse((ROOT / 'official_practice.py').read_text(encoding='utf-8'))
    core = next(ast.literal_eval(n.value) for n in official_ast.body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NAMES' for t in n.targets))
    local = tuple(core) + ('engine.py', 'dynamic.py', 'runner.py')
    for name in local:
        if digest(ROOT / 'code' / name) != frozen['experiment_files_sha256'][name]:
            raise RuntimeError('Frozen source changed: ' + name)
    target = PROJECT / 'release' / 'Gplus方案_20260912'
    target.mkdir(parents=True, exist_ok=False)
    copied = {}

    def copy(source, relative):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        assert digest(source) == digest(destination)
        copied[str(relative).replace('\\', '/')] = digest(source)

    for name in local:
        copy(ROOT / 'code' / name, Path('time_push_20260912/code') / name)
    # The original official compatibility helpers resolve this sibling folder.
    for name in core:
        if name != 'time_policy.py':
            copy(ROOT / 'code' / name, Path('local_simulator/code') / name)
    for name in ('official_practice.py', 'run_candidate.py', 'test_helper.py', 'test_helper.ps1',
                 'candidate.json', 'FREEZE.json'):
        copy(ROOT / name, Path('time_push_20260912') / name)
    for name in ('manual_official_practice.py', 'run_official_practice_f.py'):
        copy(PROJECT / 'code' / name, Path('code') / name)
    for name in ('F_FREEZE.json', 'G_FREEZE.json'):
        copy(PROJECT / 'local_simulator/reports/optimization' / name,
             Path('local_simulator/reports/optimization') / name)
    for name in ('一键测试Gplus.cmd', '测试使用说明.md'):
        copy(PROJECT / name, name)
    copy(PROJECT / 'local_simulator/web/index.html', 'local_simulator/web/index.html')
    for name in ('SUMMARY.json', 'validation_paired.csv', 'Gplus_replay.html'):
        copy(ROOT / 'reports' / name, Path('time_push_20260912/reports') / name)
    copy(ROOT / 'figures/Gplus_validation.pdf', 'time_push_20260912/figures/Gplus_validation.pdf')
    official_dir = PROJECT / 'training_logs/20260912T092438714303Z-official-practice-Gplus'
    copy(official_dir / 'verified_metrics.json', 'evidence/official_verified_metrics.json')
    copy(official_dir / 'official_ui_result.json', 'evidence/official_ui_result.json')
    # Derive the effective configuration instead of manually retyping defaults.
    preset_ast = ast.parse((ROOT / 'code/g_policy_presets.py').read_text(encoding='utf-8'))
    base = next(ast.literal_eval(n.value) for n in preset_ast.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'FROZEN_G_OPTIONS' for t in n.targets))
    policy_ast = ast.parse((ROOT / 'code/time_policy.py').read_text(encoding='utf-8'))
    policy_class = next(n for n in policy_ast.body if isinstance(n, ast.ClassDef) and n.name == 'TimePolicy')
    init = next(n for n in policy_class.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
    extra = {a.arg: ast.literal_eval(d) for a, d in zip(init.args.args[-len(init.args.defaults):], init.args.defaults)}
    extra.update(candidate.get('extra', {}))
    json_write(target / 'Gplus完整参数.json', dict(version=frozen['version'],
        policy_options={**base, **candidate['options']}, policy_extra=extra,
        source='FROZEN_G_OPTIONS + candidate.options; TimePolicy defaults + candidate.extra'))

    (target / 'README.md').write_text('''# 当前 G+ 方案提取包

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
''', encoding='utf-8')
    (target / 'Gplus方案说明.md').write_text('''# 问题三 G+ 方案

## 目标与版本

当前提取的是冻结版本 **q3-Gplus-20260912-v1**。目标是在全部干扰源清除的前提下，压低每场的平均定位清除时间 `T/n`；多场比较采用各场 `T_i/n_i` 的算术平均。

行动时间 `T = 移动距离/5 + 5×射频测向次数 + 换频道次数 + 3×光学定位次数 + 2×成功清除次数`，单位为秒。程序在电脑上运行几秒不计入此行动时间。没有完整清除的运行不能算作更快的有效成绩。

## 算法怎样运行

G+ 以原 G 的搜索、定位和路径规划为基础。控制器只接收 enter、measure、clear、exit 四类接口的实际反馈。按频道维护未清除目标的可行位置区域，用示向扇区交集逐步收缩区域，并利用已实现的无信号反馈约束排除不可能的位置。

它在搜索未知源、对已知源补测、定位清除等任务之间比较预计行动时间，执行当前选定动作，再根据新反馈重新规划。定位测站须通过原有的接收安全检查，不能只因为预计路程短就选用。确认清除依靠接口成功反馈；退出前沿用原 G 的完成条件和实际负反馈覆盖证明，预测的未来覆盖不算已经覆盖。

核心继承关系是 `TimePolicy → RouteSearchController → StructuralController → ReplanningController → OptimizedController → BaselineController`。基础类提供区域几何、任务规划、搜索路线、共享测向和退出核验；TimePolicy 改进补测点候选与评分。

## 相对原 G 的四项改进

1. **补测后重新比较全局任务。** `commit_radius` 从 120 变为 0，取消区域半径缩到 120 米就优先连续处理当前源的承诺；实际补测后返回任务规划。
2. **补测候选加入更直接的行进点。** 除原有候选外，加入区域最小包围圆中心、区域重心、沿垂直于区域长轴方向偏移 8/25 米的点，以及从中心或重心朝当前位置退回 10/20 米的点。所有候选仍须通过接收安全检查。
3. **混合考虑平均与较坏情况。** 对区域内每个假设源，用三个假设误差 `-1.005°、0°、1.005°` 预测后续成本，以 `0.5×最大成本 + 0.5×平均成本` 打分，再对假设源等权平均。总候选分数再加移动、当前测向和必要的切频时间。这个采样评分用于排列动作优先级，不是对真实误差分布的证明；区域更新仍使用完整的 ±1.01° 边界。
4. **减少收益不足的顺路测向。** `near_prediction` 从 14 变为 10，`bearing_factor` 从 0.25 变为 0.15，筛掉更多不值得支付测向时间的附带动作。光学尝试阈值仍为 40 米。

冻结 G+ 开启 `direct_candidates=true`，设置 `error_risk=0.5`；`optical_cost=false`、`source_quadrature=false`、`explore_gain=0`、`intermediate_shared=false`。代码保留其他实验开关，但它们不是当前方案。

## 生效参数与使用方法

完整配置见根目录 `Gplus完整参数.json`。实际入口把 `g_policy_presets.py` 中的原 G 参数与 `candidate.json` 的覆盖项合并，再将 TimePolicy 的额外参数传入构造函数。

不能只写 `TimePolicy(client)` 来复现当前方案，例如这个类单独使用时 `error_risk` 的默认值是 1，而冻结 G+ 使用 0.5。请直接使用随包入口。

双击根目录 `一键测试Gplus.cmd`：本地测试不需要官方模拟器；官方演练需登录团队号 202617201735，打开“问题3演练测试”，接口就绪后填入当前案例编号。具体操作见 `测试使用说明.md`。

命令行可以在包根目录运行：

```powershell
.\\一键测试Gplus.cmd --check
.\\一键测试Gplus.cmd --local --seed 13001
.\\一键测试Gplus.cmd --local --seed 13001 --baseline
```

相同场景编号下比较 G+ 与原 G。也可在 `time_push_20260912` 目录使用 `python run_candidate.py --seed 13001`，追加 `--baseline` 运行原 G。

## 已有实测结果

| 数据集 | 原 G | G+ | 说明 |
|---|---:|---:|---|
| 100 场独立配对验证 | 240.214 秒/源 | 238.647 秒/源 | 全部清除；平均改善 0.652% |
| 24 场压力配对测试 | 238.335 秒/源 | 237.853 秒/源 | 全部清除；差异区间跨零 |
| 已完成的一场官方演练 | — | 266.988366 秒/源 | 11/11 清除，总行动时间 2936.872026 秒 |

100 场独立验证中 G+ 为 65 胜、35 负，平均节省的 95% bootstrap 区间为 [0.607, 2.529] 秒/源；单场最大退步为 20.438 秒/源。它有实验支持的小幅平均改善，并非每一场都更快，也未证明全局最优。

官方案例为 48NA-EEKE-AKNH-F3JJ，其核验数值和结束页记录位于 `evidence`。本地平均值、单场官方值和不同随机案例的成绩不能直接用于判断谁更快。本次提取只做离线复现，没有新开官方演练。

原始独立验证摘要在 `time_push_20260912/reports/SUMMARY.json`，100 对逐场数据在同目录 `validation_paired.csv`。本地模拟器采用明确的源位置、接收半径和误差场假设；控制器不读取种子或隐藏真值，这些仅在退出后用于评估。

## 文件对应关系

| 文件或目录 | 用途 |
|---|---|
| time_push_20260912/code/time_policy.py | G+ 候选测站与成本评分 |
| time_push_20260912/code/route_search.py | 原 G 搜索路线规划 |
| time_push_20260912/code/structural.py、replanning.py | 任务选择、区域约束、反馈后重规划 |
| time_push_20260912/code/*geometry.py、coverage.py | 几何计算、接收安全和覆盖证明 |
| time_push_20260912/code/q3client.py | 接口、动作账本和日志 |
| time_push_20260912/candidate.json、FREEZE.json | 冻结候选与源文件哈希 |
| time_push_20260912/official_practice.py | 冻结 G+ 官方演练入口 |
| time_push_20260912/run_candidate.py | 隔离进程中的本地测试 |
| code、local_simulator | 原入口需要的兼容依赖与本地回放模板 |

文件清单与 SHA-256 放在 `文件清单.json`；提取后独立路径下的实际运行验证放在 `提取验证.json`。
''', encoding='utf-8')

    # Verify after relocating the extracted folder, using a directory with spaces
    # and Chinese characters. This copy stays separate from the delivered bundle.
    check_root = PROJECT / 'release' / ('_Gplus提取验证 ' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    shutil.copytree(target, check_root)
    checks = []
    for arguments in (['--check'], ['--local', '--seed', '13001'],
                      ['--local', '--seed', '13001', '--baseline']):
        process = subprocess.run([sys.executable, '-X', 'utf8', str(check_root / 'time_push_20260912/test_helper.py'),
                                  *arguments], cwd=check_root, capture_output=True, text=True, encoding='utf-8')
        print(process.stdout, flush=True)
        if process.returncode:
            raise RuntimeError(process.stdout + '\n' + process.stderr)
        checks.append(dict(arguments=arguments, exit_code=process.returncode))
    expected = json.loads((ROOT / 'reports/entrypoint_check.json').read_text(encoding='utf-8'))
    tests = []
    for path in (check_root / 'user_tests').glob('*/test_result.json'):
        result = json.loads(path.read_text(encoding='utf-8'))
        variant = 'Gplus' if result['strategy'] == 'G+' else 'G'
        reference = next(item for item in expected if item['variant'] == variant)
        assert result['success'] and result['clear_count'] == result['source_count']
        assert abs(result['total_time_s'] - reference['total_time']) < 1e-6
        assert Path(result['replay']).is_file()
        assert Path(result['source_directory']).resolve().is_relative_to(check_root.resolve())
        tests.append({k: result[k] for k in ('strategy', 'seed', 'clear_count', 'source_count',
                                           'total_time_s', 'seconds_per_source', 'success')})
    assert len(tests) == 2
    json_write(target / '提取验证.json', dict(version=frozen['version'],
        checked_at_utc=datetime.now(timezone.utc).isoformat(),
        extracted_source_files_verified=len(local), strategy_source_unchanged=True,
        relocated_directory_tested=True, official_connection_made=False,
        checks=checks, runs=tests, matches_original_entrypoint_to_microsecond=True))
    files = {p.relative_to(target).as_posix(): digest(p) for p in sorted(target.rglob('*')) if p.is_file()}
    json_write(target / '文件清单.json', dict(version=frozen['version'], files_sha256=files,
        copied_original_files_sha256=copied, manifest_excludes_itself=True))
    archive = target.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(target.rglob('*')):
            if path.is_file():
                stream.write(path, path.relative_to(target.parent))
    with zipfile.ZipFile(archive) as stream:
        assert stream.testzip() is None
        for relative, expected_hash in files.items():
            assert hashlib.sha256(stream.read(target.name + '/' + relative)).hexdigest() == expected_hash
    print(json.dumps(dict(folder=str(target), archive=str(archive), bytes=archive.stat().st_size,
                          files=len(files) + 1, verification='passed'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
