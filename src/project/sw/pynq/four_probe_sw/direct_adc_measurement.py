# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

'Native ADS8681 capture and one forward/reverse pair. ADC_IN=(code-32768)*5.12/32768 V; probe voltage removes2.5V common-mode and the per-range offset, without additional gain. Calibrated currents/offsets are retained from the baseline and have not been revalidated for this revision.'
from __future__ import annotations
from dataclasses import dataclass, replace
from statistics import fmean, median, pstdev, stdev
from time import monotonic, sleep
from typing import Callable, Optional, Sequence, Tuple
import math
DIRECT_ADC_MEASUREMENT_VERSION = 19
ADC_FULL_SCALE_V = 5.12
ADC_CODE_MID = 32768
ADC_CODE_FULL_SCALE = 65536
ADC_LSB_V = ADC_FULL_SCALE_V / ADC_CODE_MID
ADC_FRONTEND_OFFSET_V = 2.5
DEFAULT_VALID_SAMPLE_COUNT = 300
DEFAULT_SAMPLE_INTERVAL_S = 0.002
DEFAULT_DISCARD_FIRST = 5
DEFAULT_RANGE_SETTLE_S = 1.0
DEFAULT_CAPTURE_TIMEOUT_S = 10.0
DEFAULT_ADC_CONFIG_SETTLE_S = 0.1
DEFAULT_ADC_INPUT_MIN_V = 0.05
DEFAULT_ADC_INPUT_MAX_V = 5.0
DEFAULT_PROBE_ABS_MIN_V = 0.05
DEFAULT_PROBE_ABS_MAX_V = 2.0
DEFAULT_MAD_K = 5.0
RANGE_CURRENT_NOMINAL_A = (0.0001, 0.001, 0.01, 0.1)
DEFAULT_FORWARD_CURRENT_BY_RANGE_A = (0.0001067675194836567, 0.0009496196325972225, 0.008955403978230587, 0.08657217119232472)
DEFAULT_REVERSE_CURRENT_BY_RANGE_A = (0.00010153005040316653, 0.0008840039433859044, 0.008277879981034422, 0.08088461584683777)
DEFAULT_ZERO_OFFSET_SAMPLES = 200
DEFAULT_ZERO_OFFSET_SETTLE_S = 0.5
DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V = (-0.000608771971007042, 9.523915436486045e-05, 0.0008907877094972427, 0.0)

def calibrated_current_for_range_a(range_index):
    """Return the default forward excitation current for one range."""
    index = int(range_index)
    if index < 0 or index >= len(DEFAULT_FORWARD_CURRENT_BY_RANGE_A):
        raise ValueError('range_index must be 0, 1, 2 or 3')
    return DEFAULT_FORWARD_CURRENT_BY_RANGE_A[index]
RESISTIVITY_RANGE_TABLE = ((0.03, 3, 0.1), (0.3, 2, 0.01), (30.0, 1, 0.001), (float('inf'), 0, 0.0001))

def range_index_for_resistivity(rho_ohm_cm):
    """Return (range_index, nominal_current_a) from RESISTIVITY_RANGE_TABLE."""
    rho = _require_finite(rho_ohm_cm, 'rho_ohm_cm')
    if rho < 0.0:
        raise ValueError('rho_ohm_cm must be non-negative')
    for upper_bound, range_index, current_a in RESISTIVITY_RANGE_TABLE:
        if rho < upper_bound:
            return (int(range_index), float(current_a))
    return (0, 0.0001)

def range_index_for_voltage_window(measured, *, v_min, v_max, feasible=None):
    """Pick the excitation range from a measured probe-voltage window.

    ``measured`` is a sequence of ``(range_index, abs_probe_voltage_v)`` pairs
    produced by the pilot sweep.  The rule replaces the rho -> table lookup:

    * inside ``[v_min, v_max]`` take the LARGEST voltage (best signal-to-noise
      while staying clear of the validity ceiling);
    * otherwise take the closest one by log-distance and say so in the note.

    ``feasible`` (optional) is the set of range indices whose rho coefficient
    fits the PL's fixed-point window.  It is a SEPARATE constraint, not a
    refinement of the voltage window: K is proportional to the sample thickness,
    so for a THIN sample the range with the best voltage can be one the PL will
    refuse (900 nm at 10 mA gives K_q = 214, far below K_Q_MIN = 8192).  When the
    feasible subset is non-empty only those ranges are considered; when it is
    EMPTY the voltage rule is applied to every range and the note is marked
    ``K-INFEASIBLE`` so the operator can see in advance why the run will fail
    closed at the PL stage.

    Returns ``(range_index, note)``.  The note always starts with ``window:``
    so a reader can tell which rule decided the range.
    """
    items = []
    for index, voltage in measured:
        value = abs(float(voltage))
        if not math.isfinite(value) or value <= 0.0:
            continue
        items.append((int(index), value))
    if not items:
        raise ValueError('no usable probe voltage for range selection')
    lo = float(v_min)
    hi = float(v_max)
    if not 0.0 < lo < hi or not math.isfinite(lo) or (not math.isfinite(hi)):
        raise ValueError('voltage window must satisfy 0 < v_min < v_max')
    tag = ''
    if feasible is not None:
        allowed = set((int(index) for index in feasible))
        kept = [item for item in items if item[0] in allowed]
        if kept:
            if len(kept) != len(items):
                tag = 'K-feasible '
            items = kept
        else:
            tag = 'K-INFEASIBLE '
    inside = [item for item in items if lo <= item[1] <= hi]
    if inside:
        index, value = max(inside, key=lambda item: item[1])
        return (index, 'window:%sV=%.6g in [%.4g, %.4g] -> R%d' % (tag, value, lo, hi, index))
    center = math.sqrt(lo * hi)
    index, value = min(items, key=lambda item: (abs(math.log(item[1] / center)), -item[1]))
    position = 'below' if value < lo else 'above'
    return (index, 'window:%sV=%.6g %s [%.4g, %.4g] -> R%d (nearest)' % (tag, value, position, lo, hi, index))

class DirectMeasurementError(RuntimeError):
    """Base class for direct measurement failures."""

class MeasurementAbortedError(DirectMeasurementError):
    """Raised when a PL fault or reset request must abort acquisition."""

class CaptureTimeoutError(DirectMeasurementError):
    """Raised when not enough valid ADC samples were captured."""

class RangeSelectionError(DirectMeasurementError):
    """Raised when no current range satisfies the selection criteria."""

@dataclass(frozen=True)
class ProbeCapture:
    """Raw and decoded samples from one polarity/range capture."""
    label: str
    raw_frames: Tuple[int, ...]
    timestamps_s: Tuple[float, ...]
    probe_voltages_v: Tuple[float, ...]
    attempted_sample_count: int
    rejected_sample_count: int
    valid_sample_count_override: Optional[int] = None
    min_valid_code: Optional[int] = None
    max_valid_code: Optional[int] = None

    @property
    def valid_sample_count(self) -> int:
        if self.valid_sample_count_override is not None:
            return int(self.valid_sample_count_override)
        return len(self.probe_voltages_v)

    @property
    def sample_count(self) -> int:
        return self.attempted_sample_count

@dataclass(frozen=True)
class RangeMeasurement:
    """Filtered result for one current range and one polarity."""
    range_index: int
    reverse: bool
    current_a: float
    capture: ProbeCapture
    probe_voltage_offset_v: float
    raw_filtered_probe_voltage_v: float
    raw_median_probe_voltage_v: float
    raw_std_probe_voltage_v: float
    filtered_probe_voltage_v: float
    median_probe_voltage_v: float
    std_probe_voltage_v: float
    resistance_ohm: float
    eligible: bool
    reason: str
    min_code: Optional[int] = None
    max_code: Optional[int] = None

@dataclass(frozen=True)
class BidirectionalMeasurement:
    """Forward/reverse result for a fixed current range."""
    range_index: int
    current_a: float
    forward_current_a: float
    reverse_current_a: float
    equivalent_current_a: float
    forward_resistance_ohm: float
    reverse_resistance_ohm: float
    forward: RangeMeasurement
    reverse: RangeMeasurement
    combined_probe_voltage_v: float
    combined_resistance_ohm: float
    combined_abs_probe_voltage_v: float
    combined_abs_resistance_ohm: float
    forward_reverse_delta_v: float
    polarity_same_sign: bool
    signed_sum_v: float
    zero_offset_forward_v: Optional[float] = None
    zero_offset_reverse_v: Optional[float] = None
    pair_values_v: Tuple[float, ...] = ()
    pair_std_v: Optional[float] = None
    pair_repeats: int = 1

def _sleep_with_abort(duration_s, abort_check, poll_interval_s=0.01):
    """Sleep in short slices while polling an optional abort callback."""
    duration_s = float(duration_s)
    if duration_s <= 0.0:
        return
    if abort_check is None:
        sleep(duration_s)
        return
    poll_interval_s = max(0.0001, min(float(poll_interval_s), duration_s))
    deadline = monotonic() + duration_s
    while True:
        abort_check()
        remaining_s = deadline - monotonic()
        if remaining_s <= 0.0:
            return
        sleep(min(poll_interval_s, remaining_s))

def _require_finite(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    return value

def _require_positive(value: float, name: str) -> float:
    value = _require_finite(value, name)
    if value <= 0.0:
        raise ValueError(f'{name} must be positive')
    return value

def raw_frame_to_code(raw_frame: int) -> int:
    """Extract the ADS conversion code from RX_REG[31:16]."""
    return int(raw_frame) >> 16 & 65535

def code_to_adc_voltage_v(code: int) -> float:
    """Convert a straight-binary ADS code to ADC-side voltage."""
    return ((int(code) & 65535) - ADC_CODE_MID) * ADC_LSB_V

def adc_voltage_to_probe_voltage_v(adc_voltage_v: float) -> float:
    """Remove the 2.5 V analog-frontend common-mode offset."""
    return float(adc_voltage_v) - ADC_FRONTEND_OFFSET_V

def probe_voltage_to_code(probe_voltage_v: float) -> int:
    """Inverse mapping used by simulation and tests."""
    adc_voltage_v = float(probe_voltage_v) + ADC_FRONTEND_OFFSET_V
    code = int(round(adc_voltage_v / ADC_LSB_V + ADC_CODE_MID))
    return max(0, min(65535, code))

def filter_probe_voltages(values: Sequence[float], mad_k: float=DEFAULT_MAD_K) -> dict:
    """Return robust median/MAD-filtered voltage statistics."""
    samples = tuple((float(value) for value in values))
    if not samples:
        raise ValueError('at least one voltage sample is required')
    if any((not math.isfinite(value) for value in samples)):
        raise ValueError('voltage samples must be finite')
    mad_k = _require_positive(mad_k, 'mad_k')
    center = float(median(samples))
    deviations = tuple((abs(value - center) for value in samples))
    mad = float(median(deviations))
    if mad > 0.0:
        threshold = mad_k * 1.4826 * mad
        kept = tuple((value for value in samples if abs(value - center) <= threshold))
    else:
        sigma = float(pstdev(samples)) if len(samples) > 1 else 0.0
        threshold = 3.0 * sigma if sigma > 0.0 else 0.0
        kept = tuple((value for value in samples if abs(value - center) <= threshold)) if threshold > 0.0 else samples
    if not kept:
        kept = samples
    return {'filtered': float(fmean(kept)), 'median': center, 'mean': float(fmean(samples)), 'std': float(pstdev(kept)) if len(kept) > 1 else 0.0, 'minimum': float(min(samples)), 'maximum': float(max(samples)), 'mad': mad, 'kept_count': len(kept), 'sample_count': len(samples)}

def capture_valid_probe_samples(monitor, *, label: str, sample_count: int=DEFAULT_VALID_SAMPLE_COUNT, interval_s: float=DEFAULT_SAMPLE_INTERVAL_S, discard_first: int=DEFAULT_DISCARD_FIRST, timeout_s: float=DEFAULT_CAPTURE_TIMEOUT_S, adc_input_min_v: float=DEFAULT_ADC_INPUT_MIN_V, adc_input_max_v: float=DEFAULT_ADC_INPUT_MAX_V, probe_abs_min_v: float=DEFAULT_PROBE_ABS_MIN_V, require_count: bool=True, abort_check: Optional[Callable[[], None]]=None) -> ProbeCapture:
    """Capture valid samples until the requested count or timeout is reached.

    Validity is checked on the ADC-side voltage before the 2.5 V offset is
    removed. This prevents using saturated or out-of-range conversions.
    """
    sample_count = int(sample_count)
    discard_first = int(discard_first)
    if sample_count <= 0:
        raise ValueError('sample_count must be positive')
    if discard_first < 0:
        raise ValueError('discard_first must be non-negative')
    interval_s = _require_positive(interval_s, 'interval_s')
    timeout_s = _require_positive(timeout_s, 'timeout_s')
    adc_input_min_v = _require_finite(adc_input_min_v, 'adc_input_min_v')
    adc_input_max_v = _require_finite(adc_input_max_v, 'adc_input_max_v')
    probe_abs_min_v = _require_finite(probe_abs_min_v, 'probe_abs_min_v')
    if adc_input_max_v <= adc_input_min_v:
        raise ValueError('adc_input_max_v must be greater than adc_input_min_v')
    if probe_abs_min_v < 0.0:
        raise ValueError('probe_abs_min_v must be non-negative')
    for _ in range(discard_first):
        if abort_check is not None:
            abort_check()
        monitor.read_raw_frame()
        sleep(interval_s)
    raw_frames = []
    timestamps = []
    voltages = []
    valid_codes = []
    rejected = 0
    deadline = monotonic() + timeout_s
    while len(voltages) < sample_count and monotonic() < deadline:
        if abort_check is not None:
            abort_check()
        raw = int(monitor.read_raw_frame()) & 4294967295
        timestamp = monotonic()
        code = raw_frame_to_code(raw)
        adc_v = code_to_adc_voltage_v(code)
        probe_v = adc_voltage_to_probe_voltage_v(adc_v)
        raw_frames.append(raw)
        timestamps.append(timestamp)
        if adc_input_min_v <= adc_v <= adc_input_max_v and abs(probe_v) >= probe_abs_min_v:
            voltages.append(probe_v)
            valid_codes.append(code)
        else:
            rejected += 1
        sleep(interval_s)
    capture = ProbeCapture(label=str(label), raw_frames=tuple(raw_frames), timestamps_s=tuple(timestamps), probe_voltages_v=tuple(voltages), attempted_sample_count=len(raw_frames), rejected_sample_count=rejected, min_valid_code=min(valid_codes) if valid_codes else None, max_valid_code=max(valid_codes) if valid_codes else None)
    if require_count and len(voltages) < sample_count:
        raise CaptureTimeoutError('only %d of %d valid samples in %.3f s' % (len(voltages), sample_count, timeout_s))
    return capture

def _range_measurement_from_snapshot(snapshot, *, range_index: int, reverse: bool, current_a: float, probe_voltage_offset_v: float, probe_abs_min_v: float, probe_abs_max_v: float) -> RangeMeasurement:
    """Convert one PL aggregate snapshot into a RangeMeasurement."""
    valid_count = int(getattr(snapshot, 'valid_count'))
    rx_update_count = int(getattr(snapshot, 'rx_update_count'))
    minimum_valid_samples = int(getattr(snapshot, 'minimum_valid_samples', 1))
    strict_valid_count = bool(getattr(snapshot, 'strict_valid_count', True))
    overflow = bool(getattr(snapshot, 'overflow', False))
    snapshot_min_code = getattr(snapshot, 'min_code', None)
    snapshot_max_code = getattr(snapshot, 'max_code', None)
    snapshot_min_code = None if snapshot_min_code is None else int(snapshot_min_code)
    snapshot_max_code = None if snapshot_max_code is None else int(snapshot_max_code)

    def empty_result(reason):
        capture = ProbeCapture(label='pl_stats_bank%d_%s' % (range_index, 'reverse' if reverse else 'forward'), raw_frames=(), timestamps_s=(), probe_voltages_v=(), attempted_sample_count=max(0, rx_update_count), rejected_sample_count=max(0, rx_update_count - valid_count), valid_sample_count_override=max(0, valid_count), min_valid_code=snapshot_min_code if valid_count > 0 else None, max_valid_code=snapshot_max_code if valid_count > 0 else None)
        return RangeMeasurement(range_index=int(range_index), reverse=bool(reverse), current_a=current_a, capture=capture, probe_voltage_offset_v=float(probe_voltage_offset_v), raw_filtered_probe_voltage_v=0.0, raw_median_probe_voltage_v=0.0, raw_std_probe_voltage_v=0.0, filtered_probe_voltage_v=0.0, median_probe_voltage_v=0.0, std_probe_voltage_v=0.0, resistance_ohm=0.0, eligible=False, reason=reason)
    if rx_update_count <= 0:
        if strict_valid_count:
            raise DirectMeasurementError('PL statistics window received no ADC updates')
        return empty_result('PL statistics window received no ADC updates')
    if valid_count <= 0:
        if strict_valid_count:
            raise DirectMeasurementError('PL statistics window contains no valid samples')
        return empty_result('PL statistics window contains no valid samples')
    if overflow and strict_valid_count:
        raise DirectMeasurementError('PL statistics overflow')
    if valid_count < minimum_valid_samples and strict_valid_count:
        raise DirectMeasurementError('PL statistics valid_count=%d below minimum=%d' % (valid_count, minimum_valid_samples))
    average_code = float(snapshot.average_code)
    std_code = float(snapshot.std_code)
    raw_filtered_v = adc_voltage_to_probe_voltage_v(code_to_adc_voltage_v(average_code))
    filtered_v = raw_filtered_v - probe_voltage_offset_v
    std_v = std_code * (ADC_FULL_SCALE_V / ADC_CODE_MID)
    resistance_ohm = filtered_v / current_a if current_a else float('nan')
    eligible = True
    if overflow:
        eligible = False
        reason = 'PL statistics overflow'
    elif valid_count < minimum_valid_samples:
        eligible = False
        reason = 'PL statistics valid sample count below minimum'
    elif abs(filtered_v) < probe_abs_min_v:
        eligible = False
        reason = 'filtered voltage below minimum'
    elif abs(filtered_v) > probe_abs_max_v:
        eligible = False
        reason = 'filtered voltage above maximum'
    else:
        reason = 'eligible'
    min_code = snapshot_min_code
    max_code = snapshot_max_code
    capture = ProbeCapture(label='pl_stats_bank%d_%s' % (range_index, 'reverse' if reverse else 'forward'), raw_frames=(), timestamps_s=(), probe_voltages_v=(), attempted_sample_count=rx_update_count, rejected_sample_count=max(0, rx_update_count - valid_count), valid_sample_count_override=valid_count, min_valid_code=min_code, max_valid_code=max_code)
    return RangeMeasurement(range_index=int(range_index), reverse=bool(reverse), current_a=current_a, capture=capture, probe_voltage_offset_v=float(probe_voltage_offset_v), raw_filtered_probe_voltage_v=raw_filtered_v, raw_median_probe_voltage_v=raw_filtered_v, raw_std_probe_voltage_v=std_v, filtered_probe_voltage_v=filtered_v, median_probe_voltage_v=filtered_v, std_probe_voltage_v=std_v, resistance_ohm=resistance_ohm, eligible=eligible, reason=reason, min_code=min_code, max_code=max_code)

def measure_range_once(frontend, monitor, range_index: int, *, reverse: bool=False, sample_count: int=DEFAULT_VALID_SAMPLE_COUNT, interval_s: float=DEFAULT_SAMPLE_INTERVAL_S, discard_first: int=DEFAULT_DISCARD_FIRST, settle_s: float=DEFAULT_RANGE_SETTLE_S, timeout_s: float=DEFAULT_CAPTURE_TIMEOUT_S, configure_timeout_s: float=2.0, adc_config_settle_s: float=DEFAULT_ADC_CONFIG_SETTLE_S, adc_input_min_v: float=DEFAULT_ADC_INPUT_MIN_V, adc_input_max_v: float=DEFAULT_ADC_INPUT_MAX_V, probe_abs_min_v: float=DEFAULT_PROBE_ABS_MIN_V, probe_abs_max_v: float=DEFAULT_PROBE_ABS_MAX_V, require_count: bool=True, probe_voltage_offset_v: Optional[float]=None, abort_check: Optional[Callable[[], None]]=None, capture_source: Optional[Callable[[int, bool, bool], object]]=None, enable_current: bool=True) -> RangeMeasurement:
    """Configure one range/polarity, capture samples, and safely turn off.

    ``require_count=True`` (default) makes a capture that produced fewer than
    ``sample_count`` valid samples raise CaptureTimeoutError.  The pilot range
    sweep passes False because a partial sample set is still usable there.
    """
    range_index = int(range_index)
    if range_index not in (0, 1, 2, 3):
        raise ValueError('range_index must be 0, 1, 2 or 3')
    settle_s = _require_finite(settle_s, 'settle_s')
    adc_config_settle_s = _require_finite(adc_config_settle_s, 'adc_config_settle_s')
    if settle_s < 0.0 or adc_config_settle_s < 0.0:
        raise ValueError('settle times must be non-negative')
    if probe_voltage_offset_v is None:
        probe_voltage_offset_v = DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V[range_index]
    probe_voltage_offset_v = _require_finite(probe_voltage_offset_v, 'probe_voltage_offset_v')
    frontend.safe_off()
    stats_snapshot = None
    try:
        if abort_check is not None:
            abort_check()
        status = frontend.configure(range_index, reverse=bool(reverse), enable_current=bool(enable_current), timeout_s=configure_timeout_s, reconfigure_adc_before=False)
        if hasattr(frontend, 'status'):
            status = frontend.status()
            if bool(status.get('polarity_reversed')) != bool(reverse):
                raise DirectMeasurementError('frontend polarity status mismatch: requested=%s status=%r' % (bool(reverse), status))
            current_active = bool(status.get('current_active'))
            if enable_current and (not current_active):
                raise DirectMeasurementError('frontend current is not active after configure: %r' % status)
            if not enable_current and current_active:
                raise DirectMeasurementError('frontend current is still active during a zero-offset capture: %r' % status)
        if abort_check is not None:
            abort_check()
        if settle_s > 0.0:
            _sleep_with_abort(settle_s, abort_check)
        if abort_check is not None:
            abort_check()
        frontend.reconfigure_adc(timeout_s=configure_timeout_s)
        if adc_config_settle_s > 0.0:
            _sleep_with_abort(adc_config_settle_s, abort_check)
        if capture_source is not None:
            stats_snapshot = capture_source(int(range_index), bool(reverse), bool(require_count))
            capture = None
        else:
            capture = capture_valid_probe_samples(monitor, label='range%d_%s' % (range_index, 'reverse' if reverse else 'forward'), sample_count=sample_count, interval_s=interval_s, discard_first=discard_first, timeout_s=timeout_s, adc_input_min_v=adc_input_min_v, adc_input_max_v=adc_input_max_v, probe_abs_min_v=probe_abs_min_v, require_count=require_count, abort_check=abort_check)
    finally:
        frontend.safe_off()
    current_a = calibrated_current_for_range_a(range_index)
    if stats_snapshot is not None:
        return _range_measurement_from_snapshot(stats_snapshot, range_index=range_index, reverse=bool(reverse), current_a=current_a, probe_voltage_offset_v=probe_voltage_offset_v, probe_abs_min_v=probe_abs_min_v, probe_abs_max_v=probe_abs_max_v)
    if capture.valid_sample_count > 0:
        raw_stats = filter_probe_voltages(capture.probe_voltages_v)
        corrected_values = tuple((value - probe_voltage_offset_v for value in capture.probe_voltages_v))
        stats = filter_probe_voltages(corrected_values)
        raw_filtered_v = raw_stats['filtered']
        raw_median_v = raw_stats['median']
        raw_std_v = raw_stats['std']
        filtered_v = stats['filtered']
        median_v = stats['median']
        std_v = stats['std']
        resistance_ohm = filtered_v / current_a if current_a else float('nan')
        eligible = True
        if abs(filtered_v) < probe_abs_min_v:
            eligible = False
            reason = 'filtered voltage below minimum'
        elif abs(filtered_v) > probe_abs_max_v:
            eligible = False
            reason = 'filtered voltage above maximum'
        else:
            reason = 'eligible'
    else:
        raw_filtered_v = 0.0
        raw_median_v = 0.0
        raw_std_v = 0.0
        filtered_v = 0.0
        median_v = 0.0
        std_v = 0.0
        resistance_ohm = 0.0
        eligible = False
        reason = 'no valid samples captured'
    return RangeMeasurement(range_index=range_index, reverse=bool(reverse), current_a=current_a, capture=capture, probe_voltage_offset_v=probe_voltage_offset_v, raw_filtered_probe_voltage_v=raw_filtered_v, raw_median_probe_voltage_v=raw_median_v, raw_std_probe_voltage_v=raw_std_v, filtered_probe_voltage_v=filtered_v, median_probe_voltage_v=median_v, std_probe_voltage_v=std_v, resistance_ohm=resistance_ohm, eligible=eligible, reason=reason, min_code=capture.min_valid_code, max_code=capture.max_valid_code)

def _combine_pilot_pair(forward, reverse, *, probe_abs_min_v, probe_abs_max_v):
    """Offset-cancelled pilot candidate: 0.5*(Vf + Vr), 2026-10-17.

    The pilot used to report the FORWARD-ONLY reading, which on the GaN bench is almost
    entirely the contact offset E (0.04 .. 0.8 V while the signal is ~15 mV), so the rho
    estimate behind the range rule was noise -- 4.3e-3 .. 1361 ohm*cm across runs, i.e.
    the range was drawn at random.  The two-polarity pair cancels E exactly
    (Vf = If*R + E, Vr = Ir*R - E  =>  R = (Vf + Vr)/(If + Ir)): the same combination the
    measurement itself now uses.

    The candidate keeps the FORWARD half's diagnostics (median, std, codes, capture) and
    replaces the value the caller decides on: ``filtered_probe_voltage_v`` becomes the
    signal, ``resistance_ohm`` follows it, and ``eligible`` is re-judged against
    [probe_abs_min_v, probe_abs_max_v] -- so a narrow software window now selects by
    SIGNAL, which is what that window was always meant to describe.

    Two conventions worth stating, so nobody reads them as exact:
    * ``resistance_ohm`` here is |0.5*(Vf+Vr)| / If (the forward calibrated current only),
      while the measurement path divides by (If + Ir).  The two differ by If/Ir (~8% on
      the deployed tables), which cannot move a range decision -- but it makes this a
      SELECTION aid, never a number to report.
    * Both halves receive the same per-range TABLE offset.  It cancels inside the pair, so
      this only matters if ② is switched back on with a large, polarity-dependent zero.
    """
    signal_v = 0.5 * (float(forward.filtered_probe_voltage_v) + float(reverse.filtered_probe_voltage_v))
    both_eligible = bool(forward.eligible) and bool(reverse.eligible)
    in_window = float(probe_abs_min_v) <= abs(signal_v) <= float(probe_abs_max_v)
    if not bool(forward.eligible):
        reason = 'pilot pair: %s' % (forward.reason,)
    elif not bool(reverse.eligible):
        reason = 'pilot pair: %s' % (reverse.reason,)
    elif not in_window:
        reason = 'pilot pair signal outside the window'
    else:
        reason = 'eligible'
    current_a = float(forward.current_a)
    return replace(forward, filtered_probe_voltage_v=signal_v, resistance_ohm=abs(signal_v) / current_a if current_a > 0.0 else 0.0, eligible=bool(both_eligible and in_window), reason=reason)

def select_current_range(frontend, monitor, *, range_indices: Sequence[int]=(0, 1, 2, 3), sample_count: int=DEFAULT_VALID_SAMPLE_COUNT, interval_s: float=DEFAULT_SAMPLE_INTERVAL_S, discard_first: int=DEFAULT_DISCARD_FIRST, settle_s: float=DEFAULT_RANGE_SETTLE_S, timeout_s: float=DEFAULT_CAPTURE_TIMEOUT_S, configure_timeout_s: float=2.0, adc_config_settle_s: float=DEFAULT_ADC_CONFIG_SETTLE_S, adc_input_min_v: float=DEFAULT_ADC_INPUT_MIN_V, adc_input_max_v: float=DEFAULT_ADC_INPUT_MAX_V, probe_abs_min_v: float=DEFAULT_PROBE_ABS_MIN_V, probe_abs_max_v: float=DEFAULT_PROBE_ABS_MAX_V, probe_voltage_offset_by_range_v: Optional[Sequence[float]]=None, abort_check: Optional[Callable[[], None]]=None, capture_source: Optional[Callable[[int, bool, bool], object]]=None, bipolar: bool=False) -> Tuple[RangeMeasurement, Tuple[RangeMeasurement, ...]]:
    """Measure all candidate ranges and choose the highest-current valid one.

    ``bipolar=True`` (2026-10-17) measures BOTH polarities per range and reports the
    offset-cancelled signal, so the rho estimate that drives the range rule stops being
    the contact offset (see _combine_pilot_pair).  Cost: one extra capture per range.
    """
    range_indices = tuple((int(index) for index in range_indices))
    if not range_indices:
        raise ValueError('at least one range index is required')
    candidates = []
    for range_index in range_indices:
        if abort_check is not None:
            abort_check()
        offset_v = None if probe_voltage_offset_by_range_v is None else float(probe_voltage_offset_by_range_v[range_index])
        candidate = measure_range_once(frontend, monitor, range_index, reverse=False, sample_count=sample_count, interval_s=interval_s, discard_first=discard_first, settle_s=settle_s, timeout_s=timeout_s, configure_timeout_s=configure_timeout_s, adc_input_min_v=adc_input_min_v, adc_input_max_v=adc_input_max_v, probe_abs_min_v=probe_abs_min_v, probe_abs_max_v=probe_abs_max_v, require_count=False, probe_voltage_offset_v=offset_v, adc_config_settle_s=adc_config_settle_s, abort_check=abort_check, capture_source=capture_source)
        if bipolar:
            if abort_check is not None:
                abort_check()
            reverse_candidate = measure_range_once(frontend, monitor, range_index, reverse=True, sample_count=sample_count, interval_s=interval_s, discard_first=discard_first, settle_s=settle_s, timeout_s=timeout_s, configure_timeout_s=configure_timeout_s, adc_input_min_v=adc_input_min_v, adc_input_max_v=adc_input_max_v, probe_abs_min_v=probe_abs_min_v, probe_abs_max_v=probe_abs_max_v, require_count=False, probe_voltage_offset_v=offset_v, adc_config_settle_s=adc_config_settle_s, abort_check=abort_check, capture_source=capture_source)
            candidate = _combine_pilot_pair(candidate, reverse_candidate, probe_abs_min_v=probe_abs_min_v, probe_abs_max_v=probe_abs_max_v)
        candidates.append(candidate)
    eligible = [candidate for candidate in candidates if candidate.eligible]
    if not eligible:
        detail = '; '.join(('R%d: %s (%d valid, filtered=%s V)' % (candidate.range_index, candidate.reason, candidate.capture.valid_sample_count, 'nan' if not math.isfinite(candidate.filtered_probe_voltage_v) else '%.6f' % candidate.filtered_probe_voltage_v) for candidate in candidates))
        raise RangeSelectionError('no eligible current range: ' + detail)
    with_valid_samples = [candidate for candidate in eligible if candidate.capture.valid_sample_count > 0]
    selection_pool = with_valid_samples or eligible
    best = max(selection_pool, key=lambda candidate: (candidate.range_index, candidate.capture.valid_sample_count))
    return (best, tuple(candidates))

def currents_from_reference_resistance(forward_voltage_v: float, reverse_voltage_v: float, reference_resistance_ohm: float) -> Tuple[float, float]:
    """Return positive calibrated currents from a known reference resistor."""
    reference_resistance_ohm = _require_positive(reference_resistance_ohm, 'reference_resistance_ohm')
    forward_voltage_v = _require_finite(forward_voltage_v, 'forward_voltage_v')
    reverse_voltage_v = _require_finite(reverse_voltage_v, 'reverse_voltage_v')
    return (abs(forward_voltage_v) / reference_resistance_ohm, abs(reverse_voltage_v) / reference_resistance_ohm)

def measure_zero_offset(frontend, monitor, range_index: int, *, reverse: bool=False, sample_count: int=DEFAULT_ZERO_OFFSET_SAMPLES, settle_s: float=DEFAULT_ZERO_OFFSET_SETTLE_S, **kwargs) -> RangeMeasurement:
    """Measure the zero point with the excitation current OFF (2026-10-16).

    The parasitic EMF seen on the bench is mV-class and per-contact, and the fixed
    per-range table cannot represent it (22.txt item 2).  This capture is taken at
    the SAME range and sense polarity as the measurement that follows, so the value
    it returns is exactly the offset that measurement must subtract:  the EMF keeps
    its sign under the polarity flip, which is why the reader can pass the returned
    number straight into ``probe_voltage_offset_v``.

    ``enable_current=False`` makes the PL path fail closed if the current is still
    active, so a mis-wired or stuck relay cannot silently produce a "zero" that is
    really a measurement.

    2026-10-17 -- WHAT THIS CAN AND CANNOT MEASURE (measured, not argued)
    With the current relay open the sense pair has no low-impedance path, so the node
    floats and its level is set by whatever the last event injected plus input bias
    leakage.  Bench numbers, same sample, same range:
        probe lifted (idle)   : -9.4 .. -10.2 mV, four ranges within 1.1x, reproducible
                                to 0.2 mV  => the front-end itself is fine;
        probe pressed on GaN  : +0.205 V (x3), +0.228 V (x3), -0.323 V (x3), and once
                                -1.087 -> -1.851 V (drifting 0.76 V in ~10 s)
                                => the level flips sign between runs;
        the offset actually riding on the measurement, solved from the two DRIVEN
        captures (Vf = If*R + E, Vr = Ir*R - E): E = 0.775 V on the same sample.
    So a current-off capture is not an estimate of the measurement's offset -- it is a
    floating-node reading, and subtracting it corrupts the result (it would have made
    R = 5.28 ohm instead of 1.77 ohm).  It stays available as a quiet-state sanity
    check, and ``measure_bidirectional``/the scan keep it OFF (``zero_offset_samples=0``).
    """
    return measure_range_once(frontend, monitor, range_index, reverse=bool(reverse), sample_count=int(sample_count), settle_s=settle_s, probe_voltage_offset_v=0.0, enable_current=False, **kwargs)

def measure_bidirectional(frontend, monitor, range_index: int, *, sample_count: int=DEFAULT_VALID_SAMPLE_COUNT, interval_s: float=DEFAULT_SAMPLE_INTERVAL_S, discard_first: int=DEFAULT_DISCARD_FIRST, settle_s: float=DEFAULT_RANGE_SETTLE_S, timeout_s: float=DEFAULT_CAPTURE_TIMEOUT_S, configure_timeout_s: float=2.0, adc_config_settle_s: float=DEFAULT_ADC_CONFIG_SETTLE_S, adc_input_min_v: float=DEFAULT_ADC_INPUT_MIN_V, adc_input_max_v: float=DEFAULT_ADC_INPUT_MAX_V, probe_abs_min_v: float=DEFAULT_PROBE_ABS_MIN_V, probe_abs_max_v: float=DEFAULT_PROBE_ABS_MAX_V, forward_current_a: Optional[float]=None, reverse_current_a: Optional[float]=None, forward_probe_voltage_offset_v: Optional[float]=None, reverse_probe_voltage_offset_v: Optional[float]=None, require_count: bool=True, abort_check: Optional[Callable[[], None]]=None, capture_source: Optional[Callable[[int, bool, bool], object]]=None, zero_offset_samples: int=0, zero_offset_settle_s: float=DEFAULT_ZERO_OFFSET_SETTLE_S, max_zero_offset_v: Optional[float]=None) -> BidirectionalMeasurement:
    """Capture fixed-range forward/reverse data and apply per-polarity currents."""
    zero_forward = None
    zero_reverse = None
    if int(zero_offset_samples) > 0:
        zero_kwargs = dict(sample_count=int(zero_offset_samples), interval_s=interval_s, discard_first=discard_first, settle_s=zero_offset_settle_s, timeout_s=timeout_s, configure_timeout_s=configure_timeout_s, adc_config_settle_s=adc_config_settle_s, adc_input_min_v=adc_input_min_v, adc_input_max_v=adc_input_max_v, probe_abs_min_v=0.0, probe_abs_max_v=probe_abs_max_v, abort_check=abort_check)
        zero_forward = measure_zero_offset(frontend, monitor, range_index, reverse=False, **zero_kwargs)
        zero_reverse = measure_zero_offset(frontend, monitor, range_index, reverse=True, **zero_kwargs)
        if max_zero_offset_v is not None:
            limit = float(max_zero_offset_v)
            if not limit > 0.0 or not math.isfinite(limit):
                raise ValueError('max_zero_offset_v must be None or positive')
            for label, zero in (('forward', zero_forward), ('reverse', zero_reverse)):
                value = float(zero.filtered_probe_voltage_v)
                if abs(value) > limit:
                    raise DirectMeasurementError('zero offset %s = %.6g V exceeds the %.4g V bound (R%d): check the probe contact before trusting this point' % (label, value, limit, int(range_index)))
    forward = measure_range_once(frontend, monitor, range_index, reverse=False, sample_count=sample_count, interval_s=interval_s, discard_first=discard_first, settle_s=settle_s, timeout_s=timeout_s, configure_timeout_s=configure_timeout_s, adc_input_min_v=adc_input_min_v, adc_input_max_v=adc_input_max_v, probe_abs_min_v=probe_abs_min_v, probe_abs_max_v=probe_abs_max_v, require_count=bool(require_count), probe_voltage_offset_v=forward_probe_voltage_offset_v if zero_forward is None else float(zero_forward.filtered_probe_voltage_v), adc_config_settle_s=adc_config_settle_s, abort_check=abort_check, capture_source=capture_source)
    reverse = measure_range_once(frontend, monitor, range_index, reverse=True, sample_count=sample_count, interval_s=interval_s, discard_first=discard_first, settle_s=settle_s, timeout_s=timeout_s, configure_timeout_s=configure_timeout_s, adc_input_min_v=adc_input_min_v, adc_input_max_v=adc_input_max_v, probe_abs_min_v=probe_abs_min_v, probe_abs_max_v=probe_abs_max_v, require_count=bool(require_count), probe_voltage_offset_v=reverse_probe_voltage_offset_v if zero_reverse is None else float(zero_reverse.filtered_probe_voltage_v), adc_config_settle_s=adc_config_settle_s, abort_check=abort_check, capture_source=capture_source)
    return combine_bidirectional(forward, reverse, range_index, forward_current_a=forward_current_a, reverse_current_a=reverse_current_a, zero_forward=zero_forward, zero_reverse=zero_reverse)

def combine_bidirectional(forward: RangeMeasurement, reverse: RangeMeasurement, range_index: int, *, forward_current_a: Optional[float]=None, reverse_current_a: Optional[float]=None, zero_forward: Optional[RangeMeasurement]=None, zero_reverse: Optional[RangeMeasurement]=None) -> BidirectionalMeasurement:
    """Native ADC voltage measurement. Units are volts, amperes and seconds unless stated otherwise."""
    if not forward.eligible:
        raise DirectMeasurementError('forward measurement is not eligible: %s' % forward.reason)
    if not reverse.eligible:
        raise DirectMeasurementError('reverse measurement is not eligible: %s' % reverse.reason)
    nominal_current_a = calibrated_current_for_range_a(int(range_index))
    forward_current_a = nominal_current_a if forward_current_a is None else float(forward_current_a)
    reverse_current_a = nominal_current_a if reverse_current_a is None else float(reverse_current_a)
    forward_current_a = _require_positive(forward_current_a, 'forward_current_a')
    reverse_current_a = _require_positive(reverse_current_a, 'reverse_current_a')
    forward_v = forward.filtered_probe_voltage_v
    reverse_v = reverse.filtered_probe_voltage_v
    forward_r = forward_v / forward_current_a
    reverse_r = reverse_v / reverse_current_a
    combined_r = (forward_v + reverse_v) / (forward_current_a + reverse_current_a)
    combined_abs_r = 0.5 * (abs(forward_v) / forward_current_a + abs(reverse_v) / reverse_current_a)
    equivalent_current_a = 0.5 * (forward_current_a + reverse_current_a)
    combined_v = combined_r * equivalent_current_a
    combined_abs_v = combined_abs_r * equivalent_current_a
    return BidirectionalMeasurement(range_index=int(range_index), current_a=equivalent_current_a, forward_current_a=forward_current_a, reverse_current_a=reverse_current_a, equivalent_current_a=equivalent_current_a, forward_resistance_ohm=forward_r, reverse_resistance_ohm=reverse_r, forward=forward, reverse=reverse, combined_probe_voltage_v=combined_v, combined_resistance_ohm=combined_r, combined_abs_probe_voltage_v=combined_abs_v, combined_abs_resistance_ohm=combined_abs_r, forward_reverse_delta_v=reverse_v - forward_v, polarity_same_sign=bool(forward_v * reverse_v >= 0.0), signed_sum_v=forward_v + reverse_v, zero_offset_forward_v=None if zero_forward is None else float(zero_forward.filtered_probe_voltage_v), zero_offset_reverse_v=None if zero_reverse is None else float(zero_reverse.filtered_probe_voltage_v), pair_values_v=(float(combined_v),), pair_std_v=None, pair_repeats=1)

def measurement_to_record(measurement: BidirectionalMeasurement) -> dict:
    """Convert a bidirectional result to notebook/CSV-friendly fields."""
    return {'range_index': measurement.range_index, 'current_a': measurement.current_a, 'forward_current_a': measurement.forward_current_a, 'reverse_current_a': measurement.reverse_current_a, 'equivalent_current_a': measurement.equivalent_current_a, 'forward_resistance_ohm': measurement.forward_resistance_ohm, 'reverse_resistance_ohm': measurement.reverse_resistance_ohm, 'probe_voltage_offset_forward_v': measurement.forward.probe_voltage_offset_v, 'probe_voltage_offset_reverse_v': measurement.reverse.probe_voltage_offset_v, 'forward_raw_filtered_v': measurement.forward.raw_filtered_probe_voltage_v, 'forward_raw_median_v': measurement.forward.raw_median_probe_voltage_v, 'forward_filtered_v': measurement.forward.filtered_probe_voltage_v, 'forward_median_v': measurement.forward.median_probe_voltage_v, 'forward_std_v': measurement.forward.std_probe_voltage_v, 'forward_valid_samples': measurement.forward.capture.valid_sample_count, 'reverse_raw_filtered_v': measurement.reverse.raw_filtered_probe_voltage_v, 'reverse_raw_median_v': measurement.reverse.raw_median_probe_voltage_v, 'reverse_filtered_v': measurement.reverse.filtered_probe_voltage_v, 'reverse_median_v': measurement.reverse.median_probe_voltage_v, 'reverse_std_v': measurement.reverse.std_probe_voltage_v, 'reverse_valid_samples': measurement.reverse.capture.valid_sample_count, 'combined_probe_voltage_v': measurement.combined_probe_voltage_v, 'combined_resistance_ohm': measurement.combined_resistance_ohm, 'combined_abs_probe_voltage_v': measurement.combined_abs_probe_voltage_v, 'combined_abs_resistance_ohm': measurement.combined_abs_resistance_ohm, 'forward_reverse_delta_v': measurement.forward_reverse_delta_v, 'polarity_same_sign': measurement.polarity_same_sign, 'signed_sum_v': measurement.signed_sum_v, 'zero_offset_forward_v': measurement.zero_offset_forward_v, 'zero_offset_reverse_v': measurement.zero_offset_reverse_v, 'pair_values_v': list(measurement.pair_values_v), 'pair_std_v': measurement.pair_std_v, 'pair_repeats': measurement.pair_repeats}
