# 可复用 Agent 与 PYNQ 技能包

两类独立：Agent Skill指导AI做决策与验证；PYNQ Skill提供可运行工具。未安装全局技能，不改现场工程，不提供通用bit。

## Agent 工作流（5项）
|入口|用途|
|---|---|
|[fpga-baseline-audit](agent_skills/fpga-baseline-audit/SKILL.md)|实际综合源、封装IP、部署及版本审计|
|[ps-pl-contract-review](agent_skills/ps-pl-contract-review/SKILL.md)|地址/符号/单位/窗口/ACK与新鲜度契约|
|[hardware-chain-diagnosis](agent_skills/hardware-chain-diagnosis/SKILL.md)|Overlay→MMIO→测点→协议→模拟分层诊断|
|[motion-safety-review](agent_skills/motion-safety-review/SKILL.md)|真实调用链、看门狗、互锁、安全撤回|
|[golden-reference-verification](agent_skills/golden-reference-verification/SKILL.md)|独立模型、故障注入、假绿与证据分级|

使用：给agent提供对应SKILL.md、权威输入、实际故障日志与只读/写入授权。以assets/report.md组织输出。规则来自历史案例，未做独立agent前向行为评测。目录不自动赋予操作硬件的权限。

## PYNQ 工具（6项）
|入口|内容|
|---|---|
|[Overlay](pynq_skills/pynq_overlay_validation/README.md)|发布/寄存器契约；新增只读源码哈希比较|
|[SPI](pynq_skills/pynq_spi_validation/README.md)|4模式数字trace；新增独立配置/读取事务校验|
|[ADC](pynq_skills/pynq_adc_capture/README.md)|原帧与序号质量；新增偏置/增益逆算窗口|
|[电机](pynq_skills/pynq_motion_tuning/README.md)|参数/减速预览；新增可信高度与撤回策略审查|
|[UART](pynq_skills/pynq_uart_validation/README.md)|演示二进制协议、拆粘包/CRC/超时/吞吐预算；AXI UART Lite填满FIFO发送（逐字节停等踩坑）|
|[结果历史](pynq_skills/pynq_result_history/README.md)|完整CSV、缺失质量、来源隔离、先导航后回填|

## 一键离线验证
在此skill根目录运行：
```bash
python -B scripts/run_all_checks.py
python -B scripts/run_three_examples.py
python -B pynq_skills/pynq_uart_validation/scripts/run_example.py
python -B pynq_skills/pynq_uart_validation/scripts/run_uartlite_benchmark.py
python -B pynq_skills/pynq_result_history/scripts/run_example.py
```
第二条更新原三个包的6份MOCK报告，更新后运行 python -B scripts/refresh_manifest.py 重新生成manifest；它不是只读审计。两个新包各有01_offline_debug.ipynb，旧三个调试Notebook仍在各包notebooks中，默认不访问硬件。

## 复用/验证边界
核心标准库，不需要PYNQ就能跑离线回归。配置、契约、适配器必须按新板替换；不复制本队标定/地址/量程/机械参数。UART示例协议不是当前HMI协议；CSV回填回调不包含真实控件映射。所有示例为MOCK，数据页刷新不代表真实采集成功。

[来源索引](evidence/cases.md)记录历史失败与效果；[本轮验证](evidence/validation.md)记录实际执行范围。唯一任务账本为C:/Users/wxs/Desktop/AMD/WORKLOG.md，证据文件不是第二本进度日志。发布前应选择许可、脱敏并补充硬件/跨板验证。DMA未实现。
