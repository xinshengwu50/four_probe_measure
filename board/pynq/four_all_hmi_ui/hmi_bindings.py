# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Read-back verified current-display binding for final-copy HMI.
page1.current text component ID83; x20 integer mA, x21 hundredths, vvs1=0.
Display nominal RANGE, never substitute it for calibration currents in math/CSV.
"""
import math
NOMINAL_RANGE_MA=(.1,1.,10.,100.)
CURRENT_TEXT_TARGET='p[9].b[83]'

def nominal_range_ma(index):
    if isinstance(index,bool) or index not in range(4):raise ValueError('range index must be 0..3')
    return NOMINAL_RANGE_MA[index]

def write_current_display(uart,current_ma,*,pending=False):
    value=float(current_ma)
    if not math.isfinite(value) or value<0 or value*100>2147483647:raise ValueError('invalid display current')
    encoded=round(value*100);whole,fraction=divmod(encoded,100)
    for cmd in ['p[8].x0.val=%d'%encoded,'p[9].x20.val=%d'%whole,'p[9].x21.val=%d'%fraction,
                'p[9].t35.txt="%d"'%whole,'p[9].t36.txt="%02d"'%fraction,
                CURRENT_TEXT_TARGET+'.txt="'+('AUTO' if pending else '%d.%02dmA'%(whole,fraction))+'"']:
        uart.send_command(cmd)


def write_sample_metadata(uart, config):
    """Populate page0 sources BEFORE navigation/preinit copies them to sidebars.
    Environment is placeholder DEFAULT_NOT_MEASURED, not sensor acquisition.
    """
    from .hmi_single_point import DEFAULT_TEMPERATURE_C, DEFAULT_HUMIDITY_PCT
    values = {
        'x2': round(DEFAULT_TEMPERATURE_C * 10),
        'x3': round(DEFAULT_HUMIDITY_PCT * 10),
        'x4': round(config.thickness_um * 100),
        'x5': round(config.probe_spacing_mm * 10),
        'x6': round(config.diameter_mm * 10),
        'x7': 1 if config.polarity.upper() == 'N' else 0,
    }
    for control, value in values.items():
        if not 0 <= value <= 2147483647:
            raise ValueError('sample metadata exceeds HMI integer range')
        uart.send_command('p[8].%s.val=%d' % (control, value))
