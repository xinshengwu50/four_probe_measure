# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Exclusive zip creation after checks; archive an old zip explicitly."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from release_files import ROOT, release_files
from verify_delivery import verify


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_zip(target):
    with zipfile.ZipFile(target, 'r') as archive:
        names = set(archive.namelist())
        if any('.Xil' in name or '__pycache__' in name or name.startswith('four_probe_measure/NA/')
               for name in names):
            raise ValueError('zip contains a generated/cache path')
        manifest_name = 'four_probe_measure/build/release_manifest.json'
        if manifest_name not in names:
            raise ValueError('zip has no release manifest')
        manifest = json.loads(archive.read(manifest_name))
        for path in release_files():
            name = 'four_probe_measure/' + path.relative_to(ROOT).as_posix()
            if name not in names:
                raise ValueError('zip is missing ' + name)
            if _sha(archive.read(name)) != manifest['files'][path.relative_to(ROOT).as_posix()]:
                raise ValueError('zip file hash differs from manifest: ' + name)
        for name, expected in manifest['bitstream_pair'].items():
            arcname = 'four_probe_measure/board/pynq/' + name
            if _sha(archive.read(arcname)) != expected:
                raise ValueError('zip pair hash differs from manifest: ' + name)
    print('PASS_ZIP', target, len(names), 'entries')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive-existing', action='store_true',
                        help='move an existing release zip to build/archive before creating the new one')
    args = parser.parse_args()
    verify()
    target = ROOT / 'build/four_probe_measure.zip'
    if target.exists():
        if not args.archive_existing:
            raise SystemExit('REFUSING TO OVERWRITE %s; re-run with --archive-existing to keep it' % target)
        archive_dir = ROOT / 'build/archive'
        archive_dir.mkdir(parents=True, exist_ok=True)
        old = archive_dir / ('four_probe_measure_%s.zip' %
                             datetime.now().strftime('%Y%m%d_%H%M%S'))
        shutil.move(str(target), str(old))
        print('ARCHIVED_OLD_ZIP', old)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in release_files() + [ROOT / 'build/release_manifest.json']:
            archive.write(path, arcname='four_probe_measure/' + path.relative_to(ROOT).as_posix())
    verify_zip(target)
    print('ZIP_CREATED', target, '; human report review/board acceptance pending')


if __name__ == '__main__':
    main()
