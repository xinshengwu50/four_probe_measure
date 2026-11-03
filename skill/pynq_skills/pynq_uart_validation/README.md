# UART 协议与吞吐联调

## 适用与使用
增量收帧、CRC、拆包粘包、异常恢复、进程内所有权和线速/FIFO预算；离线示例不直接驱动UART。

包目录运行：
```bash
python -B scripts/run_example.py
python -B scripts/run_uartlite_benchmark.py
python -B -m unittest discover -s tests -v
```
也可打开 notebooks/01_offline_debug.ipynb，默认完全离线。

FrameParser.feed(bytes, monotonic_seconds)返回frames与errors；错误必须记录并按应用策略中止或请求重发，不把受损帧当命令。超时由feed包括空chunk触发。

## 验证范围
回归覆盖正常与故障路径，详见tests和根目录验证报告；示例仅MOCK，不代表硬件实测。

## 踩坑：AXI UART Lite 逐字节停等，吞吐只有线速约1/3
**适用**：PYNQ/任意Python通过MMIO直接驱动Xilinx AXI UART Lite（PG142，寄存器RX0x0/TX0x4/STAT0x8/CTRL0xC，TX FIFO16）的发送，例如串口屏、批量下发指令。与题目、板卡无关，只依赖IP寄存器语义。

**触发条件**：为防止FIFO满时写入被静默丢弃，驱动在每写1字节后都等`STAT.TX_EMPTY`（bit2）并`sleep`。FIFO实际只用1字节，每隔约2字节就要sleep一次；Linux/Windows的sleep精度远大于1字节时间（115200下87µs），吞吐被sleep精度决定，而不是由波特率决定。

**症状**：大批量刷屏明显慢于`字节数×10/波特率`。本队串口屏25点历史恢复6139B，线速0.53s，实际约2s才完成。

**定位步骤**：
1. `timing_budget(字节数, 波特率)`算出线速下限，再用`time.perf_counter()`包住实际发送；如果超过线速下限2倍以上，先查发送驱动，而不是先砍数据量。
2. 在驱动代码里找每字节都等`TX_EMPTY`的循环。
3. `python -B scripts/run_uartlite_benchmark.py`：离线虚拟时钟模型，对比两种写法在不同sleep开销下的耗时。

**修复**：`UartLiteTx.write_fill_fifo`。每个字节写之前只等`TX_FULL`（bit3）清除；整段写完后等一次`TX_EMPTY`；所有等待都保留`sleep(yield_s)`。可直接复制到自己的驱动，`mmio`传`pynq.MMIO(base, 0x10000)`。
- 不能去掉TX_FULL检查：FIFO满时UART Lite直接丢弃写入，指令会被截断（测试`test_unguarded_writes_lose_bytes`）。
- 不能改成不sleep的忙等：同进程里如果有RX泵线程，忙等会一直占着GIL，16字节RX FIFO约1.4ms就会溢出（测试`test_fill_fifo_still_yields_for_rx_thread`限制了两次让出之间最多的寄存器访问次数）。

**已验证效果**（OFFLINE_TEST，非BOARD）：在模型里发送6139B，sleep开销0/0.1/0.37ms时，停等写法分别为0.614/0.921/1.749s，填满写法都是0.533s（等于线速），零丢字节。源工程在Windows主机上用实时假UART Lite重放同一批指令：1.775s→0.597s。三种回归变异（退回停等、去掉TX_FULL检查、忙等不让出）都会被tests抓到。尚未上板计时。

**失效条件**：PS侧UART（Cadence，寄存器不同）、Linux tty驱动（`/dev/tty*`，内核已处理FIFO）、中断驱动发送、FIFO深度不是16的定制IP，以及需要逐字节间隔的慢设备。模型的sleep开销只是参数，不是任何板子的实测值；Linux调度仍然不能保证RX不溢出。

## 失败来源与边界
协议为演示A55A+长度+payload+CRC32+5AA5，不兼容本工程现有HMI帧，不可直接替换屏幕固件。串口错误位须由硬件适配层上报。本地所有权仅同一registry对象有效，不是跨Kernel/进程锁；Linux调度不保证FIFO不溢出。

UART源于历史FIFO溢出/双服务风险与显示耗时；历史管理源于返回页清空后必须从完整持久化快照恢复，而不是仅保存显示文本。来源见 ../../evidence/cases.md。不提供材料模型、真实HMI控件映射、通用bit或硬件急停。
