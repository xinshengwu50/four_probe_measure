# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest

from four_probe_sw.filtering import median, summarize_samples
from four_probe_sw.quality import QualityThresholds, evaluate_quality


class FilteringAndQualityTests(unittest.TestCase):
    def test_median_is_robust_to_single_outlier(self) -> None:
        self.assertEqual(median([1.0, 100.0, 2.0, 3.0, 4.0]), 3.0)

    def test_summary_rejects_zero_and_out_of_range_samples(self) -> None:
        summary = summarize_samples(
            [0.0, 1.0, 1.1, 100.0, float("nan")],
            minimum=0.5,
            maximum=2.0,
            reject_zero=True,
        )

        self.assertEqual(summary.total_count, 5)
        self.assertEqual(summary.valid_count, 2)
        self.assertEqual(summary.rejected_count, 3)
        self.assertAlmostEqual(summary.median, 1.05)

    def test_quality_passes_when_samples_are_stable(self) -> None:
        report = evaluate_quality(
            [1.00, 1.01, 0.99, 1.00, 1.02],
            QualityThresholds(
                min_samples=5,
                min_valid_ratio=1.0,
                max_stddev_v=0.02,
                max_relative_spread=0.03,
            ),
        )

        self.assertTrue(report.ok)
        self.assertEqual(report.reason_codes, ())
        self.assertGreaterEqual(report.score, 90.0)

    def test_quality_fails_for_invalid_ratio_noise_and_saturation(self) -> None:
        report = evaluate_quality(
            [0.5, 1.5, 8.0, 0.0],
            QualityThresholds(
                min_samples=3,
                min_valid_ratio=0.75,
                max_stddev_v=0.01,
                max_saturation_ratio=0.0,
            ),
            minimum=0.5,
            maximum=2.0,
            saturation_flags=[False, False, True, False],
        )

        self.assertFalse(report.ok)
        self.assertIn("VALID_RATIO_LOW", report.reason_codes)
        self.assertIn("NOISE_HIGH", report.reason_codes)
        self.assertIn("SATURATION_HIGH", report.reason_codes)

    def test_saturation_flag_length_must_match_samples(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_quality(
                [1.0, 1.0],
                QualityThresholds(),
                saturation_flags=[False],
            )


if __name__ == "__main__":
    unittest.main()
