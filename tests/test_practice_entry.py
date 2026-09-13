import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PracticeEntryTests(unittest.TestCase):
    def execute(self, *args, **kwargs):
        return subprocess.run([sys.executable, '-X', 'utf8', *args], cwd=ROOT,
                              capture_output=True, text=True, encoding='utf-8', timeout=90, **kwargs)

    def test_check_only_never_connects_and_loads_exact_freeze(self):
        script = "import sys,runpy;sys.addaudithook(lambda e,a: (_ for _ in ()).throw(AssertionError(e)) if e=='socket.connect' else None);sys.argv=['official_practice.py','--check-only','--robot-id','202617201735'];runpy.run_path('official_practice.py',run_name='__main__')"
        p = self.execute('-c', script)
        self.assertEqual(p.returncode, 0, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['network_requests'], 0)
        self.assertEqual(result['version'], 'R2_S22_ML-validated-20260912')
        self.assertEqual(result['integrity']['source_count'], 71)

    def test_missing_confirmation_is_rejected_without_connection(self):
        p = self.execute('official_practice.py', '--robot-id', '202617201735')
        self.assertEqual(p.returncode, 2)

    def test_nonloopback_address_rejected_in_preflight(self):
        p = self.execute('official_practice.py', '--check-only', '--url', 'http://192.0.2.1:2026')
        self.assertEqual(p.returncode, 2)

    def test_invalid_robot_id_rejected_in_preflight(self):
        p = self.execute('official_practice.py', '--check-only', '--robot-id', 'bad\nteam')
        self.assertEqual(p.returncode, 2)

    def test_chinese_launcher_cancellation_only_runs_preflight(self):
        script = "import start_practice as p;from unittest.mock import patch;from types import SimpleNamespace;\nwith patch('builtins.input',return_value=''),patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:\n assert p.main()==0;assert run.call_count==1;assert '--check-only' in run.call_args.args[0];assert '202617201735' in run.call_args.args[0]"
        p = self.execute('-c', script)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_actual_frozen_controller_and_http_adapter_offline(self):
        with tempfile.TemporaryDirectory(prefix='q4-practice-') as folder:
            for case in ('success', 'lost_reply', 'rejected', 'http_error', 'uncertain', 'budget'):
                with self.subTest(case=case):
                    p = self.execute('code/practice_offline_check.py', '--case', case, '--output', folder)
                    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                    result = json.loads(p.stdout)
                    self.assertTrue(result['valid'])
                    self.assertEqual(result['actual_network_requests'], 0)


if __name__ == '__main__':
    unittest.main()
