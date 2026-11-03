import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from spi_contract import SpiConfig,build_trace,validate_trace,divider
class SpiTests(unittest.TestCase):
 def test_all_modes_orders(self):
  for mode in range(4):
   for order in ['msb','lsb']:
    c=SpiConfig(mode=mode,bit_order=order,frame_bits=8)
    r=validate_trace(build_trace(c,0xa6,0x53),c,0xa6,0x53)
    self.assertTrue(r['passed'],r);self.assertEqual(r['received'],0x53)
 def test_divider_does_not_exceed_requested(self):
  c=SpiConfig(clock_hz=50_000_000,sck_hz=3_000_000)
  d=divider(c);self.assertLessEqual(d['actual_sck_hz'],c.sck_hz)
 def test_missing_edge_and_bad_data(self):
  c=SpiConfig();trace=build_trace(c,0xa6,0x53)
  self.assertFalse(validate_trace(trace[:-2],c,0xa6,0x53)['passed'])
  self.assertFalse(validate_trace(trace,c,0xff,0x53)['passed'])
 def test_config_rejects(self):
  for args in [dict(mode=4),dict(frame_bits=0),dict(sck_hz=0),dict(clock_hz=True),dict(bit_order='weird')]:
   with self.assertRaises(ValueError):SpiConfig(**args)
 def test_setup_violation_and_cs_glitch(self):
  c=SpiConfig();trace=build_trace(c,0xa6,0x53)
  trace[2]['mosi']^=1
  self.assertFalse(validate_trace(trace,c,0xa6,0x53)['passed'])
  trace=build_trace(c,0xa6,0x53);trace[4]['cs']=1
  self.assertFalse(validate_trace(trace,c,0xa6,0x53)['passed'])
 def test_integer_frames_boundaries(self):
  c=SpiConfig(frame_bits=32)
  self.assertTrue(validate_trace(build_trace(c,0xffffffff,0),c,0xffffffff,0)['passed'])
  with self.assertRaises(ValueError):build_trace(c,1<<32)
 def test_wrong_bit_order_and_duplicate_times(self):
  c=SpiConfig();trace=build_trace(c,0xa6,0x53)
  self.assertFalse(validate_trace(trace,SpiConfig(bit_order='lsb'),0xa6,0x53)['passed'])
  trace[3]['t_cycles']=trace[2]['t_cycles']
  self.assertFalse(validate_trace(trace,c)['passed'])
 def test_24bit_and_divider_failure(self):
  c=SpiConfig(frame_bits=24,mode=1)
  self.assertTrue(validate_trace(build_trace(c,0x123abc,0x345678),c,0x123abc,0x345678)['passed'])
  with self.assertRaises(ValueError):SpiConfig(sck_hz=1,max_half_cycles=10)
 def test_first_bit_data_setup_can_exceed_cs_setup(self):
  c=SpiConfig(cs_setup_cycles=1,data_setup_cycles=10)
  self.assertTrue(validate_trace(build_trace(c,0xa6,0x53),c,0xa6,0x53)['passed'])
if __name__=='__main__':unittest.main()
