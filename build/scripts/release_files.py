# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Explicit release inventory: source/evidence, no Vivado caches or review originals."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def release_files():
    paths = [ROOT / 'README.md', ROOT / 'build/migration_manifest.json',
             ROOT / 'build/build_provenance.json']
    for folder in ('src', 'board', 'skill', 'report', 'sim/scripts',
                   'sim/results', 'build/scripts'):
        paths += [p for p in (ROOT / folder).rglob('*') if p.is_file()]
    # Current bit/hwh evidence.  The old pre-FP_DSP reports live under
    # build/reports_pre_fp_dsp and are deliberately not shipped.
    paths += [p for p in (ROOT / 'build/rebuilt').glob('*.rpt') if p.is_file()]
    good = []
    for p in sorted(set(paths)):
        rel = p.relative_to(ROOT)
        if '__pycache__' in rel.parts or '.Xil' in rel.parts:
            continue
        if any(name not in ('README.md', 'SKILL.md')
               and not re.fullmatch('[a-z0-9_.-]+', name)
               for name in rel.parts):
            raise ValueError('nonportable release filename: ' + str(rel))
        good.append(p)
    return good
