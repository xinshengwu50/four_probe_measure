# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Open-loop fast stop on the pilot sweep (2026-10-17). Offline, no board access.

Pilot voltages are the recorded `range_selection` values of real runs:
  * 202139  50 nm HEMT, no current through the sample      -> must stop
  * 133009  silicon run with an open loop (old history)     -> must stop
  * 133004 / 133018 / 133251  normal silicon scans          -> must NOT stop
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from four_probe_sw.direct_adc_measurement import MeasurementAbortedError
import four_probe_sw.final_four_probe_system as fs
from four_probe_sw.final_four_probe_system import (
    FinalFourProbeSystem,
    OpenCurrentLoopError,
    open_current_loop_diagnosis,
)

CURRENT_A = (106.7675194836567e-6, 949.6196325972225e-6,
             8.955403978230587e-3, 86.57217119232472e-3)


def pilot(*readings):
    """readings: (range_index, filtered_voltage_v, valid_samples)."""
    return tuple(
        SimpleNamespace(range_index=r, current_a=CURRENT_A[r], filtered_probe_voltage_v=v,
                        capture=SimpleNamespace(valid_sample_count=n), eligible=True,
                        resistance_ohm=v / CURRENT_A[r], reason='eligible')
        for r, v, n in readings)


HEMT_202139 = pilot((0, -0.0056412280289926025, 9524), (1, -0.0063452391543645055, 9524),
                    (2, -0.0068282877094962835, 9524))
OPEN_133009 = pilot((0, -0.008766228028993314, 9524), (1, -0.009470239154365215, 9524),
                    (2, -0.010265787709497598, 9524), (3, -0.009375000000000355, 9524))
SI_133004 = pilot((0, 0.0, 0), (1, -0.004470239154364434, 31),
                  (2, 0.06160921229050276, 9524), (3, 0.06562500000000071, 9523))
SI_133018 = pilot((0, 0.0, 0), (1, 0.0, 0), (2, 0.045359212290503326, 9524),
                  (3, 0.04812500000000064, 9524))
SI_133251 = pilot((0, -0.009391228028992745, 9524), (1, 0.008029760845634856, 9524),
                  (2, 0.057234212290503184, 9524), (3, 0.0625, 9524))


class DiagnosisTests(unittest.TestCase):
    def test_hemt_run_without_current_is_stopped(self):
        text = open_current_loop_diagnosis(HEMT_202139)
        self.assertIsNotNone(text)
        self.assertIn('open current loop', text)
        self.assertIn('current x84', text)
        self.assertIn('R2 8.955 mA: -6.828 mV', text)

    def test_old_open_loop_history_is_stopped(self):
        self.assertIsNotNone(open_current_loop_diagnosis(OPEN_133009))

    def test_normal_silicon_scans_pass(self):
        for name, candidates in (('133004', SI_133004), ('133018', SI_133018),
                                 ('133251', SI_133251)):
            with self.subTest(run=name):
                self.assertIsNone(open_current_loop_diagnosis(candidates))

    def test_no_verdict_without_a_current_span(self):
        self.assertIsNone(open_current_loop_diagnosis(HEMT_202139[2:]))          # one range
        self.assertIsNone(open_current_loop_diagnosis(()))
        close = pilot((1, -0.006, 9524), (1, -0.0061, 9524))                     # same current
        self.assertIsNone(open_current_loop_diagnosis(close))

    def test_ranges_without_samples_or_nan_are_ignored(self):
        mixed = pilot((0, -0.0056, 9524), (1, float('nan'), 9524), (2, -0.0068, 0))
        self.assertIsNone(open_current_loop_diagnosis(mixed))  # only R0 left -> no verdict

    def test_voltage_that_follows_current_is_not_flagged(self):
        # small but real: grows 9x from R1 to R2 while staying under 15 mV
        weak = pilot((1, 0.0012, 9524), (2, 0.0110, 9524))
        self.assertIsNone(open_current_loop_diagnosis(weak))


def _system(**overrides):
    kwargs = dict(
        forward_current_by_range_a=CURRENT_A, reverse_current_by_range_a=CURRENT_A,
        probe_voltage_offset_by_range_v=(0.0, 0.0, 0.0, 0.0),
        allow_unverified_deploy=True, r_home_to_center_steps=8000, r_ring_spacing_steps=3500,
        r_max_steps=40000, x_pulses_per_rev=12000, full_down_steps=7600, half_up_steps=3800,
        z_timeout_s=20.0, r_timeout_s=20.0, x_timeout_s=10.0, z_run_step_cycles=6000,
        z_end_step_cycles=96000, z_decel_window_steps=500, z_decel_seg_steps=31,
        z_decel_segments=16, z_rehome_interval_points=5, range_indices=(0, 1, 2),
        measurement_retry_count=2, measurement_retry_delay_s=0.0)
    kwargs.update(overrides)
    frontend = SimpleNamespace(safe_off=lambda: {'current_active': False},
                               reconfigure_adc=lambda timeout_s=None: 1)
    return FinalFourProbeSystem(object(), frontend, object(), lambda **kw: None, 'hemt',
                                is_n_type=True, diameter_mm=50.0, thickness_um=0.05,
                                probe_spacing_mm=1.0, **kwargs)


class ScanIntegrationTests(unittest.TestCase):
    def test_stop_is_not_a_reset(self):
        # MeasurementAbortedError holds the axes (probe stays down); this must not.
        self.assertTrue(issubclass(OpenCurrentLoopError, fs.FinalSystemError))
        self.assertFalse(issubclass(OpenCurrentLoopError, MeasurementAbortedError))

    def test_first_point_stops_without_retry_or_measurement(self):
        system = _system()
        point = system.build_scan_plan(25)[0]
        pilots, measured = [], []

        def fake_pilot(frontend, monitor, **kwargs):
            pilots.append(1)
            return HEMT_202139[2], HEMT_202139

        def fake_measure(*args, **kwargs):
            measured.append(1)
            raise AssertionError('must not measure after an open-loop pilot')

        with patch.object(fs, 'select_current_range', fake_pilot):
            with patch.object(fs, 'measure_bidirectional', fake_measure):
                with self.assertRaises(OpenCurrentLoopError) as ctx:
                    system._measure_point(point, first_point=True)
        self.assertEqual(pilots, [1])        # one pilot, no retry
        self.assertEqual(measured, [])       # never reached the pair / PL
        self.assertIn('Scan stopped before point 1', str(ctx.exception))

    def test_normal_pilot_still_measures(self):
        system = _system(range_indices=(0, 1, 2, 3))
        point = system.build_scan_plan(25)[0]
        measured = []

        def fake_pilot(frontend, monitor, **kwargs):
            return SI_133251[2], SI_133251

        def fake_measure(frontend, monitor, range_index, **kwargs):
            measured.append(int(range_index))
            raise fs.DirectMeasurementError('stop here: past the guard')

        with patch.object(fs, 'select_current_range', fake_pilot):
            with patch.object(fs, 'measure_bidirectional', fake_measure):
                record = system._measure_point(point, first_point=True)
        self.assertTrue(measured)            # the guard let it through to the pair
        self.assertFalse(record['point_valid'])


if __name__ == '__main__':
    unittest.main()
