---
name: pynq-uart-validation
description: 增量收帧、CRC、拆包粘包、异常恢复、进程内所有权和线速/FIFO预算；AXI UART Lite填满FIFO发送及逐字节停等踩坑；离线示例不直接驱动UART。
---

# UART 协议与吞吐联调

读 README.md 决定适配边界；默认只执行 scripts/run_example.py、scripts/run_uartlite_benchmark.py 和 tests，不导入PYNQ、不连接UART、不运动。

FrameParser.feed(bytes, monotonic_seconds)返回frames与errors；错误必须记录并按应用策略中止或请求重发，不把受损帧当命令。超时由feed包括空chunk触发。

发送慢于timing_budget线速下限2倍以上时，先查驱动是否逐字节等TX_EMPTY，再考虑削减数据量。UartLiteTx.write_fill_fifo：每字节前只等TX_FULL清除，整段末尾等一次TX_EMPTY，等待中保持sleep让出GIL。不得去掉TX_FULL检查（会静默丢字节），也不得改成不sleep的忙等（会饿死RX泵）。只适用于MMIO直驱AXI UART Lite，不适用于PS UART或tty驱动。

协议为演示A55A+长度+payload+CRC32+5AA5，不兼容本工程现有HMI帧，不可直接替换屏幕固件。串口错误位须由硬件适配层上报。本地所有权仅同一registry对象有效，不是跨Kernel/进程锁；Linux调度不保证FIFO不溢出。

硬件接入需用户提供权威协议/字段/单位和页面映射；示例不授权改屏幕或测量代码。历史失败来源见 ../../evidence/cases.md，当前仅OFFLINE_TEST/MOCK，不声称跨板验证。
