"""Collect Vivado utilization/timing/DRC into a provenance record, then emit a
before/after comparison table for an optimization report.

Standard library only. Reads saved report files; never launches Vivado, never
touches hardware.

Why this exists: an optimization section needs "before" and "after" numbers that
a reader can trace back to a specific build. Copying numbers by hand loses the
device, the tool version and the report they came from, and nothing stops a
figure from one device being compared against another. This module keeps the
provenance attached to every number and refuses comparisons that cannot mean
anything.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA_VERSION = 1

# Metric name -> (human label, unit, direction that counts as an improvement).
# "lower"/"higher" are facts about the metric, not opinions about a design.
METRICS = {
    'lut':        ('Slice LUTs',      'count', 'lower'),
    'lut_logic':  ('LUT as Logic',    'count', 'lower'),
    'lut_memory': ('LUT as Memory',   'count', 'lower'),
    'ff':         ('Slice Registers', 'count', 'lower'),
    'bram':       ('Block RAM Tile',  'count', 'lower'),
    'ramb36':     ('RAMB36/FIFO',     'count', 'lower'),
    'ramb18':     ('RAMB18',          'count', 'lower'),
    'dsp':        ('DSPs',            'count', 'lower'),
    'io':         ('Bonded IOB',      'count', 'lower'),
    'wns':        ('WNS',             'ns',    'higher'),
    'whs':        ('WHS',             'ns',    'higher'),
    'failing':    ('Failing endpoints', 'count', 'lower'),
    'endpoints':  ('Total endpoints', 'count', None),
}


def _num(token):
    """Parse one report token to int/float, or None when it is not a number.

    Vivado writes '<NA>' for absent values and '-' in separator rows. Both must
    come back as None rather than 0: a missing measurement is not a measurement
    of zero, and quietly turning it into 0 fabricates a result.
    """
    token = token.strip()
    if not token or token in {'-', '--', '<NA>', 'NA', 'N/A'}:
        return None
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return None


def _header_lines(text):
    """Yield (line, pill_row, dash_row) triples for Vivado ASCII tables.

    Vivado tables are: header row, row of dashes, data rows. Finding the dash
    row lets us accept any column spacing the tool happens to emit; matching
    fixed character offsets does not survive a Vivado version bump.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if '|' in line:
            continue  # pipe tables handled separately
        if i + 2 >= len(lines):
            break
        if set(lines[i + 1].strip()) <= set('- ') and lines[i + 1].strip():
            if any(tok and tok[0].isalpha() for tok in line.split()):
                yield line, lines[i + 2]
        elif set(line.strip()) <= set('- ') and line.strip():
            pass


def parse_utilization(text):
    """Extract resource counts from a `report_utilization` file.

    Returns {metric: {'used':int|None, 'available':int|None, 'util_pct':float|None}}.
    Only labels present in METRICS are collected; anything else in the report is
    left alone rather than guessed at.
    """
    out = {}
    # Pipe-table rows: | Label | Used | Fixed | Prohibited | Available | Util% |
    for match in re.finditer(
        r'^\|\s*([A-Za-z0-9 ./*]+?)\s*\|(.*)$', text, re.MULTILINE
    ):
        # Vivado marks some labels with a trailing '*' that points at a footnote
        # below the table ("RAMB36/FIFO*"). The footnote is not part of the
        # name, so strip the marker before matching.
        label = match.group(1).strip().rstrip('*').strip()
        cells = [c.strip() for c in match.group(2).rstrip('|').split('|')]
        if not cells:
            continue
        for key, (want, _unit, _dir) in METRICS.items():
            if key in out or label != want:
                continue
            used = _num(cells[0])
            # Layout is |used|fixed|prohibited|available|util%|; the available
            # and util columns are the last two, so read from the right. This
            # keeps working when a rule shows a blank "Prohibited" cell.
            available = _num(cells[-2]) if len(cells) >= 2 else None
            util = _num(cells[-1].rstrip('%'))
            out[key] = {'used': used, 'available': available, 'util_pct': util}
            break
    return out


def parse_timing(text):
    """Extract WNS/WHS/failing endpoints and the clock summary.

    Handles the `report_timing_summary` Design Timing Summary table. The number
    of metric groups varies by report options (WHS and WPWS may be absent), so
    the arity is derived from how many '(ns)' columns the header declares rather
    than assumed to be fixed.
    """
    out = {'wns': None, 'whs': None, 'wpws': None,
           'failing': None, 'endpoints': None,
           'constraints_met': None, 'clocks': []}

    lines = text.splitlines()
    for i, line in enumerate(lines):
        if 'WNS(ns)' not in line or 'WHS(ns)' not in line:
            continue
        # Each group is 4 columns: value, TNS/THS, failing, total.
        groups = line.count('(ns)') // 2
        if groups < 2:
            continue
        for candidate in lines[i + 1: i + 6]:
            values = [_num(tok) for tok in candidate.split()]
            if not values or any(v is None for v in values):
                continue
            if len(values) < groups * 4:
                continue
            out['wns'] = values[0]
            out['whs'] = values[4]
            out['failing'] = values[2]
            out['endpoints'] = values[3]
            if groups >= 3:
                out['wpws'] = values[8]
            break
        break

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('All user specified timing constraints are met'):
            out['constraints_met'] = True
        elif stripped.startswith('There are user specified timing constraints which are unrealized') \
                or stripped.startswith('Timing constraints are not met'):
            out['constraints_met'] = False

    # Clock Summary rows: name  {rise fall}  period  frequency
    # The section heading is written as '| Clock Summary', so match on
    # containment rather than on a startswith prefix; the data rows below it are
    # unprefixed. Stop at the next pipe-delimited table.
    in_clock = False
    for line in lines:
        if 'Clock Summary' in line:
            in_clock = True
            continue
        if not in_clock:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(
            r'^(\S+)\s+\{\s*[\d.]+\s+[\d.]+\s*\}\s+([\d.]+)\s+([\d.]+)\s*$', stripped)
        if match:
            out['clocks'].append({
                'name': match.group(1),
                'period_ns': _num(match.group(2)),
                'frequency_mhz': _num(match.group(3)),
            })
        elif out['clocks']:
            in_clock = False
    return out


def parse_drc(text):
    """Extract the DRC rule summary: totals per rule and any Error severity.

    Errors and warnings are kept apart. A report with 59 warnings and 0 errors
    is not the same result as one with 59 errors, and a comparison that only
    counts "59 checks" would hide that.
    """
    out = {'checks_found': None, 'rules': [], 'errors': 0, 'warnings': 0}
    match = re.search(r'Checks found:\s*(\d+)', text)
    if match:
        out['checks_found'] = int(match.group(1))
    for match in re.finditer(
        r'^\|\s*([A-Z]+-\d+)\s*\|\s*(Error|Warning|Critical Warning|Info)\s*\|'
        r'\s*([^|]*?)\s*\|\s*(\d+)\s*\|', text, re.MULTILINE):
        rule, severity, description, count = match.groups()
        count = int(count)
        out['rules'].append({'rule': rule, 'severity': severity,
                             'description': description.strip(), 'count': count})
    out['errors'] = sum(r['count'] for r in out['rules'] if r['severity'] == 'Error')
    out['warnings'] = sum(r['count'] for r in out['rules']
                          if r['severity'] in ('Warning', 'Critical Warning'))
    return out


def _provenance(text):
    """Pull the self-describing header Vivado writes at the top of every report."""
    fields = {}
    for key, pattern in (
        ('tool_version', r'\|\s*Tool Version\s*:\s*(.+)'),
        ('date', r'\|\s*Date\s*:\s*(.+)'),
        ('design', r'\|\s*Design\s*:\s*(.+)'),
        ('device', r'\|\s*Device\s*:\s*(.+)'),
        ('design_state', r'\|\s*Design State\s*:\s*(.+)'),
        ('command', r'\|\s*Command\s*:\s*(.+)'),
    ):
        match = re.search(pattern, text)
        if match:
            fields[key] = match.group(1).strip()
    return fields


def collect(utilization_path=None, timing_path=None, drc_path=None, label=''):
    """Build one comparison record from saved report files.

    Returns a dict holding the metrics plus the provenance that every number
    came from. Files that are not supplied contribute nothing; they are not
    substituted with defaults.
    """
    record = {'schema_version': SCHEMA_VERSION, 'label': label,
              'source_files': {}, 'provenance': {},
              'utilization': {}, 'timing': {}, 'drc': {}}
    sources = {'utilization': utilization_path, 'timing': timing_path, 'drc': drc_path}
    texts = {}
    for kind, path in sources.items():
        if not path:
            continue
        text = Path(path).read_text(encoding='utf-8', errors='replace')
        texts[kind] = text
        record['source_files'][kind] = Path(path).name
        for key, value in _provenance(text).items():
            record['provenance'].setdefault(key, value)

    if 'utilization' in texts:
        record['utilization'] = parse_utilization(texts['utilization'])
    if 'timing' in texts:
        record['timing'] = parse_timing(texts['timing'])
    if 'drc' in texts:
        record['drc'] = parse_drc(texts['drc'])
    return record


def _scalar(record, metric):
    """Read one metric out of a record, or None if it was never measured."""
    if metric in ('wns', 'whs', 'failing', 'endpoints'):
        return record.get('timing', {}).get(metric)
    entry = record.get('utilization', {}).get(metric)
    if isinstance(entry, dict):
        return entry.get('used')
    if metric == 'errors':
        return record.get('drc', {}).get('errors')
    return None


def compare(before, after):
    """Diff two records, refusing comparisons that cannot carry meaning.

    A device mismatch is a hard stop: utilization percentages and timing slack
    are properties of a part, so reporting "54% fewer Block RAMs" across two
    different parts compares nothing. A design-name or tool-version difference
    is surfaced as a warning and left to the author, because a rename or a patch
    upgrade is a legitimate reason for that difference to appear.
    """
    issues = []
    warnings = []

    from_dev = before.get('provenance', {}).get('device')
    to_dev = after.get('provenance', {}).get('device')
    if from_dev and to_dev and from_dev != to_dev:
        raise ValueError(
            f'refusing to compare across devices: {from_dev} vs {to_dev}. '
            'Resource percentages and timing slack are device properties; '
            'build both runs on the same part.')

    from_design = before.get('provenance', {}).get('design')
    to_design = after.get('provenance', {}).get('design')
    if from_design and to_design and from_design != to_design:
        warnings.append(f'design name differs: {from_design} vs {to_design}')

    from_tool = before.get('provenance', {}).get('tool_version')
    to_tool = after.get('provenance', {}).get('tool_version')
    if from_tool and to_tool and from_tool != to_tool:
        warnings.append(f'tool version differs: {from_tool} vs {to_tool}')

    from_state = before.get('provenance', {}).get('design_state')
    to_state = after.get('provenance', {}).get('design_state')
    if from_state and to_state and from_state != to_state:
        warnings.append(
            f'design state differs: {from_state} vs {to_state}. '
            'A synthesized-only run and a routed run are not comparable for '
            'timing; report both as synthesized or both as routed.')

    rows = []
    for key, (label, unit, direction) in METRICS.items():
        old = _scalar(before, key)
        new = _scalar(after, key)
        delta = None
        pct = None
        if old is not None and new is not None:
            delta = new - old
            if old != 0:
                pct = 100.0 * delta / old
        verdict = None
        if direction and delta is not None:
            if delta == 0:
                verdict = 'unchanged'
            elif (delta < 0) == (direction == 'lower'):
                verdict = 'improved'
            else:
                verdict = 'regressed'
        rows.append({'metric': key, 'label': label, 'unit': unit,
                     'before': old, 'after': new,
                     'delta': delta, 'delta_pct': pct, 'verdict': verdict})

    missing = [r['label'] for r in rows
               if r['before'] is None or r['after'] is None]
    if missing:
        issues.append('not measured in both runs: ' + ', '.join(missing))

    drc_before = before.get('drc', {}).get('errors')
    drc_after = after.get('drc', {}).get('errors')
    return {'schema_version': SCHEMA_VERSION, 'rows': rows,
            'warnings': warnings, 'unmeasured': missing,
            'drc_errors': {'before': drc_before, 'after': drc_after},
            'before_label': before.get('label') or 'before',
            'after_label': after.get('label') or 'after',
            'provenance': {'before': before.get('provenance', {}),
                           'after': after.get('provenance', {})}}


def _fmt(value, unit):
    if value is None:
        return 'n/a'
    if isinstance(value, float):
        if unit == 'ns':
            return f'{value:+.3f}' if value >= 0 else f'{value:.3f}'
        return f'{value:.2f}'
    return f'{value:,}'


def _fmt_delta(delta, pct, unit):
    if delta is None:
        return 'n/a'
    if isinstance(delta, float):
        shown = f'{delta:+.3f}' if unit == 'ns' else f'{delta:+.2f}'
    else:
        shown = f'{delta:+,}'
    if pct is None:
        return shown
    return f'{shown} ({pct:+.1f}%)'


def render_markdown(result, section_title='优化前后对比'):
    """Render the comparison as a Markdown table suitable for the report.

    Unmeasured rows are kept and printed as `n/a` rather than dropped, so a
    missing number stays visible instead of silently shrinking the table.
    """
    before_label = result['before_label']
    after_label = result['after_label']
    lines = [f'## {section_title}', '']
    lines.append(f'- 前：`{before_label}`')
    lines.append(f'- 后：`{after_label}`')
    prov_before = result['provenance']['before']
    prov_after = result['provenance']['after']
    for key, title in (('device', '器件'), ('tool_version', '工具版本'),
                       ('design_state', '实现状态'), ('date', '报告时间')):
        old = prov_before.get(key, 'n/a')
        new = prov_after.get(key, 'n/a')
        if old == new:
            lines.append(f'- {title}：`{old}`（两轮相同）')
        else:
            lines.append(f'- {title}：`{old}` → `{new}`')
    lines.append('')
    lines.append(f'| 指标 | {before_label} | {after_label} | 变化 | 判定 |')
    lines.append('|---|---:|---:|---:|---|')
    for row in result['rows']:
        if row['before'] is None and row['after'] is None:
            continue
        verdict = {'improved': '改善', 'regressed': '变差',
                   'unchanged': '持平', None: ''}[row['verdict']]
        lines.append(
            f"| {row['label']} | {_fmt(row['before'], row['unit'])} "
            f"| {_fmt(row['after'], row['unit'])} "
            f"| {_fmt_delta(row['delta'], row['delta_pct'], row['unit'])} "
            f"| {verdict} |")
    lines.append('')
    drc = result['drc_errors']
    if drc['before'] is not None or drc['after'] is not None:
        lines.append(f"DRC Error 数：{drc['before']} → {drc['after']}")
        lines.append('')
    if result['unmeasured']:
        lines.append('未在两轮中同时测得的指标（保持 n/a，不以 0 填充）：'
                     + '、'.join(result['unmeasured']))
        lines.append('')
    for warning in result['warnings']:
        lines.append(f'> ⚠️ {warning}')
    if result['warnings']:
        lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    collect_parser = sub.add_parser('collect', help='write one provenance record')
    collect_parser.add_argument('--utilization')
    collect_parser.add_argument('--timing')
    collect_parser.add_argument('--drc')
    collect_parser.add_argument('--label', default='')
    collect_parser.add_argument('--output', required=True)

    compare_parser = sub.add_parser('compare', help='diff two records')
    compare_parser.add_argument('before')
    compare_parser.add_argument('after')
    compare_parser.add_argument('--markdown')
    compare_parser.add_argument('--json')
    compare_parser.add_argument('--title', default='优化前后对比')

    args = parser.parse_args()
    if args.command == 'collect':
        record = collect(args.utilization, args.timing, args.drc, args.label)
        Path(args.output).write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'COLLECTED {args.output}')
        return

    before = json.loads(Path(args.before).read_text(encoding='utf-8'))
    after = json.loads(Path(args.after).read_text(encoding='utf-8'))
    result = compare(before, after)
    if args.markdown:
        Path(args.markdown).write_text(
            render_markdown(result, args.title) + '\n', encoding='utf-8')
        print(f'REPORT {args.markdown}')
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'RESULT {args.json}')
    if not args.markdown and not args.json:
        print(render_markdown(result, args.title))


if __name__ == '__main__':
    main()
