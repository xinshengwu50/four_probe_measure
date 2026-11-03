# 实例复盘：三个真实失败与它们留下的规则

技能包最容易写成"正确的废话"——每条都对，但没人知道它从哪来、什么时候真能救命。这份文件把三次真实失败摊开：当时的判断、证据、错在哪、最后怎么定的。

三例都出自同一个 PYNQ-Z2 四探针项目（Zynq-7000 XC7Z020，Vivado 2026.1）。**没有一件是事后编的教学案例**：编译器输出和报告原文都在。

---

## 一、"这段是死代码"——我删了它，综合直接拒绝

### 背景

项目里有个 `meas_chain` 模块，负责从 ADC 采样算出电阻率 ρ 和薄层电阻 Rs。做资源优化时，我在 `all_final.v` 里搜它的输出信号 `rho`，看到的引用都在很深的位置，判断"没人用"，准备删除。

### 当时的"证据"

三条，每条单独看都成立：

1. 在 AXI 回读多路选择器（约 2200 行之后）附近搜索，没看到 `rho`/`Rs` 的 case 分支。
2. 一个 Tcl 探针脚本统计综合网表里 `*u_meas_chain*v0r*` 的实例数，结果是 **0**。
3. WORKLOG 里几轮优化都绕着从电机/BCD 那一大坨走，从没提过 ρ。

### 综合说了什么

改完提交，综合在 40 秒内失败：

```
ERROR: [Synth 8-36] 'rho' is not declared [all_final.v:1973]
ERROR: [Synth 8-36] 'Rs' is not declared  [all_final.v:1976]
```

真正的读取在 **1973/1976 行**，距离 `meas_chain` 的例化位置（约 917 行）有一千多行：

```verilog
localparam [11:0] AXI_REG_RHO = 8'h20;   // line ~436
localparam [11:0] AXI_REG_RS  = 8'h24;   // line ~437

AXI_REG_RHO: begin axi_rdata_reg <= rho; end   // line 1973
AXI_REG_RS:  begin axi_rdata_reg <= Rs;  end   // line 1976
```

### 消费者链

```
all_final.v:1973  AXI_REG_RHO ← rho
        ↓  AXI 0x020 / 0x024
all_final.py:238  def rho_raw(self) -> int: return self._mmio.read(REG_RHO)
all_final.py:382  "rho_raw": self.rho_raw(), "rs_raw": self.rs_raw()
        ↓
button_link.py:105  "rho_raw": self.rho_raw, "rs_raw": self.rs_raw
button_link.py:215  rho_raw = int(result.get("rho_raw", 0))
button_link.py:239  rho_raw=rho_raw, rs_raw=rs_raw      ← 写进每条 HMI 结果记录
```

删掉 RTL，屏幕按键测出来的 ρ/Rs 会**全变 0**。而且这个故障只在按物理按钮时才暴露——所有离线测试都不会发现。

### 三条"证据"为什么都错了

| 当时看到的 | 实际情况 |
|---|---|
| 在多路选择器附近搜不到 | 搜错了位置。真正的读取在 1973/1976，离我搜的地方 1000 行 |
| 网表里 `*u_meas_chain*v0r*` 计数为 0 | **假阴性**。综合会重命名内部寄存器，拿源码变量名去匹配网表单元本来就不可靠 |
| WORKLOG 没提 ρ | WORKLOG 没提不等于代码没用。进程记录不是代码索引 |

### 留下的规则

写进了 [ps-pl-contract-review](../agent_skills/ps-pl-contract-review/SKILL.md)：

> **判断 PS/PL 接口是否被使用，必须沿着 AXI 外设边界追踪到 Python 消费者，不能只搜信号名或数网表单元。**

具体操作是三步，缺一不可：
1. 找出信号进入 `axi_rdata_reg` 的 case 分支（不是搜信号名，是看那个 `case` 语句）。
2. 由寄存器偏移查出 Python 侧的常量（`all_final.py` 的 `REG_XXX`）。
3. 追踪该常量被谁读取、写进了什么（`button_link.py` 写进 HMI 记录）。

顺带一条：删除前先跑一次综合。40 秒的综合比两小时的调试便宜。

### 正确做法

真要删 `meas_chain`，得先把 PS 侧切到已有的 `pl_resistivity.read_rho_q()`（0x154/0x158），让屏幕不再依赖 0x020/0x024，**然后**才能删 RTL。那是跨 PS/PL 的接口迁移，不是顺手清理。本工程没做。

最终 `all_final.v` 与 `tb_all_final_window.sv` 已逐字节恢复原状（`diff -b -B` 验证）。

---

## 二、时序瓶颈在不该找的地方找了很久

### 背景

优化完成后 WNS 只有 +1.337 ns（50 MHz 时钟，周期 20 ns）。想进一步提高频率，得先知道最差路径在哪。

### 怎么找到的

跑 `report_timing -max_paths 40 -path_type summary`，拿到 40 条最差路径，**全部**长这样：

```
Slack: 1.337ns
Source:      u_fit/b_syy_reg[6]/C
Destination: u_fit/best_rss_reg[*]/CE
Data Path Delay: 18.121ns  (logic 8.9ns / route 9.2ns)
Logic Levels: 33 CARRY4
```

40 条全挤在同一个模块、同一对源宿寄存器上。这不是"普遍偏紧"，是**一个点**。

### 根因

`fpd_settle_fit.v` 的 `S_RSS` 状态里干了三件事，在同一个时钟周期内：

1. 100 位减法树求残差平方和（33 级 CARRY4）
2. 与当前最优值比较 `<`
3. 比较结果驱动 `best_rss` / `best_k` / `best_A` / `best_V` 的写使能

减法树的 33 级进位链和比较器串在一起，时钟就没法收敛。

### 修法

把比较挪到下一拍。减法树和饱和留在 `S_RSS`，结果先存进 `rss_sat_r`：

```verilog
S_RSS: begin
    rss_sat_r <= rss_sat;      // 100 位减法树 + 饱和
    sst       <= S_CMP;
end
S_CMP: begin
    if (!best_valid || rss_sat_r < best_rss) begin
        best_valid <= 1'b1;
        best_k <= sk; best_A <= A; best_V <= V;
        best_rss <= rss_sat_r;  // 比较结果单独一拍
    end
    sst <= S_NEXT;
end
```

代价是一拍延迟，换来 WNS +1.337 → +2.767 ns。

### 留下的规则

- **先看 40 条最差路径是不是集中在同一对源宿**。如果是，缺的是流水级；如果散在几十个地方，缺的是整体架构调整。这两种情况的处理方式完全不同。
- 状态机的拆分粒度是按**组合逻辑深度**走的，不是按功能走的。一段功能上连贯、但组合链穿过 33 级进位的代码，就该拆。

---

## 三、解析器只通过自己的测试用例，等于没测

### 背景

新写 `pynq_build_report`，用它解析 Vivado 报告。写了一组合成夹具，全过。

### 真实报告打脸两次

**第一次**：把真实 `utilization.rpt` 喂进去，`RAMB36/FIFO` 读不出来。原因是 Vivado 给这个标签加了脚注星号——`RAMB36/FIFO*`——而我的正则字符类里没有 `*`，整行根本没匹配上。

**第二次**：`timing_summary.rpt` 的 Clock Summary 解析出 0 个时钟。原因是我用 `startswith('Clock Summary')` 找段头，但 Vivado 实际写的是 `| Clock Summary`（带表格竖线前缀）。

两次都是合成夹具覆盖不到的，因为**夹具是我按源码的假设写的**。

### 留下的规则

- 解析器必须拿**真实产物**做测试，而且真实产物要随包提交，让下一个人能重跑。
- `pynq_build_report/examples/` 下放的正是本项目的真实报告，测试直接断言 BRAM 104→55。这些数字不来自夹具，来自 Vivado。
- 换成别的工具、别的版本，先拿一份真实报告跑一遍再改代码。

同一条规则在 [golden-reference-verification](../agent_skills/golden-reference-verification/SKILL.md) 里写作"黄金参考必须独立推导，不能用被测算法生成期望"。

---

## 这三个例子共同指向什么

三次失败都不是"知识不够"，是**证据层级搞错了**：

| 例 | 我当时的证据层级 | 真实的层级 |
|---|---|---|
| 一 | HYPOTHESIS（推断"没人用"） | BUILD（综合报错）+ 源码链路（0x020 → Python） |
| 二 | 无（凭感觉找瓶颈） | BUILD（>`report_timing` 的实际路径） |
| 三 | OFFLINE_TEST（自己写的夹具） | 真实产物（Vivado 导出的报告原文） |

证据分级（`RAW_OBSERVATION` / `OFFLINE_TEST` / `RTL_SIM` / `BUILD` / `BOARD` / `HYPOTHESIS`）见 [cases.md](cases.md)。**未执行不可写通过；推断不可当已确认。**

---

## 边界

- 三个例子的数字都来自**这一块板、这一个工程、Vivado 2026.1**。换器件换版本，根因和量级都要重新测。
- 例一的消费者链行号对应当前源码快照，改动后行号会漂移，但追查方法不变。
- 这些是方法的复盘，不是"照做就成功"的保证。有用的部分是**怎么判断**，不是具体数值。
