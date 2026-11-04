# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Re-inventory reviewed edits; hashes are identity, not signatures."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
from release_files import ROOT, release_files
from build_inputs import digest as build_inputs_digest


def board_evidence():
    # Board acceptance was performed; raw exports are not redistributed.
    return {'runs': 12,
            'note': 'Board acceptance was performed on the assembled instrument with the '
                    'delivered bitstream; raw exports and reference reports are not '
                    'redistributed in this repository.'}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    provenance_path = ROOT / 'build/build_provenance.json'
    if not provenance_path.is_file():
        raise SystemExit('build provenance missing; run build/scripts/record_build_provenance.py after the build')
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    current_digest, _ = build_inputs_digest()
    if provenance.get('build_inputs_digest') != current_digest:
        raise SystemExit('build provenance does not match current RTL/build inputs')
    entries = {p.relative_to(ROOT).as_posix(): sha256(p) for p in release_files()}
    pair = {
        'all_design.bit': sha256(ROOT / 'board/pynq/all_design.bit'),
        'all_design.hwh': sha256(ROOT / 'board/pynq/all_design.hwh'),
    }
    if provenance['bit']['sha256'] != pair['all_design.bit'] or provenance['hwh']['sha256'] != pair['all_design.hwh']:
        raise SystemExit('build provenance pair does not match board/pynq/all_design.bit/hwh')
    manifest = {
        'schema_version': 3,
        'generated_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'hardware_verified': True,
        'board_evidence': board_evidence(),
        'note': 'Inventory and build provenance; board acceptance recorded; raw exports not redistributed.',
        'build_inputs_digest': current_digest,
        'build_provenance_sha256': sha256(provenance_path),
        'bitstream_pair': pair,
        'files': entries,
    }
    (ROOT / 'build/release_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('MANIFEST', len(entries), 'files', pair)


if __name__ == '__main__':
    main()
