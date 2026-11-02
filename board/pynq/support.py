# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Offline register stand-in for FP_DSP; never accesses hardware."""
from four_probe_sw import pl_autorange as p

class FakeFpDsp:
    def __init__(self, model):
        self.model=model;self.regs={p.REG_ID:p.FPD_ID,p.REG_VERSION:p.FPD_VERSION,p.REG_CAPS:0x417}
        self.owned=False;self.starts=[];self.writes=[];self.force_busy=False;self.force_version=None
    def read(self,addr):
        if addr==p.REG_VERSION and self.force_version is not None:return self.force_version
        if addr==p.REG_STATUS:return self.regs.get(addr,0) | (p.STATUS_OWNED if self.owned else 0) | (p.STATUS_BUSY if self.force_busy else 0)
        return self.regs.get(addr,0)
    def write(self,addr,value):
        self.writes.append((addr,value))
        if addr!=p.REG_CONTROL:self.regs[addr]=value;return
        if value&p.CTRL_ABORT:self.regs[p.REG_STATUS]=0;return
        if value&p.CTRL_CLAIM:self.owned=True
        if value&p.CTRL_RELEASE:self.owned=False
        if value&p.CTRL_CLEAR:self.regs[p.REG_STATUS]=0
        if not value&p.CTRL_START:return
        mode=(value>>p.CTRL_MODE_SHIFT)&3;index=(value>>p.CTRL_RANGE_SHIFT)&3;self.starts.append((mode,index))
        if not self.owned:self.regs[p.REG_STATUS]=p.STATUS_DONE|p.STATUS_ERROR|(p.R_CONFIG_ERROR<<16);return
        cfg=p.AutorangeRegisters(**{k:self.regs[v[0]] for k,v in p.CONFIG_REGISTERS.items()})
        currents=tuple(self.regs[p.REG_IF_BASE+4*i]+self.regs[p.REG_IR_BASE+4*i] for i in range(4))
        run=p.simulate_run(cfg,currents,mode,index,self.model.window_mean)
        self.regs[p.RES_SELECT]=(run.selected_range or 0)|(run.tested_mask<<4)|(mode<<8)
        self.regs[p.RES_REASON]=run.reason|(run.flags<<8)
        self.regs[p.RES_WINDOWS]=run.windows[0]|(run.windows[1]<<16)
        for addr,v in [(p.RES_S,run.s_q8),(p.RES_E,run.e_q8),(p.RES_MF,run.mf_q8),(p.RES_MR,run.mr_q8),(p.RES_MF_FIRST,run.mf_first_q8),(p.RES_MF_LAST,run.mf_last_q8)]:self.regs[addr]=v&0xffffffff
        for i,(f,rv) in run.pilot.items():
            base=p.RES_PILOT_BASE+16*i;self.regs[base]=f&0xffffffff;self.regs[base+4]=rv&0xffffffff;self.regs[base+12]=100|(100<<16)
        if run.ok:
            for pol,base in enumerate(p.RES_AGG_BASE):
                center=self.regs[p.REG_CENTER_BASE+4*(pol*4+run.selected_range)]
                code=center+self.model.delta_code(run.selected_range,bool(pol));n=self.model.samples_per_window
                total=code*n;sq=code*code*n
                for offset,v in [(0,total&0xffffffff),(4,total>>32),(8,sq&0xffffffff),(12,sq>>32),(16,n),(20,(code<<16)|code)]:self.regs[base+offset]=v
        self.regs[p.REG_STATUS]=p.STATUS_DONE|(p.STATUS_RESULT_VALID if run.ok else p.STATUS_ERROR)|(run.reason<<16)|(run.flags<<24)

from types import SimpleNamespace
from pathlib import Path
class Uart:

    def __init__(self):
        self.commands = []
        self.pending = b''

    def send_command(self, command):
        self.commands.append(command)

    def read_available(self):
        data = self.pending
        self.pending = b''
        return data

    def discard_pending_rx(self):
        self.pending = b''

class Frontend:

    def __init__(self):
        self.off = 0

    def safe_off(self):
        self.off += 1
        return {'current_active': False}

class System:

    def __init__(self, on_range_selected, on_point, count=25, failure=None):
        self.range_callback = on_range_selected
        self.point_callback = on_point
        self.count = count
        self.failure = failure
        self.results = []
        self.last_error = None
        self.events = []
        self.saved = False

    def run_scan(self, mode, selected_point_index=None):
        self.range_callback(3, 0.0902501127046164, 0.08587838284413209)
        self.events.append('range')
        indices = [selected_point_index] if mode == 'single' else range(1, self.count + 1)
        for i in indices:
            if self.failure == i:
                self.last_error = 'capture failure'
                break
            row = {'point_index': 0 if i == 1 else i - 2 if i <= 9 else i - 10, 'ring': 0 if i == 1 else 1 if i <= 9 else 2, 'point_valid': True, 'model_error': None, 'range_index': 3, 'equivalent_current_a': 0.08806424777437424, 'forward_current_a': 0.0902501127046164, 'reverse_current_a': 0.08587838284413209, 'forward_voltage_v': 0.9 + i * 0.0001, 'reverse_voltage_v': 0.85 + i * 0.0001, 'combined_voltage_v': 0.88, 'combined_resistance_ohm': 10.0, 'sheet_resistance_ohm_sq': 47.0, 'resistivity_ohm_cm': 3.0, 'ndop_cm3': 1000000000000000.0, 'fd': 1.0, 'fw': 1.0, 'fsp': 1.0, 'forward_valid_samples': 300, 'reverse_valid_samples': 300}
            self.results.append(row)
            self.point_callback(row)
        return SimpleNamespace(completed=self.last_error is None, quality_ok=self.last_error is None, results=self.results, selected_range_index=3, error=self.last_error)

    def save_results(self, dest):
        self.saved = True
        Path(dest).mkdir(parents=True, exist_ok=True)
        return (Path(dest) / 'result.json', Path(dest) / 'result.csv')
