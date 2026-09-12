"""Offline tests: prohibit networking while testing manual entry and case reuse."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import manual_official_practice as app


def deny_network(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'subprocess.Popen'):
        raise AssertionError('No network or process launch is allowed in these tests')


sys.addaudithook(deny_network)


class ManualPracticeTests(unittest.TestCase):
    def proof(self, **changes):
        value = dict(case_code='TEST-ABCD-EFGH-IJKL', robot_id='test-team', port=2026,
                     observed_text='问题3演练测试',
                     observed_at_utc=datetime.now(timezone.utc).isoformat())
        value.update(changes)
        return value

    def test_frozen_both_policies_offline(self):
        for strategy in ('F', 'G'):
            self.assertTrue(app.verify_policy(strategy)[3])

    def test_prepare_does_not_ask_or_run(self):
        with patch.object(sys, 'argv', ['manual', '--prepare-only']), patch('builtins.input') as ask, \
                patch.object(app, 'run_confirmed_case') as run, redirect_stdout(io.StringIO()):
            self.assertEqual(app.main(), 0)
            ask.assert_not_called()
            run.assert_not_called()

    def test_formal_title_is_rejected_before_transport(self):
        with patch.object(app, 'PracticeTransport') as transport, tempfile.TemporaryDirectory() as directory:
            with patch.object(app, 'PROJECT', Path(directory)), \
                    patch.object(app, 'verify_policy', return_value=({}, '', object, {})):
                with self.assertRaises(ValueError):
                    app.run_confirmed_case('G', 'test-team', 2026, self.proof(observed_text='问题3正式测试'))
            transport.assert_not_called()

    def test_cancel_sends_nothing(self):
        replies = ['G', 'test-team', '', '问题3演练测试', 'TEST-ABCD-EFGH-IJKL', '取消']
        with patch.object(sys, 'argv', ['manual']), patch('builtins.input', side_effect=replies), \
                patch.object(app, 'run_confirmed_case') as run, redirect_stdout(io.StringIO()):
            self.assertEqual(app.main(), 0)
            run.assert_not_called()

    def test_invalid_case_and_wrong_problem_rejected(self):
        for title, case in [('问题4演练测试', 'TEST-ABCD-EFGH-IJKL'), ('问题3演练测试', '../x')]:
            with self.assertRaises(ValueError):
                app.validate_case('test-team', 2026, title, case)

    def test_expired_confirmation_rejected(self):
        old = (datetime.now(timezone.utc) - timedelta(seconds=121)).isoformat()
        with self.assertRaises(ValueError):
            app.claim_case(self.proof(observed_at_utc=old))

    def test_second_case_claim_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app, 'PROJECT', Path(directory)):
            app.claim_case(self.proof())
            with self.assertRaises(FileExistsError):
                app.claim_case(self.proof())

    def test_prior_official_case_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app, 'PROJECT', Path(directory)):
            previous = Path(directory) / 'training_logs/previous/ui_mode_proof.json'
            previous.parent.mkdir(parents=True)
            previous.write_text(json.dumps(self.proof()), encoding='utf-8')
            with self.assertRaises(ValueError):
                app.claim_case(self.proof())


if __name__ == '__main__':
    unittest.main()
