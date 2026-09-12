import json,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from q4engine import Session,Source
from q4controller import Q4Controller
from q3client import Client,canonical
from geometry import contains


class Journal:
    def __init__(self):self.rows=[]
    def append(self,row):self.rows.append(row)


class FirstDirectionTests(unittest.TestCase):
    def test_replan_after_positive_keeps_region_and_does_not_visit_other_end(self):
        g=(60*math.cos(math.radians(1)),60*math.sin(math.radians(1)))
        session=Session(sources=[Source(1,*g,1500)],error_mode='minus_one')
        def transport(path,body,timeout):
            status,r=session.handle(path,body);return status,canonical(r)
        client=Client('local-robot',Journal(),transport=transport)
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/H0.json').read_text());config.update(probe_b=30,replan_after_direction=True)
        policy=Q4Controller(client,config);client.action('/enter');policy.measure((0,0),1,'unit')
        before=client.ledger.rf_count;policy.localize(1)
        self.assertEqual(client.ledger.rf_count-before,1)
        self.assertNotIn(1,client.ledger.cleared)
        self.assertTrue(contains(policy.polygons[1],g))
        self.assertTrue(any(r.get('reason')=='q4_replan_after_first_direction' for r in client.journal.rows))
        self.assertFalse(any(r.get('reason')=='q4_paired_negative_clip' for r in client.journal.rows))


if __name__=='__main__':unittest.main()
