# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Native units, real service setup and PL driver regression; offline only."""
import ast,inspect,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from dataclasses import replace
from four_probe_sw import direct_adc_measurement as adc,pl_autorange as p,pl_resistivity as rho
from four_probe_sw.final_four_probe_system import FinalFourProbeSystem
from hmi_four_all import make_system_factory,FourAllHmiService
from support import FakeFpDsp
from test_hmi_frame42 import frame
from four_all_hmi_ui.hmi_single_point import parse_22hmi_config
ROOT=next(p/'board/pynq' for p in Path(__file__).resolve().parents if (p/'board/pynq/01_four_all_system.ipynb').is_file())

class SystemTests(unittest.TestCase):
    def driver(self,ohm=99.7,**kw):
        model=p.SampleModel(ohm,**kw);fake=FakeFpDsp(model);driver=p.PlAutorange(fake,sleep=lambda _:None)
        driver.identify();driver.claim();driver.configure(model.forward_current_a,model.reverse_current_a,[model.center_code]*8)
        return model,fake,driver
    def test_native_conversion_no_gain_interface(self):
        self.assertAlmostEqual(adc.adc_voltage_to_probe_voltage_v(2.6),.1)
        self.assertEqual(p.volts_per_code(),adc.ADC_LSB_V)
        for fn in [FinalFourProbeSystem,adc.capture_valid_probe_samples,p.PlAutorange.configure,rho.coefficient_k,rho.coefficient_k_rs]:
            self.assertNotIn('probe_voltage_scale',inspect.signature(fn).parameters)
        self.assertNotIn('forward_voltage_display_scale',inspect.signature(FourAllHmiService).parameters)
    def test_native_fixed_point_coefficients(self):
        self.assertAlmostEqual(rho.coefficient_k(adc.ADC_LSB_V,4.5,1.,.0645,1.,.001),adc.ADC_LSB_V*4.5*.0645/.001)
        self.assertAlmostEqual(rho.coefficient_k_rs(adc.ADC_LSB_V,4.5,1.,1.,.001),adc.ADC_LSB_V*4.5/.001)
    def test_native_register_limits(self):
        r=p.AutorangeConfig().registers();self.assertEqual(r.s_hi,3200);self.assertEqual(r.raw_sat,10240)
        self.assertEqual(r.pair_mode,1)
        with self.assertRaises(TypeError):p.AutorangeConfig(abba_cycles=1)
    def test_full_once_per_polarity(self):
        model,fake,d=self.driver(offset_v=.003);out=d.run(p.MODE_FULL)
        self.assertTrue(out.ok);self.assertEqual(out.selected_range,1)
        self.assertEqual((out.windows_forward,out.windows_reverse),(1,1))
        self.assertEqual(out.forward.count,model.samples_per_window)
        self.assertAlmostEqual(out.as_record()['signal_v'],.0997,delta=2*adc.ADC_LSB_V)
        self.assertNotIn('histogram',out.as_record());self.assertNotIn('spectrum',out.as_record())
    def test_verify_and_forced(self):
        _,_,d=self.driver();d.run(p.MODE_FULL)
        keep=d.run(p.MODE_VERIFY,1);self.assertTrue(keep.ok);self.assertFalse(keep.reranged)
        rerange=d.run(p.MODE_VERIFY,2);self.assertTrue(rerange.ok);self.assertTrue(rerange.reranged)
        forced=d.run(p.MODE_FORCED,0);self.assertTrue(forced.ok);self.assertEqual(forced.windows_forward,1)
    def test_open_loop_and_large_emf(self):
        for e in (.008,.8):
            _,_,d=self.driver(open_loop=True,offset_v=e)
            for mode,index in [(p.MODE_FULL,0),(p.MODE_VERIFY,1)]:
                out=d.run(mode,index);self.assertFalse(out.ok);self.assertEqual(out.reason,p.R_OPEN_LOOP)
    def test_all_enabled_masks(self):
        for mask in range(1,8):
            _,_,d=self.driver();cfg=replace(d.config,range_mask=mask);d.configure([1e-4,1e-3,1e-2,.1],[1e-4,1e-3,1e-2,.1],[48768]*8,cfg)
            o=d.run(p.MODE_FULL);self.assertTrue(o.ok);self.assertTrue(mask&(1<<o.selected_range))
    def test_old_bit_driver_rejected(self):
        _,f,d=self.driver();f.force_version=4
        with self.assertRaises(p.PlAutorangeError):d.identify()
    def test_ownership_and_invalid_parameters(self):
        _,f,d=self.driver();d.release()
        with self.assertRaises(p.PlAutorangeError):d.run(p.MODE_FULL)
        for cfg in [p.AutorangeConfig(range_mask=0),p.AutorangeConfig(measure_window_ms=0),p.AutorangeConfig(settle_max_ms=1)]:
            with self.assertRaises(ValueError):cfg.registers()
    def test_busy_configuration_rejected(self):
        _,f,d=self.driver();f.force_busy=True
        with self.assertRaises(p.PlAutorangeError):d.configure([1e-4]*4,[1e-4]*4,[48768]*8)
    def test_factory_materials_and_modes_native(self):
        for material in (2,3,4):
            for mode in (1,2,3):
                c=replace(parse_22hmi_config(frame(material=material)),measurement_mode=type(parse_22hmi_config(frame()).measurement_mode)(mode))
                with patch('hmi_four_all.FinalFourProbeSystem') as cls:make_system_factory(None,None,None)(c)
                self.assertNotIn('probe_voltage_scale',cls.call_args.kwargs)
                self.assertEqual(cls.call_args.kwargs['full_down_steps'],7450 if material==3 else 7600)
    def test_manual100ma_requires_explicit_authorization(self):
        c=parse_22hmi_config(frame(current=4))
        with self.assertRaises(PermissionError):make_system_factory(None,None,None)(c)
    def test_notebook_configuration_and_actual_service_setup(self):
        from hmi_range04 import RangePictures,RangeFrontendProxy,RangePlProxy,RangeVisualService
        n=json.loads((ROOT/'01_four_all_system.ipynb').read_text());cells=[''.join(c['source']) for c in n['cells'] if c['cell_type']=='code']
        ns={'AutorangeConfig':p.AutorangeConfig};exec(next(s for s in cells if 'ALLOW_MOTION = False' in s),ns)
        for gate in ('ALLOW_MOTION','ARM_CURRENT','ALLOW_100MA','GEOMETRY_CONFIRMED'):self.assertIs(ns[gate],False)
        ns.update(mmio=Mock(),frontend=Mock(),monitor=Mock(),uart=Mock(),BIT=ROOT/'all_design.bit',ROOT=ROOT,
                  emergency=Mock(),pl_autorange=None,RangePictures=RangePictures,RangeFrontendProxy=RangeFrontendProxy,
                  RangePlProxy=RangePlProxy,RangeVisualService=RangeVisualService,make_system_factory=make_system_factory)
        service=next(s for s in cells if 'service = RangeVisualService(' in s)
        exec(service[:service.index("if (ROOT/'STOP_HMI_LISTENER')")],ns)
        self.assertIsInstance(ns['service'],RangeVisualService)
        with patch('hmi_four_all.FinalFourProbeSystem') as cls:ns['factory'](parse_22hmi_config(frame()))
        self.assertNotIn('probe_voltage_scale',cls.call_args.kwargs)
        text='\n'.join(cells)
        for retired in ['web_server','ABBA','PROBE_VOLTAGE_SCALE','DISPLAY_SCALE','hmi_auto_images','GAN_MODE','pl_wave_recorder']:
            self.assertNotIn(retired,text)
    def test_safety_gates_before_motion(self):
        s=FourAllHmiService(Mock(),Mock(),Mock())
        with self.assertRaises(PermissionError):s.run(parse_22hmi_config(frame()))
        s.system_factory.assert_not_called()
    def test_actual_core_uses_native_pl_snapshot_and_model(self):
        from test_open_current_loop import _system,CURRENT_A
        from four_probe_sw.multi_material_model import calculate_four_probe,SampleType
        model=p.SampleModel(99.7,forward_current_a=CURRENT_A,reverse_current_a=CURRENT_A)
        driver=p.PlAutorange(FakeFpDsp(model),sleep=lambda _:None)
        core=_system(pl_autorange=driver)
        core.calculate_four_probe=calculate_four_probe;core.sample_type=SampleType.ALGAN
        core._read=lambda a:0;core._write=lambda a,v:None
        core._prepare_pl_autorange()
        row=core._measure_point_once_pl(core.build_scan_plan(9)[0],first_point=True)
        self.assertTrue(row['point_valid'])
        self.assertAlmostEqual(row['combined_resistance_ohm'],99.7,delta=.2)
        self.assertLess(row['forward_voltage_v'],.2)
        self.assertEqual(row['voltage_domain'],'adc_native')
        self.assertNotIn('probe_voltage_scale',row)
    def test_ps_fallback_acquires_exactly_two_directions(self):
        from four_probe_sw.direct_adc_measurement import _range_measurement_from_snapshot
        model,_,driver=self.driver()
        result=driver.run(p.MODE_FORCED,1)
        halves=[_range_measurement_from_snapshot(result.snapshot(pol),range_index=1,reverse=pol,
                    current_a=.001,probe_voltage_offset_v=0.,probe_abs_min_v=.005,probe_abs_max_v=2.) for pol in (False,True)]
        with patch.object(adc,'measure_range_once',side_effect=halves) as capture:
            pair=adc.measure_bidirectional(Mock(),Mock(),1,forward_current_a=.001,reverse_current_a=.001)
        self.assertEqual(capture.call_count,2)
        self.assertEqual([c.kwargs['reverse'] for c in capture.call_args_list],[False,True])
        self.assertEqual(pair.pair_repeats,1)
        self.assertNotIn('pair_repeats',inspect.signature(adc.measure_bidirectional).parameters)
    def test_deployment_manifest_matches_new_core_and_pair(self):
        from four_probe_sw.final_four_probe_system import check_deploy_manifest
        check_deploy_manifest(ROOT/'four_probe_sw/deploy_manifest.json',ROOT/'four_probe_sw',ROOT/'all_design.bit')

if __name__=='__main__':unittest.main()
