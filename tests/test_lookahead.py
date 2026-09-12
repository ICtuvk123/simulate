import json,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from geometry import outer_disk,clip_bearing,contains
from directional_geometry import paired_probe
from lookahead import hypotheses,predicted_feedback,pair_cost,choose_pair,receives,shared_information_value


class LookaheadTests(unittest.TestCase):
    def test_hypotheses_keep_omni_and_obey_actual_history(self):
        poly=clip_bearing(outer_disk(),(0,0),0)
        models=hypotheses(poly,[((0,0),0)],[(1700,0)])
        self.assertTrue(models)
        self.assertTrue(any(m['heading'] is None for m in models))
        self.assertTrue(any(m['heading'] is not None for m in models))
        self.assertAlmostEqual(sum(m['weight'] for m in models),1.)
        for m in models:
            self.assertTrue(contains(poly,m['g']))
            self.assertTrue(receives(m['g'],m['r'],m['heading'],(0,0)))
            self.assertFalse(receives(m['g'],m['r'],m['heading'],(1700,0)))
    def test_backside_branch_is_in_score_without_changing_polygon(self):
        poly=clip_bearing(outer_disk(),(0,0),0);before=list(poly)
        probe=paired_probe(poly,(0,0),0)
        model=dict(g=(300,0),r=1000,heading=(-1,0),weight=1.,error=0)
        score,branches=pair_cost(poly,(0,0),probe,[probe['plus'],probe['minus']],[model])
        self.assertEqual(branches['no_signal'],2)
        self.assertGreater(score,0);self.assertEqual(poly,before)
    def test_optical_failure_cost_and_branch_are_explicit(self):
        poly=clip_bearing(outer_disk(),(0,0),0)
        g=(60*math.cos(math.radians(1)),60*math.sin(math.radians(1)))
        model=dict(g=g,r=1500.,heading=None,weight=1.,error=-1.)
        probe=paired_probe(poly,(0,0),0,b=30)
        ends=[probe['plus'],probe['minus']]
        score,branches=pair_cost(poly,(0,0),probe,ends,[model],optical_threshold=40.)
        baseline,_=pair_cost(poly,(0,0),probe,ends,[model],optical_threshold=0.)
        self.assertEqual(branches['optical_failure'],1)
        self.assertEqual(branches['optical_success'],0)
        self.assertEqual(branches['direction'],2) # Continue after the failed clear.
        self.assertGreaterEqual(score-baseline,3.-1e-8)
    def test_rank_is_deterministic_and_geometry_checked(self):
        poly=clip_bearing(outer_disk(),(0,0),0);before=list(poly)
        args=(poly,(0,0),[((0,0),0)],[],[],dict(lookahead_positions=5))
        a=choose_pair(*args);b=choose_pair(*args)
        self.assertEqual(a,b);self.assertTrue(a['probe']['geometry_valid'])
        self.assertEqual(poly,before)
        self.assertTrue(a['assumptions_only_for_ranking'])
    def test_shared_scan_far_away_has_cost_and_no_information_gain(self):
        poly=clip_bearing(outer_disk(),(0,0),0);before=list(poly)
        value=shared_information_value(poly,(-2000,0),[((0,0),0)],[])
        self.assertAlmostEqual(value['branches']['no_signal'],1.)
        self.assertAlmostEqual(value['estimated_gain_s'],-6.)
        self.assertEqual(poly,before)


if __name__=='__main__':unittest.main()
