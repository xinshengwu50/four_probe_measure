# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Optional contact/compliance diagnostics. Not an independent current measurement."""
import math
RANGE_LINEARITY_MIN_SIGNAL_V = 0.0125

def finite(value):
    return float(value) if isinstance(value, (int, float)) and (not isinstance(value, bool)) and math.isfinite(value) else None

def validate_threshold(value, name):
    if value is not None and (finite(value) is None or value < 0):
        raise ValueError(name + ' must be None or a finite nonnegative number')
    return None if value is None else float(value)

def validate_sample_label(value):
    if not isinstance(value, str) or len(value) > 160 or any((ord(c) < 32 for c in value)):
        raise ValueError('sample_label must be a single-line string of at most160 characters')
    return value

def evaluate_quality(record, candidates=(), *, max_polarity_asymmetry=None, max_offset_to_signal_ratio=None, max_range_nonlinearity=None):
    limits = [validate_threshold(v, n) for v, n in ((max_polarity_asymmetry, 'max_polarity_asymmetry'), (max_offset_to_signal_ratio, 'max_offset_to_signal_ratio'), (max_range_nonlinearity, 'max_range_nonlinearity'))]
    rf = finite(record.get('forward_resistance_ohm'))
    rr = finite(record.get('reverse_resistance_ohm'))
    resistance = finite(record.get('combined_resistance_ohm'))
    signal = finite(record.get('pair_margin_v'))
    offset = finite(record.get('offset_estimate_v'))
    asymmetry = abs(rf - rr) / abs(resistance) if rf is not None and rr is not None and (resistance not in (None, 0.0)) else None
    offset_ratio = abs(offset) / abs(signal) if offset is not None and signal not in (None, 0.0) else None
    usable = {}
    for candidate in candidates or ():
        try:
            index = int(candidate.range_index)
            voltage = finite(candidate.filtered_probe_voltage_v)
            value = finite(candidate.resistance_ohm)
            count = int(candidate.capture.valid_sample_count)
        except (AttributeError, ValueError, TypeError):
            continue
        if count > 0 and voltage is not None and (abs(voltage) >= RANGE_LINEARITY_MIN_SIGNAL_V) and (value is not None) and (value > 0):
            usable[index] = value
    ratios = [abs(usable[i + 1] / value - 1.0) for i, value in usable.items() if i + 1 in usable]
    linearity = max(ratios) if ratios else None
    values = [finite(asymmetry), finite(offset_ratio), finite(linearity)]
    flags = []
    for i, (value, limit, name) in enumerate(zip(values, limits, ('POLARITY_ASYMMETRY', 'OFFSET_TO_SIGNAL', 'RANGE_NONLINEARITY'))):
        if limit is not None:
            if value is not None and value > limit:
                flags.append(name)
            elif value is None and (i < 2 or ratios):
                flags.append(name + '_UNDEFINED')
    return dict(polarity_asymmetry=values[0], offset_to_signal_ratio=values[1], range_linearity=values[2], quality_flags=flags)
