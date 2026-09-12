import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from action_diagnostics import diagnose


class DiagnosticsTests(unittest.TestCase):
    def test_interval_and_attributed_distances_are_different(self):
        def event(path,ch,t,move,**response):
            return dict(path=path,channel=ch,move_time=move,response=dict(accepted=True,virtual_time_s=t,**response))
        events=[event('/measure',1,10,1,measure_result='direction'),
                event('/measure',2,30,3,measure_result='no_signal'),
                event('/clear',1,45,2,clear_result='success'),event('/exit',None,80,0)]
        d=diagnose(events,[])
        self.assertEqual(d['mean_interval_travel_m'],25)
        self.assertEqual(d['mean_channel_action_travel_m'],10)
        self.assertEqual(d['tail_after_last_clear_s'],35)
        self.assertEqual(d['mean_discovery_to_clear_s'],35)

    def test_unfinished_case_has_no_false_tail_or_clears(self):
        d=diagnose([],[])
        self.assertIsNone(d['tail_after_last_clear_s'])
        self.assertEqual(d['cleared_count'],0)


if __name__=='__main__':unittest.main()
