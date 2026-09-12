"""Independent M regressions; run with the reviewed root's code on PYTHONPATH.

This file lives with review evidence because the reviewer's separate worktree
does not integrate M. The parent's main suite may copy it into tests/.
"""
import math,unittest
from unittest.mock import patch
from geometry import outer_disk,clip_bearing,contains
from directional_geometry import paired_probe
from lookahead import pair_cost,predicted_feedback
import adaptive_single as adaptive


class AdaptiveRecoveryThresholdTests(unittest.TestCase):
    def setUp(self):
        self.poly=clip_bearing(outer_disk(),(0.,0.),0.)
        self.probe=paired_probe(self.poly,(0.,0.),0.,80.,.5)
        self.ends=[self.probe['plus'],self.probe['minus']]
        self.model=dict(g=(1000.,-10.),r=1500.,heading=(-1.,0.),error=-1.,weight=1.)
        self.current=(1050.,-10.)
        self.assertEqual(predicted_feedback(self.model,self.current)[0],'no_signal')

    def pair(self,threshold):
        cost,branches=pair_cost(self.poly,self.current,self.probe,self.ends,[self.model],
                                optical_threshold=threshold)
        return dict(probe=self.probe,endpoints=self.ends,estimated_remaining_s=cost),branches

    def test_real_optical_failure_no_signal_must_pay_same_recovery_policy(self):
        pair,branches=self.pair(60.)
        self.assertEqual(branches['optical_failure'],1.)
        corrected=adaptive.one_action_cost(self.poly,self.current,self.current,[self.model],pair,
                                            switch_cost=1,optical_threshold=60.)
        mismatched=adaptive.one_action_cost(self.poly,self.current,self.current,[self.model],pair,
                                             switch_cost=1,optical_threshold=0.)
        # Reproduces the old misleading advantage, then protects the corrected
        # same-policy comparison. No simulator or hidden scenario is involved.
        self.assertLess(mismatched['estimated_remaining_s'],pair['estimated_remaining_s']-40)
        self.assertAlmostEqual(corrected['estimated_remaining_s'],pair['estimated_remaining_s']+6.,places=9)
        self.assertAlmostEqual(corrected['weighted_pair_recovery_cost_s']['no_signal'],
                               pair['estimated_remaining_s'],places=9)
        self.assertEqual(corrected['branches']['no_signal'],1.)

    def test_selector_passes_optical_threshold_and_rejects_uninformative_point(self):
        pair,_=self.pair(60.)
        with (patch('adaptive_single.hypotheses',return_value=[self.model]),
              patch('adaptive_single.candidate_points',return_value=[(self.current,'current')])):
            selected=adaptive.choose_adaptive_single(self.poly,self.current,[((0.,0.),0.)],[],[],
                {'lookahead_optical':60.,'adaptive_single_gain_s':1.},pair,switch_cost=1)
        self.assertIsNone(selected)

    def test_default_zero_threshold_still_pays_exact_extra_radio(self):
        pair,_=self.pair(0.)
        result=adaptive.one_action_cost(self.poly,self.current,self.current,[self.model],pair)
        self.assertAlmostEqual(result['estimated_remaining_s'],pair['estimated_remaining_s']+5.,places=9)

    def test_direction_clipping_preserves_true_compatible_model_at_radius_boundary(self):
        captured=[]
        fast,full=adaptive.predicted_region,adaptive.clip_bearing
        def wrap(fn,name):
            def invoke(*args):
                region=fn(*args);captured.append((name,region));return region
            return invoke
        model=dict(self.model,heading=None,error=0.)
        pair,_=self.pair(0.)
        with (patch('adaptive_single.predicted_region',side_effect=wrap(fast,'bearing')),
              patch('adaptive_single.clip_bearing',side_effect=wrap(full,'disk'))):
            for q in ((750.,300.),(2500.,-10.)):
                self.assertEqual(predicted_feedback(model,q)[0],'direction')
                adaptive.one_action_cost(self.poly,self.current,q,[model],pair)
        self.assertEqual({name for name,_ in captured},{'bearing','disk'})
        for _,region in captured:self.assertTrue(contains(region,model['g']))


if __name__=='__main__':unittest.main()
