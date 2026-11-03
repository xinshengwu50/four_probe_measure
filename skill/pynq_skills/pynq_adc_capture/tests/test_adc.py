import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from adc_capture import AdcConfig,decode_frame,SequenceTracker,analyze_records,capture,CaptureError
class AdcTests(unittest.TestCase):
 def test_binary_scale(self):
  c=AdcConfig(frame_bits=16,code_bits=12,input_min_v=0,input_max_v=4.096)
  self.assertAlmostEqual(decode_frame(2048,c)['signal_v'],2.048)
  self.assertAlmostEqual(decode_frame(4095,c)['adc_v'],4.095)
 def test_signed_offset(self):
  for coding,zero,minimum in [('twos',0,128),('offset',128,0)]:
   c=AdcConfig(frame_bits=8,code_bits=8,coding=coding,input_min_v=-1,input_max_v=1)
   self.assertEqual(decode_frame(zero,c)['adc_v'],0)
   self.assertEqual(decode_frame(minimum,c)['adc_v'],-1)
 def test_new_equal_codes_duplicate_reject_wrap_gap(self):
  t=SequenceTracker(8)
  self.assertEqual(t.accept(254),'new');self.assertEqual(t.accept(255),'new');self.assertEqual(t.accept(0),'new')
  self.assertEqual(t.accept(0),'duplicate');self.assertEqual(t.accept(255),'out_of_order')
  self.assertEqual(t.accept(3),'new');self.assertEqual(t.missing,2)
  c=AdcConfig();r=analyze_records([dict(sequence=i,frame=2000) for i in range(3)],c)
  self.assertEqual(r['valid_count'],3)
 def test_no_sequence_not_claimed_fresh(self):
  r=analyze_records([dict(frame=2000)],AdcConfig())
  self.assertEqual(r['valid_count'],0);self.assertIn('NO_FRESHNESS_EVIDENCE',r['quality_flags'])
 def test_channel_status_saturation(self):
  c=AdcConfig(frame_bits=16,code_bits=12,channel_lsb=12,channel_bits=2,expected_channel=1)
  records=[dict(sequence=1,frame=0),dict(sequence=2,frame=(1<<12)|4095),dict(sequence=3,frame=(1<<12)|10,status_ok=False)]
  r=analyze_records(records,c);self.assertEqual(r['valid_count'],1);self.assertEqual(r['saturation_count'],1)
 def test_capture_timeout_is_partial_error(self):
  with self.assertRaises(CaptureError):capture(lambda:None,AdcConfig(),required_samples=2,timeout_s=.001,poll_s=.0001)
 def test_discard_and_gain(self):
  c=AdcConfig(frame_bits=12,code_bits=12,input_min_v=0,input_max_v=4.096,bias_v=1,gain=2)
  r=analyze_records([dict(sequence=i,frame=2000) for i in range(4)],c,discard_first=1)
  self.assertEqual(r['valid_count'],3);self.assertAlmostEqual(r['mean_signal_v'],.5)
 def test_bad_configs(self):
  for args in [dict(code_bits=0),dict(gain=0),dict(coding='weird'),dict(channel_bits=2,channel_lsb=1),dict(input_max_v=float('nan'))]:
   with self.assertRaises(ValueError):AdcConfig(**args)
 def test_capture_identical_codes_fresh_success(self):
  iterator=iter([dict(sequence=i,frame=2000) for i in range(4)])
  result=capture(lambda:next(iterator),AdcConfig(),required_samples=3,timeout_s=1)
  self.assertEqual(result['valid_count'],3)
 def test_exhaustion_and_saturation_are_not_success(self):
  for records in [[],[dict(sequence=0,frame=0)]]:
   it=iter(records)
   with self.assertRaises(CaptureError) as cm:capture(lambda:next(it),AdcConfig(),required_samples=1,timeout_s=1)
   self.assertFalse(cm.exception.partial['passed'])
 def test_bipolar_endpoints_and_offsets(self):
  c=AdcConfig(frame_bits=16,code_bits=16,coding='twos',input_min_v=-2.5,input_max_v=2.5)
  self.assertTrue(decode_frame(0x7fff,c)['saturated']);self.assertTrue(decode_frame(0x8000,c)['saturated'])
  self.assertAlmostEqual(decode_frame(0xffff,c)['adc_v'],-5/65536)
 def test_noise_and_missing_sequences(self):
  c=AdcConfig(max_std_v=.0001)
  r=analyze_records([dict(sequence=0,frame=1000),dict(sequence=2,frame=2000)],c)
  self.assertIn('SEQUENCE_GAP',r['quality_flags']);self.assertIn('NOISE_HIGH',r['quality_flags'])
 def test_provider_error_retains_partial(self):
  n=[0]
  def provider():
   n[0]+=1
   if n[0]>1:raise OSError('read failed')
   return dict(sequence=0,frame=2000)
  with self.assertRaises(CaptureError) as cm:capture(provider,AdcConfig(),required_samples=2)
  self.assertEqual(cm.exception.partial['valid_count'],1)
if __name__=='__main__':unittest.main()
