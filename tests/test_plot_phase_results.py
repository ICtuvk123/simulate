import csv,importlib.util,json,statistics,tempfile,unittest
from pathlib import Path

FILE=Path(__file__).resolve().parents[1]/'reports/plot_phase_results.py'
spec=importlib.util.spec_from_file_location('plot_phase_results',FILE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


class PlotDataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.reg=dict(phase='unit',role='development',seeds=[1,2,3],variants={'a':'a.json','b':'b.json'},
                      tasks=[dict(seed=s,variant=v) for s in [1,2,3] for v in ('a','b')])
        self.rows=[];self.summary={}
        for v,values in [('a',[100.,110.,120.]),('b',[90.,115.,119.])]:
            for seed,total in zip([1,2,3],values):self.rows.append(dict(seed=seed,variant=v,total_time=total,mean_time_per_source=total/10,policy_wall_time_s=1.,all_success='True'))
            mean=statistics.mean(values)
            self.summary[v]=dict(n=3,complete=3,all_success=True,mean_total=mean,mean_per_source=mean/10,
                p95=mod.quantile(values,.95),worst=max(values),mean_wall=1.,mean_move_time=mean-10.,
                mean_RF_detection_time=5.,mean_channel_switch_time=1.,mean_optical_time=3.,mean_clear_time=1.)
        self.comp=dict(baseline='a',candidate='b',pairs=3,all_registered_pairs_present=True,
                       identical_worlds_verified=3,all_success=True,mean_per_source_baseline=11.,
                       mean_per_source_candidate=10.8,p95_baseline=119.,p95_candidate=118.6,
                       improvement_percent=100*(1-10.8/11.))
        self.write()
    def tearDown(self):self.temp.cleanup()
    def write(self):
        for name,value in [('registration.json',self.reg),('summary.json',self.summary),('comparison_a_b.json',self.comp)]:
            (self.path/name).write_text(json.dumps(value))
        with (self.path/'paired_results.csv').open('w',newline='') as file:
            writer=csv.DictWriter(file,list(self.rows[0]));writer.writeheader();writer.writerows(self.rows)
    def test_registered_all_pairs_and_regressions_retained(self):
        d=mod.load_phase(self.path);self.assertEqual(d['comparisons'][0]['differences'],[-10.,5.,-1.]);self.assertEqual(d['seeds'],[1,2,3])
    def test_failed_scene_kept_when_reports_agree(self):
        self.rows[-1]['all_success']='False';self.summary['b'].update(complete=2,all_success=False);self.comp['all_success']=False;self.write()
        d=mod.load_phase(self.path);self.assertEqual(len(d['comparisons'][0]['differences']),3);self.assertFalse(d['data']['b'][3]['all_success'])
    def test_missing_scene_cannot_be_dropped(self):
        self.rows.pop();self.write()
        with self.assertRaisesRegex(ValueError,'missing registered'):mod.load_phase(self.path)
    def test_duplicate_seed_rejected(self):
        self.rows.append(dict(self.rows[0]));self.write()
        with self.assertRaisesRegex(ValueError,'duplicate'):mod.load_phase(self.path)
    def test_different_seed_rejected_even_with_equal_n(self):
        self.rows[-1]['seed']=4;self.write()
        with self.assertRaisesRegex(ValueError,'Unregistered'):mod.load_phase(self.path)
    def test_same_world_verification_required(self):
        self.comp['identical_worlds_verified']=2;self.write()
        with self.assertRaisesRegex(ValueError,'same-world'):mod.load_phase(self.path)
    def test_action_total_reconciled(self):
        self.summary['b']['mean_move_time']+=1;self.write()
        with self.assertRaisesRegex(ValueError,'accounting'):mod.load_phase(self.path)
    def test_unknown_phase_role_not_inferred(self):
        self.reg['role']='unknown';self.write()
        with self.assertRaisesRegex(ValueError,'registered role'):mod.load_phase(self.path)
    def test_summary_statistics_recomputed(self):
        self.summary['b']['p95']+=1;self.write()
        with self.assertRaisesRegex(ValueError,'p95'):mod.load_phase(self.path)


if __name__=='__main__':unittest.main()
