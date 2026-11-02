# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

'FP_DSPv5 driver and integer golden decisions. NativeADC codes, ms and calibratednA; FULL/VERIFY/FORCED perform a singleF/R pair. Current switching remains underALL_Final safety and exclusive ownership. Advanced diagnostic engines are not present.'
from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple
import math
import time
try:
    from .direct_adc_measurement import ADC_LSB_V
    from .pl_window_stats import PlWindowSnapshot
except ImportError:
    from direct_adc_measurement import ADC_LSB_V
    from pl_window_stats import PlWindowSnapshot
PL_AUTORANGE_VERSION = 5
FPD_DEFAULT_BASE = 1136721920
FPD_ADDRESS_RANGE = 65536
FPD_ID = 1179665457
FPD_VERSION = 5
FPD_CAP_AUTORANGE = 1 << 4
FPD_CAP_MASTER = 1 << 10
REG_ID = 0
REG_VERSION = 4
REG_CAPS = 8
REG_STATUS = 12
REG_CONTROL = 16
REG_REASON = 20
REG_SAMPLE_COUNT = 24
REG_FRAME_DIAG = 28
REG_SAMPLE_RATE = 32
REG_MISMATCH = 36
REG_LAST_SAMPLE = 40
REG_ALLF_BASE = 44
REG_AXI_DIAG = 48
CTRL_START = 1 << 0
CTRL_ABORT = 1 << 1
CTRL_CLEAR = 1 << 2
CTRL_CLAIM = 1 << 3
CTRL_RELEASE = 1 << 4
CTRL_MODE_SHIFT = 8
CTRL_RANGE_SHIFT = 12
STATUS_BUSY = 1 << 0
STATUS_DONE = 1 << 1
STATUS_ERROR = 1 << 2
STATUS_OWNED = 1 << 3
STATUS_RESULT_VALID = 1 << 4
STATUS_AXI_HUNG = 1 << 5
MODE_FULL = 0
MODE_VERIFY = 1
MODE_FORCED = 2
MODE_NAMES = {MODE_FULL: 'FULL', MODE_VERIFY: 'VERIFY', MODE_FORCED: 'FORCED'}
CONFIG_REGISTERS = {'range_mask': (64, 4), 's_hi': (68, 16), 's_lo': (72, 16), 'raw_sat': (76, 16), 'lin_tol_q16': (80, 24), 'lin_min': (84, 16), 'open_vmax': (88, 16), 'open_iratio_q16': (92, 24), 'open_vratio_q16': (96, 24), 'noise_floor': (100, 16), 'hyst_q16': (104, 24), 'pilot_win_ms': (108, 16), 'meas_win_ms': (112, 16), 'pair_mode': (116, 4), 't_min_ms': (120, 16), 't_max_ms': (124, 16), 'eps_rel_q16': (128, 24), 'eps_abs_q8': (132, 16), 'warmup_ms': (136, 16), 'options': (140, 2), 't_skip_ms': (144, 16), 'seg_ms': (148, 16), 'settle_k': (152, 4), 'cfg_timeout_ms': (156, 16)}
REG_CENTER_BASE = 160
REG_IF_BASE = 192
REG_IR_BASE = 208
CURRENT_MAX_NA = (1 << 28) - 1
OPTION_SETTLE_ENABLE = 1 << 0
OPTION_ADC_REINIT = 1 << 1
RES_BASE = 256
RES_SELECT = 256
RES_REASON = 260
RES_RUN_MS = 264
RES_MISMATCH = 268
RES_PILOT_BASE = 272
RES_S = 384
RES_E = 388
RES_MF = 392
RES_MR = 396
RES_MF_FIRST = 400
RES_MF_LAST = 404
RES_SETTLE = 408
RES_WINDOWS = 412
RES_AGG_BASE = (416, 448)
R_OK = 0
R_OK_TOP = 1
R_OK_SAT_BACKOFF = 2
R_OK_NONLINEAR_BACKOFF = 3
R_OPEN_LOOP = 8
R_OVER_RANGE_AT_MIN = 9
R_NO_SAMPLES = 10
R_ANALOG_SEQ_ERROR = 11
R_SAFETY_ABORT = 12
R_OWNERSHIP_CONFLICT = 13
R_PS_ABORT = 14
R_AXI_ERROR = 15
R_CONFIG_ERROR = 16
REASON_NAMES = {R_OK: 'OK', R_OK_TOP: 'OK_TOP', R_OK_SAT_BACKOFF: 'OK_SAT_BACKOFF', R_OK_NONLINEAR_BACKOFF: 'OK_NONLINEAR_BACKOFF', R_OPEN_LOOP: 'OPEN_LOOP', R_OVER_RANGE_AT_MIN: 'OVER_RANGE_AT_MIN', R_NO_SAMPLES: 'NO_SAMPLES', R_ANALOG_SEQ_ERROR: 'ANALOG_SEQ_ERROR', R_SAFETY_ABORT: 'SAFETY_ABORT', R_OWNERSHIP_CONFLICT: 'OWNERSHIP_CONFLICT', R_PS_ABORT: 'PS_ABORT', R_AXI_ERROR: 'AXI_ERROR', R_CONFIG_ERROR: 'CONFIG_ERROR'}
F_LOW_SIGNAL = 1
F_ABOVE_TARGET_AT_MIN = 2
F_RERANGED = 4
F_SETTLE_TIMEOUT = 8
FLAG_NAMES = {F_LOW_SIGNAL: 'LOW_SIGNAL', F_ABOVE_TARGET_AT_MIN: 'ABOVE_TARGET_AT_MIN', F_RERANGED: 'RERANGED', F_SETTLE_TIMEOUT: 'SETTLE_TIMEOUT'}

class PlAutorangeError(RuntimeError):
    """FP_DSP is missing, misconfigured, or a run did not complete."""

def flag_names(flags: int) -> Tuple[str, ...]:
    return tuple((name for bit, name in sorted(FLAG_NAMES.items()) if int(flags) & bit))

def volts_per_code() -> float:
    return ADC_LSB_V

@dataclass(frozen=True)
class AutorangeRegisters:
    """Integer register image; the golden model works on exactly these numbers."""
    range_mask: int
    s_hi: int
    s_lo: int
    raw_sat: int
    lin_tol_q16: int
    lin_min: int
    open_vmax: int
    open_iratio_q16: int
    open_vratio_q16: int
    noise_floor: int
    hyst_q16: int
    pilot_win_ms: int
    meas_win_ms: int
    pair_mode: int
    t_min_ms: int
    t_max_ms: int
    eps_rel_q16: int
    eps_abs_q8: int
    warmup_ms: int
    options: int
    t_skip_ms: int
    seg_ms: int
    settle_k: int
    cfg_timeout_ms: int

    def validate(self) -> 'AutorangeRegisters':
        for name, (_, bits) in CONFIG_REGISTERS.items():
            value = int(getattr(self, name))
            if value < 0 or value >= 1 << bits:
                raise ValueError('%s=%d does not fit %d bits' % (name, value, bits))
        if self.range_mask == 0:
            raise ValueError('range_mask must enable at least one range')
        if self.pair_mode != 1:
            raise ValueError('pair_mode must be 1')
        for name in ('pilot_win_ms', 'meas_win_ms', 'seg_ms', 't_max_ms', 'cfg_timeout_ms', 'settle_k', 's_hi'):
            if int(getattr(self, name)) <= 0:
                raise ValueError('%s must be positive' % name)
        if self.t_min_ms > self.t_max_ms:
            raise ValueError('t_min_ms must not exceed t_max_ms')
        return self

@dataclass(frozen=True)
class AutorangeConfig:
    """Operator-facing FP_DSP settings in physical units (defaults: SNR preset).

    Voltages are PROBE-side volts, converted with the probe voltage scale into ADC codes.
    The TABLE preset (``table_preset()``) reproduces the recommended sheet-resistance
    table on the hardware ranges: target 4.41 .. 55.2 mV with the table's 25 % overlap.
    """
    range_mask: int = 7
    s_hi_v: float = 0.5
    s_lo_v: float = 0.02
    raw_sat_v: float = 1.6
    lin_tol: float = 0.02
    lin_min_v: float = 0.0125
    open_vmax_v: float = 0.015
    open_iratio: float = 5.0
    open_vratio: float = 2.0
    noise_floor_codes: int = 2
    hysteresis: float = 1.25
    pilot_window_ms: int = 100
    measure_window_ms: int = 400
    pair_mode: int = field(default=1, init=False)
    settle_min_ms: int = 200
    settle_max_ms: int = 5000
    settle_rel: float = 0.001
    settle_abs_codes: float = 1.0
    warmup_ms: int = 0
    settle_enable: bool = True
    adc_reinit: bool = True
    settle_skip_ms: int = 50
    settle_segment_ms: int = 100
    settle_consecutive: int = 3
    analog_timeout_ms: int = 200

    @classmethod
    def table_preset(cls, **overrides) -> 'AutorangeConfig':
        values = dict(s_hi_v=0.0552, s_lo_v=0.00441)
        values.update(overrides)
        return cls(**values)

    def registers(self) -> AutorangeRegisters:
        vpc = volts_per_code()

        def codes(volts, name):
            value = float(volts)
            if not (math.isfinite(value) and value >= 0.0):
                raise ValueError('%s must be finite and non-negative' % name)
            return int(round(value / vpc))

        def q16(value, name):
            value = float(value)
            if not (math.isfinite(value) and value >= 0.0):
                raise ValueError('%s must be finite and non-negative' % name)
            return int(round(value * 65536.0))
        options = (OPTION_SETTLE_ENABLE if self.settle_enable else 0) | (OPTION_ADC_REINIT if self.adc_reinit else 0)
        return AutorangeRegisters(range_mask=int(self.range_mask), s_hi=codes(self.s_hi_v, 's_hi_v'), s_lo=codes(self.s_lo_v, 's_lo_v'), raw_sat=codes(self.raw_sat_v, 'raw_sat_v'), lin_tol_q16=q16(self.lin_tol, 'lin_tol'), lin_min=codes(self.lin_min_v, 'lin_min_v'), open_vmax=codes(self.open_vmax_v, 'open_vmax_v'), open_iratio_q16=q16(self.open_iratio, 'open_iratio'), open_vratio_q16=q16(self.open_vratio, 'open_vratio'), noise_floor=int(self.noise_floor_codes), hyst_q16=q16(self.hysteresis, 'hysteresis'), pilot_win_ms=int(self.pilot_window_ms), meas_win_ms=int(self.measure_window_ms), pair_mode=int(self.pair_mode), t_min_ms=int(self.settle_min_ms), t_max_ms=int(self.settle_max_ms), eps_rel_q16=q16(self.settle_rel, 'settle_rel'), eps_abs_q8=int(round(float(self.settle_abs_codes) * 256.0)), warmup_ms=int(self.warmup_ms), options=options, t_skip_ms=int(self.settle_skip_ms), seg_ms=int(self.settle_segment_ms), settle_k=int(self.settle_consecutive), cfg_timeout_ms=int(self.analog_timeout_ms)).validate()

def currents_na(currents_a: Sequence[float], name: str) -> Tuple[int, ...]:
    values = tuple(currents_a)
    if len(values) != 4:
        raise ValueError('%s must have four entries' % name)
    out = []
    for index, value in enumerate(values):
        value = float(value)
        if not (math.isfinite(value) and value > 0.0):
            raise ValueError('%s[%d] must be finite and positive' % (name, index))
        na = int(round(value * 1000000000.0))
        if not 0 < na <= CURRENT_MAX_NA:
            raise ValueError('%s[%d]=%r A does not fit the 28-bit nA register' % (name, index, value))
        out.append(na)
    return tuple(out)

def trunc_div(numerator: int, denominator: int) -> int:
    """Sign-magnitude division, truncating toward zero (the RTL divider)."""
    if denominator <= 0:
        raise ValueError('denominator must be positive')
    magnitude = abs(int(numerator)) // int(denominator)
    return -magnitude if numerator < 0 else magnitude

def mean_q8(sum_delta: int, count: int) -> int:
    """Window mean of (code - centre) in Q8."""
    return trunc_div(int(sum_delta) << 8, int(count))

def pair_q8(mean_forward: int, mean_reverse: int) -> Tuple[int, int]:
    """(S, E) = ((mF + mR) >> 1, (mF - mR) >> 1), arithmetic shift (floor)."""
    return (int(mean_forward) + int(mean_reverse) >> 1, int(mean_forward) - int(mean_reverse) >> 1)

def settle_agree(m_prev: int, m_now: int, eps_rel_q16: int, eps_abs_q8: int) -> bool:
    return abs(int(m_now) - int(m_prev)) <= (int(eps_rel_q16) * abs(int(m_now)) >> 16) + int(eps_abs_q8)

def lowest_enabled(mask: int) -> int:
    for index in range(4):
        if mask & 1 << index:
            return index
    return 3

def next_enabled(mask: int, index: int) -> Optional[int]:
    for candidate in range(int(index) + 1, 4):
        if mask & 1 << candidate:
            return candidate
    return None

def flags_for(regs: AutorangeRegisters, range_index: int, abs_signal: int) -> int:
    value = 0
    if abs_signal < regs.s_lo << 8:
        value |= F_LOW_SIGNAL
    if range_index == lowest_enabled(regs.range_mask) and abs_signal > regs.s_hi << 8:
        value |= F_ABOVE_TARGET_AT_MIN
    return value

@dataclass(frozen=True)
class Decision:
    kind: str
    range_index: Optional[int] = None
    reason: int = R_OK
    flags: int = 0

def evaluate_pilot(regs: AutorangeRegisters, isum: Sequence[int], i: int, s_i: int, p_i: int, j: Optional[int], s_j: int, s_max: int, f: Optional[int]=None, s_f: int=0) -> Decision:
    """One EVALUATE step (5.5.4).

    ``isum[k]`` = If_nA[k] + Ir_nA[k]; ``j``/``s_j`` the previous tested range, ``f``/``s_f``
    the FIRST tested range of this pilot; ``s_max`` is max(|S|) over tested ranges.

    Open loop is judged only where the pilot would STOP, against the first range, i.e.
    over the whole current span -- the PS rule of 2026-10-17.  Judging it already at the
    second range (the first draft of the plan) mislabels a real low-resistance sample:
    2 ohm gives 1.8 mV at 1 mA, inside the noise floor, and 17 mV at 10 mA.
    """
    abs_i = abs(s_i)
    if p_i > regs.raw_sat << 8:
        if j is None:
            return Decision('fail', reason=R_OVER_RANGE_AT_MIN)
        return Decision('select', j, R_OK_SAT_BACKOFF, flags_for(regs, j, abs(s_j)))
    if j is not None:
        abs_j = abs(s_j)
        lm = regs.lin_min << 8
        if abs_i >= lm and abs_j >= lm:
            lhs = abs(s_i * isum[j] - s_j * isum[i])
            rhs = (abs_j * isum[i] >> 16) * regs.lin_tol_q16
            if lhs > rhs:
                return Decision('select', j, R_OK_NONLINEAR_BACKOFF, flags_for(regs, j, abs_j))
    n = next_enabled(regs.range_mask, i)
    if n is not None and abs_i * isum[n] <= (regs.s_hi << 8) * isum[i]:
        return Decision('next', n)
    if f is not None and f != i:
        floor = max(abs(s_f), regs.noise_floor << 8)
        if s_max < regs.open_vmax << 8 and isum[i] << 16 >= regs.open_iratio_q16 * isum[f] and (abs_i << 16 < regs.open_vratio_q16 * floor):
            return Decision('fail', reason=R_OPEN_LOOP)
    return Decision('select', i, R_OK_TOP if n is None else R_OK, flags_for(regs, i, abs_i))

def verify_lock(regs: AutorangeRegisters, isum: Sequence[int], locked: int, s: int, p: int) -> Decision:
    """VERIFY: 'select' keeps the lock, 'next' means rerange with a FULL pilot."""
    abs_s = abs(s)
    hi = regs.s_hi << 8
    if abs_s < regs.open_vmax << 8:
        return Decision('next')
    if p > regs.raw_sat << 8 or abs_s << 16 > hi * regs.hyst_q16:
        return Decision('next')
    n = next_enabled(regs.range_mask, locked)
    if n is not None and (abs_s * isum[n] >> 16) * regs.hyst_q16 <= hi * isum[locked]:
        return Decision('next')
    return Decision('select', locked, R_OK if n is not None else R_OK_TOP, flags_for(regs, locked, abs_s))

@dataclass
class SimulatedRun:
    """What fpd_autorange leaves in its result registers (window-level model)."""
    ok: bool
    reason: int
    flags: int
    selected_range: Optional[int]
    tested_mask: int
    pilot: Dict[int, Tuple[int, int]]
    s_q8: int = 0
    e_q8: int = 0
    mf_q8: int = 0
    mr_q8: int = 0
    mf_first_q8: int = 0
    mf_last_q8: int = 0
    windows: Tuple[int, int] = (0, 0)
    reranged: bool = False

def simulate_run(regs: AutorangeRegisters, isum: Sequence[int], mode: int, range_index: int, window_mean: Callable[[int, int, int], int]) -> SimulatedRun:
    """Run the sequencer on window means only (no timing, no settling).

    ``window_mean(range, pol, n)`` returns the Q8 mean of the n-th window integrated at
    (range, pol) during this run (n counts per (range, pol) from 0).
    """
    regs.validate()
    counters: Dict[Tuple[int, int], int] = {}

    def window(r, pol):
        key = (int(r), int(pol))
        n = counters.get(key, 0)
        counters[key] = n + 1
        return int(window_mean(int(r), int(pol), n))
    flags = 0
    pilot: Dict[int, Tuple[int, int]] = {}
    tested = 0

    def full_pilot():
        nonlocal tested, flags
        tested = 0
        pilot.clear()
        i = lowest_enabled(regs.range_mask)
        j, s_j, s_max = (None, 0, 0)
        f, s_f = (None, 0)
        while True:
            mf = window(i, 0)
            mr = window(i, 1)
            pilot[i] = (mf, mr)
            s_i, _ = pair_q8(mf, mr)
            p_i = max(abs(mf), abs(mr))
            s_max = max(s_max, abs(s_i))
            tested |= 1 << i
            if f is None:
                f, s_f = (i, s_i)
            decision = evaluate_pilot(regs, isum, i, s_i, p_i, j, s_j, s_max, f, s_f)
            if decision.kind == 'next':
                j, s_j, i = (i, s_i, decision.range_index)
                continue
            if decision.kind == 'fail':
                return decision
            flags |= decision.flags
            return decision

    def measure(r, verify):
        nonlocal flags
        two_n = 1
        f_means = [window(r, 0)]
        r_means = [window(r, 1)]
        if verify:
            signal, _ = pair_q8(f_means[0], r_means[0])
            decision = verify_lock(regs, isum, r, signal, max(abs(f_means[0]), abs(r_means[0])))
            if decision.kind == 'next':
                return None
            flags |= decision.flags
            verify_reason[0] = decision.reason
        mf = trunc_div(sum(f_means), two_n)
        mr = trunc_div(sum(r_means), two_n)
        s, e = pair_q8(mf, mr)
        return dict(s_q8=s, e_q8=e, mf_q8=mf, mr_q8=mr, mf_first_q8=f_means[0], mf_last_q8=f_means[-1], windows=(len(f_means), len(r_means)))
    verify_reason = [R_OK]
    reranged = False
    if mode == MODE_FULL:
        decision = full_pilot()
    else:
        if not regs.range_mask & 1 << range_index:
            return SimulatedRun(False, R_CONFIG_ERROR, 0, None, 0, {})
        if mode == MODE_VERIFY:
            outcome = measure(range_index, True)
            if outcome is not None:
                return SimulatedRun(True, verify_reason[0], flags, range_index, 0, {}, **outcome)
            flags |= F_RERANGED
            reranged = True
            decision = full_pilot()
        else:
            outcome = measure(range_index, False)
            return SimulatedRun(True, R_OK, flags, range_index, 0, {}, **outcome)
    if decision.kind == 'fail':
        return SimulatedRun(False, decision.reason, flags, None, tested, dict(pilot), reranged=reranged)
    outcome = measure(decision.range_index, False)
    return SimulatedRun(True, decision.reason, flags, decision.range_index, tested, dict(pilot), reranged=reranged, **outcome)

@dataclass(frozen=True)
class PilotRecord:
    range_index: int
    mean_forward_q8: int
    mean_reverse_q8: int
    settle_forward_ms: int
    settle_reverse_ms: int
    samples_forward: int
    samples_reverse: int

    @property
    def signal_q8(self) -> int:
        return pair_q8(self.mean_forward_q8, self.mean_reverse_q8)[0]

    @property
    def offset_q8(self) -> int:
        return pair_q8(self.mean_forward_q8, self.mean_reverse_q8)[1]

@dataclass(frozen=True)
class AggregateStats:
    sum_codes: int
    sum_squares: int
    count: int
    min_code: int
    max_code: int

@dataclass(frozen=True)
class AutorangeResult:
    ok: bool
    reason: int
    flags: int
    mode: int
    selected_range: int
    tested_mask: int
    run_ms: int
    mismatch_samples: int
    pilots: Tuple[PilotRecord, ...]
    s_q8: int
    e_q8: int
    mf_q8: int
    mr_q8: int
    mf_first_q8: int
    mf_last_q8: int
    settle_max_ms: int
    settle_timeouts: int
    windows_forward: int
    windows_reverse: int
    forward: AggregateStats
    reverse: AggregateStats

    @property
    def reason_name(self) -> str:
        return REASON_NAMES.get(self.reason, 'REASON_%d' % self.reason)

    @property
    def flag_names(self) -> Tuple[str, ...]:
        return flag_names(self.flags)

    @property
    def reranged(self) -> bool:
        return bool(self.flags & F_RERANGED)

    def snapshot(self, reverse: bool, minimum_valid_samples: int=1) -> PlWindowSnapshot:
        """Native ADC voltage measurement. Units are volts, amperes and seconds unless stated otherwise."""
        agg = self.reverse if reverse else self.forward
        return PlWindowSnapshot(bank=int(self.selected_range) + (4 if reverse else 0), seq=0, valid_count=int(agg.count), rx_update_count=int(agg.count), sum_codes=int(agg.sum_codes), sum_squares=int(agg.sum_squares), min_code=int(agg.min_code), max_code=int(agg.max_code), ready=True, empty=agg.count == 0, overflow=False, minimum_valid_samples=int(minimum_valid_samples), strict_valid_count=True)

    def as_record(self) -> dict:
        """JSON-safe summary for the point record (volts and ms)."""
        vpc = volts_per_code()

        def v(q8):
            return float(q8) / 256.0 * vpc
        return {'version': PL_AUTORANGE_VERSION, 'mode': MODE_NAMES.get(self.mode, str(self.mode)), 'reason': self.reason_name, 'flags': list(self.flag_names), 'selected_range': int(self.selected_range), 'tested_ranges': [r for r in range(4) if self.tested_mask & 1 << r], 'run_ms': int(self.run_ms), 'pilot': [{'range_index': p.range_index, 'forward_v': v(p.mean_forward_q8), 'reverse_v': v(p.mean_reverse_q8), 'signal_v': v(p.signal_q8), 'offset_v': v(p.offset_q8), 'settle_forward_ms': p.settle_forward_ms, 'settle_reverse_ms': p.settle_reverse_ms, 'samples_forward': p.samples_forward, 'samples_reverse': p.samples_reverse} for p in self.pilots], 'signal_v': v(self.s_q8), 'offset_v': v(self.e_q8), 'forward_first_v': v(self.mf_first_q8), 'forward_last_v': v(self.mf_last_q8), 'settle_max_ms': int(self.settle_max_ms), 'settle_timeouts': int(self.settle_timeouts), 'windows': [int(self.windows_forward), int(self.windows_reverse)], 'mismatch_samples': int(self.mismatch_samples)}

def _signed32(value: int) -> int:
    value = int(value) & 4294967295
    return value - (1 << 32) if value & 2147483648 else value

class PlAutorange:
    """Register-level driver for FP_DSP.

    ``mmio`` is a PYNQ ``MMIO(FPD_DEFAULT_BASE, FPD_ADDRESS_RANGE)`` (or any object with
    read/write).  The PS must not touch ALL_Final's analog registers while a run is BUSY;
    FP_DSP aborts with OWNERSHIP_CONFLICT if the relay pins change behind its back.
    """

    def __init__(self, mmio, config: Optional[AutorangeConfig]=None, *, poll_s: float=0.005, timeout_s: float=300.0, sleep=time.sleep, monotonic=time.monotonic):
        self.mmio = mmio
        self.config = config or AutorangeConfig()
        self.poll_s = float(poll_s)
        self.timeout_s = float(timeout_s)
        self._sleep = sleep
        self._monotonic = monotonic
        self.registers_written: Optional[AutorangeRegisters] = None
        self.currents_forward_na: Optional[Tuple[int, ...]] = None
        self.currents_reverse_na: Optional[Tuple[int, ...]] = None
        self.center_codes: Optional[Tuple[int, ...]] = None
        self._caps: Optional[int] = None

    @classmethod
    def from_overlay(cls, overlay, mmio_factory, config: Optional[AutorangeConfig]=None, ip_name: str='fp_dsp_0', **kwargs) -> 'PlAutorange':
        """Build the driver only if the loaded overlay really contains FP_DSP.

        Reading an address no PL slave decodes ends in an AXI DECERR, which on Zynq is a
        bus error that can kill the Python kernel -- so the hwh, not a probe read, decides.
        """
        ip = (getattr(overlay, 'ip_dict', None) or {}).get(ip_name)
        if ip is None:
            raise PlAutorangeError('the loaded overlay has no %s: this all_design.bit was built without hw/rtl/fp_dsp (keep USE_PL_AUTORANGE=False or rebuild)' % ip_name)
        base = int(ip['phys_addr'])
        size = int(ip.get('addr_range', FPD_ADDRESS_RANGE))
        return cls(mmio_factory(base, size), config, **kwargs)

    def read(self, offset: int) -> int:
        return int(self.mmio.read(int(offset))) & 4294967295

    def write(self, offset: int, value: int) -> None:
        self.mmio.write(int(offset), int(value) & 4294967295)

    def _write_checked(self, offset: int, value: int, name: str) -> None:
        self.write(offset, value)
        back = self.read(offset)
        if back != int(value) & 4294967295:
            raise PlAutorangeError('FP_DSP %s at 0x%03X read back 0x%X, wrote 0x%X' % (name, offset, back, value))

    def identify(self) -> dict:
        ident = self.read(REG_ID)
        version = self.read(REG_VERSION)
        caps = self.read(REG_CAPS)
        if ident != FPD_ID:
            raise PlAutorangeError('FP_DSP not found (ID 0x%08X, expected 0x%08X): load an all_design.bit built with hw/rtl/fp_dsp, or set USE_PL_AUTORANGE=False' % (ident, FPD_ID))
        if version != FPD_VERSION:
            raise PlAutorangeError('FP_DSP version %d, this driver speaks %d' % (version, FPD_VERSION))
        if not (caps & FPD_CAP_AUTORANGE and caps & FPD_CAP_MASTER):
            raise PlAutorangeError('FP_DSP CAPS 0x%08X lacks auto-ranging' % caps)
        self._caps = caps
        return {'id': ident, 'version': version, 'caps': caps, 'sample_rate_sps': self.read(REG_SAMPLE_RATE), 'allf_base': self.read(REG_ALLF_BASE)}

    def status(self) -> dict:
        value = self.read(REG_STATUS)
        return {'raw': value, 'busy': bool(value & STATUS_BUSY), 'done': bool(value & STATUS_DONE), 'error': bool(value & STATUS_ERROR), 'owned': bool(value & STATUS_OWNED), 'result_valid': bool(value & STATUS_RESULT_VALID), 'axi_hung': bool(value & STATUS_AXI_HUNG), 'state': value >> 8 & 63, 'reason': value >> 16 & 255, 'flags': value >> 24 & 255}

    def diagnostics(self) -> dict:
        frames = self.read(REG_FRAME_DIAG)
        last = self.read(REG_LAST_SAMPLE)
        axi = self.read(REG_AXI_DIAG)
        return {'sample_count': self.read(REG_SAMPLE_COUNT), 'config_frames': frames & 65535, 'bad_frames': frames >> 16, 'sample_rate_sps': self.read(REG_SAMPLE_RATE), 'mismatch_samples': self.read(REG_MISMATCH), 'last_code': last & 65535, 'last_label': last >> 16 & 7, 'last_label_valid': bool(last & 1 << 23), 'axi_errors': axi & 65535, 'axi_hung': bool(axi & 1 << 16)}

    def claim(self) -> None:
        self.write(REG_CONTROL, CTRL_CLAIM)
        if not self.status()['owned']:
            raise PlAutorangeError('FP_DSP did not accept CLAIM (busy?)')

    def release(self) -> None:
        if self.status()['busy']:
            raise PlAutorangeError('FP_DSP is busy; abort the run before RELEASE')
        self.write(REG_CONTROL, CTRL_RELEASE)

    def abort(self) -> None:
        self.write(REG_CONTROL, CTRL_ABORT)

    def wait_idle(self, timeout_s: float=2.0) -> dict:
        deadline = self._monotonic() + float(timeout_s)
        while True:
            status = self.status()
            if not status['busy']:
                return status
            if self._monotonic() >= deadline:
                raise PlAutorangeError('FP_DSP still busy after ABORT: %r' % (status,))
            self._sleep(self.poll_s)

    def configure(self, forward_current_a: Sequence[float], reverse_current_a: Sequence[float], center_codes: Sequence[int], config: Optional[AutorangeConfig]=None) -> AutorangeRegisters:
        """Write every configuration register and read each one back (exact)."""
        if config is not None:
            self.config = config
        if self.status()['busy']:
            raise PlAutorangeError('FP_DSP is busy; configuration writes would be dropped')
        regs = self.config.registers()
        forward = currents_na(forward_current_a, 'forward_current_a')
        reverse = currents_na(reverse_current_a, 'reverse_current_a')
        centers = tuple((int(c) for c in center_codes))
        if len(centers) != 8 or any((not 0 <= c <= 65535 for c in centers)):
            raise ValueError('center_codes must be eight codes 0..65535 (bank = pol*4 + range)')
        for name, (offset, _) in CONFIG_REGISTERS.items():
            self._write_checked(offset, getattr(regs, name), name)
        for bank, code in enumerate(centers):
            self._write_checked(REG_CENTER_BASE + 4 * bank, code, 'center[%d]' % bank)
        for index in range(4):
            self._write_checked(REG_IF_BASE + 4 * index, forward[index], 'if[%d]' % index)
            self._write_checked(REG_IR_BASE + 4 * index, reverse[index], 'ir[%d]' % index)
        self.registers_written = regs
        self.currents_forward_na = forward
        self.currents_reverse_na = reverse
        self.center_codes = centers
        return regs

    @property
    def caps(self) -> int:
        if self._caps is None:
            self._caps = self.read(REG_CAPS)
        return self._caps

    @property
    def current_sums_na(self) -> Tuple[int, ...]:
        if self.currents_forward_na is None:
            raise PlAutorangeError('FP_DSP is not configured')
        return tuple((f + r for f, r in zip(self.currents_forward_na, self.currents_reverse_na)))

    def run(self, mode: int, range_index: int=0, abort_check: Optional[Callable[[], None]]=None) -> AutorangeResult:
        """Start one run and wait for it.  ``abort_check`` may raise to stop it."""
        if mode not in MODE_NAMES:
            raise ValueError('mode must be MODE_FULL, MODE_VERIFY or MODE_FORCED')
        status = self.status()
        if status['busy']:
            raise PlAutorangeError('FP_DSP is already busy')
        if not status['owned']:
            raise PlAutorangeError('FP_DSP is not claimed by the PS')
        self.write(REG_CONTROL, CTRL_CLEAR)
        self.write(REG_CONTROL, CTRL_START | int(mode) << CTRL_MODE_SHIFT | (int(range_index) & 3) << CTRL_RANGE_SHIFT)
        deadline = self._monotonic() + self.timeout_s
        while True:
            status = self.status()
            if status['done'] and (not status['busy']):
                break
            try:
                if abort_check is not None:
                    abort_check()
                if self._monotonic() >= deadline:
                    raise PlAutorangeError('FP_DSP run did not finish within %.0f s: %r' % (self.timeout_s, status))
            except BaseException:
                self.abort()
                try:
                    self.wait_idle()
                except PlAutorangeError:
                    pass
                raise
            self._sleep(self.poll_s)
        return self.read_result(mode)

    def read_result(self, mode: int=MODE_FULL) -> AutorangeResult:
        status = self.status()
        select = self.read(RES_SELECT)
        reason_word = self.read(RES_REASON)
        tested = select >> 4 & 15
        pilots = []
        for index in range(4):
            if not tested & 1 << index:
                continue
            base = RES_PILOT_BASE + 16 * index
            settle = self.read(base + 8)
            samples = self.read(base + 12)
            pilots.append(PilotRecord(range_index=index, mean_forward_q8=_signed32(self.read(base)), mean_reverse_q8=_signed32(self.read(base + 4)), settle_forward_ms=settle & 65535, settle_reverse_ms=settle >> 16, samples_forward=samples & 65535, samples_reverse=samples >> 16))

        def aggregate(base):
            minmax = self.read(base + 20)
            return AggregateStats(sum_codes=self.read(base) | (self.read(base + 4) & 65535) << 32, sum_squares=self.read(base + 8) | self.read(base + 12) << 32, count=self.read(base + 16), min_code=minmax & 65535, max_code=minmax >> 16)
        settle = self.read(RES_SETTLE)
        windows = self.read(RES_WINDOWS)
        ok = bool(status['result_valid']) and (not status['error'])
        selected = select & 3
        return AutorangeResult(ok=ok, reason=reason_word & 255, flags=reason_word >> 8 & 255, mode=int(mode), selected_range=selected, tested_mask=tested, run_ms=self.read(RES_RUN_MS), mismatch_samples=self.read(RES_MISMATCH), pilots=tuple(pilots), s_q8=_signed32(self.read(RES_S)), e_q8=_signed32(self.read(RES_E)), mf_q8=_signed32(self.read(RES_MF)), mr_q8=_signed32(self.read(RES_MR)), mf_first_q8=_signed32(self.read(RES_MF_FIRST)), mf_last_q8=_signed32(self.read(RES_MF_LAST)), settle_max_ms=settle & 65535, settle_timeouts=settle >> 16, windows_forward=windows & 31, windows_reverse=windows >> 16 & 31, forward=aggregate(RES_AGG_BASE[0]), reverse=aggregate(RES_AGG_BASE[1]))

@dataclass
class SampleModel:
    """Linear four-probe sample as FP_DSP would see it, per (range, polarity) window.

    forward reading Vf = If*R + E, reverse Vr = Ir*R - E (probe volts).  ``open_loop``
    leaves only +/-E.  ``samples_per_window`` is what one window integrates.
    """
    resistance_ohm: float
    offset_v: float = 0.0
    forward_current_a: Sequence[float] = (0.0001, 0.001, 0.01, 0.1)
    reverse_current_a: Sequence[float] = (0.0001, 0.001, 0.01, 0.1)
    center_code: int = 48768
    samples_per_window: int = 1000
    open_loop: bool = False

    def delta_code(self, range_index: int, reverse: bool) -> int:
        vpc = volts_per_code()
        current = 0.0 if self.open_loop else self.reverse_current_a[range_index] if reverse else self.forward_current_a[range_index]
        volts = current * self.resistance_ohm + (-self.offset_v if reverse else self.offset_v)
        return int(round(volts / vpc))

    def window_mean(self, range_index: int, pol: int, _n: int) -> int:
        return mean_q8(self.delta_code(range_index, bool(pol)) * self.samples_per_window, self.samples_per_window)
