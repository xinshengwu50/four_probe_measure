# 大模型协作记录精选（待人工审查）

整理日期：2026-10-11。用途：协作过程记录素材，突出开发者提供实物事实、跨 Agent 复核、AI定位/实现与验证的协作过程。

**此文件为编辑草稿，不是全会话记录，也不是当前工程验收报告。** 选取八个有区分力的案例；保留错误、修正与未完成项，不把所有讨论包装为成功。

## 阅读与证据说明
- 原文以四反引号text块展示，连续截取，不改写；每段给出消息编号、时间、绝对来源、行号。完整上下文可回原记录。
- “选择理由/贡献划分/历史结果/经验”为本轮编辑归纳，不冒充原始对话。
- “用户/助手”沿用导出角色。用户消息中有转贴另一Agent复核；未可靠标注模型身份，不虚构模型名称，也不将转贴内容全归为人手编写。
- 两组导出有重复，本文件选定一份权威来源，不以重复消息当多次验证。内部推理、交接摘要、工具调用和无意义寒暄不入选。
- 数字与命令结果引用历史快照，本轮只校验节选可追溯性，没有重跑历史工程。离线测试、RTL仿真、构建和板测分别陈述。
- 原文可能含私人绝对路径、网址或旧代码片段；仅为审查材料，不是运行指令。对外提交前应脱敏，不应直接执行其中硬件操作。

## 案例索引
|案例|主要价值|历史证据边界|
|---|---|---|
|01 构建来源|仿真新源、综合旧源的定位|新版bit当时未生成|
|02 安全调用链|看门狗时机、退出与解除武装|纯PS/mock不等于物理安全|
|03 运动互锁|矩阵、撤回、接触高度及反证|位置估计不是实际间隙|
|04 ADC事务|输入斜率区分位移和配置问题|读帧通过不代表配置保持|
|05 DAC边沿|将猜测转为可回解时序|未证明DAC模拟输出恢复|
|06 接线纠错|用户实物事实纠正AI结论|初始引脚误判已撤回|
|07 物理模型|独立参考与标定条件|数学一致不等于仪器准确|
|08 模拟显示|阶段式解耦验证|模拟不是空间测量|

---

## 案例 01｜仿真通过却交付旧 RTL：构建来源追溯

### 选择理由（编辑归纳）
问题不在算法，而在“验证对象”和“实际综合对象”不是同一份源文件。保留发现错误、用户停止授权以及未完成项，避免只展示成功。

### 对话原文节选

**E01｜207 · 助手 · 2026-10-11T11:46:07+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 8934–8934 行**

````text
⚠️ The Vivado-generated RTL copy is still the OLD revision — the build may have used stale RTL. Let me investigate.
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E02｜208 · 助手 · 2026-10-11T11:46:40+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 8940–8940 行**

````text
Found it — the user IP source is at the workspace-level `ip_repo`, not inside the project. The bitstream I built used stale RTL. Let me confirm and fix.
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E03｜211 · 用户 · 2026-10-11T11:50:13+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 8958–8958 行**

````text
不用帮我跑比特流
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E04｜217 · 助手（最终回复） · 2026-10-11T11:52:51+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 8996–9008 行**

````text
## 一、⚠️ 两个重要发现（都是这次跑构建才暴露的）

**1. 综合读的不是 `four_probe_pynq/hw/rtl/all/all_final.v`**
BD 里实例化的是打包用户 IP `xilinx.com:user:ALL_Final:1.0`，它的源码在 **`C:\Users\HS6Pro.L\Desktop\AMD\ip_repo\all_final\src\all_final.v`**（`.xpr` 里 `IPRepoPath = $PPRDIR/../ip_repo`）；工程里的那份被脚本标成 `used_in_synthesis false`。
→ **第一次重建静默综合了旧版 RTL**：`ipshared` 副本 221324 字节（旧），我改的是 208731 字节（新），综合日志确认读的是 `ipshared/5941/src/all_final.v`。

已修：`scripts/rebuild_all_final_with_radial_ports.tcl` 现在会先把 `hw/rtl` 镜像到 `ip_repo`，再**逐字节比对**生成的 `ipshared` 副本，不一致就直接报错停下。四个副本现已完全一致（`0E86B2D5…`）。

**2. 那次构建抓到我新写的 RTL 一个真 bug**
`DRC MDRV-1 Multiple Driver Nets`：`stats_ack_seq_pending` 被两个 always 块驱动（XSim 不报，综合才报）。已改成 **一次性脉冲 `stats_ack_seq_set`（AXI 写块驱动）+ 状态标志 `stats_ack_seq_pending`（统计块驱动）**，每个寄存器只有一个驱动。
并新增 **`scripts/check_all_final_multi_driver.py`** 离线检查这类问题（已用故意写坏的模块自测能抓到），当前 `all_final.v` 报 **0 个多驱动**。

## 二、批 3 改了什么
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E05｜217 · 助手（最终回复） · 2026-10-11T11:52:51+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 9029–9046 行**

````text
## 三、验证结果
- **5/5 个 XSim 测试台全部 PASS**（历史上第一次全绿）。
- 多驱动 lint：**0**；`xvlog`：**0 error**。
- Python 单元测试：**146 项 OK**。
- 4 份 `all_final.v`（hw/rtl、ip_repo、两个 ipshared）SHA256 完全一致。

## 四、没做 / 风险
- **比特流未生成**：`build/bit and hwh/all_design.bit` 是第一次（旧 RTL）的产物，`VERSION=0x414C5833`，PS 的版本门限会拒绝它 —— 不会误用，但也别烧录。你需要自己跑：
  `vivado -mode batch -source scripts/rebuild_all_final_with_radial_ports.tcl`
  （成功会打印 `Verified generated RTL is identical to …` 和 `PASS: rebuilt overlay in …`）
- 失败那次把 `impl_1` 留在 error 状态；脚本会先 `reset_run`，下次直接跑即可。
- 批 4 上板验证（VERSION 回读、kill PS 看门狗、25 点重跑、按复位观察停轴）未做。
- 构建日志里还有 **2 条既有（非本次引入）XDC 关键警告**，建议后续处理：`all.xdc:55/56` 的 `[get_ports RST_0]` 匹配不到任何对象（ADS8681 复位引脚约束没生效）、`all.xdc:257` 在 XDC 里用了 `foreach`（不支持，9 个模拟控制输出的 `DRIVE` 未生效）。

## 五、工作日志
`C:\Users\HS6Pro.L\Desktop\AMD\WORKLOG.md` 末尾新增 `2026-10-11 Batch 3: single RTL rework …`，含上述全部内容、两个发现、未执行项与风险。

要我接着做批 4 的上板清单（我可以先写好可直接粘贴到 Notebook 的验证步骤），还是先处理那两条 XDC 警告？
````

*连续原文节选；未选部分省略，完整上下文见来源。*

### 协作贡献与结果（编辑归纳）
贡献划分：开发者限定是否继续生成bit；Agent通过生成副本和IP源定位版本错配，并补构建一致性门禁。

历史结果：回复和工作日志记录5组XSim、146项Python、源码副本一致。最终新版bit当时未生成；第一次旧产物不能当修复交付。

### 可复用经验
可复用经验：查真实综合源→比较源码/封装IP/生成副本→同批bit/hwh→上板VERSION；不是只比较项目目录文件。对应fpga-baseline-audit。

### 人工审查
- [ ] 保留该案例
- [ ] 贡献归属、证据范围和原文语境准确
- [ ] 对外提交前完成路径/身份脱敏
- [ ] 需要补充的真实验收或原始附件：________

---

## 案例 02｜看门狗“实现了但没接线”：从函数存在到真实安全调用链

### 选择理由（编辑归纳）
这段包含跨记录复核与方案修正：心跳启动时机、退出线程、清故障和外部复位请求不能混为一件事。

### 对话原文节选

**E06｜142 · 用户 · 2026-10-11T10:57:38+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 5588–5607 行**

````text
二、🔴 方案没覆盖的阻塞点：板上的包目录名不是 pynq
方案的第 4 项写：

python


from sw.pynq.analog_frontend import AnalogFrontendController
但 Notebook 自己的 find_file() 暴露了板上真实的目录结构：

python


for candidate in (root / filename,
                  root / 'sw' / 'four_probe_sw' / filename,     # ← 板上是这个
                  root / 'sw' / 'pynq' / filename):
而 WORKLOG 第 3812 节就是 "Rename Four_ALL module directory to four_probe_sw" ✓

所以板上很可能是 sw/four_probe_sw/，方案里的 from sw.pynq... 在板上会直接 ImportError ✗

方案问的 Q3 只问了工程根目录，没问包目录名 ✗ —— 这比根目录更关键。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E07｜144 · 助手（最终回复） · 2026-10-11T10:58:51+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 5740–5805 行**

````text
## 2. 停止和解除武装

复核提出的“两条路径都在最后解除”方向正确，但需要一个安全条件：

```text
先确认 safe_off 成功、电流已经关闭
-> stop_heartbeat(join)
-> clear_faults()
```

顺序不能反：

- 如果先 `clear_faults` 再停心跳，下一次心跳又会重新武装看门狗；
- 如果先停心跳再清故障，之后不会再有心跳写入，看门狗保持未武装，不会在正常结束后误触发。

异常路径：

- 先执行 `safe_shutdown()`；
- 确认 `frontend.safe_off()` 和 `current_active=False`；
- 再停止心跳、清故障；
- 如果无法确认电流已关闭，则不调用 `clear_faults`，让已武装的看门狗在 1 秒后强制断电流。

这样兼顾：

```text
安全性：PS 死亡时看门狗仍会断电流
可用性：正常失败后可以立刻重跑，不会每次都被 preflight 拦住
```

## 3. `stop_heartbeat()` 修复

增加 join：

```python
thread = self._heartbeat_thread
self._heartbeat_stop.set()
if thread is not None:
    thread.join(timeout=1.0)
self._heartbeat_thread = None
```

避免线程泄漏和双线程喂狗。

## 4. 复位接口不修改

`request_system_reset()`、`clear_faults()` 的串口屏接口保持原样。
本轮只增加内部心跳生命周期管理，不改变复位协议。

---

# 二、零样本 `eligible=True`

将 raw 路径的：

```python
eligible = True
reason = "zero voltage fallback (no valid samples)"
```

改为：

```python
eligible = False
```

并真正实现 `require_count`：
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E08｜148 · 用户 · 2026-10-11T11:03:10+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 6577–6597 行**

````text
核实完毕。未修改任何文件。 方案已经收敛，我只补充两个新发现——其中一个暴露了方案内部的矛盾。

一、核实：它引用的两处事实都准确 ✅
断言	核实
"当前测试数是 121，不是 113"	✅ 正确 —— 我实测 Ran 121 tests ... OK
WORKLOG 第 3816 节记录了 sw/pynq → sw/four_probe_sw 的重命名	✅ 准确 —— 原文："Eliminate the local package name collision with the official PYNQ package by renaming the deployment module directory from sw/pynq to sw/four_probe_sw" ✓ 而且它当时就改了 Four_ALL 的测试导入 ✓
二、🎯 新发现：方案内部有矛盾 —— 自动 clear_faults() 会静默抹掉串口屏的复位请求
矛盾在哪
位置	说法
方案第四节	"复位接口留给串口屏开发者…写入和 clear 交串口屏" ✓
方案批次 1	"确认 safe_off 后清故障" ✗
这两条冲突。 而且 RTL 里 CLEAR_FAULTS 同时清两个锁存：

verilog


5031: end else if (clr_faults_wr) begin
5032:     reset_latched <= 1'b0; watchdog_tripped <= 1'b0;      // ← 两个一起清
5033:     watchdog_cnt <= 32'd0; watchdog_armed <= 1'b0;
后果链条
代码块
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E09｜149 · 助手（最终回复） · 2026-10-11T11:03:33+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 6694–6752 行**

````text
# 一、`clear_faults()` 与串口屏复位请求冲突

RTL 当前行为：

```verilog
end else if (clr_faults_wr) begin
    reset_latched <= 1'b0;
    watchdog_tripped <= 1'b0;
    watchdog_cnt <= 32'd0;
    watchdog_armed <= 1'b0;
end
```

所以 `CLEAR_FAULTS` 同时做三件事：

```text
清 reset_latched
清 watchdog_tripped
解除 watchdog 武装
```

如果 PS 在扫描结束的 `finally` 中无条件调用 `clear_faults()`，确实会：

```text
串口屏按下复位
-> reset_latched=1
-> PS 检测到 MeasurementAbortedError
-> safe_shutdown()
-> finally 调用 clear_faults()
-> reset_latched 被静默抹掉
-> 串口屏无法确认复位已被响应
```

这与“复位接口留给串口屏、清除必须人工确认”的约定冲突。

## 我将采用的三分支规则

顺序保持：

```text
先 safe_shutdown / safe_off
再 stop_heartbeat(join)
最后才考虑是否解除故障
```

逻辑伪代码：

```python
def _finish_scan(self):
    safe_off_ok = False

    # 1. 先安全关断
    try:
        result = self.frontend.safe_off()
        safe_off_ok = not bool(result.get('current_active'))
        if hasattr(self.frontend, 'status'):
            safe_off_ok = not bool(self.frontend.status().get('current_active'))
    except Exception:
        safe_off_ok = False
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E10｜158 · 助手（最终回复） · 2026-10-11T11:10:38+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 8025–8072 行**

````text
# 分析结论

这份复核补充的三条都成立，而且它把问题的层级拆得更清楚了：

```text
PS abort_check  -> 只能让软件提前退出等待
Z/R STOP        -> 能停 Z/R，但会清 homed
X 控制器        -> 根本没有停止命令
RTL 复位/看门狗 -> 当前完全不参与轴停止
```

因此“按下复位立即停止”这件事，必须同时改 PS 和 RTL，单靠批次 1 做不到。

---

# 一、X 轴确实没有停止命令

我核实 RTL：

```verilog
AXI_REG_X_CONTROL:
    if (axi_wstrb_reg[0] && axi_wdata_reg[0])
        axi_x_var_start_pulse <= 1'b1;
```

X 只有：

```text
bit0 = start
```

没有：

```text
STOP
ABORT
CLEAR
```

X 控制器结构：

```verilog
x_busy
x_pulse_cnt
x_target_active
```

一旦 `x_busy=1`，它就会一直输出脉冲，直到：
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E11｜170 · 助手（最终回复） · 2026-10-11T11:21:05+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 8639–8656 行**

````text
## 三、执行的验证
- `py -3 -m unittest discover -s tests -t .` → **137 项全部通过**（原 121，新增 16，无删除）；其中 2 项按新契约更新（零样本断言 `eligible=False`；部分样本测试显式传 `require_count=False`）。
- `py -3 -m py_compile` 三个模块 → PASS。
- 未执行：任何 XSim / 综合 / 上板（本批次纯 PS，无 RTL 改动）。

## 四、工作日志
追加在 `C:\Users\HS6Pro.L\Desktop\AMD\WORKLOG.md` 末尾（`2026-10-11 Batch 1 (pure PS) repair`），含全部字段；全文件统一为 CRLF，未触碰损坏隔离区。

## 五、未验证 / 遗留风险
- **验证范围**：心跳与三分支收尾以 mock 对象驱动，覆盖逻辑路径。
- 串口屏复位与 PS 清锁存之间仍有**微秒级竞争窗口**（读 STATUS 与写 CLEAR_FAULTS 之间），批次 3 的 `WATCHDOG_DISARM`(CONTROL bit7) 才能根除。
- X 轴仍无法软件急停（需 RTL 加 abort）。
- 看门狗仍不可观测（`watchdog_armed` 不可读，批次 3 加 STATUS bit18 + 0x140）。
- `SUM_SQUARES` 位宽、ACK/SEQ、自动 disarm、fail-closed 默认窗口未动 → 需批次 3 一次性重建。
- Notebook 仍走自制 `load_module()`，与包导入是双路径 → 批次 2 统一（并顺带加只读安全状态单元）。
- 外部复位后 `reset_latched` 会保留，`preflight()` 会按设计拒绝启动，需操作者确认后 `clear_faults()`。

要我继续批次 2（`sw/pynq → sw/four_probe_sw` 重命名 + Notebook 改写）吗？
````

*连续原文节选；未选部分省略，完整上下文见来源。*

### 协作贡献与结果（编辑归纳）
贡献划分：开发者转贴并补充复核，要求核对板上目录和复位目的；Agent追踪真实入口，发现纯PS取消不等于PL停止，再拆分修复批次。转贴复核不等于人工独立完成全部代码核验。

历史结果：纯PS批137项单元测试与编译检查记录通过；该批未执行XSim、综合或上板，微秒级清锁存竞争仍需后续独立DISARM解决。

### 可复用经验
可复用经验：安全功能应检查调用链、首次硬件使能前的保护时机、线程生命周期和异常分支；故障锁存与解除武装分开。对应motion-safety-review。

### 人工审查
- [ ] 保留该案例
- [ ] 贡献归属、证据范围和原文语境准确
- [ ] 对外提交前完成路径/身份脱敏
- [ ] 需要补充的真实验收或原始附件：________

---

## 案例 03｜互锁修复引发撤回阻塞：从 busy 互斥升级到接触高度保护

### 选择理由（编辑归纳）
这是很好的反复复核案例：新增互锁不一定更安全，错误的互锁会拒绝安全撤回；静止压针也会造成横向拖动危险。

### 对话原文节选

**E12｜230 · 用户 · 2026-10-11T12:07:09+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 9250–9288 行**

````text
二、🎯 我发现：互锁矩阵是不对称的 —— 正是这个 bug 的镜像
我把三轴的启动前置检查逐个列出来：

发起轴	检查 z_busy	检查 r_busy	检查 x_busy
Z	（自身）	✅ 刚恢复	✅
R	❌ 没有	（自身）	✅
X	❌ 没有	❌ 没有	（自身）
证据
R 的检查（3399 行）——漏了 z_busy：

verilog


3399: end else if ((main_state != S_IDLE) || x_busy || err_latch) begin
3400:     r_error_code <= R_ERR_BUSY;
✓ 检查了 x_busy ✗ 但没有检查 z_busy

X 的检查（745、744 行）——完全没检查其它轴：

verilog


744: assign x_direct_start     = axi_x_start_pulse     && (main_state == S_IDLE) && !err_latch;
745: assign x_var_direct_start = axi_x_var_start_pulse && (main_state == S_IDLE) && !err_latch;
3253: if((x_start_internal || x_direct_start || x_var_direct_start) && !motion_all_lock) begin
✓ 只检查 main_state == S_IDLE（遗留状态机已停用 → 实际恒为真）和 !err_latch ✗ ✓ 全项目搜 x_* 与 z_busy / r_busy 的组合 → 零匹配 ✗

后果，用你们自己的话
"若探针在下压状态就是拖拽风险"

X 在 Z 下压时启动 → 探针接触状态下旋转 → 拖过硅片 ✗
R 在 Z 下压时启动 → 径向拖拽 ✗
这正是你们刚修好的那个险情的另外两个方向 ✗

三、严重性评估（我尽量客观）
正常路径是安全的 —— 靠的是 PS 的相位顺序
PS 的扫描顺序是 Z 抬 → R 移 → X 转 → Z 下压 → 测量 ✓ 从不重叠 ✓

而且 PS 侧明确知道这个险情 —— safe_shutdown() 的 docstring 写着：
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E13｜241 · 助手（最终回复） · 2026-10-11T12:15:11+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 9673–9687 行**

````text
只分析、未改任何文件。逐项核实结果如下（其中两处结论与你不同）。

## 一、你这条的核实结果

| 你的论断 | 核实 |
|---|---|
| `z_busy` 不存在（项目里 0 次） | ✅ 最小修正成立 |
| R 补 `z_direct_busy`、X 改在汇聚点更好 | ✅ 同意 |
| 冲突检查在 `case` 之前（3618 vs 3619） | ✅ 原文位置一致 |
| `z_done_reg<=0` 在检查之前 → 20 s 超时 | ✅ 顺序确实如此（3612 行前清 done） |
| `Z_CMD_HOME`(3622) / `RETURN_HOME_SAFE`(3642) 无条件 `Z_DIR_UP` | ✅ 两条都核实 |
| (b) 应排除（依赖 z_position，而它恰好在最需要时不可靠） | ✅ 同意，而且理由比你写的更硬 |
| 锁存型 abort 后 X 停不下来 → 与 Z 抬针重叠 | ⚠️ 见下（机制不同，结论是"被丢弃"而非"重叠"） |

**(b) 我再补一条更硬的理由**：`Z_CMD_HOME` / `RETURN_HOME_SAFE` 本身**完全不看 `z_position`** —— 它们靠 `sen_stable`（home 传感器）+ 目标位 0 终止。所以 (b) 不只是"在需要它的场景里失效"，而是**给这两条命令引入一个它们现在刻意不依赖的量**，与 `safe_shutdown()` docstring 里"position counter may be wrong"的设计前提直接矛盾。排除是对的。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E14｜245 · 用户 · 2026-10-11T12:19:48+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 9865–9881 行**

````text
一、你的证据链我逐条核实，全部成立
你的论断	核实
3602 复位同时清 z_homed 和 z_position	✅ z_done_reg<=0; z_fault<=0; z_homed<=0; z_position<=0; ✓
3607 STOP 清 z_homed 但保留 z_position	✅ 原文：if ((axi_z_stop_pulse || motion_stop_pulse) && z_direct_busy) begin z_state<=Z_STATE_IDLE; z_timeout_cnt<=0; z_done_reg<=0; z_homed<=0; end ✓ 这是我没找到的第二条 fail-closed 路径 ✓
3606 CLEAR 不伪造回零	✅ 只清 z_fault / z_error_code / z_done_reg ✓ 不碰 homed/position ✓
z_homed<=1 的 5 个赋值点全部由 sen_stable==0 门控	✅ 我逐点确认了 ✓ 见下
STATUS bit19 空闲 / 0x148 空闲	✅ 两者都空闲 ✓
z_homed==1 的物理锚定 —— 我把 5 个点全查了
行	上下文	门控
3621	Z_CMD_HOME：传感器已在家	if (sen_stable==0) ✓
3641	RETURN_HOME_SAFE：已在家	else if (z_position==0 && sen_stable==0) ✓
3645	Z_CMD_ZERO	if (sen_stable==0) ✓
3654	MOVE 中 return_home 撞到传感器	if (z_after_setup_return_home && sen_stable==0) ✓
3680	Z_STATE_HOME 状态撞到传感器（正常回零路径）	if (sen_stable==0) ✓ ← 这条我上一轮没验到，现在确认 ✓
而失效方向是全面的：

代码块
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E15｜265 · 助手 · 2026-10-11T12:32:47+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 10502–10502 行**

````text
7 条反证**全部命中**（每条变异都被对应断言抓住），RTL 已恢复到已验证版本。现在第 3、4 步：同步镜像 + 版本号。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E16｜268 · 助手 · 2026-10-11T12:33:50+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 10520–10520 行**

````text
5 处失败都定位了，其中一处是**我实现里的真矛盾**（等待失败却仍然发回位命令）。一起修：
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E17｜271 · 助手（最终回复） · 2026-10-11T12:35:46+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a12076_20261009/conversation.md)，第 10550–10567 行**

````text
## 二、实现了什么

**RTL（VERSION `0x414C5834` → `0x414C5835`）**
- **(a)** `Z_CMD_HOME`/`RETURN_HOME_SAFE` 豁免冲突检查。安全依据：Z 的 STEP/DIR **独占**（`step_pulse <= (z_driver_armed && z_direct_busy) ? z_pul_out : 1'b0`），遗留状态机无路径抢引脚。
- **(a')** `wire z_probe_clear = z_homed && (z_position <= z_safe_travel_reg)`：
  - R：**所有**命令（含 R HOME）拒绝，错误码新增 `R_ERR_NOT_CLEAR = 10`（丢弃、不置 fault）；
  - X：加在**唯一汇聚点**（覆盖 `x_start_internal`），静默丢弃；
  - `0x148 Z_SAFE_TRAVEL` R/W，**上电默认 0**（fail-closed）。
  - `z_homed` 是 fail-closed 的关键：复位清 `homed`+`position`，停轴清 `homed` 保留 `position`，而 `homed=1` 只能由 home 传感器置位。
- **STATUS[19]** 粘滞"有运动命令被拒"（三轴 × 各拒绝原因），**只由 CLEAR_FAULTS 清**；独立 always 块驱动，未新增多驱动。

**PS**
- `configure_z_safe_travel()`：用 `full_down - half_up`（单一来源）写 0x148，**回读必须完全相等**（太小挡死扫描、太大静默削弱，都立刻报错），在 `preflight()` 调用；
- `read_safety_status()` 增加 `motion_refused / z_safe_travel / z_homed / z_position / probe_clear`；
- **(c1)** 回位前等 X 停（有界）；**(c2)** 用**实测** `X_POSITION` 而非陈旧的 `_current_x_target`；
- 可选 `z_lateral_lift_steps`（默认=当前行为；设 0 则横向运动改在全收位，换来 3650 步真实裕度，25 点约 +23 s），Notebook 暴露为 `Z_LATERAL_LIFT_STEPS`。

## 三、验证（全部通过）
````

*连续原文节选；未选部分省略，完整上下文见来源。*

### 协作贡献与结果（编辑归纳）
贡献划分：开发者提供三轴矩阵及纠正意见；Agent以真实信号名、命令入口和状态逻辑核验，补前置条件、拒绝可观测性及反证测试。双方都发现并承认过自身疏漏。

历史结果：工作日志记录5组XSim、7条变异反证、154项Python；当条新版bit尚未生成。位置来自步数估计，不能证明真实机械间隙。

### 可复用经验
可复用经验：验证命令×危险状态矩阵，不仅检查busy；故意移除高度门限/撤回例外，证明测试能抓错。HOME例外依赖真实安全方向，不适用于所有轴。对应motion-safety-review及golden-reference-verification。

### 人工审查
- [ ] 保留该案例
- [ ] 贡献归属、证据范围和原文语境准确
- [ ] 对外提交前完成路径/身份脱敏
- [ ] 需要补充的真实验收或原始附件：________

---

## 案例 04｜ADC读帧修复后配置丢失：两个已知输入定位不同层级的问题

### 选择理由（编辑归纳）
保留实测数值和后续新问题，展示不是一次猜中；读取与配置需要独立事务契约。

### 对话原文节选

**E18｜327 · 用户 · 2026-10-04T21:33:27+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a0e7c7_20260928/conversation.md)，第 15871–15911 行**

````text
第一步：万用表实测 ADS AIN_P - AIN_GND (V)：2.494

确认输入稳定在 2.4940 V，按 Enter 开始第一帧采集...

capture=live_voltage_1, samples=240

  [000] raw=0xBE7C0000 high16=0xBE7C low16=0x0000

  [001] raw=0xBE7C0000 high16=0xBE7C low16=0x0000

  [002] raw=0xBE7B0000 high16=0xBE7B low16=0x0000

  [003] raw=0xBE7C0000 high16=0xBE7C low16=0x0000

  [004] raw=0xBE7C0000 high16=0xBE7C low16=0x0000

  [005] raw=0xBE7D0000 high16=0xBE7D low16=0x0000

  [006] raw=0xBE7C0000 high16=0xBE7C low16=0x0000

  [007] raw=0xBE7D0000 high16=0xBE7D low16=0x0000

  [008] raw=0xBE7C0000 high16=0xBE7C low16=0x0000

  [009] raw=0xBE7B0000 high16=0xBE7B low16=0x0000

  [010] raw=0xBE7C0000 high16=0xBE7C low16=0x0000

  [011] raw=0xBE7C0000 high16=0xBE7C low16=0x0000

  ... 228 more frames

all frames: count=240 unique=4 span=196608

high16                 unique=   4 span=     3 std=    0.539 first=0xBE7C last=0xBE7C

low16                  unique=   1 span=     0 std=    0.000 first=0x0000 last=0x0000

high16_swap_bytes      unique=   4 span=   768 std=  138.054 first=0x7CBE last=0x7CBE

low16_swap_bytes       unique=   1 span=     0 std=    0.000 first=0x0000 last=0x0000
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E19｜329 · 助手（最终回复） · 2026-10-04T21:34:09+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a0e7c7_20260928/conversation.md)，第 15987–16093 行**

````text
这次实机验证已经成功，33 位捕获修改确实生效了。

## 验证结果

第一步：

```text
DMM = 2.494 V
预期 code = 48730
实测 high16 = 0xBE7C = 48764
误差 = +34 code ≈ 5.3 mV
```

第二步：

```text
DMM = 3.762 V
预期 code = 56845
实测 high16 = 56897
误差 = +52 code ≈ 8.1 mV
```

变化量：

```text
预期变化 = +8115 code
实测变化 = +8133 code
跟踪比例 = 约 100.2%
```

说明：

```text
RX_REG[31:16] 现在就是正确的转换结果字段
```

之前的固定 1 bit 右移已经消失，说明：

- RVS 等待逻辑；
- 33 个 SCLK；
- 丢弃第一个采样位；
- 保留后 32 位到 `SPI_RX_Data`；

这一组合已经在实机上生效。

## 当前状态

现在可以确定：

```text
low16 稳定为 0x0000
high16 正确跟随 ADS AIN_P - AIN_GND
shift30_15 不再代表转换结果
```

后续不要再使用：

```text
RX_REG[30:15]
```

也不需要继续对负码做“位修复”。当前残余误差约 `5～8 mV`，属于下一步零偏和增益校准范围。

## 下一步

当前 Bitstream/HWH 可以作为有效版本冻结：

```text
33 位 ADS 捕获版本
```

然后继续测试四探针电流回路：

1. 重新运行四档电流扫描；
2. 每档记录：
   - `high16`
   - `P2-P3` DMM
   - `H4.1` DMM
   - 实际电流
3. 先做零电流或 `P2-P3` 短接基线；
4. 再进行已知电阻测试；
5. 最后接真实四探针和样品。

如果已知电阻测试正常，例如：

```text
RANGE0 + 10 kΩ -> P2-P3 约 0.95 V
RANGE1 + 1 kΩ  -> P2-P3 约 0.95 V
RANGE2 + 100 Ω -> P2-P3 约 0.95 V
RANGE3 + 10 Ω  -> P2-P3 约 0.95 V
```

就可以继续进入真实样品测量。

工作日志已追加实机验证结果：

```text
C:\Users\HS6Pro.L\Desktop\AMD\WORKLOG.md
```

记录时间：

```text
2026-10-04 21:45 +08:00
```

目前唯一剩余的系统性误差是约 `5～8 mV` 的小偏置，后续应按量程做零偏扣除。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E20｜344 · 助手 · 2026-10-04T22:27:52+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a0e7c7_20260928/conversation.md)，第 16816–16825 行**

````text
这次数据已经直接暴露出新的根因：`0x9Axx/0xA2BC` 对应的是 ADS8681 的**默认 ±12.288 V 档**，不是配置后的 ±5.12 V。说明 33 位长帧把配置写命令破坏了。

修复方案：配置写帧恢复为 32 位，只有读取帧使用 33 位丢首拍。这样能同时保证：

```text
配置写命令正确进入 ADS
读取帧仍能对齐 D31:D0
```

我现在修改两份 RTL。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E21｜348 · 助手（最终回复） · 2026-10-04T22:34:03+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/1/session_01a0e7c7_20260928/conversation.md)，第 16851–16952 行**

````text
这次数据已经定位到新的明确原因：**ADS 仍工作在默认的 ±12.288 V 档，说明 RANGE_SEL 写配置没有生效。**

这些码值与默认 ±12.288 V 档完全吻合：

```text
AIN_P-AIN_GND = 2.498 V -> 预期默认档约 0x9A11，实测 0x9A11
2.495 V -> 0x9A0F，实测 0x9A0F
2.585 V -> 0x9B04，实测 0x9B04
3.339 V -> 0xA2BC，实测 0xA2BC
```

如果按配置后的 ±5.12 V 档，2.5 V 应约为 `0xBE7C`，而不是 `0x9Axx`。

所以问题不是 ADC 位对齐，也不是模拟输入，而是：

```text
33 位长帧破坏了 ADS 的 32 位配置写命令
```

## 已完成修改

两份 RTL 已同步：

```text
C:\Users\HS6Pro.L\Desktop\AMD\four_probe_pynq\hw\rtl\all\all_final.v
C:\Users\HS6Pro.L\Desktop\AMD\ip_repo\all_final\src\all_final.v
```

修改为：

```text
配置写帧：32 位
正常读取帧：33 位，丢弃第一位
```

具体包括：

- 新增 `SPI_CONFIG_WIDTH=32`；
- 保留 `SPI_FRAME_WIDTH=33`；
- 配置帧仍发送完整的 `0xD0140003`；
- 读取帧继续使用 33 位，丢弃首拍；
- 新增动态帧长度选择；
- 修复了 `spi_frame_bits` 多驱动问题。

## 验证结果

```text
ADC 窗口 XSim：通过
模拟板控制/DAC XSim：通过
OOC 综合：
0 errors
0 critical warnings
```

两份 RTL 最终 SHA256 一致：

```text
AB2794D40EAFBAE0D0F316AD6302BE1C39A4F6DD36CF6B8DB175D0FC307040B5
```

## 下一步

必须重新生成：

```text
Bitstream
HWH
```

然后重跑 15 号引导测试。

预期结果应变为：

```text
ADS 2.498 V -> high16 ≈ 0xBE73
ADS 2.495 V -> high16 ≈ 0xBE60
ADS 2.585 V -> high16 ≈ 0xC0A0
ADS 3.339 V -> high16 ≈ 0xD379
```

不再出现：

```text
0x9Axx
0xA2BC
```

这类默认 ±12.288 V 档码值。

工作日志已追加到：

```text
C:\Users\HS6Pro.L\Desktop\AMD\WORKLOG.md
```

记录时间：

```text
2026-10-04 22:34 +08:00
```

当前仍属于代码和综合验证通过，尚未在 PYNQ 实机上验证配置档恢复后的结果。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

### 协作贡献与结果（编辑归纳）
贡献划分：开发者提供DMM模拟输入与ADC原始帧；Agent比较码值变化量及不同量程的斜率，先定位捕获对齐，再识别写配置的副作用。

历史结果：两个已知输入跟踪支持当时读取路径修复；后续配置仍需验证，不能将读帧成功推为全链路成功。工作日志记录配置恢复32位后的离线仿真/综合，注明该轮为离线验证。

### 可复用经验
可复用经验：不要将33拍当作ADS8681的通用规范；那是特定控制器丢弃首拍的实现。分别验证配置帧、读帧、dummy位、复位及量程保持。对应hardware-chain-diagnosis和PYNQ SPI/ADC工具。

### 人工审查
- [ ] 保留该案例
- [ ] 贡献归属、证据范围和原文语境准确
- [ ] 对外提交前完成路径/身份脱敏
- [ ] 需要补充的真实验收或原始附件：________

---

## 案例 05｜静态 GPIO 正常但 DAC 不更新：逐边沿验证首末位

### 选择理由（编辑归纳）
硬件表象不能代替协议证据；本例把“引脚不适合SPI”转为可验证的具体时序假设。

### 对话原文节选

**E22｜35 · 用户 · 2026-10-01T21:18:28+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 9246–9246 行**

````text
静态GPIO正常，手头没有逻辑分析仪，不会把AR3-AR5换成A0-A2，你再想想还有没有别的测试或者可能出现的问题，有没有可能AR引脚不适合发送这样的信号
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E23｜36 · 助手 · 2026-10-01T21:22:05+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 9252–9252 行**

````text
你这个静态 GPIO 测试很关键：它说明 AR3～AR5 至少能输出稳定的高低电平，但还不能证明 DAC 收到了正确的 **24 位时钟帧**。我检查了现有发送函数和 DAC8562 时序要求，发现一个比“AR 引脚不适合 SPI”更具体的可疑点：最后一个 SCLK 下降沿和 SYNC 拉高被写在同一次 GPIO 操作里。我先把这个时序问题用离线波形测试确认并修正，再给你一套不用逻辑分析仪的上板排查步骤。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E24｜37 · 助手 · 2026-10-01T21:25:46+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 9269–9324 行**

````text
## 现在这样排查

### 1. 先确认板上运行的是修正版

把更新的 `probe_board_test.py` 复制到 PYNQ，**重启 Jupyter Kernel**，重新加载 Overlay 和 `ctrl`。只替换电脑上的文件不会改变板上已加载的 Python 模块。

保持 `CURRENT_EN=0`，暂时不要接真实样品，然后重新执行 DAC 扫描，重点先测 `0x0000` 与 `0x8000`：

```python
ctrl.enable_current(False)
ctrl.write_dac(0x0000)
# 万用表测 R26 的 DAC_OUT 端对 AGND

ctrl.write_dac(0x8000)
# 再测同一点，并测 R26 的 VSET 端对 AGND
```

先看两次读数**是否变化**，不要先用某个固定电压值判定成败。

### 2. 若仍为 0，用万用表“放慢”SPI

万用表读不到正常发送时很短的脉冲。修正版可临时把每步延时拉长，让 `SYNC` 维持低电平数秒：

```python
ctrl.enable_current(False)
old_delay = ctrl.spi_delay_s

try:
    ctrl.spi_delay_s = 0.2
    print("现在开始发送；立即测 U3 pin6（SYNC）对 AGND")
    ctrl.write_dac(0x8000)
finally:
    ctrl.spi_delay_s = old_delay

print("发送结束；再测 DAC_OUT 和 VSET")
```

发送过程中，**U3 pin6（SYNC）应保持接近 0V**；发送结束后应回到约 3.3V。测芯片细脚时务必防止表笔碰到相邻脚；优先选同网络、较大的焊盘。

### 3. 把检查点推进到 U3 芯片脚，而不只测排针

从当前 PCB 网表和 DAC8562 引脚定义核对，关键点是：

| U3 引脚 | 信号 | 应检查什么 |
|---:|---|---|
| 4 | LDAC | 对 AGND 应为低电平 |
| 5 | CLR | 对 AGND 应为高电平；低电平会清零输出 |
| 6 | SYNC | 慢速发送期间为低，结束后为高 |
| 7 | SCLK | 静态切换 GPIO 时能到达此脚 |
| 8 | DIN | 静态切换 GPIO 时能到达此脚 |
| 9 | AVDD | 实测约 3.3V |
| 10 | VREF | 实测约 2.5V |

**特别测 U3 pin5／R25 的 CLR 网络。**“VREF、供电正常”并不能排除 CLR 被异常拉低；DAC8562 的 CLR 是低电平触发的清零输入。LDAC 在当前设计中应接地，用于同步更新。

如果修正版仍无输出，结果可以这样分流：
````

*连续原文节选；未选部分省略，完整上下文见来源。*

### 协作贡献与结果（编辑归纳）
贡献划分：开发者给出静态电平测试与仪器限制；Agent检查最后采样边沿，补离线波形回解和慢速诊断。

历史结果：log/2/WORKLOG.md的2026-10-01末位修复条目记录6项专项和121项全套测试，24个下降沿正确；该轮没有新的PCB输出或示波器实测。DAC零输出的硬件根因不能据此判定已解决。

### 可复用经验
可复用经验：模拟记录GPIO操作→在CS有效期间按器件边沿回解→数完整采样位→检查收尾/下一帧；静态GPIO只能证明电平，不证明完整事务。对应hardware-chain-diagnosis及pynq_spi_validation。

### 人工审查
- [ ] 保留该案例
- [ ] 贡献归属、证据范围和原文语境准确
- [ ] 对外提交前完成路径/身份脱敏
- [ ] 需要补充的真实验收或原始附件：________

---

## 案例 06｜引脚判断被实际接线纠正：保留错误与撤回，而非只展示正确答案

### 选择理由（编辑归纳）
这是一段有价值的失败记录：AI误解AR名称，开发者明确使用独立SPI排针后，AI撤回不适用的建议。

### 对话原文节选

**E25｜57 · 助手 · 2026-10-02T19:05:13+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 9811–9817 行**

````text
**有一处足以让 DAC 完全收不到三路信号的错误：当前 XDC 的物理引脚约束，与“接 AR3、AR4、AR5”的方案不一致。**

| 信号 | GPIO 位 | 当前 XDC 约束 | PYNQ-Z2 手册中的 AR 引脚 |
|---|---:|---|---|
| DAC_SCK | bit1 | `H15` | **AR3 = `V13`** |
| DAC_DATA | bit2 | `T12` | **AR4 = `V15`** |
| DAC_SYNC | bit3 | `F16` | **AR5 = `T15`** |
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E26｜58 · 用户 · 2026-10-02T19:07:22+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 9834–9834 行**

````text
我现在bit用的就是在pynq的spi排针，接线也是在这些spi排针
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E27｜59 · 助手 · 2026-10-02T19:07:59+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 9840–9846 行**

````text
明白，是我上一条把你的**实际接线位置**理解错了，抱歉。你接的是 PYNQ 的独立 SPI 排针，而当前 XDC 的 `H15/T12/F16` 正对应这组排针的 `AR_SCK/AR_MOSI/AR_SS`。因此，**我上一条所说的引脚不匹配问题不适用于你现在的接线**，不需要为了这件事改 XDC 或重做 bit。

针对发送逻辑，我做过只读模拟：现有 DAC 测试代码在 **SYNC 拉低期间发送了完整的 24 个 SCLK 下降沿**，DIN 在各下降沿之前设置；测试码 `0x1234` 被逐位还原为预期帧 `0x181234`，随后 SYNC 拉高。**没有发现三路信号的软件发帧逻辑存在“少一个时钟”或“最后一位未发送”的错误。**

但这只证明代码写入 GPIO 的顺序正确，**不证明波形已到 U3**。如果 DAC_OUT 仍为 0，下一项最有区分力的检查是：发送一帧慢速 `0x188000` 时，直接在 **U3 pin6（SYNC）、pin7（SCLK）、pin8（DIN）** 测量，而不只量 PYNQ SPI 排针或 J_CTRL。尤其要确认 SYNC 为低的整个期间，U3 pin7 确实完成 **24 次下降沿**；万用表能确认静态高低，却不能仅凭读数证明边沿数。若 U3 引脚处波形也正确，再转查 DAC 的 CLR#、VREF、供电及器件本身，不能仅凭 DAC_OUT 为 0 判定芯片损坏。

本轮未修改文件，仅做离线分析。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

### 协作贡献与结果（编辑归纳）
贡献划分：开发者提供不可从代码确认的真实接线事实；Agent承认误解，保留现有XDC/bit，转向芯片端动态测量。

历史结果：只读逻辑检查，不含该轮硬件测量；最初“引脚不匹配”结论不适用于澄清后的接线，不能作为最终成果引用。

### 可复用经验
可复用经验：先确认实际针脚和测点，不凭旧注释、信号昵称推断接线；信息不对称时问最阻塞的一件事。对应hardware-chain-diagnosis。

### 人工审查
- [ ] 保留该案例
- [ ] 贡献归属、证据范围和原文语境准确
- [ ] 对外提交前完成路径/身份脱敏
- [ ] 需要补充的真实验收或原始附件：________

---

## 案例 07｜独立物理模型审查与VSET条件确认：避免旧代码自证和重复补偿

### 选择理由（编辑归纳）
本例把算法、仪器校准和接触变化分开，并明确拒绝为了落入目标电阻率区间拟合系数。

### 对话原文节选

**E28｜178 · 用户 · 2026-10-06T18:07:43+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 16737–16738 行**

````text
## My request:
数据发送是正常的，没有第九个点因为ADC没电了，不是代码原因，你去建模验证这个四探针测量的模型，看看有没有计算模型错误，我们供给VSET的电压实测应该是0.990V，所以测定值电阻需要电压电流修正，测量硅片的电阻率应该在1.8-2.2之间，因为手压的原因数据误差较大
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E29｜179 · 助手 · 2026-10-06T18:08:08+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 16744–16746 行**

````text
我会把第九点缺失按你说明的ADC断电处理，不再当作代码故障。接下来只针对四探针计算模型做核对：单位、几何修正、正反向合并和电流校准。

VSET实测0.990V可能影响激励电流，但要先确认现有电流校准表是否已经包含这个影响，避免重复修正。我也不会为了让结果落在1.8～2.2Ω·cm而反推系数。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E30｜180 · 助手 · 2026-10-06T18:12:14+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 16752–16754 行**

````text
初步发现一个需要重点验证的问题：现有厚度修正公式在 \(W/S=0.645\) 时算出约7.993，随后被硬截成1.05。现有测试验证的是“与旧代码一致”，不是独立物理正确性。

我会另建不控制板卡的参考模型，用两种独立计算方法交叉验证厚度修正和极限情况。对于均匀硅片、上下表面绝缘、等间距四针这些明确假设，参考厚度因子初算约0.988；同时会单独检查正反电流不相等时的合并公式。现阶段先不替换正在使用的计算模型。
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E31｜181 · 助手 · 2026-10-06T18:29:21+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 16793–16852 行**

````text
### 为什么说旧公式有问题？

旧公式在厚度/间距为0.645时，未截断结果约为：

```text
7.993164
```

随后直接限制到：

```text
1.05
```

**硬截断不等于物理正确。** 原有测试断言FW等于1.05，只证明程序与旧代码一致，没有独立验证实际厚度修正。

但这里也有边界：如果你的硅片是分层、双面扩散结构，或者背面与导电平台形成电接触，就不能不加确认地使用上述均匀绝缘背面模型。**仅凭材料名称“硅”，不足以决定采用哪种修正模型。**

## 2. 用旧图相同输入比较，结果是多少？

旧图的输入为：

```text
70.4mV / 10mA → V/I = 7.04Ω
```

对同一输入计算：

| 模型 | 电阻率 |
|---|---:|
| 当前程序 | **2.16314Ω·cm** |
| 独立均匀平板参考 | **2.03310Ω·cm** |

这两个值都在你给的1.8～2.2范围附近。**2.03310不是根据这个范围反推出来的，而是独立方程计算结果。** 旧图本身仍不能作为精度标准。

有限圆片边界我也检查了：50mm直径、1mm间距下，中心和偏心2～4mm的二维薄片边界因子差异很小，不能解释手压数据数倍变化。厚度与边界因子简单相乘只能作近似，不能冒充精确有限厚圆柱模型。

## 3. VSET=0.990V应该怎样修正？

**VSET是电流源的设定电压，不是V23测量电压，也不是ADC参考电压。**

在线性恒流区、且标定条件明确时：

\[
I_{\text{现在}}
=I_{\text{校准表}}
\frac{VSET_{\text{现在}}}{VSET_{\text{标定时}}}
\]

有两种不同情况：

### 电流表是在1.000V时标定的

现在实测0.990V，则条件性地：

\[
I_{\text{现在}}=0.99I_{\text{表}}
\]

固定已测V23不变时：
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E32｜181 · 助手 · 2026-10-06T18:29:21+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 16830–16909 行**

````text
## 3. VSET=0.990V应该怎样修正？

**VSET是电流源的设定电压，不是V23测量电压，也不是ADC参考电压。**

在线性恒流区、且标定条件明确时：

\[
I_{\text{现在}}
=I_{\text{校准表}}
\frac{VSET_{\text{现在}}}{VSET_{\text{标定时}}}
\]

有两种不同情况：

### 电流表是在1.000V时标定的

现在实测0.990V，则条件性地：

\[
I_{\text{现在}}=0.99I_{\text{表}}
\]

固定已测V23不变时：

\[
R_{\text{修正}}=\frac{R_{\text{原}}}{0.99}
\]

电阻和电阻率增加约 **1.01%**。你当前两相电流参数会对应为：

- 正向：约 **85.706mA**；
- 反向：约 **80.076mA**。

### 电流表本来就是在0.990V时标定的

**不应再次乘0.99。** 表已经包含这个条件，再修正就是重复补偿。

而且，由参考电阻的V/R反算得到的“校准电流”，可能同时吸收ADC增益等误差，所以仍需要独立负载验证。

**既然你此前确认万用表V23与软件一致，没有依据仅因为VSET为0.990V，就再把V23乘或除0.99。** 电压修正应根据测量通道的零偏、增益与万用表参考确定。

## 4. 正反向合并还有一个可改进点

当前计算是：

\[
R_{\text{平均}}
=\frac12\left(\frac{V_f}{I_f}+\frac{V_r}{I_r}\right)
\]

你正反电流不相等，而电流、电压继电器都会翻转。在静态接触、相同增益和正确极性关系下：

\[
V_f=I_fR+E,\qquad V_r=I_rR-E
\]

能抵消静态偏置的估计为：

\[
\boxed{R=\frac{V_f+V_r}{I_f+I_r}}
\]

旧平均法在电流不相等时，会留下部分偏置影响。我已经用数学测试验证了这个差异。

**但加权公式不能消除两次采集之间的手压变化，也不能解决实际电流与校准表不一致。** 所以本轮只在离线工具中比较，没有直接替换运行算法。

## 5. 对你实际硅片结果的判断边界

若独立平板模型适用，且实际电流确实接近当前表中的86.572mA和80.885mA，那么电阻率为1.8～2.2Ω·cm时，预计电压量级为：

| 方向 | 预计电压 |
|---|---:|
| 正向 | **约540～660mV** |
| 反向 | **约504～616mV** |

如果仍是之前手压时的5～25mV，**1%的VSET影响和约6%的模型差异，都不能把它修正成2Ω·cm**。不能为达到预期区间强行调整系数。

这次附件中只有“8点回填成功”的日志，没有八点的具体V/I/ρ，因此我尚未对**本次实际八点**逐行重算。

## 6. 验证工具已经放好
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E33｜182 · 用户 · 2026-10-06T19:06:27+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 16936–16936 行**

````text
0.99
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E34｜184 · 助手 · 2026-10-06T19:08:01+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 16948–16968 行**

````text
明白，**标定电流表时和现在的VSET都是0.990V，因此不需要再做1%补偿。**

\[
I_{\text{现在}}=I_{\text{表}}\times\frac{0.990}{0.990}=I_{\text{表}}
\]

所以：

- **电流表保持原值**，不能再乘0.99；
- **电阻、电阻率不能再除0.99**；
- V23测量电压也不因VSET为0.990V而额外缩放。

我已把离线验证配置中的标定基准改为0.990V：

**`C:\Users\wxs\Desktop\fore_probe_demo\15_four_probe_model_validation.ipynb`**

Notebook执行及16项模型测试通过，记录在 **`C:\Users\wxs\Desktop\AMD\WORKLOG.md`**。正在运行的测量模型、校准表和位流没有修改。

现在重点剩下的是**厚度修正与实际硅片结构是否匹配**。此前算出的FW≈0.987875，适用于均匀硅片、底面绝缘的参考模型，不能直接套到所有结构上。

**这块硅片背面是绝缘放置，还是与金属台或背面电极形成电接触？**
````

*连续原文节选；未选部分省略，完整上下文见来源。*

### 协作贡献与结果（编辑归纳）
贡献划分：开发者澄清ADC断电、提供VSET及参考范围；Agent构建独立参考、检查几何/单位/正反合并，并询问标定基准后避免重复补偿。

历史结果：独立数学路线约一致，模型审查16项离线测试记录通过；约6.4%差异仅在明确均匀平板假设下成立，不代表实物精度已校正。0.990V同时用于原标定与当前工作时不再做1%修正。

### 可复用经验
可复用经验：黄金参考独立推导；区分原始测量、校准条件、模型假设、留出负载验证。样品结构未知时不能仅凭“硅片”选模型。对应golden-reference-verification。

### 人工审查
- [ ] 保留该案例
- [ ] 贡献归属、证据范围和原文语境准确
- [ ] 对外提交前完成路径/身份脱敏
- [ ] 需要补充的真实验收或原始附件：________

---

## 案例 08｜先做模拟显示，再接真实采集：把行列映射与测量精度解耦

### 选择理由（编辑归纳）
保留限制范围与用户确认，以展示阶段式联调，而不是将模拟25行当成真实25个位置的测量。

### 对话原文节选

**E35｜136 · 助手 · 2026-10-05T20:25:39+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 13805–13840 行**

````text
已修改。**本轮只修显示格式、错列映射和 25 点显示联调，没有改 ADC 算法、校准值或位流。**

- 综合页的源变量仍保持：`page1.x8` 是电阻率，`page1.x9/x10` 是掺杂浓度尾数/指数，**不要交换这组变量**。
- 单点硅页已改为：中间列 `x1/t19` 写掺杂浓度，右侧 `x11/t54` 写电阻率。
- 非三代 25 点页也同步改为：中间列掺杂浓度、右侧电阻率。
- 方块电阻尾数保持两位小数。

## 一、修改后的前初始化代码

**先清空 `page0` 原来的前初始化代码，再完整粘贴下面这一份，不要追加。** 原来重复的第二段已经删除。

也已保存为可直接复制的文件：  
[page0_preinitialize_fixed.txt](C:/Users/wxs/Desktop/AMD/HMI/project/page0_preinitialize_fixed.txt)

```text
// page0 前初始化：完整替换旧代码，不要追加到旧代码末尾
// 只修正显示格式；原有计算输入、评估占位与模型文案保留
// 小数部分显式补零，不依赖 covx 固定长度的具体实现

//方块电阻对page1.x86.val赋值，系数为100
page1.x87.val=page1.x86.val/100
page1.x88.val=page1.x86.val%100
covx page1.x87.val,page1.t91.txt,0,0
covx page1.x88.val,page1.t92.txt,0,0
if(page1.x88.val<10)
{
  page1.t92.txt="0"+page1.t92.txt
}
page0.t0.txt="方块电阻:"+page1.t91.txt+"."+page1.t92.txt+"Ω"

//直径取值
page1.x0.val=page0.x6.val/10
page1.x1.val=page0.x6.val%10
covx page1.x0.val,page1.t0.txt,0,0
covx page1.x1.val,page1.t1.txt,0,0
page1.直径.txt="直径"+page1.t0.txt+"."+page1.t1.txt+"mm"
````

*连续原文节选；未选部分省略，完整上下文见来源。*

**E36｜137 · 用户 · 2026-10-05T21:47:04+08:00｜[原记录](C:/Users/wxs/Desktop/AMD/log/2/four_probe_session_20261011_163943/conversation.md)，第 14256–14260 行**

````text
串口屏刷新正常，你直接写完整25点启动测试吧

<image name=[Image #1] path="C:\Users\wxs\Documents\Tencent Files\1507018156\nt_qq\nt_data\Pic\2026-10\Ori\70ce15aa35c96273d6f5fc7a6bdf4688.jpg">
[图片附件：此导出不嵌入原始图像数据，参见消息中的文件引用]
</image>
````

*连续原文节选；未选部分省略，完整上下文见来源。*

### 协作贡献与结果（编辑归纳）
贡献划分：开发者要求先跑通显示并反馈屏幕刷新；Agent修复rho/掺杂列映射、小数拼接，并提供不运动、不采ADC的诊断图样。

历史结果：用户明确反馈模拟数据串口屏刷新正常；只支持当时的显示链路，不证明ADC精度、电机轨迹或真实扫描完成。后续真实测量不是本节模拟验证的证据。

### 可复用经验
可复用经验：用易区分固定图样验证页/行/列，再接真实数据源；硬件驱动不应作为显示层测试依赖。对应pynq_uart_validation及pynq_result_history。

### 人工审查
- [ ] 保留该案例
- [ ] 贡献归属、证据范围和原文语境准确
- [ ] 对外提交前完成路径/身份脱敏
- [ ] 需要补充的真实验收或原始附件：________

---

## 不建议列为成果的内容
- 只有“已完成”、没有命令/输出/版本或用户反馈的回复。
- 与后续纠正冲突的旧判断，例如引脚误判、未确认前端增益就认定倍率笔误。
- 在指定物理假设之外推广模型，或为了命中样品参考区间调整系数。
- 将新版软件、旧bit、不同工程目录的测试数量拼成一次当前验收。
- 把示例/模拟/单元测试写为实际硬件完成，或以测试总数代替覆盖率。

## 最终审查建议
优先保留01、03、04、07为技术主案例；02证明PS/PL协作与安全责任；05、06证明调试和纠错；08作为阶段式验证补充。可根据报告篇幅删除整例，不建议仅删除未验证边界而保留成功结论。

来源清单及每段节选SHA-256在同目录selection_sources.json；它只证明节选与提供的导出文本一致，不证明原对话技术断言正确或导出身份真实性。
