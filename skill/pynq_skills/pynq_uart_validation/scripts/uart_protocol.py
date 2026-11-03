"""Offline binary framing: A55A + uint16be length + payload + CRC32be + 5AA5.
This is a demonstration contract, NOT the existing HMI protocol or a UART driver.
"""
import math, struct, zlib
HEAD = b'\xa5\x5a'
TAIL = b'\x5a\xa5'

def _positive(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError('invalid ' + name)
    return value

def encode(payload, max_payload=4096):
    _positive(max_payload, 'max_payload')
    if max_payload > 65535 or not isinstance(payload, bytes) or not 0 < len(payload) <= max_payload:
        raise ValueError('invalid payload')
    body = struct.pack('>H', len(payload)) + payload
    return HEAD + body + struct.pack('>I', zlib.crc32(body)) + TAIL

class FrameParser:
    def __init__(self, max_payload=4096, frame_timeout_s=1.0):
        _positive(max_payload, 'max_payload')
        if max_payload > 65535 or isinstance(frame_timeout_s,bool) or not isinstance(frame_timeout_s,(int,float)) or not math.isfinite(frame_timeout_s) or frame_timeout_s <= 0:
            raise ValueError('invalid parser limits')
        self.max_payload = max_payload
        self.timeout = float(frame_timeout_s)
        self.buffer = bytearray()
        self.started = None
        self.last_now = None

    def reset(self):
        self.buffer.clear()
        self.started = None
        self.last_now = None

    def feed(self, chunk, now):
        if not isinstance(chunk, bytes) or len(chunk) > self.max_payload + 10:
            raise ValueError('feed bounded bytes chunks; split larger reads')
        if isinstance(now,bool) or not isinstance(now,(int,float)) or not math.isfinite(now) or (self.last_now is not None and now < self.last_now):
            raise ValueError('now must be monotonic finite seconds')
        self.last_now = now
        errors, frames = [], []
        if self.started is not None and now - self.started >= self.timeout:
            errors.append('FRAME_TIMEOUT')
            self.buffer.clear()
            self.started = None
        self.buffer.extend(chunk)
        while self.buffer:
            at = self.buffer.find(HEAD)
            if at < 0:
                # retain only a possible first header byte
                keep = self.buffer[-1:] if self.buffer[-1:] == HEAD[:1] else b''
                if len(self.buffer) > len(keep): errors.append('NOISE_DISCARDED')
                self.buffer[:] = keep
                self.started = now if keep else None
                break
            if at:
                del self.buffer[:at]
                errors.append('NOISE_DISCARDED')
                self.started = None
            if self.started is None: self.started = now
            if len(self.buffer) < 4: break
            length = int.from_bytes(self.buffer[2:4], 'big')
            if not 0 < length <= self.max_payload:
                errors.append('LENGTH_INVALID')
                del self.buffer[0]
                self.started = None
                continue
            total = length + 10
            if len(self.buffer) < total: break
            packet = bytes(self.buffer[:total])
            if packet[-2:] != TAIL or int.from_bytes(packet[-6:-2], 'big') != zlib.crc32(packet[2:-6]):
                errors.append('FRAME_INTEGRITY_ERROR')
                del self.buffer[0]
                self.started = None
                continue
            frames.append(packet[4:-6])
            del self.buffer[:total]
            self.started = None
        return {'frames': frames, 'errors': errors, 'buffered_bytes': len(self.buffer),
                'hardware_verified': False}

class UartOwnership:
    """Process-local claim registry. Not an OS lock and not shared across kernels."""
    def __init__(self):
        self.claims = {}
    def acquire(self, resource, owner):
        if not isinstance(resource,str) or not resource or not isinstance(owner,str) or not owner:
            raise ValueError('explicit resource/owner names required')
        if resource in self.claims:
            raise RuntimeError('UART already claimed')
        self.claims[resource] = owner
    def release(self, resource, owner):
        if self.claims.get(resource) != owner:
            raise RuntimeError('not the UART owner')
        del self.claims[resource]

def timing_budget(payload_bytes, baud, fifo_bytes=16, bits_per_character=10):
    for value,name in [(payload_bytes,'bytes'),(baud,'baud'),(fifo_bytes,'FIFO'),(bits_per_character,'character bits')]:
        _positive(value,name)
    return {'wire_seconds': payload_bytes * bits_per_character / baud,
            'fifo_fill_seconds': fifo_bytes * bits_per_character / baud,
            'polling_guaranteed': False}
