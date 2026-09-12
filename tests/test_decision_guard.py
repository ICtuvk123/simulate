import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from decision_guard import DecisionGuard


class DecisionGuardTests(unittest.TestCase):
    def test_controller_cannot_open_adjacent_truth_or_directory(self):
        guard=DecisionGuard()
        with guard:
            with self.assertRaisesRegex(RuntimeError,'data-channel'):
                Path(__file__).read_text()
            with self.assertRaisesRegex(RuntimeError,'data-channel'):
                list(Path('.').iterdir())
        self.assertFalse(guard.active)
    def test_engine_import_and_network_events_blocked(self):
        with DecisionGuard() as guard:
            for event,args in [('import',('q4engine',)),('socket.connect',()),('subprocess.Popen',())]:
                with self.assertRaises(RuntimeError):guard.check(event,args)


if __name__=='__main__':unittest.main()
