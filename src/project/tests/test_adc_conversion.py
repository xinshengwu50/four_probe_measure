# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest

from four_probe_sw.adc_conversion import AdcConfig, AdcEncoding, decode_frame


class AdcConversionTests(unittest.TestCase):
    def test_offset_binary_midscale_is_zero(self) -> None:
        config = AdcConfig(bits=16, full_scale_v=5.12)

        sample = decode_frame(0x8000_1234, config)

        self.assertEqual(sample.code, 0x8000)
        self.assertAlmostEqual(sample.voltage_v, 0.0, places=12)
        self.assertFalse(sample.saturated)

    def test_offset_binary_rail_is_reported_as_saturated(self) -> None:
        config = AdcConfig(bits=16, full_scale_v=5.12)

        low = decode_frame(0x0000_0000, config)
        high = decode_frame(0xFFFF_0000, config)

        self.assertTrue(low.saturated)
        self.assertTrue(high.saturated)
        self.assertAlmostEqual(low.voltage_v, -5.12, places=6)
        self.assertAlmostEqual(high.voltage_v, 5.12 * (32767 / 32768), places=6)

    def test_twos_complement_conversion(self) -> None:
        config = AdcConfig(
            bits=16,
            full_scale_v=2.5,
            encoding=AdcEncoding.TWOS_COMPLEMENT,
        )

        negative = decode_frame(0x8000_0000, config)
        positive = decode_frame(0x7FFF_0000, config)

        self.assertAlmostEqual(negative.voltage_v, -2.5, places=6)
        self.assertAlmostEqual(positive.voltage_v, 2.5 * (32767 / 32768), places=6)
        self.assertTrue(negative.saturated)
        self.assertTrue(positive.saturated)

    def test_frame_range_and_code_range_are_checked(self) -> None:
        config = AdcConfig(bits=16, full_scale_v=5.12, frame_bits=32)

        with self.assertRaises(ValueError):
            decode_frame(-1, config)
        with self.assertRaises(ValueError):
            decode_frame(1 << 32, config)

        with self.assertRaises(ValueError):
            AdcConfig(bits=16, full_scale_v=5.12, code_lsb=17)


if __name__ == "__main__":
    unittest.main()
