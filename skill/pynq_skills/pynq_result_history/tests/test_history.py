import sys,unittest,tempfile,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from result_history import save_snapshot,load_snapshot,list_history,restore_snapshot,validate_snapshot
from run_example import mock_snapshot
class HistoryTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            m,r=mock_snapshot();p=save_snapshot(d,m,r);s=load_snapshot(p)
            self.assertEqual(s['metadata'],m);self.assertEqual(s['records'],r)
    def test_exclusive_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            m,r=mock_snapshot();p=save_snapshot(d,m,r);raw=p.read_bytes()
            with self.assertRaises(FileExistsError):save_snapshot(d,m,r)
            self.assertEqual(p.read_bytes(),raw);self.assertFalse(list(Path(d).glob('*.tmp')))
    def test_complete_missing_pair(self):
        m,r=mock_snapshot()
        with self.assertRaises(ValueError):validate_snapshot(m,r[:-1])
        m['complete']=False;validate_snapshot(m,r[:-1])
    def test_missing_null_flags(self):
        m,r=mock_snapshot();r[0]['value']=None;r[0]['quality_flags']=['ADC_OFF']
        validate_snapshot(m,r);r[0]['quality_flags']=[]
        with self.assertRaises(ValueError):validate_snapshot(m,r)
    def test_units_duplicate_nonfinite(self):
        m,r=mock_snapshot();bad=copy.deepcopy(r);bad[0]['unit']='mV'
        with self.assertRaises(ValueError):validate_snapshot(m,bad)
        with self.assertRaises(ValueError):validate_snapshot(m,r+[r[0]])
        r[0]['value']=float('nan')
        with self.assertRaises(ValueError):validate_snapshot(m,r)
    def test_no_io_before_validation(self):
        with tempfile.TemporaryDirectory() as d:
            m,r=mock_snapshot();m['run_id']='../escape'
            with self.assertRaises(ValueError):save_snapshot(Path(d)/'new',m,r)
            self.assertFalse((Path(d)/'new').exists())
    def test_list_sources_partial_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            m,r=mock_snapshot();save_snapshot(d,m,r)
            m['run_id']='partial';m['complete']=False;save_snapshot(d,m,r[:-1])
            (Path(d)/'broken.csv').write_text('garbage')
            x=list_history(d,source='MOCK');self.assertEqual(len(x['items']),1);self.assertEqual(len(x['errors']),1)
            self.assertEqual(list_history(d,source='BOARD')['items'],[])
    def test_page_first_and_no_callback_on_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            m,r=mock_snapshot();p=save_snapshot(d,m,r);events=[]
            restore_snapshot(p,begin=lambda m:events.append('page'),write_row=lambda r:events.append(r),finish=lambda m:events.append('done'))
            self.assertEqual(events[0],'page');self.assertEqual(events[-1],'done');self.assertEqual(len(events),52)
            p.write_text('bad');events.clear()
            with self.assertRaises(ValueError):restore_snapshot(p,begin=lambda m:events.append('page'),write_row=lambda r:events.append(r),finish=lambda m:events.append('done'))
            self.assertFalse(events)
    def test_failed_write_never_finishes(self):
        with tempfile.TemporaryDirectory() as d:
            m,r=mock_snapshot();p=save_snapshot(d,m,r);events=[]
            def fail(row):raise RuntimeError('display disconnected')
            with self.assertRaises(RuntimeError):restore_snapshot(p,begin=lambda m:events.append('page'),write_row=fail,finish=lambda m:events.append('done'))
            self.assertEqual(events,['page'])
    def test_malformed_quantity_and_formula_label(self):
        m,r=mock_snapshot();r[0]['quantity']=[]
        with self.assertRaises(ValueError):validate_snapshot(m,r)
        m,r=mock_snapshot();m['quantities']={'=1+1':'V'}
        with self.assertRaises(ValueError):validate_snapshot(m,r)
    def test_byte_limit(self):
        with tempfile.TemporaryDirectory() as d:
            m,r=mock_snapshot();p=save_snapshot(d,m,r)
            with self.assertRaises(ValueError):load_snapshot(p,max_bytes=20)
if __name__=='__main__':unittest.main()
