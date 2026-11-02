# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Hardware test utility for the custom relay current-source PCB.

Run this script on PYNQ after the matching .bit/.hwh files are present.
The script performs register-level checks and prints expected measurements.
It cannot read the DAC analog output, so DAC_OUT, VSET, coil voltages and
currents must be measured externally.
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path
try:
    from pynq import MMIO, Overlay
except ImportError:
    MMIO = None
    Overlay = None
try:
    from analog_frontend import AnalogFrontendController, RANGE_CURRENT_LABELS
except ImportError:
    from sw.four_probe_sw.analog_frontend import AnalogFrontendController, RANGE_CURRENT_LABELS
try:
    from final_four_probe_system import EXPECTED_PL_VERSION as EXPECTED_VERSION
except ImportError:
    from sw.four_probe_sw.final_four_probe_system import EXPECTED_PL_VERSION as EXPECTED_VERSION
REG_VERSION = 16
REG_DAC_CODE = 216
REG_DAC_STATUS = 224
REG_DAC_SEQ = 228
REG_ANALOG_SEQ = 232
RELAY_NAMES = ('RANGE0 / 0.1mA / RELAY1', 'RANGE1 / 1mA / RELAY2', 'RANGE2 / 10mA / RELAY3', 'RANGE3 / 100mA / RELAY4', 'POL_I / RELAY5', 'POL_V / RELAY6')

def parse_int(value):
    return int(value, 0)

def find_overlay_pair(explicit_bitstream=None):
    if explicit_bitstream:
        bit_path = Path(explicit_bitstream).expanduser().resolve()
        hwh_path = bit_path.with_suffix('.hwh')
        if not bit_path.is_file():
            raise FileNotFoundError('bitstream not found: %s' % bit_path)
        if not hwh_path.is_file():
            raise FileNotFoundError('matching hwh not found: %s' % hwh_path)
        return (bit_path, hwh_path)
    roots = [Path.cwd(), Path('/home/xilinx/jupyter_notebooks/four_probe_pynq/all_design'), Path('/home/xilinx/jupyter_notebooks/four_probe_pynq'), Path('/home/xilinx/jupyter_notebooks')]
    checked = []
    seen = set()
    for root in roots:
        root = root.expanduser().resolve()
        if root in seen or not root.is_dir():
            continue
        seen.add(root)
        checked.append(str(root))
        for bit_path in sorted(root.glob('*.bit')):
            hwh_path = bit_path.with_suffix('.hwh')
            if hwh_path.is_file():
                return (bit_path, hwh_path)
    raise FileNotFoundError('No matching .bit/.hwh pair found. Checked: %s' % checked)

def make_controller(bitstream=None, ip_name=None, timeout_s=2.0):
    if MMIO is None or Overlay is None:
        raise RuntimeError('pynq package is required; run this script on the PYNQ board')
    bit_path, hwh_path = find_overlay_pair(bitstream)
    print('bitstream:', bit_path)
    print('hwh      :', hwh_path)
    overlay = Overlay(str(bit_path))
    names = [ip_name] if ip_name else [name for name in overlay.ip_dict if any((token in name.lower() for token in ('all_final', 'allfinal', 'all_'))) and 'phys_addr' in overlay.ip_dict[name] and ('addr_range' in overlay.ip_dict[name])]
    verified = []
    for name in names:
        info = overlay.ip_dict[name]
        addr = int(info['phys_addr'])
        size = min(int(info['addr_range']), 65536)
        mmio = MMIO(addr, size)
        version = int(mmio.read(REG_VERSION))
        print('%s: VERSION=0x%08X phys=0x%08X range=0x%X' % (name, version, addr, size))
        if version == EXPECTED_VERSION:
            verified.append((name, mmio))
    if len(verified) != 1:
        raise RuntimeError('Expected one ALL_Final IP, found %d' % len(verified))
    name, mmio = verified[0]
    print('using:', name)
    return AnalogFrontendController(mmio, timeout_s=timeout_s)

def print_status(controller):
    status = controller.status()
    print('analog status:', status)
    print('dac status   :', controller.dac_status())
    print('dac code     : 0x%04X' % (controller.read(REG_DAC_CODE) & 65535))
    print('dac seq      : %d' % (controller.read(REG_DAC_SEQ) & 65535))
    print('analog seq   : %d' % (controller.read(REG_ANALOG_SEQ) & 65535))

def prompt_continue(pause, text):
    if pause:
        input(text + ' Press Enter to continue...')

def run_dac(args, controller):
    controller.safe_off()
    voltages = [0.0, 0.5, 1.0, 1.5, 2.5] if args.sweep else [args.voltage]
    for voltage in voltages:
        seq_before = controller.read(REG_DAC_SEQ) & 65535
        code = controller.set_dac_voltage(voltage, timeout_s=args.timeout)
        seq_after = controller.read(REG_DAC_SEQ) & 65535
        print('\nDAC request: %.6f V code=0x%04X' % (voltage, code))
        print('DAC status :', controller.dac_status())
        print('DAC seq    : %d -> %d' % (seq_before, seq_after))
        print('Expected external measurement: DAC_OUT and VSET about %.6f V' % voltage)
        prompt_continue(args.pause, 'Measure DAC_OUT and VSET.')

def run_relays(args, controller):
    controller.safe_off()
    masks = [args.mask] if args.mask is not None else [1 << index for index in range(6)]
    for mask in masks:
        controller.enter_direct_test(relay_mask=mask)
        names = [RELAY_NAMES[index] for index in range(6) if mask & 1 << index]
        print('\nRelay test mask=0x%02X: %s' % (mask, ', '.join(names)))
        print('Expected: target relay coil about 5 V; all other relay coils about 0 V.')
        prompt_continue(args.pause, 'Measure relay coil and contacts.')
    controller.exit_direct_test()

def run_current(args, controller):
    controller.safe_off()
    if args.use_dac:
        controller.set_dac_voltage(args.voltage, timeout_s=args.timeout)
    else:
        print('PL DAC disabled: VSET is assumed to be the external fixed 1.0 V divider.')
    ranges = range(4) if args.all_ranges else [args.range]
    for range_index in ranges:
        status = controller.configure(range_index, reverse=args.reverse, enable_current=True, timeout_s=args.timeout)
        label = RANGE_CURRENT_LABELS[range_index]
        expected_a = args.voltage / (10000.0, 1000.0, 100.0, 10.0)[range_index]
        print('\nRange %d / %s, reverse=%s' % (range_index, label, args.reverse))
        print('Expected current about %.9g A' % expected_a)
        print('Analog status:', status)
        prompt_continue(args.pause, 'Measure current through the dummy load.')
    controller.safe_off()

def run_safe(controller):
    print('safe state:', controller.safe_off())

def build_parser():
    parser = argparse.ArgumentParser(description='PYNQ hardware test for the custom analog PCB')
    parser.add_argument('--bitstream', help='path to matching .bit file')
    parser.add_argument('--ip-name', help='ALL_Final IP name in overlay.ip_dict')
    parser.add_argument('--timeout', type=float, default=2.0, help='register sequence timeout in seconds')
    parser.add_argument('--no-pause', dest='pause', action='store_false', help='do not wait for Enter')
    parser.set_defaults(pause=True)
    sub = parser.add_subparsers(dest='stage', required=True)
    sub.add_parser('status')
    sub.add_parser('safe')
    dac = sub.add_parser('dac')
    dac.add_argument('--voltage', type=float, default=1.0)
    dac.add_argument('--sweep', action='store_true')
    relay = sub.add_parser('relay')
    relay.add_argument('--mask', type=parse_int, help='relay mask, for example 0x01 or 0x20')
    current = sub.add_parser('current')
    current.add_argument('--range', type=int, default=0, choices=(0, 1, 2, 3))
    current.add_argument('--all-ranges', action='store_true')
    current.add_argument('--voltage', type=float, default=1.0)
    current.add_argument('--reverse', action='store_true')
    current.add_argument('--use-dac', action='store_true', help='drive DAC through PL before current test')
    return parser

def main(argv=None):
    args = build_parser().parse_args(argv)
    controller = make_controller(args.bitstream, args.ip_name, args.timeout)
    try:
        if args.stage == 'status':
            print_status(controller)
        elif args.stage == 'safe':
            run_safe(controller)
        elif args.stage == 'dac':
            run_dac(args, controller)
        elif args.stage == 'relay':
            run_relays(args, controller)
        elif args.stage == 'current':
            run_current(args, controller)
        else:
            raise RuntimeError('unsupported stage: %s' % args.stage)
    finally:
        try:
            controller.safe_off()
            print('final safe state:', controller.status())
        except Exception as exc:
            print('WARNING: final safe_off failed:', exc, file=sys.stderr)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
