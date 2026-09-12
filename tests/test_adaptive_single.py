import json,math,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from adaptive_single import candidate_points,one_action_cost,choose_adaptive_single
from directional_geometry import paired_probe
from geometry import outer_disk,clip_bearing
from lookahead import pair_cost
from q4engine import Session,Source
from q3client import Client,canonical
from q4controller import Q4Controller


class AdaptiveSingleTests(unittest.TestCase):
    def setUp(self):
        self.poly=clip_bearing(outer_disk(),(0.,0.),0.)
        self.current=(0.,0.);self.positives=[((0.,0.),0.)]
        self.probe=paired_probe(self.poly,(0.,0.),0.,80.,.5)
        self.models=[dict(g=(300.,0.),r=1000.,heading=(-1.,0.),weight=1.,error=0.)]
        ends=[self.probe['plus'],self.probe['minus']]
        cost,_=pair_cost(self.poly,self.current,self.probe,ends,self.models)
        self.pair=dict(probe=self.probe,endpoints=ends,estimated_remaining_s=cost)

    def test_candidate_generation_does_not_repeat_or_consume_recovery_endpoints(self):
        measured=[(0.,0.),(750.,15.)]
        points=candidate_points(self.poly,self.current,measured,self.pair['endpoints'])
        self.assertGreater(len(points),20)
        for i,(q,kind) in enumerate(points):
            self.assertTrue(all(math.dist(q,p)>=.05 for p in measured+self.pair['endpoints']))
            self.assertTrue(all(math.dist(q,p)>=.05 for p,_ in points[:i]))
        kinds={kind for _,kind in points}
        self.assertIn('G_center_lateral',kinds);self.assertIn('G_approach',kinds);self.assertIn('G_travel_lateral',kinds)

    def test_current_site_allowed_only_for_unmeasured_channel(self):
        current=(100.,200.)
        self.assertIn((current,'current'),candidate_points(self.poly,current,[],self.pair['endpoints']))
        self.assertNotIn((current,'current'),candidate_points(self.poly,current,[current],self.pair['endpoints']))

    def test_all_no_signal_models_pay_complete_pair_and_never_win(self):
        with (patch('adaptive_single.predicted_feedback',return_value=('no_signal',None)),
              patch('lookahead.predicted_feedback',return_value=('no_signal',None)),
              patch('adaptive_single.hypotheses',return_value=self.models)):
            baseline,_=pair_cost(self.poly,self.current,self.probe,self.pair['endpoints'],self.models)
            pair=dict(self.pair,estimated_remaining_s=baseline)
            for q,_ in candidate_points(self.poly,self.current,[],pair['endpoints']):
                cost=one_action_cost(self.poly,self.current,q,self.models,pair,switch_cost=1)
                self.assertGreaterEqual(cost['estimated_remaining_s'],baseline+1+5-1e-7)
                self.assertEqual(cost['recovery_mass'],1.)
                full,_=pair_cost(self.poly,q,self.probe,pair['endpoints'],self.models)
                self.assertAlmostEqual(cost['weighted_pair_recovery_cost_s']['no_signal'],full)
            self.assertIsNone(choose_adaptive_single(self.poly,self.current,self.positives,[],[],{},pair,switch_cost=1))

    def test_complete_cost_counts_initial_switch_and_near_optical(self):
        q=(100.,0.)
        with patch('adaptive_single.predicted_feedback',return_value=('near',None)):
            cost=one_action_cost(self.poly,self.current,q,self.models,self.pair,switch_cost=1)
        self.assertAlmostEqual(cost['estimated_remaining_s'],100/5+5+1+3+2)
        self.assertEqual(cost['recovery_mass'],0.)

    def test_informative_single_can_win_without_modifying_pair(self):
        # A real geometric near branch beats the full pair; an unavailable
        # fallback pair must still reject the proposal.
        with (patch('adaptive_single.hypotheses',return_value=self.models),
              patch('adaptive_single.candidate_points',return_value=[((300.,0.),'unit')])):
            r=choose_adaptive_single(self.poly,self.current,self.positives,[],[],{},self.pair)
            self.assertIsNotNone(r);self.assertEqual(r['branches']['near'],1.)
            self.assertEqual(r['recovery_endpoints'],self.pair['endpoints'])
            self.assertIsNone(choose_adaptive_single(self.poly,self.current,self.positives,[],self.pair['endpoints'][:1],{},self.pair))

    def test_no_signal_does_not_delete_and_single_action_returns_to_replanning(self):
        class Journal:
            def __init__(self):self.rows=[]
            def append(self,row):self.rows.append(row)
        engine=Session(sources=[Source(1,300.,0.,1000.,180.)]);engine._error=lambda ch,p:0.
        def transport(path,body,timeout):
            status,response=engine.handle(path,body);return status,canonical(response)
        journal=Journal();client=Client('local-robot',journal,transport=transport)
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/R2_M_adaptive_single.json').read_text())
        config['compact_optical']=False
        policy=Q4Controller(client,config);client.action('/enter');policy.measure((0.,0.),1,'unit')
        before=list(policy.polygons[1]);count=client.ledger.rf_count
        choice=dict(point=(900.,0.),estimated_remaining_s=1.)
        with patch('q4controller.choose_adaptive_single',return_value=choice):policy.localize(1)
        self.assertEqual(client.ledger.rf_count,count+1)
        self.assertEqual(policy.polygons[1],before)
        self.assertIn((900.,0.),policy.negatives[1]);self.assertEqual(policy.rounds[1],1)
        self.assertTrue(any(r.get('reason')=='q4_replan_after_adaptive_single' for r in journal.rows))
        self.assertFalse(any(r.get('reason')=='q4_paired_negative_clip' for r in journal.rows))
        points=candidate_points(before,client.ledger.position,[q for ch,q in policy.measured if ch==1],self.pair['endpoints'])
        self.assertFalse(any(math.dist(q,(900.,0.))<.05 for q,_ in points))

    def test_disabled_option_never_calls_new_ranking(self):
        class Journal:
            def append(self,row):pass
        engine=Session(sources=[Source(1,300.,0.,1000.,180.)]);engine._error=lambda ch,p:0.
        def transport(path,body,timeout):
            status,response=engine.handle(path,body);return status,canonical(response)
        client=Client('local-robot',Journal(),transport=transport)
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/D_compact_optical.json').read_text())
        policy=Q4Controller(client,config);client.action('/enter');policy.measure((0.,0.),1,'unit')
        with patch('q4controller.choose_adaptive_single',side_effect=AssertionError('disabled option ran')):policy.localize(1)


if __name__=='__main__':unittest.main()
