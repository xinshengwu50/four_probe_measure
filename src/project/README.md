# 四探针电阻率测量系统

面向 PYNQ-Z2（xc7z020clg400-1），采用 PS/Python + PL/RTL 协作。
本版电压按 ADC 原生单位换算，不额外乘4，不提供独立显示倍率。

## 功能边界

保留：自定义单点、9点、25点；自动及授权范围内手动量程；半抬扫描、Z减速和周期回零；简单正反向测量；串口屏结果、离散色块热力图；CSV/JSON保存及最近四次完整历史；复位保持、看门狗和独立人工恢复。

删除：网页服务、自动双图片生成/上传、专用GaN实验预设、重复ABBA测量、频谱、直方图、指数拟合与毫秒波形记录。

GaN材料码仍为4，沿用AlGaN计算模型；结构2仍选择HEMT模型。旧历史中的AlN身份不改写。模型适用性、接触压力、实际电流和偏置仍需独立验证。

## 目录

|目录|用途|
|---|---|
|board/pynq|唯一上板入口01、匹配bit/hwh及完整Python依赖|
|src/project/hw/rtl|ALL_Final 及 FP_DSP v5|
|src/project/hw/constraints|引脚和时钟约束|
|src/project/hw/tb|可自检的RTL测试平台|
|src/project/sw/pynq|与部署包一致的生产Python源码|
|src/project/tests|原生单位、协议、模型、扫描和安全回归|
|src/project/scripts|BD重建和FP_DSP接入Tcl|
|src/ip_repo|ALL_Final封装IP|
|src/hmi/events|现有屏端事件参考；不是已重新编译的TFT|
|build/scripts|工程重建、构建、清单及一致性校验|
|build/rebuilt|本版构建产物及报告|
|sim|离线Python/命令行XSim入口及结果|
|report|当前技术说明、验证边界和历史AI协作证据|
|skill|独立可复用Agent/PYNQ技能；示例不表示本工程启用所有功能|
|data|实测结果归档位置，勿混入未经确认的旧数据|

## PS/PL划分

PS负责串口协议、安全授权、扫描规划、材料/几何模型、结果解释、CSV/JSON和历史回填。
ALL_Final负责ADC底层时序、前端控制、电机脉冲/减速、位置及安全互锁。
FP_DSP v5负责真实试档、基本均值判稳、每方向一个正式积分窗口和结果统计，通过AXI访问ALL_Final；底层复位/看门狗保护不能被它绕过。

接口：ALL_Final 0x40000000、AXI UART Lite 0x42C00000（115200/8N1）、probe_gpio 0x43C00000、FP_DSP 0x43C10000。
ALL_Final ABI仍为0x414C5835；FP_DSP版本5与旧版本4不兼容，驱动拒绝混用。

电压：ADC直二进制码先换算双极性ADC输入，再扣2.5V共模和保留的偏置表，不附加增益。
校准电流和偏置沿用既有表，不代表已对新换算重新标定；更换模拟板应独立标定，不能按目标电阻率反推倍率。

## 离线验证

```text
python -B sim/scripts/run_tests.py
python -B sim/scripts/run_hdl.py --vivado-bin <Vivado安装目录>/bin --suite all
python -B build/scripts/gen_register_map.py --check
python -B build/scripts/verify_delivery.py
```

测试不启动真实电机/电流。XSim必须有终止PASS且无Fatal/ERROR，不能只看进程返回0。
具体本轮结果见report/verification.md；覆盖率与实机精度未经测量时不作声明。

## 重建硬件

Vivado2026.1，使用纯英文短路径。

```text
vivado -mode batch -source build/scripts/create_project.tcl
vivado -mode batch -source build/scripts/build_overlay.tcl
```

本地工程为 `build/vivado/four_probe_measure.xpr`。Windows中文目录存在IP生成路径兼容问题；当前本机英文入口 `C:/Users/wxs/Desktop/four_probe_measure_open` 是指向本目录的目录联接，不是第二份副本。公开发布时请解压到英文短路径并运行Tcl。
默认发布包不包含Vivado缓存和生成工程。不要手改xpr；已有同名工程时重建脚本拒绝覆盖。
新构建放build/rebuilt，不自动替换上板文件。确认仿真/综合/实现后再复制同批bit/hwh，记录构建来源并更新部署/发布清单；不要给旧bit标注新源码身份。

## 上板

1. 上传整个board/pynq到同一Jupyter目录，不混用旧目录的模块。
2. 只运行01_four_all_system.ipynb。无需网页服务或Pillow图片生成环境。
3. 先停其他服务并关闭电流，确认机构不依赖Z保持扭矩，才允许加载Overlay。
4. 默认ALLOW_MOTION、ARM_CURRENT、ALLOW_100MA、GEOMETRY_CONFIRMED和人工恢复均False。不得为消除报错而放宽门限/行程。
5. 状态核对后运行服务格，由串口屏START触发测量。RANGE_READY是选档完成，不是整场完成。
6. 安全无负载检查、已知电阻单点、9点、25点、历史回填逐级验证。

Ctrl-C和屏幕RST触发停止保持，不自动回零。人工确认后在恢复格清故障并Z/R回零，X方位需确认。禁止靠重载bit/重启Kernel绕过故障。物理急停仍必需。

参数改变后安全停止并重建服务对象，不要在扫描中修改。测量结果保存到four_all_results；抓包保存到uart_capture；不再生成_wave.csv和自动上传图片。
已有屏幕图片页应隐藏入口或标为不支持，避免把旧图片当成新结果；本轮未修改.HMI或下载TFT。
23C/60%RH仍为占位值，压力自适应未实现。色块为离散采样位置示意，非连续成像；相对色阶不可直接跨批比较。

## 发布校验

有源码/结果变更后，先复核测试与构建来源，再依次更新部署清单、校验值、发布清单。
`build/scripts/package_release.py`创建zip，已有zip拒绝覆盖。清单哈希用于身份检查，不替代真实板卡验收。
历史协作摘录只记录当时事实，不能用作本版硬件验收证据。
