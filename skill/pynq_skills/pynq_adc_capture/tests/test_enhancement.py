import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import adc_window as mod
class EnhancementTests(unittest.TestCase):

    def test_center_and_inverse(self):
        from adc_capture import AdcConfig,decode_frame
        c=AdcConfig(frame_bits=16,code_bits=16,input_min_v=-5.12,input_max_v=5.12,bias_v=2.5)
        r=mod.signal_window_codes(c,-.001,.001)
        self.assertEqual(r['signal_zero_raw_code'],48768)
        for lo,hi in r['raw_intervals']:
            for code in (lo,hi):self.assertLessEqual(abs(decode_frame(code,c)['signal_v']),.001)
        with self.assertRaises(ValueError):mod.signal_window_codes(c,20,21)
        with self.assertRaises(ValueError):mod.signal_window_codes(c,float('nan'),1)
    def test_twos_wrap(self):
        from adc_capture import AdcConfig,decode_frame
        c=AdcConfig(frame_bits=8,code_bits=8,coding='twos',input_min_v=-1,input_max_v=1)
        r=mod.signal_window_codes(c,-.1,.1)
        self.assertEqual(len(r['raw_intervals']),2)
        for lo,hi in r['raw_intervals']:
            for code in range(lo,hi+1):self.assertLessEqual(abs(decode_frame(code,c)['signal_v']),.1)

if __name__=='__main__':unittest.main()
