import copy,json,math,random,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from directional_geometry import ALPHA,MARGIN,paired_probe,verify_paired_geometry,apply_paired_negative
from geometry import outer_disk,clip_bearing,contains
from lookahead import choose_pair,receives
from audit import audit_pair_witness


class NarrowProbeTests(unittest.TestCase):
    def setUp(self):
        self.poly=clip_bearing(outer_disk(),(0.,0.),0.)

    def witness(self,fraction=.9,b=25.):
        return paired_probe(self.poly,(0.,0.),0.,b,fraction,narrow_probe=True)

    def test_expands_legal_candidates_beyond_full_region_1000_bound(self):
        old=paired_probe(self.poly,(0.,0.),0.,25.,.9)
        new=self.witness()
        self.assertFalse(old['geometry_valid'])
        self.assertTrue(new['geometry_valid'])
        self.assertEqual(new['radius_witness'],'positive_station_radius')
        self.assertGreater(max(math.dist(q,v) for q in [new['plus'],new['minus']] for v in self.poly),1000)
        self.assertTrue(verify_paired_geometry(self.poly,new))

    def test_baseline_remains_available_when_disabled(self):
        p=paired_probe(self.poly,(0.,0.),0.)
        self.assertTrue(p['geometry_valid'])
        self.assertEqual(p['radius_witness'],'minimum_radius_all_region')

    def test_margins_reject_angular_and_radius_boundary(self):
        w=self.witness(.5,30.)
        lower=w['t']*math.tan(ALPHA)
        angular=paired_probe(self.poly,(0.,0.),0.,lower,.5,narrow_probe=True)
        self.assertFalse(angular['geometry_valid'])
        self.assertFalse(verify_paired_geometry(self.poly,angular))
        # Equality is mathematically safe, but the implementation requires margin.
        upper=w['t']*(math.sqrt(1+math.tan(ALPHA)**2)-math.tan(ALPHA))
        radius=paired_probe(self.poly,(0.,0.),0.,upper,.5,narrow_probe=True)
        self.assertFalse(radius['geometry_valid'])
        self.assertFalse(verify_paired_geometry(self.poly,radius))

    def test_single_or_positive_feedback_never_justifies_cut(self):
        w=self.witness()
        for results in [[],['no_signal'],['no_signal','direction'],['near','no_signal']]:
            with self.assertRaises(ValueError):
                apply_paired_negative(self.poly,dict(w,results=results))

    def test_forged_valid_marker_and_basis_are_rejected(self):
        w=dict(self.witness(),results=['no_signal','no_signal'])
        for patch in [dict(b=2000.),dict(t=-1.),dict(d=(0.,1.)),dict(plus=(0.,0.)),
                      dict(radius_witness='future_station'),dict(b=float('nan'))]:
            with self.assertRaises(ValueError):
                apply_paired_negative(self.poly,dict(w,geometry_valid=True,**patch))

    def test_independent_audit_requires_actual_positive_and_both_negatives(self):
        w=dict(self.witness(),channel=1,before_polygon=self.poly,results=['no_signal','no_signal'])
        pos={1:[((0.,0.),0.)]};neg={1:[w['plus'],w['minus']]}
        self.assertTrue(audit_pair_witness(w,pos,neg))
        self.assertFalse(audit_pair_witness(w,{},neg))
        self.assertFalse(audit_pair_witness(w,pos,{1:[w['plus']]}))
        # An attacker cannot replace the bound with a convenient saved flag/gap.
        forged=dict(w,b=2000.,geometry_valid=True,positive_radius_gap_sq_m2=1e10)
        self.assertFalse(audit_pair_witness(forged,pos,neg))

    def test_without_spanning_condition_both_backside_counterexample(self):
        t=750.;b=5.;g=(800.,800.*math.tan(math.radians(1.)))
        norm=math.hypot(*g);heading=(-g[1]/norm,g[0]/norm)
        self.assertTrue(receives(g,1000.,heading,(0.,0.))) # Inclusive edge.
        self.assertFalse(receives(g,1000.,heading,(t,b)))
        self.assertFalse(receives(g,1000.,heading,(t,-b)))
        self.assertGreater(g[0],t)

    def test_without_radius_condition_both_distance_counterexample(self):
        t=500.;b=1100.;g=(501.,0.)
        self.assertTrue(receives(g,1000.,None,(0.,0.)))
        self.assertFalse(receives(g,1000.,None,(t,b)))
        self.assertFalse(receives(g,1000.,None,(t,-b)))

    def test_random_far_sources_cannot_produce_two_negatives(self):
        rng=random.Random(18291);checks=0
        for fraction in (.05,.35,.5,.75,.95):
            trial=self.witness(fraction,30.);t=trial['t']
            for scale in (1.00001,1.5,3.):
                b=math.ceil(t*math.tan(ALPHA)*scale+MARGIN)
                w=self.witness(fraction,b)
                self.assertTrue(w['geometry_valid'])
                for i in range(150):
                    # Actual allowed bearing error is 1 degree, not the 1.01 margin.
                    error=(-1.,0.,1.)[i%3] if i<9 else rng.uniform(-1.,1.)
                    e=math.radians(error)
                    x=t+(1500*math.cos(e)-t)*rng.random()
                    g=(x,x*math.tan(e));distance=math.hypot(*g)
                    radius=max(1000.,distance) if i%2 else 1500.
                    for q in (w['plus'],w['minus']):
                        self.assertLessEqual(math.dist(g,q),distance+1e-8)
                    central=math.atan2(-g[1],-g[0])
                    for offset in (-math.pi/2,math.pi/2,rng.uniform(-math.pi/2,math.pi/2)):
                        heading=(math.cos(central+offset),math.sin(central+offset))
                        self.assertTrue(receives(g,radius,heading,(0.,0.)))
                        self.assertTrue(any(receives(g,radius,heading,q) for q in (w['plus'],w['minus'])))
                        checks+=1
        self.assertEqual(checks,6750)

    def test_near_side_dual_negative_cut_preserves_source(self):
        w=self.witness(.9,25.);g=(300.,0.);heading=(-1.,0.)
        self.assertTrue(receives(g,1000.,heading,(0.,0.)))
        self.assertTrue(all(not receives(g,1000.,heading,q) for q in (w['plus'],w['minus'])))
        cut=apply_paired_negative(self.poly,dict(w,results=['no_signal','no_signal']))
        self.assertTrue(contains(cut,g))

    def test_rotated_translated_witness_and_deterministic_rank(self):
        s=(-1350.,123.);beta=359.999
        poly=clip_bearing(outer_disk(),s,beta)
        w=paired_probe(poly,s,beta,25.,.9,narrow_probe=True)
        self.assertTrue(w['geometry_valid']);self.assertTrue(verify_paired_geometry(poly,w))
        options=dict(narrow_probe=True,lookahead_positions=3)
        args=(poly,s,[(s,beta)],[],[],options)
        a=choose_pair(*args);b=choose_pair(*args)
        self.assertEqual(a,b);self.assertIsNotNone(a)
        self.assertTrue(verify_paired_geometry(poly,a['probe']))
        self.assertGreater(a['candidate_count'],9)


if __name__=='__main__':unittest.main()
