# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""ADC mapping and 10 ms window helpers for the four-probe PYNQ system.

The ADS8681 is configured for a bipolar +/-5.12 V range and returns a signed
16-bit two's-complement code. PL accumulates accepted positive codes over a
10 ms window; PS reads SUM/COUNT and performs the division.
"""
from __future__ import annotations
import math
ADC_CODE_BITS = 16
ADC_CODE_MID = 1 << ADC_CODE_BITS - 1
ADC_CODE_FULL_SCALE = 1 << ADC_CODE_BITS
ADC_FULL_SCALE_V = 5.12
ADC_FRONTEND_DIVIDER = 1.0
ADC_MIN_VALID_MV = 50.0
ADC_MAX_VALID_MV = 5000.0

def _code_bounds_for_probe_mv(minimum_mv: float, maximum_mv: float, frontend_divider: float) -> tuple[int, int]:
    if not math.isfinite(frontend_divider) or frontend_divider <= 0.0:
        raise ValueError('frontend_divider must be finite and positive')
    if minimum_mv < 0.0 or maximum_mv < minimum_mv:
        raise ValueError('invalid mV range')
    adc_min_v = minimum_mv / frontend_divider / 1000.0
    adc_max_v = maximum_mv / frontend_divider / 1000.0
    code_min = int(math.ceil(adc_min_v * ADC_CODE_MID / ADC_FULL_SCALE_V))
    code_max = int(math.floor(adc_max_v * ADC_CODE_MID / ADC_FULL_SCALE_V))
    code_min = max(0, min(ADC_CODE_MID - 1, code_min))
    code_max = max(0, min(ADC_CODE_MID - 1, code_max))
    return (code_min, code_max)

def code_bounds_for_probe_mv(minimum_mv: float, maximum_mv: float, frontend_divider: float) -> tuple[int, int]:
    """Public wrapper returning raw-code bounds for a probe-voltage range."""
    return _code_bounds_for_probe_mv(minimum_mv, maximum_mv, frontend_divider)
ADC_VALID_CODE_MIN, ADC_VALID_CODE_MAX = _code_bounds_for_probe_mv(ADC_MIN_VALID_MV, ADC_MAX_VALID_MV, ADC_FRONTEND_DIVIDER)

def extract_code(raw_frame: int) -> int:
    """Extract the 16-bit ADC code from the upper half of the 32-bit frame."""
    return int(raw_frame) >> 16 & 65535

def code_to_signed(code: int) -> int:
    """Interpret a 16-bit ADS8681 code as two's complement."""
    code = int(code)
    if not 0 <= code <= 65535:
        raise ValueError('ADC code must be in 0..65535')
    return code - ADC_CODE_FULL_SCALE if code & ADC_CODE_MID else code

def is_valid_voltage_code(code: int) -> bool:
    """Return whether a raw code is a positive voltage in the configured range."""
    signed_code = code_to_signed(int(code))
    return ADC_VALID_CODE_MIN <= signed_code <= ADC_VALID_CODE_MAX

def code_to_mv(code: int, frontend_divider: float=ADC_FRONTEND_DIVIDER) -> float:
    """Convert one ADC code to probe-side millivolts."""
    if not math.isfinite(frontend_divider) or frontend_divider <= 0.0:
        raise ValueError('frontend_divider must be finite and positive')
    signed_code = code_to_signed(code)
    adc_mv = signed_code * ADC_FULL_SCALE_V * 1000.0 / ADC_CODE_MID
    return adc_mv * frontend_divider

def code_to_scaled_0p1mv(code: int, frontend_divider: float=ADC_FRONTEND_DIVIDER) -> int:
    """Return probe voltage in 0.1 mV units using half-up rounding."""
    value = code_to_mv(code, frontend_divider) * 10.0
    if value >= 0.0:
        return int(math.floor(value + 0.5))
    return -int(math.floor(-value + 0.5))

def average_window_code(sum_code: int, count: int) -> float:
    """Return the average raw code for a PL window; count must be positive."""
    if int(count) <= 0:
        raise ValueError('count must be positive')
    return float(sum_code) / float(count)

def average_window_mv(sum_code: int, count: int, frontend_divider: float=ADC_FRONTEND_DIVIDER) -> float:
    """Convert a PL SUM/COUNT window into average probe-side millivolts."""
    if not math.isfinite(frontend_divider) or frontend_divider <= 0.0:
        raise ValueError('frontend_divider must be finite and positive')
    average_code = average_window_code(sum_code, count)
    adc_mv = average_code * ADC_FULL_SCALE_V * 1000.0 / ADC_CODE_MID
    return adc_mv * frontend_divider
Q24_SCALE = 1 << 24

def adc_scale_mv_per_code(frontend_divider: float=ADC_FRONTEND_DIVIDER) -> float:
    """ADC-code-to-probe millivolt scale before geometry correction."""
    if not math.isfinite(frontend_divider) or frontend_divider <= 0.0:
        raise ValueError('frontend_divider must be finite and positive')
    return ADC_FULL_SCALE_V * 1000.0 / ADC_CODE_MID * frontend_divider

def quantize_q8_24(value: float) -> int:
    """Quantize a non-negative value to unsigned Q8.24."""
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError('Q8.24 value must be finite and non-negative')
    scaled = value * Q24_SCALE
    if scaled > 4294967295:
        raise OverflowError('Q8.24 value exceeds 32-bit range')
    return int(math.floor(scaled + 0.5))

def q8_24_to_float(value_q: int) -> float:
    return float(int(value_q)) / float(Q24_SCALE)

def product96_to_float(product_low: int, product_mid: int, product_high: int) -> float:
    """Decode a 96-bit PL product carrying Q8.24 scaling."""
    packed = int(product_high) << 64 | int(product_mid) << 32 | int(product_low)
    return q8_24_to_float(packed)
