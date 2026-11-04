# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Verified AXI UART Lite transport extracted from the working HMI driver.
RX=0x00, TX=0x04, STATUS=0x08, CONTROL=0x0C; 115200 baud is fixed in the screen UART Lite IP (8N1).
"""
from __future__ import annotations
import time
TJC_END = b"\xff\xff\xff"
U_REG_RX, U_REG_TX, U_REG_STAT, U_REG_CTL = 0x00, 0x04, 0x08, 0x0C
HMI_BAUD_RATE = 115200
HMI_RX_POLL_S = 0.0002

U_STAT_RX_VALID, U_STAT_TX_EMPTY, U_STAT_TX_FULL = 1, 4, 8
U_CTL_RST_TX, U_CTL_RST_RX = 1, 2

class Uart:
    """AXI UART Lite 薄封装（FIFO 深度 16，必须逐字节写）。"""

    def __init__(self, mmio, byte_timeout_s: float = 1.0) -> None:
        self._m = mmio
        self._byte_timeout_s = byte_timeout_s

    # ---- 状态 ----
    def stat(self) -> int:
        return int(self._m.read(U_REG_STAT))

    def rx_ready(self) -> bool:
        return bool(self.stat() & U_STAT_RX_VALID)

    def tx_ready(self) -> bool:
        """TX FIFO 还有空间。真正发完由 ``write_byte``/``write_bytes`` 末尾等待。"""

        return not bool(self.stat() & U_STAT_TX_FULL)

    def reset(self) -> None:
        self._m.write(U_REG_CTL, U_CTL_RST_TX | U_CTL_RST_RX)
        time.sleep(0.02)

    # ---- 读 ----
    def read_byte(self):
        if self.rx_ready():
            return int(self._m.read(U_REG_RX)) & 0xFF
        return None

    def read_available(self) -> bytes:
        out = bytearray()
        while self.rx_ready():
            out.append(int(self._m.read(U_REG_RX)) & 0xFF)
        return bytes(out)

    def read_exact(self, count: int, timeout_s: float = 1.0) -> bytes:
        """等收满 count 字节；超时返回已收到的部分。"""

        buf = bytearray()
        deadline = time.monotonic() + timeout_s
        while len(buf) < count and time.monotonic() < deadline:
            b = self.read_byte()
            if b is None:
                time.sleep(0.002)
            else:
                buf.append(b)
        return bytes(buf)

    # ---- 写 ----
    def _wait_tx_space(self) -> None:
        # FIFO 满时 UART Lite 会静默丢弃写入，所以每个字节写之前都要确认还有空位。
        deadline = time.monotonic() + self._byte_timeout_s
        while not self.tx_ready():
            if time.monotonic() > deadline:
                raise TimeoutError("TX FIFO 一直满，UART 可能没配好")
            time.sleep(0.0002)

    def _wait_tx_drained(self) -> None:
        deadline = time.monotonic() + self._byte_timeout_s
        while not (self.stat() & U_STAT_TX_EMPTY):
            if time.monotonic() > deadline:
                raise TimeoutError("等待 TX FIFO 清空超时，UART 可能没配好")
            time.sleep(0.0002)

    def write_byte(self, byte: int) -> None:
        self._wait_tx_space()
        self._m.write(U_REG_TX, byte & 0xFF)
        self._wait_tx_drained()

    def write_bytes(self, data: bytes) -> None:
        # 连续填满 16 字节 FIFO，只在满时等待，整段写完再确认清空一次：
        # 原来每个字节都等清空，FIFO 实际只用 1 字节，历史页恢复慢约 3 倍。
        # 等待时仍 sleep，让出 GIL，RX 泵线程（0.2 ms 轮询）不会被饿死。
        for b in data:
            self._wait_tx_space()
            self._m.write(U_REG_TX, b & 0xFF)
        self._wait_tx_drained()

    def send_command(self, text: str, *, terminator: bytes = TJC_END) -> None:
        """发一条 TJC 指令（自动补 FF FF FF）。"""

        self.write_bytes(text.encode("ascii", "strict") + terminator)

