"""Inverse conversion of a signal-voltage window to raw ADC codes; no MMIO."""
import math
from adc_capture import AdcConfig, decode_frame

def signal_window_codes(config, low_v, high_v):
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (low_v, high_v)) or low_v > high_v:
        raise ValueError('invalid voltage window')
    levels = 1 << config.code_bits
    lsb = (config.input_max_v - config.input_min_v) / levels
    a = (low_v * config.gain + config.bias_v - config.input_min_v) / lsb
    b = (high_v * config.gain + config.bias_v - config.input_min_v) / lsb
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError('inverse conversion overflow')
    lo, hi = max(0, math.ceil(a)), min(levels - 1, math.floor(b))
    if lo > hi:
        raise ValueError('window contains no representable code')
    # normalized monotonic codes differ from raw encoding for two's complement.
    if config.coding == 'twos':
        half = levels // 2
        pieces = []
        if lo < half:
            pieces.append([lo + half, min(hi, half - 1) + half])
        if hi >= half:
            pieces.append([max(lo, half) - half, hi - half])
    else:
        pieces = [[lo, hi]]
    zero_normal = (config.bias_v - config.input_min_v) / lsb
    zero_raw = None
    if 0 <= zero_normal <= levels - 1:
        n = round(zero_normal)
        zero_raw = (n - levels // 2) % levels if config.coding == 'twos' else n
    return {'normalized_bounds': [lo, hi], 'raw_intervals': pieces,
            'signal_zero_raw_code': zero_raw, 'adc_lsb_v': lsb,
            'evidence': 'OFFLINE_INVERSE_MODEL', 'hardware_verified': False}
