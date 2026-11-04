# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""PYNQ driver for the custom relay current-source frontend.

The PL owns relay sequencing and DAC serialization.  Python only writes
high-level commands and waits for the corresponding status/sequence bits.
All register offsets are relative to the ALL_Final AXI-Lite base address.
"""
from __future__ import annotations
import math
import time
from typing import Dict, Optional
REG_CONTROL = 0
REG_ADC_CFG_SEQ = 236
REG_ANALOG_CONTROL = 208
REG_ANALOG_TEST_CONTROL = 212
REG_DAC_CODE = 216
REG_DAC_CONTROL = 220
REG_DAC_STATUS = 224
REG_DAC_SEQ = 228
REG_ANALOG_SEQ = 232
CONTROL_ADC_REINIT = 1 << 4
ANALOG_CTRL_START = 1 << 0
ANALOG_CTRL_ABORT = 1 << 1
ANALOG_CTRL_CURRENT_ENABLE = 1 << 2
ANALOG_CTRL_RANGE_SHIFT = 3
ANALOG_CTRL_POLARITY = 1 << 5
ANALOG_STATUS_BUSY = 1 << 0
ANALOG_STATUS_DONE = 1 << 1
ANALOG_STATUS_ERROR = 1 << 2
ANALOG_STATUS_STATE_MASK = 7
ANALOG_STATUS_STATE_SHIFT = 8
TEST_ENABLE = 1 << 31
TEST_CURRENT_ENABLE = 1 << 8
TEST_RELAY_MASK = 63
TEST_RANGE_MASK = 15
DAC_CONTROL_START = 1 << 0
DAC_CONTROL_ABORT = 1 << 1
DAC_STATUS_BUSY = 1 << 0
DAC_STATUS_DONE = 1 << 1
DAC_STATUS_CODE_LOADED = 1 << 2
DAC_REFERENCE_V = 2.5
DAC_MAX_CODE = 65535
DAC_WRITE_UPDATE_A = 1572864
RANGE_CURRENT_LABELS = ('0.1mA/100uA', '1mA', '10mA', '100mA')
RANGE_FEEDBACK_OHM = (10000.0, 1000.0, 100.0, 10.0)
ANALOG_STATE_NAMES = {0: 'IDLE', 1: 'WAIT_SAFE', 2: 'WAIT_READY', 3: 'ACTIVE'}

class AnalogFrontendError(RuntimeError):
    """Raised when the PL-controlled analog frontend does not complete."""

def validate_range_index(range_index: int) -> int:
    range_index = int(range_index)
    if range_index < 0 or range_index >= len(RANGE_FEEDBACK_OHM):
        raise ValueError('range_index must be 0, 1, 2 or 3')
    return range_index

def voltage_to_dac_code(voltage_v: float) -> int:
    """Convert a desired VSET voltage to a straight-binary DAC8562 code."""
    voltage_v = float(voltage_v)
    if not math.isfinite(voltage_v):
        raise ValueError('voltage must be finite')
    if voltage_v < 0.0 or voltage_v > DAC_REFERENCE_V:
        raise ValueError('voltage must be within 0.0..2.5 V')
    return int(round(voltage_v * DAC_MAX_CODE / DAC_REFERENCE_V))

def dac_code_to_voltage(code: int) -> float:
    code = int(code)
    if code < 0 or code > DAC_MAX_CODE:
        raise ValueError('DAC code must be within 0..65535')
    return code * DAC_REFERENCE_V / DAC_MAX_CODE

def expected_current_a(voltage_v: float, range_index: int) -> float:
    range_index = validate_range_index(range_index)
    voltage_v = float(voltage_v)
    if not math.isfinite(voltage_v) or voltage_v < 0.0:
        raise ValueError('voltage must be finite and non-negative')
    return voltage_v / RANGE_FEEDBACK_OHM[range_index]

def _bit_count(value: int) -> int:
    return bin(int(value) & 4294967295).count('1')

class AnalogFrontendController:
    """Small register-level controller used by notebooks and bring-up scripts."""

    def __init__(self, mmio, timeout_s: float=1.0):
        self.mmio = mmio
        self.timeout_s = float(timeout_s)
        if self.timeout_s <= 0.0:
            raise ValueError('timeout_s must be positive')
        self._range_index = 0
        self._reverse = False
        self._current_enabled = False
        self._direct_test = False

    def read(self, offset: int) -> int:
        return int(self.mmio.read(int(offset))) & 4294967295

    def write(self, offset: int, value: int) -> None:
        self.mmio.write(int(offset), int(value) & 4294967295)

    def status(self) -> Dict[str, object]:
        value = self.read(REG_ANALOG_CONTROL)
        return {'raw': value, 'busy': bool(value & ANALOG_STATUS_BUSY), 'done': bool(value & ANALOG_STATUS_DONE), 'error': bool(value & ANALOG_STATUS_ERROR), 'state': value >> ANALOG_STATUS_STATE_SHIFT & ANALOG_STATUS_STATE_MASK, 'state_name': ANALOG_STATE_NAMES.get(value >> ANALOG_STATUS_STATE_SHIFT & ANALOG_STATUS_STATE_MASK, 'UNKNOWN'), 'range_index': value >> ANALOG_CTRL_RANGE_SHIFT & 3, 'polarity_reversed': bool(value & ANALOG_CTRL_POLARITY), 'current_requested': bool(value & ANALOG_CTRL_CURRENT_ENABLE), 'current_active': bool(value & 1 << 7), 'direct_test': self._direct_test}

    def safe_off(self) -> Dict[str, object]:
        """Disable current immediately, release both polarity relays and ranges."""
        self.write(REG_ANALOG_CONTROL, ANALOG_CTRL_ABORT)
        self._range_index = 0
        self._reverse = False
        self._current_enabled = False
        self._direct_test = False
        return self.status()

    def _wait_analog_complete(self, seq_before: int, timeout_s: Optional[float]=None) -> Dict[str, object]:
        timeout = self.timeout_s if timeout_s is None else float(timeout_s)
        if timeout <= 0.0:
            raise ValueError('timeout must be positive')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.status()
            if status['error']:
                raise AnalogFrontendError(f'PL analog sequence error: {status}')
            if self.read(REG_ANALOG_SEQ) & 65535 != seq_before:
                return status
            time.sleep(0.0005)
        raise AnalogFrontendError(f'PL analog sequence timeout: {self.status()}')

    def reconfigure_adc(self, timeout_s: Optional[float]=None) -> int:
        """Restart the ADS8681 configuration sequence and wait for completion."""
        timeout = self.timeout_s if timeout_s is None else float(timeout_s)
        if timeout <= 0.0:
            raise ValueError('timeout must be positive')
        seq_before = self.read(REG_ADC_CFG_SEQ) & 65535
        self.write(REG_CONTROL, CONTROL_ADC_REINIT)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            seq_after = self.read(REG_ADC_CFG_SEQ) & 65535
            if seq_after != seq_before:
                return seq_after
            time.sleep(0.0005)
        raise AnalogFrontendError(f'ADC configuration sequence timeout: seq={seq_before}')

    def configure(self, range_index: int, reverse: bool=False, enable_current: bool=True, timeout_s: Optional[float]=None, reconfigure_adc_before: bool=True) -> Dict[str, object]:
        """Apply a complete state through the PL's safe relay sequence."""
        range_index = validate_range_index(range_index)
        command = ANALOG_CTRL_START | range_index << ANALOG_CTRL_RANGE_SHIFT | (ANALOG_CTRL_POLARITY if reverse else 0) | (ANALOG_CTRL_CURRENT_ENABLE if enable_current else 0)
        self._direct_test = False
        if reconfigure_adc_before:
            self.reconfigure_adc(timeout_s=timeout_s)
        seq_before = self.read(REG_ANALOG_SEQ) & 65535
        self.write(REG_ANALOG_CONTROL, command)
        status = self._wait_analog_complete(seq_before, timeout_s)
        self._range_index = range_index
        self._reverse = bool(reverse)
        self._current_enabled = bool(enable_current)
        return status

    def select_range(self, range_index: int, timeout_s: Optional[float]=None) -> Dict[str, object]:
        return self.configure(range_index, self._reverse, self._current_enabled, timeout_s)

    def set_polarity(self, reverse: bool, timeout_s: Optional[float]=None) -> Dict[str, object]:
        return self.configure(self._range_index, reverse, self._current_enabled, timeout_s)

    def enable_current(self, enabled: bool, timeout_s: Optional[float]=None) -> Dict[str, object]:
        return self.configure(self._range_index, self._reverse, enabled, timeout_s)

    def set_dac_code(self, code: int, timeout_s: Optional[float]=None) -> int:
        code = int(code)
        if code < 0 or code > DAC_MAX_CODE:
            raise ValueError('DAC code must be within 0..65535')
        timeout = self.timeout_s if timeout_s is None else float(timeout_s)
        if timeout <= 0.0:
            raise ValueError('timeout must be positive')
        seq_before = self.read(REG_DAC_SEQ) & 65535
        self.write(REG_DAC_CODE, code)
        self.write(REG_DAC_CONTROL, DAC_CONTROL_START)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.read(REG_DAC_SEQ) & 65535 != seq_before:
                return code
            time.sleep(0.0005)
        raise AnalogFrontendError(f'DAC sequence timeout: status=0x{self.read(REG_DAC_STATUS):08X}')

    def set_dac_voltage(self, voltage_v: float, timeout_s: Optional[float]=None) -> int:
        return self.set_dac_code(voltage_to_dac_code(voltage_v), timeout_s)

    def dac_status(self) -> Dict[str, int]:
        value = self.read(REG_DAC_STATUS)
        return {'raw': value, 'busy': int(bool(value & DAC_STATUS_BUSY)), 'done': int(bool(value & DAC_STATUS_DONE)), 'code_loaded': int(bool(value & DAC_STATUS_CODE_LOADED)), 'sequence': self.read(REG_DAC_SEQ) & 65535}

    def enter_direct_test(self, relay_mask: int=0, pol_i: bool=False, pol_v: bool=False, enable_current: bool=False) -> Dict[str, object]:
        relay_mask = int(relay_mask) & TEST_RELAY_MASK
        range_mask = relay_mask & TEST_RANGE_MASK
        if _bit_count(range_mask) > 1:
            raise ValueError('range relays must be one-hot or all zero')
        if enable_current and _bit_count(range_mask) != 1:
            raise ValueError('current enable in test mode requires exactly one range relay')
        value = TEST_ENABLE | relay_mask | (TEST_CURRENT_ENABLE if enable_current else 0)
        if pol_i:
            value |= 1 << 4
        if pol_v:
            value |= 1 << 5
        self.write(REG_ANALOG_TEST_CONTROL, value)
        time.sleep(0.001)
        status = self.status()
        if status['error']:
            raise AnalogFrontendError(f'test mode rejected state: {status}')
        self._direct_test = True
        return status

    def exit_direct_test(self) -> Dict[str, object]:
        self.write(REG_ANALOG_TEST_CONTROL, 0)
        self._direct_test = False
        return self.status()

    def set_test_current(self, enabled: bool) -> Dict[str, object]:
        if not self._direct_test:
            raise AnalogFrontendError('enter_direct_test() must be called first')
        if not enabled:
            return self.exit_direct_test()
        return self.enter_direct_test(relay_mask=1 << self._range_index, pol_i=self._reverse, pol_v=self._reverse, enable_current=True)
