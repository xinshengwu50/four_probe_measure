#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Regenerate the generated block inside docs/register_map.md from the RTL.

The register map used to be maintained by hand and silently drifted: the head of
docs/register_map.md still described the M2-era `ads8681_axi_lite` peripheral
(VERSION 0x0002_0000) after `ALL_Final` had redefined the same addresses.

Everything that can be derived mechanically is now generated from
`hw/rtl/all/all_final.v` - the address table, the access direction (from which
case block the address appears in), the CONTROL write bits and the STATUS read
bits - plus the error-code tables and a "which PS module knows this address"
column built from the `REG_* = 0x..` constants of the PS modules.

Usage:
    python scripts/gen_register_map.py            # rewrite the generated block
    python scripts/gen_register_map.py --check    # exit 1 if it is out of date
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RTL = ROOT / 'src' / 'project' / 'hw' / 'rtl' / 'all' / 'all_final.v'
DOC = ROOT / 'report' / 'register_map.md'
PS_MODULES = sorted((ROOT / 'src' / 'project' / 'sw' / 'pynq' / 'four_probe_sw').glob('*.py'))

BEGIN = '<!-- BEGIN GENERATED: 寄存器映射'
END = '<!-- END GENERATED -->'


def _case_block(text: str, case_header: str) -> str:
    """Return the text of a `case (<header>) ... endcase` block (no nesting)."""
    start = text.index(case_header)
    end = text.index('endcase', start)
    return text[start:end]


def _sub_block(block: str, label: str) -> str:
    """Return the text of one `label: begin ... end` case item."""
    m = re.search(r'^\s*%s\s*:' % re.escape(label), block, re.M)
    if not m:
        return ''
    start = m.end()
    nxt = re.search(r'^\s*AXI_REG_\w+\s*:', block[start:], re.M)
    return block[start:start + (nxt.start() if nxt else len(block))]


def collect() -> str:
    rtl = RTL.read_text(encoding='utf-8')

    regs = {}
    for m in re.finditer(
            r"localparam \[11:0\] (AXI_REG_\w+)\s*=\s*(?:8'h([0-9A-Fa-f]{2})|12'h([0-9A-Fa-f]{3}));",
            rtl):
        addr = int(m.group(2), 16) if m.group(2) else int(m.group(3), 16)
        regs[m.group(1)] = addr

    write_case = _case_block(rtl, 'case (axi_awaddr_reg[11:0])')
    read_case = _case_block(rtl, 'case (S_AXI_ARADDR[11:0])')
    writable = set(re.findall(r'^\s*(AXI_REG_\w+)\s*:', write_case, re.M))
    readable = set(re.findall(r'^\s*(AXI_REG_\w+)\s*:', read_case, re.M))

    control_bits = re.findall(r'axi_wdata_reg\[(\d+)\]\)\s*([A-Za-z_]\w*)',
                              _sub_block(write_case, 'AXI_REG_CONTROL'))
    status_bits = re.findall(r'axi_rdata_reg\[(\d+)\]\s*<=\s*([^;]+);',
                             _sub_block(read_case, 'AXI_REG_STATUS'))

    errors = {}
    for m in re.finditer(r"localparam (R_ERR_\w+|Z_ERR_\w+|MEAS_ERR_\w+)\s*=\s*\d*'d(\d+);", rtl):
        errors.setdefault(m.group(1).split('_')[0], []).append((m.group(1), int(m.group(2))))

    ps_owner = {}
    for p in PS_MODULES:
        for m in re.finditer(r'^(REG_\w+)\s*=\s*(0x[0-9A-Fa-f_]+|[0-9_]+)', p.read_text(encoding='utf-8'), re.M):
            ps_owner.setdefault(int(m.group(2).replace("_", ""), 0), []).append('%s:%s' % (m.group(1), p.name))

    out = []
    out.append('<!-- BEGIN GENERATED: 寄存器映射（由 scripts/gen_register_map.py 从 hw/rtl/all/all_final.v 生成，请勿手工编辑；%d 个寄存器）-->' % len(regs))
    out.append('')
    out.append('> Counting rule: this generated block contains %d unique AXI_REG addresses; '
               'manual tables elsewhere may repeat the same address under alias names.' % len(regs))
    out.append('')
    out.append('### 寄存器总表')
    out.append('')
    out.append('| 偏移 | RTL 名称 | 访问 | PS 常量（模块） |')
    out.append('|---:|---|---|---|')
    for name, addr in sorted(regs.items(), key=lambda kv: kv[1]):
        access = []
        if name in readable:
            access.append('R')
        if name in writable:
            access.append('W')
        owners = ps_owner.get(addr, [])
        if owners:
            names = sorted({o.split(':')[0] for o in owners})
            mods = sorted({o.split(':')[1] for o in owners})
            ps = '%s\n(%s)' % (' / '.join(names), ', '.join(mods))
            ps = ps.replace('\n', ' ')
        else:
            ps = '—'
        out.append('| `0x%03X` | `%s` | %s | %s |' % (addr, name, '/'.join(access) or '?', ps))
    out.append('')
    out.append('> 访问方向由该地址是否出现在 AXI 写译码 / 读译码的 case 项推出；')
    out.append('> `PS 常量` 列由 `sw/four_probe_sw/*.py` 的 `REG_* = 0x..` 汇总，')
    out.append('> `—` 表示当前 PS 未直接引用（可能由其它模块或仅诊断用）。')
    out.append('')
    out.append('### `0x00 CONTROL` 写位')
    out.append('')
    out.append('| bit | 目标信号 |')
    out.append('|---:|---|')
    for bit, sig in sorted(((int(b), s) for b, s in control_bits)):
        out.append('| %d | `%s` |' % (bit, sig))
    out.append('')
    out.append('### `0x04 STATUS` 读位')
    out.append('')
    out.append('| bit | 信号 |')
    out.append('|---:|---|')
    for bit, sig in sorted(((int(b), s.strip()) for b, s in status_bits)):
        out.append('| %d | `%s` |' % (bit, sig))
    out.append('')
    out.append('### 轴错误码（RTL localparam）')
    out.append('')
    for axis in ('R', 'Z', 'MEAS'):
        if axis not in errors:
            continue
        out.append('| %s | 值 |' % axis)
        out.append('|---|---:|')
        for name, val in sorted(errors[axis], key=lambda kv: kv[1]):
            out.append('| `%s` | %d |' % (name, val))
        out.append('')
    out.append(END)
    return '\n'.join(out) + '\n'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true',
                    help='only verify that the generated block is current')
    args = ap.parse_args()

    block = collect()
    text = DOC.read_text(encoding='utf-8')
    i = text.find(BEGIN[:40])
    j = text.find(END)
    if i < 0 or j < 0 or j < i:
        print('ERROR: generated markers not found in %s' % DOC, file=sys.stderr)
        return 2
    j += len(END)
    current = text[i:j] + '\n'
    if current == block:
        print('OK: %s is up to date' % DOC)
        return 0
    if args.check:
        print('OUT OF DATE: %s differs from the RTL; run scripts/gen_register_map.py'
              % DOC, file=sys.stderr)
        return 1
    with open(DOC, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text[:i] + block + text[j:])
    print('updated %s (%d registers)' % (DOC, block.count('`AXI_REG_') or 0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
