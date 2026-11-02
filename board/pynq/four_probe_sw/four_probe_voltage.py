# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Direct four-probe voltage measurement through the PL ADC window.

The external ADS8681 is assumed to be configured for the bipolar +/-5.12 V
range. The custom analog board adds a 2.5 V common-mode offset before the ADC:

    ADC_IN = 2.5 V + (P2 - P3)

Therefore the real probe differential voltage is:

    V_probe = V_ADC - 2.5 V
"""
from __future__ import annotations
import math
import statistics
import time
from dataclasses import dataclass
from typing import Optional
try:
    from .analog_frontend import AnalogFrontendController
    from .adc_voltage_map import ADC_FULL_SCALE_V, ADC_CODE_MID
except ImportError:
    from analog_frontend import AnalogFrontendController
    from adc_voltage_map import ADC_FULL_SCALE_V, ADC_CODE_MID
REG_WINDOW_SUM_LOW = 128
REG_WINDOW_SUM_HIGH = 132
REG_WINDOW_COUNT = 136
REG_WINDOW_SEQ = 140
REG_WINDOW_FLAGS = 144
REG_WINDOW_CONTROL = 156
WINDOW_RESET = 1 << 0
WINDOW_ENABLE = 1 << 1
WINDOW_ACK = 1 << 2
WINDOW_DISABLE = 1 << 3
DEFAULT_RELAY_SETTLE_S = 1.0
ADC_FRONTEND_OFFSET_V = 2.5
ADC_LSB_V = ADC_FULL_SCALE_V / ADC_CODE_MID
DEFAULT_ADC_ZERO_OFFSET_BY_RANGE_V = (0.06234375, 0.0625, 0.06234375, 0.0621875)
DEFAULT_CALIBRATED_CURRENT_BY_RANGE_A = (0.00010414878494341161, 0.0009804688214200066, 0.009762569832402233, 0.08806424777437424)
DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V = (-0.000608771971007042, 9.523915436486045e-05, 0.0008907877094972427, 0.0)
MAGNITUDE_MODE_ABS = 'straight_binary_abs'
MAGNITUDE_MODE_RESTORE_MSB = 'restore_msb'

@dataclass(frozen=True)
class FourProbeMeasurement:
    range_index: int
    reverse: bool
    current_a: float
    average_code: float
    adc_voltage_v: float
    probe_voltage_v: float
    resistance_ohm: Optional[float]

def adc_code_to_voltage_v(code: float) -> float:
    return (float(code) - float(ADC_CODE_MID)) * ADC_LSB_V

def adc_voltage_to_probe_voltage_v(adc_voltage_v: float) -> float:
    return float(adc_voltage_v) - ADC_FRONTEND_OFFSET_V

def adc_code_to_magnitude_voltage_v(code: int, mode: str=MAGNITUDE_MODE_ABS) -> float:
    """Convert straight-binary code to positive ADC-side magnitude."""
    code = int(round(code)) & 65535
    if mode == MAGNITUDE_MODE_ABS:
        code_abs = min(65535, ADC_CODE_MID + abs(code - ADC_CODE_MID))
    elif mode == MAGNITUDE_MODE_RESTORE_MSB:
        code_abs = code | ADC_CODE_MID if code < ADC_CODE_MID else code
    else:
        raise ValueError(f'unsupported magnitude mode: {mode!r}')
    return adc_code_to_voltage_v(code_abs)

def adc_voltage_to_probe_magnitude_v(adc_voltage_v: float) -> float:
    return abs(float(adc_voltage_v) - ADC_FRONTEND_OFFSET_V)

def correct_adc_zero_offset_v(adc_voltage_v: float, zero_offset_v: float) -> float:
    """Apply a measured ADC-side zero offset before frontend conversion."""
    return float(adc_voltage_v) - float(zero_offset_v)

def _validate_settle_s(settle_s: float) -> float:
    settle_s = float(settle_s)
    if settle_s < 0.0:
        raise ValueError('settle_s must be non-negative')
    return settle_s

def _validate_zero_offsets_v(zero_offsets_v) -> tuple:
    values = tuple((float(value) for value in zero_offsets_v))
    if len(values) != 4:
        raise ValueError('zero_offsets_v must contain four range offsets')
    if any((not math.isfinite(value) for value in values)):
        raise ValueError('zero_offsets_v values must be finite')
    return values

def _validate_range_table(values, name: str) -> tuple:
    values = tuple((float(value) for value in values))
    if len(values) != 4:
        raise ValueError(f'{name} must contain four range values')
    if any((not math.isfinite(value) for value in values)):
        raise ValueError(f'{name} values must be finite')
    return values

def calibrated_current_for_range_a(range_index: int) -> float:
    range_index = int(range_index)
    if range_index < 0 or range_index >= len(DEFAULT_CALIBRATED_CURRENT_BY_RANGE_A):
        raise ValueError('range_index must be 0, 1, 2 or 3')
    return DEFAULT_CALIBRATED_CURRENT_BY_RANGE_A[range_index]

def calibrated_probe_voltage_v(probe_voltage_v: float, range_index: int) -> float:
    range_index = int(range_index)
    if range_index < 0 or range_index >= len(DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V):
        raise ValueError('range_index must be 0, 1, 2 or 3')
    return float(probe_voltage_v) - DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V[range_index]

def calibrated_resistance_ohm(probe_voltage_v: float, range_index: int) -> float:
    current_a = calibrated_current_for_range_a(range_index)
    if current_a == 0.0:
        raise ValueError('calibrated current must be non-zero')
    return calibrated_probe_voltage_v(probe_voltage_v, range_index) / current_a

def current_for_range_a(range_index: int, vset_v: float=1.0) -> float:
    resistors = (10000.0, 1000.0, 100.0, 10.0)
    if range_index < 0 or range_index >= len(resistors):
        raise ValueError('range_index must be 0, 1, 2 or 3')
    return float(vset_v) / resistors[range_index]

class DirectFourProbeVoltage:

    def __init__(self, frontend: AnalogFrontendController, vset_v: float=1.0, magnitude_mode: str=MAGNITUDE_MODE_ABS, zero_offsets_v=DEFAULT_ADC_ZERO_OFFSET_BY_RANGE_V, use_calibrated_current: bool=True):
        if magnitude_mode not in (MAGNITUDE_MODE_ABS, MAGNITUDE_MODE_RESTORE_MSB):
            raise ValueError(f'unsupported magnitude mode: {magnitude_mode!r}')
        self.frontend = frontend
        self.mmio = frontend.mmio
        self.vset_v = float(vset_v)
        self.magnitude_mode = magnitude_mode
        self.zero_offsets_v = _validate_zero_offsets_v(zero_offsets_v)
        self.use_calibrated_current = bool(use_calibrated_current)

    def zero_offset_for_range(self, range_index: int) -> float:
        range_index = int(range_index)
        if range_index < 0 or range_index >= len(self.zero_offsets_v):
            raise ValueError('range_index must be 0, 1, 2 or 3')
        return self.zero_offsets_v[range_index]

    def _convert_code(self, range_index: int, code: float):
        adc_v = adc_code_to_magnitude_voltage_v(code, self.magnitude_mode)
        adc_v = correct_adc_zero_offset_v(adc_v, self.zero_offset_for_range(range_index))
        probe_v = adc_voltage_to_probe_magnitude_v(adc_v)
        if self.use_calibrated_current:
            current_a = calibrated_current_for_range_a(range_index)
        else:
            current_a = current_for_range_a(range_index, self.vset_v)
        return (adc_v, probe_v, current_a)

    def read(self, offset: int) -> int:
        return int(self.mmio.read(int(offset))) & 4294967295

    def write(self, offset: int, value: int) -> None:
        self.mmio.write(int(offset), int(value) & 4294967295)

    def diagnostics(self):
        return {'adc_raw': self.read(28), 'window_seq': self.read(REG_WINDOW_SEQ), 'window_count': self.read(REG_WINDOW_COUNT), 'window_flags': self.read(REG_WINDOW_FLAGS), 'window_control': self.read(REG_WINDOW_CONTROL), 'code_min': self.read(148), 'code_max': self.read(152)}

    def disable_window(self) -> None:
        self.write(REG_WINDOW_CONTROL, WINDOW_DISABLE)

    def reset_window(self) -> None:
        self.write(REG_WINDOW_CONTROL, WINDOW_RESET)

    def enable_window(self) -> None:
        self.write(REG_WINDOW_CONTROL, WINDOW_ENABLE)

    def read_window_snapshot(self, previous_seq: Optional[int]=None, timeout_s: float=1.0):
        deadline = time.monotonic() + float(timeout_s)
        while time.monotonic() < deadline:
            seq_before = self.read(REG_WINDOW_SEQ)
            if previous_seq is not None and seq_before == previous_seq:
                time.sleep(0.0005)
                continue
            sum_low = self.read(REG_WINDOW_SUM_LOW)
            sum_high = self.read(REG_WINDOW_SUM_HIGH)
            count = self.read(REG_WINDOW_COUNT)
            flags = self.read(REG_WINDOW_FLAGS)
            seq_after = self.read(REG_WINDOW_SEQ)
            if seq_before != seq_after:
                continue
            total = sum_high << 32 | sum_low
            if count <= 0:
                time.sleep(0.0005)
                continue
            return {'seq': seq_after, 'sum': total, 'count': count, 'average_code': float(total) / float(count), 'flags': flags}
        raise TimeoutError('ADC window did not produce a stable non-empty snapshot: ' + repr(self.diagnostics()))

    def measure_window(self, range_index: int, reverse: bool=False, timeout_s: float=1.0, settle_s: float=DEFAULT_RELAY_SETTLE_S, keep_current_on: bool=False) -> FourProbeMeasurement:
        settle_s = _validate_settle_s(settle_s)
        self.frontend.safe_off()
        self.disable_window()
        self.reset_window()
        self.frontend.configure(range_index, reverse=reverse, enable_current=True)
        if settle_s > 0.0:
            time.sleep(settle_s)
        success = False
        try:
            self.enable_window()
            start_seq = self.read(REG_WINDOW_SEQ)
            snapshot = self.read_window_snapshot(start_seq, timeout_s)
            self.write(REG_WINDOW_CONTROL, WINDOW_ACK)
            success = True
        finally:
            self.disable_window()
            if not (keep_current_on and success):
                self.frontend.safe_off()
        code = snapshot['average_code']
        adc_v, probe_v, current_a = self._convert_code(range_index, code)
        resistance_ohm = probe_v / current_a if current_a != 0.0 else None
        return FourProbeMeasurement(range_index=int(range_index), reverse=bool(reverse), current_a=current_a, average_code=code, adc_voltage_v=adc_v, probe_voltage_v=probe_v, resistance_ohm=resistance_ohm)

    def measure_median(self, range_index: int, reverse: bool=False, windows: int=5, timeout_s: float=1.0, settle_s: float=DEFAULT_RELAY_SETTLE_S, keep_current_on: bool=False) -> FourProbeMeasurement:
        windows = int(windows)
        if windows <= 0:
            raise ValueError('windows must be positive')
        settle_s = _validate_settle_s(settle_s)
        self.frontend.safe_off()
        self.disable_window()
        self.reset_window()
        self.frontend.configure(range_index, reverse=reverse, enable_current=True)
        if settle_s > 0.0:
            time.sleep(settle_s)
        self.enable_window()
        values = []
        last_seq = self.read(REG_WINDOW_SEQ)
        success = False
        try:
            for _ in range(windows):
                snapshot = self.read_window_snapshot(last_seq, timeout_s)
                last_seq = snapshot['seq']
                self.write(REG_WINDOW_CONTROL, WINDOW_ACK)
                code = snapshot['average_code']
                adc_v, probe_v, current_a = self._convert_code(range_index, code)
                values.append((code, adc_v, probe_v, current_a))
            success = True
        finally:
            self.disable_window()
            if not (keep_current_on and success):
                self.frontend.safe_off()
        median_values = [statistics.median((item[index] for item in values)) for index in range(4)]
        code, adc_v, probe_v, current_a = median_values
        return FourProbeMeasurement(range_index=int(range_index), reverse=bool(reverse), current_a=current_a, average_code=code, adc_voltage_v=adc_v, probe_voltage_v=probe_v, resistance_ohm=probe_v / current_a)
