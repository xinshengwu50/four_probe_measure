# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Complete real-scan CSV history. No ADC, motion or Overlay operations."""
from hmi_real_heatmap import RealHeatmap
from dataclasses import dataclass, asdict, replace
from datetime import datetime
from pathlib import Path
import csv
import json
import math
import os
import re
import tempfile
import uuid

from four_all_hmi_ui.hmi_single_point import MeasurementConfig, MeasurementMode, SampleKind
from four_all_hmi_ui.hmi_bindings import nominal_range_ma
from hmi_history_protocol import HistoryPoint, _render_commands, _data_page, _indices, _HistoryWriter
from four_all_hmi_ui.hmi_single_point import Hmi22Writer

REAL_HISTORY_VERSION = 1
NAME = re.compile(r'real_(\d{6,})_([0-9_]+)_([0-9a-f]{8})\.csv$')
FIELDS = ['schema_version', 'data_source', 'sequence', 'record_id', 'metadata_json', 'point_json']
SOURCE = 'REAL_MEASUREMENT'

@dataclass(frozen=True)
class RealSnapshot:
    sequence: int
    record_id: str
    created_at: str
    config: MeasurementConfig
    rows: tuple
    raw_rows: tuple
    selected_range_index: int
    temperature_c: float
    humidity_pct: float
    alpha: float
    diameter_over_spacing: float
    fd: float
    fw: float
    fsp: float


def _finite(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('invalid ' + name)
    if positive and value <= 0:
        raise ValueError('nonpositive ' + name)
    return value


def _index(row):
    ring, point = row['ring'], row['point_index']
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (ring, point)):
        raise ValueError('invalid point index')
    if ring == 0 and point == 0:return 1
    if ring == 1 and 0 <= point < 8:return 2 + point
    if ring == 2 and 0 <= point < 16:return 10 + point
    raise ValueError('invalid ring/point')


def validate(snapshot):
    snapshot.config.validate()
    match = NAME.fullmatch(snapshot.record_id + '.csv')
    if not match or int(match.group(1)) != snapshot.sequence or snapshot.sequence < 1:
        raise ValueError('invalid real history identity')
    if snapshot.config.current_ma != nominal_range_ma(snapshot.selected_range_index):
        raise ValueError('range/display mismatch')
    if snapshot.config.measurement_mode not in (MeasurementMode.SINGLE_POINT, MeasurementMode.NINE_POINT, MeasurementMode.TWENTY_FIVE_POINT):
        raise ValueError('unsupported mode')
    if [_index(row) for row in snapshot.raw_rows] != _indices(snapshot.config):
        raise ValueError('incomplete/duplicate/out-of-order history')
    row_ranges = []
    for row in snapshot.raw_rows:
        if row.get('point_valid') is not True or row.get('model_error') is not None:
            raise ValueError('invalid measurement point')
        range_index = row.get('range_index')
        if isinstance(range_index, bool) or not isinstance(range_index, int) or range_index not in range(4):
            raise ValueError('invalid range index')
        row_ranges.append(range_index)
        for key in ('forward_voltage_v','reverse_voltage_v','combined_voltage_v','combined_resistance_ohm',
                    'sheet_resistance_ohm_sq','resistivity_ohm_cm','fd','fw','fsp'):
            _finite(row[key],key)
        for key in ('forward_current_a','reverse_current_a','equivalent_current_a'):
            _finite(row[key],key,positive=True)
        if row['ndop_cm3'] is not None:
            # Existing non-Si model uses0 as NOT_ESTIMATED, not a measured zero density.
            if not (snapshot.config.model_sample_kind == SampleKind.SILICON) and row['ndop_cm3'] == 0:
                _finite(row['ndop_cm3'],'doping')
            else:
                _finite(row['ndop_cm3'],'doping',positive=True)
    if snapshot.selected_range_index not in row_ranges:
        raise ValueError('selected range absent from point history')
    for name in ('temperature_c','humidity_pct','alpha','diameter_over_spacing','fd','fw','fsp'):
        _finite(getattr(snapshot,name),name)
    return snapshot


def _snapshot(sequence, identity, metadata, raw_rows):
    cfg_data = dict(metadata['config'])
    cfg_data['measurement_mode'] = MeasurementMode(cfg_data['measurement_mode'])
    cfg_data['sample_kind'] = SampleKind(cfg_data['sample_kind'])
    cfg = MeasurementConfig(**cfg_data)
    rows = tuple(HistoryPoint(_index(r),r['forward_voltage_v']*1000,r['reverse_voltage_v']*1000,
                    r['combined_voltage_v']*1000,r['sheet_resistance_ohm_sq'],r['resistivity_ohm_cm'],r['ndop_cm3'])
                 for r in raw_rows)
    last = raw_rows[-1]
    return validate(RealSnapshot(sequence,identity,metadata['created_at'],cfg,rows,tuple(raw_rows),
        metadata['selected_range_index'],metadata['temperature_c'],metadata['humidity_pct'],
        cfg.thickness_um*.001/cfg.probe_spacing_mm,cfg.diameter_mm/cfg.probe_spacing_mm,
        last['fd'],last['fw'],last['fsp']))


class RealHistoryWriter(_HistoryWriter):
    def _val(self,target,value):
        value=int(value)
        if not -2147483648<=value<=2147483647:raise ValueError('value outside HMI int32 range')
        Hmi22Writer._val(self,target,value)


class RealHistoryStore:
    def __init__(self,directory):self.directory=Path(directory).resolve()
    def _files(self):
        if not self.directory.exists():return []
        files=[]
        for path in self.directory.glob('real_*.csv'):
            match=NAME.fullmatch(path.name)
            if match and path.is_file() and path.resolve().parent==self.directory:
                files.append((int(match.group(1)),path.name,path))
        return [p for _,_,p in sorted(files,reverse=True)]
    def list_history(self):
        return [dict(slot=i+1,file=str(p),sequence=int(NAME.fullmatch(p.name).group(1)))
                for i,p in enumerate(self._files()[:4])]
    def save_complete(self,config,raw_rows,selected_range_index):
        if not raw_rows:
            raise ValueError('empty measurement history')
        if selected_range_index is None:
            selected_range_index=raw_rows[-1].get('range_index')
        files=self._files();sequence=int(NAME.fullmatch(files[0].name).group(1))+1 if files else 1
        identity='real_%06d_%s_%s'%(sequence,datetime.now().strftime('%Y%m%d_%H%M%S_%f'),uuid.uuid4().hex[:8])
        cfg=replace(config,current_ma=nominal_range_ma(selected_range_index))
        cfg_dict=asdict(cfg);cfg_dict['measurement_mode']=int(cfg.measurement_mode);cfg_dict['sample_kind']=cfg.sample_kind.value
        # Environment is the same default displayed live; it is NOT a sensor reading.
        from four_all_hmi_ui.hmi_single_point import DEFAULT_TEMPERATURE_C, DEFAULT_HUMIDITY_PCT
        meta=dict(config=cfg_dict,created_at=datetime.now().astimezone().isoformat(),
                  selected_range_index=selected_range_index,temperature_c=DEFAULT_TEMPERATURE_C,
                  humidity_pct=DEFAULT_HUMIDITY_PCT,environment_source='DEFAULT_NOT_MEASURED',completed=True)
        _snapshot(sequence,identity,meta,raw_rows)  # validate everything before publish
        encoded=json.dumps(meta,ensure_ascii=False,allow_nan=False,sort_keys=True)
        self.directory.mkdir(parents=True,exist_ok=True)
        target=self.directory/(identity+'.csv');tmp=None
        try:
            with tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='',dir=self.directory,suffix='.tmp',delete=False) as f:
                tmp=Path(f.name);writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
                for row in raw_rows:
                    writer.writerow(dict(schema_version=1,data_source=SOURCE,sequence=sequence,record_id=identity,
                        metadata_json=encoded,point_json=json.dumps(row,ensure_ascii=False,allow_nan=False)))
                f.flush();os.fsync(f.fileno())
            if target.exists():raise FileExistsError(target)
            os.replace(tmp,target);tmp=None
        finally:
            if tmp is not None:tmp.unlink(missing_ok=True)
        return target
    def load_recent(self,slot=1):
        if isinstance(slot,bool) or not isinstance(slot,int) or not 1<=slot<=4:raise ValueError('history slot must be 1..4')
        files=self._files()
        if slot>len(files):raise FileNotFoundError('no complete real history in slot %d'%slot)
        path=files[slot-1]
        if path.resolve().parent!=self.directory or path.stat().st_size>1024*1024:raise ValueError('unsafe/oversized history')
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if reader.fieldnames!=FIELDS:raise ValueError('unsupported real CSV schema')
            rows=[]
            for row in reader:
                if len(rows)>=25 or None in row or any(v is None for v in row.values()):raise ValueError('invalid CSV row')
                rows.append(row)
        if not rows:raise ValueError('empty history CSV')
        first=rows[0]
        if first['schema_version']!='1' or first['data_source']!=SOURCE or first['record_id']!=path.stem:
            raise ValueError('not matching real history CSV')
        if any(any(r[k]!=first[k] for k in FIELDS[:-1]) for r in rows):raise ValueError('inconsistent CSV metadata')
        meta=json.loads(first['metadata_json'])
        if meta.get('completed') is not True:raise ValueError('partial history')
        return _snapshot(int(first['sequence']),path.stem,meta,[json.loads(r['point_json']) for r in rows])
    def restore(self,uart,slot=1,report=False):
        snapshot=self.load_recent(slot)  # disk reread; no current scan dependence
        commands=_render_commands(snapshot,report=report,validator=validate,writer_class=RealHistoryWriter)
        # Prebuild all heatmap commands before any UART TX; no measurement/motion.
        class Buffer:
            def __init__(self):self.commands=[]
            def send_command(self,cmd):self.commands.append(cmd)
        buffer=Buffer();heatmap=RealHeatmap(buffer);heatmap.begin()
        for row in snapshot.rows:heatmap.update(row.index,row.sheet_resistance_ohm_sq)
        rho_heatmap=RealHeatmap(buffer,page="p[27]");rho_heatmap.begin()
        for row in snapshot.raw_rows:
            index=1 if row["ring"]==0 else 2+row["point_index"] if row["ring"]==1 else 10+row["point_index"]
            rho_heatmap.update(index,row.get("resistivity_ohm_cm"),valid=row.get("point_valid") is True)
        # Keep final assignment for each target; no intermediate gray/recolor flood on recall.
        final={}
        for cmd in buffer.commands:
            key,value=cmd.split('=',1);final[key]=value
        commands.extend(key+'='+value for key,value in final.items())
        for cmd in commands:uart.send_command(cmd)
        return dict(status='RESTORED',display_only=True,synthetic=False,sequence=snapshot.sequence,
                    points_written=len(snapshot.rows),target_page=8 if report else _data_page(snapshot.config))
