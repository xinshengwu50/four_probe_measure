# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""真实Rs→page2全局25色块；不拥有电机/ADC，不计算或修正物理结果。"""
import math
CONTROLS=('t0','t1')+tuple('t%d'%i for i in range(3,26))
# 方形示意：中心1；内圈从上方开始顺时针2..9；外圈从上方中央开始顺时针10..25。
GRID=((24,25,10,11,12),(23,9,2,3,13),(22,8,1,4,14),(21,7,6,5,15),(20,19,18,17,16))
POINT_TO_CELL={point:row*5+col for row,line in enumerate(GRID) for col,point in enumerate(line)}

def format_rs(value):
    if value==0:return '0.00'
    fixed='%.2f'%value
    if .01<=value<1000 and len(fixed)<=6:return fixed
    sci=('%.1e'%value).replace('e+','e').replace('e-0','e-').replace('e0','e')
    if len(sci)<=6:return sci
    return ('%.0e'%value).replace('e+','e').replace('e-0','e-').replace('e0','e')

def color(value,low,high):
    from heatmap_field import blue_color
    rgb=blue_color(value,low,high)
    r,g,b=rgb;bg=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
    return bg,0 if .299*r+.587*g+.114*b>145 else 65535

class RealHeatmap:
    def __init__(self,uart,abort_check=None,page="page2"):
        self.page=page;self.uart=uart;self.abort_check=abort_check;self.values={};self.sent={}
    def _send(self,target,value):
        if self.sent.get(target)==value:return
        if self.abort_check is not None:self.abort_check()
        self.uart.send_command(target+'='+str(value));self.sent[target]=value
    def begin(self):
        self.values={};self.sent={};self.render()
    def update(self,index,rs,valid=True):
        if isinstance(index,bool) or index not in POINT_TO_CELL:raise ValueError('heatmap index must be1..25')
        ok=valid and isinstance(rs,(int,float)) and not isinstance(rs,bool) and math.isfinite(rs) and rs>=0
        self.values[index]=float(rs) if ok else None
        self.render()
    def render(self):
        valid=[v for v in self.values.values() if v is not None]
        low=min(valid) if valid else 0.;high=max(valid) if valid else 0.
        for point,cell in POINT_TO_CELL.items():
            target=self.page+'.'+CONTROLS[cell]
            if point not in self.values:bg,fg,label=33808,65535,'--'
            elif self.values[point] is None:bg,fg,label=16904,65535,'ERR'
            else:
                bg,fg=color(self.values[point],low,high);label=format_rs(self.values[point])
            text='%d\\r%s'%(point,label)
            if len(text)>10:raise ValueError('HMI text length exceeds10')
            self._send(target+'.bco',bg);self._send(target+'.pco',fg)
            self._send(target+'.txt','"'+text+'"')
