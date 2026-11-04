# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest, json, ast
from pathlib import Path

class Regression(unittest.TestCase):

    def test_recovery_notebook_does_not_use_measurement_factory(self):
        n = json.loads((next(p/'board/pynq' for p in Path(__file__).resolve().parents if (p/'board/pynq/01_four_all_system.ipynb').is_file()) / '01_four_all_system.ipynb').read_text(encoding='utf-8'))
        code = next((''.join(c['source']) for c in n['cells'] if 'MANUAL_CLEAR_AND_REHOME =' in ''.join(c['source'])))
        self.assertNotIn('factory(MeasurementConfig())', code)
from types import SimpleNamespace as NS
from unittest.mock import Mock
import threading
import four_probe_sw.final_four_probe_system as fs
from hmi_emergency import EmergencyReceiver
from hmi_recovery import MechanicalRecoveryController, manual_clear_and_rehome
MECHANICS = dict(r_home_to_center_steps=8000, r_ring_spacing_steps=3500, r_max_steps=40000, x_pulses_per_rev=12000, full_down_steps=7600, half_up_steps=3800, z_timeout_s=0.05, r_timeout_s=0.05, x_timeout_s=0.05, z_run_step_cycles=6000, z_end_step_cycles=96000, z_decel_window_steps=500, z_decel_seg_steps=31, z_decel_segments=16, z_rehome_interval_points=5, poll_interval_s=0.0001)

class MMIO:

    def __init__(self):
        self.regs = {fs.REG_STATUS: 1 << 16, fs.REG_VERSION: fs.EXPECTED_PL_VERSION, fs.REG_Z_POSITION: 100, fs.REG_R_POSITION: 200}
        self.writes = []
        self.homes = []
        self.armed = False
        self.on_home = None
        self.fail_r = False

    def read(self, offset):
        if offset == fs.REG_Z_CONTROL:
            return fs.Z_CONTROL_ARMED_BIT if self.armed else 0
        return self.regs.get(offset, 0)

    def write(self, offset, value):
        self.writes.append((offset, value))
        if offset == fs.REG_CONTROL:
            if value & 1 << 6:
                self.regs[fs.REG_STATUS] = 0
            if value & 1 << 5:
                self.regs[fs.REG_STATUS] = 1 << 16
        elif offset == fs.REG_Z_CONTROL:
            if value & fs.Z_CONTROL_ARM:
                self.armed = True
            if value == 1 and self.regs.get(fs.REG_Z_COMMAND) == fs.AXIS_CMD_HOME:
                self.homes.append('Z')
                self.regs[fs.REG_Z_STATUS] = fs.AXIS_STATUS_DONE | fs.AXIS_STATUS_AT_HOME | fs.AXIS_STATUS_HOMED
                self.regs[fs.REG_Z_POSITION] = 0
                if self.on_home:
                    self.on_home('Z')
        elif offset == fs.REG_R_CONTROL:
            if value == 1 and self.regs.get(fs.REG_R_COMMAND) == fs.AXIS_CMD_HOME:
                self.homes.append('R')
                self.regs[fs.REG_R_STATUS] = fs.AXIS_STATUS_FAULT if self.fail_r else fs.AXIS_STATUS_DONE | fs.AXIS_STATUS_AT_HOME | fs.AXIS_STATUS_HOMED
                self.regs[fs.REG_R_POSITION] = 0 if not self.fail_r else 10
                if self.on_home:
                    self.on_home('R')
        else:
            self.regs[offset] = value

class Frontend:

    def __init__(self):
        self.active = False
        self.off = 0

    def status(self):
        return dict(current_active=self.active)

    def safe_off(self):
        self.active = False
        self.off += 1
        return self.status()

    def configure(self, *args, **kwargs):
        raise AssertionError('Recovery must not select ranges')

    def reconfigure_adc(self, *args, **kwargs):
        raise AssertionError('Recovery must not configure ADC')

class UART:

    def __init__(self, em):
        self.running = True
        self._rx_thread = NS(is_alive=lambda: self.running)
        self.rx_transform = em.feed
        self.rx_fatal_error = None
        self.starts = 0
        self.stops = 0
        self.discards = 0
        self.rx_error_count = 187
        self.image_transport_needs_check = True
        self.lock = threading.Lock()

    def start_receiving(self, **kwargs):
        self.starts += 1
        self.running = True

    def stop_receiving(self):
        self.stops += 1
        self.running = False

    def discard_pending_rx(self):
        self.discards += 1

class RecoveryTests(unittest.TestCase):

    def setup_case(self):
        m = MMIO()
        f = Frontend()
        em = EmergencyReceiver(m)
        em.stopped.set()
        u = UART(em)
        c = MechanicalRecoveryController(m, f, **MECHANICS)
        return (m, f, em, u, c)

    def run_recovery(self, c, u, em, **kwargs):
        return manual_clear_and_rehome(c, u, em, confirmed=True, **kwargs)

    def test_constructor_pure_and_measurement_apis_disabled(self):
        m, f, em, u, c = self.setup_case()
        self.assertFalse(m.writes)
        self.assertIsNone(c.monitor)
        self.assertIsNone(c.pl_autorange)
        self.assertIsNone(c.pl_calc)
        self.assertIsNone(c.window_stats)
        for fn in [lambda: c.run_scan('single', 1), lambda: c.save_results('.'), lambda: c.clear_faults(), lambda: c.rehome()]:
            with self.assertRaises((RuntimeError, PermissionError)):
                fn()
        self.assertFalse(m.writes)

    def test_actual_core_z_r_home_and_rx_preserved(self):
        m, f, em, u, c = self.setup_case()
        self.assertIs(self.run_recovery(c, u, em), c)
        self.assertEqual(m.homes, ['Z', 'R'])
        self.assertFalse(em.stopped.is_set())
        self.assertFalse(m.read(fs.REG_STATUS) & 196608)
        self.assertEqual(u.stops, 0)
        self.assertTrue(u.running)
        self.assertEqual(u.rx_error_count, 187)
        self.assertTrue(u.image_transport_needs_check)
        self.assertFalse(c.heartbeat_is_running())
        self.assertNotIn(fs.REG_X_CONTROL, [a for a, v in m.writes])
        self.assertFalse(f.active)

    def test_unconfirmed_or_busy_or_current_on_never_clear(self):
        for kind in ('confirm', 'busy', 'current'):
            m, f, em, u, c = self.setup_case()
            if kind == 'busy':
                m.regs[fs.REG_X_STATUS] = 1
            if kind == 'current':
                f.active = True
            with self.assertRaises((PermissionError, RuntimeError)):
                manual_clear_and_rehome(c, u, em, confirmed=kind != 'confirm')
            self.assertFalse(m.writes)
            self.assertTrue(em.stopped.is_set())

    def test_stuck_heartbeat_refuses_clear_keeps_rx(self):
        m, f, em, u, c = self.setup_case()
        old = Mock()
        old.stop_heartbeat.side_effect = RuntimeError('still stopping')
        with self.assertRaisesRegex(RuntimeError, 'stopping'):
            self.run_recovery(c, u, em, previous_systems=(old,))
        self.assertFalse(m.writes)
        self.assertEqual(u.stops, 0)
        self.assertTrue(u.running)

    def test_new_rst_during_homing_is_not_cleared(self):
        m, f, em, u, c = self.setup_case()
        m.on_home = lambda axis: em.feed(b'RST\r\n')
        with self.assertRaises(fs.MeasurementAbortedError):
            self.run_recovery(c, u, em)
        self.assertTrue(em.stopped.is_set())
        self.assertTrue(m.read(fs.REG_STATUS) & 1 << 16)
        self.assertEqual(m.homes, ['Z'])
        self.assertEqual(u.stops, 0)
        self.assertFalse(c.heartbeat_is_running())

    def test_failed_r_home_re_latches_without_x_or_retries(self):
        m, f, em, u, c = self.setup_case()
        m.fail_r = True
        with self.assertRaises(fs.FinalSystemError):
            self.run_recovery(c, u, em)
        self.assertEqual(m.homes, ['Z', 'R'])
        self.assertTrue(em.stopped.is_set())
        self.assertTrue(m.read(fs.REG_STATUS) & 1 << 16)
        self.assertEqual(u.stops, 0)
        self.assertFalse(c.heartbeat_is_running())

    def test_rx_loss_during_home_aborts_and_latches(self):
        m, f, em, u, c = self.setup_case()
        m.on_home = lambda axis: setattr(u, 'running', False)
        with self.assertRaisesRegex(RuntimeError, 'RX'):
            self.run_recovery(c, u, em)
        self.assertTrue(em.stopped.is_set())
        self.assertTrue(m.read(fs.REG_STATUS) & 1 << 16)
        self.assertEqual(m.homes, ['Z'])

    def test_old_rx_stopped_by_failed_cell_is_restarted(self):
        m, f, em, u, c = self.setup_case()
        u.running = False
        self.run_recovery(c, u, em)
        self.assertTrue(u.running)
        self.assertGreater(u.starts, 0)
        self.assertEqual(u.stops, 0)

    def test_partial_rst_refuses_clear_without_discarding_parser(self):
        m, f, em, u, c = self.setup_case()
        em.feed(b'RS')
        with self.assertRaisesRegex(RuntimeError, 'Partial'):
            self.run_recovery(c, u, em)
        self.assertEqual(bytes(em.buffer), b'RS')
        self.assertFalse(m.writes)

    def test_bad_rx_route_or_fatal_error_refuses(self):
        for kind in ('route', 'fatal'):
            m, f, em, u, c = self.setup_case()
            if kind == 'route':
                u.rx_transform = lambda b: b
            else:
                u.rx_fatal_error = 'RX thread stopped'
            with self.assertRaises(RuntimeError):
                self.run_recovery(c, u, em)
            self.assertFalse(m.writes)

    def test_tx_owned_or_fp_dsp_stuck_refuses_clear(self):
        m, f, em, u, c = self.setup_case()
        u.lock.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, 'TX'):
                self.run_recovery(c, u, em)
        finally:
            u.lock.release()
        self.assertFalse(m.writes)
        driver = Mock()
        driver.wait_idle.side_effect = RuntimeError('FP_DSP stuck')
        with self.assertRaisesRegex(RuntimeError, 'stuck'):
            self.run_recovery(c, u, em, pl_autorange=driver)
        driver.release.assert_not_called()
        self.assertFalse(m.writes)
        self.assertTrue(u.running)

    def test_wrong_overlay_is_read_only_refusal(self):
        m, f, em, u, c = self.setup_case()
        m.regs[fs.REG_VERSION] = 0
        with self.assertRaisesRegex(RuntimeError, 'VERSION'):
            self.run_recovery(c, u, em)
        self.assertFalse(m.writes)

    def test_new_rst_while_stopping_old_workers_prevents_clear(self):
        m, f, em, u, c = self.setup_case()
        old = Mock()
        old.stop_heartbeat.side_effect = lambda **kwargs: em.feed(b'RST\r\n')
        old.heartbeat_is_running.return_value = False
        with self.assertRaises(fs.MeasurementAbortedError):
            self.run_recovery(c, u, em, previous_systems=(old,))
        self.assertNotIn((fs.REG_CONTROL, 1 << 6), m.writes)
        self.assertFalse(m.homes)
        self.assertTrue(em.stopped.is_set())
        self.assertEqual(u.stops, 0)

    def test_keyboard_interrupt_during_home_holds_fault(self):
        m, f, em, u, c = self.setup_case()

        def interrupt(axis):
            raise KeyboardInterrupt()
        m.on_home = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_recovery(c, u, em)
        self.assertTrue(m.read(fs.REG_STATUS) & 1 << 16)
        self.assertTrue(em.stopped.is_set())
        self.assertEqual(u.stops, 0)
        self.assertFalse(c.heartbeat_is_running())

    def test_old_matching_system_pl_owner_released_even_if_global_is_none(self):
        m, f, em, u, c = self.setup_case()
        driver = Mock()
        previous = NS(mmio=m, pl_autorange=driver, stop_heartbeat=lambda **kwargs: None, heartbeat_is_running=lambda: False)
        self.run_recovery(c, u, em, previous_systems=(previous,))
        driver.abort.assert_called_once()
        driver.wait_idle.assert_called_once()
        driver.release.assert_called_once()
        self.assertEqual(m.homes, ['Z', 'R'])

    def test_stopping_rx_or_changed_route_is_not_treated_healthy(self):
        m, f, em, u, c = self.setup_case()
        u._rx_stop = threading.Event()
        u._rx_stop.set()
        with self.assertRaisesRegex(RuntimeError, 'RX'):
            self.run_recovery(c, u, em)
        self.assertFalse(m.writes)
        m, f, em, u, c = self.setup_case()
        m.on_home = lambda axis: setattr(u, 'rx_transform', lambda b: b)
        with self.assertRaisesRegex(RuntimeError, 'RX'):
            self.run_recovery(c, u, em)
        self.assertTrue(em.stopped.is_set())
        self.assertTrue(m.read(fs.REG_STATUS) & 1 << 16)
if __name__ == '__main__':
    unittest.main()
