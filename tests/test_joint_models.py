import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from joint_models import *
from lookahead import receives


class JointModelsTests(unittest.TestCase):
    def test_single_positive_changes_type_mass(self):
        models=build_joint_models([(500.,0.)],[((0.,0.),0.)],[])
        self.assertAlmostEqual(sum(m['weight'] for m in models if m['heading'] is None),2/3)
        self.assertAlmostEqual(sum(m['weight'] for m in models),1.)

    def test_radius_likelihood_retained_across_positions(self):
        models=build_joint_models([(500.,0.),(1250.,0.)],[((0.,0.),0.)],[])
        self.assertAlmostEqual(sum(m['weight'] for m in models if m['g'][0]==500),2/3)
        self.assertAlmostEqual(sum(m['weight'] for m in models if m['g'][0]==1250),1/3)

    def test_all_models_match_actual_history(self):
        g=(500.,0.);positives=[((0.,0.),0.),((300.,20.),0.)];negatives=[(850.,100.),(1600.,0.)]
        models=build_joint_models([g],positives,negatives)
        self.assertTrue(models)
        self.assertFalse(any(m['heading'] is None for m in models))
        for m in models:
            self.assertTrue(all(receives(g,m['r'],m['heading'],p) for p,_ in positives))
            self.assertTrue(all(not receives(g,m['r'],m['heading'],n) for n in negatives))

    def test_failed_optical_disk_filters_only_models(self):
        models=build_joint_models([(500.,0.),(700.,0.)],[((0.,0.),0.)],[],
                                  [dict(point=(500.,0.),radius=19.99999)])
        self.assertTrue(models)
        self.assertTrue(all(m['g']==(700.,0.) for m in models))

    def test_radius_partition_retains_omni_below_negative_distance(self):
        models=build_joint_models([(500.,0.)],[((0.,0.),0.)],[(1700.,0.)])
        self.assertTrue(any(m['heading'] is None for m in models))
        for m in models:
            if m['heading'] is None:self.assertLess(m['r'],1200.)


if __name__=='__main__':unittest.main()
