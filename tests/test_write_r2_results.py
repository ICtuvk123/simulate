import csv,importlib.util,json,tempfile,unittest
from pathlib import Path

FILE=Path(__file__).resolve().parents[1]/'code/write_r2_results.py'
spec=importlib.util.spec_from_file_location('writer',FILE);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


class ResultsEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.folder=self.root/'reports/check';self.folder.mkdir(parents=True)
        self.options={'version':'best'};self.hashes={'actor.py':mod.hashlib.sha256(b'# frozen\n').hexdigest()}
        self.freeze=dict(source_hashes=self.hashes,config_sha256='bestconfig')
        self.reg=dict(phase='check',role='validation',seeds=[1,2],variants={'base':'base.json','best':'best.json'},
            tasks=[dict(seed=s,variant=v,scene={}) for s in (1,2) for v in ('base','best')],
            worker_provenance=[dict(source_hashes=self.hashes,configurations={
                'base':dict(options={'version':'base'},sha256='baseconfig'),
                'best':dict(options=self.options,sha256='bestconfig')})])
        self.rows=[];self.summary={};self.directories=[]
        for task in self.reg['tasks']:
            v=task['variant'];seed=task['seed'];count=14 if seed==1 else 16;total=(140 if seed==1 else 160)+(10 if v=='base' else 0)
            rid=f'{v}-{seed}';d=self.root/'runs'/rid;(d/'source').mkdir(parents=True);(d/'source/actor.py').write_bytes(b'# frozen\n');self.directories.append(d)
            events=[]
            for i in range(count+2):
                path='/enter' if i==0 else '/exit' if i==count+1 else '/clear'
                response=dict(accepted=True,virtual_time_s=total if path=='/exit' else 0)
                if path=='/clear':response['clear_result']='success'
                events.append(dict(event='response',http_status=200,path=path,payload=dict(request_id=str(i),channel=i),response_body=json.dumps(response)))
            journal=d/'requests.jsonl';journal.write_text(''.join(json.dumps(e)+'\n' for e in events))
            m={k:0. for k in mod.METRICS};m.update(total_time=float(total),mean_time_per_source=total/count,
                policy_wall_time_s=1.,move_time=total-10.,RF_detection_time=5.,channel_switch_time=1.,optical_time=3.,clear_time=1.,
                engine_source_count=count,clear_count=count,all_success=True,run_id=rid,data_origin='local_q4')
            m['journal_bytes']=journal.stat().st_size
            self.write(d/'manifest.json',dict(run_id=rid,source_hashes=self.hashes,policy_options={'version':v}))
            self.write(d/'independent_exit.json',dict(valid=True,journal_sha256=mod.sha(journal)))
            self.write(d/'feedback_replay.json',dict(valid=True,actions=count+2))
            self.rows.append(dict(task=task,run_id=rid,directory=str(d),metrics=m))
        self.flush()
    def tearDown(self):self.tmp.cleanup()
    def write(self,path,value):path.write_text(json.dumps(value),encoding='utf-8')
    def flush(self):
        self.summary={v:mod.stats([r['metrics'] for r in self.rows if r['task']['variant']==v]) for v in ('base','best')}
        self.write(self.folder/'registration.json',self.reg);self.write(self.folder/'summary.json',self.summary)
        self.write(self.folder/'independent_exit_report.json',dict(runs=4,all_valid=True))
        (self.folder/'runs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
        with (self.folder/'paired_results.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['seed','variant','total_time','mean_time_per_source','all_success','engine_source_count'])
            for r in self.rows:
                m=r['metrics'];w.writerow([r['task']['seed'],r['task']['variant'],m['total_time'],m['mean_time_per_source'],m['all_success'],m['engine_source_count']])
        a,b=self.summary['base'],self.summary['best'];self.write(self.folder/'comparison_base_best.json',dict(
            baseline='base',candidate='best',pairs=2,all_registered_pairs_present=True,identical_worlds_verified=2,
            mean_per_source_baseline=a['mean_per_source'],mean_per_source_candidate=b['mean_per_source'],
            improvement_percent=100*(1-b['mean_per_source']/a['mean_per_source']),p95_baseline=a['p95'],p95_candidate=b['p95'],
            all_success=all(r['metrics']['all_success'] for r in self.rows)))
    def audit(self):return mod.audit_phase(self.root,'check',self.freeze,self.options)
    def test_full_raw_evidence_and_auto_best(self):
        p=self.audit();self.assertEqual(p['variant'],'best');self.assertTrue(p['all_verified']);self.assertEqual(len(p['audits']),4)
    def test_source_count_14_and_empty_strata(self):
        s=mod.source_strata(self.audit());self.assertEqual(len(s),14)
        fourteen=next(r for r in s if r['variant']=='best' and r['source_count']==14)
        self.assertEqual(fourteen['n'],1);self.assertEqual(fourteen['mean_per_source'],10.)
        self.assertEqual(next(r for r in s if r['variant']=='best' and r['source_count']==10)['n'],0)
    def test_actual_source_tamper_rejected(self):
        (self.directories[0]/'source/actor.py').write_bytes(b'# changed\n')
        with self.assertRaisesRegex(ValueError,'changed source'):self.audit()
    def test_missing_run_not_dropped(self):
        self.rows.pop();self.flush()
        with self.assertRaisesRegex(ValueError,'Missing registered'):self.audit()
    def test_journal_changed_since_independent_exit_rejected(self):
        with (self.directories[0]/'requests.jsonl').open('a') as f:f.write('\n')
        with self.assertRaisesRegex(ValueError,'bind this journal'):self.audit()
    def test_failed_run_retained_without_success_only_average(self):
        self.rows[-1]['metrics']['all_success']=False;self.flush();p=self.audit()
        self.assertEqual(p['summary']['best']['n'],2);self.assertEqual(p['summary']['best']['complete'],1);self.assertFalse(p['all_verified'])
    def test_frozen_multiversion_registration_supported(self):
        old=self.reg['worker_provenance'][0];self.reg['worker_provenance']={v:[dict(source_hashes=old['source_hashes'],configuration=c['options'],config_sha256=c['sha256'])] for v,c in old['configurations'].items()};self.flush()
        self.assertEqual(self.audit()['variant'],'best')
    def test_incumbent_hash_mismatch_rejected(self):
        self.freeze['source_hashes']={'actor.py':'wrong'}
        with self.assertRaisesRegex(ValueError,'identify incumbent'):self.audit()
    def test_current_configuration_mismatch_rejected(self):
        self.freeze['config_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'configuration'):self.audit()
    def test_source_count_does_not_leak_from_filename(self):
        self.rows[0]['metrics']['engine_source_count']=13;self.flush()
        with self.assertRaisesRegex(ValueError,'per source'):self.audit()
    def test_replay_failure_is_visible_not_filtered(self):
        self.write(self.directories[0]/'feedback_replay.json',dict(valid=False,actions=16))
        p=self.audit();self.assertFalse(p['all_verified']);self.assertEqual(len(p['audits']),4)
    def test_historical_report_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError,'Historical'):mod.build(self.root,self.root/'reports/RESULTS_REPORT.md')
    def test_original_absolute_directory_is_not_an_evidence_source(self):
        # The raw files are local; an obsolete developer directory must not
        # redirect the audit away from the explicitly selected evidence root.
        self.rows[0]['directory']=str(self.root/'obsolete_developer_worktree')
        self.flush();self.assertTrue(self.audit()['all_verified'])
    def test_run_id_cannot_escape_selected_evidence_root(self):
        self.rows[0]['run_id']='../outside';self.flush()
        with self.assertRaisesRegex(ValueError,'leaves evidence root'):self.audit()


if __name__=='__main__':unittest.main()
