# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

'Scan orchestrator: PS trajectory/model/data ownership, optionalFP_DSPv5 single-pair acquisition. Hardware safety remains authoritative. A reset holds axes/currentOFF; only explicit independent recovery may HOME. All voltage thresholds use nativeADC-derived volts.'
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Optional, Sequence, Tuple
import csv
import hashlib
import json
import re
import math
import threading
from types import SimpleNamespace
try:
    from .measurement_quality import evaluate_quality, validate_threshold, validate_sample_label
except ImportError:
    from measurement_quality import evaluate_quality, validate_threshold, validate_sample_label
try:
    from .direct_adc_measurement import ADC_CODE_MID, DIRECT_ADC_MEASUREMENT_VERSION, ADC_FULL_SCALE_V, ADC_LSB_V, DEFAULT_ADC_INPUT_MAX_V, DEFAULT_ADC_INPUT_MIN_V, DEFAULT_CAPTURE_TIMEOUT_S, DEFAULT_DISCARD_FIRST, DEFAULT_PROBE_ABS_MIN_V, DEFAULT_PROBE_ABS_MAX_V, DEFAULT_ADC_CONFIG_SETTLE_S, DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V, DEFAULT_SAMPLE_INTERVAL_S, DEFAULT_VALID_SAMPLE_COUNT, DirectMeasurementError, MeasurementAbortedError, RESISTIVITY_RANGE_TABLE, calibrated_current_for_range_a, measure_bidirectional, measure_zero_offset, range_index_for_resistivity, range_index_for_voltage_window, probe_voltage_to_code, select_current_range
    from .pl_resistivity import CALC_FLAG_NEGATIVE, K_Q_HW_MIN, K_Q_MIN, PlCalcError, PlMeasCalc, check_k_rs_relation, coefficient_k, coefficient_k_rs, decode_rs_q, fixed_point_rho_pair, fixed_point_rs_pair, quantize_coefficient_k
    from .pl_window_stats import PlWindowStats, PlWindowStatsError, REG_STATS_CENTER_CODE, REG_STATS_FLAGS, REG_STATS_SEQ, REG_STATS_SUM_HIGH, REG_STATS_SUM_LOW, REG_STATS_VALID_COUNT, STATS_FLAG_OVERFLOW
    from .direct_adc_measurement import _range_measurement_from_snapshot, combine_bidirectional
    from .pl_autorange import MODE_FULL as PL_MODE_FULL, MODE_VERIFY as PL_MODE_VERIFY, MODE_FORCED as PL_MODE_FORCED, R_AXI_ERROR as PL_R_AXI_ERROR, R_CONFIG_ERROR as PL_R_CONFIG_ERROR, R_OPEN_LOOP as PL_R_OPEN_LOOP, R_OWNERSHIP_CONFLICT as PL_R_OWNERSHIP_CONFLICT, R_SAFETY_ABORT as PL_R_SAFETY_ABORT, PlAutorangeError
except ImportError:
    from direct_adc_measurement import ADC_CODE_MID, DIRECT_ADC_MEASUREMENT_VERSION, ADC_FULL_SCALE_V, ADC_LSB_V, DEFAULT_ADC_INPUT_MAX_V, DEFAULT_ADC_INPUT_MIN_V, DEFAULT_CAPTURE_TIMEOUT_S, DEFAULT_DISCARD_FIRST, DEFAULT_PROBE_ABS_MIN_V, DEFAULT_PROBE_ABS_MAX_V, DEFAULT_ADC_CONFIG_SETTLE_S, DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V, DEFAULT_SAMPLE_INTERVAL_S, DEFAULT_VALID_SAMPLE_COUNT, DirectMeasurementError, MeasurementAbortedError, RESISTIVITY_RANGE_TABLE, calibrated_current_for_range_a, measure_bidirectional, measure_zero_offset, range_index_for_resistivity, range_index_for_voltage_window, probe_voltage_to_code, select_current_range
    from pl_resistivity import CALC_FLAG_NEGATIVE, K_Q_HW_MIN, K_Q_MIN, PlCalcError, PlMeasCalc, check_k_rs_relation, coefficient_k, coefficient_k_rs, decode_rs_q, fixed_point_rho_pair, fixed_point_rs_pair, quantize_coefficient_k
    from pl_window_stats import PlWindowStats, PlWindowStatsError, REG_STATS_CENTER_CODE, REG_STATS_FLAGS, REG_STATS_SEQ, REG_STATS_SUM_HIGH, REG_STATS_SUM_LOW, REG_STATS_VALID_COUNT, STATS_FLAG_OVERFLOW
    from direct_adc_measurement import _range_measurement_from_snapshot, combine_bidirectional
    from pl_autorange import MODE_FULL as PL_MODE_FULL, MODE_VERIFY as PL_MODE_VERIFY, MODE_FORCED as PL_MODE_FORCED, R_AXI_ERROR as PL_R_AXI_ERROR, R_CONFIG_ERROR as PL_R_CONFIG_ERROR, R_OPEN_LOOP as PL_R_OPEN_LOOP, R_OWNERSHIP_CONFLICT as PL_R_OWNERSHIP_CONFLICT, R_SAFETY_ABORT as PL_R_SAFETY_ABORT, PlAutorangeError
REG_CONTROL = 0
REG_STATUS = 4
REG_VERSION = 16
REG_MEAS_CONTROL = 88
REG_MEAS_STATUS = 92
REG_MEAS_POINT = 96
REG_MEAS_HOLD = 100
REG_MEAS_ERROR = 104
REG_R_CONTROL = 40
REG_R_COMMAND = 44
REG_R_TARGET = 48
REG_R_STATUS = 52
REG_R_POSITION = 56
REG_R_ERROR = 60
REG_Z_CONTROL = 64
REG_Z_COMMAND = 68
REG_Z_TARGET = 72
REG_Z_STATUS = 76
REG_Z_POSITION = 80
REG_Z_ERROR = 84
REG_X_TARGET = 108
REG_X_STATUS = 112
REG_X_POSITION = 116
REG_X_CONTROL = 120
REG_Z_STEP_INTERVAL = 124
REG_Z_DECEL_CONTROL = 168
REG_Z_DECEL_WINDOW = 172
REG_Z_DECEL_SEG_STEPS = 176
REG_Z_DECEL_LUT_INDEX = 180
REG_Z_DECEL_LUT_DATA = 184
REG_Z_HOME_STEPS = 240
REG_Z_TIMEOUT_CYCLES = 244
REG_R_TIMEOUT_CYCLES = 248
REG_HEARTBEAT = 252
PL_CLK_FREQ_HZ = 50000000
TIMEOUT_MARGIN_S = 2.0
RANGE_SELECTION_TIMEOUT_S = 3.0
PILOT_REFERENCE_MIN_V = 0.05
PILOT_COLLAPSE_RATIO = 0.02
OPEN_LOOP_MAX_V = 0.015
OPEN_LOOP_MIN_CURRENT_RATIO = 5.0
OPEN_LOOP_MIN_VOLTAGE_RATIO = 2.0
EXPECTED_PL_VERSION = 1095522357
SCAN_RESULT_SCHEMA_VERSION = 2
FINAL_FOUR_PROBE_SYSTEM_VERSION = 24
Z_DECEL_CONTROL_ALL_MOVES = 15
CMD_CLEAR_FAULT = 4
AXIS_CMD_HOME = 1
AXIS_CMD_MOVE_TO = 2
AXIS_CMD_MOVE_TO_MEASURE = 3
Z_CONTROL_START = 1 << 0
Z_CONTROL_STOP = 1 << 1
Z_CONTROL_CLEAR = 1 << 2
Z_CONTROL_ARM = 1 << 3
Z_CONTROL_DISARM = 1 << 4
R_CONTROL_STOP = 1 << 1
R_CONTROL_CLEAR = 1 << 2
Z_CONTROL_ARMED_BIT = 1 << 1
STATUS_RESET_LATCHED = 1 << 16
STATUS_WATCHDOG_TRIPPED = 1 << 17
STATUS_WATCHDOG_ARMED = 1 << 18
REG_WATCHDOG_COUNT = 320
REG_Z_SAFE_TRAVEL = 328
STATUS_MOTION_REFUSED = 1 << 19
PL_WATCHDOG_TIMEOUT_CYCLES = 50000000
CONTROL_WATCHDOG_DISARM = 1 << 7
R_STEPS_PER_MM = 800
AXIS_STATUS_BUSY = 1 << 0
AXIS_STATUS_DONE = 1 << 1
AXIS_STATUS_AT_HOME = 1 << 2
AXIS_STATUS_FAULT = 1 << 3
AXIS_STATUS_HOMED = 1 << 4
X_STATUS_BUSY = 1 << 0
X_STATUS_DONE = 1 << 1
Z_HARD_LIMIT_STEPS = 10000

class FinalSystemError(RuntimeError):
    """Raised when the final scan cannot continue safely."""

class MeasurementQualityError(FinalSystemError):

    def __init__(self, quality):
        self.quality = quality
        super().__init__('measurement quality: ' + ', '.join(quality['quality_flags']))

class PlAutorangeFatalError(FinalSystemError):
    """FP_DSP refused in a way no retry can fix (configuration, AXI, ownership).

    Like OpenCurrentLoopError it goes through the ordinary safe_shutdown and is never
    retried; a reset/watchdog cut is reported as MeasurementAbortedError instead.
    """

class OpenCurrentLoopError(FinalSystemError):
    """The pilot sweep saw no current-proportional signal: stop the scan before point 1.

    Deliberately NOT a MeasurementAbortedError: that one means RESET and holds the axes
    in place, which would leave the probe pressed on the wafer.  This one goes through
    the ordinary safe_shutdown (current off, Z HOME retract) and is never retried --
    no retry or range escalation can push current through an open loop.
    """

def open_current_loop_diagnosis(candidates):
    """Return a refusal text when the pilot voltages do not follow the current, else None.

    ``candidates`` are the pilot results (``range_index``, ``current_a``,
    ``filtered_probe_voltage_v``, ``capture.valid_sample_count``).  Only candidates with
    valid samples and a finite voltage take part; fewer than two distinct currents, a
    span below OPEN_LOOP_MIN_CURRENT_RATIO, or any |V| >= OPEN_LOOP_MAX_V return None
    (no verdict -- the existing per-point checks still apply).
    """
    usable = []
    for candidate in candidates or ():
        try:
            count = int(candidate.capture.valid_sample_count)
            current_a = float(candidate.current_a)
            voltage_v = float(candidate.filtered_probe_voltage_v)
        except (AttributeError, TypeError, ValueError):
            continue
        if count > 0 and current_a > 0.0 and math.isfinite(current_a) and math.isfinite(voltage_v):
            usable.append((current_a, abs(voltage_v), int(candidate.range_index), voltage_v))
    if len(set((item[0] for item in usable))) < 2:
        return None
    if max((item[1] for item in usable)) >= OPEN_LOOP_MAX_V:
        return None
    low = min(usable)
    high = max(usable)
    current_ratio = high[0] / low[0]
    if current_ratio < OPEN_LOOP_MIN_CURRENT_RATIO:
        return None
    voltage_ratio = high[1] / max(low[1], 1e-12)
    if voltage_ratio >= OPEN_LOOP_MIN_VOLTAGE_RATIO:
        return None
    readings = ', '.join(('R%d %.4g mA: %+.3f mV' % (item[2], item[0] * 1000.0, item[3] * 1000.0) for item in sorted(usable)))
    return 'open current loop or no electrical contact: the pilot voltage does not follow the current (%s; current x%.0f, |V| x%.2f, all below %.0f mV) -- the sample sees no current. Scan stopped before point 1. Check probe contact and the current loop with the probe down; on HEMT/AlGaN epi a pressure probe may not reach the 2DEG through the barrier/cap layer' % (readings, current_ratio, voltage_ratio, OPEN_LOOP_MAX_V * 1000.0)

@dataclass(frozen=True)
class ScanPoint:
    label: str
    scan_type: str
    ring: int
    point_index: int
    r_home_steps: int
    r_offset_steps: int
    x_pulses: int
    x_deg: float
    z_steps: int

@dataclass
class ScanSummary:
    """Result of one scan.

    ``completed`` keeps its historical meaning ("at least one point was
    measured").  ``quality_ok`` is the stricter, configurable gate: at least
    ``min_quality_valid_ratio`` of the planned points were valid, so a run that
    produced one good point out of twenty-five is no longer reported as a good
    scan.  Every new field carries a default so existing positional
    constructions keep working.
    """
    completed: bool
    selected_range_index: Optional[int]
    results: list
    error: Optional[str]
    total_points: int = 0
    valid_points: int = 0
    invalid_points: int = 0
    quality_ok: bool = False
    min_quality_valid_ratio: float = 0.0
    pl_quality_judged_points: int = 0
    pl_quality_failed_points: int = 0

def scan_quality_ok(valid_ratio_ok, pl_quality_failed):
    """The scan-level verdict: the valid-point ratio AND zero PL quality failures.

    Kept as a named function on purpose.  Phase C moved the quality judgement into PL
    and the verdict into PS, so the verdict has to be testable on its own -- otherwise
    "the decision moved" would also mean "only an end-to-end scan can check it".
    """
    return bool(valid_ratio_ok) and int(pl_quality_failed) == 0

def summarize_pl_quality(results):
    """Count the points whose PL-side quality judgement failed.

    Phase C put the judgement (count floor, span ceiling) in PL but deliberately left
    the *verdict* to the PS, so the test obligation moved here with it: a point PL
    judged out of limits keeps its measured value but must not be silently counted
    into a "good" scan.  Returns (judged_points, failed_points); points without a PL
    judgement (PL rho disabled, or the model failed) are simply not counted.
    """
    judged = 0
    failed = 0
    for record in results:
        if not isinstance(record, dict):
            continue
        details = record.get('rho_pl_details')
        if not isinstance(details, dict):
            continue
        verdict = details.get('quality_ok')
        if verdict is None:
            continue
        judged += 1
        if not verdict:
            failed += 1
    return (judged, failed)
DEPLOY_MANIFEST_NAME = 'deploy_manifest.json'
DEPLOY_MANIFEST_VERSION = 1
_DEPLOY_WATCH = {'pl_window_stats.py': ('def average_code', 'return self\\.sum_codes'), 'direct_adc_measurement.py': ('median_probe_voltage_v=', 'filtered_probe_voltage_v=', 'capture_source', 'average_code ='), 'final_four_probe_system.py': ('FINAL_FOUR_PROBE_SYSTEM_VERSION =', 'offset_v / probe_scale', "'relative_error': float\\(relative\\)"), 'pl_resistivity.py': '^(COEFF_FRAC|OUT_FRAC|MEAN_FRAC|K_Q_MIN|K_Q_HW_MIN) ='}
_DEPLOY_WATCH_MAX_LINES = 8

def _sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()

def _deploy_watch_lines(name, path) -> str:
    """The lines that decide this file's argument, read from the deployed copy."""
    patterns = _DEPLOY_WATCH.get(str(name))
    if not patterns:
        return '<no watch list for this file>'
    try:
        hits = []
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            for number, line in enumerate(handle, 1):
                text = line.rstrip('\n')
                if any((re.search(pattern, text) for pattern in patterns)):
                    hits.append('%d: %s' % (number, text.strip()))
                    if len(hits) >= _DEPLOY_WATCH_MAX_LINES:
                        hits.append('... (truncated)')
                        break
        return ' | '.join(hits) if hits else '<no watched line found>'
    except OSError as exc:
        return '<unreadable: %r>' % (exc,)

def check_deploy_manifest(manifest_path, package_dir, bitstream_path) -> bool:
    """Fail-closed: raise unless the deployed files are the audited revision.

    Every failure mode raises: no manifest, an unreadable or wrong-version one, a
    file the manifest lists that the deployment lacks, a size or SHA256 that
    differs, or a bitstream pair that does not match it.  "Cannot tell" must never
    pass a gate (AGENTS.md section 6).
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise FinalSystemError('deploy manifest not found: %s' % (manifest_path,))
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise FinalSystemError('deploy manifest is unreadable (%r): %s' % (exc, manifest_path))
    if int(manifest.get('manifest_version', 0)) != DEPLOY_MANIFEST_VERSION:
        raise FinalSystemError('deploy manifest version %r is not the one this code understands (%d): %s' % (manifest.get('manifest_version'), DEPLOY_MANIFEST_VERSION, manifest_path))
    problems = []
    package_dir = Path(package_dir)
    for entry in manifest.get('files') or ():
        path = package_dir / str(entry.get('name'))
        if not path.is_file():
            problems.append('missing  %s' % (path,))
            continue
        size = path.stat().st_size
        digest = _sha256_of(path)
        if size != int(entry.get('size', -1)) or digest != str(entry.get('sha256')):
            problems.append('differs  %s\n             manifest %d B %s\n             deployed %d B %s\n             markers  %s' % (path, int(entry.get('size', -1)), entry.get('sha256'), size, digest, _deploy_watch_lines(entry.get('name'), path)))
    stream = None if bitstream_path is None else Path(bitstream_path)
    if stream is None or not stream.is_file():
        problems.append('missing  bitstream %s' % (stream,))
    else:
        siblings = (stream, stream.with_suffix('.hwh'))
        for entry in manifest.get('bitstream') or ():
            suffix = Path(str(entry.get('name'))).suffix.lower()
            matches = [p for p in siblings if p.suffix.lower() == suffix]
            if not matches:
                problems.append('manifest bitstream %s has no counterpart beside %s' % (entry.get('name'), stream))
                continue
            path = matches[0]
            if not path.is_file():
                problems.append('missing  %s' % (path,))
                continue
            size = path.stat().st_size
            digest = _sha256_of(path)
            if size != int(entry.get('size', -1)) or digest != str(entry.get('sha256')):
                problems.append('differs  %s\n             manifest %d B %s\n             deployed %d B %s' % (path, int(entry.get('size', -1)), entry.get('sha256'), size, digest))
    if problems:
        raise FinalSystemError('the deployed files are NOT the audited revision (%d problem(s)):\n  %s\n  Copy the whole sw/four_probe_sw/ together with .bit/.hwh again, then\n  restart the kernel.  If a .py differs, fetch THAT file back and diff it\n  against the repository -- a hash names the file, never the line.' % (len(problems), '\n  '.join(problems)))
    return True

class FinalFourProbeSystem:
    """Orchestrates motion, ADC selection, bidirectional measurement, and model math."""

    def __init__(self, mmio, frontend, monitor, calculate_four_probe, sample_type, *, is_n_type: bool, diameter_mm: float, thickness_um: float, probe_spacing_mm: float, forward_current_by_range_a: Sequence[Optional[float]], reverse_current_by_range_a: Sequence[Optional[float]], probe_voltage_offset_by_range_v: Sequence[float], r_home_to_center_steps: int, r_ring_spacing_steps: int, r_max_steps: int, x_pulses_per_rev: int, full_down_steps: int, half_up_steps: int, z_timeout_s: float, r_timeout_s: float, x_timeout_s: float, z_run_step_cycles: int, z_end_step_cycles: int, z_decel_window_steps: int, z_decel_seg_steps: int, z_decel_segments: int, z_rehome_interval_points: int, use_pl_window_stats: bool=False, pl_stats_timeout_s: float=0.1, pl_stats_min_valid_samples: int=1, use_pl_calc: bool=False, pl_rho_tolerance: float=0.0001, allow_unverified_deploy: bool=False, deploy_manifest_path: Optional[str]=None, bitstream_path: Optional[str]=None, allow_motion: bool=False, range_indices: Sequence[int]=(0, 1, 2, 3), range_selection_sample_count: int=100, select_range_by_resistivity: bool=True, zero_offset_samples: int=0, zero_offset_settle_s: float=0.5, max_zero_offset_v: Optional[float]=0.05, max_polarity_asymmetry: Optional[float]=None, max_offset_to_signal_ratio: Optional[float]=None, max_range_nonlinearity: Optional[float]=None, sample_label: str='', pl_window_abs_min_v: float=0.0, reselect_range_on_retry: bool=True, full_range_reselect_on_retry: bool=True, reselect_range_every_point: bool=False, pair_significance_k: float=3.0, pair_significance_floor_v: float=0.0, pilot_bipolar: bool=True, check_current_path: bool=True, measurement_retry_count: int=2, measurement_retry_delay_s: float=0.5, valid_sample_count: int=DEFAULT_VALID_SAMPLE_COUNT, sample_interval_s: float=DEFAULT_SAMPLE_INTERVAL_S, discard_first: int=DEFAULT_DISCARD_FIRST, range_settle_s: float=0.05, bidirectional_settle_s: float=1.0, adc_config_settle_s: float=DEFAULT_ADC_CONFIG_SETTLE_S, capture_timeout_s: float=DEFAULT_CAPTURE_TIMEOUT_S, adc_input_min_v: float=DEFAULT_ADC_INPUT_MIN_V, adc_input_max_v: float=DEFAULT_ADC_INPUT_MAX_V, probe_abs_min_v: float=DEFAULT_PROBE_ABS_MIN_V, probe_abs_max_v: float=DEFAULT_PROBE_ABS_MAX_V, poll_interval_s: float=0.01, min_quality_valid_ratio: float=0.8, z_lateral_lift_steps: Optional[int]=None, pl_autorange=None, on_range_selected=None, on_point=None, motion_trace=False):
        self.max_polarity_asymmetry = validate_threshold(max_polarity_asymmetry, 'max_polarity_asymmetry')
        self.max_offset_to_signal_ratio = validate_threshold(max_offset_to_signal_ratio, 'max_offset_to_signal_ratio')
        self.max_range_nonlinearity = validate_threshold(max_range_nonlinearity, 'max_range_nonlinearity')
        self.sample_label = validate_sample_label(sample_label)
        self.pl_autorange = pl_autorange
        if pl_autorange is not None and (not hasattr(pl_autorange, 'run')):
            raise ValueError('pl_autorange must be a pl_autorange.PlAutorange driver')
        self.pl_autorange_identity = None
        self._hmi_range_index = None
        self.on_range_selected = on_range_selected
        self.on_point = on_point
        self.motion_trace = motion_trace
        self._manual_rehome_required = False
        self.mmio = mmio
        self.frontend = frontend
        self.monitor = monitor
        self.calculate_four_probe = calculate_four_probe
        self.sample_type = sample_type
        self.is_n_type = bool(is_n_type)
        self.diameter_mm = float(diameter_mm)
        self.thickness_um = float(thickness_um)
        self.probe_spacing_mm = float(probe_spacing_mm)
        self.forward_current_by_range_a = tuple(forward_current_by_range_a)
        self.reverse_current_by_range_a = tuple(reverse_current_by_range_a)
        self.probe_voltage_offset_by_range_v = tuple(probe_voltage_offset_by_range_v)
        if len(self.forward_current_by_range_a) != 4 or len(self.reverse_current_by_range_a) != 4:
            raise ValueError('current calibration tables must contain four entries')
        if len(self.probe_voltage_offset_by_range_v) != 4:
            raise ValueError('probe voltage offset table must contain four entries')
        self.allow_motion = bool(allow_motion)
        allowed = tuple(sorted({int(index) for index in range_indices}))
        if not allowed:
            raise ValueError('range_indices must contain at least one range')
        if allowed[0] < 0 or allowed[-1] > 3:
            raise ValueError('range_indices must be within 0..3')
        self.range_indices = allowed
        self.range_selection_sample_count = int(range_selection_sample_count)
        self.valid_sample_count = int(valid_sample_count)
        if self.range_selection_sample_count <= 0:
            raise ValueError('range_selection_sample_count must be positive')
        self.select_range_by_resistivity = bool(select_range_by_resistivity)
        self.zero_offset_samples = int(zero_offset_samples)
        if self.zero_offset_samples < 0:
            raise ValueError('zero_offset_samples must be non-negative')
        self.zero_offset_settle_s = float(zero_offset_settle_s)
        if self.zero_offset_settle_s < 0.0 or not math.isfinite(self.zero_offset_settle_s):
            raise ValueError('zero_offset_settle_s must be finite and non-negative')
        if max_zero_offset_v is not None:
            bound = float(max_zero_offset_v)
            if not bound > 0.0 or not math.isfinite(bound):
                raise ValueError('max_zero_offset_v must be None or positive')
            self.max_zero_offset_v = bound
        else:
            self.max_zero_offset_v = None
        self.quiet_zero_by_bank = {}
        self.pl_window_abs_min_v = float(pl_window_abs_min_v)
        if self.pl_window_abs_min_v < 0.0 or not math.isfinite(self.pl_window_abs_min_v):
            raise ValueError('pl_window_abs_min_v must be finite and non-negative')
        self.reselect_range_on_retry = bool(reselect_range_on_retry)
        self.full_range_reselect_on_retry = bool(full_range_reselect_on_retry)
        self.reselect_range_every_point = bool(reselect_range_every_point)
        self.pair_repeats = 1
        if self.pair_repeats < 1:
            raise ValueError('pair_repeats must be positive')
        self.pair_significance_k = float(pair_significance_k)
        if not math.isfinite(self.pair_significance_k) or self.pair_significance_k <= 0.0:
            raise ValueError('pair_significance_k must be finite and positive')
        self.pair_significance_floor_v = float(pair_significance_floor_v)
        if not math.isfinite(self.pair_significance_floor_v) or self.pair_significance_floor_v < 0.0:
            raise ValueError('pair_significance_floor_v must be finite and non-negative')
        self.pilot_bipolar = bool(pilot_bipolar)
        self.check_current_path = bool(check_current_path)
        self.measurement_retry_count = int(measurement_retry_count)
        if self.measurement_retry_count < 0:
            raise ValueError('measurement_retry_count must be non-negative')
        self.measurement_retry_delay_s = float(measurement_retry_delay_s)
        if self.measurement_retry_delay_s < 0.0:
            raise ValueError('measurement_retry_delay_s must be non-negative')
        self.sample_interval_s = float(sample_interval_s)
        self.discard_first = int(discard_first)
        self.range_settle_s = float(range_settle_s)
        self.bidirectional_settle_s = float(bidirectional_settle_s)
        self.adc_config_settle_s = float(adc_config_settle_s)
        self.capture_timeout_s = float(capture_timeout_s)
        self.adc_input_min_v = float(adc_input_min_v)
        self.adc_input_max_v = float(adc_input_max_v)
        self.probe_abs_min_v = float(probe_abs_min_v)
        self.probe_abs_max_v = float(probe_abs_max_v)
        self.r_home_to_center_steps = int(r_home_to_center_steps)
        self.r_ring_spacing_steps = int(r_ring_spacing_steps)
        self.r_max_steps = int(r_max_steps)
        self.x_pulses_per_rev = int(x_pulses_per_rev)
        self.z_hard_limit_steps = int(Z_HARD_LIMIT_STEPS)
        self.full_down_steps = int(full_down_steps)
        self.half_up_steps = int(half_up_steps)
        clear_height = self.full_down_steps - self.half_up_steps
        self.z_lateral_lift_steps = clear_height if z_lateral_lift_steps is None else int(z_lateral_lift_steps)
        if not 0 <= self.z_lateral_lift_steps <= clear_height:
            raise ValueError('z_lateral_lift_steps must be between 0 (fully retracted) and %d (the calibrated clear height)' % clear_height)
        if self.full_down_steps > self.z_hard_limit_steps:
            raise ValueError('full_down_steps=%d exceeds the Z hard travel limit %d; raise the RTL parameter Z_MAX_STEPS and Z_HARD_LIMIT_STEPS together only after measuring the real axis travel' % (self.full_down_steps, self.z_hard_limit_steps))
        if not 0 < self.half_up_steps < self.full_down_steps:
            raise ValueError('half_up_steps must be between 0 and full_down_steps')
        self.z_timeout_s = float(z_timeout_s)
        self.r_timeout_s = float(r_timeout_s)
        self.x_timeout_s = float(x_timeout_s)
        self.z_run_step_cycles = int(z_run_step_cycles)
        self.z_end_step_cycles = int(z_end_step_cycles)
        self.z_decel_window_steps = int(z_decel_window_steps)
        self.z_decel_seg_steps = int(z_decel_seg_steps)
        self.z_decel_segments = int(z_decel_segments)
        self.z_rehome_interval_points = int(z_rehome_interval_points)
        if self.z_run_step_cycles <= 0 or self.z_end_step_cycles < self.z_run_step_cycles:
            raise ValueError('invalid Z deceleration step periods')
        if self.z_decel_segments < 2 or self.z_decel_seg_steps <= 0:
            raise ValueError('invalid Z deceleration segment configuration')
        self.poll_interval_s = float(poll_interval_s)
        self.min_quality_valid_ratio = float(min_quality_valid_ratio)
        if not 0.0 <= self.min_quality_valid_ratio <= 1.0:
            raise ValueError('min_quality_valid_ratio must be between 0 and 1')
        self.pl_stats_timeout_s = float(pl_stats_timeout_s)
        if not math.isfinite(self.pl_stats_timeout_s) or self.pl_stats_timeout_s <= 0.0:
            raise ValueError('pl_stats_timeout_s must be finite and positive')
        self.pl_stats_min_valid_samples = int(pl_stats_min_valid_samples)
        if self.pl_stats_min_valid_samples < 0:
            raise ValueError('pl_stats_min_valid_samples must be non-negative')
        self.window_stats = PlWindowStats(self._read, self._write) if bool(use_pl_window_stats) else None
        if bool(use_pl_calc) and self.window_stats is None:
            raise ValueError('use_pl_calc=True requires use_pl_window_stats=True')
        self.pl_calc = PlMeasCalc(self._read, self._write) if bool(use_pl_calc) else None
        self.pl_rho_tolerance = float(pl_rho_tolerance)
        if not (math.isfinite(self.pl_rho_tolerance) and self.pl_rho_tolerance > 0.0):
            raise ValueError('pl_rho_tolerance must be finite and positive')
        self.allow_unverified_deploy = bool(allow_unverified_deploy)
        self.deploy_manifest_path = str(deploy_manifest_path or Path(__file__).resolve().parent / DEPLOY_MANIFEST_NAME)
        self.bitstream_path = None if bitstream_path is None else str(bitstream_path)
        self.pl_calc_probe = None
        self.results = []
        self.selected_range_index = None
        self.selected_candidates = ()
        self.range_selection_note = None
        self.range_selection_resistivity_ohm_cm = None
        self.shutdown_result = None
        self._mmio_lock = threading.Lock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None
        self.last_error = None
        self.last_summary = None
        self.stop_result = None
        self.safety_cleanup = None
        self._scan_return_x = None
        self._current_x_target = 0

    def _read(self, offset):
        with self._mmio_lock:
            return int(self.mmio.read(int(offset))) & 4294967295

    def _write(self, offset, value):
        with self._mmio_lock:
            self.mmio.write(int(offset), int(value) & 4294967295)

    def _raise_if_measurement_aborted(self):
        """Abort an in-flight capture when the PL fault latch is set."""
        status = self._read(REG_STATUS)
        if status & STATUS_RESET_LATCHED:
            raise MeasurementAbortedError('PL SYSTEM_RESET is latched; capture aborted')
        if status & STATUS_WATCHDOG_TRIPPED:
            raise MeasurementAbortedError('PL heartbeat watchdog tripped; capture aborted')

    def _pl_stats_bank(self, range_index, reverse):
        range_index = int(range_index)
        if range_index not in (0, 1, 2, 3):
            raise ValueError('range_index must be 0, 1, 2 or 3')
        return range_index + (4 if bool(reverse) else 0)

    def _quiet_zero_for(self, range_index, reverse):
        """The zero this bank is measured against -- and the one the PL must centre on.

        ``quiet_zero_by_bank`` holds the value captured BEFORE any excitation at the
        current point (see ``_measure_quiet_zeros``).  When ② is off -- or before that
        capture -- the per-range table is used, which is exactly the old behaviour.
        """
        measured = self.quiet_zero_by_bank.get((int(range_index), bool(reverse)))
        if measured is None:
            return float(self.probe_voltage_offset_by_range_v[int(range_index)])
        return float(measured)

    def _measure_quiet_zero(self, range_index, reverse):
        """Native ADC voltage measurement. Units are volts, amperes and seconds unless stated otherwise."""
        samples = int(self.zero_offset_samples)
        if samples <= 0:
            return None
        zero = measure_zero_offset(self.frontend, self.monitor, int(range_index), reverse=bool(reverse), sample_count=samples, interval_s=self.sample_interval_s, discard_first=self.discard_first, settle_s=self.zero_offset_settle_s, timeout_s=self.capture_timeout_s, configure_timeout_s=2.0, adc_config_settle_s=self.adc_config_settle_s, adc_input_min_v=self.adc_input_min_v, adc_input_max_v=self.adc_input_max_v, probe_abs_min_v=0.0, probe_abs_max_v=self.probe_abs_max_v, require_count=False, abort_check=self._raise_if_measurement_aborted)
        value = float(zero.filtered_probe_voltage_v)
        limit = self.max_zero_offset_v
        if limit is not None:
            bound = float(limit)
            if not bound > 0.0 or not math.isfinite(bound):
                raise ValueError('max_zero_offset_v must be None or positive')
            if abs(value) > bound:
                raise DirectMeasurementError('quiet zero %s = %.6g V exceeds the %.4g V bound (R%d): check the probe contact before trusting this point' % ('reverse' if reverse else 'forward', value, bound, int(range_index)))
        return value

    def _measure_quiet_zeros(self, range_indices):
        """Capture and remember the quiet zero for each (range, polarity) pair given."""
        for index in range_indices:
            for reverse in (False, True):
                value = self._measure_quiet_zero(index, reverse)
                if value is None:
                    return
                self.quiet_zero_by_bank[int(index), bool(reverse)] = value

    def _pl_stats_window_params(self, range_index, reverse=None):
        range_index = int(range_index)
        if reverse is None:
            offset_v = float(self.probe_voltage_offset_by_range_v[range_index])
        else:
            offset_v = self._quiet_zero_for(range_index, reverse)
        probe_scale = float(1.0)
        if not probe_scale > 0.0:
            raise FinalSystemError('native voltage conversion invariant violated, got %r' % (probe_scale,))
        center_code = probe_voltage_to_code(offset_v / probe_scale)
        adc_code_per_volt = 1.0 / ADC_LSB_V
        adc_min_code = int(round(ADC_CODE_MID + self.adc_input_min_v * adc_code_per_volt))
        adc_max_code = int(round(ADC_CODE_MID + self.adc_input_max_v * adc_code_per_volt))
        if adc_min_code > adc_max_code:
            raise FinalSystemError('ADC input limits produce an inverted code interval')
        if center_code < adc_min_code:
            adc_mag_min = adc_min_code - center_code
            adc_mag_max = adc_max_code - center_code
        elif center_code > adc_max_code:
            adc_mag_min = center_code - adc_max_code
            adc_mag_max = center_code - adc_min_code
        else:
            adc_mag_min = 0
            adc_mag_max = min(center_code - adc_min_code, adc_max_code - center_code)
        probe_code_per_volt = adc_code_per_volt / 1.0
        probe_mag_min = math.ceil(self.pl_window_abs_min_v * probe_code_per_volt)
        probe_mag_max = math.floor(self.probe_abs_max_v * probe_code_per_volt)
        mag_min = max(0, adc_mag_min, probe_mag_min)
        mag_max = min(65535, adc_mag_max, probe_mag_max)
        if mag_min > mag_max:
            raise FinalSystemError('PL statistics magnitude window is empty: min=%d max=%d' % (mag_min, mag_max))
        return (center_code, mag_min, mag_max)

    def _capture_pl_window_snapshot(self, range_index, reverse, strict_valid_count=True):
        if self.window_stats is None:
            raise PlWindowStatsError('PL statistics path is not enabled')
        bank = self._pl_stats_bank(range_index, reverse)
        center_code, mag_min, mag_max = self._pl_stats_window_params(range_index, reverse)
        self.window_stats.configure_bank(bank, center_code, mag_min, mag_max)
        self.window_stats.clear_bank(bank)
        self.window_stats.arm()
        try:
            snapshot = self.window_stats.wait_snapshot(bank, timeout_s=self.pl_stats_timeout_s, abort_check=self._raise_if_measurement_aborted)
        finally:
            self.window_stats.disarm()
        return replace(snapshot, minimum_valid_samples=self.pl_stats_min_valid_samples, strict_valid_count=bool(strict_valid_count))

    def start_heartbeat(self, period_s=0.1):
        """Arm and feed the PL watchdog from a background thread.

        The PL watchdog only runs after the first 0xFC write, so nothing trips
        before this is called.  Keep the period well below the 1 s PL timeout.
        """
        period_s = float(period_s)
        if not math.isfinite(period_s) or period_s <= 0.0:
            raise ValueError('period_s must be finite and positive')
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            if self._heartbeat_stop.is_set():
                raise FinalSystemError('Previous heartbeat thread is still stopping')
            return self._heartbeat_thread
        self._heartbeat_stop.clear()

        def _run():
            while not self._heartbeat_stop.wait(period_s):
                try:
                    self._write(REG_HEARTBEAT, 1)
                except Exception:
                    return
        self._heartbeat_thread = threading.Thread(target=_run, daemon=True)
        self._heartbeat_thread.start()
        return self._heartbeat_thread

    def stop_heartbeat(self, join=False, timeout_s=1.0):
        """Stop feeding the watchdog and optionally wait for the thread to exit.

        ``join=True`` is required before clearing the PL fault latches: a late
        0xFC write would re-arm the watchdog after the latches were cleared, so
        the two actions must not interleave.
        """
        timeout_s = float(timeout_s)
        if not math.isfinite(timeout_s) or timeout_s < 0.0:
            raise ValueError('timeout_s must be finite and nonnegative')
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if join and thread is not None and thread.is_alive():
            thread.join(timeout_s)
        if thread is not None and thread.is_alive():
            if join:
                raise FinalSystemError('Heartbeat thread did not stop within %.3g s' % timeout_s)
        else:
            self._heartbeat_thread = None
        return thread

    def heartbeat_is_running(self):
        """True while the watchdog feed thread is alive (read-only diagnostic)."""
        thread = self._heartbeat_thread
        return bool(thread is not None and thread.is_alive())

    def _safety_hint(self):
        """Safety summary appended to an axis-wait failure.

        A refused command can be silent (X) or record only an error code (R), so a
        bare "timeout" says nothing about why the axis never moved.  Error codes
        stay diagnostic; this appends the STATUS bits that explain the wait.
        """
        try:
            safety = self.read_safety_status()
        except Exception as exc:
            return ' (safety status unavailable: %r)' % (exc,)
        return ' [reset=%s wdt_tripped=%s wdt_armed=%s refused=%s probe_clear=%s z_homed=%s z_pos=%s]' % (safety['reset_latched'], safety['watchdog_tripped'], safety['watchdog_armed'], safety['motion_refused'], safety.get('probe_clear'), safety.get('z_homed'), safety.get('z_position'))

    def _wait_x_idle(self, label='X_WAIT_IDLE', timeout_s=None):
        """Wait (bounded) until the X axis stops stepping.  True when idle."""
        timeout_s = self.x_timeout_s if timeout_s is None else float(timeout_s)
        deadline = monotonic() + timeout_s
        while monotonic() < deadline:
            if not self.x_read_status()['busy']:
                return True
            sleep(self.poll_interval_s)
        print('%s: X axis still busy after %.1f s' % (label, timeout_s))
        return False

    def axis_read_status(self, status_reg):
        value = self._read(status_reg)
        return {'raw': value, 'busy': bool(value & AXIS_STATUS_BUSY), 'done': bool(value & AXIS_STATUS_DONE), 'at_home': bool(value & AXIS_STATUS_AT_HOME), 'fault': bool(value & AXIS_STATUS_FAULT), 'homed': bool(value & AXIS_STATUS_HOMED)}

    def axis_wait_done(self, status_reg, error_reg, timeout_s, label, abort_check=None):
        deadline = monotonic() + float(timeout_s)
        saw_busy = False
        while monotonic() < deadline:
            if abort_check is not None:
                abort_check()
            status = self.axis_read_status(status_reg)
            if status['fault']:
                raise FinalSystemError('%s fault=%d' % (label, self._read(error_reg) & 15))
            if status['busy']:
                saw_busy = True
            if status['done'] and (not status['busy']):
                return status
            if saw_busy and (not status['busy']):
                raise FinalSystemError('%s left busy without done' % label)
            sleep(self.poll_interval_s)
        raise FinalSystemError('%s timeout%s' % (label, self._safety_hint()))

    def axis_home(self, control_reg, command_reg, status_reg, error_reg, timeout_s, label, abort_check=None):
        if control_reg == REG_Z_CONTROL:
            self.verify_z_armed(label)
        self._write(command_reg, AXIS_CMD_HOME)
        self._write(control_reg, 1)
        return self.axis_wait_done(status_reg, error_reg, timeout_s, label, abort_check=abort_check)

    def axis_move_to(self, control_reg, command_reg, target_reg, status_reg, error_reg, target_steps, timeout_s, label, abort_check=None):
        target_steps = int(target_steps)
        if target_steps < 0:
            raise ValueError('%s target is negative' % label)
        self._write(target_reg, target_steps)
        self._write(command_reg, AXIS_CMD_MOVE_TO)
        self._write(control_reg, 1)
        return self.axis_wait_done(status_reg, error_reg, timeout_s, label, abort_check=abort_check)

    def verify_axis_home(self, status_reg, position_reg, label):
        status = self.axis_read_status(status_reg)
        position = self._read(position_reg)
        if not status['at_home'] or position != 0:
            raise FinalSystemError('%s verification failed: status=%r position=%d' % (label, status, position))

    def z_decel_periods(self):
        periods = []
        for index in range(self.z_decel_segments):
            fraction = index / (self.z_decel_segments - 1)
            velocity = 1.0 / self.z_run_step_cycles + (1.0 / self.z_end_step_cycles - 1.0 / self.z_run_step_cycles) * fraction
            periods.append(int(round(1.0 / velocity)))
        return tuple(periods)

    def configure_z_decel(self):
        self._write(REG_Z_STEP_INTERVAL, self.z_run_step_cycles)
        self._write(REG_Z_DECEL_CONTROL, 0)
        self._write(REG_Z_DECEL_WINDOW, self.z_decel_window_steps)
        self._write(REG_Z_DECEL_SEG_STEPS, self.z_decel_seg_steps)
        for index, period in enumerate(self.z_decel_periods()):
            self._write(REG_Z_DECEL_LUT_INDEX, index)
            self._write(REG_Z_DECEL_LUT_DATA, period)
        self._write(REG_Z_DECEL_CONTROL, Z_DECEL_CONTROL_ALL_MOVES)
        print('Z deceleration periods:', self.z_decel_periods())

    def verify_z_position(self, target_steps, label):
        target_steps = int(target_steps)
        position = self._read(REG_Z_POSITION)
        if position != target_steps:
            raise FinalSystemError('%s position mismatch: expected=%d actual=%d' % (label, target_steps, position))
        return position

    def z_move_to_measure(self, target_steps, label, abort_check=None):
        target_steps = int(target_steps)
        self.verify_z_armed(label)
        current_position = int(self._read(REG_Z_POSITION))
        retracted_position = self.z_lateral_lift_steps
        allowed_starts = (0, retracted_position)
        if current_position not in allowed_starts:
            raise FinalSystemError('%s Z down refused: position=%d is not HOME(0) or the verified retracted position(%d)' % (label, current_position, retracted_position))
        if target_steps <= current_position:
            raise FinalSystemError('%s Z down refused: target=%d is not below position=%d' % (label, target_steps, current_position))
        self._write(REG_Z_TARGET, target_steps)
        self._write(REG_Z_COMMAND, AXIS_CMD_MOVE_TO_MEASURE)
        self._write(REG_Z_CONTROL, 1)
        status = self.axis_wait_done(REG_Z_STATUS, REG_Z_ERROR, self.z_timeout_s, label, abort_check=abort_check)
        self.verify_z_position(target_steps, label)
        return status

    def z_move_to(self, target_steps, label, abort_check=None):
        target_steps = int(target_steps)
        self.verify_z_armed(label)
        status = self.axis_move_to(REG_Z_CONTROL, REG_Z_COMMAND, REG_Z_TARGET, REG_Z_STATUS, REG_Z_ERROR, target_steps, self.z_timeout_s, label, abort_check=abort_check)
        self.verify_z_position(target_steps, label)
        return status

    def r_move_to(self, target_steps, label, abort_check=None):
        return self.axis_move_to(REG_R_CONTROL, REG_R_COMMAND, REG_R_TARGET, REG_R_STATUS, REG_R_ERROR, target_steps, self.r_timeout_s, label, abort_check=abort_check)

    def x_read_status(self):
        value = self._read(REG_X_STATUS)
        return {'raw': value, 'busy': bool(value & X_STATUS_BUSY), 'done': bool(value & X_STATUS_DONE), 'dir': value >> 2 & 1}

    def x_wait_done(self, label, abort_check=None):
        deadline = monotonic() + self.x_timeout_s
        saw_busy = False
        while monotonic() < deadline:
            if abort_check is not None:
                abort_check()
            status = self.x_read_status()
            if status['busy']:
                saw_busy = True
            if saw_busy and (not status['busy']):
                return status
            if status['done'] and (not status['busy']) and (not saw_busy):
                return status
            sleep(self.poll_interval_s)
        raise FinalSystemError('%s timeout%s' % (label, self._safety_hint()))

    def x_rotate_pulses(self, pulses, label, abort_check=None):
        pulses = int(pulses)
        if pulses < 0:
            raise ValueError('X axis is configured for one-direction rotation only')
        if pulses == 0:
            return self.x_read_status()
        start_position = self._read(REG_X_POSITION)
        self._write(REG_X_TARGET, pulses)
        self._write(REG_X_CONTROL, 1)
        status = self.x_wait_done(label, abort_check=abort_check)
        actual = self._read(REG_X_POSITION) - start_position
        if actual != pulses:
            raise FinalSystemError('%s pulse mismatch: expected %d, got %d' % (label, pulses, actual))
        return status

    def build_scan_plan(self, point_count):
        point_count = int(point_count)
        if point_count not in (9, 25):
            raise ValueError('point_count must be 9 or 25')
        plan = [ScanPoint(label='C', scan_type='polar_%d' % point_count, ring=0, point_index=0, r_home_steps=self.r_home_to_center_steps, r_offset_steps=0, x_pulses=0, x_deg=0.0, z_steps=self.full_down_steps)]
        ring_count = 1 if point_count == 9 else 2
        for ring in range(1, ring_count + 1):
            ring_points = 8 * ring
            for index in range(ring_points):
                x_pulses = int(round(self.x_pulses_per_rev * index / ring_points))
                r_home_steps = self.r_home_to_center_steps + ring * self.r_ring_spacing_steps
                if r_home_steps < 0 or r_home_steps > self.r_max_steps:
                    raise ValueError('ring %d R target out of range: %d' % (ring, r_home_steps))
                plan.append(ScanPoint(label='R%d_P%d' % (ring, index + 1), scan_type='polar_%d' % point_count, ring=ring, point_index=index, r_home_steps=r_home_steps, r_offset_steps=ring * self.r_ring_spacing_steps, x_pulses=x_pulses, x_deg=x_pulses * 360.0 / self.x_pulses_per_rev, z_steps=self.full_down_steps))
        return plan

    def _validated_currents(self, values):
        values = tuple(values)
        if len(values) != 4:
            raise ValueError('expected exactly four per-range currents')
        out = []
        for value in values:
            value = float(value)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError('every current must be finite and positive')
            out.append(value)
        return tuple(out)

    def set_forward_currents(self, currents):
        """Override the calibrated forward excitation currents (4 values, amps)."""
        self.forward_current_by_range_a = self._validated_currents(currents)
        return self.forward_current_by_range_a

    def set_reverse_currents(self, currents):
        """Override the calibrated reverse excitation currents (4 values, amps)."""
        self.reverse_current_by_range_a = self._validated_currents(currents)
        return self.reverse_current_by_range_a

    def set_range_currents(self, forward=None, reverse=None):
        """Set either or both polarity tables in one call."""
        if forward is not None:
            self.set_forward_currents(forward)
        if reverse is not None:
            self.set_reverse_currents(reverse)
        return self.get_range_currents()

    def get_range_currents(self):
        """Return the currents currently used for the calculation."""
        return {'forward': tuple(self.forward_current_by_range_a), 'reverse': tuple(self.reverse_current_by_range_a), 'nominal': tuple((calibrated_current_for_range_a(i) for i in range(4)))}

    def request_system_reset(self, reason='manual'):
        """Ask the PL to reset: current off, latches set, no axis is moved."""
        self._write(REG_CONTROL, 1 << 5)
        return {'reason': str(reason), 'control': self._read(REG_CONTROL), 'status': self._read(REG_STATUS)}

    def clear_faults(self):
        """Clear reset/PL fault latches. Only call after checking the fixture."""
        self._manual_rehome_required = True
        self._write(REG_CONTROL, 1 << 6)
        return self._read(REG_STATUS)

    def watchdog_disarm(self):
        """Disarm the watchdog without touching the fault latches.

        CLEAR_FAULTS also disarms, but it clears reset_latched /
        watchdog_tripped as well, so a SYSTEM_RESET that arrives in the few
        microseconds between the PS status read and the write is swallowed.
        CONTROL bit7 closes that window: WATCHDOG_DISARM only zeroes the
        counter and the armed flag.
        """
        self._write(REG_CONTROL, CONTROL_WATCHDOG_DISARM)
        return self._read(REG_STATUS)

    def configure_z_safe_travel(self):
        """Program the PL lateral-motion height gate from the calibrated heights.

        The gate must equal the clear height (the height the scan actually moves
        R/X at), otherwise it would either block the normal scan or silently stop
        protecting.  The readback therefore has to match EXACTLY - a value that is
        too small blocks the scan, a value that is too large weakens the gate, and
        both are caught here instead of on the fixture.
        """
        threshold = self.full_down_steps - self.half_up_steps
        if threshold < self.z_lateral_lift_steps:
            raise FinalSystemError('internal inconsistency: the clear height %d is below the lateral lift height %d' % (threshold, self.z_lateral_lift_steps))
        self._write(REG_Z_SAFE_TRAVEL, threshold)
        readback = int(self._read(REG_Z_SAFE_TRAVEL))
        if readback != threshold:
            raise FinalSystemError('Z_SAFE_TRAVEL readback mismatch: wrote %d, read %d. The loaded bitstream does not implement 0x148 (rebuild from the current RTL).' % (threshold, readback))
        self.z_safe_travel = threshold
        return threshold

    def watchdog_count(self):
        """PL watchdog counter in 50 MHz cycles (20 ns per count)."""
        return self._read(REG_WATCHDOG_COUNT)

    def read_safety_status(self):
        """Read-only snapshot of the PL safety state (no register is written)."""
        status = self._read(REG_STATUS)
        safety = {'status_raw': status, 'reset_latched': bool(status & STATUS_RESET_LATCHED), 'watchdog_tripped': bool(status & STATUS_WATCHDOG_TRIPPED), 'watchdog_armed': bool(status & STATUS_WATCHDOG_ARMED), 'main_state': status & 31, 'pl_fault': bool(status & 1 << 8), 'x_busy': bool(status & 1 << 10), 'motion_refused': bool(status & STATUS_MOTION_REFUSED), 'z_safe_travel': getattr(self, 'z_safe_travel', None)}
        try:
            z = self.axis_read_status(REG_Z_STATUS)
            threshold = getattr(self, 'z_safe_travel', None)
            position = int(self._read(REG_Z_POSITION))
            safety['z_homed'] = bool(z['homed'])
            safety['z_position'] = position
            safety['probe_clear'] = bool(z['homed'] and threshold is not None and (position <= threshold))
        except Exception:
            safety['probe_clear'] = None
        return safety

    def stop_all_axes(self):
        """Global reset halts all axes and preserves Z ARM and position."""
        self.request_system_reset('stop all axes')
        return dict(z_stopped=True, r_stopped=True, x_stop_supported=True)

    @property
    def reset_latched(self):
        return bool(self._read(REG_STATUS) & STATUS_RESET_LATCHED)

    def rehome(self):
        """Explicit manual recovery after fixture inspection and CLEAR."""
        self._raise_if_measurement_aborted()
        self.frontend.safe_off()
        self.configure_z_safe_travel()
        self._write(REG_Z_CONTROL, Z_CONTROL_ARM | Z_CONTROL_CLEAR)
        self._write(REG_R_CONTROL, R_CONTROL_CLEAR)
        self.z_driver_arm()
        self.start_heartbeat()
        try:
            self.axis_home(REG_Z_CONTROL, REG_Z_COMMAND, REG_Z_STATUS, REG_Z_ERROR, self.z_timeout_s, 'MANUAL_Z_HOME', abort_check=self._raise_if_measurement_aborted)
            self.verify_axis_home(REG_Z_STATUS, REG_Z_POSITION, 'MANUAL_Z_HOME')
            self.axis_home(REG_R_CONTROL, REG_R_COMMAND, REG_R_STATUS, REG_R_ERROR, self.r_timeout_s, 'MANUAL_R_HOME', abort_check=self._raise_if_measurement_aborted)
            self.verify_axis_home(REG_R_STATUS, REG_R_POSITION, 'MANUAL_R_HOME')
            self._manual_rehome_required = False
        finally:
            self.frontend.safe_off()
            self.finish_safety_cleanup()

    def finish_safety_cleanup(self):
        """End-of-scan safety wrap-up: heartbeat, latches, watchdog.

        Rules, in this exact order:

        1. Stop the heartbeat thread first (and join it).  Clearing latches
           while the feed thread still runs would let a late 0xFC write re-arm
           the watchdog right after it was disarmed.
        2. If a PL fault latch is set, the request came from outside the scan:
           the serial screen pressed SYSTEM_RESET, or the watchdog fired.  The
           latches are left untouched so the operator still sees the request;
           clearing them here would silently swallow an operator reset.
        3. Otherwise, clear the latches only after the excitation current is
           confirmed off.  If the current state cannot be confirmed, the
           latches stay and the (now un-fed) watchdog cuts the current about a
           second later.

        The protection against a dead PS comes from the heartbeat *thread*
        disappearing, not from the latches, so this is safe for the scan itself;
        it only decides what the next run inherits.
        """
        result = {'heartbeat_stopped': False, 'faults_cleared': False, 'left_latched': False, 'watchdog_left_armed': False, 'current_off': None, 'status': None}
        try:
            self.stop_heartbeat(join=True)
            result['heartbeat_stopped'] = True
        except Exception as exc:
            result['error'] = 'stop_heartbeat: %r' % (exc,)
            result['watchdog_left_armed'] = True
            return result
        try:
            status = self._read(REG_STATUS)
        except Exception as exc:
            result['error'] = 'status read: %r' % (exc,)
            result['watchdog_left_armed'] = True
            return result
        result['status'] = int(status)
        if status & (STATUS_RESET_LATCHED | STATUS_WATCHDOG_TRIPPED):
            result['left_latched'] = True
            return result
        safe_off_ok = False
        try:
            off = self.frontend.safe_off()
            if isinstance(off, dict):
                safe_off_ok = not bool(off.get('current_active', True))
        except Exception as exc:
            result['error'] = 'safe_off: %r' % (exc,)
        if hasattr(self.frontend, 'status'):
            try:
                safe_off_ok = safe_off_ok and (not bool(self.frontend.status().get('current_active')))
            except Exception as exc:
                safe_off_ok = False
                result['error'] = 'frontend status: %r' % (exc,)
        result['current_off'] = safe_off_ok
        if safe_off_ok:
            try:
                self.watchdog_disarm()
                result['faults_cleared'] = True
            except Exception as exc:
                result['error'] = 'watchdog_disarm: %r' % (exc,)
        else:
            result['watchdog_left_armed'] = True
        return result

    def z_driver_disarm(self):
        self._write(REG_Z_CONTROL, Z_CONTROL_DISARM)
        control = self._read(REG_Z_CONTROL)
        if control & Z_CONTROL_ARMED_BIT:
            raise FinalSystemError('Z driver did not disarm: 0x%08X' % control)
        return control

    def z_driver_arm(self):
        self._write(REG_Z_CONTROL, Z_CONTROL_ARM)
        sleep(self.poll_interval_s)
        control = self._read(REG_Z_CONTROL)
        if not control & Z_CONTROL_ARMED_BIT:
            raise FinalSystemError('Z driver did not arm: 0x%08X. The loaded bitstream has no Z ARM interlock; rebuild and load all_design.bit from the current RTL before moving the Z axis.' % control)
        return control

    def verify_z_armed(self, label='Z'):
        """Abort before any Z motion if the PL driver interlock is not armed."""
        control = self._read(REG_Z_CONTROL)
        if not control & Z_CONTROL_ARMED_BIT:
            raise FinalSystemError('%s: Z driver interlock is not armed (Z_CONTROL=0x%08X)' % (label, control))
        return control

    def prepare_z_power_up(self):
        """Disarm, stop, clear Z state, then arm only after the axis is idle."""
        self._write(REG_Z_CONTROL, Z_CONTROL_DISARM | Z_CONTROL_STOP | Z_CONTROL_CLEAR)
        self._write(REG_Z_TARGET, 0)
        deadline = monotonic() + self.z_timeout_s
        while monotonic() < deadline:
            status = self.axis_read_status(REG_Z_STATUS)
            if not status['busy']:
                self.configure_z_decel()
                self.z_driver_arm()
                self.verify_z_armed('Z_POWER_UP')
                return self.axis_read_status(REG_Z_STATUS)
            sleep(self.poll_interval_s)
        raise FinalSystemError('Z did not become idle during power-up preparation')

    def _check_pair_significance(self, measurement):
        """Reject a pair whose sign/magnitude is inside the between-pair noise.

        The within-window standard deviation is tiny at N=1000 and does not
        describe contact-EMF wander between captures.  ``pair_std_v`` is the
        spread of repeated pair averages (C3); with one pair there is no sigma,
        so only the explicit absolute floor applies.  A negative average is still
        rejected when it is at or beyond the threshold -- it means the two
        polarities disagree or polarity wiring is wrong.
        """
        average_v = float(measurement.combined_probe_voltage_v)
        sigma_v = getattr(measurement, 'pair_std_v', None)
        floor_v = max(float(self.pair_significance_floor_v), 2.0 * ADC_LSB_V)
        threshold_v = floor_v if sigma_v is None else max(floor_v, self.pair_significance_k * float(sigma_v))
        if abs(average_v) < threshold_v:
            raise FinalSystemError('point is at the noise floor: |0.5*(Vf+Vr)| = %.3f mV < %.3f mV (k=%.1f, sigma_between_pairs=%s) -- use a higher current range' % (average_v * 1000.0, threshold_v * 1000.0, self.pair_significance_k, 'n/a' if sigma_v is None else '%.3f mV' % (float(sigma_v) * 1000.0)))
        if average_v < 0.0:
            raise FinalSystemError('pair average is significantly NEGATIVE (%.3f mV, threshold %.3f mV): the two polarities contradict each other -- check probe contact and polarity wiring' % (average_v * 1000.0, threshold_v * 1000.0))
        return threshold_v

    def _pl_rho_pair(self, range_index, model_result, measurement):
        """Return (rho_ohm_cm, details) with the forward/reverse average done in PL.

        One exact, fail-closed check before the number is accepted:

        1. hardware vs ``fixed_point_rho_pair`` on the SAME latched window snapshots,
           compared for EXACT equality: the oracle mirrors the RTL statement for
           statement, so a mismatch means the silicon does not implement the spec and
           no tolerance can excuse it.

        The comparison with the deployed float model is RECORDED, never gated
        (operator decision 2026-10-16, see the note where the code bound used to be):
        ``relative_error`` / ``rs_relative_error`` / ``model_ohm_cm`` / ``rs_model_ohm_sq``
        go into the point record, and a disagreement no longer refuses the point.  The
        two paths differ by construction -- integer centre code, the per-point zero
        that only the model subtracts, and the model's truncated mean code.

        Rs-only fallback (2026-10-16, 900 nm GaN): when K_rho falls below K_Q_MIN the
        rho channel is outside its own 1e-4 accuracy budget, and the point is taken
        from the Rs channel instead.  K_rs = K_rho/W_cm is 1/W_cm times larger, so the
        SAME 10 mA measurement that gives K_q = 213 (two orders below the floor) gives
        K_rs_q = 2.4e6 (deep inside it) on a 900 nm layer, and rho = Rs*W_cm is one
        parameter away.  The fallback moves the EXACT oracle comparison onto the
        channel that is reported and changes nothing else: the hardware window
        (0, COEFF_MAX] still gates both coefficients, ``first/second['overflow']`` and
        the latched flags still refuse the point, and the rho channel is recorded as
        ``rho_pl_channel_ohm_cm`` so the below-budget value stays visible
        (``details['rho_from_rs']`` says which path produced the number).

        Caveat that is RECORDED, never gated: the RTL averages the two half results with
        EQUAL weights, i.e. 0.5*(Vf/If + Vr/Ir), while the PS model now uses the exactly
        offset-free (Vf + Vr)/(If + Ir) (2026-10-17).  The two agree when the two
        calibrated currents are equal and diverge in proportion to the contact offset:
        with If/Ir = 1.07 and E = 5x the signal (the GaN bench) they differ by ~18%, so a
        ``relative_error`` of that order there is expected arithmetic, not a fault.  Making
        the two currents equal, or changing the RTL's pair weights, is what would close it.

        The capture helper disarms the window before this runs, so each bank's latched
        SUM/COUNT is still the data the model was computed from.  Centre codes are
        read back and compared for equality (write-then-read-back rule).
        """
        if self.window_stats is None:
            raise PlCalcError('PL rho needs the banked statistics path')
        expected_center_forward, _, _ = self._pl_stats_window_params(range_index, False)
        expected_center_reverse, _, _ = self._pl_stats_window_params(range_index, True)
        thickness_cm = float(self.thickness_um) * 0.0001
        bank_forward = self._pl_stats_bank(range_index, False)
        bank_reverse = self._pl_stats_bank(range_index, True)

        def snapshot(bank, expected_center):
            self.window_stats.select_bank(int(bank))
            center = self._read(REG_STATS_CENTER_CODE) & 65535
            if center != expected_center:
                raise PlCalcError('bank %d centre_code read back as %d, expected %d' % (bank, center, expected_center))
            low = self._read(REG_STATS_SUM_LOW) & 4294967295
            high = self._read(REG_STATS_SUM_HIGH) & 4294967295
            return {'sum': high << 32 | low, 'count': self._read(REG_STATS_VALID_COUNT) & 4294967295, 'seq': self._read(REG_STATS_SEQ) & 4294967295, 'overflow': bool(self._read(REG_STATS_FLAGS) & STATS_FLAG_OVERFLOW)}
        self.pl_calc.write_quality_limits(self.pl_stats_min_valid_samples, 0)
        self.pl_quality_ok = None
        first = snapshot(bank_forward, expected_center_forward)
        second = snapshot(bank_reverse, expected_center_reverse)
        if first['overflow'] or second['overflow']:
            raise PlCalcError('PL window overflow latched on a measured bank')

        def k_q_for(current_a):
            """Return (k_q, rho_budget_ok): the hardware window is a gate, K_Q_MIN is not.

            A K_q below the accuracy floor is legal to WRITE -- the RTL only refuses
            (0, COEFF_MAX] -- and the Rs-only fallback below does write it.  What such a
            coefficient may not do is be REPORTED as rho, which is what the flag says.
            """
            k = coefficient_k(ADC_LSB_V, model_result.fd, model_result.fw, thickness_cm, model_result.fsp, current_a)
            k_q = quantize_coefficient_k(k, k_q_floor=K_Q_HW_MIN)
            return (k_q, k_q >= K_Q_MIN)

        def k_rs_q_for(current_a):
            k_rs = coefficient_k_rs(ADC_LSB_V, model_result.fd, model_result.fw, model_result.fsp, current_a)
            return quantize_coefficient_k(k_rs)
        k_q_forward, k_q_forward_budget = k_q_for(float(measurement.forward_current_a))
        k_q_reverse, k_q_reverse_budget = k_q_for(float(measurement.reverse_current_a))
        k_rs_q_forward = k_rs_q_for(float(measurement.forward_current_a))
        k_rs_q_reverse = k_rs_q_for(float(measurement.reverse_current_a))
        rho_channel_ok = k_q_forward_budget and k_q_reverse_budget
        k_rs_relation_tolerance = max(check_k_rs_relation(k_q_forward, k_rs_q_forward, thickness_cm), check_k_rs_relation(k_q_reverse, k_rs_q_reverse, thickness_cm))
        oracle_q, oracle_flags, oracle_pair = fixed_point_rho_pair(first['count'], first['sum'], expected_center_forward, k_q_forward, second['count'], second['sum'], expected_center_reverse, k_q_reverse)
        if oracle_flags & ~CALC_FLAG_NEGATIVE or not oracle_pair:
            raise PlCalcError('golden model refuses this pair (flags=0x%02X): count=%d/%d%s' % (oracle_flags, first['count'], second['count'], self._pair_refusal_hint(measurement, range_index) if int(oracle_flags) & CALC_FLAG_NEGATIVE else ''))
        rs_oracle_q = None
        if not rho_channel_ok:
            rs_oracle_q, rs_flags, rs_pair = fixed_point_rs_pair(first['count'], first['sum'], expected_center_forward, k_rs_q_forward, second['count'], second['sum'], expected_center_reverse, k_rs_q_reverse)
            if rs_flags & ~CALC_FLAG_NEGATIVE or not rs_pair:
                raise PlCalcError('golden model refuses the Rs pair (flags=0x%02X): count=%d/%d' % (rs_flags, first['count'], second['count']))
        rho_hw = self.pl_calc.compute_pair(k_q_forward, k_rs_q_forward, k_q_reverse, k_rs_q_reverse, select_first=lambda: self.window_stats.select_bank(bank_forward), select_second=lambda: self.window_stats.select_bank(bank_reverse), k_q_floor=K_Q_HW_MIN)
        rho_hw_q = self.pl_calc.read_rho_q()
        rs_hw_q = self.pl_calc.read_rs_q()
        self.pl_quality_ok = self.pl_calc.read_quality_ok()
        if rho_hw_q != oracle_q:
            raise PlCalcError('hardware rho_q=%d != golden model %d for the same snapshot (seq %d/%d): the PL arithmetic does not match the spec' % (rho_hw_q, oracle_q, first['seq'], second['seq']))
        if rs_oracle_q is not None and rs_hw_q != rs_oracle_q:
            raise PlCalcError('hardware rs_q=%d != golden model %d for the same snapshot (seq %d/%d): the PL arithmetic does not match the spec' % (rs_hw_q, rs_oracle_q, first['seq'], second['seq']))
        rs_hw = decode_rs_q(rs_hw_q)
        if rho_channel_ok:
            reported_rho = float(rho_hw)
        else:
            reported_rho = rs_hw * thickness_cm
        model_rho = float(model_result.resistivity_ohm_cm)
        relative = abs(reported_rho - model_rho) / abs(model_rho)
        model_rs = float(model_result.sheet_resistance_ohm_per_square)
        rs_relative = abs(rs_hw - model_rs) / abs(model_rs) if model_rs else 0.0
        return (reported_rho, {'rho_source': 'model_pl_verified' if rho_channel_ok else 'model_pl_rs_verified', 'rho_from_rs': not rho_channel_ok, 'k_q_rho_budget_ok': bool(rho_channel_ok), 'rho_pl_channel_ohm_cm': float(rho_hw), 'rho_q': int(rho_hw_q), 'oracle_q': int(oracle_q), 'model_ohm_cm': model_rho, 'relative_error': float(relative), 'k_q_forward': int(k_q_forward), 'k_q_reverse': int(k_q_reverse), 'count_forward': int(first['count']), 'count_reverse': int(second['count']), 'rs_pl_ohm_sq': float(rs_hw), 'rs_model_ohm_sq': model_rs, 'rs_relative_error': float(rs_relative), 'rs_q': int(rs_hw_q), 'oracle_rs_q': None if rs_oracle_q is None else int(rs_oracle_q), 'comparison_gated': False, 'tolerance_configured': float(self.pl_rho_tolerance), 'quality_ok': None if self.pl_quality_ok is None else bool(self.pl_quality_ok), 'k_rs_q_forward': int(k_rs_q_forward), 'k_rs_q_reverse': int(k_rs_q_reverse), 'k_rs_relation_tolerance': float(k_rs_relation_tolerance)})

    def preflight(self):
        if not self.allow_motion:
            raise FinalSystemError('ALLOW_MOTION=False: final scan not started')
        version = self._read(REG_VERSION)
        if version != EXPECTED_PL_VERSION:
            raise FinalSystemError('PL register map mismatch: expected 0x%08X, got 0x%08X. Rebuild and load all_design.bit from the current RTL before moving anything.' % (EXPECTED_PL_VERSION, version))
        if self.allow_unverified_deploy:
            print('WARNING: allow_unverified_deploy=True -- the deployed files are NOT\n         verified against the audited revision.  Only a test\n         harness should set this.')
        elif self.bitstream_path is None:
            raise FinalSystemError('bitstream_path is not set, so the deployed files cannot be verified against the audited revision: pass str(overlay.bitfile_name), or set allow_unverified_deploy=True to opt out on purpose.')
        else:
            check_deploy_manifest(self.deploy_manifest_path, Path(__file__).resolve().parent, self.bitstream_path)
        if self.pl_calc is not None:
            try:
                self.pl_calc_probe = self.pl_calc.probe_registers()
            except Exception as exc:
                raise FinalSystemError('PL rho block unusable: %r. Load an all_design.bit containing the CALC_* registers (rebuild from the current RTL), or construct the system with use_pl_calc=False.' % (exc,))
        if self.pl_autorange is not None:
            self._prepare_pl_autorange()
        try:
            z_cycles = self._read(REG_Z_TIMEOUT_CYCLES)
            r_cycles = self._read(REG_R_TIMEOUT_CYCLES)
            if 0 < z_cycles <= 10000000000:
                self.z_timeout_s = z_cycles / float(PL_CLK_FREQ_HZ) + TIMEOUT_MARGIN_S
            if 0 < r_cycles <= 10000000000:
                self.r_timeout_s = r_cycles / float(PL_CLK_FREQ_HZ) + TIMEOUT_MARGIN_S
        except Exception as exc:
            print('preflight: axis timeout readback failed (%r); keeping the configured timeouts' % (exc,))
        status = self._read(REG_STATUS)
        if status & STATUS_RESET_LATCHED:
            raise FinalSystemError('PL reset is latched (SYSTEM_RESET was requested). Clear it with clear_faults() after checking the fixture, then re-home.')
        if status & STATUS_WATCHDOG_TRIPPED:
            raise FinalSystemError('PL heartbeat watchdog tripped, excitation current was cut. Check the fixture, then clear_faults() and re-home.')
        if status & 31 != 0:
            raise FinalSystemError('main_state is not IDLE: 0x%08X' % status)
        if status & 1 << 8:
            raise FinalSystemError('PL fault is latched')
        if status & 1 << 10:
            raise FinalSystemError('X axis is busy')
        r_status = self.axis_read_status(REG_R_STATUS)
        if r_status['fault']:
            raise FinalSystemError('R axis fault before scan: %r' % (r_status,))
        self.configure_z_safe_travel()
        self.start_heartbeat()
        try:
            self._write(REG_MEAS_CONTROL, CMD_CLEAR_FAULT)
            self._write(REG_MEAS_POINT, 0)
            self._write(REG_MEAS_HOLD, 200000000)
            self.prepare_z_power_up()
            z_status = self.axis_read_status(REG_Z_STATUS)
            if z_status['fault']:
                raise FinalSystemError('Z axis fault before scan: %r' % (z_status,))
        except Exception:
            self.stop_heartbeat(join=True)
            raise

    def safe_shutdown(self):
        """Retract the probe safely and report what actually happened.

        Rules (all of them exist to keep the wafer and the probe intact):

        * Z is retracted with HOME, never with MOVE_TO 0.  HOME is terminated by
          the home sensor, so it still works when the position counter is wrong
          (for example right after a PL reset, where Z_POSITION reads 0 while the
          probe can still be pressed on the sample).
        * If the Z driver is not armed, no Z command is issued at all.  The PL
          cannot generate STEP pulses while disarmed, so a HOME here would only
          sit for 15 s and then report a timeout while the operator believes the
          probe is being lifted.  The ARM is never set automatically.
        * X and R are only moved after the Z retract has been verified, because
          lateral motion with the probe still touching the sample drags it
          across the wafer.
        * The Z driver is only disarmed after a verified retract.  Otherwise it
          stays armed on purpose so the screw keeps holding torque.
        """
        try:
            locked = bool(self._read(REG_STATUS) & (STATUS_RESET_LATCHED | STATUS_WATCHDOG_TRIPPED))
        except Exception:
            locked = True
        if locked or self._manual_rehome_required:
            self.frontend.safe_off()
            self._manual_rehome_required = True
            return dict(ok=True, errors=[], held_in_place=True, retract_attempted=False, retract_ok=False, x_returned=False, r_homed=False, z_disarmed=False)
        result = {'ok': True, 'errors': [], 'retract_attempted': False, 'retract_ok': False, 'retract_method': None, 'x_returned': False, 'r_homed': False, 'z_disarmed': False, 'retract_pre_position': None, 'retract_home_steps': None}
        try:
            self.frontend.safe_off()
        except Exception as exc:
            result['errors'].append('safe_off: %r' % exc)
        try:
            armed = bool(self._read(REG_Z_CONTROL) & Z_CONTROL_ARMED_BIT)
        except Exception as exc:
            armed = False
            result['errors'].append('Z_CONTROL read: %r' % exc)
        if not armed:
            result['retract_method'] = 'skipped-not-armed'
            result['errors'].append('Z driver is not armed, so no retract command was issued. The probe may still be resting on the sample: check the fixture by hand, then call prepare_z_power_up() and safe_shutdown() again.')
        else:
            result['retract_attempted'] = True
            result['retract_method'] = 'HOME'
            try:
                pre_position = int(self._read(REG_Z_POSITION))
            except Exception:
                pre_position = None
            try:
                self.axis_home(REG_Z_CONTROL, REG_Z_COMMAND, REG_Z_STATUS, REG_Z_ERROR, self.z_timeout_s, 'Z_SAFE_RETRACT')
                status = self.axis_read_status(REG_Z_STATUS)
                position = self._read(REG_Z_POSITION)
                try:
                    home_steps = int(self._read(REG_Z_HOME_STEPS))
                except Exception:
                    home_steps = None
                result['retract_pre_position'] = pre_position
                result['retract_home_steps'] = home_steps
                ok = bool(status['at_home'] and status['homed'] and (position == 0))
                if ok and pre_position is not None and (pre_position > 50):
                    if home_steps is None or home_steps * 2 < pre_position:
                        ok = False
                result['retract_ok'] = ok
                if not ok:
                    result['errors'].append('Z retract verification failed: status=%r position=%d pre_position=%s home_steps=%s' % (status, position, pre_position, home_steps))
            except Exception as exc:
                result['errors'].append('Z retract: %r' % exc)
        if result['retract_ok']:
            try:
                return_x = self._scan_return_x
                if return_x is not None:
                    if self._wait_x_idle('X_SAFE_SHUTDOWN_WAIT'):
                        current_x = int(self._read(REG_X_POSITION))
                        if current_x < return_x:
                            self.x_rotate_pulses(return_x - current_x, 'X_SAFE_SHUTDOWN')
                            result['x_returned'] = True
                        self._current_x_target = return_x
                    else:
                        result['errors'].append('X was still moving after %.1f s; the return command was not issued' % self.x_timeout_s)
            except Exception as exc:
                result['errors'].append('X shutdown: %r' % exc)
            try:
                self.axis_home(REG_R_CONTROL, REG_R_COMMAND, REG_R_STATUS, REG_R_ERROR, self.r_timeout_s, 'R_SAFE_SHUTDOWN')
                result['r_homed'] = True
            except Exception as exc:
                result['errors'].append('R shutdown: %r' % exc)
        else:
            result['errors'].append('Z retract was not verified: X and R were left untouched so the probe cannot be dragged across the sample.')
        if result['retract_ok']:
            try:
                self.z_driver_disarm()
                result['z_disarmed'] = True
            except Exception as exc:
                result['errors'].append('Z driver disarm: %r' % exc)
        else:
            result['errors'].append('Z driver left ARMED on purpose: holding torque is kept because the probe position is not verified.')
        try:
            self.frontend.safe_off()
        except Exception as exc:
            result['errors'].append('final safe_off: %r' % exc)
        result['ok'] = not result['errors']
        return result

    def _currents_for_range(self, range_index):
        nominal = calibrated_current_for_range_a(range_index)
        forward = self.forward_current_by_range_a[range_index]
        reverse = self.reverse_current_by_range_a[range_index]
        current_calibrated = bool(nominal is not None and math.isfinite(float(nominal)) and (float(nominal) > 0.0))
        polarity_current_calibrated = forward is not None and reverse is not None
        if forward is None:
            forward = nominal
        if reverse is None:
            reverse = nominal
        return (float(forward), float(reverse), current_calibrated, polarity_current_calibrated)

    def _candidate_resistivity_ohm_cm(self, candidate):
        """Estimate rho from one pilot candidate with the scan model."""
        current_ma = float(candidate.current_a) * 1000.0
        voltage_mv = float(candidate.filtered_probe_voltage_v) * 1000.0
        if not math.isfinite(current_ma) or current_ma <= 0.0:
            raise ValueError('candidate current is not usable')
        if not math.isfinite(voltage_mv) or voltage_mv == 0.0:
            raise ValueError('candidate voltage is zero')
        result = self.calculate_four_probe(sample_type=self.sample_type, is_n_type=self.is_n_type, diameter_mm=self.diameter_mm, thickness_um=self.thickness_um, current_ma=current_ma, voltage_mv=voltage_mv, probe_spacing_mm=self.probe_spacing_mm)
        rho = float(result.resistivity_ohm_cm)
        if not math.isfinite(rho) or rho <= 0.0:
            raise ValueError('model returned a non-positive resistivity')
        return rho

    def _pilot_reference_v(self, range_index):
        """The value the PILOT decided on for THIS range, or None.

        That is ``filtered_probe_voltage_v`` -- with ``pilot_bipolar`` it is the
        offset-cancelled signal 0.5*(Vf+Vr), otherwise the forward reading.  Comparing it
        with the forward HALF of the pair (an earlier version did that) is comparing two
        different quantities: on the bench the pilot's forward half sat at its noise floor
        while the combined value was 0.778 V, so the guard saw "reference < 50 mV" and went
        silent exactly when it was needed.
        """
        for candidate in self.selected_candidates or ():
            if int(candidate.range_index) == int(range_index):
                return float(getattr(candidate, 'filtered_probe_voltage_v', 0.0))
        return None

    def _current_path_now_v(self, measurement):
        """The same quantity as _pilot_reference_v, measured NOW."""
        if self.pilot_bipolar:
            return 0.5 * (float(measurement.forward.filtered_probe_voltage_v) + float(measurement.reverse.filtered_probe_voltage_v))
        return float(measurement.forward.filtered_probe_voltage_v)

    def _current_path_ratio(self, measurement, range_index):
        """(pilot reference V, forward-now V, ratio) or None when there is no reference.

        The reference is the pilot's forward raw reading for the SAME range; ``now`` is the
        forward half of the pair just acquired.  None when the reference is missing or not
        worth using (< PILOT_REFERENCE_MIN_V: inside the tens-of-mV offset wander).
        """
        reference = self._pilot_reference_v(range_index)
        if reference is None or abs(reference) < PILOT_REFERENCE_MIN_V:
            return None
        now = self._current_path_now_v(measurement)
        return (float(reference), now, abs(now) / abs(reference))

    def _check_current_path(self, measurement, range_index):
        """Abort when the current path collapsed between the pilot and the pair.

        2026-10-17 bench (50 nm HEM, R3): the pilot saw 0.835 V, the very next pair saw
        0.008 V -- a dead loop reads the contact EMF, so the pair average turns small and
        negative and the operator is told "noise floor" while the real fault is an open
        current loop (connectors / range relay / source).  Comparing the pilot's forward
        reading for the chosen range with the forward half of the pair just acquired catches
        that at zero extra cost.

        Only a RATIO is judged, and only against a reference worth using (>= 50 mV, i.e.
        outside the tens-of-mV offset wander).  A pilot that is itself at the noise floor is
        left to the existing "noise floor" refusal -- there is no ratio to trust there.
        """
        ratio = self._current_path_ratio(measurement, range_index)
        if ratio is None:
            return
        reference, now, value = ratio
        if value < PILOT_COLLAPSE_RATIO:
            raise MeasurementAbortedError('current path open between the pilot and the measurement (pilot %.4g V at R%d, now %.4g V, ratio %.1f%%) -- check the current-loop connectors / range relay before trusting any rho' % (reference, int(range_index), now, 100.0 * value))

    def _pair_refusal_hint(self, measurement, range_index=None):
        """Explain a NEGATIVE pair average in the operator's terms (2026-10-17).

        The RTL reports the pair average as a MAGNITUDE plus a sign flag, so a negative
        average must stay a refusal -- but "golden model refuses this pair (flags=0x10)"
        gave the operator nothing to act on.  This appends the two numbers that identify
        the case: the offset-cancelled signal (the marginal quantity, 0.5*(Vf+Vr)) next to
        the contact offset it had to remove (E = Vf - If*R).  When the two are the same
        size the point is sitting on its own noise floor: move to a higher current range,
        or average several pairs.
        """
        try:
            forward_v = float(measurement.forward.filtered_probe_voltage_v)
            reverse_v = float(measurement.reverse.filtered_probe_voltage_v)
            forward_i = float(measurement.forward_current_a)
            reverse_i = float(measurement.reverse_current_a)
        except AttributeError:
            return ''
        if forward_i + reverse_i <= 0.0:
            return ''
        r_ohm = (forward_v + reverse_v) / (forward_i + reverse_i)
        margin_v = 0.5 * (forward_v + reverse_v)
        offset_v = forward_v - forward_i * r_ohm
        text = ' | pair average %+.6g V <= 0 while the contact offset it must cancel is %+.6g V -- the point sits on the noise floor: use a higher current range or average several pairs' % (margin_v, offset_v)
        if range_index is not None:
            ratio = self._current_path_ratio(measurement, range_index)
            if ratio is not None:
                reference, now, value = ratio
                text += ' | pilot reference for R%d: %.4g V, pair now %+.4g V (ratio %.1f%%)' % (int(range_index), reference, now, 100.0 * value)
            else:
                pilot = self._pilot_reference_v(range_index)
                text += ' | no usable pilot reference for R%d (%s) -- the pilot was already on the noise floor: check the current loop end to end' % (int(range_index), 'missing candidate' if pilot is None else 'pilot %.4g V < %.4g V' % (pilot, PILOT_REFERENCE_MIN_V))
        return text

    def _k_feasible_range_indices(self, candidates):
        """Range indices where the PL can produce a REPORTABLE number.

        Two conditions, and the second one is what the Rs-only fallback (2026-10-16)
        changed:

        * the HARDWARE window: both coefficients inside ``(0, COEFF_MAX]``, which is all
          the RTL refuses -- and it refuses BOTH results when either one is outside it;
        * at least one CHANNEL inside its own 1e-4 accuracy budget: the rho channel
          needs ``K_q >= K_Q_MIN``, and when that is out of reach the Rs channel
          (``K_rs = K_rho/W_cm``, ``1/W_cm`` times larger) may hold the budget instead
          -- that is the fallback, and ``_pl_rho_pair`` then reports ``rho = Rs*W_cm``.

        K is proportional to the sample thickness, which is why the OLD rule (rho budget
        only) left a thin sample with a single usable range: 900 nm at 10 mA gives
        ``K_q = 213`` (rho out of budget) while ``K_rs_q = 2.4e6`` (deep inside the Rs
        budget), and the same layer at 0.1 mA gives ``K_q = 21300`` whose ~1 mV signal
        the polarity average cannot even read -- which is exactly the range the bench
        picked when the flags=0x10 refusal came out of it.

        The K gates are REUSED (``coefficient_k`` / ``coefficient_k_rs`` /
        ``quantize_coefficient_k``), so there is exactly one definition of each window
        in the package.

        Returns ``None`` when the geometry factors cannot be computed; the caller
        then applies the voltage rule WITHOUT the K filter (fail-open on the
        *filter* only -- the PL still refuses a bad K at the measurement itself).
        """
        try:
            thickness_cm = float(self.thickness_um) * 0.0001
            probe = self.calculate_four_probe(sample_type=self.sample_type, is_n_type=self.is_n_type, diameter_mm=self.diameter_mm, thickness_um=self.thickness_um, current_ma=1.0, voltage_mv=1.0, probe_spacing_mm=self.probe_spacing_mm)
        except Exception:
            return None
        feasible = set()
        for candidate in candidates:
            current_a = float(candidate.current_a)
            try:
                k = coefficient_k(ADC_LSB_V, probe.fd, probe.fw, thickness_cm, probe.fsp, current_a)
                k_rs = coefficient_k_rs(ADC_LSB_V, probe.fd, probe.fw, probe.fsp, current_a)
                k_q = quantize_coefficient_k(k, k_q_floor=K_Q_HW_MIN)
                k_rs_q = quantize_coefficient_k(k_rs, k_q_floor=K_Q_HW_MIN)
            except Exception:
                continue
            if k_q < K_Q_MIN and k_rs_q < K_Q_MIN:
                continue
            feasible.add(int(candidate.range_index))
        return feasible

    def _choose_range_for_candidates(self, candidates, fallback_range_index):
        """
        Pick the excitation range from RESISTIVITY_RANGE_TABLE.

        The pilot sweep already measured every range, so the sample resistance
        (and therefore rho) is known before the final range is chosen.  The
        table target is used when that range produced a usable probe voltage;
        otherwise the closest usable range is substituted and the substitution
        is reported.
        """
        measured = [candidate for candidate in candidates if candidate.capture.valid_sample_count > 0 and math.isfinite(candidate.filtered_probe_voltage_v)]
        estimates = []
        for candidate in measured:
            try:
                rho = self._candidate_resistivity_ohm_cm(candidate)
            except Exception:
                continue
            estimates.append((abs(candidate.filtered_probe_voltage_v), candidate, rho))
        if not estimates:
            return (int(fallback_range_index), 'table:no resistivity estimate, using highest-current range', None)
        in_window = [item for item in estimates if item[1].eligible]
        source = max(in_window or estimates, key=lambda item: item[0])
        rho_estimate = source[2]
        target_index, target_current = range_index_for_resistivity(rho_estimate)
        if target_index in {item[1].range_index for item in in_window}:
            note = 'table:rho=%.6g ohm_cm -> R%d (%.4g A)' % (rho_estimate, target_index, target_current)
            return (int(target_index), note, rho_estimate)
        usable = sorted({item[1].range_index for item in in_window})
        if usable:
            chosen = min(usable, key=lambda index: (abs(index - target_index), -index))
            note = 'table:rho=%.6g ohm_cm -> R%d unavailable, substituted R%d' % (rho_estimate, target_index, chosen)
            return (int(chosen), note, rho_estimate)
        return (int(fallback_range_index), 'table:rho=%.6g ohm_cm but no usable range, fallback R%d' % (rho_estimate, int(fallback_range_index)), rho_estimate)

    def _failed_point_record(self, point, attempts, reason, quality=None):
        """Neutral record for a point whose measurement never succeeded."""
        range_index = self.selected_range_index
        if range_index is None:
            forward_current = 0.0
            reverse_current = 0.0
            current_calibrated = False
            polarity_current_calibrated = False
        else:
            forward_current, reverse_current, current_calibrated, polarity_current_calibrated = self._currents_for_range(range_index)
        record = {'point': point.label, 'scan_type': point.scan_type, 'point_valid': False, 'measurement_attempts': int(attempts), 'measurement_error': reason, 'range_index': None if range_index is None else int(range_index), 'range_selection_note': self.range_selection_note, 'range_selection_resistivity_ohm_cm': self.range_selection_resistivity_ohm_cm, 'calibration_valid': bool(current_calibrated), 'current_calibrated': bool(current_calibrated), 'polarity_current_calibrated': bool(polarity_current_calibrated), 'ring': int(point.ring), 'point_index': int(point.point_index), 'r_home_steps': int(point.r_home_steps), 'r_offset_steps': int(point.r_offset_steps), 'r_offset_mm': point.r_offset_steps / float(R_STEPS_PER_MM), 'x_pulses': int(point.x_pulses), 'x_deg': float(point.x_deg), 'z_steps': int(point.z_steps), 'forward_current_a': forward_current, 'reverse_current_a': reverse_current, 'equivalent_current_a': 0.0, 'probe_voltage_offset_forward_v': None, 'probe_voltage_offset_reverse_v': None, 'voltage_domain': 'adc_native', 'forward_raw_voltage_v': 0.0, 'reverse_raw_voltage_v': 0.0, 'forward_voltage_v': 0.0, 'forward_median_v': 0.0, 'reverse_voltage_v': 0.0, 'reverse_median_v': 0.0, 'combined_voltage_v': 0.0, 'forward_resistance_ohm': 0.0, 'reverse_resistance_ohm': 0.0, 'combined_resistance_ohm': 0.0, 'forward_reverse_delta_v': 0.0, 'polarity_same_sign': False, 'forward_valid_samples': 0, 'reverse_valid_samples': 0, 'forward_std_v': 0.0, 'reverse_std_v': 0.0, 'forward_min_code': None, 'forward_max_code': None, 'reverse_min_code': None, 'reverse_max_code': None, 'sample_type': getattr(self.sample_type, 'value', str(self.sample_type)), 'is_n_type': bool(self.is_n_type), 'diameter_mm': self.diameter_mm, 'thickness_um': self.thickness_um, 'probe_spacing_mm': self.probe_spacing_mm, 'model_error': reason, 'pair_margin_v': None, 'offset_estimate_v': None, 'pair_span_s': None, 'current_path_ratio': None, 'rho_source': None, 'rho_pl_ohm_cm': None, 'rho_pl_details': None, 'resistivity_ohm_cm': None, 'sheet_resistance_ohm_sq': None, 'ndop_cm3': None, 'fd': None, 'fw': None, 'fsp': None, 'used_table_type': None, 'rho_exp': None, 'rho_mant': None, 'rs_exp': None, 'rs_mant': None, 'ndop_exp': None, 'ndop_mant': None}
        if self.selected_candidates:
            record['range_selection'] = [{'range_index': candidate.range_index, 'valid_samples': candidate.capture.valid_sample_count, 'filtered_voltage_v': candidate.filtered_probe_voltage_v, 'resistance_ohm': candidate.resistance_ohm, 'eligible': candidate.eligible, 'reason': candidate.reason} for candidate in self.selected_candidates]
        record['sample_label'] = self.sample_label
        record.update(quality if quality is not None else evaluate_quality({}))
        return record

    def _prepare_pl_autorange(self):
        """Identify FP_DSP, write its configuration (read back exactly) and claim it.

        The enabled ranges, the calibrated per-polarity currents and the per-bank centre
        codes are taken from THIS system, so PL judges with the same numbers the PS model
        later computes with.
        """
        driver = self.pl_autorange
        try:
            self.pl_autorange_identity = driver.identify()
            if driver.status()['busy']:
                driver.abort()
                driver.wait_idle()
            mask = 0
            for index in self.range_indices:
                mask |= 1 << int(index)
            forward = [self._currents_for_range(r)[0] for r in range(4)]
            reverse = [self._currents_for_range(r)[1] for r in range(4)]
            centers = [self._pl_stats_window_params(r, reverse_pol)[0] for reverse_pol in (False, True) for r in range(4)]
            driver.configure(forward, reverse, centers, config=replace(driver.config, range_mask=mask))
            driver.claim()
        except PlAutorangeError as exc:
            raise FinalSystemError('PL auto-ranging unusable: %s. Load an all_design.bit that contains FP_DSP, or set USE_PL_AUTORANGE=False.' % (exc,))

    def _release_pl_autorange(self):
        driver = self.pl_autorange
        try:
            if driver.status()['busy']:
                driver.abort()
                driver.wait_idle()
            driver.release()
        except Exception as exc:
            print('PL auto-ranging release failed: %r' % (exc,))

    def _pl_candidates(self, result):
        """FP_DSP pilot pairs in the shape the record / current-path guard expect."""
        volts_per_code = ADC_LSB_V
        candidates = []
        for pilot in result.pilots:
            forward, reverse, _, _ = self._currents_for_range(pilot.range_index)
            signal_v = pilot.signal_q8 / 256.0 * volts_per_code
            i_eq = 0.5 * (forward + reverse)
            candidates.append(SimpleNamespace(range_index=int(pilot.range_index), current_a=float(forward), filtered_probe_voltage_v=float(signal_v), resistance_ohm=signal_v / i_eq if i_eq > 0.0 else 0.0, eligible=True, reason='pl pilot pair', capture=SimpleNamespace(valid_sample_count=min(int(pilot.samples_forward), int(pilot.samples_reverse)))))
        return tuple(candidates)

    def _pl_low_resistance_open(self, result):
        """Distinguish a low-resistance sample from a true open current loop.

        The PL open-loop rule uses a two-code noise floor.  A real 0.2-0.3 ohm
        sample can therefore trip it even though the offset-cancelled signal is
        still present.  If a pilot candidate has a signal above that floor and
        a finite resistance below 1 ohm, report the point as unmeasurable/low
        signal instead of aborting the whole scan.
        """
        try:
            candidates = self._pl_candidates(result) if result.pilots else ()
        except Exception:
            return False
        noise_v = 2.0 * ADC_LSB_V
        for candidate in candidates:
            try:
                signal_v = abs(float(candidate.filtered_probe_voltage_v))
                resistance = float(candidate.resistance_ohm)
            except (TypeError, ValueError):
                continue
            if signal_v > noise_v and 0.0 < resistance < 1.0:
                return True
        return False

    def _measure_point_once_pl(self, point, first_point=False, force_range_index=None):
        """One point on the FP_DSP path; the PS keeps the model and the record.

        First point: FULL (up-ranging pilot).  Later points: VERIFY the locked range,
        except at the highest enabled range where VERIFY would rerange on a legitimate
        low signal even though no higher range exists; there we use FORCED.  A retry
        asks for a fresh FULL selection instead of the PS's one-step escalation.
        """
        driver = self.pl_autorange
        if force_range_index is not None or first_point or self.selected_range_index is None or self.reselect_range_every_point:
            mode, locked = (PL_MODE_FULL, 0)
        elif int(self.selected_range_index) == max(self.range_indices):
            mode, locked = (PL_MODE_FORCED, int(self.selected_range_index))
        else:
            mode, locked = (PL_MODE_VERIFY, int(self.selected_range_index))
        started = monotonic()
        try:
            result = driver.run(mode, locked, abort_check=self._raise_if_measurement_aborted)
        except PlAutorangeError as exc:
            raise PlAutorangeFatalError('FP_DSP run failed at point %s: %s' % (point.label, exc))
        span_s = monotonic() - started
        pl_record = result.as_record()
        if not result.ok:
            text = 'FP_DSP %s at point %s (flags %s, tested R%s)' % (result.reason_name, point.label, ','.join(result.flag_names) or '-', ','.join((str(r) for r in range(4) if result.tested_mask & 1 << r)))
            if result.reason == PL_R_OPEN_LOOP:
                if self._pl_low_resistance_open(result):
                    self.range_selection_note = 'pl:low signal/unmeasurable low resistance (not an open loop)'
                    return self._failed_point_record(point, 1, self.range_selection_note)
                raise OpenCurrentLoopError(text + ': open current loop -- the pilot signal did not follow the current.  Scan stopped before point %s; check the probe contact and the current loop.' % (point.label,))
            if result.reason == PL_R_SAFETY_ABORT:
                raise MeasurementAbortedError(text)
            if result.reason in (PL_R_CONFIG_ERROR, PL_R_AXI_ERROR, PL_R_OWNERSHIP_CONFLICT):
                raise PlAutorangeFatalError(text)
            raise FinalSystemError(text)
        range_index = int(result.selected_range)
        candidates = self._pl_candidates(result) if result.pilots else ()
        if candidates:
            self.selected_candidates = candidates
        self.selected_range_index = range_index
        mode_name = 'FULL' if mode == PL_MODE_FULL or result.reranged else 'FORCED' if mode == PL_MODE_FORCED else 'VERIFY'
        self.range_selection_note = 'pl:%s %s -> R%d%s' % (mode_name, result.reason_name, range_index, ' [%s]' % ','.join(result.flag_names) if result.flags else '')
        self.range_selection_resistivity_ohm_cm = None
        forward_current, reverse_current, current_calibrated, polarity_current_calibrated = self._currents_for_range(range_index)
        if self.on_range_selected is not None and self._hmi_range_index != range_index:
            self.on_range_selected(range_index, forward_current, reverse_current)
            self._hmi_range_index = range_index
        halves = []
        for reverse_pol, current_a in ((False, forward_current), (True, reverse_current)):
            halves.append(_range_measurement_from_snapshot(result.snapshot(reverse_pol, self.pl_stats_min_valid_samples), range_index=range_index, reverse=reverse_pol, current_a=current_a, probe_voltage_offset_v=self._quiet_zero_for(range_index, reverse_pol), probe_abs_min_v=self.probe_abs_min_v, probe_abs_max_v=self.probe_abs_max_v))
        measurement = combine_bidirectional(halves[0], halves[1], range_index, forward_current_a=forward_current, reverse_current_a=reverse_current)
        return self._finish_point_record(point, range_index, measurement, candidates, span_s, current_calibrated, polarity_current_calibrated, pl_autorange_record=pl_record)

    def _measure_point(self, point, first_point=False):
        """Native ADC voltage measurement. Units are volts, amperes and seconds unless stated otherwise."""
        return self._measure_point_attempts(point, first_point)

    def _measure_point_attempts(self, point, first_point=False):
        """Acquire one point, retrying a failed acquisition before giving up.

        A failed measurement criterion no longer aborts the whole scan: the
        point is retried up to `measurement_retry_count` times and is then
        recorded with point_valid=False so the scan can continue.

        By default a retry clears the lock and runs a FRESH pilot; setting
        ``full_range_reselect_on_retry=False`` restores the old one-step forced-range
        policy.  Both paths write ``self.selected_range_index``, and that attribute
        outlives this point -- it is reset only at ``run_scan`` entry.  The entry values
        are therefore saved and restored on a failed attempt, or one flaky point would
        poison every later point.
        """
        attempts_allowed = 1 + max(0, int(self.measurement_retry_count))
        last_error = None
        last_quality = None
        for attempt in range(1, attempts_allowed + 1):
            forced = None
            full_reselect = False
            if attempt > 1 and self.reselect_range_on_retry:
                if self.full_range_reselect_on_retry:
                    full_reselect = True
                else:
                    base = self.selected_range_index
                    if base is not None:
                        step = -1 if 'overflow' in (last_error or '').lower() else 1
                        low, high = (min(self.range_indices), max(self.range_indices))
                        forced = max(low, min(high, int(base) + (attempt - 1) * step))
            saved_range = self.selected_range_index
            saved_note = self.range_selection_note
            saved_rho = self.range_selection_resistivity_ohm_cm
            if full_reselect:
                self.selected_range_index = None
                self.range_selection_note = '%s | retry full pilot' % (saved_note or 'range inherited')
                self.range_selection_resistivity_ohm_cm = None
            success = False
            try:
                try:
                    record = self._measure_point_once(point, first_point=first_point, force_range_index=forced)
                except (MeasurementAbortedError, OpenCurrentLoopError, PlAutorangeFatalError):
                    raise
                except Exception as exc:
                    last_error = '%s: %s' % (type(exc).__name__, exc)
                    last_quality = exc.quality if isinstance(exc, MeasurementQualityError) else None
                    print('point %s attempt %d/%d failed: %s' % (point.label, attempt, attempts_allowed, last_error))
                    if attempt < attempts_allowed and self.measurement_retry_delay_s > 0.0:
                        sleep(self.measurement_retry_delay_s)
                    continue
                record['measurement_attempts'] = int(attempt)
                if not record.get('point_valid', False):
                    return record
                record['measurement_error'] = None
                success = True
                return record
            finally:
                if forced is not None:
                    self.selected_range_index = saved_range
                    self.range_selection_note = saved_note
                elif full_reselect and (not success):
                    self.selected_range_index = saved_range
                    self.range_selection_note = saved_note
                    self.range_selection_resistivity_ohm_cm = saved_rho
        return self._failed_point_record(point, attempts_allowed, last_error, quality=last_quality)

    def _measure_point_once(self, point, first_point=False, force_range_index=None):
        if self.pl_autorange is not None:
            return self._measure_point_once_pl(point, first_point, force_range_index)
        candidates = ()
        if force_range_index is not None:
            forced = max(0, min(3, int(force_range_index)))
            if forced != self.selected_range_index:
                self.selected_range_index = forced
                self.range_selection_note = '%s | retry -> R%d' % (self.range_selection_note or 'range inherited', forced)
                if int(self.zero_offset_samples) > 0:
                    self._measure_quiet_zeros((forced,))
            else:
                self.range_selection_note = '%s | retry R%d (already at the top range)' % (self.range_selection_note or 'range inherited', forced)
        selecting_range = force_range_index is None and (first_point or self.selected_range_index is None or self.reselect_range_every_point)
        if int(self.zero_offset_samples) > 0:
            if selecting_range:
                self.quiet_zero_by_bank = {}
                self._measure_quiet_zeros((0, 1, 2, 3))
            elif self.selected_range_index is not None:
                self._measure_quiet_zeros((int(self.selected_range_index),))
        if selecting_range:
            best, candidates = select_current_range(self.frontend, self.monitor, range_indices=self.range_indices, sample_count=self.range_selection_sample_count, interval_s=self.sample_interval_s, discard_first=self.discard_first, settle_s=self.range_settle_s, timeout_s=min(self.capture_timeout_s, RANGE_SELECTION_TIMEOUT_S), configure_timeout_s=2.0, adc_input_min_v=self.adc_input_min_v, adc_input_max_v=self.adc_input_max_v, probe_abs_min_v=self.probe_abs_min_v, probe_abs_max_v=self.probe_abs_max_v, probe_voltage_offset_by_range_v=[self._quiet_zero_for(index, False) for index in (0, 1, 2, 3)], bipolar=self.pilot_bipolar, adc_config_settle_s=self.adc_config_settle_s, abort_check=self._raise_if_measurement_aborted, capture_source=self._capture_pl_window_snapshot if self.window_stats is not None else None)
            self.selected_candidates = candidates
            open_loop = open_current_loop_diagnosis(candidates)
            if open_loop is not None:
                raise OpenCurrentLoopError(open_loop)
            if self.select_range_by_resistivity:
                try:
                    range_index, note, rho_estimate = self._choose_range_for_candidates(candidates, fallback_range_index=int(best.range_index))
                except Exception as exc:
                    range_index = int(best.range_index)
                    note = 'table failed (%r), using highest-current range' % (exc,)
                    rho_estimate = None
            else:
                range_index = int(best.range_index)
                measured_voltages = [(candidate.range_index, abs(candidate.filtered_probe_voltage_v)) for candidate in candidates if candidate.capture.valid_sample_count > 0 and math.isfinite(candidate.filtered_probe_voltage_v)]
                try:
                    range_index, note = range_index_for_voltage_window(measured_voltages, v_min=self.probe_abs_min_v, v_max=self.probe_abs_max_v, feasible=self._k_feasible_range_indices(candidates))
                except Exception as exc:
                    range_index = int(best.range_index)
                    note = 'window failed (%r), using highest-current range' % (exc,)
                rho_estimate = None
                rho_estimate = None
            self.selected_range_index = int(range_index)
            self.range_selection_note = note
            self.range_selection_resistivity_ohm_cm = rho_estimate
        if self.selected_range_index is None:
            raise FinalSystemError('current range has not been selected')
        range_index = self.selected_range_index
        forward_current, reverse_current, current_calibrated, polarity_current_calibrated = self._currents_for_range(range_index)
        if self.on_range_selected is not None and self._hmi_range_index != range_index:
            self.on_range_selected(range_index, forward_current, reverse_current)
            self._hmi_range_index = range_index
        pair_started = monotonic()
        measurement = measure_bidirectional(self.frontend, self.monitor, range_index, sample_count=self.valid_sample_count, interval_s=self.sample_interval_s, discard_first=self.discard_first, settle_s=self.bidirectional_settle_s, timeout_s=self.capture_timeout_s, configure_timeout_s=2.0, adc_input_min_v=self.adc_input_min_v, adc_input_max_v=self.adc_input_max_v, probe_abs_min_v=self.probe_abs_min_v, probe_abs_max_v=self.probe_abs_max_v, forward_current_a=forward_current, reverse_current_a=reverse_current, forward_probe_voltage_offset_v=self._quiet_zero_for(range_index, False), reverse_probe_voltage_offset_v=self._quiet_zero_for(range_index, True), adc_config_settle_s=self.adc_config_settle_s, abort_check=self._raise_if_measurement_aborted, capture_source=self._capture_pl_window_snapshot if self.window_stats is not None else None, zero_offset_samples=0)
        pair_span_s = monotonic() - pair_started
        return self._finish_point_record(point, range_index, measurement, candidates, pair_span_s, current_calibrated, polarity_current_calibrated)

    def _finish_point_record(self, point, range_index, measurement, candidates, pair_span_s, current_calibrated, polarity_current_calibrated, pl_autorange_record=None):
        """Model, PL rho cross-check and the point record -- shared by the PS and PL paths.

        ``pl_autorange_record`` (2026-10-18) marks a point measured by FP_DSP.  ALL_Final's
        meas_calc computes from the stats banks the PS arms during ITS captures; on the PL
        path those banks are not armed, so the fixed-point cross-check is skipped (and
        said so in the record) instead of comparing against stale windows.
        """
        if self.check_current_path:
            self._check_current_path(measurement, range_index)
        pair_threshold_v = self._check_pair_significance(measurement)
        quality = evaluate_quality(dict(forward_resistance_ohm=measurement.forward_resistance_ohm, reverse_resistance_ohm=measurement.reverse_resistance_ohm, combined_resistance_ohm=measurement.combined_resistance_ohm, pair_margin_v=None if getattr(measurement, 'signed_sum_v', None) is None else 0.5 * measurement.signed_sum_v, offset_estimate_v=None if measurement.combined_resistance_ohm is None else measurement.forward.filtered_probe_voltage_v - measurement.forward_current_a * measurement.combined_resistance_ohm), candidates, max_polarity_asymmetry=self.max_polarity_asymmetry, max_offset_to_signal_ratio=self.max_offset_to_signal_ratio, max_range_nonlinearity=self.max_range_nonlinearity)
        if quality['quality_flags']:
            raise MeasurementQualityError(quality)
        current_ma = measurement.equivalent_current_a * 1000.0
        voltage_mv = measurement.combined_probe_voltage_v * 1000.0
        point_valid = True
        model_error = None
        try:
            model_result = self.calculate_four_probe(sample_type=self.sample_type, is_n_type=self.is_n_type, diameter_mm=self.diameter_mm, thickness_um=self.thickness_um, current_ma=current_ma, voltage_mv=voltage_mv, probe_spacing_mm=self.probe_spacing_mm)
        except Exception as exc:
            point_valid = False
            model_error = repr(exc)
            model_result = None
        pl_rho = None
        pl_details = None
        pair_repeats = int(getattr(measurement, 'pair_repeats', 1))
        pl_rho_skipped_reason = None
        if self.pl_calc is not None and model_result is not None and (pl_autorange_record is None) and (pair_repeats <= 1):
            try:
                pl_rho, pl_details = self._pl_rho_pair(range_index, model_result, measurement)
            except PlCalcError as exc:
                raise FinalSystemError('PL rho failed at point %s: %s' % (point.label, exc))
        record = {'point': point.label, 'scan_type': point.scan_type, 'point_valid': bool(point_valid), 'range_index': int(range_index), 'range_selection_note': self.range_selection_note, 'range_selection_resistivity_ohm_cm': self.range_selection_resistivity_ohm_cm, 'rho_source': pl_details['rho_source'] if pl_details is not None else 'model', 'rho_pl_ohm_cm': None if pl_rho is None else float(pl_rho), 'rho_pl_details': pl_details, 'pl_rho_skipped_reason': pl_rho_skipped_reason if pl_rho_skipped_reason else 'pair_repeats>1: PL banks hold only the last pair' if pair_repeats > 1 else None, 'pair_significance_threshold_v': float(pair_threshold_v), 'pair_std_v': getattr(measurement, 'pair_std_v', None), 'pair_values_v': list(getattr(measurement, 'pair_values_v', ())), 'pair_repeats': pair_repeats, 'calibration_valid': bool(current_calibrated), 'current_calibrated': bool(current_calibrated), 'polarity_current_calibrated': bool(polarity_current_calibrated), 'ring': int(point.ring), 'point_index': int(point.point_index), 'r_home_steps': int(point.r_home_steps), 'r_offset_steps': int(point.r_offset_steps), 'r_offset_mm': point.r_offset_steps / float(R_STEPS_PER_MM), 'x_pulses': int(point.x_pulses), 'x_deg': float(point.x_deg), 'z_steps': int(point.z_steps), 'forward_current_a': measurement.forward_current_a, 'reverse_current_a': measurement.reverse_current_a, 'equivalent_current_a': measurement.equivalent_current_a, 'probe_voltage_offset_forward_v': measurement.forward.probe_voltage_offset_v, 'probe_voltage_offset_reverse_v': measurement.reverse.probe_voltage_offset_v, 'voltage_domain': 'adc_native', 'forward_raw_voltage_v': measurement.forward.raw_filtered_probe_voltage_v, 'reverse_raw_voltage_v': measurement.reverse.raw_filtered_probe_voltage_v, 'forward_voltage_v': measurement.forward.filtered_probe_voltage_v, 'forward_median_v': measurement.forward.median_probe_voltage_v, 'reverse_voltage_v': measurement.reverse.filtered_probe_voltage_v, 'reverse_median_v': measurement.reverse.median_probe_voltage_v, 'combined_voltage_v': measurement.combined_probe_voltage_v, 'forward_resistance_ohm': measurement.forward_resistance_ohm, 'reverse_resistance_ohm': measurement.reverse_resistance_ohm, 'combined_resistance_ohm': measurement.combined_resistance_ohm, 'pair_margin_v': None if getattr(measurement, 'signed_sum_v', None) is None else 0.5 * float(measurement.signed_sum_v), 'offset_estimate_v': None if getattr(measurement, 'combined_resistance_ohm', None) is None else float(measurement.forward.filtered_probe_voltage_v - measurement.forward_current_a * measurement.combined_resistance_ohm), 'pair_span_s': float(pair_span_s), 'current_path_ratio': None if self._current_path_ratio(measurement, range_index) is None else float(self._current_path_ratio(measurement, range_index)[2]), 'forward_reverse_delta_v': measurement.forward_reverse_delta_v, 'zero_offset_forward_v': self.quiet_zero_by_bank.get((range_index, False)), 'zero_offset_reverse_v': self.quiet_zero_by_bank.get((range_index, True)), 'zero_offset_source': 'quiet_measured' if (range_index, False) in self.quiet_zero_by_bank else 'table', 'polarity_same_sign': bool(measurement.polarity_same_sign), 'forward_valid_samples': measurement.forward.capture.valid_sample_count, 'reverse_valid_samples': measurement.reverse.capture.valid_sample_count, 'forward_std_v': measurement.forward.std_probe_voltage_v, 'reverse_std_v': measurement.reverse.std_probe_voltage_v, 'forward_min_code': getattr(measurement.forward, 'min_code', None), 'forward_max_code': getattr(measurement.forward, 'max_code', None), 'reverse_min_code': getattr(measurement.reverse, 'min_code', None), 'reverse_max_code': getattr(measurement.reverse, 'max_code', None), 'sample_type': getattr(self.sample_type, 'value', str(self.sample_type)), 'is_n_type': bool(self.is_n_type), 'diameter_mm': self.diameter_mm, 'thickness_um': self.thickness_um, 'probe_spacing_mm': self.probe_spacing_mm, 'model_error': model_error}
        if model_result is not None:
            record.update({'resistivity_ohm_cm': model_result.resistivity_ohm_cm, 'sheet_resistance_ohm_sq': model_result.sheet_resistance_ohm_per_square, 'ndop_cm3': model_result.ndop_cm3, 'fd': model_result.fd, 'fw': model_result.fw, 'fsp': model_result.fsp, 'used_table_type': model_result.used_table_type, 'rho_exp': model_result.rho_scientific.exponent, 'rho_mant': model_result.rho_scientific.mantissa, 'rs_exp': model_result.sheet_scientific.exponent, 'rs_mant': model_result.sheet_scientific.mantissa, 'ndop_exp': model_result.ndop_scientific.exponent, 'ndop_mant': model_result.ndop_scientific.mantissa})
        else:
            record.update({'resistivity_ohm_cm': None, 'sheet_resistance_ohm_sq': None, 'ndop_cm3': None, 'fd': None, 'fw': None, 'fsp': None, 'used_table_type': None, 'rho_exp': None, 'rho_mant': None, 'rs_exp': None, 'rs_mant': None, 'ndop_exp': None, 'ndop_mant': None})
        if pl_autorange_record is not None:
            record['pl_autorange'] = pl_autorange_record
            if self.pl_calc is not None:
                record['rho_pl_skipped'] = 'PL auto-ranging path: ALL_Final stats banks were not armed, meas_calc cross-check not run'
        if candidates:
            record['range_selection'] = [{'range_index': candidate.range_index, 'valid_samples': candidate.capture.valid_sample_count, 'filtered_voltage_v': candidate.filtered_probe_voltage_v, 'resistance_ohm': candidate.resistance_ohm, 'eligible': candidate.eligible, 'reason': candidate.reason} for candidate in candidates]
        record['sample_label'] = self.sample_label
        record.update(quality)
        return record

    def _x_target_for_point(self, point):
        if point.ring == 0:
            return 0
        return (point.ring - 1) * self.x_pulses_per_rev + point.x_pulses

    @staticmethod
    def normalize_scan_mode(mode):
        mode = str(mode).strip().lower()
        if mode in ('9', 'nine', '9point'):
            return '9'
        if mode in ('25', 'twentyfive', '25point'):
            return '25'
        if mode in ('single', 'one', 'point'):
            return 'single'
        raise ValueError("mode must be '9', '25', or 'single'")

    def resolve_scan(self, mode, selected_point_index=None):
        mode = self.normalize_scan_mode(mode)
        if mode == 'single':
            if selected_point_index is None:
                raise ValueError('selected_point_index is required for single mode')
            plan = self.build_scan_plan(25)
            index = int(selected_point_index)
            if index < 1 or index > len(plan):
                raise ValueError('selected_point_index must be 1..%d' % len(plan))
            return (mode, [plan[index - 1]], plan)
        plan = self.build_scan_plan(int(mode))
        return (mode, plan, plan)

    def run_scan(self, mode, selected_point_index=None):
        mode, points, plan = self.resolve_scan(mode, selected_point_index)
        point_count = len(plan)
        self.results = []
        self._hmi_range_index = None
        self.selected_range_index = None
        self.selected_candidates = ()
        self.range_selection_note = None
        self.range_selection_resistivity_ohm_cm = None
        self.last_error = None
        self.last_summary = None
        self.stop_result = None
        self.shutdown_result = None
        self.safety_cleanup = None
        self._scan_return_x = None
        self._current_x_target = 0
        completed = False
        total_points = 0
        valid_points = 0
        invalid_points = 0
        quality_ok = False
        try:
            if self._manual_rehome_required:
                raise MeasurementAbortedError('Manual rehome required after reset/clear')
            self.preflight()
            self.axis_home(REG_Z_CONTROL, REG_Z_COMMAND, REG_Z_STATUS, REG_Z_ERROR, self.z_timeout_s, 'Z_HOME', abort_check=self._raise_if_measurement_aborted)
            self.verify_axis_home(REG_Z_STATUS, REG_Z_POSITION, 'Z_HOME')
            self.axis_home(REG_R_CONTROL, REG_R_COMMAND, REG_R_STATUS, REG_R_ERROR, self.r_timeout_s, 'R_HOME', abort_check=self._raise_if_measurement_aborted)
            self.verify_axis_home(REG_R_STATUS, REG_R_POSITION, 'R_HOME')
            if mode == 'single':
                self._scan_return_x = points[0].ring * self.x_pulses_per_rev
            else:
                self._scan_return_x = (1 if point_count == 9 else 2) * self.x_pulses_per_rev
            current_r = 0
            current_x = 0
            for point_index, point in enumerate(points):
                label = point.label
                self.frontend.safe_off()
                if point_index > 0:
                    self.z_move_to(self.z_lateral_lift_steps, label + '_Z_UP', abort_check=self._raise_if_measurement_aborted)
                target_r = point.r_home_steps
                if target_r != current_r:
                    self.r_move_to(target_r, label + '_R_MOVE', abort_check=self._raise_if_measurement_aborted)
                    current_r = target_r
                target_x = self._x_target_for_point(point)
                if target_x != current_x:
                    self.x_rotate_pulses(target_x - current_x, label + '_X_MOVE', abort_check=self._raise_if_measurement_aborted)
                    current_x = target_x
                    self._current_x_target = current_x
                self.z_move_to_measure(self.full_down_steps, label + '_Z_DOWN', abort_check=self._raise_if_measurement_aborted)
                record = self._measure_point(point, first_point=point_index == 0)
                self.results.append(record)
                if self.on_point is not None:
                    self.on_point(record)
                if not record['point_valid']:
                    print('point %s invalid after %d attempt(s): %s -- continuing with the next point' % (label, record.get('measurement_attempts', 0), record.get('measurement_error') or record.get('model_error')))
                self.z_move_to(self.z_lateral_lift_steps, label + '_Z_HALF_UP', abort_check=self._raise_if_measurement_aborted)
                if self.z_rehome_interval_points > 0 and (point_index + 1) % self.z_rehome_interval_points == 0 and (point_index + 1 < len(points)):
                    self.frontend.safe_off()
                    self.axis_home(REG_Z_CONTROL, REG_Z_COMMAND, REG_Z_STATUS, REG_Z_ERROR, self.z_timeout_s, label + '_Z_REHOME', abort_check=self._raise_if_measurement_aborted)
                    self.verify_axis_home(REG_Z_STATUS, REG_Z_POSITION, label + '_Z_REHOME')
            if mode != 'single':
                ring_count = 1 if point_count == 9 else 2
                end_x = ring_count * self.x_pulses_per_rev
                if current_x != end_x:
                    self.x_rotate_pulses(end_x - current_x, 'X_SCAN_RETURN', abort_check=self._raise_if_measurement_aborted)
                    current_x = end_x
                    self._current_x_target = current_x
            elif points[0].ring != 0:
                end_x = points[0].ring * self.x_pulses_per_rev
                if current_x < end_x:
                    self.x_rotate_pulses(end_x - current_x, 'X_SINGLE_RETURN', abort_check=self._raise_if_measurement_aborted)
                    current_x = end_x
                    self._current_x_target = current_x
            self.axis_home(REG_Z_CONTROL, REG_Z_COMMAND, REG_Z_STATUS, REG_Z_ERROR, self.z_timeout_s, 'Z_RETURN_HOME', abort_check=self._raise_if_measurement_aborted)
            self.verify_axis_home(REG_Z_STATUS, REG_Z_POSITION, 'Z_RETURN_HOME')
            self.axis_home(REG_R_CONTROL, REG_R_COMMAND, REG_R_STATUS, REG_R_ERROR, self.r_timeout_s, 'R_RETURN_HOME', abort_check=self._raise_if_measurement_aborted)
            self.verify_axis_home(REG_R_STATUS, REG_R_POSITION, 'R_RETURN_HOME')
            total_points = len(self.results)
            valid_points = sum((1 for record in self.results if record.get('point_valid')))
            invalid_points = total_points - valid_points
            completed = valid_points > 0
            valid_ratio = valid_points / float(total_points) if total_points else 0.0
            quality_ok = scan_quality_ok(bool(total_points) and valid_ratio >= self.min_quality_valid_ratio, 0)
            pl_quality_points, pl_quality_failed = summarize_pl_quality(self.results)
            quality_ok = scan_quality_ok(quality_ok, pl_quality_failed)
            if not completed:
                self.last_error = 'no valid scan points'
            elif not quality_ok and pl_quality_failed:
                print('scan quality below threshold: %d of %d PL-judged points are out of the programmed limits' % (pl_quality_failed, pl_quality_points))
            elif not quality_ok:
                print('scan quality below threshold: %d/%d points valid (%.0f%% < %.0f%%)' % (valid_points, total_points, valid_ratio * 100.0, self.min_quality_valid_ratio * 100.0))
        except Exception as exc:
            self.last_error = str(exc)
            if isinstance(exc, MeasurementAbortedError):
                self.stop_result = self.stop_all_axes()
            self.shutdown_result = self.safe_shutdown()
            if not self.shutdown_result['ok']:
                self.last_error += ' | safe_shutdown: ' + '; '.join(self.shutdown_result['errors'])
            total_points = len(self.results)
            valid_points = sum((1 for record in self.results if record.get('point_valid')))
            invalid_points = total_points - valid_points
            quality_ok = False
        finally:
            if self.pl_autorange is not None:
                self._release_pl_autorange()
            self.frontend.safe_off()
            self.safety_cleanup = self.finish_safety_cleanup()
        pl_quality_points, pl_quality_failed = summarize_pl_quality(self.results)
        summary = ScanSummary(completed, self.selected_range_index, list(self.results), self.last_error, total_points=total_points, valid_points=valid_points, invalid_points=invalid_points, quality_ok=quality_ok, min_quality_valid_ratio=self.min_quality_valid_ratio, pl_quality_judged_points=pl_quality_points, pl_quality_failed_points=pl_quality_failed)
        self.last_summary = summary
        return summary

    def save_results(self, output_dir=None):
        output_dir = Path.cwd() if output_dir is None else Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = output_dir / ('four_probe_scan_%s.json' % stamp)
        csv_path = output_dir / ('four_probe_scan_%s.csv' % stamp)
        try:
            pl_version = '0x%08X' % (self._read(REG_VERSION) & 4294967295)
        except Exception as exc:
            pl_version = None
            print('save_results: PL version read failed (%r)' % (exc,))
        summary = self.last_summary
        payload = {'sample_label': self.sample_label, 'schema_version': SCAN_RESULT_SCHEMA_VERSION, 'software': {'direct_adc_measurement_version': DIRECT_ADC_MEASUREMENT_VERSION, 'expected_pl_version': '0x%08X' % EXPECTED_PL_VERSION, 'pl_version': pl_version, 'min_quality_valid_ratio': self.min_quality_valid_ratio}, 'completed': self.last_error is None, 'pl_quality_judged_points': getattr(summary, 'pl_quality_judged_points', 0), 'pl_quality_failed_points': getattr(summary, 'pl_quality_failed_points', 0), 'selected_range_index': self.selected_range_index, 'range_selection_note': self.range_selection_note, 'range_selection_resistivity_ohm_cm': self.range_selection_resistivity_ohm_cm, 'invalid_points': [row['point'] for row in self.results if not row.get('point_valid')], 'shutdown_result': self.shutdown_result, 'error': self.last_error, 'quality_ok': None if summary is None else bool(summary.quality_ok), 'total_points': None if summary is None else int(summary.total_points), 'valid_points': None if summary is None else int(summary.valid_points), 'invalid_point_count': None if summary is None else int(summary.invalid_points), 'stop_result': self.stop_result, 'safety_cleanup': self.safety_cleanup, 'results': self.results}
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        rows = list(self.results)
        if rows:
            fieldnames = list(rows[0].keys())
            for row in rows[1:]:
                for key in row.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)
            with csv_path.open('w', newline='', encoding='utf-8') as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows((dict(row, quality_flags=json.dumps(row['quality_flags'])) if 'quality_flags' in row else row for row in rows))
        return (json_path, csv_path)
