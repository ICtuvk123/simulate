import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from coverage import validate_completion
from directional_geometry import skeleton


class ExitAuditTests(unittest.TestCase):
    def base(self):return [dict(path='/clear',channel=ch,result='success',position=(0,0)) for ch in range(1,11)]
    def test_discovered_sixteen_is_not_cleared_sixteen(self):
        events=self.base()+[dict(path='/measure',channel=ch,result='direction',position=(0,0)) for ch in range(11,17)]+[dict(path='/exit')]
        cert=dict(kind='q4_sixteen_actual_successes',cleared_channels=list(range(1,11)))
        self.assertFalse(validate_completion(events,cert)[0])
    def test_planned_stations_do_not_count_as_negative_feedback(self):
        events=self.base()+[dict(path='/exit')]
        cert=dict(kind='q4_actual_directional_local_hull',cleared_channels=list(range(1,11)),empty_channels=list(range(11,21)),planned_stations=skeleton())
        self.assertFalse(validate_completion(events,cert)[0])
    def test_full_actual_negative_station_set_proves_empty_partition(self):
        events=self.base()+[dict(path='/measure',channel=ch,result='no_signal',position=q) for ch in range(11,21) for q in skeleton()]+[dict(path='/exit')]
        cert=dict(kind='q4_actual_directional_local_hull',cleared_channels=list(range(1,11)),empty_channels=list(range(11,21)))
        self.assertTrue(validate_completion(events,cert)[0])
        events.insert(-1,dict(path='/measure',channel=11,result='near',position=(0,0)))
        self.assertFalse(validate_completion(events,cert)[0])


if __name__=='__main__':unittest.main()
