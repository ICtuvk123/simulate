import json,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from routing import open_route,refined_open_route,route_length
from test_shared_stops import Journal
from q4engine import Session,Source
from q4controller import Q4Controller
from q3client import Client,canonical


class RouteForecastTests(unittest.TestCase):
    def test_relocation_keeps_all_tasks_and_never_lengthens_open_route(self):
        points=[(1000*math.cos(k*1.7),700*math.sin(k*.6)) for k in range(18)]
        p=(350,250);old=open_route(p,points);new=refined_open_route(p,points)
        self.assertEqual(sorted(new),list(range(len(points))))
        self.assertLessEqual(route_length(p,points,new),route_length(p,points,old)+1e-6)
    def test_forecast_never_becomes_a_negative_or_removes_a_fallback(self):
        session=Session(sources=[Source(1,500,0,1500)])
        def transport(path,body,timeout):
            status,r=session.handle(path,body);return status,canonical(r)
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/E_combo.json').read_text())
        config['forecast_search']=True
        client=Client('local-robot',Journal(),transport=transport)
        c=Q4Controller(client,config);client.action('/enter')
        c.polygons[1]=[(490,-1),(510,-1),(510,1),(490,1)]
        c.positives[1]=[((0,0),0)]
        # Deliberately favorable planning geometry, while actual empty-channel
        # refresh stays unproved. The certificate is never used for exit here.
        class PlannerProof:
            def prove(self,stations):return {'complete':len(stations)>5}
        c.coverage=PlannerProof();c.remaining=[(5000,0),(6000,0),(100,0),(0,100),(0,-100),(-100,0)]
        before=list(c.remaining);c.scan_for_forecast_complement()
        self.assertEqual(c.remaining,before)
        self.assertTrue(any(r.get('reason')=='q4_forecast_scan_plan' for r in client.journal.rows))
        self.assertTrue(all(q==(0.,0.) for stations in c.negatives.values() for q in stations))
        self.assertFalse(c.empty)


if __name__=='__main__':unittest.main()
