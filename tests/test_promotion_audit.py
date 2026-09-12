import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from promote_candidate import require_independent_exit


class PromotionAuditTests(unittest.TestCase):
    def test_missing_or_mismatched_second_audit_cannot_promote(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);journal=folder/'requests.jsonl';journal.write_text('original accepted journal')
            with self.assertRaises(ValueError):require_independent_exit(folder)
            report=dict(valid=True,truth_read=False,controller_geometry_imported=False,
                        journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest())
            (folder/'independent_exit.json').write_text(json.dumps(report))
            require_independent_exit(folder)
            journal.write_text('changed journal')
            with self.assertRaises(ValueError):require_independent_exit(folder)

    def test_failed_or_nonindependent_proof_cannot_promote(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);journal=folder/'requests.jsonl';journal.write_text('journal')
            original=dict(valid=True,truth_read=False,controller_geometry_imported=False,
                          journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest())
            for key,value in [('valid',False),('truth_read',True),('controller_geometry_imported',True)]:
                (folder/'independent_exit.json').write_text(json.dumps(dict(original,**{key:value})))
                with self.assertRaises(ValueError):require_independent_exit(folder)


if __name__=='__main__':unittest.main()
