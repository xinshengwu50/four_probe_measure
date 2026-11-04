# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest

from four_probe_sw.ads8681_frame_diagnostics import (
    ADC_CODE_MID,
    ADC_FULL_SCALE_V,
    ADC_LSB_V,
    ENCODINGS,
    FRAME_FIELDS,
    FrameCapture,
    Ads8681FrameMonitor,
    candidate_stats,
    classify_full_scale,
    code_to_voltage,
    decode_candidate,
    diagnose_captures,
    extract_field,
    frame_activity,
    rank_candidates,
)


def twos_code(voltage_v):
    return int(round(float(voltage_v) / ADC_LSB_V)) & 0xFFFF


def offset_code(voltage_v):
    return (ADC_CODE_MID + int(round(float(voltage_v) / ADC_LSB_V))) & 0xFFFF


class FrameDiagnosticsTests(unittest.TestCase):
    def test_extract_known_fields(self):
        raw = 0xCD06_5200
        self.assertEqual(extract_field(raw, 'high16'), 0xCD06)
        self.assertEqual(extract_field(raw, 'low16'), 0x5200)
        self.assertEqual(extract_field(raw, 'high16_swap_bytes'), 0x06CD)
        self.assertEqual(extract_field(raw, 'low16_swap_bytes'), 0x0052)

    def test_classify_full_scale_distinguishes_5v_from_12v(self):
        code_5v = offset_code(2.5)
        code_12v = int(round(ADC_CODE_MID + 2.5 / 12.288 * ADC_CODE_MID))
        result_5v = classify_full_scale(2.5, code_5v)
        result_12v = classify_full_scale(2.5, code_12v)
        self.assertAlmostEqual(result_5v['inferred_full_scale_v'], 5.12)
        self.assertAlmostEqual(result_12v['inferred_full_scale_v'], 12.288)

    def test_code_decoding_modes(self):
        code_2p5 = int(round(2.5 / ADC_LSB_V)) & 0xFFFF
        code_minus_2p5 = (-int(round(2.5 / ADC_LSB_V))) & 0xFFFF
        self.assertAlmostEqual(code_to_voltage(code_2p5, 'twos_complement'), 2.5, places=6)
        self.assertAlmostEqual(code_to_voltage(code_minus_2p5, 'twos_complement'), -2.5, places=6)
        self.assertAlmostEqual(code_to_voltage(offset_code(2.5), 'offset_binary'), 2.5, places=6)
        self.assertAlmostEqual(code_to_voltage(code_2p5, 'twos_complement_magnitude'), 2.5, places=6)

    def test_rank_candidates_selects_low16_twos_complement(self):
        captures = []
        for index, voltage in enumerate((-1.0, 0.0, 1.0)):
            code = twos_code(voltage)
            raw = (0xCD06 << 16) | code
            captures.append(
                FrameCapture(
                    label=f'v{index}',
                    raw_frames=(raw, raw, raw),
                    ads_diff_voltage_v=voltage,
                )
            )
        ranking = rank_candidates(captures, minimum_dynamic_code_span=1)
        self.assertTrue(ranking)
        self.assertTrue(ranking[0].eligible)
        self.assertEqual(ranking[0].field, 'low16')
        self.assertEqual(ranking[0].encoding, 'twos_complement')
        self.assertLess(ranking[0].rmse_v, 1e-9)

    def test_rank_candidates_selects_low16_offset_binary(self):
        captures = []
        for index, voltage in enumerate((-1.0, 0.0, 1.0)):
            code = offset_code(voltage)
            raw = (0x1234 << 16) | code
            captures.append(
                FrameCapture(
                    label=f'o{index}',
                    raw_frames=(raw, raw, raw),
                    ads_diff_voltage_v=voltage,
                )
            )
        ranking = rank_candidates(captures, minimum_dynamic_code_span=1)
        self.assertTrue(ranking)
        self.assertTrue(ranking[0].eligible)
        self.assertEqual(ranking[0].field, 'low16')
        self.assertEqual(ranking[0].encoding, 'offset_binary')

    def test_frozen_frame_is_diagnosed(self):
        raw = 0xCD06_5200
        captures = [
            FrameCapture(label='a', raw_frames=(raw, raw), ads_diff_voltage_v=0.0),
            FrameCapture(label='b', raw_frames=(raw, raw), ads_diff_voltage_v=1.0),
        ]
        result = diagnose_captures(captures)
        self.assertEqual(result['status'], 'spi_frame_frozen')

    def test_activity_reports_moving_low16(self):
        frames = [(0xCD06 << 16) | code for code in (0x4000, 0x4001, 0x4002)]
        activity = frame_activity(frames)
        self.assertEqual(activity['high16'].code_span, 0)
        self.assertEqual(activity['low16'].code_span, 2)
        self.assertEqual(activity['low16'].unique_values, 3)

    def test_monitor_captures_full_raw_frames(self):
        values = [0x11111111, 0x22222222, 0x33333333]
        class FakeMMIO:
            def __init__(self, values):
                self.values = list(values)
                self.index = 0
            def read(self, offset):
                assert offset == 0x1C
                value = self.values[self.index]
                self.index = min(self.index + 1, len(self.values) - 1)
                return value
        monitor = Ads8681FrameMonitor(FakeMMIO(values), sample_interval_s=1e-6)
        capture = monitor.capture_raw(label='fake', sample_count=2, discard_first=1, interval_s=1e-6)
        self.assertEqual(capture.raw_frames, (0x22222222, 0x33333333))

    def test_candidate_stats_include_all_candidates(self):
        code_2p5 = int(round(2.5 / ADC_LSB_V)) & 0xFFFF
        raw = (0xCD06 << 16) | code_2p5
        stats = candidate_stats((raw, raw))
        self.assertEqual(len(stats), len(FRAME_FIELDS) * len(ENCODINGS))
        self.assertIn(('low16', 'twos_complement'), stats)
        self.assertAlmostEqual(stats[('low16', 'twos_complement')].voltage_mean, 2.5, places=6)


if __name__ == '__main__':
    unittest.main()
