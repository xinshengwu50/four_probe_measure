# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Native ADC voltage measurement. Units are volts, amperes and seconds unless stated otherwise."""
from __future__ import annotations
import time
from typing import Optional, Tuple
REG_CALC_CONTROL = 332
REG_CALC_STATUS = 336
REG_CALC_RHO_LOW = 340
REG_CALC_RHO_HIGH = 344
REG_CALC_FLAGS = 348
REG_CALC_COEFF_K = 352
REG_CALC_COEFF_RS = 356
REG_CALC_RS_LOW = 360
REG_CALC_RS_HIGH = 364
REG_CALC_MIN_COUNT = 368
REG_CALC_MAX_SPAN = 372
CALC_CONTROL_START = 1 << 0
CALC_CONTROL_CLEAR = 1 << 1
CALC_CONTROL_AVERAGE_PAIR = 1 << 2
CALC_STATUS_BUSY = 1 << 0
CALC_STATUS_DONE = 1 << 1
CALC_STATUS_VALID = 1 << 2
CALC_STATUS_PAIR_VALID = 1 << 3
CALC_STATUS_QUALITY_OK = 1 << 4
CALC_FLAG_ZERO_COUNT = 1 << 0
CALC_FLAG_COUNT_OVER_MAX = 1 << 1
CALC_FLAG_SUM_OVERFLOW = 1 << 2
CALC_FLAG_COEFF_INVALID = 1 << 3
CALC_FLAG_NEGATIVE = 1 << 4
CALC_FLAG_PAIR_MISSING = 1 << 5
CALC_FLAG_QUALITY_LOW_COUNT = 1 << 6
CALC_FLAG_QUALITY_WIDE_SPAN = 1 << 7
COEFF_FRAC = 23
OUT_FRAC = 32
MEAN_FRAC = 16
COUNT_MAX = 65536
COEFF_MAX = 268435455
K_Q_MIN = 1 << 13
K_Q_HW_MIN = 1
ADC_LSB_V = 5.12 / 32768.0
_POLL_INTERVAL_S = 0.0001

class PlCalcError(RuntimeError):
    """PL arithmetic refused to produce a usable resistivity."""

class PlCalcRegistersAbsent(PlCalcError):
    """The bitstream does not implement the CALC_* registers."""

def coefficient_k(lsb_v: float, fd: float, fw: float, thickness_cm: float, fsp: float, current_a: float) -> float:
    """Return K in ohm*cm per ADC code (the whole material/geometry model)."""
    for name, value in (('lsb_v', lsb_v), ('fd', fd), ('fw', fw), ('thickness_cm', thickness_cm), ('fsp', fsp), ('current_a', current_a)):
        if not float(value) > 0.0 or float(value) != float(value):
            raise PlCalcError('%s must be finite and positive' % name)
    return float(lsb_v) * float(1.0) * float(fd) * float(fw) * float(thickness_cm) * float(fsp) / float(current_a)

def coefficient_k_rs(lsb_v: float, fd: float, fw: float, fsp: float, current_a: float) -> float:
    """Return K_rs in ohm/square per ADC code: K_rho WITHOUT the W_cm factor.

    Rs = rho / W_cm and rho = offset*K_rho, so Rs = offset*K_rs with
    K_rs = LSB*scale*FD*FW*Fsp/I -- the same q, one more multiply, no new divider.
    """
    for name, value in (('lsb_v', lsb_v), ('fd', fd), ('fw', fw), ('fsp', fsp), ('current_a', current_a)):
        if not float(value) > 0.0 or float(value) != float(value):
            raise PlCalcError('%s must be finite and positive' % name)
    return float(lsb_v) * float(1.0) * float(fd) * float(fw) * float(fsp) / float(current_a)

def check_k_rs_relation(k_q_rho: int, k_q_rs: int, thickness_cm: float, tolerance: Optional[float]=None) -> float:
    """Cross-check K_rs == K_rho / W_cm; refuse the run when it does not hold.

    With no explicit ``tolerance`` the bound is the EXACT one of the independent
    rounding, not a fudge: each coefficient is rounded to a whole code, and K_q_rho is
    then DIVIDED by W_cm, so the compared values can differ by up to
    0.5*(1 + 1/W_cm) codes -- 0.5*(1 + 1/W_cm)/expected in relative terms.  Both ends
    of that bound are needed: at the deployed 645 um / 10 mA setting (K_q = 179885,
    W_cm = 6.45e-2) it is 3.0e-6, so the 1e-5 floor still applies, while below the rho
    accuracy floor the coefficient's own rounding IS the largest term (900 nm at
    10 mA: K_q_rho = 213 -> 2.3e-3).  A point below the floor is reported from the Rs
    channel, so the check must stay live exactly there instead of being skipped.

    Both coefficients are computed by the PS from the same parameters, so the
    relation is free extra evidence that the two registers were configured for the
    same bank -- a mismatch means one of them is stale and every number after it
    would be wrong.  Returns the tolerance used, so the caller can record it.
    """
    if not float(thickness_cm) > 0.0:
        raise PlCalcError('thickness_cm must be positive')
    expected = k_q_rho / float(thickness_cm)
    limit = max(1e-05, 0.5 * (1.0 + 1.0 / float(thickness_cm)) / expected) if tolerance is None else float(tolerance)
    if abs(float(k_q_rs) - expected) / expected > limit:
        raise PlCalcError('K_rs=%.9g does not match K_rho/W_cm=%.9g (W_cm=%.6g, tolerance %.3g)' % (k_q_rs, expected, thickness_cm, limit))
    return limit

def quality_flags(count: int, min_code: int, max_code: int, min_valid_count: int, max_span: int):
    """Bit-accurate model of meas_calc's phase C judgements.

    Returns (quality_ok, low_count, wide_span).  Either limit at 0 disables that
    check -- PL reports the judgement, it does not veto the result.
    """
    low_count = int(min_valid_count) != 0 and int(count) < int(min_valid_count)
    span = int(max_code) - int(min_code)
    wide_span = int(max_span) != 0 and span > int(max_span)
    return (not low_count and (not wide_span), low_count, wide_span)

def fixed_point_rs(count: int, sum_code: int, center_code: int, k_rs_q: int):
    """Bit-accurate single-shot Rs model (mirrors meas_calc's second multiply)."""
    count = int(count)
    if count == 0:
        return (0, CALC_FLAG_ZERO_COUNT)
    if count > COUNT_MAX:
        return (0, CALC_FLAG_COUNT_OVER_MAX)
    if int(k_rs_q) == 0 or int(k_rs_q) > COEFF_MAX:
        return (0, CALC_FLAG_COEFF_INVALID)
    d = int(sum_code) - int(center_code) * count
    flags = CALC_FLAG_NEGATIVE if d < 0 else 0
    q = (abs(d) << MEAN_FRAC) // count
    return (q * int(k_rs_q) >> MEAN_FRAC + COEFF_FRAC - OUT_FRAC, flags)

def decode_rs_q(rs_q: int) -> float:
    """Return Rs in ohm/square from the hardware's Q32 result word."""
    return int(rs_q) / float(1 << OUT_FRAC)

def quantize_coefficient_k(k: float, *, k_q_floor: int=K_Q_MIN) -> int:
    """Return K_q = round(K * 2**COEFF_FRAC), refusing values outside the window.

    The refusal is deliberate and two-sided: 0 would silently produce a zero
    reading and anything above COEFF_MAX would overflow the hardware product.

    ``k_q_floor`` defaults to K_Q_MIN, the ACCURACY floor: below it the coefficient's
    own quantization error breaks the 1e-4 budget, so a caller that REPORTS rho must
    keep the default.  One caller lowers it, and only to the hardware floor
    K_Q_HW_MIN: the Rs-only fallback, which writes the true K_q but reports
    ``rho = Rs*W_cm`` from the Rs channel instead (see the module header).
    The hardware window (0, COEFF_MAX] is enforced whatever the floor is.
    """
    value = float(k)
    if not value > 0.0 or value != value:
        raise PlCalcError('coefficient must be finite and positive, got %r' % (k,))
    limit = int(k_q_floor)
    if limit < K_Q_HW_MIN:
        raise PlCalcError('coefficient floor %d is outside the hardware window [%d, %d]' % (limit, K_Q_HW_MIN, COEFF_MAX))
    k_q = int(round(value * (1 << COEFF_FRAC)))
    if k_q < limit or k_q > COEFF_MAX:
        raise PlCalcError('coefficient K_q=%d outside [%d, %d]; K must be in [%.4g, %.4g] ohm*cm per code%s' % (k_q, limit, COEFF_MAX, limit / float(1 << COEFF_FRAC), COEFF_MAX / float(1 << COEFF_FRAC), ' to hold the 1e-4 budget' if limit == K_Q_MIN else ' (HARDWARE window: the 1e-4 floor was not applied, so this result must not be reported as rho)'))
    return k_q

def decode_rho_q(rho_q: int) -> float:
    """Return rho in ohm*cm from the hardware's Q24 result word."""
    return int(rho_q) / float(1 << OUT_FRAC)

def fixed_point_rho(count: int, sum_code: int, center_code: int, k_q: int) -> Tuple[int, int]:
    """Bit-accurate model of meas_calc: return (rho_q, flags).  Test-only oracle.

    This mirrors the RTL statement for statement so the golden comparison in
    tests/test_pl_resistivity.py exercises the *algorithm*, not a re-derivation
    of it.  Kept next to the driver so the two cannot drift apart unnoticed.
    """
    flags = 0
    if int(count) == 0:
        flags |= CALC_FLAG_ZERO_COUNT
    if int(count) > COUNT_MAX:
        flags |= CALC_FLAG_COUNT_OVER_MAX
    if int(k_q) == 0 or int(k_q) > COEFF_MAX:
        flags |= CALC_FLAG_COEFF_INVALID
    if flags:
        return (0, flags)
    d = int(sum_code) - int(center_code) * int(count)
    if d < 0:
        flags |= CALC_FLAG_NEGATIVE
    d = abs(d)
    q = (d << MEAN_FRAC) // int(count)
    rho_q = q * int(k_q) >> MEAN_FRAC + COEFF_FRAC - OUT_FRAC
    return (rho_q, flags)

def _pair_average(first_q: int, first_flags: int, second_q: int, second_flags: int):
    """Mirror meas_calc's signed pair averaging; returns (magnitude, flags, pair_valid).

    Shared by the rho and the Rs pair models on purpose: the RTL runs the SAME pair
    state machine for both channels (``rho_avg_s`` and ``rs_avg_s`` are one statement
    apart), they share one sign decision -- the sign comes from the offset ``d``, not
    from the coefficient -- and the pair-presence gates are coefficient-independent.
    One implementation is therefore the exact mirror of both, and the two cannot drift
    apart.

    A failed FIRST half leaves the second reporting PAIR_MISSING with 0: the RTL drops
    have_prev on failure, so a pair may only ever join two consecutive successes.
    """
    if first_flags & ~CALC_FLAG_NEGATIVE:
        return (0, CALC_FLAG_PAIR_MISSING, False)
    if second_flags & ~CALC_FLAG_NEGATIVE:
        return (0, second_flags, False)
    signed_first = -first_q if first_flags & CALC_FLAG_NEGATIVE else first_q
    signed_second = -second_q if second_flags & CALC_FLAG_NEGATIVE else second_q
    average = signed_first + signed_second >> 1
    flags = CALC_FLAG_NEGATIVE if average < 0 else 0
    return (abs(average), flags, True)

def fixed_point_rho_pair(count_first: int, sum_first: int, center_first: int, k_q_first: int, count_second: int, sum_second: int, center_second: int, k_q_second: int):
    """Bit-accurate model of two consecutive computes with AVERAGE_PAIR on the second.

    Mirrors meas_calc's pair mode statement for statement: the second call returns
    |0.5*(signed_first + signed_second)| and is VALID only if the first one was VALID;
    a failed first compute leaves the second reporting PAIR_MISSING with rho 0.

    Returns (rho_q, flags, pair_valid).
    """
    first_q, first_flags = fixed_point_rho(count_first, sum_first, center_first, k_q_first)
    second_q, second_flags = fixed_point_rho(count_second, sum_second, center_second, k_q_second)
    return _pair_average(first_q, first_flags, second_q, second_flags)

def fixed_point_rs_pair(count_first: int, sum_first: int, center_first: int, k_rs_q_first: int, count_second: int, sum_second: int, center_second: int, k_rs_q_second: int):
    """Bit-accurate pair model for the Rs CHANNEL: same pipeline, second coefficient.

    Same contract and same (rs_q, flags, pair_valid) shape as ``fixed_point_rho_pair``,
    because the RTL averages rs_q with the same signed shift
    (``rs_avg_s = (rs_prev_s + rs_new_s) >>> 1``).  It is needed because below the rho
    accuracy floor the REPORTED number comes from this channel, so this is the oracle
    the hardware word has to match bit for bit.
    """
    first_q, first_flags = fixed_point_rs(count_first, sum_first, center_first, k_rs_q_first)
    second_q, second_flags = fixed_point_rs(count_second, sum_second, center_second, k_rs_q_second)
    return _pair_average(first_q, first_flags, second_q, second_flags)

class PlMeasCalc:
    """Driver for the CALC_* register block (fail-closed on every path)."""

    def __init__(self, read, write, poll_interval_s: float=_POLL_INTERVAL_S):
        self._quality_limits = (0, 0)
        self._read_raw = read
        self._write_raw = write
        self._poll = float(poll_interval_s)

    def _read(self, offset: int) -> int:
        return int(self._read_raw(offset))

    def _write(self, offset: int, value: int) -> None:
        self._write_raw(offset, int(value) & 4294967295)

    def read_coefficient_k(self) -> int:
        return self._read(REG_CALC_COEFF_K)

    def write_coefficient_k(self, k_q: int, *, verify: bool=True, k_q_floor: int=K_Q_MIN) -> int:
        """Write K_q and (by default) require an EQUAL read-back.

        Equality, not ">=": a larger-than-written value means the register is
        aliased to something else, a smaller one means the write was dropped.
        Both directions must stop the caller.

        ``k_q_floor`` defaults to the accuracy floor K_Q_MIN, and only the Rs-only
        fallback passes K_Q_HW_MIN: the value written is still exactly the coefficient
        the model asks for, the hardware window (0, COEFF_MAX] is enforced either way,
        and that caller reports ``rho = Rs*W_cm`` from the other channel.
        """
        value = int(k_q)
        if value < int(k_q_floor) or value > COEFF_MAX:
            raise PlCalcError('refusing to write K_q=%d (window is [%d, %d])' % (value, int(k_q_floor), COEFF_MAX))
        self._write(REG_CALC_COEFF_K, value)
        back = self.read_coefficient_k()
        if verify and back != value:
            raise PlCalcError('CALC_COEFF_K read-back mismatch: wrote 0x%08X, read 0x%08X' % (value, back))
        return back

    def probe_registers(self) -> int:
        """Fail-closed capability probe; returns the canary that read back.

        The canary is a coefficient-shaped value that is never zero, so a
        bitstream without these registers (read-back 0) is detected instead of
        being mistaken for "no measurement yet".
        """
        canary = 172997
        self.write_coefficient_k(canary)
        self._write(REG_CALC_CONTROL, CALC_CONTROL_CLEAR)
        return canary

    def start(self, *, pair: bool=False) -> None:
        """Trigger a compute; `pair=True` asks PL to average it with the previous one."""
        self._write(REG_CALC_CONTROL, CALC_CONTROL_START | (CALC_CONTROL_AVERAGE_PAIR if pair else 0))

    def clear(self) -> None:
        self._write(REG_CALC_CONTROL, CALC_CONTROL_CLEAR)

    def read_status(self) -> int:
        return self._read(REG_CALC_STATUS)

    def read_flags(self) -> int:
        return self._read(REG_CALC_FLAGS)

    def write_coefficient_rs(self, k_q: int, *, verify: bool=True) -> int:
        """Write K_rs with the same exact read-back requirement as K_rho."""
        value = int(k_q)
        if value < K_Q_MIN or value > COEFF_MAX:
            raise PlCalcError('refusing to write K_rs=%d (window is [%d, %d])' % (value, K_Q_MIN, COEFF_MAX))
        self._write(REG_CALC_COEFF_RS, value)
        back = self._read(REG_CALC_COEFF_RS)
        if verify and back != value:
            raise PlCalcError('CALC_COEFF_RS read-back mismatch: wrote 0x%08X, read 0x%08X' % (value, back))
        return back

    def write_quality_limits(self, min_valid_count: int=0, max_span: int=0) -> None:
        """Program the phase C limits (0 disables a check) with exact read-back.

        The values are remembered and re-written by every compute, so a scan can set
        them once and cannot end up judging a window against stale limits.
        """
        limit_count = int(min_valid_count)
        limit_span = int(max_span)
        if not 0 <= limit_count <= 4294967295:
            raise PlCalcError('min_valid_count out of range: %d' % limit_count)
        if not 0 <= limit_span <= 131071:
            raise PlCalcError('max_span out of range: %d' % limit_span)
        self._write(REG_CALC_MIN_COUNT, limit_count)
        self._write(REG_CALC_MAX_SPAN, limit_span)
        back_count = self._read(REG_CALC_MIN_COUNT)
        back_span = self._read(REG_CALC_MAX_SPAN) & 131071
        if back_count != limit_count or back_span != limit_span:
            raise PlCalcError('quality limits read back as %d/%d, wrote %d/%d' % (back_count, back_span, limit_count, limit_span))
        self._quality_limits = (limit_count, limit_span)

    def read_quality_ok(self) -> bool:
        return bool(self.read_status() & CALC_STATUS_QUALITY_OK)

    def read_rs_q(self) -> int:
        low = self._read(REG_CALC_RS_LOW) & 4294967295
        high = self._read(REG_CALC_RS_HIGH) & 4294967295
        return high << 32 | low

    def read_rho_q(self) -> int:
        low = self._read(REG_CALC_RHO_LOW) & 4294967295
        high = self._read(REG_CALC_RHO_HIGH) & 4294967295
        return high << 32 | low

    def wait_done(self, timeout_s: float=0.05) -> int:
        """Poll STATUS.DONE; raise if the block never finishes."""
        deadline = time.monotonic() + float(timeout_s)
        while True:
            status = self.read_status()
            if status & CALC_STATUS_DONE:
                return status
            if time.monotonic() > deadline:
                raise PlCalcError('meas_calc did not finish within %.4g s (status=0x%08X)' % (timeout_s, status))
            time.sleep(self._poll)

    def verify_arithmetic(self, *, sum_code: int, count: int, center_code: int, k_q: int, k_rs_q: int, tolerance_lsb: int=1, timeout_s: float=0.05) -> int:
        """Prove the multiply/divide/shift chain, not just the register file.

        probe_registers() only shows that CALC_COEFF_K exists and holds what was
        written.  This runs one *real* compute at a known operating point (the
        caller must have armed a window whose snapshot is exactly
        sum/count/center_code) and compares the hardware word with the Python
        oracle bit for bit.  A zero coefficient, a stuck divider or a mis-wired
        shift all pass probe_registers() but fail here.

        Returns the observed rho_q; raises PlCalcError on any disagreement.
        """
        expected_q, flags = fixed_point_rho(count, sum_code, center_code, k_q)
        if flags:
            raise PlCalcError('canary snapshot is not computable: %s' % describe_flags(flags))
        self.write_coefficient_k(k_q)
        self.write_coefficient_rs(k_rs_q)
        self._write(REG_CALC_MIN_COUNT, 0)
        self._write(REG_CALC_MAX_SPAN, 0)
        self.clear()
        self.start()
        status = self.wait_done(timeout_s=timeout_s)
        flags = self.read_flags()
        if flags:
            raise PlCalcError('canary compute flagged 0x%02X (%s)' % (flags, describe_flags(flags)))
        if not status & CALC_STATUS_VALID:
            raise PlCalcError('canary compute finished without VALID (status=0x%08X)' % status)
        observed = self.read_rho_q()
        if abs(observed - expected_q) > int(tolerance_lsb):
            raise PlCalcError('canary mismatch: hardware rho_q=%d, oracle=%d (tolerance %d)' % (observed, expected_q, tolerance_lsb))
        return observed

    def compute_pair(self, k_q_first: int, k_rs_q_first: int, k_q_second: int, k_rs_q_second: int, *, select_first=None, select_second=None, timeout_s: float=0.05, k_q_floor: int=K_Q_MIN) -> float:
        """Return rho in ohm*cm for a forward/reverse pair, averaged *inside PL*.

        This is the last piece of measurement arithmetic that used to live in the PS:
        the geometry factor is common to both polarities, so averaging the two rho
        values equals the deployed combined model exactly.

        `select_first` / `select_second` are called before each half so the caller can
        point STATS_BANK_SELECT at the right bank (PS owns that).  Both halves are
        strictly gated: the second one must report PAIR_VALID, otherwise this raises
        instead of returning a lone half.

        ``k_q_floor`` goes to BOTH halves unchanged: a pair that averaged two different
        coefficient policies would be neither one.  Only the Rs-only fallback lowers it
        (see write_coefficient_k), and that caller reads Rs back itself.
        """
        if select_first is not None:
            select_first()
        self.compute(k_q_first, k_rs_q_first, timeout_s=timeout_s, k_q_floor=k_q_floor)
        if select_second is not None:
            select_second()
        self.write_coefficient_k(k_q_second, k_q_floor=k_q_floor)
        self.write_coefficient_rs(k_rs_q_second)
        self.write_quality_limits(*self._quality_limits)
        self.start(pair=True)
        status = self.wait_done(timeout_s=timeout_s)
        flags = self.read_flags()
        if flags:
            raise PlCalcError('paired compute flagged 0x%02X (%s)' % (flags, describe_flags(flags)))
        if not status & CALC_STATUS_VALID:
            raise PlCalcError('paired compute finished without VALID (status=0x%08X)' % status)
        if not status & CALC_STATUS_PAIR_VALID:
            raise PlCalcError('paired compute is missing its first half (status=0x%08X): refusing to report a lone half' % status)
        return decode_rho_q(self.read_rho_q())

    def compute(self, k_q: int, k_rs_q: int, *, timeout_s: float=0.05, k_q_floor: int=K_Q_MIN) -> float:
        """Write K_q, trigger, and return rho in ohm*cm or raise.

        The bank is whatever STATS_BANK_SELECT currently points at; the caller
        owns that (it also owns stats_center_code for that bank).  An invalid
        result raises instead of returning a number: 0 ohm is never a
        measurement, the flags are the authority.

        Both coefficients are mandatory: the RTL gates them together, so a missing
        K_rs would make every compute INVALID rather than quietly returning a rho
        without its sheet resistance.  ``k_q_floor`` is the rho channel's accuracy
        floor (see write_coefficient_k); K_rs always keeps K_Q_MIN, because the
        fallback that lowers the floor reports Rs and therefore needs Rs in budget.
        """
        self.write_coefficient_k(k_q, k_q_floor=k_q_floor)
        self.write_coefficient_rs(k_rs_q)
        self.write_quality_limits(*self._quality_limits)
        self.clear()
        self.start()
        status = self.wait_done(timeout_s=timeout_s)
        flags = self.read_flags()
        if flags:
            raise PlCalcError('meas_calc reported flags=0x%02X (status=0x%08X): %s' % (flags, status, describe_flags(flags)))
        if not status & CALC_STATUS_VALID:
            raise PlCalcError('meas_calc finished without VALID (status=0x%08X, flags=0x%02X)' % (status, flags))
        return decode_rho_q(self.read_rho_q())
_FLAG_NAMES = ((CALC_FLAG_ZERO_COUNT, 'zero_count'), (CALC_FLAG_COUNT_OVER_MAX, 'count_over_max'), (CALC_FLAG_SUM_OVERFLOW, 'sum_overflow'), (CALC_FLAG_COEFF_INVALID, 'coeff_invalid'), (CALC_FLAG_NEGATIVE, 'negative_d'), (CALC_FLAG_PAIR_MISSING, 'pair_missing'), (CALC_FLAG_QUALITY_LOW_COUNT, 'quality_low_count'), (CALC_FLAG_QUALITY_WIDE_SPAN, 'quality_wide_span'))

def describe_flags(flags: int) -> str:
    """Return a human-readable list of the latched reason bits."""
    names = [name for bit, name in _FLAG_NAMES if int(flags) & bit]
    return ', '.join(names) if names else 'none'

def summarize(*, count: int, sum_code: int, center_code: int, k_q: int) -> Optional[float]:
    """Convenience wrapper for notebooks: None when the result is not usable."""
    rho_q, flags = fixed_point_rho(count, sum_code, center_code, k_q)
    if flags:
        return None
    return decode_rho_q(rho_q)
