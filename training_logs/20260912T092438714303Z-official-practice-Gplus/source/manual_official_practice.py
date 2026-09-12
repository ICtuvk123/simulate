"""Human-operated launcher for one official Problem 3 practice; never auto-starts a case."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

from run_official_practice_f import (
    PROJECT, POLICY_CODE, NAMES, PracticeTransport, verify_frozen_policy,
)
from structural import StructuralController
from route_search import RouteSearchController
from f_policy_presets import FROZEN_F_OPTIONS, FROZEN_F_VERSION
from g_policy_presets import FROZEN_G_OPTIONS, FROZEN_G_VERSION
from q3client import Client, JsonlJournal, ProtocolError, canonical, identifier, parse_journal


def verify_policy(strategy):
    verified = verify_frozen_policy()
    options, version, controller = FROZEN_F_OPTIONS, FROZEN_F_VERSION, StructuralController
    if strategy == 'G':
        options, version, controller = FROZEN_G_OPTIONS, FROZEN_G_VERSION, RouteSearchController
        frozen = json.loads((PROJECT / 'local_simulator/reports/optimization/G_FREEZE.json').read_text(encoding='utf-8'))
        if frozen['version'] != version or frozen['policy_options'] != options:
            raise ProtocolError('G configuration differs from the frozen version; no request sent')
        for name, expected in frozen['policy_file_sha256'].items():
            if name == 'engine.py':
                continue  # Official operation neither imports nor uses the local source generator.
            actual = hashlib.sha256((POLICY_CODE / name).read_bytes()).hexdigest()
            if actual != expected:
                raise ProtocolError('Frozen G file changed: ' + name + '; no request sent')
            verified[name] = actual
    elif strategy != 'F':
        raise ValueError('Choose F or G')
    assert 'engine' not in sys.modules and 'runner' not in sys.modules
    return dict(options), version, controller, verified


def validate_case(robot_id, port, title, case_code):
    if not identifier(robot_id, 64):
        raise ValueError('参赛队号格式无效。')
    if not 1 <= port <= 65535:
        raise ValueError('端口必须在 1–65535 之间。')
    if re.sub(r'\s+', '', title) != '问题3演练测试':
        raise ValueError('只接受页面标题“问题3演练测试”；尚未发送任何请求。')
    if not re.fullmatch(r'[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}', case_code):
        raise ValueError('案例编号应形如 XXXX-XXXX-XXXX-XXXX，请从当前演练页面读取。')


def claim_case(proof):
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(proof['observed_at_utc'])).total_seconds()
    if not 0 <= age <= 120:
        raise ValueError('确认已超过两分钟，请重新核对当前演练页面。')
    for previous in (PROJECT / 'training_logs').glob('*/ui_mode_proof.json'):
        if json.loads(previous.read_text(encoding='utf-8')).get('case_code') == proof['case_code']:
            raise ValueError('这个案例已经运行过，不能重复进入。请查看该次日志。')
    directory = PROJECT / 'audit/manual_practice_claims'
    directory.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents two launchers from entering the same case.
    with (directory / (proof['case_code'] + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2)


def run_confirmed_case(strategy, robot_id, port, proof):
    options, version, controller_type, verified = verify_policy(strategy)
    validate_case(robot_id, port, proof['observed_text'], proof['case_code'])
    claim_case(proof)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-manual-official-practice-' + strategy
    directory = PROJECT / 'training_logs' / run_id
    snapshot = directory / 'source'
    snapshot.mkdir(parents=True, exist_ok=False)
    fingerprint = hashlib.sha256()
    for name in sorted(verified):
        source = POLICY_CODE / name
        fingerprint.update(name.encode() + source.read_bytes())
        shutil.copy2(source, snapshot / name)
    for source in (Path(__file__), PROJECT / 'code/run_official_practice_f.py'):
        shutil.copy2(source, snapshot / source.name)
    (directory / 'ui_mode_proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    (directory / 'frozen_policy_verification.json').write_text(json.dumps(verified, indent=2), encoding='utf-8')
    metadata = dict(run_id=run_id, mode='training', data_origin='official_problem3_practice',
                    case_code=proof['case_code'], seed=None, strategy_version=version,
                    strategy_hash=fingerprint.hexdigest(), parameters=options,
                    policy_configuration=dict(strategy=strategy, policy_options=options),
                    parameter_hash=hashlib.sha256(canonical(options).encode()).hexdigest(),
                    authorization='Human manually confirmed current Problem 3 practice in this launcher',
                    mode_evidence_source='human_read_current_official_UI', mode_verified_by_HTTP=False)
    journal = JsonlJournal(directory / 'requests.jsonl', metadata)
    client = Client(robot_id, journal, transport=PracticeTransport(port))
    error = None
    print('\n正在运行一场演练。请保持官方模拟器开启，不要重复启动脚本。', flush=True)
    try:
        controller_type(client, **options).run()
    except (Exception, KeyboardInterrupt) as exc:
        error = f'{type(exc).__name__}: {exc}'
        journal.append(dict(event='client_stop', error=error, pending_request=client.pending))
    finally:
        journal.close()
    metrics = parse_journal(directory / 'requests.jsonl')
    metrics['client_error'] = error
    metrics['true_source_count'] = None  # Only the official UI reveals it after exit.
    (directory / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n成功清除：{metrics['clear_count']} 个（真实总数请查看官方结束页面）")
    print(f"总行动时间：{metrics['total_time']:.2f} 秒")
    print(f"完成证明：{'通过' if metrics['completion_proved'] else '未通过'}")
    print('本地记录：' + str(directory))
    if error:
        print('程序停止：' + error + '\n不要重跑同一案例；保留当前页面和日志以便检查。')
    else:
        print('本次运行已结束。请在官方界面核对总数，并从日志列表导出本次演练的原始日志。')
    return int(bool(error) or not metrics['completion_proved'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true', help='Offline file verification only; no connection')
    args = parser.parse_args()
    for strategy in ('F', 'G'):
        _, version, _, verified = verify_policy(strategy)
        print(f'{strategy} 文件核验通过：{version}，{len(verified)} 个文件。')
    if args.prepare_only:
        print('离线预检完成，没有建立网络连接。')
        return 0
    print('\n手动运行官方问题3演练；本程序不启动、选择或重开官方案例。')
    print('G：当前策略，已有本地验证。F：上一版，已有官方演练记录。')
    strategy = (input('选择策略 [G/F，回车用 G]：').strip().upper() or 'G')
    verify_policy(strategy)
    robot_id = input('输入官方模拟器当前登录的参赛队号（不是密码）：').strip()
    port = int(input('官方接口端口 [回车用 2026]：').strip() or '2026')
    if not identifier(robot_id, 64) or not 1 <= port <= 65535:
        raise ValueError('队号或端口格式无效，尚未发送任何请求。')
    print('\n现在打开官方模拟器，登录，选择“问题3演练测试”，等待5秒倒计时结束、接口开放。')
    print('HTTP接口不返回测试模式；必须由你读取当前官方页面。看到正式测试时请关闭本脚本。')
    title = input('请输入当前页面的测试标题（应为 问题3演练测试）：').strip()
    case_code = input('输入当前演练案例编号：').strip().upper()
    validate_case(robot_id, port, title, case_code)
    proof = dict(mode='problem3_practice', case_code=case_code, robot_id=robot_id, port=port,
                 observed_text=title, interface_ready=True,
                 observed_at_utc=datetime.now(timezone.utc).isoformat(),
                 evidence_source='human_read_current_official_UI', independently_verified_by_agent=False)
    print(f'即将连接 127.0.0.1:{port}，策略 {strategy}，案例 {case_code}。')
    if input('确认页面确实为演练且接口已开放后，输入“演练”并回车开始：').strip() != '演练':
        print('已取消，未发送任何请求。')
        return 0
    return run_confirmed_case(strategy, robot_id, port, proof)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print('\n已停止：' + str(exc))
        raise SystemExit(1)
