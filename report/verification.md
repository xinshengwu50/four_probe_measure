# 验证与限制

## 本轮执行

- Python：board/pynq115项、src/project/tests158项通过；均为离线测试，无覆盖率百分比声明。
- XSim六套件全部终止PASS：fp_dsp、analog、axi、z_safety、stats_bank、reset_watchdog。
- 新FP_DSP对原生单位FULL/VERIFY/FORCED、一对正反窗口、开路、高偏置、所有权冲突和复位有端到端自检；PS回退路径确认只采两方向。
- 原生电压、定点系数、真实核心消费PL快照、1/9/25扫描编排、CSV/JSON保存、完整历史恢复和中断部分保存均有离线回归。
- 真实RX分帧/RST优先、心跳线程停止失败、Overlay下载前保护、独立人工恢复及恢复中再次RST有回归。
- 全部12个ALL_Final活动RTL文件和封装IP逐字节与备份一致；LSB、共模、校准电流/偏置逐常量一致。
- Vivado2026.1完整综合、实现、write_bitstream成功：PASS_BUILD_OVERLAY。

## 路由后资源

|指标|完整基线|当前版本|
|---|---:|---:|
|LUT|25157|12796（24.05%）|
|FF|24968|10900（10.24%）|
|BRAM Tile|104|0|
|DSP|39|17（7.73%）|
|WNS|+1.337ns|+1.728ns|
|WHS|+0.015ns|+0.045ns|

新报告：build/rebuilt/utilization.rpt、timing_summary.rpt、drc.rpt。约束内失败端点0；DRC0错误、30项警告（DSP流水及无负载网络）。不是零警告工程。

## 配对身份

- bit SHA256：`2137d9ffac43e02e5b3fa077f9288ffab401cd8b87789d1e03152a1ffa8364fa`
- hwh SHA256：`52a2b3c540bd6a1ae60e8d43783c90ffb6edd33ea1e6401563119fcd67ac3da7`
- PS24/ADC19/HMI11/FP_DSP5，控制器ABI0x414C5835，115200串口。
- build/build_provenance.json记录本次构建输入；部署清单与发布清单检查源码/产物一致性。

## 测试修订经过

初次GUI式XSim停在会话连接阶段，没有当作通过；结束仅属于本轮的进程后采用命令行XSim，最终六套件均运行到终止PASS。
继承的AXI旧夹具使用过时WINDOW_CYCLES参数、模块化前层级名、未满足Z回零/高度条件的运动指令及ALX1版本号。更新夹具匹配当前ABI：总线测试独立核验地址通道和读写，机械/复位约束由独立安全台验证；未修改DUT绕过互锁。
旧高级诊断测试被功能匹配的测试替代，并保留外部完整备份，不沿用原300项全部通过的结论。

## 尚未验证

本轮验证限于离线范围：RTL 仿真与 Python 回归；硬件接口（ADC 真实采样、电机运动、串口屏/TFT 显示、电流/偏置/压力标定、物理复位延迟与测量准确度）不在本轮范围内。
继承的PS DDR负偏斜警告、生成SmartConnect宽度警告和外部IO时序约束完整性仍需硬件复核。约束内正裕量不等于外部链路完整验收。
取消×4和ABBA改变了测量行为；不能声称读数精度改善。应从已知负载单点逐级验证到9/25点。
已有屏端图片页不再自动更新，应隐藏入口或标为不支持；本轮没有编辑.HMI或下载TFT。
