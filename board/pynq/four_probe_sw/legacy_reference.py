# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Executable reference for the old integer expressions.

These functions preserve the legacy stepwise truncation for regression only.
They are intentionally separate from :mod:`measurement_model`, whose public
API uses SI units and documented calibration parameters.
"""
from __future__ import annotations

def legacy_resistance(v_mV: int, i_mA: int) -> int:
    """Return the old ``(V_mV * 100) / I_mA`` integer result."""
    if i_mA == 0:
        raise ValueError('legacy current must not be zero')
    return v_mV * 100 // i_mA

def legacy_resistivity(v_mV: int, *, fsp: int=1001, fd: int=4532, fw: int=1050, w_mm: int=645) -> int:
    """Preserve the old bulk-resistivity expression and truncation points."""
    step1 = v_mV * fd // 10
    step2 = step1 * fw // 1000
    step3 = step2 * w_mm // 10000
    return step3 * fsp // 100

def legacy_sheet_resistance(v_mV: int, *, fsp: int=1001, fd: int=4532, fw: int=1050) -> int:
    """Preserve the old sheet-resistance expression and truncation points."""
    step1 = v_mV * fd // 100
    step2 = step1 * fw // 1000
    return step2 * fsp // 1000
