# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""ADC frame decoding and code-to-voltage conversion.

The ADS8681 framing details are kept configurable because the legacy design
does not document the analog front-end gain or the exact meaning of every
received bit.  This module therefore exposes a small, explicit conversion
boundary instead of baking legacy constants into the measurement formula.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional

class AdcEncoding(str, Enum):
    """Digital encoding used by an ADC data word."""
    OFFSET_BINARY = 'offset_binary'
    TWOS_COMPLEMENT = 'twos_complement'

@dataclass(frozen=True)
class AdcConfig:
    """Parameters needed to decode one ADC frame.

    ``code_lsb`` is the bit index of the least-significant ADC code bit in
    the received frame.  For a 32-bit frame containing a 16-bit code in the
    upper half this is 16, matching the legacy ``RX_REG[31:16]`` extraction.
    ``full_scale_v`` is the magnitude of the positive/negative analog range,
    not the peak-to-peak span.
    """
    bits: int = 16
    full_scale_v: float = 5.12
    encoding: AdcEncoding = AdcEncoding.OFFSET_BINARY
    frame_bits: int = 32
    code_lsb: int = 16
    voltage_gain: float = 1.0
    voltage_offset_v: float = 0.0
    valid_code_min: Optional[int] = None
    valid_code_max: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.bits, int) or isinstance(self.bits, bool) or (not 1 <= self.bits <= 32):
            raise ValueError('bits must be an integer from 1 to 32')
        if not isinstance(self.frame_bits, int) or isinstance(self.frame_bits, bool) or (not 1 <= self.frame_bits <= 64):
            raise ValueError('frame_bits must be an integer from 1 to 64')
        if not isinstance(self.code_lsb, int) or isinstance(self.code_lsb, bool):
            raise ValueError('code_lsb must be an integer')
        if self.code_lsb < 0 or self.code_lsb + self.bits > self.frame_bits:
            raise ValueError('ADC code does not fit inside frame_bits')
        if not math.isfinite(self.full_scale_v) or self.full_scale_v <= 0:
            raise ValueError('full_scale_v must be finite and positive')
        if not math.isfinite(self.voltage_gain) or self.voltage_gain == 0:
            raise ValueError('voltage_gain must be finite and non-zero')
        if not math.isfinite(self.voltage_offset_v):
            raise ValueError('voltage_offset_v must be finite')
        encoding = self.encoding
        if not isinstance(encoding, AdcEncoding):
            try:
                encoding = AdcEncoding(str(encoding))
            except ValueError as exc:
                raise ValueError(f'unsupported ADC encoding: {self.encoding!r}') from exc
            object.__setattr__(self, 'encoding', encoding)
        maximum = (1 << self.bits) - 1
        code_min = 0 if self.valid_code_min is None else self.valid_code_min
        code_max = maximum if self.valid_code_max is None else self.valid_code_max
        if not isinstance(code_min, int) or not isinstance(code_max, int):
            raise ValueError('valid code limits must be integers')
        if not 0 <= code_min <= maximum or not 0 <= code_max <= maximum or code_min > code_max:
            raise ValueError('valid code limits are outside the ADC code range')
        object.__setattr__(self, 'valid_code_min', code_min)
        object.__setattr__(self, 'valid_code_max', code_max)

    @property
    def code_max(self) -> int:
        """Largest representable code for this ADC word."""
        return (1 << self.bits) - 1

    @property
    def mid_code(self) -> int:
        """Half-scale code used by both supported encodings."""
        return 1 << self.bits - 1

@dataclass(frozen=True)
class AdcSample:
    """Decoded ADC sample with its original frame and saturation state."""
    raw_frame: int
    code: int
    voltage_v: float
    saturated: bool

def _require_integer(value: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f'{name} must be an integer')
    return value

def extract_code(raw_frame: int, config: AdcConfig) -> int:
    """Extract and validate the ADC code from a received frame."""
    raw_frame = _require_integer(raw_frame, 'raw_frame')
    frame_max = (1 << config.frame_bits) - 1
    if not 0 <= raw_frame <= frame_max:
        raise ValueError('raw_frame is outside the configured frame width')
    code = raw_frame >> config.code_lsb & config.code_max
    if not config.valid_code_min <= code <= config.valid_code_max:
        raise ValueError('ADC code is outside the configured valid range')
    return code

def code_to_voltage(code: int, config: AdcConfig) -> float:
    """Convert one ADC code into volts using explicit encoding semantics."""
    code = _require_integer(code, 'code')
    if not 0 <= code <= config.code_max:
        raise ValueError('code is outside the ADC code range')
    if not config.valid_code_min <= code <= config.valid_code_max:
        raise ValueError('code is outside the configured valid range')
    if config.encoding is AdcEncoding.OFFSET_BINARY:
        signed_code = code - config.mid_code
    else:
        signed_code = code if code < config.mid_code else code - (1 << config.bits)
    voltage = signed_code * config.full_scale_v / config.mid_code
    return voltage * config.voltage_gain + config.voltage_offset_v

def is_saturated_code(code: int, config: AdcConfig) -> bool:
    """Return whether a code is one of the ideal ADC rails."""
    code = _require_integer(code, 'code')
    if not 0 <= code <= config.code_max:
        raise ValueError('code is outside the ADC code range')
    if config.encoding is AdcEncoding.OFFSET_BINARY:
        return code in (0, config.code_max)
    return code in (config.mid_code, config.mid_code - 1)

def decode_frame(raw_frame: int, config: AdcConfig) -> AdcSample:
    """Decode a frame and return code, voltage and rail information."""
    code = extract_code(raw_frame, config)
    return AdcSample(raw_frame=raw_frame, code=code, voltage_v=code_to_voltage(code, config), saturated=is_saturated_code(code, config))
