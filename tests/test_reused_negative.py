import json,math,random,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from geometry import outer_disk,clip_bearing,contains
from reused_negative import make_reuse_probe,verify_reused_geometry,apply_reused_negative,choose_reused_probe
from audit import audit_reused_witness
from lookahead import receives
from q4engine import Session,Source
from q3client import Client,canonical,ProtocolError
from q4controller import Q4Controller


class ReusedNegativeTests(unittest.TestCase):
    def setUp(self):self.poly=clip_bearing(outer_disk(),(0.,0.),0.)

    def make(self,h=(750.,80.),b=14.):
        return make_reuse_probe(self.poly,(0.,0.),0.,h,b)

    def test_asymmetric_geometry_and_second_negative(self):
        w=self.make()
        self.assertTrue(w['geometry_valid']);self.assertTrue(verify_reused_geometry(self.poly,w))
        self.assertEqual(w['new_station'],(750.,-14.))
        cut=apply_reused_negative(self.poly,dict(w,results=['no_signal','no_signal']))
        self.assertTrue(contains(cut,(500.,0.)));self.assertFalse(contains(cut,(1000.,0.)))
        for results in [[],['no_signal'],['no_signal','direction'],['no_signal','near']]:
            with self.assertRaises(ValueError):apply_reused_negative(self.poly,dict(w,results=results))

    def test_invalid_old_negative_geometry_is_rejected(self):
        for point in [(750.,5.),(750.,1000.),(-1.,80.),(0.,80.)]:
            w=self.make(point)
            self.assertFalse(w['geometry_valid'])
            self.assertFalse(verify_reused_geometry(self.poly,w))

    def test_audit_checks_channel_order_cleared_and_real_responses(self):
        w=dict(self.make(),channel=1,before_polygon=self.poly,results=['no_signal','no_signal'])
        pos={1:[((0.,0.),0.)]};neg={1:[w['historical_negative'],w['new_station']]}
        self.assertTrue(audit_reused_witness(w,pos,neg,set()))
        self.assertFalse(audit_reused_witness(w,pos,neg,{1}))
        self.assertFalse(audit_reused_witness(w,pos,{2:neg[1]},set()))
        self.assertFalse(audit_reused_witness(w,pos,{1:neg[1][::-1]},set()))
        self.assertFalse(audit_reused_witness(w,{},neg,set()))
        self.assertFalse(audit_reused_witness(w,pos,{1:[w['historical_negative']]},set()))

    def test_far_sources_cannot_give_second_no_signal_after_historical_negative(self):
        rng=random.Random(27801);checked=0
        for side in (-1,1):
            w=self.make((750.,side*80.),14.)
            for i in range(800):
                x=rng.uniform(750.,1499.);e=math.radians(rng.uniform(-1.,1.));g=(x,x*math.tan(e))
                central=math.atan2(-g[1],-g[0]);angle=central+rng.uniform(-math.pi/2,math.pi/2)
                heading=(math.cos(angle),math.sin(angle));radius=max(1000.,math.hypot(*g))
                self.assertTrue(receives(g,radius,heading,(0.,0.)))
                if not receives(g,radius,heading,w['historical_negative']):
                    self.assertTrue(receives(g,radius,heading,w['new_station']));checked+=1
        self.assertGreater(checked,20)

    def test_ranking_has_one_new_rf_and_no_truth_inputs(self):
        s=(0.,0.);h=(750.,80.);args=(self.poly,(750.,-14.),[(s,0.)],[h],[h],dict(lookahead_positions=5))
        a=choose_reused_probe(*args);b=choose_reused_probe(*args)
        self.assertEqual(a,b);self.assertIsNotNone(a)
        self.assertTrue(a['assumptions_only_for_ranking'])
        self.assertEqual(a['new_rf_actions'],1)
        self.assertEqual(a['historical_rf_cost_s'],0.)
        self.assertAlmostEqual(sum(a['branches'].values()),1.)

    def fixture(self,x,heading):
        class Journal:
            def __init__(self):self.rows=[]
            def append(self,row):self.rows.append(row)
        engine=Session(sources=[Source(1,x,0.,1500.,heading)])
        engine._error=lambda ch,p:0. # A valid fixed spatial error field for this fixture.
        def transport(path,body,timeout):
            status,response=engine.handle(path,body);return status,canonical(response)
        client=Client('local-robot',Journal(),transport=transport)
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/R2_AR_reuse.json').read_text())
        policy=Q4Controller(client,config);client.action('/enter')
        self.assertEqual(policy.measure((0.,0.),1,'unit'),'direction')
        self.assertEqual(policy.measure((750.,80.),1,'unit'),'no_signal')
        before=list(policy.polygons[1]);w=make_reuse_probe(before,(0.,0.),0.,(750.,80.),14.)
        return client,policy,before,dict(probe=w,point=w['new_station'])

    def test_actual_second_negative_pays_only_one_new_rf_and_keeps_truth(self):
        client,policy,before,selected=self.fixture(300.,180.)
        count=client.ledger.rf_count;policy.execute_reused_probe(1,selected,before)
        self.assertEqual(client.ledger.rf_count-count,1)
        self.assertTrue(contains(policy.polygons[1],(300.,0.)))
        self.assertLessEqual(max(v[0] for v in policy.polygons[1]),750.000001)
        self.assertTrue(any(r.get('reason')=='q4_reused_negative_clip' for r in client.journal.rows))

    def test_actual_positive_cannot_trigger_reused_cut(self):
        heading=math.degrees(math.atan2(-1.,-.05))%360
        client,policy,before,selected=self.fixture(1000.,heading)
        count=client.ledger.rf_count;policy.execute_reused_probe(1,selected,before)
        self.assertEqual(client.ledger.rf_count-count,1)
        self.assertTrue(contains(policy.polygons[1],(1000.,0.)))
        self.assertFalse(any(r.get('reason')=='q4_reused_negative_clip' for r in client.journal.rows))
        client.action('/clear',(1000.,0.),1)
        with self.assertRaises(ProtocolError):policy.execute_reused_probe(1,selected,before)


if __name__=='__main__':unittest.main()
