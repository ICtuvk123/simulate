import copy,json,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from scan_commit_scheduler import choose_scan_before_commit
from q4controller import Q4Controller
from q4engine import Session,Source
from q3client import Client,canonical
from test_shared_stops import Journal

ROOT=Path(__file__).resolve().parents[1]


class ScanCommitTests(unittest.TestCase):
    def setup_plan(self):
        regions={1:[(50,-1),(150,-1),(150,1),(50,1)],2:[(150,-1),(250,-1),(250,1),(150,1)]}
        return [(0,0),[('source',1),('scan',0),('source',2)],[(100,0),(120,20),(200,0)],
                [0,1,2],regions,set(),lambda ch,p:dict(estimated_gain_s=100 if ch==1 else 20,
                                branches=dict(no_signal=.25,direction=.75,near=0),model_count=7),
                dict(scan_before_commit=True,shared_bearing=True,shared_limit_per_stop=3,shared_gain_s=10)]

    def test_existing_scan_is_promoted_and_whole_open_route_cost_is_charged(self):
        args=self.setup_plan();before=copy.deepcopy(args[:6]);result=choose_scan_before_commit(*args)
        self.assertEqual(result['task_index'],1);self.assertEqual(result['proposed_order'],[1,0,2])
        a=(100+math.hypot(20,20)+math.hypot(80,20))/5
        b=(math.hypot(120,20)+math.hypot(20,20)+100)/5
        self.assertAlmostEqual(result['planned_move_change_s'],b-a)
        self.assertAlmostEqual(result['expected_net_gain_s'],100-(b-a))
        self.assertEqual(before,args[:6]);self.assertEqual(result['predicted_target_branches']['no_signal'],.25)

    def test_disabled_preserves_baseline_and_never_queries_future_information(self):
        args=self.setup_plan();args[-1]['scan_before_commit']=False
        args[-2]=lambda ch,p:self.fail('Disabled scheduler must not score')
        self.assertIsNone(choose_scan_before_commit(*args))

    def test_guaranteed_clear_source_is_not_delayed(self):
        args=self.setup_plan();args[4][1]=[(95,-1),(105,-1),(105,1),(95,1)]
        self.assertIsNone(choose_scan_before_commit(*args))

    def test_target_outside_existing_shared_budget_keeps_source_first(self):
        args=self.setup_plan();args[-1]['shared_limit_per_stop']=1
        args[-2]=lambda ch,p:dict(estimated_gain_s=100 if ch==1 else 200,branches={},model_count=7)
        self.assertIsNone(choose_scan_before_commit(*args))

    def test_measured_point_is_not_counted_as_fresh_information(self):
        args=self.setup_plan();args[5].add((1,(120,20)))
        self.assertIsNone(choose_scan_before_commit(*args))

    def test_excess_route_cost_rejects_scan_promotion(self):
        args=self.setup_plan();args[2][1]=(1000,1000)
        args[-2]=lambda ch,p:dict(estimated_gain_s=20,branches={},model_count=7)
        self.assertIsNone(choose_scan_before_commit(*args))

    def test_forced_scan_and_finite_source_only_tail_are_unchanged(self):
        args=self.setup_plan();args[3]=[1,0,2]
        self.assertIsNone(choose_scan_before_commit(*args))
        args=self.setup_plan();args[1]=[('source',1),('source',2)];args[2]=[(100,0),(200,0)];args[3]=[0,1]
        self.assertIsNone(choose_scan_before_commit(*args))

    def test_forecast_cannot_modify_region_or_create_actual_negative_and_real_miss_stays_conservative(self):
        # A directional source facing west is visible at origin, not at (800,0).
        session=Session(sources=[Source(1,500,0,1500,direction_deg=180.)])
        def transport(path,body,timeout):
            status,response=session.handle(path,body);return status,canonical(response)
        options=json.loads((ROOT/'configs/D_compact_optical.json').read_text());journal=Journal()
        client=Client('local-robot',journal,transport=transport);c=Q4Controller(client,options);client.action('/enter')
        c.measure((0,0),1,'unit');before=list(c.polygons[1]);neg=list(c.negatives[1]);events=len(client.ledger.events)
        args=self.setup_plan();args[4][1]=c.polygons[1];choose_scan_before_commit(*args)
        self.assertEqual(c.polygons[1],before);self.assertEqual(c.negatives[1],neg);self.assertEqual(len(client.ledger.events),events)
        self.assertEqual(c.measure((800,0),1,'unit'),'no_signal')
        self.assertEqual(c.polygons[1],before);self.assertEqual(c.negatives[1],neg+[(800,0)])


if __name__=='__main__':unittest.main()
