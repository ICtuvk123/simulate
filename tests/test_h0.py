import json,math,random,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from directional_geometry import *
from geometry import outer_disk,clip_bearing,contains
from q4engine import Session,Source
from q3client import Client,ProtocolError,canonical,Ledger
from coverage import validate_completion


class Journal:
    def __init__(self):self.rows=[]
    def append(self,r):self.rows.append(r)


def client_for(session):
    def transport(path,body,timeout):
        status,reply=session.handle(path,body);return status,canonical(reply)
    return Client('local-robot',Journal(),transport=transport)


class GeometryTests(unittest.TestCase):
    def test_h0_continuous_coverage(self):
        self.assertTrue(DirectionalCoverage().prove(skeleton())['complete'])
    def test_22_candidate_reverified(self):
        self.assertTrue(DirectionalCoverage().prove(skeleton(7,14,995,1860))['complete'])
    def test_omni_skeleton_is_not_directional(self):
        p=[(0,0)]+[(1130*math.cos(k*math.pi/3),1130*math.sin(k*math.pi/3)) for k in range(6)]
        self.assertFalse(DirectionalCoverage().prove(p)['complete'])
    def test_global_hull_cannot_replace_local_hull(self):
        p=[(2000*math.cos(k*math.pi/16),2000*math.sin(k*math.pi/16)) for k in range(32)]
        self.assertTrue(in_hull(hull(p),(0,0)))
        self.assertFalse(DirectionalCoverage().prove(p)['complete'])
    def test_budget_or_depth_returns_unproved(self):
        self.assertFalse(DirectionalCoverage(max_depth=0).prove(skeleton())['complete'])
        self.assertFalse(DirectionalCoverage(max_cells=0).prove(skeleton())['complete'])
    def test_incremental_reuse(self):
        c=DirectionalCoverage();p=skeleton()
        for n in (4,8,16):self.assertFalse(c.prove(p[:n])['complete'])
        self.assertTrue(c.prove(p)['complete']);c.prove(p);self.assertEqual(c.hits,1)
    def test_pair_witness_requires_two_actual_negatives(self):
        poly=clip_bearing(outer_disk(),(0,0),0)
        w=paired_probe(poly,(0,0),0)
        self.assertTrue(w['geometry_valid'])
        for results in (['no_signal'],['direction','no_signal'],['near','no_signal']):
            with self.assertRaises(ValueError):apply_paired_negative(poly,dict(w,results=results))
    def test_pair_cut_contains_all_consistent_sampled_sources(self):
        poly=clip_bearing(outer_disk(),(0,0),0);w=paired_probe(poly,(0,0),0)
        updated=apply_paired_negative(poly,dict(w,results=['no_signal','no_signal']))
        count=0
        for x in range(25,1501,25):
            for error in (-1.,0.,1.):
                g=(x*math.cos(math.radians(error)),x*math.sin(math.radians(error)))
                for angle in range(0,360,5):
                    u=(math.cos(math.radians(angle)),math.sin(math.radians(angle)))
                    emit=lambda q:sum((q[k]-g[k])*u[k] for k in (0,1))>=-1e-10
                    if emit((0,0)) and not emit(w['plus']) and not emit(w['minus']):
                        self.assertTrue(contains(updated,g,1e-4));count+=1
        self.assertGreater(count,0)
    def test_positive_hull_safe_but_outside_not_proved(self):
        p=[(0,0),(100,0),(0,100)]
        self.assertTrue(positive_hull_reception((25,25),p))
        self.assertFalse(positive_hull_reception((101,0),p))
    def test_optical_strip_cover(self):
        points=optical_strip((0,0),0);self.assertEqual(len(points),183)
        for x in range(0,1501,7):
            for y in (-1500*math.sin(ALPHA),-12.5,0,12.5,1500*math.sin(ALPHA)):
                self.assertLess(min(math.dist((x,y),p) for p in points),20)
    def test_old_q3_exit_rejected(self):
        self.assertFalse(validate_completion([{'path':'/exit'}],{'kind':'analytic_center_ring'})[0])


class ProtocolTests(unittest.TestCase):
    def test_directional_boundary_and_back(self):
        c=client_for(Session(sources=[Source(1,0,0,1000,0)]));c.action('/enter')
        self.assertEqual(c.action('/measure',(0,100),1)['measure_result'],'direction')
        self.assertEqual(c.action('/measure',(-1e-6,100),1)['measure_result'],'no_signal')
        self.assertEqual(c.action('/measure',(0,-100),1)['measure_result'],'direction')
    def test_near_requires_emitting_side_but_clear_does_not(self):
        c=client_for(Session(sources=[Source(1,0,0,1000,0)]));c.action('/enter')
        self.assertEqual(c.action('/measure',(-1,0),1)['measure_result'],'no_signal')
        self.assertEqual(c.action('/measure',(1,0),1)['measure_result'],'near')
        self.assertEqual(c.action('/clear',(-1,0),1)['clear_result'],'success')
    def test_documented_199_seconds_and_clear_keeps_channel(self):
        c=client_for(Session(sources=[Source(1,1500,0,1000,None)]));c.action('/enter')
        c.action('/measure',(300,400),1);c.action('/measure',(300,400),2)
        c.action('/clear',(300,0),3);self.assertEqual(c.ledger.channel,2)
        c.action('/measure',(300,0),2);self.assertEqual(c.ledger.virtual_time,199)
    def test_retry_same_id_no_duplicate_cost(self):
        s=Session(sources=[]);sent=[]
        def transport(path,body,timeout):
            sent.append(body);status,r=s.handle(path,body)
            if len(sent)==1:raise TimeoutError('response lost after execution')
            return status,canonical(r)
        c=Client('local-robot',Journal(),transport=transport);c.action('/enter')
        self.assertEqual(sent[0],sent[1]);self.assertEqual(len(s.events),1)
    def test_fixed_spatial_error(self):
        c=client_for(Session(seed=27,sources=[Source(1,500,0,1500,None)]));c.action('/enter')
        a=c.action('/measure',(0,0),1);b=c.action('/measure',(0,0),1)
        self.assertEqual(a['svd_deg'],b['svd_deg']);self.assertEqual(c.ledger.rf_count,2)
    def test_accepted_false_cannot_move_or_reset(self):
        s=Session(sources=[]);c=client_for(s);c.action('/enter');c.action('/measure',(300,400),1)
        p=dict(arena_id='default',robot_id='local-robot',request_id='new',position={'x':900,'y':900},channel=2)
        self.assertFalse(c.ledger.apply('/measure',p,200,{'accepted':False,'virtual_time_s':0,'real_timestamp_ms':0}))
        self.assertEqual(c.ledger.position,(300,400));self.assertEqual(c.ledger.virtual_time,105)
    def test_wrong_http_status_not_a_negative(self):
        l=Ledger();p=dict(arena_id='default',robot_id='local-robot',request_id='test')
        with self.assertRaises(ProtocolError):l.apply('/enter',p,500,dict(accepted=True,virtual_time_s=0,real_timestamp_ms=0))
        self.assertFalse(l.entered)
    def test_actual_remaining_budget(self):
        now=[0.];s=Session(sources=[],monotonic=lambda:now[0]);now[0]=1400
        c=client_for(s);r=c.action('/enter');self.assertEqual(r['remaining_real_duration_s'],100)
        self.assertLessEqual(c._budget(),100)


if __name__=='__main__':unittest.main()
