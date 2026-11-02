# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Reusable measurement and PYNQ-side software components."""
from .adc_conversion import AdcConfig, AdcEncoding, AdcSample, decode_frame
from .ads8681_frame_diagnostics import Ads8681FrameMonitor, CandidateScore, CandidateStats, FrameCapture, FrameSample, diagnose_captures, frame_activity, rank_candidates
from .analog_frontend import AnalogFrontendController, AnalogFrontendError, expected_current_a, voltage_to_dac_code
from .filtering import SampleSummary, median, summarize_samples
from .direct_adc_measurement import DEFAULT_FORWARD_CURRENT_BY_RANGE_A, DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V, DEFAULT_REVERSE_CURRENT_BY_RANGE_A, MeasurementAbortedError, RESISTIVITY_RANGE_TABLE, calibrated_current_for_range_a, range_index_for_resistivity
from .pl_window_stats import PlWindowSnapshot, PlWindowStats, PlWindowStatsError
from .materials import CalculationMode, MaterialProfile, MaterialRegistry
from .measurement_model import MeasurementResult, MeasurementStatus, calculate_from_adc_frame, calculate_measurement
from .quality import QualityReport, QualityThresholds, evaluate_quality
__all__ = ['AdcConfig', 'AdcEncoding', 'AdcSample', 'Ads8681FrameMonitor', 'CandidateScore', 'CandidateStats', 'FrameCapture', 'FrameSample', 'AnalogFrontendController', 'AnalogFrontendError', 'CalculationMode', 'MaterialProfile', 'MaterialRegistry', 'MeasurementResult', 'MeasurementStatus', 'QualityReport', 'QualityThresholds', 'SampleSummary', 'DEFAULT_FORWARD_CURRENT_BY_RANGE_A', 'DEFAULT_REVERSE_CURRENT_BY_RANGE_A', 'DEFAULT_PROBE_VOLTAGE_OFFSET_BY_RANGE_V', 'MeasurementAbortedError', 'PlWindowSnapshot', 'PlWindowStats', 'PlWindowStatsError', 'RESISTIVITY_RANGE_TABLE', 'calibrated_current_for_range_a', 'range_index_for_resistivity', 'calculate_from_adc_frame', 'calculate_measurement', 'decode_frame', 'diagnose_captures', 'frame_activity', 'rank_candidates', 'evaluate_quality', 'expected_current_a', 'median', 'summarize_samples', 'voltage_to_dac_code']
