# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import math
import unittest

from four_probe_sw.adc_conversion import AdcConfig
from four_probe_sw.materials import CalculationMode, MaterialProfile
from four_probe_sw.measurement_model import MeasurementStatus, calculate_from_adc_frame, calculate_measurement


class MeasurementModelTests(unittest.TestCase):
    def test_bulk_resistivity_uses_si_units(self) -> None:
        profile = MaterialProfile(
            material_id="bulk",
            name="Bulk reference",
            mode=CalculationMode.BULK,
            adc=AdcConfig(),
            excitation_current_a=0.01,
            probe_spacing_m=1e-3,
            geometry_factor=2.0 * math.pi,
        )

        result = calculate_measurement(0.1, profile)

        self.assertEqual(result.status, MeasurementStatus.OK)
        self.assertAlmostEqual(result.resistance_ohm, 10.0, places=12)
        self.assertAlmostEqual(result.resistivity_ohm_m, 2.0 * math.pi * 1e-3 * 10.0)

    def test_thin_film_resistivity_is_sheet_resistance_times_thickness(self) -> None:
        profile = MaterialProfile(
            material_id="film",
            name="Thin film reference",
            mode=CalculationMode.THIN_FILM,
            adc=AdcConfig(),
            excitation_current_a=1e-3,
            thickness_m=100e-9,
        )

        result = calculate_measurement(0.01, profile)

        self.assertEqual(result.status, MeasurementStatus.OK)
        self.assertAlmostEqual(result.resistance_ohm, 10.0, places=12)
        self.assertAlmostEqual(result.resistivity_ohm_m, result.sheet_resistance_ohm_per_square * 100e-9)

    def test_custom_calibration_is_applied_after_geometry_calculation(self) -> None:
        profile = MaterialProfile(
            material_id="custom",
            name="Calibrated sample",
            mode=CalculationMode.CUSTOM,
            adc=AdcConfig(),
            excitation_current_a=0.01,
            custom_resistivity_factor_m=0.5,
            calibration_gain=1.1,
            calibration_offset_ohm_m=0.25,
        )

        result = calculate_measurement(0.1, profile)

        self.assertAlmostEqual(result.resistivity_ohm_m, 5.75, places=12)

    def test_invalid_voltage_and_current_do_not_produce_results(self) -> None:
        profile = MaterialProfile(
            material_id="limited",
            name="Limited",
            mode=CalculationMode.BULK,
            adc=AdcConfig(),
            excitation_current_a=0.01,
            probe_spacing_m=1e-3,
            geometry_factor=2.0,
            valid_voltage_min_v=0.01,
            valid_voltage_max_v=1.0,
        )

        voltage_result = calculate_measurement(0.001, profile)
        current_result = calculate_measurement(0.1, profile, current_a=0.0)

        self.assertEqual(voltage_result.status, MeasurementStatus.INVALID_VOLTAGE)
        self.assertIsNone(voltage_result.resistance_ohm)
        self.assertEqual(current_result.status, MeasurementStatus.INVALID_CURRENT)

    def test_resistivity_range_is_a_warning_not_a_silent_clamp(self) -> None:
        profile = MaterialProfile(
            material_id="range",
            name="Range limited",
            mode=CalculationMode.CUSTOM,
            adc=AdcConfig(),
            excitation_current_a=0.01,
            custom_resistivity_factor_m=1.0,
            resistivity_min_ohm_m=1.0,
            resistivity_max_ohm_m=2.0,
        )

        result = calculate_measurement(0.1, profile)

        self.assertEqual(result.status, MeasurementStatus.OK)
        self.assertIn("RESISTIVITY_OUT_OF_RANGE", result.warning_codes)
        self.assertAlmostEqual(result.resistivity_ohm_m, 10.0)

    def test_frame_measurement_keeps_raw_code_and_saturation_warning(self) -> None:
        profile = MaterialProfile(
            material_id="frame",
            name="Frame reference",
            mode=CalculationMode.CUSTOM,
            adc=AdcConfig(),
            excitation_current_a=0.01,
            custom_resistivity_factor_m=1.0,
        )

        result = calculate_from_adc_frame(0xFFFF_0000, profile)

        self.assertEqual(result.raw_code, 0xFFFF)
        self.assertIn("ADC_SATURATED", result.warning_codes)
        self.assertEqual(result.status, MeasurementStatus.OK)


if __name__ == "__main__":
    unittest.main()
