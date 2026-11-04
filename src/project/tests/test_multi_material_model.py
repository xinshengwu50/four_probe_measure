# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Offline checks for four_probe_sw.multi_material_model (no board access).

Reference numbers come from the independent image/spectral solvers in
four_probe_pynq/sw/pynq/four_probe_physics_reference.py and are hard-coded
here so this test runs from the Four_ALL delivery directory alone.
"""

import math
import unittest

from four_probe_sw.multi_material_model import (
    SampleType,
    calculate_four_probe,
    fd_circular_disk,
    fw_from_alpha,
)

# W/S -> exact slab factor (spectral reference, rtol 1e-10).
FW_REFERENCE = {
    0.1: 0.999999999999,
    0.3: 0.999968713472,
    0.5: 0.997362267229,
    0.645: 0.987874933422,
    1.0: 0.921456802884,
    2.0: 0.633656441073,
    5.0: 0.275335186880,
    10.0: 0.138505568754,
}

# Circular column of the reference correction table (Smits), D/S -> FD.
SMITS_CIRCLE = {3.0: 2.2662, 4.0: 2.9289, 5.0: 3.3625, 7.5: 3.9273,
                10.0: 4.1716, 15.0: 4.3646, 20.0: 4.4364, 40.0: 4.5076}


class ThicknessFactorTests(unittest.TestCase):
    def test_matches_exact_slab_reference(self):
        for alpha, expected in FW_REFERENCE.items():
            with self.subTest(alpha=alpha):
                self.assertAlmostEqual(fw_from_alpha(alpha) / expected, 1.0, delta=1e-9)

    def test_project_wafer_value(self):
        # 645 um wafer, 1 mm pitch: legacy code returned the clamp value 1.05.
        self.assertAlmostEqual(fw_from_alpha(0.645), 0.9878749334, delta=1e-9)

    def test_limits_and_no_clamp(self):
        self.assertAlmostEqual(fw_from_alpha(1e-4), 1.0, delta=1e-12)
        self.assertAlmostEqual(fw_from_alpha(1000.0) * 1000.0, 2 * math.log(2), delta=1e-6)
        self.assertLess(fw_from_alpha(2.0), 0.80)  # old clamp floor no longer applies
        self.assertLessEqual(fw_from_alpha(0.645), 1.0)

    def test_monotonic_decreasing(self):
        values = [fw_from_alpha(a / 20.0) for a in range(1, 200)]
        for left, right in zip(values, values[1:]):
            self.assertLessEqual(right, left + 1e-9)  # documented accuracy

    def test_invalid_alpha(self):
        self.assertEqual(fw_from_alpha(0.0), 1.0)
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                fw_from_alpha(bad)


class DiameterFactorTests(unittest.TestCase):
    def test_closed_form_reproduces_table_circle_column(self):
        for ratio, table_value in SMITS_CIRCLE.items():
            if ratio <= 3.0:
                continue
            with self.subTest(ratio=ratio):
                self.assertAlmostEqual(fd_circular_disk(ratio), table_value, delta=6e-4)

    def test_project_wafer_value_and_infinite_limit(self):
        self.assertAlmostEqual(fd_circular_disk(50.0), 4.5167211315, delta=1e-9)
        self.assertAlmostEqual(fd_circular_disk(1e8), math.pi / math.log(2), delta=1e-12)

    def test_requires_probes_inside_disk(self):
        for bad in (3.0, 1.0, float("nan")):
            with self.assertRaises(ValueError):
                fd_circular_disk(bad)


class CalculateFourProbeTests(unittest.TestCase):
    def _silicon(self, voltage_mv, current_ma, diameter_mm=50.0):
        return calculate_four_probe(sample_type=SampleType.SILICON, is_n_type=True,
                                    diameter_mm=diameter_mm, thickness_um=645.0,
                                    current_ma=current_ma, voltage_mv=voltage_mv,
                                    probe_spacing_mm=1.0)

    def test_silicon_end_to_end(self):
        # History 20250505_133004 centre point: combined R = 6.525035940 ohm.
        r = 6.525035940033755
        result = self._silicon(voltage_mv=r * 10.0, current_ma=10.0)
        expected_rho = r * 4.5167211315 * 0.9878749334 * 0.0645 * 1.001
        self.assertAlmostEqual(result.fd, 4.5167211315, delta=1e-9)
        self.assertAlmostEqual(result.fw, 0.9878749334, delta=1e-9)
        self.assertAlmostEqual(result.resistivity_ohm_cm / expected_rho, 1.0, delta=1e-9)
        self.assertAlmostEqual(result.sheet_resistance_ohm_per_square,
                               result.resistivity_ohm_cm / 0.0645, delta=1e-12)
        self.assertEqual(result.used_table_type, 5)
        # Legacy output was 31.0838 ohm/sq; x (0.98787/1.05) x (4.51672/4.5324).
        self.assertAlmostEqual(result.sheet_resistance_ohm_per_square, 29.1435, delta=1e-4)

    def test_thin_film_uses_closed_form_fd_and_unit_fw(self):
        result = calculate_four_probe(sample_type=SampleType.HEMT, is_n_type=True,
                                      diameter_mm=50.0, thickness_um=645.0,
                                      current_ma=1.0, voltage_mv=1.0, probe_spacing_mm=1.0)
        self.assertAlmostEqual(result.fd, 4.5167211315, delta=1e-9)
        self.assertEqual(result.fw, 1.0)
        self.assertEqual(result.used_table_type, 6)

    def test_small_disk_keeps_legacy_table(self):
        # D/S <= 3: closed form undefined, legacy table values unchanged.
        self.assertEqual(self._silicon(1.0, 1.0, diameter_mm=1.0).fd, 1.9976)
        self.assertEqual(self._silicon(1.0, 1.0, diameter_mm=2.5).fd, 3.6408)


if __name__ == "__main__":
    unittest.main()
