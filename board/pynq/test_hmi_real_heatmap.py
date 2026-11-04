# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sw'/'pynq'))
from hmi_real_heatmap import RealHeatmap,POINT_TO_CELL,format_rs
class Uart:
    def __init__(self):self.commands=[]
    def send_command(self,c):self.commands.append(c)
class HeatTests(unittest.TestCase):
    def test_complete_layout_and_limits(self):
        self.assertEqual(len(set(POINT_TO_CELL.values())),25)
        self.assertEqual(POINT_TO_CELL[1],12)
        u=Uart();h=RealHeatmap(u);h.begin()
        for i in range(1,26):h.update(i,10+i,valid=True)
        self.assertEqual(len(h.values),25)
        self.assertTrue(any('page2.t13.txt="1' in c for c in u.commands))
        self.assertFalse(any(c.startswith('page ') or c.startswith('ref ') for c in u.commands))
        for c in u.commands:
            if '.txt=' in c:self.assertLessEqual(len(c.split('"')[1]),10)
            if '.bco=' in c or '.pco=' in c:self.assertTrue(0<=int(c.split('=')[1])<=65535)
    def test_missing_invalid_zero_uniform_and_rounding(self):
        u=Uart();h=RealHeatmap(u);h.begin();h.update(1,None,valid=False)
        self.assertIn('page2.t13.txt="1\\rERR"',u.commands)
        h.update(2,0,valid=True);h.update(3,0,valid=True)
        for x in [0,1e-200,1e200,1.2345,999999,1000000000000]:self.assertLessEqual(len(format_rs(x)),6)
        self.assertNotEqual(format_rs(1e-8),'0.00')
    def test_recolors_when_minmax_changes_and_skips_duplicate(self):
        u=Uart();h=RealHeatmap(u);h.begin();h.update(1,10);u.commands=[]
        h.update(2,20);self.assertTrue(any(c.startswith('page2.t13.bco=') for c in u.commands))
        u.commands=[];h.update(2,20);self.assertEqual(u.commands,[])
    def test_abort_check_prevents_further_uart(self):
        def abort():raise RuntimeError('RST')
        u=Uart();h=RealHeatmap(u,abort_check=abort)
        with self.assertRaises(RuntimeError):h.begin()
        self.assertEqual(u.commands,[])
if __name__=='__main__':unittest.main()
