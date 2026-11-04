# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Manual mechanical-only recovery. No sample factory, ADC, render, Overlay or UART TX."""
from hmi_emergency import stop_before_overlay
from four_probe_sw.final_four_probe_system import FinalFourProbeSystem, MeasurementAbortedError, EXPECTED_PL_VERSION, REG_VERSION, REG_STATUS, REG_R_STATUS, REG_Z_STATUS, REG_X_STATUS, REG_Z_POSITION, REG_R_POSITION
HMI_RECOVERY_VERSION = 1

def _unavailable(*args, **kwargs):
    raise RuntimeError('Mechanical recovery cannot scan, sample, calculate, save results or move to a target')

class MechanicalRecoveryController(FinalFourProbeSystem):
    """Reuse validated core HOME/heartbeat/fault code without measurement configuration.

    Geometry zeros/None material are unused placeholders, never a measured sample.
    Construction is write-free. All actual motion needs manual_clear_and_rehome.
    """

    def __init__(self, mmio, frontend, **mechanics):
        self._recovery_active = False
        self._recovery_guard = None
        super().__init__(mmio, frontend, None, _unavailable, None, is_n_type=False, diameter_mm=0.0, thickness_um=0.0, probe_spacing_mm=0.0, allow_motion=False, use_pl_calc=False, use_pl_window_stats=False, pl_autorange=None, range_indices=(0,), sample_label='MECHANICAL_RECOVERY_ONLY', forward_current_by_range_a=(0.0,) * 4, reverse_current_by_range_a=(0.0,) * 4, probe_voltage_offset_by_range_v=(0.0,) * 4, **mechanics)
    run_scan = _unavailable
    preflight = _unavailable
    _measure_point = _unavailable
    save_results = _unavailable
    axis_move_to = _unavailable
    x_rotate_pulses = _unavailable

    def _require_active(self):
        if not self._recovery_active:
            raise PermissionError('Use manually confirmed manual_clear_and_rehome, not individual axis commands')

    def clear_faults(self):
        self._require_active()
        return super().clear_faults()

    def axis_home(self, *args, **kwargs):
        self._require_active()
        return super().axis_home(*args, **kwargs)

    def rehome(self):
        self._require_active()
        return super().rehome()

    def _raise_if_measurement_aborted(self):
        super()._raise_if_measurement_aborted()
        if self._recovery_guard is not None:
            self._recovery_guard()

def manual_clear_and_rehome(controller, uart, emergency, *, confirmed=False, previous_systems=(), pl_autorange=None):
    """Explicit clear+ZHOME+RHOME; retain unique RX/RST, never move X or download bit.

    New RST/RX failure at any stage refuses completion. After CLEAR/HOME failure,
    request actual SYSTEM_RESET to hold axes/torque/current-off; no automatic retry.
    """
    if confirmed is not True:
        raise PermissionError('Manual fixture/limits/current-off confirmation required')
    if not isinstance(controller, MechanicalRecoveryController):
        raise TypeError('A mechanical-only recovery controller is required')
    if emergency.mmio is not controller.mmio:
        raise RuntimeError('Recovery and RST must address the same controller MMIO')
    if getattr(uart.rx_transform, '__self__', None) is not emergency:
        raise RuntimeError('Restore original emergency RX route; end image/capture sessions first')
    epoch = emergency.count

    def check_rx():
        thread = uart._rx_thread
        stopping = getattr(uart, '_rx_stop', None)
        if getattr(uart.rx_transform, '__self__', None) is not emergency or (stopping is not None and stopping.is_set()) or uart.rx_fatal_error or (thread is None) or (not thread.is_alive()):
            raise RuntimeError('UART RX not healthy; no fault clearing or recovery motion allowed')
        if emergency.count != epoch:
            raise MeasurementAbortedError('New RST arrived during manual recovery')

    def check_idle_off():
        if any((controller._read(reg) & 1 for reg in (REG_R_STATUS, REG_Z_STATUS, REG_X_STATUS))):
            raise RuntimeError('Axis still busy; manual recovery refused')
        if controller.frontend.status().get('current_active', True):
            raise RuntimeError('Current not confirmed OFF; manual recovery refused')
    if uart.rx_fatal_error:
        raise RuntimeError('Diagnose fatal RX error before manual recovery')
    uart.start_receiving(poll_s=0.0002)
    check_rx()
    if controller._read(REG_VERSION) != EXPECTED_PL_VERSION:
        raise RuntimeError('Wrong loaded controller VERSION; no recovery writes performed')
    check_idle_off()
    stop_before_overlay(uart=None, systems=tuple(previous_systems) + (controller,))
    check_rx()
    if not uart.lock.acquire(blocking=False):
        raise RuntimeError('UART TX owned by another session; RX retained, recovery refused')
    changed = False
    try:
        driver = pl_autorange
        if driver is None:
            for previous in previous_systems:
                if previous is not None and getattr(previous, 'mmio', None) is controller.mmio:
                    driver = getattr(previous, 'pl_autorange', None)
                    if driver is not None:
                        break
        if driver is not None:
            driver.abort()
            driver.wait_idle()
            driver.release()
        check_rx()
        check_idle_off()
        if emergency.buffer:
            raise RuntimeError('Partial screen frame/RST pending; wait for RX completion, do not discard it')
        controller._recovery_guard = check_rx
        controller._recovery_active = True
        changed = True
        controller.clear_faults()
        controller._raise_if_measurement_aborted()
        controller.rehome()
        controller._raise_if_measurement_aborted()
        check_idle_off()
        if controller.heartbeat_is_running():
            raise RuntimeError('Recovery heartbeat did not stop; refuse completion')
        if controller._read(REG_Z_POSITION) != 0 or controller._read(REG_R_POSITION) != 0:
            raise RuntimeError('Z/R position not zero after HOME')
        check_rx()
        emergency.stopped.clear()
        controller._raise_if_measurement_aborted()
        uart.discard_pending_rx()
        return controller
    except BaseException:
        if changed:
            emergency.request('manual recovery failed; axes held for inspection')
        raise
    finally:
        controller._recovery_active = False
        controller._recovery_guard = None
        uart.lock.release()
