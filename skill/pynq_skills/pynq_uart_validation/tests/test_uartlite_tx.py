import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from uartlite_tx import UartLiteTx,UartLiteModel,benchmark,STAT,TX,STAT_TX_EMPTY,STAT_TX_FULL,FIFO_DEPTH
PAYLOAD=bytes(range(256))*24
class UartLiteModelTests(unittest.TestCase):
    def test_model_golden_fifo_depth_and_drop(self):
        # Idle shifter takes byte 1 at once; 16 more fill the FIFO; the 18th write is dropped.
        m=UartLiteModel()
        m.write(TX,1);self.assertEqual(m.read(STAT),STAT_TX_EMPTY)
        for b in range(2,18):m.write(TX,b)
        self.assertEqual(m.read(STAT),STAT_TX_FULL)
        m.write(TX,99);self.assertEqual(m.dropped,1);self.assertEqual(bytes(m.out),bytes(range(1,18)))
        m.sleep(17*10/115200);self.assertEqual(m.read(STAT),STAT_TX_EMPTY)
    def test_unguarded_writes_lose_bytes(self):
        # Negative control: writing without checking TX_FULL is what silently truncates commands.
        m=UartLiteModel()
        for b in PAYLOAD[:64]:m.write(TX,b)
        self.assertEqual(m.dropped,64-1-FIFO_DEPTH)
    def test_invalid_model_parameters(self):
        for kw in ({'baud':0},{'baud':True},{'fifo_depth':0},{'sleep_overhead_s':-1}):
            with self.assertRaises(ValueError):UartLiteModel(**kw)
class UartLiteTxTests(unittest.TestCase):
    def test_fill_fifo_reaches_line_rate_without_loss(self):
        for overhead in (0,.0001,.00037):
            r=benchmark(PAYLOAD,'fill_fifo',sleep_overhead_s=overhead)
            self.assertEqual(r['dropped'],0);self.assertTrue(r['bytes_match'])
            self.assertLess(r['seconds'],r['wire_seconds']*1.01)
            self.assertFalse(r['hardware_verified'])
    def test_stop_and_wait_is_bounded_by_sleep_granularity(self):
        # Every second byte finds the shifter busy and sleeps once: ~bytes/2*(yield+overhead).
        r=benchmark(PAYLOAD,'stop_and_wait',sleep_overhead_s=.00037)
        self.assertEqual(r['dropped'],0);self.assertTrue(r['bytes_match'])
        self.assertEqual(r['sleep_calls'],len(PAYLOAD)//2)
        self.assertAlmostEqual(r['seconds'],len(PAYLOAD)//2*.00057,delta=.01)
        self.assertGreater(r['seconds'],3*benchmark(PAYLOAD,'fill_fifo',sleep_overhead_s=.00037)['seconds'])
    def test_fill_fifo_still_yields_for_rx_thread(self):
        r=benchmark(PAYLOAD,'fill_fifo')
        self.assertGreater(r['sleep_calls'],0)
        self.assertLessEqual(r['max_accesses_between_yields'],2*FIFO_DEPTH+3)
    def test_stuck_full_fifo_times_out(self):
        class Stuck:
            def read(self,offset):return STAT_TX_FULL
            def write(self,offset,value):raise AssertionError('must not write into a full FIFO')
        clock=[0.]
        tx=UartLiteTx(Stuck(),timeout_s=.01,sleep=lambda s:clock.__setitem__(0,clock[0]+s),monotonic=lambda:clock[0])
        with self.assertRaises(TimeoutError):tx.write_fill_fifo(b'x')
    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):benchmark(b'x','burst')
        for kw in ({'timeout_s':0},{'yield_s':float('nan')},{'yield_s':True}):
            with self.assertRaises(ValueError):UartLiteTx(UartLiteModel(),**kw)
if __name__=='__main__':unittest.main()
