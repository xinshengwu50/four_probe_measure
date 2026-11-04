# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import json,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from hmi_emergency import EmergencyReceiver,stop_before_overlay
from four_all_hmi_ui.hmi_address import NumericPageUart
from four_probe_sw.final_four_probe_system import FinalFourProbeSystem,FinalSystemError
from test_hmi_frame42 import frame

class WireSafetyTests(unittest.TestCase):

    def receiver(self):
        clock = [0.0]
        mmio = Mock()
        mmio.read.return_value = 0
        receiver = EmergencyReceiver(mmio, monotonic=lambda: clock[0])
        return (receiver, mmio, clock)

    def test_every_truncated_start_preserves_following_rst(self):
        for size in range(1, 42):
            with self.subTest(prefix=size):
                receiver, mmio, clock = self.receiver()
                receiver.feed(frame()[:size])
                receiver.feed(b'RST\r\n')
                self.assertEqual(receiver.count, 1)
                clock[0] = 0.051
                receiver.feed(b'')
                self.assertEqual(receiver.count, 1)
                self.assertTrue(receiver.stopped.is_set())
                mmio.write.assert_called_once_with(0, 32)

    def test_valid_frames_all_splits_and_history_are_unchanged(self):
        legacy = frame()[:36] + b'\xaa'
        auto33 = legacy[:17] + legacy[21:]
        for packet in (frame(), legacy, auto33, b'\xa5HIST\x01Z', b'\xa5RPRT\x04Z', b'\xa5CLER\x00Z'):
            for split in range(1, len(packet)):
                receiver, mmio, clock = self.receiver()
                output = receiver.feed(packet[:split])
                clock[0] = 0.01
                output += receiver.feed(packet[split:])
                self.assertEqual(output, packet)
                mmio.write.assert_not_called()

    def test_binary_rst_prefix_is_not_a_stop_and_following_rst_is(self):
        receiver, mmio, _ = self.receiver()
        packet = bytearray(frame())
        packet[2:6] = b'RST\r'
        self.assertEqual(receiver.feed(packet), bytes(packet))
        mmio.write.assert_not_called()
        receiver.feed(b'RST\r\n')
        self.assertEqual(receiver.count, 1)

    def test_expired_config_cannot_consume_a_fresh_start(self):
        receiver, mmio, clock = self.receiver()
        receiver.feed(frame()[:23])
        clock[0] = 0.1
        self.assertEqual(receiver.feed(frame()), frame())
        mmio.write.assert_not_called()

    def test_idle_rx_poll_delivers_rst_held_behind_partial_start(self):
        receiver, mmio, clock = self.receiver()
        raw = Mock()
        raw.stat.return_value = 0
        raw.read_available.side_effect = [b'\xa5RST\r\n', b'']
        uart = NumericPageUart(raw)
        uart.rx_transform = receiver.feed
        uart._receive_once()
        self.assertFalse(receiver.stopped.is_set())
        clock[0] = 0.051
        uart._receive_once()
        self.assertTrue(receiver.stopped.is_set())

    def test_invalid_history_header_cannot_hide_rst(self):
        receiver, mmio, _ = self.receiver()
        self.assertEqual(receiver.feed(b'\xa5RST\r\nZ'), b'')
        self.assertEqual(receiver.count, 1)

    def test_partial_rst_survives_idle_timeout_and_parser_reset_keeps_latch(self):
        receiver, mmio, clock = self.receiver()
        receiver.feed(b'RS')
        clock[0] = 1.0
        receiver.feed(b'')
        receiver.feed(b'T\r\n')
        receiver.reset_parser()
        self.assertTrue(receiver.stopped.is_set())
        self.assertEqual(receiver.count, 1)

class HeartbeatSafetyTests(unittest.TestCase):

    def test_blocked_writer_timeout_retains_handle_and_refuses_restart(self):
        system = FinalFourProbeSystem.__new__(FinalFourProbeSystem)
        system._heartbeat_stop = threading.Event()
        system._heartbeat_thread = None
        entered, release = (threading.Event(), threading.Event())

        def blocked_write(*args):
            entered.set()
            release.wait(5.0)
        system._write = blocked_write
        thread = system.start_heartbeat(0.001)
        try:
            self.assertTrue(entered.wait(1.0))
            with self.assertRaisesRegex(FinalSystemError, 'did not stop'):
                system.stop_heartbeat(join=True, timeout_s=0.001)
            self.assertIs(system._heartbeat_thread, thread)
            self.assertTrue(system.heartbeat_is_running())
            system.stop_heartbeat(join=False)
            self.assertIs(system._heartbeat_thread, thread)
            with self.assertRaisesRegex(FinalSystemError, 'still stopping'):
                system.start_heartbeat()
        finally:
            release.set()
            system.stop_heartbeat(join=True)
        self.assertIsNone(system._heartbeat_thread)
        self.assertFalse(thread.is_alive())

    def test_cleanup_timeout_does_not_read_mmio_or_disarm_watchdog(self):
        system = FinalFourProbeSystem.__new__(FinalFourProbeSystem)
        system._heartbeat_stop = threading.Event()
        thread = Mock()
        thread.is_alive.return_value = True
        system._heartbeat_thread = thread
        system._read, system._write = (Mock(), Mock())
        system.frontend = Mock()
        result = system.finish_safety_cleanup()
        self.assertFalse(result['heartbeat_stopped'])
        self.assertTrue(result['watchdog_left_armed'])
        self.assertIn('did not stop', result['error'])
        self.assertIs(system._heartbeat_thread, thread)
        system._read.assert_not_called()
        system._write.assert_not_called()

class OverlaySafetyTests(unittest.TestCase):

    def source(self):
        notebook = json.loads((next(p/'board/pynq' for p in Path(__file__).resolve().parents if (p/'board/pynq/01_four_all_system.ipynb').is_file()) / '01_four_all_system.ipynb').read_text(encoding='utf-8'))
        return next((''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code' and ''.join(cell['source']).startswith('def find_overlay_pair')))

    def namespace(self, uart):
        mmio = Mock()
        mmio.read.return_value = 0
        frontend = Mock()
        frontend.status.return_value = {'current_active': False}
        return dict(ROOT=next(p/'board/pynq' for p in Path(__file__).resolve().parents if (p/'board/pynq/01_four_all_system.ipynb').is_file()), MODULE_ROOT=next(p/'board/pynq' for p in Path(__file__).resolve().parents if (p/'board/pynq/01_four_all_system.ipynb').is_file()), mmio=mmio, frontend=frontend, uart=uart, emergency=SimpleNamespace(stopped=threading.Event()), check_deploy_manifest=Mock(), Overlay=Mock())

    def test_actual_notebook_refuses_download_with_old_rx_alive(self):
        uart = Mock()
        uart._rx_thread.is_alive.return_value = True
        namespace = self.namespace(uart)
        with self.assertRaisesRegex(RuntimeError, 'RX thread failed'):
            exec(self.source(), namespace)
        namespace['Overlay'].assert_not_called()
        namespace['check_deploy_manifest'].assert_not_called()

    def test_actual_notebook_download_only_after_successful_stop(self):
        uart = SimpleNamespace(_rx_thread=Mock())
        uart.stop_receiving = lambda: setattr(uart, '_rx_thread', None)
        namespace = self.namespace(uart)

        class BeforeHardware(Exception):
            pass
        namespace['Overlay'].side_effect = BeforeHardware
        with self.assertRaises(BeforeHardware):
            exec(self.source(), namespace)
        namespace['Overlay'].assert_called_once()
        self.assertIsNone(uart._rx_thread)

    def test_rst_during_thread_stop_is_rechecked_before_download(self):
        uart = SimpleNamespace(_rx_thread=None)
        namespace = self.namespace(uart)
        uart.stop_receiving = namespace['emergency'].stopped.set
        with self.assertRaisesRegex(RuntimeError, '急停'):
            exec(self.source(), namespace)
        namespace['Overlay'].assert_not_called()
