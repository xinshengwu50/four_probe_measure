# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""量程阶段显示：观察真实选档，不改变测量结果；仅使用统一UART接收者。"""
import json
import time
from pathlib import Path
from hmi_four_all import FourAllHmiService
from four_all_hmi_ui.hmi_single_point import MeasurementMode

class RangePictures:
    def __init__(self, uart, abort_check=None):
        self.uart=uart; self.abort_check=abort_check
        self.page=None; self.index=None; self.events=[]; self.selecting=False

    def _send(self, command):
        if self.abort_check is not None:self.abort_check()
        self.uart.send_command(command)

    @staticmethod
    def _validate(index):
        if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<=3:
            raise ValueError('量程灯索引必须为0..3整数')

    def _show(self, page, index):
        self._send('page %d'%page)
        for i in range(4):self._send('p%d.pic=%d'%(i,(68 if i==index else 64)+i))
        self.page=page;self.index=index

    def begin(self):
        self.events=[];self.selecting=True
        self._show(4,None)

    def changed(self,index):
        self._validate(index)
        if not self.selecting or self.page is None or self.index==index:return
        previous=self.index
        if previous is not None:self._send('p%d.pic=%d'%(previous,64+previous))
        self._send('p%d.pic=%d'%(index,68+index))
        self.index=index
        self.events.append(dict(event='configured',index=index,page=self.page,monotonic_s=time.monotonic()))
        print('[RANGE04] 实际量程配置完成 R%d -> p[%d].p%d.pic=%d'%(index,self.page,index,68+index),flush=True)

    def selected(self,index):
        self._validate(index)
        self._show(5,index);self.selecting=False
        self.events.append(dict(event='selected',index=index,page=5,monotonic_s=time.monotonic()))
        print('[RANGE04] 选档完成 R%d；第5页仅此档亮起（不是整场测量完成）'%index,flush=True)

    def save(self,path):
        Path(path).write_text(json.dumps(self.events,ensure_ascii=False,indent=2),encoding='utf-8')

class RangeFrontendProxy:
    """仅在configure成功返回且开电流时通知；关断/同档正反向不会假跑灯。"""
    def __init__(self, frontend, pictures, allowed=(0,1,2)):
        self.frontend=frontend;self.pictures=pictures;self.allowed=tuple(allowed)
    def __getattr__(self,name):return getattr(self.frontend,name)
    def configure(self,range_index,reverse=False,enable_current=True,
                  timeout_s=None,reconfigure_adc_before=True):
        if range_index not in self.allowed:raise PermissionError('04禁止此量程: R%s'%range_index)
        result=self.frontend.configure(range_index,reverse=reverse,enable_current=enable_current,
                    timeout_s=timeout_s,reconfigure_adc_before=reconfigure_adc_before)
        if enable_current:self.pictures.changed(range_index)
        return result

class RangeVisualService(FourAllHmiService):
    def __init__(self,*args,pictures,**kwargs):
        super().__init__(*args,**kwargs)
        self.pictures=pictures
    def run(self,config):
        self._validate(config)  # 安全门通过之后才改变界面/启动运动。
        # 先清除上次n0，避免进入第4页瞬间被旧完成标志跳走。
        self.writer.clear_done_flag(early_release=False,point_index=config.point_index)
        self.pictures.begin()
        try:return super().run(config)
        finally:
            self.output_dir.mkdir(parents=True,exist_ok=True)
            stamp=time.strftime('%Y%m%d_%H%M%S')
            self.pictures.save(self.output_dir/('range04_'+stamp+'.json'))
    def _range_selected(self,index,forward_a,reverse_a):
        # 04使用第4/5页显式导航，不由n0提前跳走，其他测量与结果回填仍复用原服务。
        previous=self.range_ready
        self.range_ready=True
        try:super()._range_selected(index,forward_a,reverse_a)
        except BaseException:
            self.range_ready=previous
            raise
        if self.pictures.selecting:
            self.pictures.selected(index)
            # 先写完第5页最终灯，再发布原HMI导航标志；不丢失n0跳数据页协议。
            self.writer.release_wait_page()


class RangePlProxy:
    """PL模式从已新增的实际ADC帧标签观察量程，复用run轮询，不另开UART线程。

    标签不是继电器边沿探针；Linux暂停可漏过很短档位，不补画虚假档位。
    """
    def __init__(self,driver,pictures):self.driver=driver;self.pictures=pictures
    def __getattr__(self,name):return getattr(self.driver,name)
    def run(self,mode,range_index=0,abort_check=None):
        # 仅跟踪本次run中新采样，避免把上一点的标签当成本次切档。
        baseline=self.driver.diagnostics()['sample_count']
        def poll():
            nonlocal baseline
            if abort_check is not None:abort_check()
            diag=self.driver.diagnostics()
            if diag['sample_count']!=baseline:
                baseline=diag['sample_count']
                if diag['last_label_valid']:
                    self.pictures.changed(int(diag['last_label']) & 3)
        return self.driver.run(mode,range_index,abort_check=poll)
