# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Minimal reset interface for external front-ends (e.g. a serial screen).

This module deliberately does not import FinalFourProbeSystem: whoever drives the
TJC screen only needs an MMIO object and these four calls.

Register contract (PL ALL_Final):
  0x00 CONTROL bit5 (W) SYSTEM_RESET  -> current off, latches set, no axis moves
  0x00 CONTROL bit6 (W) CLEAR_FAULTS  -> clear reset/watchdog latches
  0x04 STATUS  bit16 (R) reset_latched
  0x04 STATUS  bit17 (R) watchdog_tripped
  0xFC HEARTBEAT      (W) must be written at least once per second
"""

REG_CONTROL = 0x00
REG_STATUS = 0x04
REG_HEARTBEAT = 0xFC

CONTROL_SYSTEM_RESET = 1 << 5
CONTROL_CLEAR_FAULTS = 1 << 6

STATUS_RESET_LATCHED = 1 << 16
STATUS_WATCHDOG_TRIPPED = 1 << 17


def request_reset(mmio):
    """Immediately stop the excitation current and latch a reset request."""
    mmio.write(REG_CONTROL, CONTROL_SYSTEM_RESET)
    return is_reset_latched(mmio)


def is_reset_latched(mmio):
    return bool(int(mmio.read(REG_STATUS)) & STATUS_RESET_LATCHED)


def is_watchdog_tripped(mmio):
    return bool(int(mmio.read(REG_STATUS)) & STATUS_WATCHDOG_TRIPPED)


def clear_faults(mmio):
    """Clear the latches. Call only after the fixture has been checked by hand."""
    mmio.write(REG_CONTROL, CONTROL_CLEAR_FAULTS)
    return int(mmio.read(REG_STATUS))


def kick_watchdog(mmio):
    mmio.write(REG_HEARTBEAT, 1)
