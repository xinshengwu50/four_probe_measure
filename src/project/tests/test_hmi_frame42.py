# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest,struct,tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock,patch
from four_all_hmi_ui.hmi_single_point import parse_22hmi_config,Hmi22ConfigParser,SampleKind
from four_all_hmi_ui.hmi_wire import config_frame_length,split_config_frame
from hmi_emergency import EmergencyReceiver
from hmi_four_all import make_system_factory,FourAllHmiService
from four_probe_sw.multi_material_model import calculate_four_probe,SampleType,fw_from_alpha

def frame(current=0,structure=0,material=3,point=1):
    return b'\xaa'+b''.join(bytes([k])+struct.pack('<I',v) for k,v in [(0xbb,1),(0xcc,500),(0xdd,64500),(0xee,current),(0xff,material),(0x66,1),(0x77,point),(0x88,structure)])+b'\xaa'

class Tests(unittest.TestCase):
    def test_all_modes(self):
        for mode,ma in enumerate([None,.1,1.,10.,100.]):
            c=parse_22hmi_config(frame(current=mode));self.assertEqual(c.current_mode,mode)
            self.assertEqual(c.current_ma,ma);self.assertEqual(c.sample_structure,0)
    def test_length_and_split(self):
        b=frame();self.assertEqual(len(b),42);self.assertEqual(config_frame_length(b),42)
        self.assertEqual(struct.unpack('<I',split_config_frame(b)[0x88])[0],0)
    def test_every_split(self):
        b=frame()
        for i in range(1,42):
            p=Hmi22ConfigParser();self.assertEqual(p.feed(b[:i]),[]);self.assertEqual(len(p.feed(b[i:])),1)
    def test_back_to_back(self):
        self.assertEqual(len(Hmi22ConfigParser().feed(frame()+frame(current=2))),2)
    def test_rst(self):
        mm=Mock();mm.read.return_value=0;r=EmergencyReceiver(mm);out=bytearray()
        for b in frame()+b'RST\r\n':out.extend(r.feed(bytes([b])))
        self.assertEqual(bytes(out),frame());self.assertTrue(r.stopped.is_set())
        mm.write.assert_called_with(0x00,0x20)
    def test_gan_parse(self):self.assertEqual(parse_22hmi_config(frame(material=4)).sample_kind.value,'gan')
    def test_invalid(self):
        for kw in [dict(current=5),dict(structure=3),dict(point=0),dict(point=26)]:
            with self.assertRaises(ValueError):parse_22hmi_config(frame(**kw))
    def test_manual_factory(self):
        c=parse_22hmi_config(frame(current=2))
        with patch('hmi_four_all.FinalFourProbeSystem') as cls:
            make_system_factory(None,None,None)(c)
            self.assertEqual(cls.call_args.kwargs['range_indices'],(1,))
            self.assertFalse(cls.call_args.kwargs['select_range_by_resistivity'])
    def test_100ma_locked(self):
        with self.assertRaises(PermissionError):make_system_factory(None,None,None)(parse_22hmi_config(frame(current=4)))
    def test_structure_model(self):
        kw=dict(sample_type=SampleType.SILICON,is_n_type=True,diameter_mm=50,thickness_um=645,current_ma=1,voltage_mv=10)
        a=calculate_four_probe(**kw,sample_structure=0);b=calculate_four_probe(**kw,sample_structure=1)
        self.assertEqual(a.fw,1.)
        self.assertAlmostEqual(b.fw,fw_from_alpha(.645))
        self.assertAlmostEqual(b.resistivity_ohm_cm/a.resistivity_ohm_cm,b.fw)
    def test_aln_no_motion_saved(self):
        with tempfile.TemporaryDirectory() as d:
            frontend=Mock();factory=Mock()
            service=FourAllHmiService(Mock(),frontend,factory,output_dir=d)
            with self.assertRaises(ValueError):service.run(replace(parse_22hmi_config(frame(material=2)),sample_kind=SampleKind.ALN))
            frontend.assert_not_called();factory.assert_not_called()
            self.assertTrue(list((Path(d)/'requests').glob('*.json')))
    def test_factory_structure_callback(self):
        c=parse_22hmi_config(frame(structure=0))
        with patch('hmi_four_all.FinalFourProbeSystem') as cls:
            make_system_factory(None,None,None)(c)
            model=cls.call_args.args[3]
            result=model(sample_type=SampleType.SILICON,is_n_type=True,diameter_mm=50,thickness_um=645,current_ma=1,voltage_mv=10)
            self.assertEqual(result.fw,1.)
    def test_manual_100ma_requires_both_gates(self):
        c=parse_22hmi_config(frame(current=4))
        with self.assertRaises(PermissionError):make_system_factory(None,None,None,allow_100ma=True)(c)
        with patch('hmi_four_all.FinalFourProbeSystem') as cls:
            make_system_factory(None,None,None,range_indices=(0,1,2,3),allow_100ma=True)(c)
            self.assertEqual(cls.call_args.kwargs['range_indices'],(3,))
    def test_history_metadata_roundtrip(self):
        from dataclasses import asdict
        from four_all_hmi_ui.hmi_single_point import MeasurementConfig,MeasurementMode
        c=parse_22hmi_config(frame(current=3,structure=1))
        import json
        v=json.loads(json.dumps(asdict(c)))
        v['sample_kind']=SampleKind(v['sample_kind']);v['measurement_mode']=MeasurementMode(v['measurement_mode'])
        d=MeasurementConfig(**v).validate()
        self.assertEqual((d.current_mode,d.sample_structure),(3,1))
    def test_crc_marker_corruption_rejected(self):
        b=bytearray(frame());b[36]=0x89
        with self.assertRaises(ValueError):split_config_frame(b)
    def test_mixed_frames(self):
        old=frame(current=1000)[:36]+b'\xaa';auto=old[:17]+old[21:]
        self.assertEqual(len(Hmi22ConfigParser().feed(auto+frame()+old)),3)
    def test_legacy(self):
        old=frame(current=1000)[:36]+b'\xaa'
        c=parse_22hmi_config(old);self.assertIsNone(c.current_mode);self.assertIsNone(c.sample_structure)
        auto=old[:17]+old[21:]
        self.assertIsNone(parse_22hmi_config(auto).current_ma)
if __name__=='__main__':unittest.main()
