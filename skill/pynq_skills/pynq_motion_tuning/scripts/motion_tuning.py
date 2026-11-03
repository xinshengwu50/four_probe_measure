"""Unit-aware motor parameter preview and explicit adapter execution. No built-in board/pins."""
from dataclasses import dataclass,asdict
import argparse,hashlib,json,math,time
from pathlib import Path


def _int(v,name):
    if isinstance(v,bool) or not isinstance(v,int):raise ValueError('invalid '+name)
    return v


def _number(v,name,positive=False):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or (positive and v<=0):raise ValueError('invalid '+name)
    return float(v)

@dataclass(frozen=True)
class AxisConfig:
    axis:str='example_axis'
    unit:str='mm'
    full_steps_per_rev:int=200
    microsteps:int=16
    gear_ratio:float=1.
    units_per_output_rev:float=2.
    clock_hz:int=50_000_000
    hard_min_steps:int=0
    hard_max_steps:int=16000
    soft_min:float=0.
    soft_max:float=10.
    max_speed:float=20.
    min_pulse_cycles:int=2
    max_period_cycles:int=0xffffffff
    def __post_init__(self):
        if not isinstance(self.axis,str) or not self.axis or self.unit not in ('mm','deg'):raise ValueError('invalid axis/unit')
        for k in ('full_steps_per_rev','microsteps','clock_hz','min_pulse_cycles','max_period_cycles'):
            if _int(getattr(self,k),k)<=0:raise ValueError('nonpositive '+k)
        lo=_int(self.hard_min_steps,'hard minimum');hi=_int(self.hard_max_steps,'hard maximum')
        if not -(1<<31)<=lo<hi<(1<<31):raise ValueError('hard step bounds exceed int32')
        for k in ('gear_ratio','units_per_output_rev','max_speed'):_number(getattr(self,k),k,True)
        if _number(self.soft_min,'soft minimum')>=_number(self.soft_max,'soft maximum'):raise ValueError('invalid soft bounds')
        _number(self.steps_per_unit,'derived steps_per_unit',True)
        if self.max_period_cycles>0xffffffff:raise ValueError('period register exceeds32bits')
        if self.soft_min*self.steps_per_unit<lo or self.soft_max*self.steps_per_unit>hi:raise ValueError('soft limits cannot enlarge PL hard limits')
    @property
    def steps_per_unit(self):return self.full_steps_per_rev*self.microsteps*self.gear_ratio/self.units_per_output_rev


def _period(c,speed):
    speed=_number(speed,'speed',True)
    if speed>c.max_speed:raise ValueError('speed above configured mechanical maximum')
    raw_period=c.clock_hz/(speed*c.steps_per_unit)
    if not math.isfinite(raw_period):raise ValueError('period conversion overflow')
    period=math.ceil(raw_period)
    if not 2*c.min_pulse_cycles<=period<=c.max_period_cycles:raise ValueError('pulse width or register period not realizable')
    return period


def preview_move(c,current_steps,target,speed,end_speed,decel_window_steps=100,segments=8,homed=False,trusted=False):
    if homed is not True or trusted is not True:raise ValueError('position must be homed and trusted')
    _int(current_steps,'current_steps');_number(target,'target')
    if not c.hard_min_steps<=current_steps<=c.hard_max_steps:raise ValueError('current position outside hard limits')
    if not c.soft_min<=current_steps/c.steps_per_unit<=c.soft_max:raise ValueError('current position outside soft limits')
    if not c.soft_min<=target<=c.soft_max:raise ValueError('target outside soft limits')
    # Python ties-to-even nearest step; quantization explicitly reported.
    target_steps=round(target*c.steps_per_unit)
    if not c.hard_min_steps<=target_steps<=c.hard_max_steps:raise ValueError('target beyond PL hard limit')
    if not c.soft_min<=target_steps/c.steps_per_unit<=c.soft_max:raise ValueError('quantized target beyond soft limit')
    distance=abs(target_steps-current_steps)
    if not distance:raise ValueError('zero-distance move not a valid test')
    if _number(end_speed,'end speed',True)>_number(speed,'speed',True):raise ValueError('end speed must not exceed run speed')
    for v,k in [(decel_window_steps,'window'),(segments,'segments')]:
        if _int(v,k)<=0:raise ValueError('positive '+k+' required')
    if segments>256:raise ValueError('maximum256segments')
    run=_period(c,speed);end=_period(c,end_speed);window=min(decel_window_steps,distance)
    if segments>window:raise ValueError('more decel segments than effective window steps; reduce segments')
    periods=[round(run+(end-run)*i/(segments-1)) for i in range(segments)] if segments>1 else [end]
    return dict(schema_version=1,config=asdict(c),current_steps=current_steps,target_requested=target,
        speed_requested=speed,end_speed_requested=end_speed,decel_window_requested=decel_window_steps,segments=segments,
        target_steps=target_steps,actual_target=target_steps/c.steps_per_unit,
        quantization_error=target_steps/c.steps_per_unit-target,distance_steps=distance,
        actual_speed=c.clock_hz/run/c.steps_per_unit,run_period_cycles=run,end_period_cycles=end,
        pulse_high_cycles=run//2,pulse_low_cycles=run-run//2,decel_window_steps=window,decel_periods=periods,
        decel_segment_steps=[window//segments+(1 if i<window%segments else 0) for i in range(segments)],
        profile='LINEAR_PERIOD_NOT_CONSTANT_ACCEL',position_source='STEP_ESTIMATE',evidence_kind='PREVIEW_ONLY',hardware_verified=False)


def fingerprint(plan):return hashlib.sha256(json.dumps(plan,sort_keys=True,allow_nan=False).encode()).hexdigest()


def _verify_plan(plan):
    c=AxisConfig(**plan['config'])
    expected=preview_move(c,plan['current_steps'],plan['target_requested'],plan['speed_requested'],plan['end_speed_requested'],plan['decel_window_requested'],plan['segments'],True,True)
    if plan!=expected:raise ValueError('plan changed or incompatible')
    return c


def authorize(plan,*,mechanism_confirmed=False,estop_confirmed=False,limits_confirmed=False):
    _verify_plan(plan)
    if any(v is not True for v in (mechanism_confirmed,estop_confirmed,limits_confirmed)):raise PermissionError('all three safety confirmations required')
    return dict(plan_sha256=fingerprint(plan),used=False)


def execute_plan(adapter,plan,authorization,timeout_s=5.,poll_s=.01):
    if not authorization or authorization.get('used') is not False or authorization.get('plan_sha256')!=fingerprint(plan):raise PermissionError('missing/stale/used authorization')
    c=_verify_plan(plan);caps=adapter.capabilities
    if caps.get('immediate_stop') is not True:raise PermissionError('adapter has no verified immediate STOP; use preview only')
    for k in ('clock_hz','hard_min_steps','hard_max_steps','axis'):
        if caps.get(k)!=getattr(c,k):raise PermissionError('adapter/PL capability mismatch: '+k)
    if caps.get('profile')!=plan['profile']:raise PermissionError('PL does not support this deceleration profile')
    for v in (timeout_s,poll_s):
        if _number(v,'timing',True)<=0:raise ValueError('invalid timing')
    status=adapter.status()
    if status.get('busy') is not False or status.get('fault') is not False or status.get('homed') is not True or status.get('trusted') is not True or status.get('position_steps')!=plan['current_steps']:
        raise PermissionError('axis not ready or position changed')
    authorization['used']=True;started=False;deadline=time.monotonic()+timeout_s
    try:
        started=True
        if adapter.start(plan) is not True:raise RuntimeError('command not explicitly accepted')
        while True:
            if time.monotonic()>=deadline:raise TimeoutError('axis timeout; stop requested')
            status=adapter.status()
            if status.get('fault') is not False:raise RuntimeError('axis fault or invalid status')
            if status.get('done') is True and status.get('busy') is False:
                if status.get('trusted') is not True or status.get('position_steps')!=plan['target_steps']:raise RuntimeError('untrusted/mismatched final position')
                return status
            time.sleep(min(poll_s,max(0.,deadline-time.monotonic())))
    except BaseException as exc:
        if started:
            try:adapter.stop()
            except Exception as stop_error:setattr(exc,'stop_error',repr(stop_error))
        raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    data=json.loads(Path(a.config).read_text());plan=preview_move(AxisConfig(**data['axis']),**data['move'])
    report=dict(plan=plan,plan_sha256=fingerprint(plan))
    Path(a.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('PREVIEW_ONLY:',plan['target_steps'],'steps; no hardware or motion API called')
if __name__=='__main__':main()
