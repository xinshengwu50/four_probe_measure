import sys,unittest,tempfile,hashlib,contextlib,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_package
class PackageAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.old=audit_package.ROOT;audit_package.ROOT=self.root
        (self.root/'README.md').write_text('[entry](module.py)',encoding='utf-8')
        (self.root/'module.py').write_text('answer=42',encoding='utf-8');self.refresh()
    def tearDown(self):
        audit_package.ROOT=self.old;self.temp.cleanup()
    def refresh(self):
        rows=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in self.root.iterdir() if p.name!='checksums.sha256']
        (self.root/'checksums.sha256').write_text('\n'.join(rows),encoding='utf-8')
    def test_good(self):
        with contextlib.redirect_stdout(io.StringIO()):audit_package.audit()
    def test_mutated_source_fails_hash(self):
        (self.root/'module.py').write_text('answer=43')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):audit_package.audit()
    def test_missing_link_fails_even_with_new_manifest(self):
        (self.root/'README.md').write_text('[entry](missing.py)');self.refresh()
        with self.assertRaisesRegex(ValueError,'broken link'):audit_package.audit()
    def test_syntax_fails_even_with_new_manifest(self):
        (self.root/'module.py').write_text('def broken(');self.refresh()
        with self.assertRaises(SyntaxError):audit_package.audit()
if __name__=='__main__':unittest.main()
