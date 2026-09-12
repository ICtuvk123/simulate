import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
import compare_phase


class PortableComparisonTests(unittest.TestCase):
    def fixture(self,root,seeds):
        folder=root/'reports'/'test';folder.mkdir(parents=True)
        (folder/'registration.json').write_text(json.dumps({'seeds':seeds}))
        rows=[]
        for variant,time in [('a',100),('b',90)]:
            directory=root/'runs'/variant;directory.mkdir(parents=True)
            (directory/'evaluation.json').write_text(json.dumps({'sources':[{'channel':1}]}))
            (directory/'manifest.json').write_text(json.dumps({'engine_configuration':{'seed':1}}))
            rows.append({'task':{'seed':1,'variant':variant},'run_id':variant,'directory':'Z:/old-machine/nonexistent',
                         'metrics':{'all_success':True,'mean_time_per_source':time/10,'total_time':time}})
        (folder/'runs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def test_relocated_evidence_ignores_original_absolute_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root,[1]);old=compare_phase.ROOT;compare_phase.ROOT=root
            try:result=compare_phase.compare('test','a','b')
            finally:compare_phase.ROOT=old
            self.assertTrue(result['gate_passed']);self.assertEqual(result['identical_worlds_verified'],1)

    def test_missing_entire_registered_pair_cannot_pass_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root,[1,2]);old=compare_phase.ROOT;compare_phase.ROOT=root
            try:result=compare_phase.compare('test','a','b')
            finally:compare_phase.ROOT=old
            self.assertFalse(result['all_registered_pairs_present']);self.assertFalse(result['gate_passed'])
