# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""ADS8681 full-frame diagnostics for the PYNQ PS side.

This module intentionally bypasses the PL 10 ms window and reads the complete
32-bit `RX_REG` at AXI offset 0x1C.  That lets a notebook compare the upper and
lower 16-bit halves, byte order, bit alignment, and code encoding without
rebuilding the bitstream first.
"""
from __future__ import annotations
import math
import statistics
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
RAW_ADC_REG = 28
ADC_FULL_SCALE_V = 5.12
ADC_CODE_MID = 32768
ADC_CODE_FULL_SCALE = 65536
ADC_LSB_V = ADC_FULL_SCALE_V / ADC_CODE_MID
FULL_SCALE_CANDIDATES_V = (5.12, 12.288)
FRAME_FIELDS: Tuple[str, ...] = ('high16', 'low16', 'high16_swap_bytes', 'low16_swap_bytes', 'shift30_15', 'shift16_1')
ENCODINGS: Tuple[str, ...] = ('offset_binary', 'twos_complement', 'offset_binary_magnitude', 'twos_complement_magnitude')
FIELD_DESCRIPTIONS: Dict[str, str] = {'high16': 'bits[31:16]', 'low16': 'bits[15:0]', 'high16_swap_bytes': 'swap bytes of bits[31:16]', 'low16_swap_bytes': 'swap bytes of bits[15:0]', 'shift30_15': 'bits[30:15], useful if SDO is delayed/advanced by one bit', 'shift16_1': 'bits[16:1], useful if SDO is delayed/advanced by one bit'}
ENCODING_DESCRIPTIONS: Dict[str, str] = {'offset_binary': 'offset binary: zero at 0x8000', 'twos_complement': "two's complement: zero at 0x0000", 'offset_binary_magnitude': 'absolute offset-binary magnitude', 'twos_complement_magnitude': "absolute two's-complement magnitude"}

@dataclass(frozen=True)
class FrameSample:
    """One complete 32-bit RX_REG sample."""
    timestamp_s: float
    raw_frame: int

@dataclass(frozen=True)
class FrameCapture:
    """A sequence of frames plus optional DMM reference values."""
    label: str
    raw_frames: Tuple[int, ...]
    timestamps_s: Tuple[float, ...] = ()
    range_index: Optional[int] = None
    reverse: bool = False
    expected_voltage_v: Optional[float] = None
    ads_diff_voltage_v: Optional[float] = None
    h4_1_voltage_v: Optional[float] = None
    probe_voltage_v: Optional[float] = None
    actual_current_a: Optional[float] = None

    @property
    def sample_count(self) -> int:
        return len(self.raw_frames)

    def with_instrumentation(self, *, expected_voltage_v: Optional[float]=None, ads_diff_voltage_v: Optional[float]=None, h4_1_voltage_v: Optional[float]=None, probe_voltage_v: Optional[float]=None, actual_current_a: Optional[float]=None) -> 'FrameCapture':
        return FrameCapture(label=self.label, raw_frames=self.raw_frames, timestamps_s=self.timestamps_s, range_index=self.range_index, reverse=self.reverse, expected_voltage_v=self.expected_voltage_v if expected_voltage_v is None else float(expected_voltage_v), ads_diff_voltage_v=self.ads_diff_voltage_v if ads_diff_voltage_v is None else float(ads_diff_voltage_v), h4_1_voltage_v=self.h4_1_voltage_v if h4_1_voltage_v is None else float(h4_1_voltage_v), probe_voltage_v=self.probe_voltage_v if probe_voltage_v is None else float(probe_voltage_v), actual_current_a=self.actual_current_a if actual_current_a is None else float(actual_current_a))

@dataclass(frozen=True)
class CandidateStats:
    field: str
    encoding: str
    count: int
    code_min: int
    code_max: int
    code_mean: float
    code_median: float
    code_std: float
    code_unique: int
    voltage_min: float
    voltage_max: float
    voltage_mean: float
    voltage_median: float
    voltage_std: float
    first_voltage: float
    last_voltage: float

    @property
    def voltage_span(self) -> float:
        return self.voltage_max - self.voltage_min

@dataclass(frozen=True)
class CandidateScore:
    field: str
    encoding: str
    reference_count: int
    reference_span_v: float
    measured_span_v: float
    slope: float
    intercept_v: float
    rmse_v: float
    max_abs_error_v: float
    dynamic_code_span: int
    score: float
    eligible: bool
    reason: str

@dataclass(frozen=True)
class FrameActivity:
    field: str
    unique_values: int
    code_span: int
    code_std: float
    first_value: int
    last_value: int

    @property
    def changes(self) -> bool:
        return self.unique_values > 1 or self.code_span != 0

def _swap16(code: int) -> int:
    code = int(code) & 65535
    return (code & 255) << 8 | (code & 65280) >> 8

def extract_field(raw_frame: int, field: str) -> int:
    """Extract a candidate 16-bit code from a 32-bit RX frame."""
    raw = int(raw_frame) & 4294967295
    if field == 'high16':
        return raw >> 16 & 65535
    if field == 'low16':
        return raw & 65535
    if field == 'high16_swap_bytes':
        return _swap16(raw >> 16 & 65535)
    if field == 'low16_swap_bytes':
        return _swap16(raw & 65535)
    if field == 'shift30_15':
        return raw >> 15 & 65535
    if field == 'shift16_1':
        return raw >> 1 & 65535
    raise ValueError(f'unsupported frame field: {field!r}')

def classify_full_scale(reference_voltage_v: float, code: int) -> Dict[str, object]:
    """Infer which full-scale range best explains a known input voltage and code."""
    reference_voltage_v = float(reference_voltage_v)
    code = int(code) & 65535
    expected_codes = {float(full_scale_v): int(round(ADC_CODE_MID + reference_voltage_v / float(full_scale_v) * ADC_CODE_MID)) for full_scale_v in FULL_SCALE_CANDIDATES_V}
    errors = {full_scale_v: code - expected_code for full_scale_v, expected_code in expected_codes.items()}
    inferred = min(errors, key=lambda full_scale_v: abs(errors[full_scale_v]))
    return {'code': code, 'reference_voltage_v': reference_voltage_v, 'expected_codes': expected_codes, 'code_errors': errors, 'inferred_full_scale_v': inferred}

def code_to_signed(code: int) -> int:
    code = int(code) & 65535
    return code - ADC_CODE_FULL_SCALE if code & ADC_CODE_MID else code

def code_to_voltage(code: int, encoding: str) -> float:
    """Decode a 16-bit code using one of the candidate interpretations."""
    code = int(code) & 65535
    signed = code_to_signed(code)
    if encoding == 'offset_binary':
        return (code - ADC_CODE_MID) * ADC_LSB_V
    if encoding == 'twos_complement':
        return signed * ADC_LSB_V
    if encoding == 'offset_binary_magnitude':
        return abs((code - ADC_CODE_MID) * ADC_LSB_V)
    if encoding == 'twos_complement_magnitude':
        return abs(signed * ADC_LSB_V)
    raise ValueError(f'unsupported code encoding: {encoding!r}')

def decode_candidate(raw_frame: int, field: str, encoding: str) -> float:
    return code_to_voltage(extract_field(raw_frame, field), encoding)

def expected_reference_voltage(capture: FrameCapture) -> Optional[float]:
    if capture.ads_diff_voltage_v is not None:
        return float(capture.ads_diff_voltage_v)
    if capture.expected_voltage_v is not None:
        return float(capture.expected_voltage_v)
    if capture.probe_voltage_v is not None and capture.h4_1_voltage_v is not None:
        return float(capture.h4_1_voltage_v) - 2.5
    return None

def candidate_stats(raw_frames: Sequence[int], fields: Sequence[str]=FRAME_FIELDS, encodings: Sequence[str]=ENCODINGS) -> Dict[Tuple[str, str], CandidateStats]:
    """Calculate code and voltage statistics for every candidate."""
    frames = tuple((int(frame) & 4294967295 for frame in raw_frames))
    if not frames:
        raise ValueError('raw_frames must not be empty')
    result: Dict[Tuple[str, str], CandidateStats] = {}
    for field in fields:
        codes = [extract_field(frame, field) for frame in frames]
        code_min = min(codes)
        code_max = max(codes)
        code_mean = statistics.mean(codes)
        code_median = statistics.median(codes)
        code_std = statistics.pstdev(codes) if len(codes) > 1 else 0.0
        code_unique = len(set(codes))
        for encoding in encodings:
            voltages = [code_to_voltage(code, encoding) for code in codes]
            result[field, encoding] = CandidateStats(field=field, encoding=encoding, count=len(codes), code_min=code_min, code_max=code_max, code_mean=code_mean, code_median=code_median, code_std=code_std, code_unique=code_unique, voltage_min=min(voltages), voltage_max=max(voltages), voltage_mean=statistics.mean(voltages), voltage_median=statistics.median(voltages), voltage_std=statistics.pstdev(voltages) if len(voltages) > 1 else 0.0, first_voltage=voltages[0], last_voltage=voltages[-1])
    return result

def frame_activity(raw_frames: Sequence[int], fields: Sequence[str]=FRAME_FIELDS) -> Dict[str, FrameActivity]:
    frames = tuple((int(frame) & 4294967295 for frame in raw_frames))
    if not frames:
        raise ValueError('raw_frames must not be empty')
    result: Dict[str, FrameActivity] = {}
    for field in fields:
        values = [extract_field(frame, field) for frame in frames]
        result[field] = FrameActivity(field=field, unique_values=len(set(values)), code_span=max(values) - min(values), code_std=statistics.pstdev(values) if len(values) > 1 else 0.0, first_value=values[0], last_value=values[-1])
    return result

def _linear_fit(xs: Sequence[float], ys: Sequence[float]) -> Tuple[float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError('linear fit requires at least two paired samples')
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    var_x = sum(((x - mean_x) ** 2 for x in xs))
    if var_x <= 1e-15:
        return (0.0, mean_y)
    cov = sum(((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)))
    slope = cov / var_x
    intercept = mean_y - slope * mean_x
    return (slope, intercept)

def rank_candidates(captures: Sequence[FrameCapture], *, fields: Sequence[str]=FRAME_FIELDS, encodings: Sequence[str]=ENCODINGS, minimum_reference_span_v: float=0.05, minimum_dynamic_code_span: int=4) -> List[CandidateScore]:
    """Rank frame-field/encoding candidates against DMM reference voltages.

    The ranking is designed for at least two captures with different known
    ADS differential voltages.  A candidate must both fit the references and
    show measurable code movement; otherwise it is marked ineligible.
    """
    reference_pairs = []
    for capture in captures:
        reference = expected_reference_voltage(capture)
        if reference is None or not math.isfinite(reference):
            continue
        reference_pairs.append((capture, float(reference)))
    if not reference_pairs:
        return []
    xs = [reference for _, reference in reference_pairs]
    reference_span = max(xs) - min(xs)
    all_stats = {(capture.label, field, encoding): stats for capture in captures for (field, encoding), stats in candidate_stats(capture.raw_frames, fields=fields, encodings=encodings).items()}
    scores: List[CandidateScore] = []
    for field in fields:
        for encoding in encodings:
            ys = [all_stats[capture.label, field, encoding].voltage_mean for capture, _ in reference_pairs]
            dynamic_values: List[int] = []
            for capture in captures:
                dynamic_values.extend((extract_field(frame, field) for frame in capture.raw_frames))
            dynamic_span = max(dynamic_values) - min(dynamic_values)
            measured_span = max(ys) - min(ys)
            try:
                slope, intercept = _linear_fit(xs, ys)
            except ValueError:
                slope, intercept = (0.0, statistics.mean(ys) if ys else 0.0)
            residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
            rmse = math.sqrt(sum((value * value for value in residuals)) / len(residuals))
            max_abs_error = max((abs(value) for value in residuals))
            reasons = []
            eligible = True
            if reference_span < minimum_reference_span_v:
                eligible = False
                reasons.append('reference span too small')
            if dynamic_span < minimum_dynamic_code_span:
                eligible = False
                reasons.append('code does not move')
            if not math.isfinite(slope):
                eligible = False
                reasons.append('invalid slope')
            if eligible:
                if abs(slope - 1.0) > 0.6:
                    eligible = False
                    reasons.append('fitted slope far from 1')
            if eligible:
                score = rmse + 0.1 * abs(slope - 1.0)
                reasons.append('eligible')
            else:
                score = float('inf')
            scores.append(CandidateScore(field=field, encoding=encoding, reference_count=len(reference_pairs), reference_span_v=reference_span, measured_span_v=measured_span, slope=slope, intercept_v=intercept, rmse_v=rmse, max_abs_error_v=max_abs_error, dynamic_code_span=dynamic_span, score=score, eligible=eligible, reason='; '.join(reasons)))
    scores.sort(key=lambda item: (not item.eligible, item.score, item.rmse_v, item.max_abs_error_v))
    return scores

def diagnose_captures(captures: Sequence[FrameCapture]) -> Dict[str, object]:
    """Return a human-readable diagnosis of frame activity and candidate fit."""
    if not captures:
        return {'status': 'no_captures', 'message': 'No frame captures were supplied.'}
    all_raw = [frame for capture in captures for frame in capture.raw_frames]
    raw_unique = len(set(all_raw))
    raw_span = max(all_raw) - min(all_raw)
    references = [expected_reference_voltage(capture) for capture in captures]
    references = [value for value in references if value is not None]
    reference_span = max(references) - min(references) if references else 0.0
    activity_all: Dict[str, FrameActivity] = {}
    for field in FRAME_FIELDS:
        values = [extract_field(frame, field) for frame in all_raw]
        activity_all[field] = FrameActivity(field=field, unique_values=len(set(values)), code_span=max(values) - min(values), code_std=statistics.pstdev(values) if len(values) > 1 else 0.0, first_value=values[0], last_value=values[-1])
    ranking = rank_candidates(captures)
    recommended = ranking[0] if ranking and ranking[0].eligible else None
    dynamic_fields = sorted(activity_all.values(), key=lambda item: item.code_span, reverse=True)
    if raw_unique == 1 or raw_span == 0:
        status = 'spi_frame_frozen'
        message = 'RX_REG did not change at all. Suspect ADS/SPI lock, missing SDO toggling, or a stalled read state machine.'
    elif reference_span == 0.0:
        status = 'insufficient_reference_span'
        message = 'The frame changes, but the DMM reference voltages did not span enough to identify the correct field/encoding.'
    elif recommended is None:
        status = 'ambiguous'
        message = 'Frame activity exists, but no candidate fits the DMM references with a slope near one.'
    elif recommended.field == 'low16':
        status = 'low16_selected'
        message = 'The lower 16 bits are the likely ADC code. The PL currently uses RX_REG[31:16] in its window path.'
    elif recommended.field == 'high16':
        status = 'high16_selected'
        message = 'The upper 16 bits are the likely ADC code. If the result is still inconsistent, inspect SPI timing and frame validity.'
    else:
        status = 'bit_alignment_selected'
        message = 'A shifted or byte-swapped field fits best. The SPI sample edge or endianness needs correction.'
    return {'status': status, 'message': message, 'raw_unique': raw_unique, 'raw_span': raw_span, 'reference_span_v': reference_span, 'activity': {name: activity.__dict__ for name, activity in activity_all.items()}, 'dynamic_fields': [item.field for item in dynamic_fields], 'recommended': None if recommended is None else recommended.__dict__, 'ranking': [item.__dict__ for item in ranking]}

class Ads8681FrameMonitor:
    """Read complete RX frames and, optionally, trigger frontend ranges."""

    def __init__(self, mmio, sample_interval_s: float=0.002):
        if sample_interval_s <= 0.0:
            raise ValueError('sample_interval_s must be positive')
        self.mmio = mmio
        self.sample_interval_s = float(sample_interval_s)

    def read_raw_frame(self) -> int:
        return int(self.mmio.read(RAW_ADC_REG)) & 4294967295

    def capture_raw(self, *, label: str, sample_count: int=200, interval_s: Optional[float]=None, discard_first: int=5, range_index: Optional[int]=None, reverse: bool=False) -> FrameCapture:
        sample_count = int(sample_count)
        discard_first = int(discard_first)
        if sample_count <= 0:
            raise ValueError('sample_count must be positive')
        if discard_first < 0:
            raise ValueError('discard_first must be non-negative')
        interval = self.sample_interval_s if interval_s is None else float(interval_s)
        if interval <= 0.0:
            raise ValueError('interval_s must be positive')
        for _ in range(discard_first):
            self.read_raw_frame()
            time.sleep(interval)
        frames: List[int] = []
        timestamps: List[float] = []
        for _ in range(sample_count):
            frames.append(self.read_raw_frame())
            timestamps.append(time.monotonic())
            time.sleep(interval)
        return FrameCapture(label=str(label), raw_frames=tuple(frames), timestamps_s=tuple(timestamps), range_index=range_index, reverse=bool(reverse))

    def capture_range(self, frontend, range_index: int, *, label: Optional[str]=None, reverse: bool=False, enable_current: bool=True, settle_s: float=1.0, sample_count: int=200, interval_s: Optional[float]=None, keep_current_on: bool=False) -> FrameCapture:
        if settle_s < 0.0:
            raise ValueError('settle_s must be non-negative')
        label = label or f'RANGE{int(range_index)}_reverse_{bool(reverse)}'
        current_on = False
        frontend.safe_off()
        try:
            frontend.configure(int(range_index), reverse=bool(reverse), enable_current=bool(enable_current))
            current_on = bool(enable_current)
            if settle_s > 0.0:
                time.sleep(float(settle_s))
            capture = self.capture_raw(label=label, sample_count=sample_count, interval_s=interval_s, range_index=int(range_index), reverse=bool(reverse))
        finally:
            if not keep_current_on:
                frontend.safe_off()
                current_on = False
        return capture

def format_candidate_table(scores: Sequence[CandidateScore], limit: int=12) -> str:
    """Return a compact text table for notebook display."""
    lines = ['eligible | field               | encoding                 | RMSE(mV) | slope  | span code | reason', '---------+---------------------+--------------------------+----------+--------+-----------+-----------------------------']
    for item in list(scores)[:int(limit)]:
        lines.append('%-8s | %-19s | %-24s | %8.3f | %6.3f | %9d | %s' % (str(item.eligible), item.field, item.encoding, item.rmse_v * 1000.0, item.slope, item.dynamic_code_span, item.reason))
    return '\n'.join(lines)

def format_frame_report(capture: FrameCapture, limit: int=8) -> str:
    """Return a compact report for one capture."""
    stats = candidate_stats(capture.raw_frames)
    lines = [f'capture={capture.label} samples={capture.sample_count}', f'reference_voltage_v={expected_reference_voltage(capture)}', 'field                    | encoding                 | mean(V) | min(V) | max(V) | code span', '-------------------------+--------------------------+---------+--------+--------+----------']
    ordered = sorted(stats.items(), key=lambda item: (item[1].voltage_std, item[1].code_std, item[1].field, item[1].encoding))
    for (field, encoding), item in ordered[:int(limit)]:
        lines.append('%-24s | %-24s | %7.4f | %6.4f | %6.4f | %9d' % (field, encoding, item.voltage_mean, item.voltage_min, item.voltage_max, item.code_max - item.code_min))
    return '\n'.join(lines)
