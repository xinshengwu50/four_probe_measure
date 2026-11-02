# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Read-only inventory, pair, mirrors and safe-default checks; never loads hardware."""
import ast
from datetime import datetime
import hashlib
import json
import xml.etree.ElementTree as ET

from release_files import ROOT, release_files
from fp_dsp_structure import check as check_fp_dsp_structure
from build_inputs import digest as build_inputs_digest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_time(value, label):
    try:
        parsed = datetime.fromisoformat(str(value))
    except Exception as exc:
        raise ValueError('%s has no valid ISO timestamp: %r' % (label, value)) from exc
    if parsed.tzinfo is None:
        raise ValueError('%s timestamp must include a timezone' % label)


def _runtime_py_files():
    board = ROOT / 'board/pynq'
    # Test fixtures live next to the runtime modules but have no src mirror.
    return [p for p in board.rglob('*.py')
            if p.name != 'support.py' and not p.name.startswith('test_')]


def _check_deploy_manifest(pair):
    package = ROOT / 'board/pynq/four_probe_sw'
    manifest_path = package / 'deploy_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if int(manifest.get('manifest_version', 0)) != 1:
        raise ValueError('deploy manifest version mismatch')
    _parse_time(manifest.get('generated_at'), 'deploy manifest generated_at')
    declared = {str(entry.get('name')) for entry in manifest.get('files') or ()}
    actual = {path.name for path in package.glob('*.py')}
    if declared != actual:
        raise ValueError('deploy manifest does not cover all package Python files')
    for entry in manifest.get('files') or ():
        path = package / str(entry.get('name'))
        if not path.is_file():
            raise ValueError('deploy manifest lists a missing file: ' + str(path))
        if path.stat().st_size != int(entry.get('size', -1)) or sha(path) != entry.get('sha256'):
            raise ValueError('deploy manifest file differs: ' + str(path))
    got_pair = {entry.get('name'): entry.get('sha256') for entry in manifest.get('bitstream') or ()}
    if got_pair != pair:
        raise ValueError('deploy manifest bit/hwh pair differs from board pair')
    src_package = ROOT / 'src/project/sw/pynq/four_probe_sw'
    if sha(manifest_path) != sha(src_package / 'deploy_manifest.json'):
        raise ValueError('board/src deploy manifests differ')


def verify():
    files = release_files()
    manifest = json.loads((ROOT / 'build/release_manifest.json').read_text(encoding='utf-8'))
    if int(manifest.get('schema_version', 0)) != 3:
        raise ValueError('release manifest schema_version is not 3')
    _parse_time(manifest.get('generated_at'), 'release manifest generated_at')
    expected = manifest.get('files')
    if not isinstance(expected, dict):
        raise ValueError('release manifest has no files mapping')
    actual = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    if actual != expected:
        raise ValueError('inventory/hash mismatch')
    for rel in ('build/rebuilt/timing_summary.rpt', 'build/rebuilt/utilization.rpt',
                'build/rebuilt/drc.rpt'):
        if rel not in expected:
            raise ValueError('current build report missing from release: ' + rel)
    if any(rel.startswith('build/reports/') or rel.startswith('build/reports_pre_fp_dsp/')
           for rel in expected):
        raise ValueError('stale pre-FP_DSP reports must not be in the release')
    timing = (ROOT / 'build/rebuilt/timing_summary.rpt').read_text(encoding='utf-8', errors='replace')
    if 'All user specified timing constraints are met.' not in timing:
        raise ValueError('current timing report is not a passing report')

    current_digest, _ = build_inputs_digest()
    if manifest.get('build_inputs_digest') != current_digest:
        raise ValueError('current RTL/build inputs differ from the recorded build inputs')
    provenance_path = ROOT / 'build/build_provenance.json'
    if not provenance_path.is_file():
        raise ValueError('build provenance is missing')
    if manifest.get('build_provenance_sha256') != sha(provenance_path):
        raise ValueError('build provenance hash differs from release manifest')
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    if provenance.get('build_inputs_digest') != current_digest:
        raise ValueError('provenance build digest is stale')

    pair = manifest.get('bitstream_pair') or {}
    for name in ('all_design.bit', 'all_design.hwh'):
        if pair.get(name) != sha(ROOT / 'board/pynq' / name):
            raise ValueError('fixed delivered pair changed: ' + name)
        if expected.get('board/pynq/' + name) != pair.get(name):
            raise ValueError('pair hash missing from release inventory: ' + name)
    if provenance['bit']['sha256'] != pair['all_design.bit']:
        raise ValueError('provenance bitstream hash does not match delivered bit')
    if provenance['hwh']['sha256'] != pair['all_design.hwh']:
        raise ValueError('provenance HWH hash does not match delivered HWH')

    board = ROOT / 'board/pynq'
    source = ROOT / 'src/project/sw/pynq'
    for path in _runtime_py_files():
        peer = source / path.relative_to(board)
        if not peer.is_file() or sha(path) != sha(peer):
            raise ValueError('PS deployment/source differs: ' + str(path.relative_to(board)))
    if sha(ROOT / 'src/project/hw/rtl/all/all_final.v') != sha(ROOT / 'src/ip_repo/all_final/src/all_final.v'):
        raise ValueError('packaged RTL mismatch')
    _check_deploy_manifest(pair)

    mods = [m for m in ET.parse(board / 'all_design.hwh').iter('MODULE')
            if m.get('INSTANCE') in ('axi_uartlite_0', 'fp_dsp_0')]
    names = {m.get('INSTANCE') for m in mods}
    if names != {'axi_uartlite_0', 'fp_dsp_0'}:
        raise ValueError('UART or FP_DSP missing from HWH')
    uart = next(m for m in mods if m.get('INSTANCE') == 'axi_uartlite_0')
    params = {p.get('NAME'): p.get('VALUE') for p in uart.iter('PARAMETER')}
    if params.get('C_BAUDRATE') != '115200':
        raise ValueError('wrong baud')

    notebooks = list(board.glob('*.ipynb'))
    allowed={'01_four_all_system.ipynb'}
    if {p.name for p in notebooks}!=allowed:
        raise ValueError('expected only01 production entry')
    for path in notebooks:
        document=json.loads(path.read_text(encoding='utf-8'))
        values={}
        for cell in document['cells']:
            if cell['cell_type']!='code':continue
            if cell.get('outputs') or cell.get('execution_count') is not None:
                raise ValueError('Notebook outputs not cleared: '+path.name)
            for node in ast.parse(''.join(cell['source'])).body:
                if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant):
                    for target in node.targets:
                        if isinstance(target,ast.Name):values[target.id]=node.value.value
        gates=('CONNECT_SCREEN','EXCLUSIVE_UART_AND_SAFE_IDLE_CONFIRMED','SEND_IMAGE') if path.name.startswith('03') else ('ALLOW_MOTION','ARM_CURRENT','ALLOW_100MA','GEOMETRY_CONFIRMED','MANUAL_CLEAR_AND_REHOME')
        if path.name.startswith('04'):gates+=('LOAD_OVERLAY','SAFE_TO_RECONFIGURE','LOADED_PAIR_CONFIRMED')
        if any(values.get(gate) is not False for gate in gates):
            raise ValueError('unsafe/missing default testgate: '+path.name)
    nb = json.loads((board/'01_four_all_system.ipynb').read_text(encoding='utf-8'))
    assignments = {}
    for c in nb['cells']:
        if c['cell_type'] == 'code':
            tree = ast.parse(''.join(c['source']))
            if c.get('outputs') or c.get('execution_count') is not None:
                raise ValueError('outputs not cleared')
            for node in tree.body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            assignments[target.id] = node.value.value
    for gate in ('ALLOW_MOTION', 'ARM_CURRENT', 'ALLOW_100MA', 'GEOMETRY_CONFIRMED', 'MANUAL_CLEAR_AND_REHOME'):
        if assignments.get(gate) is not False:
            raise ValueError('unsafe default ' + gate)
    for required in ('USE_PL_AUTORANGE','USE_PL_RHO','RESELECT_RANGE_EVERY_POINT','FULL_RANGE_RESELECT_ON_RETRY'):
        if required not in assignments:raise ValueError('missing required parameter '+required)
    if assignments.get('USE_PL_AUTORANGE') is not True:raise ValueError('PL path must default enabled')
    retired=('PROBE_VOLTAGE_SCALE','HMI_FORWARD_VOLTAGE_DISPLAY_SCALE','HMI_REVERSE_VOLTAGE_DISPLAY_SCALE','PL_ABBA_CYCLES','GAN_MODE')
    if any(n in assignments for n in retired):raise ValueError('retired configuration returned')
    runtime_text='\n'.join(p.read_text(encoding='utf-8-sig') for p in _runtime_py_files())
    if 'probe_voltage_scale' in runtime_text:raise ValueError('retired gain API/metadata still present')
    if 'FPD_VERSION = 5' not in (board/'four_probe_sw/pl_autorange.py').read_text(encoding='utf-8'):raise ValueError('wrong PL driver')
    for name in ('web_live.py','hmi_auto_images.py','hmi_abba.py','hmi_image03.py','gan_profile.py'):
        if (board/name).exists():raise ValueError('retired module '+name)

    for path in files:
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    check_fp_dsp_structure()
    print('PASS_DELIVERY', len(files), 'files; PS/RTL mirrors, deploy anchor, fixed pair, UART115200, FP_DSP structure, five gates False; board evidence archived')


if __name__ == '__main__':
    verify()
