"""Chinese interactive launcher; no official request before manual confirmation."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description='第四问演练启动器')
    parser.add_argument('--check-only', action='store_true', help='检查环境和冻结文件后结束，不连接官方接口')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        print('需要 Python 3.10 或更新版本。')
        return 2
    settings = json.loads((ROOT / 'practice_settings.json').read_text(encoding='utf-8-sig'))
    robot_id = settings.get('robot_id', '')
    url = settings.get('url', 'http://127.0.0.1:2026')
    if not isinstance(robot_id, str) or not isinstance(url, str):
        raise ValueError('practice_settings.json 中队号和地址必须填写为字符串。')
    if not robot_id:
        if args.check_only:
            raise ValueError('请先在 practice_settings.json 中填写队号。')
        robot_id = input('请输入与官方登录身份一致的参赛队号：').strip()
    command = [sys.executable, str(ROOT / 'official_practice.py'), '--robot-id', robot_id, '--url', url]
    print('\n第四问演练脚本 | 队号：' + robot_id + '\nPython：' + sys.executable + '\n正在离线检查算法文件……', flush=True)
    check = subprocess.run(command + ['--check-only'], cwd=ROOT)
    if check.returncode:
        print('离线检查未通过，未启动演练。')
        return check.returncode
    if args.check_only:
        print('环境和冻结文件检查通过，未发送官方请求。')
        return 0
    print('\n请先在官方模拟器中登录上述队号，选择【问题4 → 演练测试】。\n'
          '点击开始演练，等待5秒倒计时结束、接口开放。\n'
          '接口不能查询当前题号或演练/正式模式，请在官方界面核对。\n'
          '确认后输入 Q4 PRACTICE 并回车；直接回车则取消。', flush=True)
    if input('确认：').strip() != 'Q4 PRACTICE':
        print('已取消，未发送官方请求。')
        return 0
    result = subprocess.run(command + ['--confirm-practice', 'I_HAVE_SELECTED_PRACTICE'], cwd=ROOT)
    if result.returncode:
        print('\n本次未确认完整成功。请保留日志并查看官方界面；状态不明时不要直接重开脚本。')
    else:
        print('\n已完成，日志与结果保存在 official_practice_logs 文件夹。')
    return result.returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\n已取消操作。')
        raise SystemExit(130)
    except Exception as exc:
        print(f'无法启动：{type(exc).__name__}: {exc}')
        raise SystemExit(2)
