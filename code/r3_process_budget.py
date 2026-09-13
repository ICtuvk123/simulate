"""Bound owned experiment processes by UTC; never outlive the registered round."""
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path


def utc_epoch(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def stop_owned_tree(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        system_root = next(v for k, v in os.environ.items() if k.casefold() == 'systemroot')
        subprocess.run([str(Path(system_root) / 'System32/taskkill.exe'), '/PID', str(process.pid), '/T', '/F'],
                       capture_output=True, timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        import signal
        os.killpg(process.pid, signal.SIGTERM)
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def run_bounded(command, cwd, hard_stop_epoch, stop_event=None):
    if time.time() >= hard_stop_epoch or (stop_event is not None and stop_event.is_set()):
        return dict(returncode=None, stdout='', stderr='', stopped='not_started_budget')
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding='utf-8', errors='replace',
                               start_new_session=os.name != 'nt',
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    reason = None
    try:
        while True:
            remaining = hard_stop_epoch - time.time()
            if remaining <= 0 or (stop_event is not None and stop_event.is_set()):
                reason = 'hard_deadline' if remaining <= 0 else 'requested_stop'
                stop_owned_tree(process)
                stdout, stderr = process.communicate(timeout=10)
                break
            try:
                stdout, stderr = process.communicate(timeout=min(1., remaining))
                break
            except subprocess.TimeoutExpired:
                pass
    except BaseException:
        stop_owned_tree(process)
        raise
    return dict(returncode=process.returncode, stdout=stdout, stderr=stderr, stopped=reason)
