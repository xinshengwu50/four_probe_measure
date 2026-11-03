import unittest, tempfile, json, copy, importlib.util
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import pynq_toolkit as t

class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.contract=json.loads((ROOT/'examples/vector_sum/contract.json').read_text())
    def test_contract_and_two_examples(self):
        for name in ['vector_sum','threshold_counter']:
            c=t.load_contract(ROOT/'examples'/name/'contract.json')
            self.assertEqual(c['schema_version'],1)
    def test_bad_access_alignment_names_effect(self):
        for key,value in [('offset',2),('access','unknown'),('read_effect','unknown')]:
            c=copy.deepcopy(self.contract);c['registers']['version'][key]=value
            with self.assertRaises(ValueError):t.validate_contract(c)
        c=copy.deepcopy(self.contract);c['registers']['bad-name']=c['registers'].pop('version')
        with self.assertRaises(ValueError):t.validate_contract(c)
    def test_mmio_permissions_signed_scaled_and_timeout(self):
        bus=t.MemoryTransport({16:65537,8:0xffffffff,4:0})
        d=t.RegisterClient(self.contract,bus)
        self.assertEqual(d.read('result'),-1)
        with self.assertRaises(PermissionError):d.write('version',2)
        with self.assertRaises(PermissionError):d.write('control',1)
        with self.assertRaises(TimeoutError):d.wait('status',1,1,timeout_s=.001,poll_s=.0001)
    def test_dangerous_optin_and_destructive_reads(self):
        c=copy.deepcopy(self.contract);c['registers']['status']['read_effect']='clear'
        d=t.RegisterClient(c,t.MemoryTransport(),allow_writes=True)
        with self.assertRaises(PermissionError):d.read('status')
        with self.assertRaises(PermissionError):d.write('control',1)
        d.write('control',1,allow_side_effect=True)
        with self.assertRaises(ValueError):d.write('control',1<<32,allow_side_effect=True)
    def test_metadata_and_version_fail_before_writes(self):
        info={'processor_0':{'phys_addr':0x40000000,'addr_range':4096,'type':'vendor:ip:vector_sum:1.0'}}
        t.check_ip_dict(self.contract,info)
        with self.assertRaises(ValueError):t.check_ip_dict(self.contract,{})
        bad=copy.deepcopy(info);bad['processor_0']['phys_addr']=0
        with self.assertRaises(ValueError):t.check_ip_dict(self.contract,bad)
        with self.assertRaises(ValueError):t.verify_versions(t.RegisterClient(self.contract,t.MemoryTransport({16:2})))
    def test_golden_signed_abs_relative_nan_shape(self):
        self.assertTrue(t.compare([1,-2],[1.001,-2],atol=.002)['passed'])
        self.assertFalse(t.compare([float('nan')],[0])['passed'])
        self.assertFalse(t.compare([1],[1,2])['passed'])
        self.assertTrue(t.compare([100],[101],rtol=.02)['passed'])
        with self.assertRaises(ValueError):t.compare([1],[1],atol=-1)
    def test_bundle_hash_and_missing_pair(self):
        with tempfile.TemporaryDirectory() as path:
            p=Path(path);(p/'demo.bit').write_bytes(b'not-a-real-bit')
            (p/'demo.hwh').write_text('<ROOT/>')
            t.make_manifest(p/'demo.bit',p/'release.json','TEST_FIXTURE')
            self.assertEqual(t.check_bundle(p/'demo.bit',p/'release.json')['board'],'TEST_FIXTURE')
            (p/'demo.bit').write_bytes(b'changed')
            with self.assertRaises(ValueError):t.check_bundle(p/'demo.bit',p/'release.json')
            (p/'demo.hwh').unlink()
            with self.assertRaises(FileNotFoundError):t.check_bundle(p/'demo.bit',p/'release.json')
    def test_hwh_parser_and_missing_report_not_zero(self):
        xml='<ROOT><MODULE INSTANCE="processor_0" VLNV="vendor:ip:vector_sum:1.0"><MEMRANGE INSTANCE="processor_0" BASEVALUE="0x40000000" HIGHVALUE="0x40000fff"/></MODULE></ROOT>'
        with tempfile.TemporaryDirectory() as path:
            p=Path(path)/'x.hwh';p.write_text(xml)
            t.check_ip_dict(self.contract,t.read_hwh(p))
        report=t.parse_vivado('')
        self.assertIsNone(report['wns_ns']);self.assertIsNone(report['lut'])
        report=t.parse_vivado('WNS(ns) TNS(ns) WHS(ns)\n------- ------- -------\n3.903 0.000 0.032\n| Slice LUTs | 6846 | 0 |\n| DSPs | 9 | 0 |')
        self.assertEqual(report['wns_ns'],3.903);self.assertEqual(report['dsp'],9)
    def test_generation_and_unvalidated_input_rejected(self):
        code=t.generate_driver(self.contract);compile(code,'generated','exec')
        ns={};exec(code,ns);d=ns['Driver'](t.MemoryTransport({16:65537}))
        self.assertEqual(d.read_version(),65537)
    def test_report_provenance_and_no_board_claim(self):
        r=t.validation_report('MOCK',self.contract,t.compare([1],[1]),{})
        self.assertEqual(r['evidence_kind'],'MOCK');self.assertFalse(r['hardware_verified'])
        with self.assertRaises(ValueError):t.validation_report('FAKE',self.contract,{}, {})
    def test_board_disabled_before_import(self):
        with tempfile.TemporaryDirectory() as path:
            p=Path(path);(p/'demo.bit').write_bytes(b'fixture')
            (p/'demo.hwh').write_text('<ROOT><MODULE INSTANCE="processor_0" VLNV="vendor:ip:vector_sum:1.0"><MEMRANGE INSTANCE="processor_0" BASEVALUE="0x40000000" HIGHVALUE="0x40000fff"/></MODULE></ROOT>')
            t.make_manifest(p/'demo.bit',p/'release.json','TEST')
            with self.assertRaises(PermissionError):t.load_board(p/'demo.bit',p/'release.json',self.contract,actual_board='TEST')
            with self.assertRaises(ValueError):t.load_board(p/'demo.bit',p/'release.json',self.contract,actual_board='WRONG')
    def test_xml_entities_blocked(self):
        with tempfile.TemporaryDirectory() as path:
            p=Path(path)/'bad.hwh';p.write_text('<!DOCTYPE x [<!ENTITY y "z">]><ROOT/>')
            with self.assertRaises(ValueError):t.read_hwh(p)
    def test_real_format_timing_header(self):
        result=t.parse_vivado('WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns)\n-----\n3.903 0.000 0 14783 0.032 0.000')
        self.assertEqual(result['wns_ns'],3.903);self.assertEqual(result['whs_ns'],.032)
    def test_no_board_report_without_evidence(self):
        with self.assertRaises(ValueError):t.validation_report('BOARD',self.contract,{}, {})
    def test_manifest_cannot_clobber_bit(self):
        with tempfile.TemporaryDirectory() as path:
            p=Path(path);(p/'x.bit').write_bytes(b'bit');(p/'x.hwh').write_text('<ROOT/>')
            with self.assertRaises(ValueError):t.make_manifest(p/'x.bit',p/'x.bit','board')
            self.assertEqual((p/'x.bit').read_bytes(),b'bit')
if __name__=='__main__':unittest.main()
