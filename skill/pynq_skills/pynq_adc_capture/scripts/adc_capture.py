"""ADC bitfield conversion and fresh-frame quality checks; no hardware imports."""
from dataclasses import dataclass,asdict
import argparse,json,math,statistics,time
from pathlib import Path


def _int(v,name,minimum=0):
    if isinstance(v,bool) or not isinstance(v,int) or v<minimum:raise ValueError('invalid '+name)
    return v


def _finite(v,name):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('invalid '+name)
    return float(v)

@dataclass(frozen=True)
class AdcConfig:
    frame_bits:int=16
    code_bits:int=12
    code_lsb:int=0
    coding:str='straight'
    input_min_v:float=0.
    input_max_v:float=3.3
    bias_v:float=0.
    gain:float=1.
    sequence_bits:int=32
    channel_lsb:int=0
    channel_bits:int=0
    expected_channel:object=None
    max_saturation_ratio:float=0.
    min_valid_ratio:float=.8
    max_std_v:object=None
    def __post_init__(self):
        for k in ('frame_bits','code_bits','sequence_bits'):_int(getattr(self,k),k,1)
        for k in ('code_lsb','channel_lsb','channel_bits'):_int(getattr(self,k),k)
        if self.frame_bits>64 or self.sequence_bits>64 or self.code_lsb+self.code_bits>self.frame_bits:raise ValueError('bitfield out of frame')
        if self.coding not in ('straight','twos','offset'):raise ValueError('unknown coding')
        lo=_finite(self.input_min_v,'input_min_v');hi=_finite(self.input_max_v,'input_max_v')
        if not math.isfinite(hi-lo) or hi<=lo or _finite(self.gain,'gain')<=0:raise ValueError('invalid scale')
        _finite(self.bias_v,'bias')
        for key in ('max_saturation_ratio','min_valid_ratio'):
            if not 0<=_finite(getattr(self,key),key)<=1:raise ValueError('invalid quality ratio')
        if self.max_std_v is not None and _finite(self.max_std_v,'max_std_v')<0:raise ValueError('negative noise limit')
        if self.channel_bits:
            _int(self.expected_channel,'channel',0)
            if self.channel_lsb+self.channel_bits>self.frame_bits or self.expected_channel>=1<<self.channel_bits:raise ValueError('channel out of frame')
            if max(self.channel_lsb,self.code_lsb)<min(self.channel_lsb+self.channel_bits,self.code_lsb+self.code_bits):raise ValueError('overlapping channel/code')
        elif self.expected_channel is not None:raise ValueError('channel configured without bits')


def decode_frame(frame,c):
    _int(frame,'frame')
    if frame>=1<<c.frame_bits:raise ValueError('frame overflow')
    raw=(frame>>c.code_lsb)&((1<<c.code_bits)-1);levels=1<<c.code_bits;half=levels>>1
    code=raw-levels if c.coding=='twos' and raw>=half else raw-half if c.coding=='offset' else raw
    normalized=code+half if c.coding in ('twos','offset') else raw
    adc_v=c.input_min_v+normalized/levels*(c.input_max_v-c.input_min_v)
    signal_v=(adc_v-c.bias_v)/c.gain
    if not math.isfinite(signal_v):raise ValueError('conversion overflow')
    channel=(frame>>c.channel_lsb)&((1<<c.channel_bits)-1) if c.channel_bits else None
    endpoints=(-half,half-1) if c.coding in ('twos','offset') else (0,levels-1)
    return dict(raw_code=raw,signed_code=code,adc_v=adc_v,signal_v=signal_v,channel=channel,
                channel_ok=not c.channel_bits or channel==c.expected_channel,saturated=code in endpoints)


class SequenceTracker:
    def __init__(self,bits=32):
        _int(bits,'sequence bits',1)
        if bits>64:raise ValueError('sequence bits exceed64')
        self.bits=bits;self.last=None;self.missing=0
    def accept(self,seq):
        _int(seq,'sequence')
        modulus=1<<self.bits
        if seq>=modulus:raise ValueError('sequence overflow')
        if self.last is None:self.last=seq;return 'new'
        delta=(seq-self.last)%modulus
        if delta==0:return 'duplicate'
        if delta>=modulus//2:return 'out_of_order'
        self.last=seq;self.missing+=delta-1;return 'new'


class _Window:
    def __init__(self,c,discard):
        _int(discard,'discard_first');self.c=c;self.discard=discard;self.tracker=SequenceTracker(c.sequence_bits)
        self.values=[];self.records=[];self.total=0;self.fresh=0;self.saturation=0
        self.counts=dict(duplicate=0,out_of_order=0,no_sequence=0,bad_frame=0,bad_status=0,bad_channel=0,discarded=0)
    def input(self,record):
        self.total+=1
        if not isinstance(record,dict) or record.get('sequence') is None:self.counts['no_sequence']+=1;return
        try:state=self.tracker.accept(record['sequence'])
        except ValueError:self.counts['bad_frame']+=1;return
        if state!='new':self.counts[state]+=1;return
        self.fresh+=1
        if record.get('status_ok',True) is not True:self.counts['bad_status']+=1;return
        try:sample=decode_frame(record['frame'],self.c)
        except (ValueError,KeyError):self.counts['bad_frame']+=1;return
        if not sample['channel_ok']:self.counts['bad_channel']+=1;return
        if self.discard:self.discard-=1;self.counts['discarded']+=1;return
        self.values.append(sample['signal_v']);self.saturation+=int(sample['saturated'])
        self.records.append(dict(sequence=record['sequence'],frame=record['frame'],**sample))
    def result(self,required):
        _int(required,'required_samples',1);count=len(self.values);ratio=count/max(1,self.total-self.counts['discarded'])
        std=statistics.pstdev(self.values) if count else None;sat=self.saturation/count if count else 0.
        flags=[]
        if count<required:flags.append('VALID_COUNT_LOW')
        if self.counts['no_sequence']:flags.append('NO_FRESHNESS_EVIDENCE')
        if self.tracker.missing:flags.append('SEQUENCE_GAP')
        if self.counts['out_of_order']:flags.append('OUT_OF_ORDER')
        if ratio<self.c.min_valid_ratio:flags.append('VALID_RATIO_LOW')
        if sat>self.c.max_saturation_ratio:flags.append('SATURATION_HIGH')
        if self.c.max_std_v is not None and (std is None or std>self.c.max_std_v):flags.append('NOISE_HIGH')
        return dict(passed=not flags,evidence_kind='INPUT_RECORD_ANALYSIS',hardware_verified=False,
                    quality_flags=flags,total_records=self.total,valid_count=count,valid_ratio=ratio,
                    saturation_count=self.saturation,saturation_ratio=sat,missing_sequences=self.tracker.missing,
                    rejected=dict(self.counts),mean_signal_v=statistics.fmean(self.values) if count else None,
                    median_signal_v=statistics.median(self.values) if count else None,std_signal_v=std,
                    minimum_signal_v=min(self.values) if count else None,maximum_signal_v=max(self.values) if count else None,
                    samples=list(self.records))


def analyze_records(records,c,discard_first=0,required_samples=1):
    window=_Window(c,discard_first)
    for r in records:window.input(r)
    return window.result(required_samples)


class CaptureError(RuntimeError):
    def __init__(self,message,partial):super().__init__(message);self.partial=partial


def capture(provider,c,required_samples,timeout_s=1.,poll_s=.001,discard_first=0):
    _int(required_samples,'required_samples',1)
    for v in (timeout_s,poll_s):
        if _finite(v,'timing')<=0:raise ValueError('nonpositive timing')
    deadline=time.monotonic()+timeout_s;window=_Window(c,discard_first)
    while len(window.values)<required_samples:
        if time.monotonic()>=deadline:raise CaptureError('capture timeout',window.result(required_samples))
        try:record=provider()
        except StopIteration:raise CaptureError('provider exhausted',window.result(required_samples))
        except Exception as exc:raise CaptureError('provider error: '+str(exc),window.result(required_samples)) from exc
        # provider must be bounded/nonblocking and return an ATOMIC sequence+frame snapshot.
        if time.monotonic()>=deadline:raise CaptureError('provider exceeded deadline',window.result(required_samples))
        if record is None:time.sleep(min(poll_s,max(0.,deadline-time.monotonic())));continue
        window.input(record)
    result=window.result(required_samples)
    if not result['passed']:raise CaptureError('quality gate failed',result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--records',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();cfg=json.loads(Path(a.config).read_text());c=AdcConfig(**cfg['adc'])
    result=analyze_records(json.loads(Path(a.records).read_text()),c,discard_first=cfg.get('discard_first',0),required_samples=cfg.get('required_samples',1))
    result['source']='USER_OR_SYNTHETIC_RECORDS_NOT_AUTHENTICATED';result['config']=asdict(c)
    Path(a.output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if not result['passed']:raise SystemExit(1)
    print('PASS_RECORD_ANALYSIS: no hardware operations')
if __name__=='__main__':main()
