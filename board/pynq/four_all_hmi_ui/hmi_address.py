# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Numeric page addressing for final - copy.HMI; no HMI renaming needed.

IDs come from the actual editor page list, NOT the .pa resource filenames.
"""
import re
import math
import time
import threading
from .uart import HMI_RX_POLL_S

PAGE_IDS = {
    "加载": 0, "首页": 1, "测量": 2, "修改参数": 3, "正在测量": 4,
    "测量完成": 5, "历史记录": 6, "个性化": 7, "page0": 8, "page1": 9,
    "九点非三": 10, "九点三代": 11, "V9": 12,
    "二十五非三1": 13, "二十五非三2": 14, "二十五非三3": 15,
    "二十五三代1": 16, "二十五三代2": 17, "二十五三代3": 18,
    "V251": 19, "V252": 20, "V253": 21,
    "单点非三": 22, "单点三代": 23, "V1": 24, "keybdB": 25,
    "storeR1": 26, "storeR2": 27, "storeR3": 28,
    "storeV1": 29, "storeV2": 30, "storeV3": 31, "store": 32,
}


def page_target(target):
    page, dot, rest = target.partition(".")
    if page in PAGE_IDS:
        return "p[%d]" % PAGE_IDS[page] + (dot + rest if dot else "")
    if re.fullmatch(r"p\[\d+\]", page):
        return target
    raise ValueError("Unknown HMI page: %r" % page)


def numeric_command(text):
    for name in sorted(PAGE_IDS, key=len, reverse=True):
        text = re.sub(r"(?<![\w\]])" + re.escape(name) + r"(?=\.)",
                      "p[%d]" % PAGE_IDS[name], text)
    text.encode("ascii", "strict")
    return text


class NumericPageUart:
    """Rewrite page prefixes and serialize each complete UART command."""
    def __init__(self, uart):
        self.raw = uart
        self.lock = threading.RLock()
        self._rx_lock = threading.Lock()
        self._rx_buffer = bytearray()
        self._rx_stop = threading.Event()
        self._rx_thread = None
        self.rx_byte_count = 0
        self.rx_error_count = 0
        self.rx_last_error = None
        self.rx_last_error_bits = 0
        self.rx_fatal_error = None
        self.last_image_error = None  # 仅诊断，不是持久软件锁。
        self.trace = False
        self.rx_transform = None
        self.rx_error_handler = None
        self.rx_fault_handler = None

    def send_command(self, text):
        command = numeric_command(text)
        with self.lock:
            self.raw.send_command(command)
            if self.trace and command == "p[9].n0.val=1":
                print("[HMI] TX range-ready navigation:", command, flush=True)

    def _drop_frame(self, message, bits=0):
        self.rx_error_count += 1
        self.rx_last_error = message
        self.rx_last_error_bits = bits
        with self._rx_lock:
            self._rx_buffer.clear()
        if self.rx_error_handler is not None:
            self.rx_error_handler(message)
        print('[UART] DROP_FRAME count=%d %s' % (self.rx_error_count, message), flush=True)

    def _receive_once(self):
        stat = getattr(self.raw, "stat", None)
        if stat is not None:
            status = int(stat())
            # Actual screen_button_test.Uart uses AXI UART Lite bits 5/6/7.
            if status & 0xE0:
                self._drop_frame("UART RX error bits=0x%02X; resend the request" % (status & 0xE0), status & 0xE0)
                self.raw.read_available()  # 数据完整性未知，不拼接残片成START。
                return
        chunk = self.raw.read_available()
        if self.rx_transform is not None:
            # Empty polls let the emergency parser expire incomplete wire frames.
            chunk = self.rx_transform(chunk)
        if chunk:
            overflow = False
            with self._rx_lock:
                self.rx_byte_count += len(chunk)
                if len(self._rx_buffer) + len(chunk) > 8192:
                    self._rx_buffer.clear()
                    overflow = True
                else:
                    self._rx_buffer.extend(chunk)
            if overflow:self._drop_frame('host RX buffer overflow; resend the request')

    def start_receiving(self, poll_s=HMI_RX_POLL_S):
        poll_s = float(poll_s)
        if not math.isfinite(poll_s) or not 0 < poll_s <= 0.0005:
            raise ValueError("115200 baud / 16-byte FIFO requires a fast RX pump (<=0.5ms); Linux scheduling may still overrun")
        if self._rx_thread is not None and self._rx_thread.is_alive():
            return
        self._rx_stop.clear()
        def receive():
            try:
                while not self._rx_stop.is_set():
                    self._receive_once()
                    self._rx_stop.wait(poll_s)
            except Exception as exc:
                self.rx_error_count += 1
                self.rx_last_error = "RX pump stopped: %s" % exc
                self.rx_fatal_error = self.rx_last_error
                if self.rx_fault_handler is not None:self.rx_fault_handler(self.rx_fatal_error)
        self._rx_thread = threading.Thread(target=receive, name="hmi-uart-rx", daemon=True)
        self._rx_thread.start()

    def stop_receiving(self):
        self._rx_stop.set()
        thread = self._rx_thread
        if thread is not None:
            thread.join(timeout=1.0)
        if thread is None or not thread.is_alive():
            self._rx_thread = None

    def discard_pending_rx(self):
        with self._rx_lock:
            self._rx_buffer.clear()

    def read_available(self):
        if self._rx_thread is None:
            return self.raw.read_available()
        with self._rx_lock:
            chunk = bytes(self._rx_buffer)
            self._rx_buffer.clear()
        return chunk

    def query_value(self, target, timeout_s=1.0):
        """Read-only probe: verify that the screen accepts numeric page targets."""
        target=page_target(target)
        timeout_s=float(timeout_s)
        if not math.isfinite(timeout_s) or timeout_s<=0:raise ValueError("invalid query timeout")
        self.send_command("get %s.val" % target)
        data=bytearray();deadline=time.monotonic()+timeout_s
        while time.monotonic()<deadline:
            data.extend(self.read_available())
            for start,byte in enumerate(data):
                if byte==0x71 and len(data)>=start+8 and data[start+5:start+8]==b"\xff\xff\xff":
                    return int.from_bytes(data[start+1:start+5],"little",signed=False)
                if byte in (0x00,0x02,0x03,0x1A,0x1B) and data[start+1:start+4]==b"\xff\xff\xff":
                    raise RuntimeError("HMI rejected %s: code=0x%02X; check page ID/component/global scope" % (target,byte))
            time.sleep(0.001)
        raise TimeoutError("HMI did not reply to get %s.val; RX=%s" % (target,data.hex(" ")))
