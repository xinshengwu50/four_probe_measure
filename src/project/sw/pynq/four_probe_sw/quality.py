# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Measurement quality gates shared by offline tests and PYNQ applications."""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Iterable, Optional
from .filtering import SampleSummary, summarize_samples

@dataclass(frozen=True)
class QualityThresholds:
    """Acceptance thresholds for one batch of voltage samples."""
    min_samples: int = 1
    min_valid_ratio: float = 1.0
    max_stddev_v: Optional[float] = None
    max_relative_spread: Optional[float] = None
    max_saturation_ratio: float = 0.0
    reject_zero: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.min_samples, int) or isinstance(self.min_samples, bool) or self.min_samples < 0:
            raise ValueError('min_samples must be a non-negative integer')
        if not 0.0 <= self.min_valid_ratio <= 1.0:
            raise ValueError('min_valid_ratio must be between 0 and 1')
        if not 0.0 <= self.max_saturation_ratio <= 1.0:
            raise ValueError('max_saturation_ratio must be between 0 and 1')
        for value, name in ((self.max_stddev_v, 'max_stddev_v'), (self.max_relative_spread, 'max_relative_spread')):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f'{name} must be finite and non-negative')

@dataclass(frozen=True)
class QualityReport:
    """Quality result and the statistics used to reach it."""
    ok: bool
    score: float
    reason_codes: tuple[str, ...]
    total_count: int
    valid_count: int
    valid_ratio: float
    mean: Optional[float]
    median: Optional[float]
    stddev: Optional[float]
    relative_spread: Optional[float]
    saturation_count: int
    saturation_ratio: float

def _relative_spread(summary: SampleSummary) -> Optional[float]:
    if summary.mean is None or summary.stddev is None:
        return None
    if summary.mean == 0.0:
        return 0.0 if summary.stddev == 0.0 else math.inf
    return abs(summary.stddev / summary.mean)

def evaluate_quality(samples: Iterable[float], thresholds: QualityThresholds, *, minimum: Optional[float]=None, maximum: Optional[float]=None, saturation_flags: Optional[Iterable[bool]]=None) -> QualityReport:
    """Evaluate validity ratio, noise and saturation for a sample batch."""
    raw = list(samples)
    flags = [bool(flag) for flag in saturation_flags] if saturation_flags is not None else [False] * len(raw)
    if len(flags) != len(raw):
        raise ValueError('saturation_flags length must match samples')
    summary = summarize_samples(raw, minimum=minimum, maximum=maximum, reject_zero=thresholds.reject_zero)
    saturation_count = sum(flags)
    saturation_ratio = saturation_count / len(raw) if raw else 0.0
    relative_spread = _relative_spread(summary)
    reasons: list[str] = []
    if summary.valid_count < thresholds.min_samples:
        reasons.append('VALID_COUNT_LOW')
    if summary.valid_ratio < thresholds.min_valid_ratio:
        reasons.append('VALID_RATIO_LOW')
    if thresholds.max_stddev_v is not None and (summary.stddev is None or summary.stddev > thresholds.max_stddev_v):
        reasons.append('NOISE_HIGH')
    if thresholds.max_relative_spread is not None and (relative_spread is None or relative_spread > thresholds.max_relative_spread):
        reasons.append('RELATIVE_SPREAD_HIGH')
    if saturation_ratio > thresholds.max_saturation_ratio:
        reasons.append('SATURATION_HIGH')
    score = 100.0 * summary.valid_ratio
    if thresholds.max_stddev_v is not None and summary.stddev is not None and (thresholds.max_stddev_v > 0):
        score *= min(1.0, thresholds.max_stddev_v / max(summary.stddev, thresholds.max_stddev_v))
    if saturation_ratio > thresholds.max_saturation_ratio:
        score *= max(0.0, 1.0 - saturation_ratio)
    score = max(0.0, min(100.0, score))
    return QualityReport(ok=not reasons, score=score, reason_codes=tuple(reasons), total_count=summary.total_count, valid_count=summary.valid_count, valid_ratio=summary.valid_ratio, mean=summary.mean, median=summary.median, stddev=summary.stddev, relative_spread=relative_spread, saturation_count=saturation_count, saturation_ratio=saturation_ratio)
