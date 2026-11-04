# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest
from hmi_range04 import RangePictures, RangeFrontendProxy, RangeVisualService
from four_all_hmi_ui.hmi_single_point import MeasurementConfig, MeasurementMode

class UART:

    def __init__(self):
        self.commands = []

    def send_command(self, text):
        self.commands.append(text)

class Front:

    def __init__(self):
        self.calls = []
        self.fail = False

    def configure(self, index, **kwargs):
        self.calls.append((index, kwargs))
        if self.fail:
            raise RuntimeError('hardware failed')
        return {'range_index': index}

    def safe_off(self):
        return 'off'

class Tests(unittest.TestCase):

    def setUp(self):
        self.uart = UART()
        self.p = RangePictures(self.uart)

    def test_begin(self):
        self.p.begin()
        self.assertEqual(self.uart.commands, ['page 4'] + [f'p{i}.pic={64 + i}' for i in range(4)])

    def test_actual_switches_only(self):
        f = Front()
        o = RangeFrontendProxy(f, self.p)
        self.p.begin()
        for i in (0, 0, 1, 1, 2, 2):
            o.configure(i, enable_current=True)
        self.assertEqual([r['index'] for r in self.p.events], [0, 1, 2])
        self.assertEqual(len(self.uart.commands), 10)
        self.assertEqual(o.safe_off(), 'off')

    def test_selected(self):
        self.p.begin()
        self.p.changed(2)
        self.p.selected(1)
        self.assertEqual(self.uart.commands[-5:], ['page 5', 'p0.pic=64', 'p1.pic=69', 'p2.pic=66', 'p3.pic=67'])

    def test_polarity_no_duplicate(self):
        self.p.begin()
        f = RangeFrontendProxy(Front(), self.p)
        f.configure(1, reverse=False)
        n = len(self.uart.commands)
        f.configure(1, reverse=True)
        self.assertEqual(len(self.uart.commands), n)

    def test_failed_hardware(self):
        f = Front()
        f.fail = True
        o = RangeFrontendProxy(f, self.p)
        self.p.begin()
        with self.assertRaises(RuntimeError):
            o.configure(1)
        self.assertEqual(self.p.events, [])

    def test_current_off_ignored(self):
        self.p.begin()
        RangeFrontendProxy(Front(), self.p).configure(0, enable_current=False)
        self.assertEqual(self.p.events, [])

    def test_abort(self):

        def stop():
            raise RuntimeError('RESET')
        v = RangePictures(self.uart, abort_check=stop)
        with self.assertRaises(RuntimeError):
            v.begin()
        self.assertEqual(self.uart.commands, [])

    def test_range_validation(self):
        self.p.begin()
        for i in (-1, 4, True, 1.5):
            with self.assertRaises(ValueError):
                self.p.changed(i)

    def test_all_four_maps(self):
        self.p.begin()
        for index in range(4):
            self.p.selected(index)
            expected = ['page 5'] + [f'p{i}.pic={(68 if i == index else 64) + i}' for i in range(4)]
            self.assertEqual(self.uart.commands[-5:], expected)

    def test_r3_never_touches_hardware(self):
        f = Front()
        proxy = RangeFrontendProxy(f, self.p)
        with self.assertRaises(PermissionError):
            proxy.configure(3)
        self.assertEqual(f.calls, [])

    def test_real_configuration_params_unchanged(self):
        self.p.begin()
        f = Front()
        proxy = RangeFrontendProxy(f, self.p)
        proxy.configure(2, reverse=True, enable_current=True, timeout_s=3, reconfigure_adc_before=False)
        self.assertEqual(f.calls, [(2, dict(reverse=True, enable_current=True, timeout_s=3, reconfigure_adc_before=False))])

    def test_base_navigation_suppressed(self):
        from unittest.mock import patch
        from hmi_four_all import FourAllHmiService
        self.p.begin()
        service = object.__new__(RangeVisualService)
        service.pictures = self.p
        service.range_ready = False
        from unittest.mock import Mock
        service.writer = Mock()
        observed = []

        def base(s, *args):
            observed.append(s.range_ready)
        with patch.object(FourAllHmiService, '_range_selected', base):
            service._range_selected(1, 0.001, 0.001)
        self.assertEqual(observed, [True])
        service.writer.release_wait_page.assert_called_once()
        self.assertEqual(self.p.page, 5)

    def test_clear_old_done_before_page4(self):
        from unittest.mock import Mock, patch
        from hmi_four_all import FourAllHmiService
        import tempfile
        order = []
        service = object.__new__(RangeVisualService)
        service._validate = lambda c: None
        service.writer = Mock()
        service.writer.clear_done_flag.side_effect = lambda **k: order.append('clear')
        service.pictures = Mock()
        service.pictures.begin.side_effect = lambda: order.append('begin')
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path
            service.output_dir = Path(d)
            with patch.object(FourAllHmiService, 'run', lambda s, c: order.append('scan')):
                service.run(MeasurementConfig())
        self.assertEqual(order, ['clear', 'begin', 'scan'])

    def test_no_late_page_local_corruption(self):
        self.p.begin()
        self.p.selected(1)
        n = len(self.uart.commands)
        self.p.changed(2)
        self.assertEqual(len(self.uart.commands), n)

    def test_pl_sample_label_events(self):
        from hmi_range04 import RangePlProxy
        self.p.begin()

        class Driver:

            def __init__(self):
                self.count = 0
                self.label = 0

            def diagnostics(self):
                return dict(sample_count=self.count, last_label=self.label, last_label_valid=True)

            def run(self, mode, index, abort_check):
                for i in (0, 0, 1, 1, 2):
                    self.count += 1
                    self.label = i
                    abort_check()
                return 'done'
        result = RangePlProxy(Driver(), self.p).run(0)
        self.assertEqual(result, 'done')
        self.assertEqual([e['index'] for e in self.p.events], [0, 1, 2])

    def test_pl_abort_precedes_lights(self):
        from hmi_range04 import RangePlProxy
        self.p.begin()
        n = len(self.uart.commands)

        class Driver:

            def diagnostics(self):
                return dict(sample_count=0, last_label=2, last_label_valid=True)

            def run(self, m, i, abort_check):
                abort_check()

        def abort():
            raise RuntimeError('RESET')
        with self.assertRaises(RuntimeError):
            RangePlProxy(Driver(), self.p).run(0, abort_check=abort)
        self.assertEqual(len(self.uart.commands), n)

    def test_final_config_stays_page5(self):
        self.p.begin()
        self.p.changed(2)
        self.p.selected(1)
        n = len(self.uart.commands)
        RangeFrontendProxy(Front(), self.p).configure(1)
        self.assertEqual(len(self.uart.commands), n)
        self.assertEqual(self.p.page, 5)
if __name__ == '__main__':
    unittest.main()
