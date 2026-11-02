# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Unit-explicit four-probe resistance and resistivity calculations."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional
from .adc_conversion import AdcSample, decode_frame
from .materials import CalculationMode, MaterialProfile

class MeasurementStatus(str, Enum):
    """Outcome of a measurement calculation."""
    OK = 'ok'
    INVALID_VOLTAGE = 'invalid_voltage'
    INVALID_CURRENT = 'invalid_current'
    NON_FINITE_INPUT = 'non_finite_input'
    INVALID_ADC_FRAME = 'invalid_adc_frame'

@dataclass(frozen=True)
class MeasurementResult:
    """Calculated values plus warnings and source sample metadata."""
    status: MeasurementStatus
    voltage_v: Optional[float]
    current_a: Optional[float]
    resistance_ohm: Optional[float]
    sheet_resistance_ohm_per_square: Optional[float]
    resistivity_ohm_m: Optional[float]
    raw_frame: Optional[int] = None
    raw_code: Optional[int] = None
    warning_codes: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether the calculation produced usable electrical values."""
        return self.status is MeasurementStatus.OK

def _empty_result(status: MeasurementStatus, voltage_v: Optional[float], current_a: Optional[float], *, raw_frame: Optional[int]=None, raw_code: Optional[int]=None, warning_codes: tuple[str, ...]=()) -> MeasurementResult:
    return MeasurementResult(status=status, voltage_v=voltage_v, current_a=current_a, resistance_ohm=None, sheet_resistance_ohm_per_square=None, resistivity_ohm_m=None, raw_frame=raw_frame, raw_code=raw_code, warning_codes=warning_codes)

def calculate_measurement(voltage_v: float, profile: MaterialProfile, current_a: Optional[float]=None, *, raw_frame: Optional[int]=None, raw_code: Optional[int]=None, adc_saturated: bool=False) -> MeasurementResult:
    """Calculate resistance, sheet resistance and resistivity.

    Voltage and current are SI values.  A profile's calibration gain and
    offset are applied only to the calculated resistivity; raw resistance and
    sheet resistance remain available for diagnostics.
    """
    try:
        voltage = float(voltage_v)
    except (TypeError, ValueError) as exc:
        raise ValueError('voltage_v must be numeric') from exc
    if not math.isfinite(voltage):
        return _empty_result(MeasurementStatus.NON_FINITE_INPUT, voltage, current_a)
    current = profile.excitation_current_a if current_a is None else current_a
    try:
        current = float(current)
    except (TypeError, ValueError) as exc:
        raise ValueError('current_a must be numeric') from exc
    if not math.isfinite(current) or current <= 0:
        return _empty_result(MeasurementStatus.INVALID_CURRENT, voltage, current)
    if profile.valid_voltage_min_v is not None and voltage < profile.valid_voltage_min_v:
        return _empty_result(MeasurementStatus.INVALID_VOLTAGE, voltage, current)
    if profile.valid_voltage_max_v is not None and voltage > profile.valid_voltage_max_v:
        return _empty_result(MeasurementStatus.INVALID_VOLTAGE, voltage, current)
    resistance = voltage / current
    sheet_resistance = profile.sheet_geometry_factor * resistance
    if profile.mode is CalculationMode.BULK:
        assert profile.probe_spacing_m is not None
        assert profile.geometry_factor is not None
        resistivity = profile.geometry_factor * profile.probe_spacing_m * resistance
    elif profile.mode is CalculationMode.THIN_FILM:
        assert profile.thickness_m is not None
        resistivity = sheet_resistance * profile.thickness_m
    else:
        assert profile.custom_resistivity_factor_m is not None
        resistivity = profile.custom_resistivity_factor_m * resistance
    resistivity = resistivity * profile.calibration_gain + profile.calibration_offset_ohm_m
    warnings: list[str] = []
    if adc_saturated:
        warnings.append('ADC_SATURATED')
    if profile.resistivity_min_ohm_m is not None and resistivity < profile.resistivity_min_ohm_m:
        warnings.append('RESISTIVITY_OUT_OF_RANGE')
    if profile.resistivity_max_ohm_m is not None and resistivity > profile.resistivity_max_ohm_m:
        warnings.append('RESISTIVITY_OUT_OF_RANGE')
    return MeasurementResult(status=MeasurementStatus.OK, voltage_v=voltage, current_a=current, resistance_ohm=resistance, sheet_resistance_ohm_per_square=sheet_resistance, resistivity_ohm_m=resistivity, raw_frame=raw_frame, raw_code=raw_code, warning_codes=tuple(dict.fromkeys(warnings)))

def calculate_from_adc_frame(raw_frame: int, profile: MaterialProfile) -> MeasurementResult:
    """Decode one ADC frame and calculate its electrical result."""
    try:
        sample: AdcSample = decode_frame(raw_frame, profile.adc)
    except ValueError:
        return _empty_result(MeasurementStatus.INVALID_ADC_FRAME, None, profile.excitation_current_a, raw_frame=raw_frame)
    return calculate_measurement(sample.voltage_v, profile, raw_frame=sample.raw_frame, raw_code=sample.code, adc_saturated=sample.saturated)
