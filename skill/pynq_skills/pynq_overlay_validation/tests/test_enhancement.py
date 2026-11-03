import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import source_identity as mod
class EnhancementTests(unittest.TestCase):

    def test_match_and_difference(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            a,b = Path(d)/'a.v',Path(d)/'b.v'
            a.write_text('module a; endmodule'); b.write_bytes(a.read_bytes())
            self.assertTrue(mod.audit_sources([a,b])['passed'])
            b.write_text('module b; endmodule')
            self.assertFalse(mod.audit_sources([a,b])['passed'])
            with self.assertRaises(ValueError): mod.audit_sources([a,a])
            with self.assertRaises(FileNotFoundError): mod.audit_sources([a,Path(d)/'missing'])

if __name__=='__main__':unittest.main()
