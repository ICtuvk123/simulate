import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from r3_process_budget import run_bounded,utc_epoch


class BudgetTests(unittest.TestCase):
    def test_expired_or_cancelled_cannot_launch(self):
        with patch('r3_process_budget.subprocess.Popen') as launch:
            self.assertEqual(run_bounded([],'.',time.time()-1)['stopped'],'not_started_budget')
            flag=threading.Event();flag.set()
            self.assertEqual(run_bounded([],'.',time.time()+10,flag)['stopped'],'not_started_budget')
            launch.assert_not_called()

    def test_completed_output_is_preserved(self):
        result=run_bounded([sys.executable,'-c','print("test-output")'],'.',time.time()+10)
        self.assertEqual(result['returncode'],0);self.assertIsNone(result['stopped'])
        self.assertEqual(result['stdout'].strip(),'test-output')

    def test_deadline_stops_owned_process(self):
        start=time.time()
        result=run_bounded([sys.executable,'-c','import time; time.sleep(60)'],'.',start+.4)
        self.assertEqual(result['stopped'],'hard_deadline')
        self.assertLess(time.time()-start,8)

    def test_utc_deadline_is_not_virtual_action_time(self):
        self.assertEqual(utc_epoch('1970-01-01T00:00:10Z'),10)


if __name__=='__main__':unittest.main()
