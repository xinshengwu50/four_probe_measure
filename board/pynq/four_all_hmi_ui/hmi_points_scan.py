# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Multi-point scan write-back for final.HMI (mode 2 = 25点, mode 3 = 9点).

This module owns everything that is a pure HMI contract -- which control on which
page receives which quantity for point N, at what scale, in what order -- and
leaves the motion/ADC orchestration behind :class:`PointSource`.  That split
keeps the trap-heavy half testable offline.

Scales come from the 虚拟浮点数 `vvs1` (displayed value = raw / 10**vvs1):

| quantity                        | controls        | vvs1 | scale  |
|---------------------------------|-----------------|------|--------|
| 方块电阻 mantissa on data pages | x31-x39         | 2    | 100    |
| 电阻率 mantissa                 | x1-x9 / x11-x19 | 5    | 100000 |
| 掺杂浓度 mantissa               | x11-x19         | 5    | 100000 |
| 正向电压 (V pages)              | x31-x39 / x30   | 5    | 100000 |
| 反向电压 (V pages)              | x11-x19 / x10   | 5    | 100000 |

WARNING: `x31-x39` and `x11-x19` mean different things on different page
families (方块电阻/电阻率/掺杂浓度 on the data pages, 正向/反向电压 on the V
pages).  Never share a cell map between the two families.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Sequence

from .hmi_single_point import (
    Hmi22Writer,
    MeasurementMode,
    SampleKind,
)

# --------------------------------------------------------------------------
# Scales
# --------------------------------------------------------------------------
RS_SCALE = 100
RHO_SCALE = 100000
NDOP_SCALE = 100000
V_FORWARD_SCALE = 100000
V_REVERSE_SCALE = 100000

POINT_COUNT = {
    MeasurementMode.TWENTY_FIVE_POINT: 25,
    MeasurementMode.NINE_POINT: 9,
}

#: 三代 = HEMT / AlGaN ; 非三 = 硅（以及"其他"按非三处理）
FAMILY_OF_SAMPLE = {
    SampleKind.HEMT: "gen3",
    SampleKind.ALGAN: "gen3",
    SampleKind.GAN: "gen3",
    SampleKind.SILICON: "non3",
}


# --------------------------------------------------------------------------
# Page cell maps
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PageCells:
    """One data page: the point range it owns plus its per-row cell names.

    `first_point` is 1-based; row 0 of the page holds `first_point`.  三代 pages
    have only 方块电阻 and 电阻率 columns; 非三 pages add 掺杂浓度.
    """

    name: str
    first_point: int
    rs: tuple
    rs_exp: tuple
    rho: tuple
    rho_exp: tuple
    ndop: tuple = ()
    ndop_exp: tuple = ()

    @property
    def rows(self) -> int:
        return len(self.rs)

    def owns(self, index: int) -> bool:
        return self.first_point <= index < self.first_point + self.rows

    @property
    def last_point(self) -> int:
        return self.first_point + self.rows - 1


def _seq(prefix: str, start: int, n: int) -> tuple:
    return tuple("%s%d" % (prefix, start + i) for i in range(n))


_RS_EXP = ("t4", "t5", "t7", "t10", "t11", "t12", "t13", "t16", "t18")
_CENTER_EXP_NON3 = ("t19", "t22", "t24", "t26", "t28", "t30", "t32", "t34", "t36")
_RIGHT_EXP_NON3 = ("t54", "t52", "t50", "t48", "t38", "t40", "t42", "t44", "t46")

# Non3 pages: Rs x31..39; Ndop CENTER x1..9; rho RIGHT x11..19. Match the screen labels.
NON3_25 = (
    PageCells("二十五非三1", 1, _seq("x", 31, 9), _RS_EXP,
              _seq("x", 11, 9), _RIGHT_EXP_NON3, _seq("x", 1, 9), _CENTER_EXP_NON3),
    PageCells("二十五非三2", 10, _seq("x", 31, 9), _RS_EXP,
              _seq("x", 11, 9), _RIGHT_EXP_NON3, _seq("x", 1, 9), _CENTER_EXP_NON3),
    PageCells("二十五非三3", 19, _seq("x", 31, 7), _RS_EXP[:7],
              _seq("x", 11, 7), _RIGHT_EXP_NON3[:7], _seq("x", 1, 7), _CENTER_EXP_NON3[:7]),
)

# 二十五三代 1/2/3 : 无掺杂浓度列，电阻率在 x11-x19
GEN3_25 = (
    PageCells("二十五三代1", 1, _seq("x", 31, 9), _RS_EXP, _seq("x", 11, 9),
              ("t20", "t22", "t24", "t26", "t28", "t30", "t33", "t34", "t36")),
    PageCells("二十五三代2", 10, _seq("x", 31, 9), _RS_EXP, _seq("x", 11, 9),
              ("t35", "t34", "t31", "t30", "t28", "t26", "t23", "t21", "t19")),
    PageCells("二十五三代3", 19, _seq("x", 31, 7), _RS_EXP[:7], _seq("x", 11, 7),
              ("t31", "t30", "t27", "t26", "t24", "t22", "t19")),
)

# 九点页
NON3_9 = (PageCells("九点非三", 1, _seq("x", 31, 9), _RS_EXP, _seq("x", 11, 9),
                    ("t54", "t52", "t50", "t41", "t38", "t40", "t31", "t34", "t36"),
                    _seq("x", 1, 9),
                    ("t48", "t46", "t44", "t19", "t22", "t24", "t25", "t28", "t30")),)
GEN3_9 = (PageCells("九点三代", 1, _seq("x", 31, 9), _RS_EXP, _seq("x", 11, 9),
                    ("t35", "t34", "t31", "t30", "t28", "t26", "t23", "t21", "t19")),)

DATA_PAGES = {
    MeasurementMode.TWENTY_FIVE_POINT: {"non3": NON3_25, "gen3": GEN3_25},
    MeasurementMode.NINE_POINT: {"non3": NON3_9, "gen3": GEN3_9},
}

# (页名, 正向控件, 反向控件) —— V 页不分材料类型
VOLTAGE_PAGES = {
    MeasurementMode.TWENTY_FIVE_POINT: (
        ("V251", _seq("x", 31, 9), _seq("x", 11, 9)),
        ("V252", _seq("x", 31, 9), _seq("x", 11, 9)),
        ("V253", _seq("x", 31, 7), _seq("x", 11, 7)),
    ),
    MeasurementMode.NINE_POINT: (
        ("V9", _seq("x", 31, 9), _seq("x", 11, 9)),
    ),
}


def family_of(sample_kind: SampleKind) -> str:
    try:
        return FAMILY_OF_SAMPLE[sample_kind]
    except KeyError:
        raise ValueError("unsupported sample_kind=%r" % (sample_kind,))


def split_scientific(value: Optional[float], scale: int = RHO_SCALE) -> tuple:
    """Split `value` into (mantissa, exponent) with `scale` decimals held.

    final.HMI reassembles these as `int(m/scale) + "." + (m%scale) + "e+" + e`,
    so the mantissa must already carry the fractional digits.
    """

    if value is None or value == 0 or not math.isfinite(float(value)):
        return 0, 0
    v = abs(float(value))
    exp = int(math.floor(math.log10(v)))
    mant = int(round(v / (10.0 ** exp) * scale))
    if mant >= 10 * scale:
        mant //= 10
        exp += 1
    return mant, exp


# --------------------------------------------------------------------------
# Point source
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PointReading:
    """One scan point, already converted to physical units."""

    index: int
    voltage_mv: float
    reverse_voltage_mv: Optional[float] = None
    sheet_resistance_ohm_sq: Optional[float] = None
    resistivity_ohm_cm: Optional[float] = None
    doping_cm3: Optional[float] = None


class PointSource(Protocol):
    """Produces one :class:`PointReading` per point, in order 1..N."""

    def begin(self, mode: MeasurementMode, config) -> None: ...
    def read_point(self, index: int) -> PointReading: ...
    def end(self) -> None: ...


class DryRunPointSource:
    """Offline stand-in so the notebooks run without a board.

    Fabricates a slowly varying voltage; Rs/rho/Ndop are filled in by the
    supplied `calculate` callback exactly as they would be on hardware.
    """

    def __init__(self, base_mv: float = 70.4, step_mv: float = 0.6) -> None:
        self._base = base_mv
        self._step = step_mv
        self._begun = False

    def begin(self, mode, config) -> None:
        self._begun = True

    def read_point(self, index: int) -> PointReading:
        if not self._begun:
            raise RuntimeError("begin() was not called")
        return PointReading(index=index, voltage_mv=self._base + self._step * (index - 1))

    def end(self) -> None:
        self._begun = False


# --------------------------------------------------------------------------
# Writer
# --------------------------------------------------------------------------
class MultiPointWriter:
    """Streams per-point values into the HMI and releases the wait page."""

    def __init__(self, writer: Hmi22Writer) -> None:
        self._w = writer

    def _val(self, page: str, control: str, value) -> None:
        """Write a 虚拟浮点数.  Scale must be 10 ** that control's vvs1."""

        self._w._val("%s.%s" % (page, control), int(value))

    def _txt(self, page: str, control: str, value) -> None:
        """Write a **text** control -- the 角标 exponent beside a mantissa.

        The 角标 controls are text, so they need ``.txt="N"``.  Sending
        ``.val=N`` to a text control is accepted by the parser but never
        updates the label, so the exponent silently keeps its old value.
        """

        self._w._uart.send_command(
            '%s.%s.txt="%d"' % (page, control, int(value)))

    def write_point(self, mode: MeasurementMode, family: str,
                    reading: PointReading) -> None:
        """Write one point as soon as its ADC window closes.

        Called once per point so the operator watches rows fill in one at a
        time instead of waiting ~6 minutes for a silent scan.
        """

        index = reading.index
        if mode not in POINT_COUNT or family not in DATA_PAGES[mode]:
            raise ValueError("unsupported mode/family")
        if isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= POINT_COUNT[mode]:
            raise ValueError("point index outside 1..%d" % POINT_COUNT[mode])

        # --- 电压：先定位这个点落在哪个 V 页、哪一行 ---
        for page, fwd, rev in VOLTAGE_PAGES[mode]:
            if index <= len(fwd):
                self._val(page, fwd[index - 1],
                          round((reading.voltage_mv or 0.0) * V_FORWARD_SCALE))
                self._val(page, rev[index - 1],
                          0 if reading.reverse_voltage_mv is None else round(reading.reverse_voltage_mv * V_REVERSE_SCALE))
                break
            index -= len(fwd)
        else:
            raise ValueError("no voltage page owns point %d" % reading.index)

        index = reading.index

        # --- 方块电阻 / 电阻率 / 掺杂浓度 ---
        for page in DATA_PAGES[mode][family]:
            if not page.owns(index):
                continue
            row = index - page.first_point
            rs_m, rs_e = split_scientific(reading.sheet_resistance_ohm_sq, RS_SCALE)
            self._val(page.name, page.rs[row], rs_m)
            self._txt(page.name, page.rs_exp[row], rs_e)
            rho_m, rho_e = split_scientific(reading.resistivity_ohm_cm, RHO_SCALE)
            self._val(page.name, page.rho[row], rho_m)
            self._txt(page.name, page.rho_exp[row], rho_e)
            if page.ndop:
                nd_m, nd_e = split_scientific(reading.doping_cm3, NDOP_SCALE)
                self._val(page.name, page.ndop[row], nd_m)
                self._txt(page.name, page.ndop_exp[row], nd_e)
            break
        else:
            raise ValueError("no data page owns point %d" % index)

    def clear_table(self, mode, family):
        for index in range(1,POINT_COUNT[mode]+1):
            self.write_point(mode,family,PointReading(index=index,voltage_mv=0.,reverse_voltage_mv=0.))

    def write_metadata(self, mode, config) -> None:
        from .hmi_single_point import DEFAULT_TEMPERATURE_C, DEFAULT_HUMIDITY_PCT
        family=family_of(config.model_sample_kind)
        fields={"x20":round(config.current_ma*100),"x21":0,
            "x22":round(DEFAULT_TEMPERATURE_C*10),"x23":round(DEFAULT_HUMIDITY_PCT*10),
            "x24":round(config.thickness_um*100),"x25":round(config.probe_spacing_mm*10),
            "x26":round(config.diameter_mm*10),"x27":1 if config.polarity.upper()=="N" else 0}
        pages=[p.name for p in DATA_PAGES[mode][family]]+[p for p,_,_ in VOLTAGE_PAGES[mode]]
        for page in pages:
            for control,value in fields.items():self._val(page,control,value)
        self._w._val("page1.x85",{"hemt":1,"algan":2,"silicon":3}[config.model_sample_kind.value])

    def begin(self, *, early_release=True) -> None:
        """Clear the completion flag before the first point."""

        self._w.clear_done_flag(early_release=early_release)

    def finish(self, last: PointReading, *, summary=None) -> None:
        """Publish the summary values and release 正在测量.

        `summary` is a :class:`hmi_single_point.SinglePointResult` built from the
        last point when the caller wants the 综合数据页 updated too.
        """

        if summary is not None:
            self._w.write_result(summary)
        else:
            self._w.release_wait_page()
