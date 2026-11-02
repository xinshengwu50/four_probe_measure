# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Material-specific measurement configuration and registry.

The registry is deliberately independent from the ADC driver and scan
controller.  Adding a material should normally add a profile and calibration
data, not duplicate the acquisition implementation.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Iterable, Mapping, Optional
from .adc_conversion import AdcConfig

class CalculationMode(str, Enum):
    """Physical model used to turn four-probe resistance into resistivity."""
    BULK = 'bulk'
    THIN_FILM = 'thin_film'
    CUSTOM = 'custom'

@dataclass(frozen=True)
class MaterialProfile:
    """All material-dependent parameters needed by the software model.

    Units are SI: amperes, metres, volts, ohms and ohm-metres.  ``geometry_factor``
    is dimensionless for the bulk model, while ``custom_resistivity_factor_m``
    has units of metres.  A thin-film profile computes resistivity as sheet
    resistance multiplied by ``thickness_m``.
    """
    material_id: str
    name: str
    mode: CalculationMode
    adc: AdcConfig
    excitation_current_a: float
    probe_spacing_m: Optional[float] = None
    thickness_m: Optional[float] = None
    geometry_factor: Optional[float] = None
    sheet_geometry_factor: float = math.pi / math.log(2.0)
    custom_resistivity_factor_m: Optional[float] = None
    calibration_gain: float = 1.0
    calibration_offset_ohm_m: float = 0.0
    valid_voltage_min_v: Optional[float] = None
    valid_voltage_max_v: Optional[float] = None
    resistivity_min_ohm_m: Optional[float] = None
    resistivity_max_ohm_m: Optional[float] = None

    def __post_init__(self) -> None:
        if self.material_id is None:
            raise ValueError('material_id must not be empty')
        if self.name is None:
            raise ValueError('name must not be empty')
        material_id = str(self.material_id).strip()
        if not material_id:
            raise ValueError('material_id must not be empty')
        if not str(self.name).strip():
            raise ValueError('name must not be empty')
        object.__setattr__(self, 'material_id', material_id)
        object.__setattr__(self, 'name', str(self.name).strip())
        mode = self.mode
        if not isinstance(mode, CalculationMode):
            try:
                mode = CalculationMode(str(mode))
            except ValueError as exc:
                raise ValueError(f'unsupported calculation mode: {self.mode!r}') from exc
            object.__setattr__(self, 'mode', mode)
        adc = self.adc
        if isinstance(adc, Mapping):
            adc = AdcConfig(**dict(adc))
            object.__setattr__(self, 'adc', adc)
        if not isinstance(adc, AdcConfig):
            raise ValueError('adc must be an AdcConfig instance or mapping')
        if not math.isfinite(self.excitation_current_a) or self.excitation_current_a <= 0:
            raise ValueError('excitation_current_a must be finite and positive')
        if not math.isfinite(self.sheet_geometry_factor) or self.sheet_geometry_factor <= 0:
            raise ValueError('sheet_geometry_factor must be finite and positive')
        if not math.isfinite(self.calibration_gain) or self.calibration_gain <= 0:
            raise ValueError('calibration_gain must be finite and positive')
        if not math.isfinite(self.calibration_offset_ohm_m):
            raise ValueError('calibration_offset_ohm_m must be finite')
        if mode is CalculationMode.BULK:
            _require_positive(self.probe_spacing_m, 'probe_spacing_m')
            _require_positive(self.geometry_factor, 'geometry_factor')
        elif mode is CalculationMode.THIN_FILM:
            _require_positive(self.thickness_m, 'thickness_m')
        else:
            _require_positive(self.custom_resistivity_factor_m, 'custom_resistivity_factor_m')
        _validate_range(self.valid_voltage_min_v, self.valid_voltage_max_v, 'valid voltage')
        _validate_range(self.resistivity_min_ohm_m, self.resistivity_max_ohm_m, 'resistivity')
        for value, field_name in ((self.probe_spacing_m, 'probe_spacing_m'), (self.thickness_m, 'thickness_m'), (self.geometry_factor, 'geometry_factor'), (self.custom_resistivity_factor_m, 'custom_resistivity_factor_m'), (self.valid_voltage_min_v, 'valid_voltage_min_v'), (self.valid_voltage_max_v, 'valid_voltage_max_v'), (self.resistivity_min_ohm_m, 'resistivity_min_ohm_m'), (self.resistivity_max_ohm_m, 'resistivity_max_ohm_m')):
            if value is not None and (not math.isfinite(value)):
                raise ValueError(f'{field_name} must be finite when provided')
        if self.resistivity_min_ohm_m is not None and self.resistivity_min_ohm_m < 0:
            raise ValueError('resistivity_min_ohm_m must not be negative')

    def to_dict(self) -> dict[str, Any]:
        """Serialize the profile to JSON-compatible primitive values."""
        data = asdict(self)
        data['mode'] = self.mode.value
        data['adc']['encoding'] = self.adc.encoding.value
        return data

def _require_positive(value: Optional[float], name: str) -> None:
    if value is None or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')

def _validate_range(minimum: Optional[float], maximum: Optional[float], label: str) -> None:
    if minimum is not None and (not math.isfinite(minimum)):
        raise ValueError(f'{label} minimum must be finite')
    if maximum is not None and (not math.isfinite(maximum)):
        raise ValueError(f'{label} maximum must be finite')
    if minimum is not None and maximum is not None and (minimum > maximum):
        raise ValueError(f'{label} minimum must not exceed maximum')

class MaterialRegistry:
    """In-memory registry keyed by stable material identifiers."""

    def __init__(self, profiles: Iterable[MaterialProfile]=()) -> None:
        self._profiles: dict[str, MaterialProfile] = {}
        for profile in profiles:
            self.add(profile)

    def add(self, profile: MaterialProfile, *, replace: bool=False) -> None:
        if not isinstance(profile, MaterialProfile):
            raise TypeError('profile must be a MaterialProfile')
        if profile.material_id in self._profiles and (not replace):
            raise ValueError(f'material already exists: {profile.material_id}')
        self._profiles[profile.material_id] = profile

    def get(self, material_id: str) -> MaterialProfile:
        try:
            return self._profiles[material_id]
        except KeyError as exc:
            raise KeyError(f'unknown material: {material_id}') from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._profiles))

    def profiles(self) -> tuple[MaterialProfile, ...]:
        return tuple((self._profiles[key] for key in self.ids()))

    def to_dict(self) -> list[dict[str, Any]]:
        return [profile.to_dict() for profile in self.profiles()]

    @classmethod
    def from_dict(cls, payload: Iterable[Mapping[str, Any]] | Mapping[str, Any]) -> 'MaterialRegistry':
        if isinstance(payload, Mapping):
            payload = payload.get('profiles', ())
        return cls((MaterialProfile(**dict(item)) for item in payload))
