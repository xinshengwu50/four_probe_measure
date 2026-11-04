# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest

from four_probe_sw.adc_voltage_map import (
    ADC_VALID_CODE_MAX,
    ADC_VALID_CODE_MIN,
    average_window_mv,
    adc_scale_mv_per_code,
    quantize_q8_24,
    q8_24_to_float,
    product96_to_float,
    code_to_mv,
    code_to_signed,
    extract_code,
    is_valid_voltage_code,
)


class AdcVoltageMapTests(unittest.TestCase):
    def test_reverse_code_bounds_match_50_to_5000_mv(self) -> None:
        self.assertEqual(ADC_VALID_CODE_MIN, 320)
        self.assertEqual(ADC_VALID_CODE_MAX, 32000)
        self.assertAlmostEqual(code_to_mv(ADC_VALID_CODE_MIN), 50.0)
        self.assertAlmostEqual(code_to_mv(ADC_VALID_CODE_MAX), 5000.0)

    def test_two_complement_codes(self) -> None:
        self.assertEqual(code_to_signed(0x3F5E), 16222)
        self.assertEqual(code_to_signed(0xC0AA), -16214)
        self.assertAlmostEqual(code_to_mv(0x3F5E), 2534.6875)
        self.assertAlmostEqual(code_to_mv(0xC0AA), -2533.4375)

    def test_codes_outside_bounds_are_rejected(self) -> None:
        self.assertFalse(is_valid_voltage_code(319))
        self.assertFalse(is_valid_voltage_code(32001))
        self.assertTrue(is_valid_voltage_code(320))
        self.assertTrue(is_valid_voltage_code(32000))

    def test_raw_frame_extracts_upper_16_bits(self) -> None:
        self.assertEqual(extract_code(0x3F5E_8000), 0x3F5E)
        self.assertEqual(extract_code(0x0000_1234), 0x0000)

    def test_window_average(self) -> None:
        self.assertAlmostEqual(average_window_mv(900, 2), 70.3125)

    def test_q8_24_helpers_match_pl_product_words(self) -> None:
        self.assertAlmostEqual(adc_scale_mv_per_code(), 0.15625)
        coeff = quantize_q8_24(1.5)
        self.assertAlmostEqual(q8_24_to_float(coeff), 1.5)
        product = int(2.5 * (1 << 24))
        self.assertAlmostEqual(product96_to_float(product & 0xFFFFFFFF, (product >> 32) & 0xFFFFFFFF, product >> 64), 2.5)


if __name__ == "__main__":
    unittest.main()