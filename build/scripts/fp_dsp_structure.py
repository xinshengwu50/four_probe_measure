# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Machine-readable structural anchor for the FP_DSP RTL IP.

A functional simulation proves behaviour on one stimulus set; this file proves
that the module/port/parameter surface did not change unnoticed.  The baseline
is intentionally reviewed and updated only after an RTL change is simulated.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
RTL = ROOT / 'src/project/hw/rtl/fp_dsp'
BASELINE = RTL / 'fp_dsp_structure.json'
SOURCE_LIST = RTL / 'fp_dsp_sources.f'


def _strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def _balanced(text, start):
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise ValueError('unbalanced parenthesis in RTL header')


def _module_headers(text):
    headers = []
    for match in re.finditer(r'\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)', text):
        cursor = match.end()
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        pieces = [match.group(1)]
        if cursor < len(text) and text[cursor] == '#':
            open_at = text.find('(', cursor)
            if open_at < 0:
                raise ValueError('module %s has # without parameter list' % match.group(1))
            parameter_part = _balanced(text, open_at)
            pieces.append('# ' + ' '.join(parameter_part.split()))
            cursor = open_at + len(parameter_part)
        open_at = text.find('(', cursor)
        if open_at < 0:
            raise ValueError('module %s has no port list' % match.group(1))
        port_part = _balanced(text, open_at)
        pieces.append(' '.join(port_part.split()))
        headers.append(' '.join(pieces))
    return headers


def source_files():
    names = []
    for line in SOURCE_LIST.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            names.append(RTL / Path(line).name)
    return sorted(set(names))


def scan():
    files = {}
    modules = 0
    always = 0
    assigns = 0
    for path in source_files():
        raw = path.read_text(encoding='utf-8')
        clean = _strip_comments(raw)
        headers = _module_headers(clean)
        modules += len(headers)
        always += len(re.findall(r'\balways\b', clean))
        assigns += len(re.findall(r'\bassign\b', clean))
        files[path.name] = {
            'sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
            'modules': headers,
        }
    return {
        'definition': 'module parameter/port headers plus source SHA-256',
        'file_count': len(files),
        'module_count': modules,
        'always_count': always,
        'assign_count': assigns,
        'files': files,
    }


def check():
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    current = scan()
    if baseline.get('schema_version') != 1:
        raise ValueError('FP_DSP structure baseline schema mismatch')
    if baseline.get('structure') != current:
        raise ValueError('FP_DSP structure baseline mismatch: run build/scripts/fp_dsp_structure.py --update only after review')
    print('PASS_FP_DSP_STRUCTURE', current['file_count'], 'files;',
          current['module_count'], 'modules;', current['always_count'], 'always;',
          current['assign_count'], 'assign')


def update():
    current = scan()
    payload = {
        'schema_version': 1,
        'generated_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'structure': current,
    }
    BASELINE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('UPDATED_FP_DSP_STRUCTURE', BASELINE, current['file_count'], 'files;',
          current['module_count'], 'modules')


if __name__ == '__main__':
    import sys
    if '--update' in sys.argv:
        update()
    else:
        check()
