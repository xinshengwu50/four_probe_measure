# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Single RX owner: validate frames before consuming them and preserve RST."""
import math
import threading
import time

from four_all_hmi_ui.hmi_wire import config_frame_length, split_config_frame
from system_reset import request_reset


class EmergencyReceiver:
    def __init__(self, mmio, *, frame_timeout_s=0.05, monotonic=time.monotonic):
        frame_timeout_s = float(frame_timeout_s)
        if not math.isfinite(frame_timeout_s) or frame_timeout_s <= 0:
            raise ValueError('frame_timeout_s must be finite and positive')
        self.mmio = mmio
        self.buffer = bytearray()
        self.stopped = threading.Event()
        self.count = 0
        self.frame_timeout_s = frame_timeout_s
        self._monotonic = monotonic
        self._last_data_at = None

    def request(self, reason='screen'):
        self.stopped.set()
        request_reset(self.mmio)
        self.count += 1

    def reset_parser(self, reason=None):
        """Discard damaged input without clearing any PS/PL stop latch."""
        self.buffer.clear()
        self._last_data_at = None

    def _drain(self, out, expired=False):
        while self.buffer:
            if self.buffer[0] == 0xAA:
                size = config_frame_length(self.buffer)
                if size == 0:
                    del self.buffer[0]
                    continue
                if size is None or len(self.buffer) < size:
                    if not expired:
                        break
                    del self.buffer[0]
                    continue
                try:
                    split_config_frame(self.buffer[:size])
                except ValueError:
                    # A truncated START plus RST is not a valid config frame.
                    # Resynchronise one byte at a time so the RST is revisited.
                    del self.buffer[0]
                    continue
            elif self.buffer[0] == 0xA5:
                size = 7
                if len(self.buffer) < size:
                    if not expired:
                        break
                    del self.buffer[0]
                    continue
                if (self.buffer[1:5] not in (b'HIST', b'RPRT', b'CLER')
                        or self.buffer[6] != 0x5A):
                    del self.buffer[0]
                    continue
            elif self.buffer[0] == ord('R'):
                prefix = b'RST\r\n'
                n = min(len(self.buffer), len(prefix))
                if bytes(self.buffer[:n]) != prefix[:n]:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < len(prefix):
                    break  # Preserve partial RST across RX polls, including idle polls.
                del self.buffer[:len(prefix)]
                self.request()
                continue
            else:
                del self.buffer[0]
                continue
            out.extend(self.buffer[:size])
            del self.buffer[:size]

    def feed(self, data):
        now = self._monotonic()
        out = bytearray()
        if (self.buffer and self._last_data_at is not None
                and now - self._last_data_at >= self.frame_timeout_s):
            # Drain expired bytes BEFORE appending a new frame. Idle RX polls also
            # call feed(b''), so a held RST does not require another screen event.
            self._drain(out, expired=True)
        if data:
            self.buffer.extend(data)
            self._last_data_at = now
        self._drain(out)
        return bytes(out)


def stop_before_overlay(*, uart=None, systems=()):
    """Stop old runtime threads; refuse reconfiguration if any owner survives.

    The caller checks idle/current/fault state separately. Keep the RX owner
    running if an earlier worker cannot stop, so RST reception remains available.
    """
    seen = set()
    for system in systems:
        if system is None or id(system) in seen:
            continue
        seen.add(id(system))
        system.stop_heartbeat(join=True)
        if system.heartbeat_is_running():
            raise RuntimeError('Heartbeat thread failed to stop; Overlay download refused')
    if uart is not None:
        uart.stop_receiving()
        thread = uart._rx_thread
        if thread is not None and thread.is_alive():
            raise RuntimeError('RX thread failed to stop; Overlay download refused')
