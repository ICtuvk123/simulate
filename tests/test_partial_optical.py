import json,math,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from partial_optical import choose_partial,outside_exclusions,candidates,EXCLUSION_RADIUS,continuation_cost
from lookahead import hypotheses,single_probe_cost
from directional_geometry import paired_probe
from q4controller import Q4Controller
from q4engine import Session,Source
from q3client import Client,canonical,ProtocolError
from audit import postcheck
from test_shared_stops import Journal

ROOT=Path(__file__).resolve().parents[1]


class PartialOpticalTests(unittest.TestCase):
    def controller(self):
        options=json.loads((ROOT/'configs/R2_B_partial.json').read_text())
        session=Session(sources=[Source(2,500,0,1500)])
        def transport(path,body,timeout):
            status,r=session.handle(path,body);return status,canonical(r)
        journal=Journal();journal.append(dict(event='metadata',policy_options=options))
        client=Client('local-robot',journal,transport=transport)
        controller=Q4Controller(client,options);client.action('/enter')
        controller.measure((0,0),2,'unit')
        return controller,journal

    def test_hit_and_miss_costs_are_both_counted(self):
        models=[dict(g=(0,0),weight=.1),dict(g=(100,0),weight=.9)]
        selected=dict(probe={},endpoints=[(200,0),(200,10)])
        options=dict(partial_optical_candidates=2,partial_optical_gain_s=0.)
        with patch('partial_optical.continuation_cost',return_value=(50.,'paired_rf')):
            plan=choose_partial([(0,-5),(200,-5),(200,5),(0,5)],(0,0),selected,models,[],options)
        self.assertEqual(plan['point'],(0,0))
        self.assertAlmostEqual(plan['estimated_remaining_s'],48.2)
        self.assertAlmostEqual(plan['predicted_miss_remaining_s'],50.)
        self.assertFalse(plan['full_coverage_claimed'])

    def test_low_value_trial_keeps_baseline(self):
        models=[dict(g=(0,0),weight=.01),dict(g=(100,0),weight=.99)]
        with patch('partial_optical.continuation_cost',return_value=(50.,'paired_rf')):
            plan=choose_partial([(0,0)],(0,0),dict(probe={},endpoints=[(200,0)]),models,[],
                                dict(partial_optical_candidates=2,partial_optical_min_mass=0.,partial_optical_gain_s=0.))
        self.assertIsNone(plan)

    def test_failed_optical_keeps_polygon_and_channel_and_records_actual_request(self):
        c,journal=self.controller();before=list(c.polygons[2]);channel=c.client.ledger.channel
        self.assertFalse(c.clear((100,0),2,'partial_optical'))
        self.assertEqual(c.polygons[2],before);self.assertEqual(c.client.ledger.channel,channel)
        ex=c.optical_exclusions[2][0]
        self.assertEqual(ex['request_id'],c.client.ledger.events[-1]['request_id'])
        self.assertTrue(outside_exclusions((500,0),[ex]))
        self.assertFalse(outside_exclusions((100,0),[ex]))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.jsonl';path.write_text('\n'.join(json.dumps(r) for r in journal.rows),encoding='utf-8')
            result=postcheck(path,dict(sources=[dict(channel=2,x=500,y=0)]))
        self.assertTrue(result['valid'],result);self.assertEqual(result['optical_exclusions'],1)

    def test_rejected_action_cannot_create_exclusion(self):
        c,_=self.controller()
        with patch.object(c.client,'action',side_effect=ProtocolError('not accepted')):
            with self.assertRaises(ProtocolError):c.clear((100,0),2,'partial_optical')
        self.assertEqual(c.optical_exclusions,{})

    def test_exclusion_boundary_is_conservative(self):
        ex=[dict(point=(0,0),radius=EXCLUSION_RADIUS)]
        self.assertTrue(outside_exclusions((20,0),ex))
        self.assertTrue(outside_exclusions((EXCLUSION_RADIUS,0),ex))
        self.assertFalse(outside_exclusions((19.9,0),ex))
        models=hypotheses([(0,-5),(60,-5),(60,5),(0,5)],[((-100,0),0)],[],25,ex)
        self.assertTrue(models)
        self.assertTrue(all(outside_exclusions(m['g'],ex) for m in models))

    def test_trial_guards_require_new_positive_information_and_remain_finite(self):
        c,_=self.controller();self.assertTrue(c.partial_allowed(2))
        c.partial_versions[(2,len(c.positives[2]))]=1
        self.assertFalse(c.partial_allowed(2))
        c.measure((50,10),2,'unit');self.assertTrue(c.partial_allowed(2))
        c.partial_counts[2]=4;self.assertFalse(c.partial_allowed(2))

    def test_fixed_along_path_candidates_never_repeat_failed_point(self):
        models=[dict(g=(0,0)),dict(g=(40,0)),dict(g=(80,0))]
        points=candidates((0,0),(80,0),models,[dict(point=(40,0),radius=EXCLUSION_RADIUS)],3)
        self.assertNotIn((40,0),points)
        self.assertTrue(all(abs(p[1])<1e-10 and 0<=p[0]<=80 for p in points))

    def test_forged_failure_exclusion_is_rejected_by_post_run_audit(self):
        c,journal=self.controller()
        journal.append(dict(event='policy',reason='q4_actual_optical_exclusion',channel=2,
                            point=(500,0),radius=EXCLUSION_RADIUS,request_id='fiction',
                            convex_outer_region_unchanged=True))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.jsonl';path.write_text('\n'.join(json.dumps(r) for r in journal.rows),encoding='utf-8')
            result=postcheck(path,dict(sources=[dict(channel=2,x=500,y=0)]))
        self.assertFalse(result['valid']);self.assertIn('invalid_optical_exclusion',result['errors'])

    def test_after_first_continuation_is_one_rf_not_repeated_pair(self):
        poly=[(480,-5),(520,-5),(520,5),(480,5)]
        probe=paired_probe(poly,(0,0),0,40.,.5)
        models=[dict(g=(510,0),r=1000,heading=None,weight=1.,error=0.)]
        expected,_=single_probe_cost(poly,probe['plus'],probe['minus'],models,first_result='direction',probe=probe)
        cost,kind=continuation_cost(poly,probe['plus'],probe,[probe['minus']],models,None,0,compact_points=0,first_result='direction')
        self.assertEqual(kind,'paired_rf');self.assertAlmostEqual(cost,expected)

    def test_unsampled_crescent_retains_nonzero_miss_cost(self):
        models=[dict(g=(0,0),weight=1.)]
        options=dict(partial_optical_candidates=2,partial_optical_gain_s=0.,partial_optical_miss_reserve=.05)
        with patch('partial_optical.continuation_cost',return_value=(50.,'paired_rf')):
            plan=choose_partial([(-30,-5),(30,-5),(30,5),(-30,5)],(0,0),
                                dict(probe={},endpoints=[(100,0)]),models,[],options)
        self.assertAlmostEqual(plan['predicted_hit_mass'],.95)
        self.assertGreater(plan['predicted_miss_remaining_s'],0)

    def test_optional_local_candidates_obey_actual_detour_budget(self):
        poly=[(20,20),(60,20),(60,30),(20,30)]
        models=[dict(g=(40,25)),dict(g=(20,20))]
        points=candidates((0,0),(80,0),models,[],5,poly,30.)
        self.assertTrue(any(q[1]>0 for q in points))
        self.assertTrue(all(math.dist((0,0),q)+math.dist(q,(80,0))-80<=30+1e-6 for q in points))


if __name__=='__main__':unittest.main()
