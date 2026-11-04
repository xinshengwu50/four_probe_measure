# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Record the RTL/build inputs and the exact bit/hwh produced from them."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path

from build_inputs import ROOT, digest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bit', default=str(ROOT / 'build/rebuilt/all_design.bit'))
    parser.add_argument('--hwh', default=str(ROOT / 'build/rebuilt/all_design.hwh'))
    parser.add_argument('--vivado-version', default='2026.1')
    parser.add_argument('--part', default='xc7z020clg400-1')
    args = parser.parse_args()
    bit = Path(args.bit).resolve()
    hwh = Path(args.hwh).resolve()
    if not bit.is_file() or not hwh.is_file():
        raise SystemExit('bit/hwh missing: %s %s' % (bit, hwh))
    build_digest, entries = digest()
    payload = {
        'schema_version': 1,
        'generated_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'build_inputs_digest': build_digest,
        'build_inputs': entries,
        'bit': {'path': bit.relative_to(ROOT).as_posix(), 'sha256': sha(bit)},
        'hwh': {'path': hwh.relative_to(ROOT).as_posix(), 'sha256': sha(hwh)},
        'vivado_version': args.vivado_version,
        'part': args.part,
        'note': 'Provenance records the inputs and output pair; it does not replace board acceptance.',
    }
    target = ROOT / 'build/build_provenance.json'
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PROVENANCE', target, build_digest, payload['bit']['sha256'], payload['hwh']['sha256'])


if __name__ == '__main__':
    main()
