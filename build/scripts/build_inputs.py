# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Deterministic digest of every input that can change the FPGA bitstream."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'src/project'


def _read_source_list(path):
    files = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            files.append(PROJECT / line)
    return files


def input_files():
    files = [
        PROJECT / 'hw/rtl/rtl_sources.f',
        PROJECT / 'hw/rtl/fp_dsp/fp_dsp_sources.f',
        PROJECT / 'hw/constraints/all.xdc',
        PROJECT / 'scripts/recreate_bd.tcl',
        PROJECT / 'scripts/add_fp_dsp.tcl',
        ROOT / 'build/scripts/create_project.tcl',
        ROOT / 'build/scripts/build_overlay.tcl',
        ROOT / 'build/scripts/build_inputs.py',
        ROOT / 'build/scripts/record_build_provenance.py',
    ]
    files += _read_source_list(PROJECT / 'hw/rtl/rtl_sources.f')
    files += _read_source_list(PROJECT / 'hw/rtl/fp_dsp/fp_dsp_sources.f')
    files += sorted((ROOT / 'src/ip_repo/all_final/src').glob('*'))
    files.append(ROOT / 'src/ip_repo/all_final/component.xml')
    files.append(ROOT / 'src/ip_repo/all_final/xgui/all_final_v1_0.tcl')
    return sorted({p.resolve() for p in files}, key=lambda p: p.relative_to(ROOT).as_posix())


def digest():
    files = input_files()
    for path in files:
        if not path.is_file():
            raise FileNotFoundError('build input missing: %s' % path)
    h = hashlib.sha256()
    entries = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        file_hash = hashlib.sha256(data).hexdigest()
        h.update(rel.encode('utf-8'))
        h.update(b'\0')
        h.update(hashlib.sha256(data).digest())
        entries.append({'path': rel, 'sha256': file_hash})
    return h.hexdigest(), entries


if __name__ == '__main__':
    value, entries = digest()
    print(value)
    print('build inputs:', len(entries))
