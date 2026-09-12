import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from q4controller import Q4Controller
from q4engine import Session,Source
from q3client import Client,canonical
from geometry import contains


class Journal:
    def __init__(self):self.rows=[]
    def append(self,row):self.rows.append(row)


class SelectedInplaceTests(unittest.TestCase):
    def policy(self,direction=None):
        session=Session(sources=[Source(1,500,0,1000,direction)],error_mode='plus_one')
        def transport(path,body,timeout):
            status,result=session.handle(path,body);return status,canonical(result)
        client=Client('local-robot',Journal(),transport=transport)
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/D_compact_optical.json').read_text())
        config['selected_inplace_probe']=True
        policy=Q4Controller(client,config);client.action('/enter');policy.measure((0,0),1,'unit')
        return policy

    def test_actual_backside_negative_retains_region_and_pays_rf_once(self):
        p=self.policy(180.);p.clear((800.,0.),20,'unit')
        before=list(p.polygons[1]);time=p.client.ledger.virtual_time;distance=p.client.ledger.move_distance
        with patch('q4controller.shared_information_value',return_value={'estimated_gain_s':20.}):
            self.assertTrue(p.probe_selected_task_in_place(1))
            self.assertFalse(p.probe_selected_task_in_place(1))
        self.assertEqual(p.polygons[1],before)
        self.assertEqual(p.negatives[1],[(800.,0.)])
        self.assertAlmostEqual(p.client.ledger.virtual_time-time,5.)
        self.assertAlmostEqual(p.client.ledger.move_distance,distance)

    def test_actual_direction_contracts_only_selected_channel(self):
        p=self.policy();p.clear((200.,150.),20,'unit');radius=p.info(1)[1]
        with patch('q4controller.shared_information_value',return_value={'estimated_gain_s':20.}):
            self.assertTrue(p.probe_selected_task_in_place(1))
        self.assertLess(p.info(1)[1],radius)
        self.assertTrue(contains(p.polygons[1],(500.,0.)))
        self.assertEqual(p.client.ledger.events[-1]['channel'],1)

    def test_disabled_or_unprofitable_adds_no_action(self):
        p=self.policy();p.clear((200.,150.),20,'unit');count=len(p.client.ledger.events)
        with patch('q4controller.shared_information_value',return_value={'estimated_gain_s':-2.}):
            self.assertFalse(p.probe_selected_task_in_place(1))
        p.options['selected_inplace_probe']=False
        self.assertFalse(p.probe_selected_task_in_place(1))
        self.assertEqual(len(p.client.ledger.events),count)


if __name__=='__main__':unittest.main()
