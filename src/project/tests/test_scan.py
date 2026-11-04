# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest,tempfile
from dataclasses import replace
from pathlib import Path
from support import Uart,Frontend,System
from four_all_hmi_ui.hmi_address import NumericPageUart
from four_all_hmi_ui.hmi_single_point import MeasurementConfig,MeasurementMode
from hmi_four_all import FourAllHmiService
from four_probe_sw.direct_adc_measurement import MeasurementAbortedError
from test_open_current_loop import _system

class ScanTests(unittest.TestCase):
    def service(self,abort_at=None):
        self.raw=Uart();front=Frontend();self.events=[]
        fixture=System(lambda *a:None,lambda r:None,count=25);fixture.run_scan('25');rows=fixture.results
        # Synthetic fixtures use permittedR1; no hardware/currents are enabled by this test.
        for row in rows:row.update(range_index=1,equivalent_current_a=.001,forward_current_a=.001,reverse_current_a=.001)
        def factory(config,**callbacks):
            s=_system(allow_motion=True);self.core=s
            s.on_point=callbacks['on_point'];s.on_range_selected=callbacks['on_range_selected']
            state={'status':0}
            s._read=lambda a:state['status'] if a==4 else 0x414C5835 if a==16 else 0
            def write(a,v):
                if a==0 and v==32:state['status']=1<<16
            s._write=write;s.preflight=lambda:None
            s.axis_home=lambda *a,**kw:self.events.append('home')
            s.verify_axis_home=lambda *a:None;s.r_move_to=lambda *a,**kw:None
            s.x_rotate_pulses=lambda *a,**kw:None;s.z_move_to_measure=lambda *a,**kw:None;s.z_move_to=lambda *a,**kw:None
            def point(p,first_point=False):
                i=1 if p.ring==0 else 2+p.point_index if p.ring==1 else 10+p.point_index
                if i==abort_at:s.request_system_reset('offlineRST');s._raise_if_measurement_aborted()
                if s.selected_range_index is None:s.selected_range_index=1;s.on_range_selected(1,.001,.001)
                return rows[i-1]
            s._measure_point=point
            return s
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        return FourAllHmiService(NumericPageUart(self.raw),front,factory,allow_motion=True,arm_current=True,
                               geometry_confirmed=True,output_dir=tmp.name,trace=False)
    def test_real_scan_orchestrator_single9and25_save_history(self):
        for mode,n in [(MeasurementMode.SINGLE_POINT,1),(MeasurementMode.NINE_POINT,9),(MeasurementMode.TWENTY_FIVE_POINT,25)]:
            s=self.service();r=s.run(MeasurementConfig(measurement_mode=mode))
            self.assertEqual(r['status'],'COMPLETE');self.assertEqual(r['points_completed'],n)
            self.assertEqual(self.core.last_summary.valid_points,n)
            self.assertTrue(Path(r['csv_path']).is_file());self.assertTrue(Path(r['json_path']).is_file())
            self.assertEqual(len(s.history.load_recent(1).rows),n)
            self.assertEqual(s.history.restore(s.uart,1)['status'],'RESTORED')
    def test_rst_saves_partial_never_complete_history_or_auto_home(self):
        s=self.service(abort_at=3);r=s.run(MeasurementConfig(measurement_mode=MeasurementMode.NINE_POINT))
        self.assertEqual(r['status'],'ERROR');self.assertEqual(r['points_completed'],2)
        self.assertEqual(self.events,['home','home']);self.assertTrue(self.core.shutdown_result['held_in_place'])
        self.assertEqual(s.history.list_history(),[]);self.assertTrue(Path(r['csv_path']).is_file())
    def test_native_voltage_screen_and_csv_have_no_display_multiplier(self):
        s=self.service();self.assertEqual(s._display_voltage(.123,False),.123)
        self.assertEqual(s._display_voltage(-.123,True),-.123)
        self.assertIsNone(s._display_voltage(None,False))
if __name__=='__main__':unittest.main()
