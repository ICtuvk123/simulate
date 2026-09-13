import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
import evidence_scope


class EvidenceScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.previous=evidence_scope.ROOT;evidence_scope.ROOT=self.root
        self.phase=self.root/'reports/R2_unit';self.phase.mkdir(parents=True)
        (self.phase/'registration.json').write_text(json.dumps(dict(role='development')))
        (self.phase/'paired_results.csv').write_text('seed,variant\n1,a\n1,b\n')
    def tearDown(self):
        evidence_scope.ROOT=self.previous;self.temp.cleanup()
    def manifest(self,name):
        folder=self.root/'runs'/name;folder.mkdir(parents=True);(folder/'manifest.json').write_text('{}')
    def test_csv_without_run_column_still_counts_raw_records(self):
        (self.phase/'runs.jsonl').write_text('{"run_id":"one"}\n{"run_id":"two"}\n')
        self.manifest('one');self.manifest('two')
        item=evidence_scope.build()['phases'][0]
        self.assertEqual(item['referenced_runs'],2);self.assertEqual(item['csv_run_references'],0)
    def test_missing_recorded_run_fails_even_without_csv_ids(self):
        (self.phase/'worker0.jsonl').write_text('{"run_id":"missing"}\n')
        with self.assertRaisesRegex(ValueError,'not yet collected'):evidence_scope.build()
    def test_csv_and_raw_records_union_without_double_count(self):
        (self.phase/'paired_results.csv').write_text('seed,run_id\n1,one\n')
        (self.phase/'runs.jsonl').write_text('{"run_id":"one"}\n{"run_id":"two"}\n')
        self.manifest('one');self.manifest('two')
        self.assertEqual(evidence_scope.build()['phases'][0]['raw_runs_included'],2)


if __name__=='__main__':unittest.main()
