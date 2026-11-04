# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Deterministic sample filtering and descriptive statistics."""
from __future__ import annotations
from dataclasses import dataclass
import math
import statistics
from typing import Iterable, Optional

@dataclass(frozen=True)
class SampleSummary:
    """Statistics for the accepted subset of a sample batch."""
    total_count: int
    valid_count: int
    rejected_count: int
    valid_ratio: float
    mean: Optional[float]
    median: Optional[float]
    stddev: Optional[float]
    rms: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]
    valid_samples: tuple[float, ...]

def median(values: Iterable[float]) -> float:
    """Return the median of a non-empty iterable."""
    data = [float(value) for value in values]
    if not data:
        raise ValueError('median requires at least one value')
    if any((not math.isfinite(value) for value in data)):
        raise ValueError('median values must be finite')
    return statistics.median(data)

def summarize_samples(samples: Iterable[float], *, minimum: Optional[float]=None, maximum: Optional[float]=None, reject_zero: bool=True) -> SampleSummary:
    """Reject invalid samples and compute statistics for the remaining values."""
    if minimum is not None and (not math.isfinite(minimum)):
        raise ValueError('minimum must be finite')
    if maximum is not None and (not math.isfinite(maximum)):
        raise ValueError('maximum must be finite')
    if minimum is not None and maximum is not None and (minimum > maximum):
        raise ValueError('minimum must not exceed maximum')
    raw = list(samples)
    accepted: list[float] = []
    for item in raw:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        if reject_zero and value == 0.0:
            continue
        if minimum is not None and value < minimum:
            continue
        if maximum is not None and value > maximum:
            continue
        accepted.append(value)
    total_count = len(raw)
    valid_count = len(accepted)
    if valid_count == 0:
        return SampleSummary(total_count=total_count, valid_count=0, rejected_count=total_count, valid_ratio=0.0 if total_count else 0.0, mean=None, median=None, stddev=None, rms=None, minimum=None, maximum=None, valid_samples=())
    mean_value = statistics.fmean(accepted)
    return SampleSummary(total_count=total_count, valid_count=valid_count, rejected_count=total_count - valid_count, valid_ratio=valid_count / total_count if total_count else 0.0, mean=mean_value, median=statistics.median(accepted), stddev=statistics.pstdev(accepted) if valid_count > 1 else 0.0, rms=math.sqrt(statistics.fmean((value * value for value in accepted))), minimum=min(accepted), maximum=max(accepted), valid_samples=tuple(accepted))
