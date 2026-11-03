import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from motion_tuning import AxisConfig,preview_move,authorize,execute_plan
class Adapter:
 capabilities={'immediate_stop':True,'axis':'linear','clock_hz':50_000_000,'hard_min_steps':0,'hard_max_steps':16000,'profile':'LINEAR_PERIOD_NOT_CONSTANT_ACCEL'}
 def __init__(self):self.calls=[];self.position=0
 def status(self):return dict(busy=False,done=bool(self.calls),fault=False,position_steps=self.position,trusted=True,homed=True)
 def start(self,p):self.calls.append(p);self.position=p['target_steps'];return True
 def stop(self):self.calls.append('stop')
class MotionTests(unittest.TestCase):
 def cfg(self):return AxisConfig(axis='linear',unit='mm',full_steps_per_rev=200,microsteps=16,gear_ratio=1,units_per_output_rev=2,hard_min_steps=0,hard_max_steps=16000,soft_min=0,soft_max=10,max_speed=20)
 def plan(self):return preview_move(self.cfg(),current_steps=0,target=1,speed=5,end_speed=1,decel_window_steps=100,segments=4,homed=True,trusted=True)
 def test_units_quantization(self):
  p=self.plan();self.assertEqual(p['target_steps'],1600);self.assertLessEqual(p['actual_speed'],5)
  c=AxisConfig(axis='turntable',unit='deg',full_steps_per_rev=200,microsteps=16,gear_ratio=1,units_per_output_rev=360,hard_min_steps=0,hard_max_steps=3200,soft_min=0,soft_max=360,max_speed=180)
  p=preview_move(c,0,90,30,5,100,4,True,True);self.assertEqual(p['target_steps'],800)
 def test_no_bounds_bypass(self):
  for kwargs in [dict(target=11),dict(speed=30),dict(homed=False),dict(trusted=False)]:
   args=dict(current_steps=0,target=1,speed=5,end_speed=1,decel_window_steps=100,segments=4,homed=True,trusted=True);args.update(kwargs)
   with self.assertRaises(ValueError):preview_move(self.cfg(),**args)
 def test_safe_default_requires_receipt(self):
  with self.assertRaises(PermissionError):execute_plan(Adapter(),self.plan(),None)
 def test_changed_plan_revokes_authorization(self):
  p=self.plan();a=authorize(p,mechanism_confirmed=True,estop_confirmed=True,limits_confirmed=True)
  p['target_steps']=1700
  with self.assertRaises(PermissionError):execute_plan(Adapter(),p,a)
 def test_immediate_stop_capability_required(self):
  p=self.plan();a=authorize(p,mechanism_confirmed=True,estop_confirmed=True,limits_confirmed=True)
  adapter=Adapter();adapter.capabilities={'immediate_stop':False}
  with self.assertRaises(PermissionError):execute_plan(adapter,p,a)
  self.assertFalse(adapter.calls)
 def test_fake_execute(self):
  p=self.plan();a=authorize(p,mechanism_confirmed=True,estop_confirmed=True,limits_confirmed=True)
  self.assertEqual(execute_plan(Adapter(),p,a)['position_steps'],1600)
 def test_decel_monotonic(self):
  lut=self.plan()['decel_periods'];self.assertEqual(lut,sorted(lut))
 def test_invalid_config_and_zero_distance(self):
  with self.assertRaises(ValueError):AxisConfig(microsteps=0)
  with self.assertRaises(ValueError):preview_move(self.cfg(),0,0,1,1,100,4,True,True)
 def test_changed_current_position_refuses_start(self):
  p=self.plan();a=authorize(p,mechanism_confirmed=True,estop_confirmed=True,limits_confirmed=True);adapter=Adapter();adapter.position=100
  with self.assertRaises(PermissionError):execute_plan(adapter,p,a)
  self.assertFalse(adapter.calls)
 def test_timeout_and_fault_attempt_stop(self):
  for fault in [False,True]:
   class Slow(Adapter):
    def status(self):
     if not self.calls:return super().status()
     return dict(busy=True,done=False,fault=fault,position_steps=0,trusted=True)
   p=self.plan();a=authorize(p,mechanism_confirmed=True,estop_confirmed=True,limits_confirmed=True);adapter=Slow()
   with self.assertRaises((RuntimeError,TimeoutError)):execute_plan(adapter,p,a,timeout_s=.001,poll_s=.0001)
   self.assertEqual(adapter.calls[-1],'stop')
 def test_interrupt_and_failed_stop_preserve_exception(self):
  class Broken(Adapter):
   def start(self,p):raise KeyboardInterrupt()
   def stop(self):raise OSError('stop failed')
  p=self.plan();a=authorize(p,mechanism_confirmed=True,estop_confirmed=True,limits_confirmed=True)
  with self.assertRaises(KeyboardInterrupt) as cm:execute_plan(Broken(),p,a)
  self.assertIn('stop failed',cm.exception.stop_error)
 def test_receipt_one_use_and_profile_mismatch(self):
  p=self.plan();a=authorize(p,mechanism_confirmed=True,estop_confirmed=True,limits_confirmed=True);execute_plan(Adapter(),p,a)
  with self.assertRaises(PermissionError):execute_plan(Adapter(),p,a)
  a=authorize(p,mechanism_confirmed=True,estop_confirmed=True,limits_confirmed=True);adapter=Adapter();adapter.capabilities=dict(adapter.capabilities,profile='other')
  with self.assertRaises(PermissionError):execute_plan(adapter,p,a)
 def test_three_gates_and_hard_limit_cannot_raise(self):
  with self.assertRaises(PermissionError):authorize(self.plan())
  with self.assertRaises(ValueError):AxisConfig(hard_max_steps=100,soft_max=10)
 def test_segment_budget_and_remainder(self):
  p=preview_move(self.cfg(),0,1,5,1,103,4,True,True)
  self.assertEqual(sum(p['decel_segment_steps']),103)
  self.assertEqual(p['decel_segment_steps'],[26,26,26,25])
  with self.assertRaises(ValueError):preview_move(self.cfg(),0,1/1600,5,1,100,4,True,True)
if __name__=='__main__':unittest.main()
