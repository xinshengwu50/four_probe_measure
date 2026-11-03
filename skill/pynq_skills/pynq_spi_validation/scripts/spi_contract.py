"""SPI digital trace contracts. No MMIO, GPIO, Overlay or pin operations."""
from dataclasses import dataclass,asdict
import argparse,csv,json,math
from pathlib import Path


def _int(v,name,minimum=0):
    if isinstance(v,bool) or not isinstance(v,int) or v<minimum:raise ValueError('invalid '+name)
    return v

@dataclass(frozen=True)
class SpiConfig:
    clock_hz:int=50_000_000
    sck_hz:int=1_000_000
    mode:int=0
    frame_bits:int=8
    bit_order:str='msb'
    cs_setup_cycles:int=2
    cs_hold_cycles:int=2
    data_setup_cycles:int=1
    data_hold_cycles:int=1
    max_half_cycles:int=65535
    def __post_init__(self):
        for key in ('clock_hz','sck_hz','frame_bits','cs_setup_cycles','cs_hold_cycles','data_setup_cycles','data_hold_cycles','max_half_cycles'):_int(getattr(self,key),key,1)
        _int(self.mode,'mode')
        if self.mode not in range(4) or self.frame_bits>4096 or self.bit_order not in ('msb','lsb'):raise ValueError('invalid SPI format')
        if self.clock_hz>1_000_000_000_000 or self.sck_hz>self.clock_hz/2:raise ValueError('clock cannot produce requested SCK')
        d=math.ceil(self.clock_hz/(2*self.sck_hz))
        if d>self.max_half_cycles or d<max(self.data_setup_cycles,self.data_hold_cycles):raise ValueError('divider/setup not realizable')
    @property
    def cpol(self):return self.mode>>1
    @property
    def cpha(self):return self.mode&1


def divider(config):
    half=math.ceil(config.clock_hz/(2*config.sck_hz))
    return dict(half_cycles=half,actual_sck_hz=config.clock_hz/(2*half),requested_sck_hz=config.sck_hz)


def _bits(value,c):
    _int(value,'word')
    if value>=1<<c.frame_bits:raise ValueError('word exceeds frame bits')
    shifts=range(c.frame_bits-1,-1,-1) if c.bit_order=='msb' else range(c.frame_bits)
    return [(value>>s)&1 for s in shifts]


def build_trace(c,tx,rx=0):
    a,b=_bits(tx,c),_bits(rx,c);half=divider(c)['half_cycles'];level=c.cpol
    trace=[dict(t_cycles=0,cs=1,sck=level,mosi=0,miso=0)]
    trace.append(dict(t_cycles=1,cs=0,sck=level,mosi=a[0] if not c.cpha else 0,miso=b[0] if not c.cpha else 0))
    t=1+max(c.cs_setup_cycles,c.data_setup_cycles if not c.cpha else 0)
    for i in range(c.frame_bits):
        if c.cpha:
            trace.append(dict(t_cycles=t,cs=0,sck=1-level,mosi=a[i],miso=b[i]));t+=half
            trace.append(dict(t_cycles=t,cs=0,sck=level,mosi=a[i],miso=b[i]));t+=half
        else:
            trace.append(dict(t_cycles=t,cs=0,sck=1-level,mosi=a[i],miso=b[i]));t+=half
            trace.append(dict(t_cycles=t,cs=0,sck=level,mosi=a[min(i+1,c.frame_bits-1)],miso=b[min(i+1,c.frame_bits-1)]));t+=half
    last=trace[-1];trace.append(dict(t_cycles=last['t_cycles']+c.cs_hold_cycles,cs=1,sck=level,mosi=last['mosi'],miso=last['miso']))
    return trace


def validate_trace(trace,c,expected_tx=None,expected_rx=None):
    if expected_tx is not None:_bits(expected_tx,c)
    if expected_rx is not None:_bits(expected_rx,c)
    events=list(trace);flags=[];samples=[];edges=[];fall=None;rise=None;transactions=0;last_sample=None;last_changes={'mosi':None,'miso':None}
    if not events:return dict(passed=False,quality_flags=['EMPTY_TRACE'],transmitted=None,received=None)
    try:
        for e in events:
            _int(e['t_cycles'],'time')
            for k in ('cs','sck','mosi','miso'):
                _int(e[k],k)
                if e[k] not in (0,1):raise ValueError('logic levels must be0/1')
        if any(y['t_cycles']<=x['t_cycles'] for x,y in zip(events,events[1:])):raise ValueError('times must increase')
    except (ValueError,KeyError) as exc:return dict(passed=False,quality_flags=['INVALID_TRACE: '+str(exc)],transmitted=None,received=None)
    previous=events[0]
    if previous['cs']!=1 or previous['sck']!=c.cpol:flags.append('INITIAL_IDLE_INVALID')
    for k in last_changes:last_changes[k]=previous['t_cycles']
    for e in events[1:]:
        t=e['t_cycles']
        for k in last_changes:
            if e[k]!=previous[k]:
                if last_sample is not None and t-last_sample<c.data_hold_cycles:flags.append('DATA_HOLD_SHORT')
                last_changes[k]=t
        if previous['cs']==1 and e['cs']==0:
            fall=t;transactions+=1
            if e['sck']!=c.cpol:flags.append('CS_ASSERT_CLOCK_NOT_IDLE')
        if previous['cs']==0 and e['cs']==1:
            rise=t
            if not edges or t-edges[-1]['t_cycles']<c.cs_hold_cycles:flags.append('CS_HOLD_SHORT')
            if e['sck']!=c.cpol:flags.append('CS_RELEASE_CLOCK_NOT_IDLE')
        if e['sck']!=previous['sck']:
            if previous['cs']!=0 or e['cs']!=0:flags.append('CLOCK_OUTSIDE_CS')
            else:
                if not edges and (fall is None or t-fall<c.cs_setup_cycles):flags.append('CS_SETUP_SHORT')
                if edges and t-edges[-1]['t_cycles']<divider(c)['half_cycles']:flags.append('SCK_TOO_FAST')
                edges.append(e)
                leading=e['sck']!=c.cpol
                if leading==(c.cpha==0):
                    if any(t-last_changes[k]<c.data_setup_cycles for k in last_changes):flags.append('DATA_SETUP_SHORT')
                    samples.append((e['mosi'],e['miso']));last_sample=t
        previous=e
    if transactions!=1 or rise is None or previous['cs']!=1:flags.append('CS_TRANSACTION_INCOMPLETE')
    if len(edges)!=2*c.frame_bits or len(samples)!=c.frame_bits:flags.append('EDGE_OR_BIT_COUNT')
    def word(column):
        if len(samples)!=c.frame_bits:return None
        bits=[v[column] for v in samples]
        if c.bit_order=='msb':
            value=0
            for bit in bits:value=(value<<1)|bit
            return value
        return sum(bit<<i for i,bit in enumerate(bits))
    tx,rx=word(0),word(1)
    if expected_tx is not None and tx!=expected_tx:flags.append('TX_WORD_MISMATCH')
    if expected_rx is not None and rx!=expected_rx:flags.append('RX_WORD_MISMATCH')
    return dict(passed=not flags,quality_flags=sorted(set(flags)),transmitted=tx,received=rx,
                sampled_bits=len(samples),clock_edges=len(edges),evidence_kind='DIGITAL_TRACE_CHECK',hardware_verified=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--trace-csv');p.add_argument('--output',required=True)
    a=p.parse_args();data=json.loads(Path(a.config).read_text());c=SpiConfig(**data['spi'])
    tx=int(data['tx'],0) if isinstance(data['tx'],str) else data['tx'];rx=int(data.get('rx',0),0) if isinstance(data.get('rx',0),str) else data.get('rx',0)
    if a.trace_csv:
        with open(a.trace_csv,newline='',encoding='utf-8') as f:trace=[{k:int(v) for k,v in row.items()} for row in csv.DictReader(f)]
        source='USER_TRACE_NOT_AUTHENTICATED'
    else:trace=build_trace(c,tx,rx);source='SYNTHETIC_TRACE'
    report=validate_trace(trace,c,tx,rx);report.update(source=source,config=asdict(c),divider=divider(c))
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not report['passed']:raise SystemExit(1)
    print('PASS_DIGITAL_TRACE:',source,'no hardware operations')
if __name__=='__main__':main()
