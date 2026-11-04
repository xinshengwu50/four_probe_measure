# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""HMI parameter types, incremental42-byte START parser and result writer.
Modes1/2/3 select single/25/9 points. Addresses and fixed-point encoding match the existing TFT; numeric encoding is not physical gain. Older33/37-byte frames remain readable."""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum, IntEnum
import math
from .hmi_wire import config_frame_length, split_config_frame
import threading
from typing import Any, Optional, Protocol
from .hmi_address import NumericPageUart
try:
    from .multi_material_model import SampleType, calculate_four_probe, encode_scientific
except ImportError:
    from multi_material_model import SampleType, calculate_four_probe, encode_scientific

class MeasurementMode(IntEnum):
    SINGLE_POINT = 1
    TWENTY_FIVE_POINT = 2
    NINE_POINT = 3

    @property
    def hmi_label(self) -> str:
        return {self.SINGLE_POINT: '自定义单点测量', self.TWENTY_FIVE_POINT: '二十五点测量', self.NINE_POINT: '九点测量'}[self]

class SampleKind(str, Enum):
    HEMT = 'hemt'
    ALGAN = 'algan'
    SILICON = 'silicon'
    ALN = 'aln'
    GAN = 'gan'

    @property
    def model_type(self) -> SampleType:
        return SampleType.ALGAN if self is SampleKind.GAN else SampleType(self.value)

class QualityFlag(str, Enum):
    CONFIG_DEFAULTED = 'CONFIG_DEFAULTED'
    NO_VALID_VOLTAGE = 'NO_VALID_VOLTAGE'
    DOPING_NOT_AVAILABLE = 'DOPING_NOT_AVAILABLE'
    MOTION_ERROR = 'MOTION_ERROR'
    MODEL_ERROR = 'MODEL_ERROR'
    UNSUPPORTED_MODE = 'UNSUPPORTED_MODE'
    MEASUREMENT_COMPLETE = 'MEASUREMENT_COMPLETE'

class Hmi22ProtocolError(ValueError):
    """The latest HMI frame is malformed or incomplete."""

class HmiUartLike(Protocol):

    def read_available(self) -> bytes:
        ...

    def send_command(self, text: str) -> None:
        ...

class SinglePointControllerLike(Protocol):

    def run_single_point(self) -> dict[str, Any]:
        ...

@dataclass(frozen=True)
class MeasurementConfig:
    measurement_mode: MeasurementMode = MeasurementMode.SINGLE_POINT
    sample_kind: SampleKind = SampleKind.SILICON
    polarity: str = 'N'
    diameter_mm: float = 50.0
    thickness_um: float = 645.0
    current_ma: Optional[float] = 10.0
    current_mode: Optional[int] = None
    sample_structure: Optional[int] = None
    probe_spacing_mm: float = 1.0
    point_index: int = 1
    warnings: tuple[QualityFlag, ...] = field(default_factory=tuple)
    sample_label: str = ''

    @property
    def model_sample_kind(self):
        if self.sample_structure == 2:
            return SampleKind.HEMT
        return SampleKind.ALGAN if self.sample_kind is SampleKind.GAN else self.sample_kind

    def validate(self) -> 'MeasurementConfig':
        if not isinstance(self.sample_label, str) or len(self.sample_label) > 160 or any((ord(c) < 32 for c in self.sample_label)):
            raise Hmi22ProtocolError('sample_label must be a single-line string of at most160 characters')
        if self.current_mode is not None and (isinstance(self.current_mode, bool) or self.current_mode not in range(5)):
            raise Hmi22ProtocolError('current_mode must be0..4')
        if self.sample_structure is not None and (isinstance(self.sample_structure, bool) or self.sample_structure not in (0, 1, 2)):
            raise Hmi22ProtocolError('sample_structure must be0/1/2')
        if self.polarity.upper() not in {'N', 'P'}:
            raise Hmi22ProtocolError('polarity must be N or P')
        if not isinstance(self.point_index, int) or not 0 <= self.point_index <= 25:
            raise Hmi22ProtocolError('point_index must be an integer in 0..25')
        if self.measurement_mode is MeasurementMode.SINGLE_POINT and self.point_index == 0:
            raise Hmi22ProtocolError('single-point mode needs point_index >= 1')
        for name, value in (('diameter_mm', self.diameter_mm), ('thickness_um', self.thickness_um), ('probe_spacing_mm', self.probe_spacing_mm)):
            if not math.isfinite(float(value)) or float(value) <= 0:
                raise Hmi22ProtocolError(f'{name} must be finite and positive')
        if self.current_ma is not None and (not math.isfinite(float(self.current_ma)) or float(self.current_ma) <= 0):
            raise Hmi22ProtocolError('current_ma must be positive or None for AUTO')
        return self

@dataclass(frozen=True)
class SinglePointResult:
    config: MeasurementConfig
    voltage_mv: Optional[float]
    resistivity_ohm_cm: Optional[float]
    sheet_resistance_ohm_sq: Optional[float]
    doping_cm3: Optional[float]
    alpha: Optional[float]
    diameter_over_spacing: Optional[float]
    fd: Optional[float]
    fw: Optional[float]
    fsp: Optional[float]
    quality_flags: tuple[QualityFlag, ...]
    measurement_count: int = 0
    valid_windows: int = 0
    valid_samples: int = 0
    point_index: int = 0
    error: Optional[str] = None
    forward_voltage_mv: Optional[float] = None
    reverse_voltage_mv: Optional[float] = None
    equivalent_current_ma: Optional[float] = None
    resistance_ohm: Optional[float] = None
    forward_current_ma: Optional[float] = None
    reverse_current_ma: Optional[float] = None
    forward_reverse_delta_mv: Optional[float] = None
    polarity_same_sign: Optional[bool] = None
PAGE0_PARAM_SCALE = {'x1': ('probe_voltage_mv', 10), 'x2': ('temperature_c', 10), 'x3': ('humidity_pct', 10), 'x5': ('probe_spacing_mm', 10)}
PAGE0_VOLTAGE_MIRROR_SCALE = 10
PAGE0_VOLTAGE_MIRROR_PAGES: tuple[str, ...] = ('V1', 'V9', 'V251', 'V252', 'V253', '单点三代', '单点非三', '九点三代', '九点非三', '二十五三代1', '二十五三代2', '二十五三代3', '二十五非三1', '二十五非三2', '二十五非三3')
VOLTAGE_FORWARD_SCALE = 100000
VOLTAGE_REVERSE_SCALE = 100000
PAGE1_CALC_SCALE = {'x86': ('sheet_resistance_ohm_sq', 100), 'x8': ('resistivity_ohm_cm', 100000), 'x12': ('alpha', 1000), 'x13': ('diameter_over_spacing', 10000), 'x14': ('fd', 10000), 'x15': ('fw', 10000), 'x16': ('fsp', 1000)}
PAGE1_DONE_CONTROL = 'page1.n0'
DEFAULT_TEMPERATURE_C = 23.0
DEFAULT_HUMIDITY_PCT = 60.0
DEFAULT_PRECISION_PERCENT = 0
DEFAULT_CURRENT_FIT = 1
DEFAULT_HUMIDITY_IMPACT = 1
DEFAULT_CURRENT_ADVICE = 0
DEFAULT_HUMIDITY_ADVICE = 1
DEFAULT_TEMPERATURE_COEFF_X100 = 0
AUTO_RELEASE_DELAY_S: Optional[float] = 2.0

def _parse_u32(raw: bytes, name: str) -> int:
    if len(raw) != 4:
        raise Hmi22ProtocolError(f'{name} must be a 4-byte value')
    return int.from_bytes(raw, 'little', signed=False)

def _scaled(value: Optional[float], scale: float, *, required: bool=False) -> int:
    """Scale a physical value into the integer the on-screen control expects.

    ``None`` (no valid measurement) becomes 0 so the report never keeps showing
    the previous run's numbers; ``required`` values are known parameters and a
    missing one is a programming error.
    """
    if value is None:
        if required:
            raise Hmi22ProtocolError('missing value for a required screen field')
        return 0
    return int(round(float(value) * scale))

def _scientific_parts(value: Optional[float]) -> tuple[int, int]:
    """Split a value into the ``(mantissa_x100000, exponent)`` pair.

    ``page1.x9``/``page1.x10`` render as ``mantissa/1e5 e+exponent``; a missing
    value becomes ``(0, 0)`` so the screen shows ``0.00000 e+0`` instead of a
    stale reading.
    """
    if value is None or float(value) <= 0.0:
        return (0, 0)
    encoded = encode_scientific(float(value))
    return (encoded.mantissa, encoded.exponent)

def _sample_from_code(code: int) -> SampleKind:
    try:
        return {1: SampleKind.HEMT, 2: SampleKind.ALGAN, 3: SampleKind.SILICON, 4: SampleKind.GAN}[code]
    except KeyError as exc:
        raise Hmi22ProtocolError(f'unsupported sample_type={code}') from exc

def _split_frame(frame):
    try:
        return split_config_frame(frame)
    except ValueError as error:
        raise Hmi22ProtocolError(str(error)) from error

def parse_22hmi_config(frame: bytes) -> MeasurementConfig:
    fields = _split_frame(frame)
    mode_value = _parse_u32(fields[102], 'measurement_mode')
    try:
        mode = MeasurementMode(mode_value)
    except ValueError as exc:
        raise Hmi22ProtocolError(f'unsupported measurement_mode={mode_value}') from exc
    polarity = _parse_u32(fields[187], 'polarity')
    if polarity not in (0, 1):
        raise Hmi22ProtocolError('polarity must be 0 or 1')
    point_index = _parse_u32(fields[119], 'point_index')
    current_mode = _parse_u32(fields[238], 'current_mode') if 136 in fields else None
    structure = _parse_u32(fields[136], 'sample_structure') if 136 in fields else None
    if current_mode is not None and current_mode not in range(5):
        raise Hmi22ProtocolError('current_mode must be0..4')
    if structure is not None and structure not in (0, 1, 2):
        raise Hmi22ProtocolError('sample_structure must be0/1/2')
    if 136 in fields and mode is MeasurementMode.SINGLE_POINT and (not 1 <= point_index <= 25):
        raise Hmi22ProtocolError('single point must be1..25')
    if mode is MeasurementMode.SINGLE_POINT:
        point_index = max(1, min(25, point_index))
    if structure is not None and _parse_u32(fields[255], 'sample_type') == 1:
        raise Hmi22ProtocolError('new frame material1 retired; select HEMT with structure2')
    config = MeasurementConfig(measurement_mode=mode, sample_kind=_sample_from_code(_parse_u32(fields[255], 'sample_type')), polarity='N' if polarity else 'P', diameter_mm=_parse_u32(fields[204], 'diameter') / 10.0, thickness_um=_parse_u32(fields[221], 'thickness') / 100.0, current_ma=[None, 0.1, 1.0, 10.0, 100.0][current_mode] if current_mode is not None else None if not fields[238] else _parse_u32(fields[238], 'current') / 100.0, current_mode=current_mode, sample_structure=structure, point_index=point_index, warnings=())
    return config.validate()

class Hmi22ConfigParser:
    """Incrementally parse the fixed-width latest-HMI frame and MEAS."""
    BASE_LENGTH = 42

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[MeasurementConfig | str]:
        self._buffer.extend(data)
        events: list[MeasurementConfig | str] = []
        while True:
            meas = self._buffer.find(b'MEAS')
            start = self._buffer.find(b'\xaa')
            candidates = [x for x in (meas, start) if x >= 0]
            if not candidates:
                if len(self._buffer) > 256:
                    del self._buffer[:-64]
                break
            first = min(candidates)
            if meas == first:
                del self._buffer[:first + 4]
                events.append('MEAS')
                continue
            if first:
                del self._buffer[:first]
            length = config_frame_length(self._buffer)
            if length is None:
                break
            if length == 0:
                del self._buffer[0]
                continue
            if len(self._buffer) < length:
                break
            frame = bytes(self._buffer[:length])
            del self._buffer[:length]
            try:
                events.append(parse_22hmi_config(frame))
            except Hmi22ProtocolError:
                self._buffer[:0] = frame[1:]
        return events

class Hmi22Writer:
    """Inject the numeric source variables the latest HMI reads back.

    The screen composes every report text itself from these numbers, so PS
    never writes ``t*.txt`` labels.  After the numbers are in place PS raises
    ``page1.n0.val``, which lets the 正在测量 page leave its wait loop; the
    screen then shows 测量完成 and a 1 s timer selects the material-specific result page.
    """

    def __init__(self, uart: HmiUartLike) -> None:
        self._uart = uart if isinstance(uart, NumericPageUart) else NumericPageUart(uart)
        self._state_lock = threading.RLock()
        self._released = False
        self._generation = 0
        self._auto_release: Optional[threading.Timer] = None

    def _cancel_auto_release(self) -> None:
        timer, self._auto_release = (self._auto_release, None)
        if timer is not None:
            timer.cancel()

    def _val(self, target: str, value: int) -> None:
        self._uart.send_command(f'{target}.val={int(value)}')

    def clear_done_flag(self, *, early_release=True, point_index=1) -> None:
        with self._state_lock:
            self._cancel_auto_release()
            self._generation += 1
            generation = self._generation
            self._released = False
            self._val('修改参数.x6', point_index)
            self._val(PAGE1_DONE_CONTROL, 0)
            if early_release and AUTO_RELEASE_DELAY_S is not None:
                timer = threading.Timer(AUTO_RELEASE_DELAY_S, self._auto_release_now, args=(generation,))
                timer.daemon = True
                self._auto_release = timer
                timer.start()

    def _auto_release_now(self, generation=None) -> None:
        with self._state_lock:
            if generation is not None and generation != self._generation:
                return
            self.release_wait_page()

    def release_wait_page(self) -> None:
        with self._state_lock:
            self._cancel_auto_release()
            if not self._released:
                self._val(PAGE1_DONE_CONTROL, 1)
                self._released = True

    def _scientific_cell(self, page, value_control, exponent_control, value, decimals):
        encoded = encode_scientific(0.0 if value is None else max(0.0, float(value)), decimal_places=decimals)
        self._val(page + '.' + value_control, encoded.mantissa)
        self._uart.send_command('%s.%s.txt="%d"' % (page, exponent_control, encoded.exponent))

    def write_point_result(self, result):
        """Write point 1 directly to the result page already selected by HMI."""
        silicon = result.config.model_sample_kind == SampleKind.SILICON
        page = '单点非三' if silicon else '单点三代'
        index = result.point_index or result.config.point_index
        self._val('修改参数.x6', index)
        self._val(page + '.n0', index)
        self._val(page + '.n1', index)
        self._val('V1.n0', index)
        mirrors = {'x20': _scaled(result.equivalent_current_ma if result.equivalent_current_ma is not None else result.config.current_ma, 100), 'x21': _scaled(result.voltage_mv, 10), 'x22': _scaled(DEFAULT_TEMPERATURE_C, 10), 'x23': _scaled(DEFAULT_HUMIDITY_PCT, 10), 'x24': _scaled(result.config.thickness_um, 100), 'x25': _scaled(result.config.probe_spacing_mm, 10), 'x26': _scaled(result.config.diameter_mm, 10), 'x27': 1 if result.config.polarity == 'N' else 0}
        for control, value in mirrors.items():
            self._val(page + '.' + control, value)
            self._val('V1.' + control, value)
        self._scientific_cell(page, 'x31', 't4', result.sheet_resistance_ohm_sq, 2)
        self._scientific_cell(page, 'x11', 't54' if silicon else 't31', result.resistivity_ohm_cm, 5)
        if silicon:
            self._scientific_cell(page, 'x1', 't19', result.doping_cm3, 5)
        forward = result.voltage_mv if result.forward_voltage_mv is None else result.forward_voltage_mv
        self._val('V1.x30', _scaled(forward, VOLTAGE_FORWARD_SCALE))
        self._val('V1.x10', _scaled(result.reverse_voltage_mv, VOLTAGE_REVERSE_SCALE))

    def write_result(self, result: SinglePointResult, *, include_point=True) -> None:
        cfg = result.config
        if include_point:
            self.write_point_result(result)
        self._val('page0.x0', _scaled(result.equivalent_current_ma if result.equivalent_current_ma is not None else cfg.current_ma, 100, required=True))
        values = {'probe_voltage_mv': result.voltage_mv, 'temperature_c': DEFAULT_TEMPERATURE_C, 'humidity_pct': DEFAULT_HUMIDITY_PCT, 'probe_spacing_mm': cfg.probe_spacing_mm, 'sheet_resistance_ohm_sq': result.sheet_resistance_ohm_sq, 'resistivity_ohm_cm': result.resistivity_ohm_cm, 'alpha': result.alpha, 'diameter_over_spacing': result.diameter_over_spacing, 'fd': result.fd, 'fw': result.fw, 'fsp': result.fsp}
        voltage_mirror = _scaled(values['probe_voltage_mv'], PAGE0_VOLTAGE_MIRROR_SCALE)
        for control, (key, scale) in PAGE0_PARAM_SCALE.items():
            self._val('page0.' + control, _scaled(values[key], scale, required=key == 'probe_spacing_mm'))
        for page in PAGE0_VOLTAGE_MIRROR_PAGES:
            self._val(f'{page}.x21', voltage_mirror)
        for control, (key, scale) in PAGE1_CALC_SCALE.items():
            self._val('page1.' + control, _scaled(values[key], scale))
        mantissa, exponent = _scientific_parts(result.doping_cm3)
        self._val('page1.x9', mantissa)
        self._val('page1.x10', exponent)
        self._val('page1.x11', DEFAULT_PRECISION_PERCENT)
        self._val('page1.x17', _scaled(result.resistivity_ohm_cm, 100000))
        self._val('page1.x18', DEFAULT_TEMPERATURE_COEFF_X100)
        self._val('page1.x19', DEFAULT_CURRENT_FIT)
        self._val('page1.x22', DEFAULT_HUMIDITY_IMPACT)
        self._val('page1.x23', DEFAULT_CURRENT_ADVICE)
        self._val('page1.x24', DEFAULT_HUMIDITY_ADVICE)
        self.release_wait_page()
