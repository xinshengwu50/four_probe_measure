"""AXI UART Lite (PG142) TX: FIFO-filling write vs per-byte stop-and-wait.
Works with any object exposing read(offset)/write(offset, value), e.g. pynq.MMIO.
UartLiteModel is an OFFLINE virtual-clock model, not hardware evidence.
"""
import math, time
RX, TX, STAT, CTRL = 0x00, 0x04, 0x08, 0x0C
STAT_TX_EMPTY, STAT_TX_FULL = 0x04, 0x08
FIFO_DEPTH = 16

def _seconds(value, name, allow_zero=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError('invalid ' + name)
    return float(value)

class UartLiteTx:
    """Writes never exceed FIFO space (UART Lite silently drops writes when TX_FULL).
    Every wait sleeps yield_s so an RX pump thread can still take the GIL."""
    def __init__(self, mmio, *, timeout_s=1.0, yield_s=0.0002, sleep=time.sleep, monotonic=time.monotonic):
        self.mmio = mmio
        self.timeout_s = _seconds(timeout_s, 'timeout_s')
        self.yield_s = _seconds(yield_s, 'yield_s')
        self.sleep = sleep
        self.monotonic = monotonic

    def _wait(self, ready, message):
        deadline = self.monotonic() + self.timeout_s
        while not ready(int(self.mmio.read(STAT))):
            if self.monotonic() > deadline:
                raise TimeoutError(message)
            self.sleep(self.yield_s)

    def _wait_space(self):
        self._wait(lambda s: not s & STAT_TX_FULL, 'TX FIFO stayed full; check clock/reset/baud')

    def _wait_drained(self):
        self._wait(lambda s: s & STAT_TX_EMPTY, 'TX FIFO never drained; check clock/reset/baud')

    def write_fill_fifo(self, data):
        """Recommended: keep up to 16 bytes queued, confirm drain once per call."""
        for byte in bytes(data):
            self._wait_space()
            self.mmio.write(TX, byte)
        self._wait_drained()

    def write_stop_and_wait(self, data):
        """Anti-pattern kept for comparison: waits for an empty FIFO after EVERY byte."""
        for byte in bytes(data):
            self._wait_space()
            self.mmio.write(TX, byte)
            self._wait_drained()

class UartLiteModel:
    """TX FIFO + shift register on a virtual clock. A written byte starts shifting at
    max(write time, previous byte end) and occupies the FIFO until it starts.
    sleep(s) advances the clock by s + sleep_overhead_s (OS timer slack)."""
    def __init__(self, baud=115200, bits_per_character=10, fifo_depth=FIFO_DEPTH, sleep_overhead_s=0.0):
        if type(baud) is not int or baud <= 0 or type(bits_per_character) is not int or bits_per_character <= 0 or type(fifo_depth) is not int or fifo_depth <= 0:
            raise ValueError('invalid UART model parameters')
        self.char_s = bits_per_character / baud
        self.fifo_depth = fifo_depth
        self.sleep_overhead_s = _seconds(sleep_overhead_s, 'sleep_overhead_s', allow_zero=True)
        self.now = 0.0
        self.shift_end = 0.0
        self.pending_starts = []
        self.out = bytearray()
        self.dropped = 0
        self.sleep_calls = 0
        self.accesses_since_yield = 0
        self.max_accesses_between_yields = 0

    def _access(self):
        self.accesses_since_yield += 1
        self.max_accesses_between_yields = max(self.max_accesses_between_yields, self.accesses_since_yield)
        self.pending_starts = [t for t in self.pending_starts if t > self.now]

    def read(self, offset):
        self._access()
        if offset != STAT:
            return 0
        queued = len(self.pending_starts)
        return (STAT_TX_EMPTY if queued == 0 else 0) | (STAT_TX_FULL if queued >= self.fifo_depth else 0)

    def write(self, offset, value):
        self._access()
        if offset != TX:
            return
        if len(self.pending_starts) >= self.fifo_depth:
            self.dropped += 1
            return
        start = max(self.now, self.shift_end)
        self.shift_end = start + self.char_s
        self.pending_starts.append(start)
        self.out.append(int(value) & 0xFF)

    def sleep(self, seconds):
        self.sleep_calls += 1
        self.accesses_since_yield = 0
        self.now += _seconds(seconds, 'sleep seconds', allow_zero=True) + self.sleep_overhead_s

    def monotonic(self):
        return self.now

def benchmark(data, mode, *, baud=115200, yield_s=0.0002, sleep_overhead_s=0.0):
    """Deterministic offline comparison; seconds include waiting until the last byte has shifted out."""
    data = bytes(data)
    model = UartLiteModel(baud=baud, sleep_overhead_s=sleep_overhead_s)
    tx = UartLiteTx(model, yield_s=yield_s, sleep=model.sleep, monotonic=model.monotonic)
    if mode == 'fill_fifo':
        tx.write_fill_fifo(data)
    elif mode == 'stop_and_wait':
        tx.write_stop_and_wait(data)
    else:
        raise ValueError('mode must be fill_fifo or stop_and_wait')
    return {'mode': mode, 'bytes': len(data),
            'seconds': max(model.now, model.shift_end),
            'wire_seconds': len(data) * model.char_s,
            'dropped': model.dropped, 'bytes_match': bytes(model.out) == data,
            'sleep_calls': model.sleep_calls,
            'max_accesses_between_yields': model.max_accesses_between_yields,
            'hardware_verified': False}
