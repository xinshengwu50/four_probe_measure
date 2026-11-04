# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Incremental START/history protocol and validated result-page rendering; no synthetic measurement service."""
from dataclasses import dataclass
from typing import Optional
from four_all_hmi_ui.hmi_single_point import MeasurementMode, SampleKind, SinglePointResult, Hmi22Writer, parse_22hmi_config
from four_all_hmi_ui.hmi_points_scan import MultiPointWriter, family_of, DATA_PAGES, VOLTAGE_PAGES
from four_all_hmi_ui.hmi_address import numeric_command, PAGE_IDS
from four_all_hmi_ui.hmi_wire import config_frame_length
from four_all_hmi_ui.hmi_bindings import write_current_display
HISTORY_PREFIX = b'\xa5HIST'
REPORT_PREFIX = b'\xa5RPRT'
CLEAR_PREFIX = b'\xa5CLER'
HISTORY_SLOTS = 4

@dataclass(frozen=True)
class HistoryPoint:
    index: int
    voltage_mv: float
    reverse_voltage_mv: float
    equivalent_mv: float
    sheet_resistance_ohm_sq: float
    resistivity_ohm_cm: float
    doping_cm3: Optional[float]

def _indices(config):
    if config.measurement_mode == MeasurementMode.SINGLE_POINT:
        return [config.point_index]
    return list(range(1, 26 if config.measurement_mode == MeasurementMode.TWENTY_FIVE_POINT else 10))

class HistoryWireParser:

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        events = []
        while self.buffer:
            if self.buffer[0] == 170:
                length = config_frame_length(self.buffer)
                if length is None:
                    break
                if length == 0:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < length:
                    break
                frame = bytes(self.buffer[:length])
                try:
                    event = parse_22hmi_config(frame)
                except ValueError:
                    del self.buffer[0]
                    continue
                del self.buffer[:length]
                events.append(event)
            elif self.buffer[0] == 165:
                if len(self.buffer) < 7:
                    break
                packet = bytes(self.buffer[:7])
                prefix = packet[:5]
                slot = packet[5]
                if packet[-1] == 90 and prefix in (HISTORY_PREFIX, REPORT_PREFIX, CLEAR_PREFIX):
                    del self.buffer[:7]
                    if prefix == CLEAR_PREFIX and slot == 0:
                        events.append(('clear', 0))
                    elif prefix != CLEAR_PREFIX and slot:
                        events.append(('history' if prefix == HISTORY_PREFIX else 'report', slot))
                else:
                    del self.buffer[0]
            else:
                del self.buffer[0]
        if len(self.buffer) > 4096:
            self.buffer.clear()
            raise ValueError('wire buffer overflow')
        return events

class _Buffer:

    def __init__(self):
        self.commands = []

    def send_command(self, text):
        self.commands.append(numeric_command(text))

class _HistoryWriter(Hmi22Writer):

    def release_wait_page(self):
        return

    def _val(self, target, value):
        value = int(value)
        if not 0 <= value <= 2147483647:
            raise ValueError('value outside demo HMI range: ' + target)
        super()._val(target, value)

def _result(snapshot):
    cfg = snapshot.config
    r = snapshot.rows[-1]
    return SinglePointResult(config=cfg, voltage_mv=r.equivalent_mv, resistivity_ohm_cm=r.resistivity_ohm_cm, sheet_resistance_ohm_sq=r.sheet_resistance_ohm_sq, doping_cm3=r.doping_cm3, alpha=snapshot.alpha, diameter_over_spacing=snapshot.diameter_over_spacing, fd=snapshot.fd, fw=snapshot.fw, fsp=snapshot.fsp, quality_flags=(), point_index=r.index, forward_voltage_mv=r.voltage_mv, reverse_voltage_mv=r.reverse_voltage_mv, equivalent_current_ma=cfg.current_ma, resistance_ohm=r.equivalent_mv / cfg.current_ma)

def _data_page(config):
    if config.measurement_mode == MeasurementMode.SINGLE_POINT:
        return 22 if config.model_sample_kind == SampleKind.SILICON else 23
    return PAGE_IDS[DATA_PAGES[config.measurement_mode][family_of(config.model_sample_kind)][0].name]

def _drop_overwritten(commands):
    out = []
    segment = {}
    for command in commands:
        target, eq, _ = command.partition('=')
        if not eq:
            out.extend(segment.values())
            out.append(command)
            segment = {}
            continue
        segment.pop(target, None)
        segment[target] = command
    out.extend(segment.values())
    return out

def _render_commands(snapshot, report=False, *, validator, writer_class=_HistoryWriter):
    validator(snapshot)
    cfg = snapshot.config
    buffer = _Buffer()
    writer = writer_class(buffer)
    points = MultiPointWriter(writer)
    if not report:
        buffer.send_command('page %d' % _data_page(cfg))
    writer.write_result(_result(snapshot), include_point=False)
    for target, value in [('page0.x4', round(cfg.thickness_um * 100)), ('page0.x6', round(cfg.diameter_mm * 10)), ('page0.x7', 1 if cfg.polarity.upper() == 'N' else 0), ('page0.x2', round(snapshot.temperature_c * 10)), ('page0.x3', round(snapshot.humidity_pct * 10)), ('page1.x85', {'hemt': 1, 'algan': 2, 'silicon': 3}[cfg.model_sample_kind.value])]:
        writer._val(target, value)
    if cfg.measurement_mode == MeasurementMode.SINGLE_POINT:
        writer.write_point_result(_result(snapshot))
        pages = ['单点非三' if cfg.model_sample_kind == SampleKind.SILICON else '单点三代', 'V1']
    else:
        points.write_metadata(cfg.measurement_mode, cfg)
        for row in snapshot.rows:
            points.write_point(cfg.measurement_mode, family_of(cfg.model_sample_kind), row)
        pages = [p.name for p in DATA_PAGES[cfg.measurement_mode][family_of(cfg.model_sample_kind)]] + [p for p, _, _ in VOLTAGE_PAGES[cfg.measurement_mode]]
    for page in pages:
        for control, value in [('x20', round(cfg.current_ma * 100)), ('x21', round(snapshot.rows[-1].equivalent_mv * 10)), ('x22', round(snapshot.temperature_c * 10)), ('x23', round(snapshot.humidity_pct * 10))]:
            writer._val(page + '.' + control, value)
    raw_rows = getattr(snapshot, 'raw_rows', ())
    row_ranges = {row.get('range_index') for row in raw_rows if isinstance(row, dict)}
    multi_range = len(row_ranges) > 1
    write_current_display(buffer, cfg.current_ma, pending=multi_range)
    if report:
        buffer.send_command('page 8')
    return _drop_overwritten(buffer.commands)
