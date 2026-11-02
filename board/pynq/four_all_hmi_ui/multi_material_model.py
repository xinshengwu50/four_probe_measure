# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Four-probe model migrated from the reference competition implementation.

The physical calculation follows ``ce_calc.c`` from the reference project:

    R = |V| / I
    FD = finite-diameter correction (exact centered thin-disk formula for D/S > 3)
    FW = 1.0 for single-sided diffusion, otherwise the exact F(W/S) slab factor
    rho = R * FD * FW * W * Fsp
    R_sheet = rho / W

2026-10-15 corrections against an independent physics reference
(AMD ``four_probe_physics_reference.py``):

* ``ce_calc.c`` summed ``1/(x^2+1) - 1/(x^2+4)`` instead of the image-series
  ``1/sqrt(x^2+1) - 1/sqrt(x^2+4)`` and hid the wrong result behind a
  0.80--1.05 clamp.  At W/S = 0.645 it returned 1.05; the correct value is
  0.98787 (+6.3 % error on rho and R_sheet).
* For D/S > 3 the circular-column table lookup is replaced by the closed form
  it tabulates.  The silicon (double) table held 4.5324 (the infinite-sheet
  value) for every D/S >= 3, and interpolating towards the 1e9 sentinel froze
  the single table at its D/S = 40 entry.  At D/S = 50 the correct value is
  4.51672.  The legacy tables are kept only for D/S <= 3, where the outer
  probes no longer fit on the disk.
* Off-centre points use the centred factor; no edge correction is applied.

Inputs use the unit convention requested by the AMDFPGA project: diameter in
millimetres, thickness in micrometres, current in milliamperes, voltage in
millivolts and probe spacing in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional


FSP_DEFAULT = 1.001
SCIENTIFIC_DECIMAL_PLACES = 5
_SCIENTIFIC_SCALE = 10**SCIENTIFIC_DECIMAL_PLACES


class SampleType(str, Enum):
    """Supported sample structures."""

    SILICON = "silicon"
    ALGAN = "algan"
    HEMT = "hemt"

    @classmethod
    def from_value(cls, value: object) -> "SampleType":
        if isinstance(value, cls):
            return value
        text = str(value).strip().lower()
        aliases = {
            "si": cls.SILICON,
            "silicon": cls.SILICON,
            "单晶硅": cls.SILICON,
            "algan": cls.ALGAN,
            "algan外延片": cls.ALGAN,
            "hemt": cls.HEMT,
            "hemt器件片": cls.HEMT,
        }
        try:
            return aliases[text]
        except KeyError as exc:
            raise ValueError("unsupported sample type: %r" % (value,)) from exc


@dataclass(frozen=True)
class ScientificValue:
    """A value represented as ``mantissa / 100000 * 10**exponent``."""

    exponent: int
    mantissa: int


@dataclass(frozen=True)
class FourProbeResult:
    """Computed values and correction factors for one sample point."""

    sample_type: SampleType
    a: float
    diameter_over_spacing: float
    fd: float
    fw: float
    fsp: float
    resistivity_ohm_cm: float
    sheet_resistance_ohm_per_square: float
    ndop_cm3: float
    used_table_type: int
    rho_scientific: ScientificValue
    sheet_scientific: ScientificValue
    ndop_scientific: ScientificValue


_TABLE_SINGLE = (
    (1.0, 0.9988, 0.9994, 0.9990, 0.9990, 0.9990),
    (1.25, 1.2467, 1.2248, 1.2600, 1.2600, 1.2600),
    (1.5, 1.4000, 1.4500, 1.4788, 1.4893, 1.4893),
    (1.75, 1.6500, 1.7000, 1.7196, 1.7238, 1.7238),
    (2.0, 1.9000, 1.9500, 1.9454, 1.9475, 1.9475),
    (2.5, 2.2000, 2.3000, 2.3532, 2.3541, 2.3541),
    (3.0, 2.2662, 2.4575, 2.7000, 2.7005, 2.7005),
    (4.0, 2.9289, 3.1137, 3.2246, 3.2248, 3.2248),
    (5.0, 3.3625, 3.5098, 3.5749, 3.5750, 3.5750),
    (7.5, 3.9273, 4.0095, 4.0361, 4.0362, 4.0362),
    (10.0, 4.1716, 4.2209, 4.2357, 4.2357, 4.2357),
    (15.0, 4.3646, 4.3882, 4.3947, 4.3947, 4.3947),
    (20.0, 4.4364, 4.4516, 4.4553, 4.4553, 4.4553),
    (40.0, 4.5076, 4.5120, 4.5129, 4.5129, 4.5129),
    (1e9, 4.5324, 4.5324, 4.5324, 4.5324, 4.5324),
)

_TABLE_DOUBLE = (
    (1.0, 1.9976, 1.9497, 1.9300, 1.9300, 1.9300),
    (1.25, 2.3741, 2.3550, 2.3500, 2.3500, 2.3500),
    (1.5, 2.9575, 2.7113, 2.7010, 2.7010, 2.7010),
    (1.75, 3.1596, 2.9953, 2.9887, 2.9887, 2.9887),
    (2.0, 3.3381, 3.2295, 3.2248, 3.2248, 3.2248),
    (2.5, 3.6408, 3.5778, 3.5751, 3.5751, 3.5751),
    (3.0, 4.5324, 4.9124, 3.8543, 3.8127, 3.8109),
    (4.0, 4.5324, 4.6477, 4.1118, 4.0899, 4.0888),
    (5.0, 4.5324, 4.5970, 4.2504, 4.2362, 4.2356),
    (7.5, 4.5324, 4.5415, 4.4008, 4.3946, 4.3943),
    (10.0, 4.5324, 4.5353, 4.4571, 4.4536, 4.4535),
    (15.0, 4.5324, 4.5329, 4.4985, 4.4969, 4.4969),
    (20.0, 4.5324, 4.5326, 4.5132, 4.5124, 4.5124),
    (40.0, 4.5324, 4.5325, 4.5275, 4.5273, 4.5273),
    (1e9, 4.5324, 4.5324, 4.5324, 4.5324, 4.5324),
)

_FD_FALLBACK_X = (5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 80.0, 100.0, 200.0, 1e9)
_FD_FALLBACK_Y = (4.05, 4.25, 4.42, 4.48, 4.495, 4.505, 4.515, 4.520, 4.527, 4.532)


# Image terms summed directly before the Euler-Maclaurin tail takes over.
# 64 keeps fw_from_alpha() well under 1e-9 relative error for every W/S while
# costing only ~64 loop iterations on the Cortex-A9.
_FW_DIRECT_TERMS = 64


def _image_term(n: float, alpha: float) -> float:
    """Return ``1/sqrt(1+z^2) - 1/sqrt(4+z^2)`` with ``z = 2*n*alpha``.

    Written as ``3/(u*v*(u+v))`` so the subtraction does not cancel.
    """

    z = 2.0 * n * alpha
    u = math.hypot(z, 1.0)
    v = math.hypot(z, 2.0)
    return 3.0 / (u * v * (u + v))


def _image_tail(n: float, alpha: float) -> float:
    """Euler-Maclaurin estimate of ``sum_{k>=n} _image_term(k, alpha)``."""

    # Integral from n to infinity: (ln2 - asinh(2y) + asinh(y)) / (2*alpha),
    # y = alpha*n, rearranged into a log1p so large y does not cancel.
    y = alpha * n
    denominator = (
        (math.sqrt(4.0 * y * y + 1.0) + math.sqrt(4.0 * y * y + 4.0))
        * 2.0 * (y + math.sqrt(y * y + 1.0))
    )
    integral = -math.log1p(-3.0 / denominator) / (2.0 * alpha)
    z = 2.0 * n * alpha
    derivative = -4.0 * alpha * alpha * n * (
        (1.0 + z * z) ** -1.5 - (4.0 + z * z) ** -1.5
    )
    return integral + 0.5 * _image_term(n, alpha) - derivative / 12.0


def fw_from_alpha(alpha: float) -> float:
    """Return the thickness correction ``FW = F(W/S)`` for a slab.

    Exact image solution for collinear equally spaced probes on a laterally
    infinite slab with insulating faces:

        A  = 1 + 4 * sum_n [1/sqrt(1+(2n*a)^2) - 1/sqrt(4+(2n*a)^2)]
        FW = 2*ln(2) / (a * A),   a = W/S

    FW -> 1 for a thin sheet (a -> 0) and FW -> 2*ln(2)/a for a half space.
    Reference values: a=0.5 -> 0.99737, a=0.645 -> 0.98787, a=1 -> 0.92147.
    """

    alpha = float(alpha)
    if not math.isfinite(alpha):
        raise ValueError("alpha must be finite")
    if alpha <= 0.0:
        return 1.0

    total = 0.0
    for n in range(1, _FW_DIRECT_TERMS):
        total += _image_term(n, alpha)
    total += _image_tail(_FW_DIRECT_TERMS, alpha)
    return 2.0 * math.log(2.0) / (alpha * (1.0 + 4.0 * total))


def fd_circular_disk(diameter_over_spacing: float) -> float:
    """Return the finite-diameter correction for a centred circular sheet.

    Collinear probes on a diameter, insulating rim, D/S > 3:

        FD = pi / (ln2 + ln((D^2 + 3S^2) / (D^2 - 3S^2)))

    This is the closed form behind the circular column of the reference
    tables (D/S = 3 -> 2.2662, 10 -> 4.1716, 40 -> 4.5080) and tends to
    pi/ln2 = 4.5324 for an infinite sheet.  D/S = 50 -> 4.51672.
    """

    value = float(diameter_over_spacing)
    if not math.isfinite(value) or value <= 3.0:
        raise ValueError("diameter_over_spacing must be finite and > 3")
    return math.pi / (math.log(2.0) + math.log1p(6.0 / (value * value - 3.0)))


def fd_from_ds_fallback(diameter_over_spacing: float) -> float:
    """Return the RTS-8 fallback diameter correction from the reference code."""

    value = float(diameter_over_spacing)
    if value <= _FD_FALLBACK_X[0]:
        return _FD_FALLBACK_Y[0]
    for index in range(1, len(_FD_FALLBACK_X)):
        if value <= _FD_FALLBACK_X[index]:
            lower = _FD_FALLBACK_X[index - 1]
            upper = _FD_FALLBACK_X[index]
            ratio = (value - lower) / (upper - lower)
            return _FD_FALLBACK_Y[index - 1] + ratio * (
                _FD_FALLBACK_Y[index] - _FD_FALLBACK_Y[index - 1]
            )
    return _FD_FALLBACK_Y[-1]


def _interpolate_circular_table(
    table: tuple[tuple[float, ...], ...], diameter_over_spacing: float
) -> float:
    """Interpolate the circular column of a reference correction table."""

    value = float(diameter_over_spacing)
    if value <= table[0][0]:
        return table[0][1]
    if value >= table[-1][0]:
        return table[-1][1]

    for index in range(len(table) - 1):
        x1 = table[index][0]
        x2 = table[index + 1][0]
        if abs(value - x1) < 1e-9:
            return table[index][1]
        if value < x2:
            y1 = table[index][1]
            y2 = table[index + 1][1]
            return y1 + (value - x1) * (y2 - y1) / (x2 - x1)
    return table[-1][1]


def ndop_from_rho_silicon(rho_ohm_cm: float, is_n_type: bool) -> float:
    """Return silicon doping concentration using the reference formulas."""

    rho = abs(float(rho_ohm_cm))
    if rho <= 0.0:
        return 0.0

    if not is_n_type:
        term1 = 1.330e16 / rho
        term2 = (1.082e-17 * rho) / (1.0 + (54.56 * rho) ** 1.105)
        return term1 + term2

    x = math.log10(rho)
    x2 = x * x
    x3 = x2 * x
    numerator = -3.1083 - 3.2626 * x - 1.2196 * x2 - 0.13923 * x3
    denominator = 1.0 + 1.0265 * x + 0.38755 * x2 + 0.041833 * x3
    exponent = numerator / denominator
    return (6.242e18 / rho) * (10.0 ** exponent)


def encode_scientific(value: float, decimal_places: int = SCIENTIFIC_DECIMAL_PLACES) -> ScientificValue:
    """Encode a non-negative value as a rounded mantissa and decimal exponent.

    ``mantissa / 10**decimal_places * 10**exponent`` reconstructs the displayed
    value. Rounding is half-up, as requested for the serial-screen payload.
    """

    if decimal_places < 0:
        raise ValueError("decimal_places must be non-negative")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    if value < 0.0:
        raise ValueError("scientific encoding only supports non-negative values")
    if value == 0.0:
        return ScientificValue(exponent=0, mantissa=0)

    exponent = int(math.floor(math.log10(value)))
    normalized = value / (10.0 ** exponent)
    while normalized >= 10.0:
        normalized /= 10.0
        exponent += 1
    while normalized < 1.0:
        normalized *= 10.0
        exponent -= 1

    scale = 10**decimal_places
    mantissa = int(math.floor(normalized * scale + 0.5))
    if mantissa >= 10 * scale:
        mantissa = scale
        exponent += 1
    return ScientificValue(exponent=exponent, mantissa=mantissa)


def calculate_four_probe(
    *,
    sample_type: SampleType,
    is_n_type: bool,
    diameter_mm: float,
    thickness_um: float,
    current_ma: float,
    voltage_mv: float,
    probe_spacing_mm: float = 1.0,
    sample_structure=None,
) -> FourProbeResult:
    """Calculate rho, sheet resistance and silicon doping concentration."""

    sample = SampleType.from_value(sample_type)
    values = {
        "diameter_mm": diameter_mm,
        "thickness_um": thickness_um,
        "current_ma": current_ma,
        "probe_spacing_mm": probe_spacing_mm,
    }
    converted = {}
    for name, raw_value in values.items():
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("%s must be numeric" % name) from exc
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("%s must be finite and positive" % name)
        converted[name] = value

    try:
        voltage = abs(float(voltage_mv))
    except (TypeError, ValueError) as exc:
        raise ValueError("voltage_mv must be numeric") from exc
    if not math.isfinite(voltage):
        raise ValueError("voltage_mv must be finite")

    diameter_mm = converted["diameter_mm"]
    thickness_um = converted["thickness_um"]
    current_ma = converted["current_ma"]
    probe_spacing_mm = converted["probe_spacing_mm"]

    thickness_cm = thickness_um * 1.0e-4
    probe_spacing_cm = probe_spacing_mm * 0.1
    diameter_cm = diameter_mm * 0.1
    current_a = current_ma * 1.0e-3
    voltage_v = voltage * 1.0e-3

    alpha = thickness_cm / probe_spacing_cm
    diameter_over_spacing = diameter_cm / probe_spacing_cm

    # used_table_type keeps its HMI meaning (6 = thin film, 5 = silicon slab)
    # even though FD now comes from the closed form whenever D/S > 3.
    if sample_structure is not None and (isinstance(sample_structure,bool) or sample_structure not in (0,1,2)):
        raise ValueError('sample_structure must be0epitaxial/1substrate/2HEMT')
    if sample_structure == 2:
        sample = SampleType.HEMT
    single = sample_structure in (0,2) if sample_structure is not None else sample in (SampleType.ALGAN, SampleType.HEMT)
    if single:
        used_table_type = 6
        table = _TABLE_SINGLE
        fw = 1.0
    else:
        used_table_type = 5
        table = _TABLE_DOUBLE
        fw = fw_from_alpha(alpha)
    if diameter_over_spacing > 3.0:
        fd = fd_circular_disk(diameter_over_spacing)
    else:
        fd = _interpolate_circular_table(table, diameter_over_spacing)

    if not fd > 0.0:
        fd = fd_from_ds_fallback(diameter_over_spacing)

    resistance_ohm = voltage_v / current_a
    resistivity_ohm_cm = resistance_ohm * fd * fw * thickness_cm * FSP_DEFAULT
    sheet_resistance = (
        resistivity_ohm_cm / thickness_cm if thickness_cm != 0.0 else 0.0
    )

    if sample is SampleType.SILICON:
        ndop_cm3 = ndop_from_rho_silicon(resistivity_ohm_cm, bool(is_n_type))
    else:
        ndop_cm3 = 0.0

    return FourProbeResult(
        sample_type=sample,
        a=alpha,
        diameter_over_spacing=diameter_over_spacing,
        fd=fd,
        fw=fw,
        fsp=FSP_DEFAULT,
        resistivity_ohm_cm=resistivity_ohm_cm,
        sheet_resistance_ohm_per_square=sheet_resistance,
        ndop_cm3=ndop_cm3,
        used_table_type=used_table_type,
        rho_scientific=encode_scientific(resistivity_ohm_cm),
        sheet_scientific=encode_scientific(sheet_resistance),
        ndop_scientific=encode_scientific(ndop_cm3),
    )

