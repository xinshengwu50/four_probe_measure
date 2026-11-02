# 四探针自动测量系统（PYNQ-Z2）

> 基于 Zynq-7000 PS/PL 异构架构的四探针方阻 / 电阻率自动扫描、结果评估与安全联锁系统。

![platform](https://img.shields.io/badge/platform-PYNQ--Z2-blue)
![fpga](https://img.shields.io/badge/FPGA-xc7z020clg400--1-informational)
![vivado](https://img.shields.io/badge/Vivado-2026.1-orange)
![python](https://img.shields.io/badge/python-3.8%2B-blue)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)

---

> ## ⚠️ 安全警告：请务必先读完本节
>
> 本工程**驱动真实的 Z/X/R 三轴机构、向样品通入最高 100 mA 电流，并用探针下压样品表面**。
> 误操作可能**压碎样品**、**损坏探针**、**烧毁接触点**，或造成**人身伤害**。
>
> - 首次上电前必须完成机械限位、急停回路与电流回路的**人工验证**。
> - 所有安全门（`ALLOW_MOTION`、`ARM_CURRENT`、`ALLOW_100MA`、`GEOMETRY_CONFIRMED`）**默认全部关闭**。
> - **不要为了消除报错而擅自放大行程、超时或判据门限。**
> - 物理急停按钮**不可省略**，软件复位不能替代它。
> - 断电或 Ctrl-C 后机构**保持不动**，恢复前必须人工确认。

---

## 目录

- [1. 项目简介](#1-项目简介)
- [2. 主要特性](#2-主要特性)
- [3. 硬件需求](#3-硬件需求)
- [4. 软件需求](#4-软件需求)
- [5. 快速开始](#5-快速开始)
- [6. 系统架构](#6-系统架构)
- [7. 目录结构](#7-目录结构)
- [8. 测量原理与电压换算](#8-测量原理与电压换算)
- [9. 验证状态](#9-验证状态)
- [10. 故障与恢复](#10-故障与恢复)
- [11. 常见问题](#11-常见问题)
- [12. 参与贡献](#12-参与贡献)
- [13. 许可证](#13-许可证)
- [14. 免责声明](#14-免责声明)

---

## 1. 项目简介

四探针法（Four-Point Probe）是半导体与薄膜材料方阻测量的标准方法：外侧两根探针通恒定电流，内侧两根探针测电压，由 `R = V / I` 结合几何修正因子得到方块电阻 `Rs`，再乘以导电层厚度得到电阻率 `ρ`。

本工程把这一测量流程完整地实现在一块 **PYNQ-Z2** 上：

- **PS（ARM Cortex-A9 + Linux）** 负责材料与几何模型、串口屏协议、安全授权、扫描轨迹规划、结果解释与数据落盘。
- **PL（FPGA 逻辑）** 负责 ADC 底层时序、模拟前端与继电器控制、电机脉冲与减速、硬件级安全互锁。
- **FP_DSP（自定义 PL IP）** 在硬件中完成试档、判稳与正反向积分，把对时间精度敏感的环节从 Linux 用户态移出。

提供 **单点 / 九点 / 二十五点** 三种测量模式，结果实时显示在串口 HMI 屏上，并保存为 CSV / JSON 与最近四次完整历史。

---

## 2. 主要特性

| 特性 | 说明 |
|---|---|
| 三种扫描模式 | 自定义单点、9 点、25 点（同心圆环） |
| 自动量程 | 试档后按 `R = V / I` 自动选择激励电流档位，支持授权范围内手动指定 |
| 正反向测量 | 每个测点交换激励极性各测一次，抵消接触电势 |
| 精密 Z 轴 | 16 段减速表、半抬间隙、按点数周期回零 |
| 硬件安全互锁 | 复位保持、看门狗、轴忙检测、电流状态检测，均不可由软件绕过 |
| 串口 HMI 交互 | 结果、量程灯、热力图色块，全部由 PS 写屏控件完成 |
| 数据可追溯 | CSV / JSON / 最近四次完整历史，含量程、结构参数与原始 V/I |
| 离线可验证 | 全部 Python 逻辑与 RTL 均可在无硬件条件下跑测试 |

---

## 3. 硬件需求

| 项 | 型号 / 参数 |
|---|---|
| 开发板 | TUL **PYNQ-Z2** |
| FPGA | XC7Z020-1CLG400C（`xc7z020clg400-1`） |
| ADC | **ADS8681**（16 bit，双极性，SPI） |
| 串口屏 | USART HMI（串口指令集，115200 8N1） |
| 执行机构 | Z 轴（下压）+ R 轴（径向）+ X 轴（旋转）步进机构 |
| 连接 | Micro-USB（供电 / JTAG）、以太网（SSH / Jupyter） |

---

## 4. 软件需求

| 项 | 版本 |
|---|---|
| 板载系统 | PYNQ Linux（Ubuntu 22.04 基础，Xilinx 2024.1 内核） |
| Python | 3.8+ |
| Vivado | **2026.1**（仅重建位流时需要） |

运行时 Python 依赖保持在 PYNQ 镜像自带范围内（`pynq`、`numpy`）。**本版不需要 `Pillow`，也不需要启动网页服务。**

---

## 5. 快速开始

### 5.1 上板运行

1. 将整个 `board/pynq/` 目录上传到板卡上的**同一个** Jupyter 目录。
   **不要**与旧目录的模块混用——版本断言会拒绝不一致的组合。
2. 打开并**只运行** `01_four_all_system.ipynb`。
3. 按顺序执行 notebook 的各单元格：导入与版本核对 → 参数 → 加载 Overlay → 状态核对 → 启动服务。
4. 加载 Overlay 之前，必须先停止其他服务、**关闭电流**、确认机构不依赖 Z 轴保持扭矩。
5. 服务启动后，由**串口屏**发送 START 触发测量；HIST 回填最近四次完整历史；RST 触发系统复位。
6. 建议按 **安全无负载 → 已知电阻单点 → 9 点 → 25 点 → 历史回填** 的顺序逐级验证。

> `RANGE_READY` 表示**选档完成**，不是整场测量完成。

### 5.2 离线验证

无需连接硬件，测试不会启动电机或电流。

```bash
python -B sim/scripts/run_tests.py
python -B build/scripts/gen_register_map.py --check
python -B build/scripts/verify_delivery.py
```

RTL 仿真需要本机安装 Vivado：

```bash
python -B sim/scripts/run_hdl.py --vivado-bin <Vivado安装目录>/bin --suite all
```

> XSim 必须出现终止 **PASS** 且**无 Fatal / ERROR**，不能只看进程返回 0。

### 5.3 重建硬件

要求 Vivado 2026.1 与**纯英文短路径**（中文目录会导致 IP 生成路径兼容问题）。

```bash
vivado -mode batch -source build/scripts/create_project.tcl
vivado -mode batch -source build/scripts/build_overlay.tcl
```

生成工程位于 `build/vivado/four_probe_measure.xpr`。

重建注意：

- **不要手改 `.xpr`**，一律通过 Tcl 或 GUI 完成。
- 默认发布包**不含** Vivado 缓存与生成工程。
- 同名工程已存在时重建脚本会**拒绝覆盖**。
- 新构建先放 `build/rebuilt`，**不会自动替换上板文件**；确认仿真 / 综合 / 实现通过后，再连同同批 `bit` / `hwh` 一起复制，并更新部署清单与发布清单。
- **不要给旧位流标注新源码身份。**

---

## 6. 系统架构

### 6.1 PS / PL 分工

| 域 | 职责 |
|---|---|
| **PS** | 串口协议、安全授权、扫描规划、材料 / 几何模型、结果解释、CSV / JSON / 历史回填 |
| **ALL_Final** | ADC 底层时序、前端控制、电机脉冲与减速、位置与安全互锁 |
| **FP_DSP** | 真实试档、基本均值判稳、每方向一个正式积分窗口、结果统计（通过 AXI 访问 ALL_Final） |

设计原则：**底层复位与看门狗保护不能被 FP_DSP 或上层软件绕过。**

### 6.2 地址映射

| 外设 | 基地址 |
|---|---|
| ALL_Final | `0x40000000` |
| AXI UART Lite | `0x42C00000`（115200 8N1） |
| probe_gpio | `0x43C00000` |
| FP_DSP | `0x43C10000` |

ALL_Final 的 ABI 标识为 `0x414C5835`。

### 6.3 版本与兼容性

| 组件 | 版本 | 文件 |
|---|---|---|
| 四探针统一服务 | **11** | `hmi_four_all.py` |
| 最终测量系统 | **24** | `four_probe_sw/final_four_probe_system.py` |
| 直接 ADC 测量 | **19** | `four_probe_sw/direct_adc_measurement.py` |
| FP_DSP 驱动 | **5** | `four_probe_sw/pl_autorange.py` |

notebook 启动时会**断言**这些版本号；不一致请上传完整包并重启 Kernel，**不要跳过断言**。

> **FP_DSP v5 与旧版 v4 ABI 不兼容**，驱动会拒绝混用。

---

## 7. 目录结构

```text
four_probe_measure/
├── board/pynq/              唯一上板入口：notebook、匹配 bit/hwh、完整 Python 依赖
├── src/
│   ├── project/hw/rtl/      ALL_Final 与 FP_DSP v5（8 个子模块，30 个源文件）
│   ├── project/hw/tb/       可自检 RTL 测试平台（17 个）
│   ├── project/hw/constraints/  引脚与时钟约束
│   ├── project/sw/pynq/     与部署包一致的生产 Python 源码
│   ├── project/tests/       原生单位、协议、模型、扫描与安全回归（18 个 test_*.py）
│   ├── project/scripts/     BD 重建与 FP_DSP 接入 Tcl
│   ├── ip_repo/all_final/   ALL_Final 封装 IP
│   └── hmi/events/          现有屏端事件参考（不是已重新编译的 TFT）
├── build/
│   ├── scripts/             工程重建、构建、清单与一致性校验
│   └── rebuilt/             本版构建产物及报告
├── sim/                     离线 Python / 命令行 XSim 入口及结果
├── report/                  技术说明、验证边界与历史协作记录
└── skill/                   可独立复用的 Agent / PYNQ 技能（示例，不代表本工程启用全部功能）
```

---


## 8. 测量原理与电压换算

统一判据：**`R = V / I`**，与材料、厚度、直径无关。

电压链路（本版）：

1. ADC 直接二进制码 → 换算为双极性 ADC 输入电压；
2. 扣除 **2.5 V 共模**；
3. 扣除保留的**偏置表**；
4. **不附加任何增益**（本版不额外乘 4，也不提供独立显示倍率）。

> 校准电流与偏置沿用既有表，**不代表已对新的换算方式重新标定**。
> 更换模拟板后必须独立标定，**不能按目标电阻率反推倍率**。

---

## 9. 验证状态

| 项 | 状态 |
|---|---|
| Python 离线回归 | 可运行（`sim/scripts/run_tests.py`） |
| RTL 仿真 | 可运行（需 Vivado） |
| 寄存器映射一致性 | 可校验（`gen_register_map.py --check`） |
| 交付身份校验 | 可校验（`verify_delivery.py`） |
| **真实板卡验收** | **本仓库不声明已完成** |
| **覆盖率 / 实机精度** | **未经测量，不作声明** |

具体本轮结果见 `report/verification.md`。

---

## 10. 故障与恢复

| 事件 | 行为 |
|---|---|
| Ctrl-C / 屏幕 RST | **停止并保持**，不自动回零 |
| PL 复位 / 看门狗 | 锁存，需人工按安全流程恢复 |
| 轴忙 / 电流仍开 | 拒绝重新配置 PL |

恢复步骤：

1. 等待上一个服务格完全退出；
2. **人工确认机构安全与限位**；
3. 在恢复格中清除故障并执行 Z / R 回零（X 方位需单独确认）；
4. 回零成功后才可重新启动服务格。

> **禁止**靠重载 bit 或重启 Kernel 绕过故障锁存。
> 参数改变后必须安全停止并重建服务对象，**不要在扫描过程中修改**。

---

## 11. 常见问题

**Q：运行 notebook 报版本断言失败？**
A：说明上传的模块不完整或已被旧版覆盖。上传**完整** `board/pynq` 包并**重启 Kernel**，不要跳过断言。

**Q：报 `USE_PL_AUTORANGE=True 但本位流不含 FP_DSP`？**
A：所用 `bit`/`hwh` 不含 `fp_dsp_0`。换用匹配的位流，或显式改回 PS 侧测量路径。

**Q：屏幕显示 `RANGE_READY` 但数据页没有数值？**
A：该点被判为**无效**（`point_valid=False`），服务会写入空值而不是伪造结果。请查看日志中的 `INVALID point` 与失败原因。

**Q：中文目录下 Vivado 报 IP 生成路径错误？**
A：改用**纯英文短路径**。本机可用英文目录联接指向原目录，公开发布前请解压到英文路径后运行 Tcl。


---

## 12. 参与贡献

欢迎提交 Issue 与 Pull Request。请遵守以下约定：

1. **不要降低安全门限来让测试通过**——超时、行程、判据门限的修改必须在 PR 中说明依据。
2. 修改 HDL 后至少完成 elaboration 与对应 testbench；涉及顶层时执行综合检查。
3. 修改测量算法后与 `src/project/tests` 中的参考模型比对数值、单位与误差。
4. 新增源文件放在约定目录，文件名使用小写英文、数字与下划线。
5. 与硬件相关的修改，**必须明确标注是否已在真实板卡上验证**。未运行的检查不得记为通过。

---

## 13. 许可证

本项目采用 **Apache License 2.0** 许可证，允许自由使用、修改、分发与商业应用，并**明示授予专利许可**。

- 许可证全文：[`LICENSE`](LICENSE)
- 版权与第三方声明：[`NOTICE`](NOTICE)

**版权所有 © 2026 兰新宇、吴新胜、孙毅泽**

```text
Copyright 2026 兰新宇, 吴新胜, 孙毅泽

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

> 二次分发时请保留 `LICENSE` 与 `NOTICE`。若修改了源文件，请在文件头注明已修改（Apache-2.0 第 4(b) 条）。

---

## 14. 免责声明


- 作者**不对**因使用本工程造成的设备损坏、样品损毁、数据错误或人身伤害承担责任。
- 使用者须自行完成**机械、电气与人身安全**的评估与验证。
- 测量结果的准确性依赖于**探针状态、接触压力、样品表面处理、环境温湿度与校准电流**，本仓库未对特定样品承诺精度。
- 材料模型（含 AlGaN / HEMT 近似）的**适用范围需使用者自行确认**。

---

<div align=center>

**如果这个项目对你有帮助，欢迎 Star ⭐**

</div>
