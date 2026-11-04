# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""PL-side ADC validity window and banked statistics reader.

The PL accumulates every ADC update during a fixed window (20 ms by default):
  * rx_update_count: every new RX_REG update
  * valid_count:     updates whose code magnitude is inside the selected bank
  * sum_codes:        sum of valid raw ADC codes
  * sum_squares:      sum of squared valid raw ADC codes
  * min_code/max_code: min/max valid raw ADC code

The reader uses callbacks supplied by FinalFourProbeSystem so all MMIO access
shares the same lock as the heartbeat thread.
"""
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Callable, Optional
REG_STATS_SUM_LOW = 256
REG_STATS_SUM_HIGH = 260
REG_STATS_VALID_COUNT = 264
REG_STATS_SUM_SQ_LOW = 268
REG_STATS_SUM_SQ_HIGH = 272
REG_STATS_RX_UPDATE_COUNT = 276
REG_STATS_MIN_CODE = 280
REG_STATS_MAX_CODE = 284
REG_STATS_SEQ = 288
REG_STATS_FLAGS = 292
REG_STATS_BANK_SELECT = 296
REG_STATS_CENTER_CODE = 300
REG_STATS_MAG_MIN = 304
REG_STATS_MAG_MAX = 308
REG_STATS_CONTROL = 312
REG_STATS_STATUS = 316
REG_STATS_ACK_SEQ = 324
STATS_FLAG_READY = 1 << 0
STATS_FLAG_EMPTY = 1 << 1
STATS_FLAG_OVERFLOW = 1 << 2
STATS_FLAG_BUSY = 1 << 3
STATS_CONTROL_CLEAR_BANK = 1 << 0
STATS_CONTROL_ARM = 1 << 1
STATS_CONTROL_ACK = 1 << 2
STATS_CONTROL_DISARM = 1 << 3
STATS_CONTROL_CLEAR_ALL = 1 << 4
STATS_BANK_COUNT = 8

class PlWindowStatsError(RuntimeError):
    """Raised when the PL statistics window cannot provide a valid snapshot."""

@dataclass(frozen=True)
class PlWindowSnapshot:
    bank: int
    seq: int
    valid_count: int
    rx_update_count: int
    sum_codes: int
    sum_squares: int
    min_code: int
    max_code: int
    ready: bool
    empty: bool
    overflow: bool
    minimum_valid_samples: int = 1
    strict_valid_count: bool = True

    @property
    def average_code(self) -> float:
        if self.valid_count <= 0:
            raise PlWindowStatsError('valid_count is zero')
        return self.sum_codes / float(self.valid_count)

    @property
    def variance_code(self) -> float:
        if self.valid_count <= 0:
            raise PlWindowStatsError('valid_count is zero')
        mean = self.average_code
        variance = self.sum_squares / float(self.valid_count) - mean * mean
        return max(0.0, variance)

    @property
    def std_code(self) -> float:
        return self.variance_code ** 0.5

class PlWindowStats:
    """Low-level banked PL statistics access using shared read/write callbacks."""

    def __init__(self, read: Callable[[int], int], write: Callable[[int, int], None]):
        self._read = read
        self._write = write

    @staticmethod
    def _validate_bank(bank: int) -> int:
        bank = int(bank)
        if bank < 0 or bank >= STATS_BANK_COUNT:
            raise ValueError('stats bank must be 0..7')
        return bank

    def select_bank(self, bank: int):
        bank = self._validate_bank(bank)
        self._write(REG_STATS_BANK_SELECT, bank)
        return bank

    def configure_bank(self, bank: int, center_code: int, mag_min: int, mag_max: int, verify: bool=True):
        """Program one bank's magnitude window and verify the write landed.

        A silently ignored write would leave the bank on its previous window
        (or the power-on default) while the PS believes it is filtering with a
        different one - the exact "PL and PS disagree about validity" failure
        mode.  ``verify=True`` reads the three registers back and raises when
        they differ; pass False only for write-only mock hardware.
        """
        bank = self.select_bank(bank)
        center_code = int(center_code)
        mag_min = int(mag_min)
        mag_max = int(mag_max)
        if not 0 <= center_code <= 65535:
            raise ValueError('center_code must be 0..65535')
        if not 0 <= mag_min <= mag_max <= 65535:
            raise ValueError('mag_min/mag_max must satisfy 0 <= min <= max <= 65535')
        self._write(REG_STATS_CENTER_CODE, center_code)
        self._write(REG_STATS_MAG_MIN, mag_min)
        self._write(REG_STATS_MAG_MAX, mag_max)
        if verify:
            readback = self.read_bank_config(bank)
            if readback['center_code'] != center_code or readback['mag_min'] != mag_min or readback['mag_max'] != mag_max:
                raise PlWindowStatsError('PL statistics bank %d window write did not stick: wrote center=%d min=%d max=%d, read back %r' % (bank, center_code, mag_min, mag_max, readback))
        return bank

    def read_bank_config(self, bank: int):
        self.select_bank(bank)
        return {'bank': int(bank), 'center_code': self._read(REG_STATS_CENTER_CODE) & 65535, 'mag_min': self._read(REG_STATS_MAG_MIN) & 65535, 'mag_max': self._read(REG_STATS_MAG_MAX) & 65535}

    def clear_bank(self, bank: int):
        bank = self.select_bank(bank)
        self._write(REG_STATS_CONTROL, STATS_CONTROL_CLEAR_BANK)
        return bank

    def clear_all(self):
        self._write(REG_STATS_CONTROL, STATS_CONTROL_CLEAR_ALL)

    def arm(self):
        self._write(REG_STATS_CONTROL, STATS_CONTROL_ARM)

    def disarm(self):
        self._write(REG_STATS_CONTROL, STATS_CONTROL_DISARM)

    def ack(self, bank: int, seq=None):
        """Acknowledge one snapshot, optionally naming the SEQ it consumed.

        Writing ``seq`` first lets the RTL refuse to clear the READY flag of a
        window that completed after the one being acknowledged; without it a
        late ACK silently swallowed the next snapshot's READY.
        """
        bank = self.select_bank(bank)
        if seq is not None:
            self._write(REG_STATS_ACK_SEQ, int(seq) & 4294967295)
        self._write(REG_STATS_CONTROL, STATS_CONTROL_ACK)
        return bank

    def read_flags(self) -> int:
        return int(self._read(REG_STATS_FLAGS)) & 4294967295

    def read_snapshot(self, bank: int, retries: int=3) -> PlWindowSnapshot:
        bank = self.select_bank(bank)
        for _ in range(max(1, int(retries))):
            seq_before = int(self._read(REG_STATS_SEQ)) & 4294967295
            sum_low = int(self._read(REG_STATS_SUM_LOW)) & 4294967295
            sum_high = int(self._read(REG_STATS_SUM_HIGH)) & 4294967295
            valid_count = int(self._read(REG_STATS_VALID_COUNT)) & 4294967295
            sq_low = int(self._read(REG_STATS_SUM_SQ_LOW)) & 4294967295
            sq_high = int(self._read(REG_STATS_SUM_SQ_HIGH)) & 4294967295
            rx_count = int(self._read(REG_STATS_RX_UPDATE_COUNT)) & 4294967295
            min_code = int(self._read(REG_STATS_MIN_CODE)) & 65535
            max_code = int(self._read(REG_STATS_MAX_CODE)) & 65535
            flags = int(self._read(REG_STATS_FLAGS)) & 4294967295
            seq_after = int(self._read(REG_STATS_SEQ)) & 4294967295
            if seq_before == seq_after:
                return PlWindowSnapshot(bank=bank, seq=seq_before, valid_count=valid_count, rx_update_count=rx_count, sum_codes=sum_high << 32 | sum_low, sum_squares=sq_high << 32 | sq_low, min_code=min_code, max_code=max_code, ready=bool(flags & STATS_FLAG_READY), empty=bool(flags & STATS_FLAG_EMPTY), overflow=bool(flags & STATS_FLAG_OVERFLOW))
        raise PlWindowStatsError('PL statistics snapshot changed while being read')

    def wait_snapshot(self, bank: int, *, timeout_s: float=0.1, poll_interval_s: float=0.005, abort_check: Optional[Callable[[], None]]=None) -> PlWindowSnapshot:
        bank = self.select_bank(bank)
        deadline = monotonic() + max(0.0, float(timeout_s))
        while monotonic() < deadline:
            if abort_check is not None:
                abort_check()
            flags = self.read_flags()
            if flags & STATS_FLAG_READY:
                snapshot = self.read_snapshot(bank)
                self.ack(bank, snapshot.seq)
                return snapshot
            sleep(max(0.0001, float(poll_interval_s)))
        raise PlWindowStatsError('timeout waiting for PL statistics snapshot')
