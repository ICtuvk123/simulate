import json,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from q4controller import Q4Controller
from q4engine import Session,Source
from q3client import Client,canonical
from geometry import contains


class Journal:
    def __init__(self):self.rows=[]
    def append(self,row):self.rows.append(row)


class SharedStopTests(unittest.TestCase):
    def test_real_clear_stop_reuses_position_and_keeps_conservative_region(self):
        session=Session(sources=[Source(1,500,0,1500),Source(2,550,100,1500)])
        def transport(path,body,timeout):
            status,r=session.handle(path,body);return status,canonical(r)
        client=Client('local-robot',Journal(),transport=transport)
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/E_combo.json').read_text())
        controller=Q4Controller(client,config);client.action('/enter')
        controller.measure((0,0),1,'unit');controller.measure((0,0),2,'unit')
        before=controller.info(2)[1];controller.clear((500,0),1,'unit')
        rf=client.ledger.rf_count;distance=client.ledger.move_distance
        controller.share_at_actual_station((500,0))
        self.assertEqual(client.ledger.rf_count,rf+1)
        self.assertAlmostEqual(client.ledger.move_distance,distance)
        self.assertLess(controller.info(2)[1],before)
        self.assertTrue(contains(controller.polygons[2],(550,100)))
        # Repeated access to the same actual station adds no new independent RF.
        controller.share_at_actual_station((500,0))
        self.assertEqual(client.ledger.rf_count,rf+1)
    def test_forecast_point_does_not_trigger_a_measurement(self):
        session=Session(sources=[Source(1,500,0,1500)])
        def transport(path,body,timeout):
            status,r=session.handle(path,body);return status,canonical(r)
        client=Client('local-robot',Journal(),transport=transport)
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/E_combo.json').read_text())
        controller=Q4Controller(client,config);client.action('/enter');controller.measure((0,0),1,'unit')
        before=len(client.ledger.events);controller.share_at_actual_station((500,0))
        self.assertEqual(len(client.ledger.events),before)


if __name__=='__main__':unittest.main()
