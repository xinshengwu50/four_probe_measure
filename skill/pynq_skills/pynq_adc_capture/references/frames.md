# 帧契约与故障定位

code_lsb/code_bits不得超出frame_bits(<=64)；可选channel_lsb/channel_bits不与code重叠。预期channel必须匹配。其余位当保留位，不解释CRC/帧同步/芯片busy/overflow，需要芯片适配器提供status_ok。序号最多64bits且半范围比较；帧字和序号都禁止bool/负数/越界。

常见错误：低/高16bit提取反、补码当无符号、offset binary当straight、mV与V混用、前端增益乘除反、配置后的旧样本、ADC流水线返回前一转换。先用最小码/零码/中间码/最大码黄金向量，再查时序与通道。

原子快照可使用PL latch+ack、FIFO一次读完整记录，或经过设计验证的seq-before/frame/seq-after重试；简单地先读seq后读frame可能撕裂，不属于工具已验证能力。硬件序号在采集器内生成可证明帧事件次序，但不保证ADC本身无重复转换/输入稳定。

缺样/饱和/噪声/状态错误保留原因与原数据。改门限应保存新配置，不为了结果看起来正常隐藏quality_flags。
