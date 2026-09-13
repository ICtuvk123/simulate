"""Manual Q4 practice entry. Offline preflight never opens a connection."""
import argparse
import hashlib
import importlib.util
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIRMATION = 'I_HAVE_SELECTED_PRACTICE'


def frozen_info():
    incumbent = json.loads((ROOT / 'INCUMBENT.json').read_text(encoding='utf-8'))
    paths = {key: (ROOT / incumbent[key]).resolve()
             for key in ('freeze', 'configuration', 'code_directory')}
    if not all(p.is_relative_to(ROOT) for p in paths.values()):
        raise ValueError('Frozen paths must stay inside this package')
    spec = importlib.util.spec_from_file_location('_practice_integrity', ROOT / 'code/verify_freeze.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    integrity = checker.verify(paths['freeze'], paths['code_directory'], paths['configuration'])
    if not integrity['valid']:
        raise RuntimeError('Frozen integrity check failed before any connection: ' + str(integrity['failures']))
    return incumbent, paths, integrity


def load_frozen(paths):
    """Reject cached development modules instead of silently mixing policies."""
    code = paths['code_directory']
    for source in code.glob('*.py'):
        cached = sys.modules.get(source.stem)
        if cached is not None and Path(getattr(cached, '__file__', '')).resolve() != source.resolve():
            raise RuntimeError('Run the practice entry in a fresh Python process: ' + source.stem)
    sys.path.insert(0, str(code))
    from q3client import Client, JsonlJournal, identifier
    from q4controller import Q4Controller
    from practice_transport import PracticeTransport
    from verify_exit import verify
    from independent_exit import verify as independent_verify
    return Client, JsonlJournal, identifier, Q4Controller, PracticeTransport, verify, independent_verify


def preflight(url='http://127.0.0.1:2026', robot_id=None):
    incumbent, paths, integrity = frozen_info()
    modules = load_frozen(paths)
    if robot_id is not None and not modules[2](robot_id, 64):
        raise ValueError('参赛队号格式无效：需为1至64个UTF-8字节，不能含控制字符。')
    modules[4](url, CONFIRMATION)  # Construction validates; it never connects.
    return dict(valid=True, version=incumbent['version'], integrity=integrity,
                url=url, network_requests=0, required_ui_task=4,
                mode_verifiable_by_api=False)


def run_practice(robot_id, confirmation, url='http://127.0.0.1:2026',
                 log_root=None, quiet=False, transport_factory=None):
    if confirmation != CONFIRMATION:
        raise ValueError('必须先在官方界面确认问题4演练测试。')
    incumbent, paths, integrity = frozen_info()
    Client, Journal, identifier, Controller, Transport, verify, independent_verify = load_frozen(paths)
    if not identifier(robot_id, 64):
        raise ValueError('参赛队号格式无效。')
    adapter = Transport(url, confirmation)
    if transport_factory is not None:
        adapter = transport_factory(url, confirmation)
    options = json.loads(paths['configuration'].read_text(encoding='utf-8'))
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8]
    folder = Path(log_root or ROOT / 'official_practice_logs').resolve() / run_id
    folder.mkdir(parents=True)
    manifest = dict(run_id=run_id, mode='offline_http_fixture' if transport_factory is not None else 'operator_declared_practice', task=4,
                    mode_verified_by_api=False, robot_id=robot_id, url=url,
                    version=incumbent['version'], integrity=integrity, policy_options=options,
                    freeze_sha256=hashlib.sha256(paths['freeze'].read_bytes()).hexdigest(),
                    entry_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'freeze.json').write_bytes(paths['freeze'].read_bytes())
    path = folder / 'requests.jsonl'
    journal = Journal(path, manifest)

    class ProgressClient(Client):
        def action(self, endpoint, position=None, channel=None):
            response = super().action(endpoint, position, channel)
            # Only validated, accepted actions reach this display.
            if not quiet:
                if endpoint == '/enter':
                    print(f"已进入：剩余现实时间 {response['remaining_real_duration_s']:.1f} 秒。", flush=True)
                elif endpoint == '/clear':
                    result = '清除成功' if response['clear_result'] == 'success' else '本点未清除'
                    print(f"频道 {channel}：{result}；已清除 {len(self.ledger.cleared)} 个；"
                          f"虚拟时间 {self.ledger.virtual_time:.2f} 秒。", flush=True)
                elif endpoint == '/measure' and self.ledger.rf_count % 20 == 0:
                    print(f"检测 {self.ledger.rf_count} 次；已清除 {len(self.ledger.cleared)} 个；"
                          f"虚拟时间 {self.ledger.virtual_time:.2f} 秒。", flush=True)
            return response

    client = ProgressClient(robot_id, journal, transport=adapter)
    if not quiet:
        print('算法：' + incumbent['version'] + '\n日志：' + str(folder), flush=True)
    error = None
    interrupted = False
    started = time.monotonic()
    try:
        Controller(client, options).run()
    except KeyboardInterrupt:
        interrupted = True
        error = 'KeyboardInterrupt: 操作人员停止；未自动发送退出或新动作。'
        journal.append(dict(event='client_stop', error=error))
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        journal.append(dict(event='client_stop', error=error))
    finally:
        journal.close()
    policy_wall_time = time.monotonic() - started

    def checked(function):
        try:
            return function(path)
        except Exception as exc:
            return dict(valid=False, error=f'{type(exc).__name__}: {exc}')

    verification = checked(verify)
    independent = checked(independent_verify)
    proved = bool(not error and verification['valid'] and independent['valid'])
    metrics = client.ledger.metrics()
    summary = dict(version=incumbent['version'], operator_declared_task=4,
                   mode=manifest['mode'], mode_verified_by_api=False,
                   completion_proved=proved, error=error, interrupted=interrupted,
                   clear_count=metrics['clear_count'], total_virtual_s=metrics['total_time'],
                   mean_virtual_s_per_cleared_source=metrics['mean_time_per_clear'] if proved else None,
                   policy_wall_time_s=policy_wall_time,
                   costs={key: metrics[key] for key in ('move_time', 'RF_detection_time',
                          'channel_switch_time', 'optical_time', 'clear_time')},
                   rf_count=metrics['RF_detection_count'], optical_failures=metrics['optical_failed_count'],
                   network_retries=metrics['network_retry_count'],
                   journal=str(path), verification=verification, independent_exit=independent)
    (folder / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary, (130 if interrupted else 0 if proved else 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description='第四问官方演练入口；测试模式必须在官方界面选择。')
    parser.add_argument('--robot-id')
    parser.add_argument('--confirm-practice', choices=[CONFIRMATION])
    parser.add_argument('--url', default='http://127.0.0.1:2026')
    parser.add_argument('--log-dir', help='日志保存目录，默认位于本程序旁')
    parser.add_argument('--check-only', action='store_true', help='只检查冻结文件和参数，不发送网络请求')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)
    if not args.check_only and (args.robot_id is None or args.confirm_practice is None):
        parser.error('运行需 --robot-id 和 --confirm-practice；离线检查请使用 --check-only。')
    try:
        if args.check_only:
            result, status = preflight(args.url, args.robot_id), 0
        else:
            result, status = run_practice(args.robot_id, args.confirm_practice, args.url, args.log_dir, args.quiet)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return status
    except Exception as exc:
        print(f'启动失败：{type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
