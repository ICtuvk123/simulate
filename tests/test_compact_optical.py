import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from compact_optical import rectangle_covers,verify_cover,choose_cover,expected_optical_cost
from test_shared_stops import Journal
from q4engine import Session,Source
from q4controller import Q4Controller
from q3client import Client,canonical


class CompactOpticalTests(unittest.TestCase):
    def test_rectangle_is_continuously_covered_by_cell_disks(self):
        poly=[(0,-4),(70,-4),(70,4),(0,4)]
        candidates=list(rectangle_covers(poly,2));self.assertTrue(candidates)
        for points,witness in candidates:
            self.assertEqual(len(points),2);self.assertTrue(verify_cover(witness,points))
            broken=dict(witness,bounds=[-100,-100,100,100]);self.assertFalse(verify_cover(broken,points))
    def test_failed_first_attempt_pays_motion_and_three_seconds(self):
        cost,fails=expected_optical_cost((0,0),[(0,0),(60,0)],[dict(g=(60,0),weight=1.)])
        self.assertEqual(cost,20);self.assertEqual(fails,1)
    def test_area_too_large_does_not_claim_a_small_cover(self):
        self.assertEqual(list(rectangle_covers([(-200,-200),(200,-200),(200,200),(-200,200)],4)),[])
    def test_actual_second_optical_success_after_first_failure_preserves_channel(self):
        session=Session(sources=[Source(2,67,0,1500)])
        def transport(path,body,timeout):
            status,r=session.handle(path,body);return status,canonical(r)
        client=Client('local-robot',Journal(),transport=transport)
        options=json.loads((Path(__file__).resolve().parents[1]/'configs/E_combo.json').read_text())
        c=Q4Controller(client,options);client.action('/enter')
        poly=[(0,-4),(70,-4),(70,4),(0,4)]
        cover=choose_cover(poly,(0,0),[dict(g=(10,0),weight=.9),dict(g=(67,0),weight=.1)],max_points=2)
        self.assertTrue(verify_cover(cover['witness'],cover['points']))
        first=c.clear(cover['points'][0],2,'unit');self.assertFalse(first)
        second=c.clear(cover['points'][1],2,'unit');self.assertTrue(second)
        self.assertEqual(client.ledger.channel,1);self.assertEqual(client.ledger.optical_failed_count,1)


if __name__=='__main__':unittest.main()
