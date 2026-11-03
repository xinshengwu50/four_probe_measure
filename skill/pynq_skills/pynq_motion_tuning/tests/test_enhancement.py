import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import motion_safety as mod
class EnhancementTests(unittest.TestCase):

    def test_contact_and_retract(self):
        s=dict(homed=True,position_trusted=True,position_steps=10,safe_travel_steps=5,other_axis_busy=False,fault_latched=False)
        self.assertEqual(mod.review_motion('LATERAL',**s)['reason'],'PROBE_NOT_CLEAR')
        s.update(other_axis_busy=True)
        self.assertTrue(mod.review_motion('RETRACT',retract_direction_verified=True,**s)['allowed'])
        self.assertFalse(mod.review_motion('RETRACT',**s)['allowed'])
        self.assertTrue(mod.review_motion('STOP',**s)['allowed'])
    def test_fail_closed(self):
        s=dict(homed=False,position_trusted=True,position_steps=0,safe_travel_steps=0,other_axis_busy=False,fault_latched=False)
        self.assertFalse(mod.review_motion('LATERAL',**s)['allowed'])
        s.update(homed=True)
        self.assertTrue(mod.review_motion('LATERAL',**s)['allowed'])
        s.update(fault_latched=True)
        self.assertFalse(mod.review_motion('DOWN',**s)['allowed'])
        self.assertFalse(mod.review_motion('RETRACT',retract_direction_verified=True,**s)['allowed'])

if __name__=='__main__':unittest.main()
