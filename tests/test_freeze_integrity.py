import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from verify_freeze import verify


class FreezeIntegrityTests(unittest.TestCase):
    def test_line_endings_are_bytes_not_normalized_away(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'a.py').write_bytes(b'x=1\n');(root/'config.json').write_bytes(b'{"x":1}\n')
            freeze=dict(version='unit',commit='unit',source_hashes={'a.py':hashlib.sha256(b'x=1\n').hexdigest()},configuration={'x':1},config_sha256=hashlib.sha256(b'{"x":1}\n').hexdigest())
            (root/'freeze.json').write_text(json.dumps(freeze))
            self.assertTrue(verify(root/'freeze.json',root,root/'config.json')['valid'])
            (root/'a.py').write_bytes(b'x=1\r\n')
            self.assertIn('a.py',verify(root/'freeze.json',root,root/'config.json')['failures'])
    def test_config_byte_change_is_detected_even_when_options_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'config.json').write_bytes(b'{"x": 1}\n')
            freeze=dict(version='unit',commit='unit',source_hashes={},configuration={'x':1},config_sha256=hashlib.sha256(b'{"x":1}\n').hexdigest())
            (root/'freeze.json').write_text(json.dumps(freeze))
            self.assertIn('configuration_bytes',verify(root/'freeze.json',root,root/'config.json')['failures'])
    def test_extra_source_file_cannot_silently_extend_a_frozen_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'config.json').write_text('{}');(root/'extra.py').write_text('x=1')
            (root/'freeze.json').write_text(json.dumps(dict(version='unit',commit='unit',source_hashes={},configuration={})))
            self.assertIn('unexpected_source:extra.py',verify(root/'freeze.json',root,root/'config.json')['failures'])


if __name__=='__main__':unittest.main()
