---
name: pynq-spi-validation
description: Validate configurable SPI modes, frame bit order, clock divider and CS/data timing in digital traces; use for SPI bring-up or regression models, not chip-command or analog electrical certification.
---

# SPI契约与数字时序验证

默认不访问硬件。调整examples或Notebook的CPOL/CPHA模式、位序、帧长、输入时钟、请求SCK、CS建立/保持和数据建立/保持周期。

1. 先读references/timing.md，确认目标芯片的模式与完整帧语义，不把通用字节当芯片初始化命令。
2. 用scripts/spi_contract.py计算分频，检查可实现速率不高于请求值。
3. build_trace是软件波形模板；validate_trace可检查单次CS低期间的数字记录。MODE0/2在leading采样，MODE1/3在trailing采样；位序独立配置。
4. 默认Notebook只生成合成trace，不下载Overlay或驱动信号。实际CSV要有可靠时基，整数时钟周期t_cycles和0/1电平。多事务先分段。
5. 波形检查通过只证明输入数字trace符合这份契约，不能证明模拟幅度、真实芯片接收、命令格式、MISO驱动冲突或器件供电正常。
6. 先运行tests，再用已测trace/手册验证适配；其他PYNQ板卡只换时钟与配置，不复用不兼容bit。

## 经验增强入口
spi_transactions.py逐事务独立验证配置/读取帧长；不是器件命令生成器，不假设读写同帧长。
历史来源与验证边界见 ../../evidence/cases.md。
