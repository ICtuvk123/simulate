"""Offline launcher checks. Official runs below are fakes in temporary folders."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


HELPER_PATH = Path(__file__).resolve().parents[1] / 'test_helper.py'
SPEC = importlib.util.spec_from_file_location('gplus_test_helper_under_test', HELPER_PATH)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gplus-launcher-test-')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.root = self.project / 'experiment'
        self.root.mkdir()
        self.output = self.project / 'user_tests'
        for name, value in [('PROJECT', self.project), ('ROOT', self.root), ('OUTPUT', self.output)]:
            active = patch.object(helper, name, value)
            active.start()
            self.addCleanup(active.stop)
        # An accidental connection fails the test, even when other mocks are changed.
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex'):
            active = patch(target, side_effect=AssertionError('Offline test attempted a network connection'))
            active.start()
            self.addCleanup(active.stop)

    def arguments(self, **changes):
        values = dict(official=True, team=helper.DEFAULT_TEAM, port=2026,
                      case='TEST-CASE-0000-0001', title=helper.PRACTICE_TITLE,
                      ready=True, baseline=False, seed=13001)
        values.update(changes)
        return SimpleNamespace(**values)

    def invoke(self, argv):
        output = io.StringIO()
        with redirect_stdout(output):
            code = helper.main(argv)
        return code, output.getvalue()

    def official_argv(self):
        return ['--official', '--ready', '--case', 'TEST-CASE-0000-0001',
                '--title', helper.PRACTICE_TITLE]

    def test_default_team_is_prefilled_in_parser_and_proof(self):
        args = helper.parser().parse_args(self.official_argv())
        self.assertEqual(args.team, '202617201735')
        self.assertEqual(helper.make_proof(args)['robot_id'], '202617201735')

    def test_rejected_official_inputs_never_load_or_call_official_runner(self):
        valid = self.official_argv()
        cases = {
            'missing_readiness': [item for item in valid if item != '--ready'],
            'formal_test_title': [('--title' if item == '--title' else
                                   '问题3正式测试' if item == helper.PRACTICE_TITLE else item)
                                  for item in valid],
            'malformed_case': [item.replace('TEST-CASE-0000-0001', '../bad-case') for item in valid],
            'port_zero': valid + ['--port', '0'],
            'port_too_large': valid + ['--port', '65536'],
            'baseline_official': valid + ['--baseline'],
        }
        for label, argv in cases.items():
            with self.subTest(label=label), patch.object(helper, 'preflight') as preflight, \
                    patch.object(helper, 'load_official') as load, \
                    patch.object(helper, 'official_test') as official:
                code, output = self.invoke(argv)
                self.assertEqual(code, 2, output)
                self.assertIn('测试停止', output)
                preflight.assert_not_called()
                load.assert_not_called()
                official.assert_not_called()
        self.assertFalse(self.output.exists())

    def fake_official_app(self, success=True, *, raise_after_print=False):
        source = self.project / 'training_logs' / 'fake-current-run'
        metrics = dict(clear_count=11 if success else 3,
                       total_time=2936.872026 if success else 1234.5,
                       average_localization_clear_time_s_per_source=266.988366 if success else 411.5,
                       completion_proved=success,
                       client_error=None if success else 'simulated connection failure',
                       accounting_warnings=[])

        def run(proof):
            print('fake official progress; no network was used')
            if raise_after_print:
                print('fake failure detail on stderr', file=sys.stderr)
                raise RuntimeError('simulated official setup failure')
            source.mkdir(parents=True)
            helper.write_json(source / 'ui_mode_proof.json', proof)
            helper.write_json(source / 'metrics.json', metrics)
            print(source)
            return 0 if success else 1

        return SimpleNamespace(run=Mock(side_effect=run)), source

    def test_official_success_records_case_mean_and_output_directory(self):
        app, source = self.fake_official_app()
        with patch.object(helper, 'preflight', return_value=('test-version', 16)), \
                patch.object(helper, 'load_official', return_value=app):
            code, output = self.invoke(self.official_argv())
        self.assertEqual(code, 0, output)
        app.run.assert_called_once()
        proof = app.run.call_args.args[0]
        self.assertEqual(proof['robot_id'], '202617201735')
        self.assertEqual(proof['case_code'], 'TEST-CASE-0000-0001')
        self.assertFalse(proof['independently_verified_by_agent'])
        directory, = self.output.iterdir()
        result = json.loads((directory / 'test_result.json').read_text(encoding='utf-8'))
        self.assertTrue(result['success'])
        self.assertEqual(result['seconds_per_source'], 266.988366)
        self.assertEqual(Path(result['source_directory']), source)
        text = (directory / '测试结果.txt').read_text(encoding='utf-8-sig')
        self.assertIn('平均时间：266.988366 秒/源', text)
        self.assertIn(str(directory), output)
        self.assertIn(str(source), text)
        self.assertFalse((self.project / 'audit').exists())

    def test_official_partial_failure_keeps_metrics_and_marks_mean_diagnostic(self):
        app, source = self.fake_official_app(success=False)
        with patch.object(helper, 'preflight', return_value=('test-version', 16)), \
                patch.object(helper, 'load_official', return_value=app):
            code, output = self.invoke(self.official_argv())
        self.assertEqual(code, 1, output)
        directory, = self.output.iterdir()
        result = json.loads((directory / 'test_result.json').read_text(encoding='utf-8'))
        self.assertFalse(result['success'])
        self.assertEqual(result['seconds_per_source'], 411.5)
        self.assertEqual(Path(result['source_directory']), source)
        self.assertIn('已清除部分均时（仅供诊断）：411.500000 秒/源', output)
        self.assertIn('simulated connection failure', output)
        self.assertIn(str(directory), output)

    def test_official_raised_failure_preserves_stdout_stderr_and_traceback(self):
        app, _ = self.fake_official_app(raise_after_print=True)
        with patch.object(helper, 'preflight', return_value=('test-version', 16)), \
                patch.object(helper, 'load_official', return_value=app):
            code, output = self.invoke(self.official_argv())
        self.assertEqual(code, 1, output)
        directory, = self.output.iterdir()
        console = (directory / 'console.log').read_text(encoding='utf-8')
        self.assertIn('fake official progress', console)
        self.assertIn('fake failure detail on stderr', console)
        self.assertIn('simulated official setup failure',
                      (directory / 'error.log').read_text(encoding='utf-8'))
        result = json.loads((directory / 'test_result.json').read_text(encoding='utf-8'))
        self.assertFalse(result['success'])
        self.assertIn(str(directory), output)

    def test_result_directory_with_wrong_case_is_rejected(self):
        proof = helper.make_proof(self.arguments())
        source = self.project / 'training_logs' / 'different-case'
        source.mkdir(parents=True)
        helper.write_json(source / 'ui_mode_proof.json', dict(proof, case_code='TEST-CASE-0000-0002'))
        with self.assertRaisesRegex(RuntimeError, '结果目录'):
            helper.find_official_directory(str(source), proof)

    def test_local_execution_is_a_child_process_and_uses_requested_seed(self):
        directory = self.output / 'local-success'
        directory.mkdir(parents=True)
        source = self.root / 'runs' / 'fake-local'
        result = dict(directory=str(source), cleared=8, count=8, total_time=2400.0,
                      seconds_per_source=300.0, completion_proved=True)

        def child(command, **kwargs):
            self.assertEqual(command, [sys.executable, '-u', str(self.root / 'run_candidate.py'),
                                       '--seed', '42', '--baseline'])
            self.assertEqual(kwargs['cwd'], self.root)
            self.assertIs(kwargs['stderr'], subprocess.STDOUT)
            self.assertNotIn('shell', kwargs)
            kwargs['stdout'].write(json.dumps(result))
            return SimpleNamespace(returncode=0)

        before = set(sys.modules)
        with patch.object(helper.subprocess, 'run', side_effect=child) as execute, \
                patch.object(helper, 'load_official') as load:
            actual = helper.local_test(self.arguments(official=False, seed=42, baseline=True), directory)
        execute.assert_called_once()
        load.assert_not_called()
        self.assertFalse({'runner', 'engine'} & (set(sys.modules) - before))
        self.assertEqual(actual['strategy'], 'G')
        self.assertTrue(actual['success'])
        self.assertEqual(actual['seconds_per_source'], 300.0)

    def test_local_child_failure_saves_error_and_console_log(self):
        def child(command, **kwargs):
            kwargs['stdout'].write('simulated local child failure\n')
            return SimpleNamespace(returncode=7)

        with patch.object(helper, 'preflight', return_value=('test-version', 16)), \
                patch.object(helper.subprocess, 'run', side_effect=child):
            code, output = self.invoke(['--local', '--seed', '99'])
        self.assertEqual(code, 1, output)
        directory, = self.output.iterdir()
        self.assertIn('simulated local child failure', (directory / 'console.log').read_text(encoding='utf-8'))
        self.assertIn('RuntimeError', (directory / 'error.log').read_text(encoding='utf-8'))
        self.assertFalse(json.loads((directory / 'test_result.json').read_text(encoding='utf-8'))['success'])
        self.assertIn(str(directory), output)

    def test_failed_frozen_check_prevents_run_and_output_creation(self):
        with patch.object(helper, 'preflight', side_effect=RuntimeError('frozen file changed')), \
                patch.object(helper, 'official_test') as official, \
                patch.object(helper.subprocess, 'run') as child:
            code, output = self.invoke(self.official_argv())
        self.assertEqual(code, 1, output)
        self.assertIn('frozen file changed', output)
        official.assert_not_called()
        child.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_result_directory_permission_failure_is_reported_without_second_exception(self):
        with patch.object(helper, 'preflight', return_value=('test-version', 16)), \
                patch.object(Path, 'mkdir', side_effect=PermissionError('simulated permission denied')), \
                patch.object(helper, 'local_test') as local:
            code, output = self.invoke(['--local'])
        self.assertEqual(code, 1, output)
        self.assertIn('simulated permission denied', output)
        self.assertIn('结果文件夹无法写入', output)
        local.assert_not_called()
        self.assertFalse(self.output.exists())


class RealOfflinePreflightTests(unittest.TestCase):
    def test_real_check_validates_frozen_files_without_network_or_simulator_import(self):
        # Fresh interpreter so the test suite's own imports cannot mask isolation bugs.
        script = '''
import socket
import sys
import json
from unittest.mock import patch
def denied(*args, **kwargs):
    raise AssertionError("--check attempted network access")
with patch("socket.create_connection", side_effect=denied), patch("socket.socket.connect", side_effect=denied), patch("socket.socket.connect_ex", side_effect=denied):
    import test_helper
    from tempfile import TemporaryDirectory
    from pathlib import Path
    with TemporaryDirectory() as target:
        test_helper.OUTPUT = Path(target) / "must_not_exist"
        assert test_helper.main(["--check"]) == 0
        assert not test_helper.OUTPUT.exists()
        # Real frozen verification must also reject modified candidate options.
        app = test_helper.load_official()
        fake_root = Path(target) / "modified_freeze"
        fake_root.mkdir()
        (fake_root / "FREEZE.json").write_bytes((app.ROOT / "FREEZE.json").read_bytes())
        candidate = json.loads((app.ROOT / "candidate.json").read_text(encoding="utf-8"))
        candidate["options"]["__offline_test_changed_option__"] = True
        (fake_root / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
        with patch.object(app, "ROOT", fake_root):
            assert test_helper.main(["--check"]) != 0
        assert not test_helper.OUTPUT.exists()
    assert "runner" not in sys.modules
    assert "engine" not in sys.modules
    print("OFFLINE_CHECK_AND_ISOLATION_PASS")
'''
        completed = subprocess.run([sys.executable, '-X', 'utf8', '-c', script],
                                   cwd=HELPER_PATH.parent, capture_output=True, text=True,
                                   encoding='utf-8', timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('OFFLINE_CHECK_AND_ISOLATION_PASS', completed.stdout)
        self.assertIn('16 个冻结文件', completed.stdout)


if __name__ == '__main__':
    unittest.main()
