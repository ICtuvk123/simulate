"""Friendly, standard-library entry point for frozen G+ self-tests."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
OUTPUT = PROJECT / 'user_tests'
DEFAULT_TEAM = '202617201735'
PRACTICE_TITLE = '问题3演练测试'


def parser():
    p = argparse.ArgumentParser(description='G+ 自助测试：双击项目根目录的“一键测试Gplus.cmd”可打开中文窗口。')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='只检查文件，不连接官方模拟器')
    mode.add_argument('--local', action='store_true', help='运行一场本地测试')
    mode.add_argument('--official', action='store_true', help='运行当前官方问题3演练案例')
    p.add_argument('--team', default=DEFAULT_TEAM)
    p.add_argument('--port', type=int, default=2026)
    p.add_argument('--case', default='')
    p.add_argument('--title', default='')
    p.add_argument('--ready', action='store_true', help='本人已核对当前演练页面，且接口已开放')
    p.add_argument('--seed', type=int, default=13001)
    p.add_argument('--baseline', action='store_true', help='本地运行原 G 作对照')
    return p


def make_proof(args):
    """Only construct UI evidence from the user's explicit current-page inputs."""
    team = args.team.strip()
    title = re.sub(r'\s+', '', args.title)
    case = args.case.strip().upper()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', team):
        raise ValueError('队号格式无效，请填写官方当前登录的参赛队号。')
    if not 1 <= args.port <= 65535:
        raise ValueError('接口端口须在 1–65535 之间。')
    if title != PRACTICE_TITLE or not args.ready:
        raise ValueError('请先核对官方当前页面为“问题3演练测试”，等待接口开放，并勾选就绪选项。')
    if not re.fullmatch(r'[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}', case):
        raise ValueError('请复制当前案例编号，格式为 XXXX-XXXX-XXXX-XXXX。')
    if args.baseline:
        raise ValueError('官方入口使用 G+；原 G 对照选项只用于本地测试。')
    return dict(mode='problem3_practice', case_code=case, robot_id=team,
                port=args.port, observed_text=title, interface_ready=True,
                observed_at_utc=datetime.now(timezone.utc).isoformat(),
                evidence_source='human_read_current_official_UI',
                independently_verified_by_agent=False)


def load_official():
    # Local simulations run in a separate process: their hidden-source generator
    # must never enter the official controller's interpreter.
    import official_practice
    return official_practice


def preflight():
    if sys.version_info < (3, 10):
        raise ValueError('需要 Python 3.10 或以上版本。')
    required = [ROOT / 'run_candidate.py', PROJECT / 'local_simulator/web/index.html',
                PROJECT / 'code/manual_official_practice.py',
                PROJECT / 'code/run_official_practice_f.py']
    for path in required:
        if not path.is_file():
            raise FileNotFoundError('缺少测试文件：' + str(path))
    frozen, _, _, hashes = load_official().verify_policy()
    return frozen['version'], len(hashes)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def local_test(args, directory):
    command = [sys.executable, '-u', str(ROOT / 'run_candidate.py'), '--seed', str(args.seed)]
    if args.baseline:
        command.append('--baseline')
    with (directory / 'console.log').open('w', encoding='utf-8') as log:
        # An argument list keeps paths and user input out of shell syntax.
        process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    raw = (directory / 'console.log').read_text(encoding='utf-8')
    if process.returncode:
        raise RuntimeError('本地测试未完成，详细原因见 console.log。\n' + raw[-3000:])
    result = json.loads(raw)
    data_dir = Path(result['directory']).resolve()
    if not data_dir.is_relative_to((ROOT / 'runs').resolve()):
        raise ValueError('本地结果路径不在预期的 runs 目录内。')
    return dict(mode='local', strategy='G' if args.baseline else 'G+', seed=args.seed,
                clear_count=result['cleared'], source_count=result['count'],
                total_time_s=result['total_time'], seconds_per_source=result['seconds_per_source'],
                completion_proved=result['completion_proved'],
                success=bool(result['completion_proved'] and result['cleared'] == result['count']),
                source_directory=str(data_dir), replay=str(data_dir / 'replay.html'))


def find_official_directory(raw, proof):
    # Use the directory printed by this invocation, not a shared "latest" file
    # that another launch could overwrite.
    for line in reversed(raw.splitlines()):
        try:
            candidate = Path(line.strip()).resolve()
            if not candidate.is_relative_to((PROJECT / 'training_logs').resolve()):
                continue
            evidence = json.loads((candidate / 'ui_mode_proof.json').read_text(encoding='utf-8'))
            if evidence['case_code'] == proof['case_code'] and evidence['robot_id'] == proof['robot_id']:
                return candidate
        except (ValueError, OSError, KeyError, json.JSONDecodeError):
            continue
    raise RuntimeError('未找到本次官方结果目录，请查看 console.log 中的原始输出。')


def official_test(proof, directory):
    app = load_official()
    write_json(directory / 'ui_mode_proof.json', proof)
    output = io.StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            code = app.run(proof)
    finally:
        (directory / 'console.log').write_text(output.getvalue(), encoding='utf-8')
    data_dir = find_official_directory(output.getvalue(), proof)
    metrics = json.loads((data_dir / 'metrics.json').read_text(encoding='utf-8'))
    return dict(mode='official', strategy='G+', team=proof['robot_id'], case=proof['case_code'],
                port=proof['port'], clear_count=metrics['clear_count'], source_count=None,
                total_time_s=metrics['total_time'],
                seconds_per_source=metrics['average_localization_clear_time_s_per_source'],
                completion_proved=metrics['completion_proved'],
                success=bool(code == 0 and not metrics.get('client_error') and metrics['completion_proved']),
                client_error=metrics.get('client_error'), source_directory=str(data_dir),
                accounting_warnings=metrics.get('accounting_warnings', []))


def format_result(result, directory):
    official = result['mode'] == 'official'
    lines = ['测试完成' if result['success'] else '测试未完整通过，请检查下方记录',
             '测试类型：' + ('官方问题3演练' if official else '本地模拟'),
             '策略：' + result['strategy']]
    if official:
        lines += ['团队号：' + result['team'], '案例编号：' + result['case']]
    else:
        lines.append('场景编号：' + str(result['seed']))
    count = result['clear_count']
    lines += [f'清除数量：{count}' + (' 个（总数请核对官方结束页）' if official else f" / {result['source_count']} 个"),
              f"总行动时间：{result['total_time_s']:.6f} 秒"]
    mean = result['seconds_per_source']
    mean_label = '平均时间' if result['success'] else '已清除部分均时（仅供诊断）'
    lines.append(f'{mean_label}：{mean:.6f} 秒/源' if mean is not None else '平均时间：无有效清除记录')
    lines.append('完成证明：' + ('通过' if result['completion_proved'] else '未通过'))
    if result.get('client_error'):
        lines.append('停止原因：' + result['client_error'])
    if result.get('accounting_warnings'):
        lines.append('计时核对提示：' + json.dumps(result['accounting_warnings'], ensure_ascii=False))
    if official:
        lines += ['均时按本次总行动时间 ÷ 已清除数量计算；请在官方结束页核对是否全部清除及最终成绩。',
                  '请在官方日志列表导出本场 .jlog，保存在下方结果文件夹中。']
    else:
        lines += ['本地结果用于比较策略；它不代表官方成绩。', '离线回放：' + result['replay']]
    lines += ['原始运行记录：' + result['source_directory'], '本次结果文件夹：' + str(directory)]
    return '\n'.join(lines) + '\n'


def main(argv=None):
    args = parser().parse_args(argv)
    directory = None
    try:
        # Check the actual UI inputs before loading or invoking the official runner.
        proof = make_proof(args) if args.official else None
        version, verified = preflight()
        print(f'G+ 文件检查通过：{version}，{verified} 个冻结文件。', flush=True)
        if args.check:
            print('环境检查完成，可以使用本地测试和官方演练入口。本次未建立官方连接。')
            return 0
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        mode = 'official' if args.official else 'local'
        directory = OUTPUT / f'{stamp}_{mode}_{uuid.uuid4().hex[:6]}'
        directory.mkdir(parents=True, exist_ok=False)
        write_json(directory / 'launch_config.json', vars(args))
        print('正在运行' + ('当前官方演练' if args.official else '本地场景') + '，请等待结果……', flush=True)
        print('本次记录：' + str(directory), flush=True)
        result = official_test(proof, directory) if args.official else local_test(args, directory)
        write_json(directory / 'test_result.json', result)
        message = format_result(result, directory)
        (directory / '测试结果.txt').write_text(message, encoding='utf-8-sig')
        print('\n' + message, flush=True)
        return 0 if result['success'] else 1
    except (Exception, KeyboardInterrupt) as exc:
        message = '测试停止：' + str(exc)
        if isinstance(exc, FileExistsError) and args.official:
            message += '\n当前案例已有启动记录；请检查先前运行窗口和日志。'
        if directory is not None:
            try:
                (directory / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
                write_json(directory / 'test_result.json', dict(success=False, mode='official' if args.official else 'local',
                                                               error=f'{type(exc).__name__}: {exc}'))
                message += '\n记录保存在：' + str(directory)
                (directory / '测试结果.txt').write_text(message, encoding='utf-8-sig')
            except OSError:
                message += '\n结果文件夹无法写入，请检查该目录的写入权限：' + str(directory)
        if args.official:
            message += '\n若已开始发送动作，请保留当前官方页面和日志；不要对同一案例重复启动。'
        print(message, flush=True)
        return 2 if isinstance(exc, ValueError) else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
