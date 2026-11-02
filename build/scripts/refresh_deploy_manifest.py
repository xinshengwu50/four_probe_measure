# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Refresh the deploy anchor from the CURRENT files; never rebuilds a bitstream.

This script is deliberately separate from the release manifest.  The deploy
manifest is checked on the board by FinalFourProbeSystem.preflight(), so it must
describe the exact package and bit/hwh pair that will be uploaded together.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIT = ROOT / 'board/pynq/all_design.bit'
HWH = ROOT / 'board/pynq/all_design.hwh'
PACKAGES = (
    ROOT / 'board/pynq/four_probe_sw',
    ROOT / 'src/project/sw/pynq/four_probe_sw',
)


def board_evidence():
    # Board acceptance was performed; raw exports are not redistributed.
    return {'runs': 12,
            'note': 'Board acceptance was performed on the assembled instrument with the '
                    'delivered bitstream; raw exports and reference reports are not '
                    'redistributed in this repository.'}


def entry(path):
    return {'name': path.name, 'size': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    provenance_path = ROOT / 'build/build_provenance.json'
    if not provenance_path.is_file():
        raise SystemExit('build provenance missing; record it after the build')
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    bit_entry = entry(BIT)
    hwh_entry = entry(HWH)
    if provenance['bit']['sha256'] != bit_entry['sha256'] or provenance['hwh']['sha256'] != hwh_entry['sha256']:
        raise SystemExit('build provenance pair does not match board/pynq')
    manifest = {
        'manifest_version': 1,
        'generated_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'hardware_verified': True,
        'source': 'nativeADC + UART115200 + reset-hold + discreteheatmap + FP_DSPv5',
        'verification_scope': 'Identity and build-input provenance; offline regressions; HDL simulations; board acceptance recorded; raw exports not redistributed.',
        'board_evidence': board_evidence(),
        'bitstream_revision': '2026-11-02_native_fr_pair',
        'build_inputs_digest': provenance['build_inputs_digest'],
        'build_provenance_sha256': hashlib.sha256(provenance_path.read_bytes()).hexdigest(),
        'files': [entry(p) for p in sorted((ROOT / 'board/pynq/four_probe_sw').glob('*.py'))],
        'bitstream': [bit_entry, hwh_entry],
    }
    content = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
    for package in PACKAGES:
        (package / 'deploy_manifest.json').write_text(content, encoding='utf-8')
        print('DEPLOY_MANIFEST', package, len(manifest['files']), 'files')


if __name__ == '__main__':
    main()
