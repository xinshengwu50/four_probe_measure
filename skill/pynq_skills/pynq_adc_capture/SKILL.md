---
name: pynq-adc-capture
description: Decode configurable ADC frame bitfields and signed coding, collect atomic sequence-tagged samples, reject stale records and report quality; use for reusable ADC pipelines without application calibration.
---

# ADC帧解析与采集质量

1. 查明芯片传输函数、有效位域和编码再填AdcConfig；不要猜参考电压、偏置和增益。读references/frames.md。
2. 将硬件驱动作为provider注入capture；它必须有界/非阻塞，并返回原子的sequence+frame及可选status_ok。没有硬件序号/握手/FIFO时不宣称可靠新样本，不能使用Python循环计数伪造序号。
3. 同码值但不同序号是合法连续样本；相同序号丢弃。序号回卷使用模运算，缺失/乱序单独记录；计数器复位需要明确开启新的采集会话。
4. 默认Notebook读合成JSON，不导入PYNQ，不采ADC，不切电流或控制电机。
5. 用CLI/Notebook保留原始帧、解码值、序号、单位和质量标志；CaptureError.partial含失败前数据，不能把partial标为完整采集。
6. 无样本统计为null；电气接触/恒流是否成立属于应用独立判断，不用ADC质量通过替代。

## 经验增强入口
adc_window.py从相同偏置/增益逆算窗口，二补码跨零可能拆为两个原码区间；不会写PL，浮点边界按计算结果向内取整。
历史来源与验证边界见 ../../evidence/cases.md。
