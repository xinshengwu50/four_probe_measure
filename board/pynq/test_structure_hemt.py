# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest
from dataclasses import replace
from unittest.mock import Mock,patch
from test_hmi_frame42 import frame
from four_all_hmi_ui.hmi_single_point import parse_22hmi_config,SampleKind,MeasurementMode
from four_probe_sw.multi_material_model import calculate_four_probe,SampleType
from hmi_four_all import make_system_factory

class Tests(unittest.TestCase):
    def test_structure2_keeps_material_and_routes_hemt(self):
        c=parse_22hmi_config(frame(material=3,structure=2))
        self.assertEqual(c.sample_kind,SampleKind.SILICON)
        self.assertEqual(c.model_sample_kind,SampleKind.HEMT)

    def test_old_material1_not_hemt_selector_in_new_frame(self):
        for structure in (0,1,2):
            with self.assertRaises(ValueError):parse_22hmi_config(frame(material=1,structure=structure))

    def test_model_structure2_equivalent_to_existing_hemt_single_model(self):
        kw=dict(is_n_type=True,diameter_mm=50,thickness_um=645,current_ma=1,voltage_mv=10)
        a=calculate_four_probe(sample_type=SampleType.SILICON,sample_structure=2,**kw)
        b=calculate_four_probe(sample_type=SampleType.HEMT,sample_structure=0,**kw)
        self.assertEqual(a,b);self.assertEqual(a.ndop_cm3,0.)

    def test_factory_hemt_model_but_original_material_motion(self):
        c=parse_22hmi_config(frame(material=3,structure=2))
        with patch('hmi_four_all.FinalFourProbeSystem') as cls:
            make_system_factory(None,None,None)(c)
        self.assertEqual(cls.call_args.args[4],SampleType.HEMT)
        self.assertEqual(cls.call_args.kwargs['full_down_steps'],7450)

    def test_aln_remains_rejected_even_with_structure2(self):
        c=replace(parse_22hmi_config(frame(material=2,structure=2)),sample_kind=SampleKind.ALN)
        with patch('hmi_four_all.FinalFourProbeSystem') as cls:
            with self.assertRaises(ValueError):make_system_factory(None,None,None)(c)
        cls.assert_not_called()

    def test_multpoint_metadata_routes_hemt_pages_without_changing_material(self):
        from four_all_hmi_ui.hmi_points_scan import MultiPointWriter
        c=replace(parse_22hmi_config(frame(material=3,structure=2)),
                  measurement_mode=MeasurementMode.NINE_POINT,current_ma=10.)
        from four_all_hmi_ui.hmi_single_point import Hmi22Writer
        uart=Mock();writer=MultiPointWriter(Hmi22Writer(uart))
        writer.write_metadata(c.measurement_mode,c)
        commands=[call.args[0] for call in uart.send_command.call_args_list]
        self.assertTrue(any('p[11].' in cmd for cmd in commands))
        self.assertIn('p[9].x85.val=1',commands)
        self.assertEqual(c.sample_kind,SampleKind.SILICON)

if __name__=='__main__':unittest.main()

