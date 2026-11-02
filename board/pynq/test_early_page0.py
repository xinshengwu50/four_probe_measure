# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Final valid point publishes report inputs before run_scan returns/home/save."""
import unittest
from dataclasses import replace
from unittest.mock import Mock
from test_hmi_frame42 import frame
from four_all_hmi_ui.hmi_single_point import parse_22hmi_config, MeasurementMode, QualityFlag
from hmi_four_all import FourAllHmiService


class Tests(unittest.TestCase):
    def service(self, mode, completed=0, point=1):
        s = FourAllHmiService(Mock(), Mock(), Mock(), trace=False)
        s.request_config = replace(parse_22hmi_config(frame(point=point)), measurement_mode=mode)
        s.range_ready = True
        s.selected_range_index = 2
        s.points_completed = completed
        s.writer = Mock()
        s.points = Mock()
        s.heatmap = Mock()
        s.rho_heatmap = Mock()
        s._display_result = lambda result: result
        return s

    def row(self, ring, index, valid=True):
        return dict(ring=ring, point_index=index, point_valid=valid,
                    forward_voltage_v=.1, reverse_voltage_v=-.1, combined_voltage_v=.1,
                    equivalent_current_a=.01, forward_current_a=.01, reverse_current_a=.01,
                    combined_resistance_ohm=10., sheet_resistance_ohm_sq=100.,
                    resistivity_ohm_cm=2., ndop_cm3=1e15, fd=1., fw=1., fsp=1.,
                    forward_valid_samples=10, reverse_valid_samples=10)

    def test_last_valid_point_refreshes_without_complete_or_scan_return(self):
        for mode, completed, ring, index, point in [
            (MeasurementMode.NINE_POINT, 8, 1, 7, 1),
            (MeasurementMode.TWENTY_FIVE_POINT, 24, 2, 15, 1),
            (MeasurementMode.SINGLE_POINT, 0, 1, 2, 4),
        ]:
            with self.subTest(mode=mode):
                s=self.service(mode, completed, point)
                s._publish(self.row(ring,index))
                s.writer.write_result.assert_called_once()
                args=s.writer.write_result.call_args
                self.assertFalse(args.kwargs['include_point'])
                self.assertNotIn(QualityFlag.MEASUREMENT_COMPLETE,args.args[0].quality_flags)
                s.system_factory.assert_not_called()
                s.frontend.safe_off.assert_not_called()

    def test_not_last_and_invalid_last_do_not_refresh_report(self):
        s=self.service(MeasurementMode.NINE_POINT)
        s._publish(self.row(0,0))
        s.writer.write_result.assert_not_called()
        s=self.service(MeasurementMode.NINE_POINT,8)
        s._publish(self.row(1,7,False))
        s.writer.write_result.assert_not_called()


if __name__=='__main__':
    unittest.main()
