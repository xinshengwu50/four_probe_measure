import sys,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from uart_protocol import FrameParser,encode,UartOwnership,timing_budget
class UartTests(unittest.TestCase):
    def test_golden_packet(self):
        # Independent known CRC32('123456789') and fixed framing length.
        self.assertEqual(zlib.crc32(b'123456789'),0xcbf43926)
        packet=encode(b'abc')
        self.assertEqual(packet[:4],bytes.fromhex('a55a0003'))
        self.assertEqual(packet[-2:],bytes.fromhex('5aa5'))
        self.assertEqual(len(packet),13)
        self.assertEqual(packet[-6:-2],zlib.crc32(bytes.fromhex('0003')+b'abc').to_bytes(4,'big'))
    def test_split_every_byte_and_equal_frames(self):
        p=FrameParser();wire=encode(b'X')*2;frames=[]
        for i,b in enumerate(wire):
            r=p.feed(bytes([b]),i*.001);frames+=r['frames'];self.assertFalse(r['errors'])
        self.assertEqual(frames,[b'X',b'X'])
    def test_merged_and_noise(self):
        r=FrameParser().feed(b'noise'+encode(b'A')+encode(b'B'),0)
        self.assertEqual(r['frames'],[b'A',b'B']);self.assertIn('NOISE_DISCARDED',r['errors'])
    def test_crc_mutation(self):
        wire=bytearray(encode(b'hello'));wire[4]^=1
        r=FrameParser().feed(bytes(wire)+encode(b'good'),0)
        self.assertEqual(r['frames'],[b'good']);self.assertIn('FRAME_INTEGRITY_ERROR',r['errors'])
    def test_tail_mutation(self):
        wire=encode(b'bad')[:-1]+b'X'
        r=FrameParser().feed(wire+encode(b'next'),0)
        self.assertEqual(r['frames'],[b'next']);self.assertIn('FRAME_INTEGRITY_ERROR',r['errors'])
    def test_bad_length_and_timeout(self):
        p=FrameParser(max_payload=20,frame_timeout_s=.5)
        r=p.feed(bytes.fromhex('a55affff'),0);self.assertIn('LENGTH_INVALID',r['errors'])
        p.feed(encode(b'abc')[:5],.1)
        r=p.feed(encode(b'ok'),.7);self.assertEqual(r['frames'],[b'ok']);self.assertIn('FRAME_TIMEOUT',r['errors'])
    def test_bounds_monotonic_and_reset(self):
        p=FrameParser(4);p.feed(b'\xa5',1)
        with self.assertRaises(ValueError):p.feed(b'',0)
        with self.assertRaises(ValueError):p.feed(b'X'*15,2)
        with self.assertRaises(ValueError):encode(b'12345',4)
        p.reset();self.assertEqual(p.feed(encode(b'ok',4),0)['frames'],[b'ok'])
    def test_ownership(self):
        o=UartOwnership();o.acquire('uart0','service1')
        with self.assertRaises(RuntimeError):o.acquire('uart0','service2')
        with self.assertRaises(RuntimeError):o.release('uart0','service2')
        o.release('uart0','service1');o.acquire('uart0','service2')
    def test_timing(self):
        r=timing_budget(6811,115200)
        self.assertAlmostEqual(r['wire_seconds'],68110/115200)
        self.assertAlmostEqual(r['fifo_fill_seconds'],160/115200)
        self.assertFalse(r['polling_guaranteed'])
        with self.assertRaises(ValueError):timing_budget(10,True)
if __name__=='__main__':unittest.main()
