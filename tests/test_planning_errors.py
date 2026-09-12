import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from lookahead import planning_error,predicted_feedback,attach_error_fields,finish_error_models
from joint_models import build_joint_models


class PlanningSpatialErrorTests(unittest.TestCase):
    def test_same_position_and_world_independent_of_query_order(self):
        model=dict(g=(500.,0.),r=1500.,heading=None,error=1.,planning_error_field=3)
        points=[(0.,0.),(50.,20.),(100.,-10.)]
        first={p:predicted_feedback(model,p) for p in points}
        second={p:predicted_feedback(model,p) for p in reversed(points)}
        self.assertEqual(first,second)
        self.assertEqual(first[(0.,0.)],predicted_feedback(model,(0.,0.)))
        self.assertGreater(len({planning_error(model,p) for p in points}),1)

    def test_field_bound_and_no_true_scene_key(self):
        models=attach_error_fields([dict(error=0.) for _ in range(7)])
        for i,model in enumerate(models):
            self.assertEqual(set(model),{'error','planning_error_field'})
            self.assertEqual(model['planning_error_field'],i)
            for k in range(21):self.assertLessEqual(abs(planning_error(model,(k*125.13,-k*20.1))),1.)

    def test_default_constant_error_is_unchanged(self):
        for error in (-1.,0.,1.):
            self.assertEqual(planning_error(dict(error=error),(123.,234.)),error)

    def test_balanced_error_integration_preserves_physical_mass(self):
        original=build_joint_models([(500.,0.)],[((0.,0.),0.)],[])
        result=finish_error_models(original,balanced_errors=True)
        self.assertEqual(len(result),3*len(original))
        self.assertAlmostEqual(sum(m['weight'] for m in result),1.)
        self.assertAlmostEqual(sum(m['weight']*m['error'] for m in result),0.)
        self.assertAlmostEqual(sum(m['weight'] for m in result if m['heading'] is None),2/3)
        for error in (-1.,0.,1.):
            self.assertAlmostEqual(sum(m['weight'] for m in result if m['error']==error),1/3)

    def test_conflicting_error_experiments_rejected(self):
        with self.assertRaises(ValueError):finish_error_models([],True,True)


if __name__=='__main__':unittest.main()
