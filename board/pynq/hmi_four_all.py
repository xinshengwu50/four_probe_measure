# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

'HMI11: real single/9/25-point scans and completeCSVhistory. RANGE_READY navigates after actualselection, not after a timer. No separate display gain, rendering worker or alternative measurement service.'
from dataclasses import replace, asdict
import json
import time
from pathlib import Path
from hmi_real_heatmap import RealHeatmap
from four_probe_sw.measurement_quality import validate_sample_label
import math
from four_all_hmi_ui.hmi_single_point import Hmi22ConfigParser, Hmi22Writer, MeasurementConfig, MeasurementMode, SampleKind, SinglePointResult, QualityFlag
from four_all_hmi_ui.hmi_points_scan import MultiPointWriter, PointReading, DATA_PAGES, VOLTAGE_PAGES, family_of
from four_all_hmi_ui.hmi_bindings import nominal_range_ma, write_current_display, write_sample_metadata
from hmi_real_history import RealHistoryStore
from hmi_history_protocol import HistoryWireParser
from four_probe_sw.final_four_probe_system import FinalFourProbeSystem
from four_probe_sw.multi_material_model import SampleType, calculate_four_probe
FOUR_ALL_HMI_VERSION = 11
FORWARD_CURRENT_BY_RANGE_A = (0.0001067675194836567, 0.0009496196325972225, 0.008955403978230587, 0.08657217119232472)
REVERSE_CURRENT_BY_RANGE_A = (0.00010153005040316653, 0.0008840039433859044, 0.008277879981034422, 0.08088461584683777)

def make_system_factory(mmio, frontend, monitor, **settings):
    """Use the source orchestrator and model in an isolated package namespace."""
    from four_probe_sw.direct_adc_measurement import DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V
    profile = dict(range_selection_sample_count=100, valid_sample_count=1000, sample_interval_s=0.002, discard_first=20, range_settle_s=3.0, bidirectional_settle_s=3.0, adc_config_settle_s=0.5, capture_timeout_s=10.0, adc_input_min_v=0.005, adc_input_max_v=5.0, probe_abs_min_v=0.005, probe_abs_max_v=2.0, probe_voltage_offset_by_range_v=DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V, select_range_by_resistivity=True, use_pl_window_stats=True, pl_stats_timeout_s=0.1, pl_stats_min_valid_samples=100, r_home_to_center_steps=8000, r_ring_spacing_steps=3500, r_max_steps=40000, x_pulses_per_rev=12000, full_down_steps=7600, half_up_steps=3800, z_timeout_s=20.0, r_timeout_s=20.0, x_timeout_s=10.0, z_run_step_cycles=6000, z_end_step_cycles=96000, z_decel_window_steps=500, z_decel_seg_steps=31, z_decel_segments=16, z_rehome_interval_points=5, motion_trace=True)
    profile.update(use_pl_calc=True, pl_rho_tolerance=0.0001, range_indices=(0, 1, 2), zero_offset_samples=0, pl_window_abs_min_v=0.0, pilot_bipolar=True, check_current_path=True)
    down_by_material = settings.pop('full_down_steps_by_material', {'silicon': 7450, 'algan': 7600, 'hemt': 7600, 'gan': 7600})
    allow_100ma = bool(settings.pop('allow_100ma', False))
    profile.update(settings)
    if 3 in profile['range_indices'] and (not allow_100ma):
        raise PermissionError('R3/100mA requires explicit authorization; AMD_T defaults exclude it')

    def validate_request(config):
        config.validate()
        return None

    def factory(config, **callbacks):
        validated_down = validate_request(config)
        if config.sample_kind.value == 'aln':
            raise ValueError('AlN模型未确认，禁止真实测量')
        run_profile = dict(profile)
        run_profile['sample_label'] = config.sample_label or run_profile.get('sample_label', '') or ('GaN' if config.sample_kind is SampleKind.GAN else '')
        if config.current_mode not in (None, 0):
            forced = config.current_mode - 1
            if forced == 3 and (not allow_100ma):
                raise PermissionError('手动100mA需要独立授权')
            if forced not in profile['range_indices']:
                raise PermissionError('手动量程不在允许列表')
            run_profile.update(range_indices=(forced,), select_range_by_resistivity=False)

        def configured_model(**kwargs):
            return calculate_four_probe(sample_structure=config.sample_structure, **kwargs)
        if down_by_material is not None:
            down = int(down_by_material[config.sample_kind.value])
            run_profile.update(full_down_steps=down, half_up_steps=down // 2)
        return FinalFourProbeSystem(mmio, frontend, monitor, configured_model, SampleType(config.model_sample_kind.value), is_n_type=config.polarity.upper() == 'N', diameter_mm=config.diameter_mm, thickness_um=config.thickness_um, probe_spacing_mm=config.probe_spacing_mm, forward_current_by_range_a=FORWARD_CURRENT_BY_RANGE_A, reverse_current_by_range_a=REVERSE_CURRENT_BY_RANGE_A, allow_motion=True, **run_profile, **callbacks)
    factory.validate_request = validate_request
    return factory

class FourAllHmiService:

    def __init__(self, uart, frontend, system_factory, *, allow_motion=False, arm_current=False, allow_100ma=False, geometry_confirmed=False, r_steps_per_mm=800.0, r_ring_spacing_steps=1600, probe_margin_mm=1.5, emergency=None, enabled_ranges=(0, 1, 2), output_dir='four_all_results', trace=True, sample_label=''):
        self.sample_label = validate_sample_label(sample_label)
        self.emergency = emergency
        self.uart = uart
        self.heatmap = RealHeatmap(uart, abort_check=self._check_heatmap_reset)
        self.rho_heatmap = RealHeatmap(uart, abort_check=self._check_heatmap_reset, page='p[27]')
        self.frontend = frontend
        self.system_factory = system_factory
        self.allow_motion = bool(allow_motion)
        self.arm_current = bool(arm_current)
        self.allow_100ma = bool(allow_100ma)
        self.enabled_ranges = tuple(enabled_ranges)
        if not self.enabled_ranges or any((isinstance(i, bool) or i not in range(4) for i in self.enabled_ranges)):
            raise ValueError('enabled_ranges must contain valid0..3 range indices')
        self.geometry_confirmed = bool(geometry_confirmed)
        self.r_steps_per_mm = float(r_steps_per_mm)
        self.r_ring_spacing_steps = int(r_ring_spacing_steps)
        self.probe_margin_mm = float(probe_margin_mm)
        if not math.isfinite(self.r_steps_per_mm) or self.r_steps_per_mm <= 0:
            raise ValueError('invalid radial calibration')
        if self.r_ring_spacing_steps <= 0 or not math.isfinite(self.probe_margin_mm) or self.probe_margin_mm < 0:
            raise ValueError('invalid ring spacing/probe margin')
        self.output_dir = Path(output_dir)
        self.history = RealHistoryStore(self.output_dir / 'history')
        self.trace = bool(trace)
        self.parser = HistoryWireParser()
        self.writer = Hmi22Writer(uart)
        self.points = MultiPointWriter(self.writer)
        self.system = None
        self.points_completed = 0
        self.range_ready = False
        self.last_result = None
        self.request_config = None
        self.selected_range_index = None

    def _check_heatmap_reset(self):
        if self.emergency is not None and self.emergency.stopped.is_set():
            raise RuntimeError('SYSTEM_RESET: heatmap transmission aborted')

    def _log(self, *args):
        if self.trace:
            print('[FOUR_ALL_HMI]', *args, flush=True)

    def _validate(self, config):
        config.validate()
        if config.sample_kind.value == 'aln':
            directory = self.output_dir / 'requests'
            directory.mkdir(parents=True, exist_ok=True)
            receipt = dict(status='REJECTED', reason='AlN模型未确认，禁止真实测量', config=asdict(config))
            (directory / ('aln_' + str(time.time_ns()) + '.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
            raise ValueError(receipt['reason'])
        if config.current_mode not in (None, 0):
            forced = config.current_mode - 1
            if forced == 3 and (not self.allow_100ma):
                raise PermissionError('手动100mA需要独立授权')
            if forced not in self.enabled_ranges:
                raise PermissionError('手动量程未在允许列表中启用')
        if self.emergency is not None and self.emergency.stopped.is_set():
            raise PermissionError('Reset latched: manual clear and rehome required')
        if config.measurement_mode not in (MeasurementMode.SINGLE_POINT, MeasurementMode.TWENTY_FIVE_POINT, MeasurementMode.NINE_POINT):
            raise ValueError('unsupported screen measurement mode')
        if 3 in self.enabled_ranges and (not self.allow_100ma):
            raise PermissionError('100mA/R3 requires separate authorization')
        if not all((self.allow_motion, self.arm_current, self.geometry_confirmed)):
            raise PermissionError('locked: confirm motion/current and half-lift geometry; R3 is separately blocked by factory')
        if config.measurement_mode == MeasurementMode.SINGLE_POINT:
            rings = 0 if config.point_index == 1 else 1 if config.point_index <= 9 else 2
        else:
            rings = 2 if config.measurement_mode == MeasurementMode.TWENTY_FIVE_POINT else 1
        radius = rings * self.r_ring_spacing_steps / self.r_steps_per_mm
        if radius + self.probe_margin_mm >= config.diameter_mm / 2:
            raise ValueError('outer ring plus probe margin exceeds sample radius')
        checker = getattr(self.system_factory, '__dict__', {}).get('validate_request')
        if checker is not None:
            checker(config)

    def _display_config(self, config):
        return replace(config, current_ma=nominal_range_ma(self.selected_range_index) if self.selected_range_index is not None else config.current_ma or 0.0)

    def _display_result(self, result):
        return replace(result, config=self._display_config(result.config), equivalent_current_ma=nominal_range_ma(self.selected_range_index), forward_voltage_mv=self._display_voltage(result.forward_voltage_mv, False), reverse_voltage_mv=self._display_voltage(result.reverse_voltage_mv, True))

    def _display_voltage(self, value, reverse):
        return value

    def _write_metadata(self, config):
        write_sample_metadata(self.uart, config)
        config = self._display_config(config)
        if config.measurement_mode == MeasurementMode.SINGLE_POINT:
            self.writer.write_point_result(SinglePointResult(config=config, point_index=config.point_index, equivalent_current_ma=config.current_ma, voltage_mv=0.0, resistivity_ohm_cm=None, sheet_resistance_ohm_sq=None, doping_cm3=None, alpha=None, diameter_over_spacing=None, fd=None, fw=None, fsp=None, quality_flags=()))
            self.writer._val('page1.x85', {'hemt': 1, 'algan': 2, 'silicon': 3}[config.model_sample_kind.value])
        else:
            self.points.write_metadata(config.measurement_mode, config)

    def _range_selected(self, index, forward_a, reverse_a):
        navigate = not self.range_ready
        if index not in range(4) or not all((math.isfinite(float(v)) and float(v) > 0 for v in (forward_a, reverse_a))):
            raise ValueError('invalid selected range/current')
        actual_ma = 500.0 * (float(forward_a) + float(reverse_a))
        self.selected_range_index = int(index)
        selected = replace(self.request_config, current_ma=actual_ma)
        self._write_metadata(selected)
        write_current_display(self.uart, nominal_range_ma(index))
        if navigate:
            self.writer.release_wait_page()
        self.range_ready = True
        self._log('RANGE_READY', index, 'If/Ir mA=', forward_a * 1000, reverse_a * 1000, 'n0=1 is navigation, NOT whole-scan completion')

    def _publish(self, row):
        row.update(sample_label=self.request_config.sample_label, requested_material=self.request_config.sample_kind.value, requested_current_mode=self.request_config.current_mode, sample_structure=self.request_config.sample_structure)
        if not self.range_ready and row.get('point_valid'):
            raise RuntimeError('point arrived before automatic range selection')
        single = self.request_config.measurement_mode == MeasurementMode.SINGLE_POINT
        count = 1 if single else 25 if self.request_config.measurement_mode == MeasurementMode.TWENTY_FIVE_POINT else 9
        ring = row['ring']
        within_ring = row['point_index']
        if any((isinstance(v, bool) or not isinstance(v, int) for v in (ring, within_ring))):
            raise RuntimeError('invalid ring/point index')
        if ring == 0 and within_ring == 0:
            index = 1
        elif ring in (1, 2) and 0 <= within_ring < 8 * ring:
            index = 2 + within_ring if ring == 1 else 10 + within_ring
        else:
            raise RuntimeError('invalid ring/point index')
        if single:
            if self.points_completed != 0 or index != self.request_config.point_index:
                raise RuntimeError('duplicate/wrong selected single point')
        elif index != self.points_completed + 1 or index > count:
            raise RuntimeError('duplicate/out-of-order point')
        self.heatmap.update(index, row.get('sheet_resistance_ohm_sq'), valid=row.get('point_valid') is True)
        self.rho_heatmap.update(index, row.get('resistivity_ohm_cm'), valid=row.get('point_valid') is True)
        if not row['point_valid']:
            reading = PointReading(index, None, None, None, None, None)
            if not single:
                self.points.write_point(self.request_config.measurement_mode, family_of(self.request_config.model_sample_kind), reading)
            self.points_completed = 1 if single else index
            self._log('INVALID point', index, 'saved null; not a valid measurement')
            return
        for key in ('forward_voltage_v', 'reverse_voltage_v', 'combined_voltage_v', 'equivalent_current_a'):
            if not math.isfinite(float(row[key])):
                raise ValueError('non-finite ' + key)
        if row['equivalent_current_a'] <= 0:
            raise ValueError('invalid equivalent current')
        current_ma = row['equivalent_current_a'] * 1000
        cfg = replace(self.request_config, current_ma=current_ma, point_index=index)
        reading = PointReading(index, row['forward_voltage_v'] * 1000, row['reverse_voltage_v'] * 1000, row['sheet_resistance_ohm_sq'], row['resistivity_ohm_cm'], row['ndop_cm3'])
        self.last_result = SinglePointResult(config=cfg, voltage_mv=row['combined_voltage_v'] * 1000, forward_voltage_mv=reading.voltage_mv, reverse_voltage_mv=reading.reverse_voltage_mv, equivalent_current_ma=current_ma, forward_current_ma=row['forward_current_a'] * 1000, reverse_current_ma=row['reverse_current_a'] * 1000, resistance_ohm=row['combined_resistance_ohm'], sheet_resistance_ohm_sq=row['sheet_resistance_ohm_sq'], resistivity_ohm_cm=row['resistivity_ohm_cm'], doping_cm3=row['ndop_cm3'], alpha=cfg.thickness_um / 1000 / cfg.probe_spacing_mm, diameter_over_spacing=cfg.diameter_mm / cfg.probe_spacing_mm, fd=row['fd'], fw=row['fw'], fsp=row['fsp'], point_index=index, valid_samples=row['forward_valid_samples'] + row['reverse_valid_samples'], quality_flags=())
        if single:
            self.writer.write_point_result(self._display_result(self.last_result))
        else:
            display_reading = replace(reading, voltage_mv=self._display_voltage(reading.voltage_mv, False), reverse_voltage_mv=self._display_voltage(reading.reverse_voltage_mv, True))
            self.points.write_point(cfg.measurement_mode, family_of(cfg.model_sample_kind), display_reading)
            mirror_v = round(row['combined_voltage_v'] * 1000 * 10)
            self.writer._val('page0.x1', mirror_v)
            write_current_display(self.uart, nominal_range_ma(self.selected_range_index))
            pages = [p.name for p in DATA_PAGES[cfg.measurement_mode][family_of(cfg.model_sample_kind)]]
            pages += [p for p, _, _ in VOLTAGE_PAGES[cfg.measurement_mode]]
            for page in pages:
                self.writer._val(page + '.x21', mirror_v)
                self.writer._val(page + '.x20', round(nominal_range_ma(self.selected_range_index) * 100))
        self.points_completed = 1 if single else index
        if self.points_completed == count:
            self.writer.write_result(self._display_result(self.last_result), include_point=False)
            write_current_display(self.uart, nominal_range_ma(self.selected_range_index))
            self._log('page0 report inputs refreshed BEFORE final return/save; scan not yet COMPLETE')
        self._log('point %02d captured; progress %d/%d; sent BEFORE next motion' % (index, self.points_completed, count))

    def run(self, config):
        if self.sample_label:
            config = replace(config, sample_label=self.sample_label)
        elif config.sample_kind is SampleKind.GAN and (not config.sample_label):
            config = replace(config, sample_label='GaN')
        self.frontend.safe_off()
        self.points_completed = 0
        self.range_ready = False
        self.selected_range_index = None
        self.last_result = None
        self.system = None
        self.request_config = config
        self._validate(config)
        self.rho_heatmap.begin()
        self.heatmap.begin()
        mode = {MeasurementMode.SINGLE_POINT: 'single', MeasurementMode.TWENTY_FIVE_POINT: '25', MeasurementMode.NINE_POINT: '9'}[config.measurement_mode]
        try:
            self.system = self.system_factory(config, on_range_selected=self._range_selected, on_point=self._publish)
            if mode == 'single':
                self.writer.clear_done_flag(early_release=False, point_index=config.point_index)
            else:
                self.points.begin(early_release=False)
                self.points.clear_table(config.measurement_mode, family_of(config.model_sample_kind))
            self._write_metadata(replace(config, current_ma=0))
            write_current_display(self.uart, 0.0, pending=True)
            self.writer._val('page0.x1', 0)
            self._log('REAL', mode, 'selected point=', config.point_index, 'source profile: down/up=', getattr(self.system, 'full_down_steps', None), getattr(self.system, 'half_up_steps', None), 'auto range; half-lift; rehome every 5; no fake 2s timer')
            summary = self.system.run_scan(mode, config.point_index) if mode == 'single' else self.system.run_scan(mode)
            self.frontend.safe_off()
            if summary.results:
                json_path, csv_path = self.system.save_results(self.output_dir)
            else:
                json_path = csv_path = None
            expected = 1 if mode == 'single' else int(mode)
            complete = bool(summary.completed and summary.quality_ok and (self.points_completed == expected) and all((r.get('point_valid') for r in summary.results)))
            history_csv_path = None
            if complete:
                history_csv_path = self.history.save_complete(config, summary.results, summary.selected_range_index)
            if complete and self.last_result is not None:
                self.writer.write_result(self._display_result(replace(self.last_result, quality_flags=(QualityFlag.MEASUREMENT_COMPLETE,))), include_point=False)
                write_current_display(self.uart, nominal_range_ma(self.selected_range_index))
            if not complete:
                self._log('FAULT EXIT, not a completed scan; source recovery may return Z/X/R')
            result = dict(status='COMPLETE' if complete else 'ERROR', display_only=False, points_completed=self.points_completed, selected_range_index=summary.selected_range_index, range_ready=self.range_ready, error=summary.error or (None if complete else 'incomplete scan'), csv_path=str(csv_path) if csv_path else None, json_path=str(json_path) if json_path else None, history_csv_path=str(history_csv_path) if history_csv_path else None)
            self._log(result['status'], self.points_completed, 'CSV:', result['csv_path'])
            return result
        except BaseException as exc:
            self.frontend.safe_off()
            if self.system is not None:
                self.system.last_error = str(exc) or type(exc).__name__
                request = getattr(self.system, 'request_system_reset', None)
                if request is not None:
                    request('service exception')
                if self.system.results:
                    try:
                        paths = self.system.save_results(self.output_dir)
                        self._log('partial results saved', paths)
                    except Exception as save_error:
                        self._log('partial save failed', save_error)
            raise
        finally:
            self.frontend.safe_off()
            discard = getattr(self.uart, 'discard_pending_rx', None)
            if discard is not None:
                discard()
            self.parser = HistoryWireParser()

    def poll_once(self):
        errors = self.uart.__dict__.get('rx_error_count', 0)
        if errors != getattr(self, '_parser_rx_errors', errors):
            self.parser = HistoryWireParser()
        self._parser_rx_errors = errors
        events = self.parser.feed(self.uart.read_available())
        results = []
        starts = 0
        for event in events:
            if self.emergency is not None:
                if self.emergency.stopped.is_set() or self.emergency.mmio.read(4) & 196608:
                    break
            check = getattr(self, 'check_display_transport', None)
            error = check() if check is not None else None
            if error:
                results.append(dict(status='IMAGE_COMM_ERROR', display_only=True, error=error))
                continue
            if isinstance(event, MeasurementConfig):
                starts += 1
                if starts > 1:
                    self._log('discarding duplicate queued START frames')
                    continue
                try:
                    results.append(self.run(event))
                except Exception as exc:
                    self._log('ERROR', exc)
                    results.append(dict(status='ERROR', display_only=False, points_completed=self.points_completed, error=str(exc), range_ready=self.range_ready))
            elif event[0] in ('history', 'report'):
                try:
                    results.append(self.history.restore(self.uart, event[1], report=event[0] == 'report'))
                except Exception as exc:
                    self._log('HISTORY_ERROR', exc)
                    results.append(dict(status='HISTORY_ERROR', display_only=True, error=str(exc)))
        return results
