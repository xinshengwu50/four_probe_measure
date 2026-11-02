# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Relative blue palette for discrete measured-point cells; no interpolation."""
def blue_color(value,low,high):
    t=.5 if high==low else max(0.,min(1.,(value-low)/(high-low)))
    a=(225,242,255);b=(12,63,145)
    return tuple(round(a[i]*(1-t)+b[i]*t) for i in range(3))

