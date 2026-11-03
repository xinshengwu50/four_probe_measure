"""Tests for build_report: parsing, provenance, and the refuse-to-compare guards.

Runs offline on text fixtures only; no Vivado, no board.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import build_report as br

TEMPLATE_HEADER = """Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
-----------------------------------------------------------------------------
| Tool Version : {tool}
| Date         : {date}
| Design       : {design}
| Device       : {device}
| Speed File   : -1
| Design State : {state}
-----------------------------------------------------------------------------
"""

UTILIZATION = TEMPLATE_HEADER + """
1. Slice Logic
+----------------------------+-------+-------+------------+-----------+-------+
|          Site Type         |  Used | Fixed | Prohibited | Available | Util% |
+----------------------------+-------+-------+------------+-----------+-------+
| Slice LUTs                 | {lut} |     0 |          0 |     53200 | 47.29 |
|   LUT as Logic             | 24787 |     0 |          0 |     53200 | 46.59 |
|   LUT as Memory            |   370 |     0 |          0 |     17400 |  2.13 |
| Slice Registers            | {ff} |     0 |          0 |    106400 | 23.47 |
+----------------------------+-------+-------+------------+-----------+-------+

3. Memory
+-------------------+------+-------+------------+-----------+-------+
|     Site Type     | Used | Fixed | Prohibited | Available | Util% |
+-------------------+------+-------+------------+-----------+-------+
| Block RAM Tile    | {bram} |     0 |          0 |       140 | 74.29 |
|   RAMB36/FIFO*    | {bram} |     0 |          0 |       140 | 74.29 |
|     RAMB36E1 only | {bram} |       |            |           |       |
|   RAMB18          |    0 |     0 |          0 |       280 |  0.00 |
+-------------------+------+-------+------------+-----------+-------+
* Note: Each Block RAM Tile only has one FIFO logic available.

4. DSP
+------+------+-------+------------+-----------+-------+
| Site | Used | Fixed | Prohibited | Available | Util% |
+------+------+-------+------------+-----------+-------+
| DSPs | {dsp} |     0 |          0 |       220 | 17.73 |
+------+------+-------+------------+-----------+-------+
"""

TIMING = TEMPLATE_HEADER + """
| Design Timing Summary
| ---------------------

    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      THS(ns)  THS Failing Endpoints  THS Total Endpoints     WPWS(ns)     TPWS(ns)  TPWS Failing Endpoints  TPWS Total Endpoints
    -------      -------  ---------------------  -------------------      -------      -------  ---------------------  -------------------     --------     --------  ----------------------  --------------------
      {wns}        0.000                      0                {eps}        {whs}        0.000                      0                {eps}        8.750        0.000                       0                 25427


{met}


| Clock Summary
| -------------

Clock       Waveform(ns)       Period(ns)      Frequency(MHz)
-----       ------------       ----------      --------------
clk_fpga_0  {{0.000 10.000}}     20.000          50.000
"""

DRC = TEMPLATE_HEADER + """
1. REPORT SUMMARY
-----------------
             Checks found: {total}
+-----------+----------+------------------------+--------+
| Rule      | Severity | Description            | Checks |
+-----------+----------+------------------------+--------+
{rules}
+-----------+----------+------------------------+--------+
"""


def util(lut=25157, ff=24968, bram=104, dsp=39, device='xc7z020clg400-1',
         design='all_design_wrapper', state='Routed',
         tool='Vivado v.2026.1 (win64) Build 6511674'):
    return UTILIZATION.format(lut=lut, ff=ff, bram=bram, dsp=dsp, device=device,
                              design=design, state=state, tool=tool,
                              date='Fri Oct 30 19:47:35 2026')


def timing(wns=1.337, whs=0.015, eps=80385, met=True,
           device='xc7z020clg400-1', state='Routed',
           design='all_design_wrapper',
           tool='Vivado v.2026.1 (win64) Build 6511674'):
    return TIMING.format(wns=wns, whs=whs, eps=eps, device=device, state=state,
                         design=design,
                         tool=tool, date='Fri Oct 30 19:47:35 2026',
                         met='All user specified timing constraints are met.'
                         if met else
                         'Timing constraints are not met.')


def drc(rules=None, device='xc7z020clg400-1'):
    if rules is None:
        rules = [('DPIP-1', 'Warning', 'Input pipelining', 2),
                 ('DPOP-1', 'Warning', 'PREG Output pipelining', 21)]
    rows = '\n'.join(f'| {r} | {s} | {d} | {c} |' for r, s, d, c in rules)
    return DRC.format(device=device, date='Fri Oct 30 19:47:44 2026',
                      design='all_design_wrapper', state='Fully Routed',
                      tool='Vivado v.2026.1 (win64) Build 6511674',
                      total=sum(c for _, _, _, c in rules), rules=rows)


def record(util_text=None, timing_text=None, drc_text=None, label=''):
    import tempfile
    paths = {}
    with tempfile.TemporaryDirectory() as tmp:
        for kind, text in (('utilization', util_text), ('timing', timing_text),
                           ('drc', drc_text)):
            if text is not None:
                path = Path(tmp) / f'{kind}.rpt'
                path.write_text(text, encoding='utf-8')
                paths[kind] = path
        return br.collect(paths.get('utilization'), paths.get('timing'),
                          paths.get('drc'), label)


class ParseUtilizationTests(unittest.TestCase):
    def test_reads_used_available_and_percent(self):
        result = br.parse_utilization(util())
        self.assertEqual(result['lut']['used'], 25157)
        self.assertEqual(result['lut']['available'], 53200)
        self.assertAlmostEqual(result['lut']['util_pct'], 47.29)
        self.assertEqual(result['bram']['used'], 104)

    def test_starred_label_is_matched(self):
        # 'RAMB36/FIFO*' carries a footnote marker; the name must still match.
        result = br.parse_utilization(util())
        self.assertEqual(result['ramb36']['used'], 104)

    def test_single_digit_values_keep_their_column(self):
        # A one-digit count shifts every following character. If the parser used
        # fixed offsets instead of splitting on '|' it would read the wrong cell.
        result = br.parse_utilization(util(bram=5, dsp=9))
        self.assertEqual(result['bram']['used'], 5)
        self.assertEqual(result['dsp']['used'], 9)
        self.assertEqual(result['bram']['available'], 140)

    def test_absent_value_is_none_not_zero(self):
        # Vivado writes <NA> when a number does not apply. Treating that as 0
        # would invent a measurement.
        self.assertIsNone(br._num('<NA>'))
        self.assertIsNone(br._num('-'))
        self.assertIsNone(br._num(''))

    def test_unknown_labels_are_ignored(self):
        result = br.parse_utilization(util())
        self.assertNotIn('f7_muxes', result)


class ParseTimingTests(unittest.TestCase):
    def test_reads_wns_whs_and_endpoints(self):
        result = br.parse_timing(timing(wns=1.337, whs=0.015, eps=80385))
        self.assertAlmostEqual(result['wns'], 1.337)
        self.assertAlmostEqual(result['whs'], 0.015)
        self.assertEqual(result['endpoints'], 80385)
        self.assertEqual(result['failing'], 0)

    def test_detects_met_and_unmet(self):
        self.assertTrue(br.parse_timing(timing(met=True))['constraints_met'])
        self.assertFalse(br.parse_timing(timing(met=False))['constraints_met'])

    def test_negative_wns_parsed(self):
        result = br.parse_timing(timing(wns=-0.412))
        self.assertAlmostEqual(result['wns'], -0.412)

    def test_clock_summary_read(self):
        result = br.parse_timing(timing())
        self.assertEqual(len(result['clocks']), 1)
        self.assertEqual(result['clocks'][0]['name'], 'clk_fpga_0')
        self.assertAlmostEqual(result['clocks'][0]['frequency_mhz'], 50.0)


class ParseDrcTests(unittest.TestCase):
    def test_warning_counts_summed(self):
        result = br.parse_drc(drc())
        self.assertEqual(result['checks_found'], 23)
        self.assertEqual(result['warnings'], 23)
        self.assertEqual(result['errors'], 0)

    def test_error_severity_counted_separately(self):
        # A report with the same number of checks but one Error is a different
        # result; collapsing severities would hide that.
        result = br.parse_drc(drc([('PLACE-1', 'Error', 'Unroutable', 1),
                                   ('DPOP-1', 'Warning', 'pipelining', 20)]))
        self.assertEqual(result['errors'], 1)
        self.assertEqual(result['warnings'], 20)


class ProvenanceTests(unittest.TestCase):
    def test_header_captured(self):
        result = record(util_text=util(), label='x')
        self.assertEqual(result['provenance']['device'], 'xc7z020clg400-1')
        self.assertEqual(result['provenance']['design_state'], 'Routed')
        self.assertIn('2026.1', result['provenance']['tool_version'])

    def test_source_file_names_recorded(self):
        result = record(util_text=util(), timing_text=timing())
        self.assertEqual(result['source_files']['utilization'], 'utilization.rpt')
        self.assertEqual(result['source_files']['timing'], 'timing.rpt')
        self.assertNotIn('drc', result['source_files'])

    def test_missing_file_contributes_nothing(self):
        result = record(util_text=util())
        self.assertEqual(result['timing'], {})


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.before = record(util(25157, 24968, 104), timing(1.337, 0.015, 80385), drc())
        self.after = record(util(24976, 24930, 55), timing(2.767, 0.029, 78513), drc())

    def row(self, result, metric):
        return next(r for r in result['rows'] if r['metric'] == metric)

    def test_delta_and_percent(self):
        result = br.compare(self.before, self.after)
        row = self.row(result, 'bram')
        self.assertEqual(row['before'], 104)
        self.assertEqual(row['after'], 55)
        self.assertEqual(row['delta'], -49)
        self.assertAlmostEqual(row['delta_pct'], -47.115, places=2)

    def test_improvement_direction_per_metric(self):
        result = br.compare(self.before, self.after)
        self.assertEqual(self.row(result, 'bram')['verdict'], 'improved')
        # Slack going up is good even though the number went up.
        self.assertEqual(self.row(result, 'wns')['verdict'], 'improved')

    def test_regression_detected(self):
        worse = record(util(26000, 24968, 104), timing(0.900, 0.015, 80385), drc())
        result = br.compare(self.before, worse)
        self.assertEqual(self.row(result, 'lut')['verdict'], 'regressed')
        self.assertEqual(self.row(result, 'wns')['verdict'], 'regressed')

    def test_device_mismatch_refused(self):
        other = record(util(device='xc7z010clg400-1'),
                       timing(device='xc7z010clg400-1'), drc(device='xc7z010clg400-1'))
        with self.assertRaisesRegex(ValueError, 'refusing to compare across devices'):
            br.compare(self.before, other)

    def test_design_name_change_warns(self):
        renamed = record(util(design='all_design_wrapper_v2'),
                         timing(), drc())
        result = br.compare(self.before, renamed)
        self.assertTrue(any('design name differs' in w for w in result['warnings']))

    def test_synthesized_vs_routed_warns(self):
        # Timing from a synthesized-only run is not comparable to a routed run.
        synth = record(util(state='Synthesized'), timing(), drc())
        result = br.compare(self.before, synth)
        self.assertTrue(any('design state differs' in w for w in result['warnings']))

    def test_unmeasured_metric_reported_not_dropped(self):
        # Drop the DSP section entirely: the metric was never measured in the
        # second run, so it must surface as n/a rather than being counted as 0
        # or silently removed from the table.
        without_dsp = util(25157, 24968, 104)
        cut = without_dsp.index('4. DSP')
        partial = record(without_dsp[:cut], timing(1.337, 0.015, 80385))
        result = br.compare(self.before, partial)
        self.assertIn('DSPs', result['unmeasured'])
        row = self.row(result, 'dsp')
        self.assertIsNone(row['after'])
        self.assertIsNone(row['delta'])
        self.assertIsNone(row['verdict'])

    def test_zero_baseline_does_not_divide_by_zero(self):
        zero = record(util(25157, 24968, 0), timing(1.337, 0.015, 80385), drc())
        three = record(util(25157, 24968, 3), timing(1.337, 0.015, 80385), drc())
        result = br.compare(zero, three)
        row = self.row(result, 'bram')
        self.assertEqual(row['delta'], 3)
        self.assertIsNone(row['delta_pct'])

    def test_drc_errors_surfaced(self):
        failing = record(util(), timing(), drc([('PLACE-1', 'Error', 'bad', 2)]))
        result = br.compare(self.before, failing)
        self.assertEqual(result['drc_errors']['after'], 2)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.before = record(util(25157, 24968, 104), timing(1.337, 0.015, 80385), drc(),
                             '基线')
        self.after = record(util(24976, 24930, 55), timing(2.767, 0.029, 78513), drc(),
                            'V4')
        self.result = br.compare(self.before, self.after)

    def test_table_has_one_row_per_measured_metric(self):
        text = br.render_markdown(self.result)
        self.assertIn('| Block RAM Tile | 104 | 55 |', text)
        self.assertIn('改善', text)

    def test_none_rendered_as_na_not_zero(self):
        text = br.render_markdown(self.result)
        self.assertNotIn('| n/a | 0 |', text)

    def test_provenance_line_states_identity_when_shared(self):
        text = br.render_markdown(self.result)
        self.assertIn('两轮相同', text)

    def test_missing_metric_line_kept_visible(self):
        partial = record(util(25157, 24968, 104), timing(1.337, 0.015, 80385))
        text = br.render_markdown(br.compare(self.before, partial))
        self.assertIn('未在两轮中同时测得', text)


class RealReportTests(unittest.TestCase):
    """Parse the reports that ship in this package, not just synthetic fixtures.

    A parser that only passes its own fixtures proves nothing about real Vivado
    output; these read the actual files the project reported from.
    """
    EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'

    def test_shipped_example_reports_parse(self):
        base = self.EXAMPLES / 'baseline'
        opt = self.EXAMPLES / 'optimized'
        if not base.exists():
            self.skipTest('example reports not present')
        before = br.collect(base / 'utilization.rpt', base / 'timing_summary.rpt',
                            base / 'drc.rpt', 'before')
        after = br.collect(opt / 'utilization.rpt', opt / 'timing_summary.rpt',
                           opt / 'drc.rpt', 'after')
        self.assertEqual(before['utilization']['bram']['used'], 104)
        self.assertEqual(after['utilization']['bram']['used'], 55)
        result = br.compare(before, after)
        row = next(r for r in result['rows'] if r['metric'] == 'bram')
        self.assertAlmostEqual(row['delta_pct'], -47.115, places=2)


if __name__ == '__main__':
    unittest.main()
