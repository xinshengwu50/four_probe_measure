---
name: pynq-build-report
description: Parse saved Vivado utilization/timing/DRC reports into a provenance-carrying record and emit a before/after comparison table for an optimization report; refuses comparisons across devices or between synthesized and routed runs. Use when writing up a resource or timing optimization.
---

# 构建报告采集与优化前后对比

优化章节最难的部分不是跑出数字，而是让读者相信两个数字可以放在一起比。手工抄表会丢掉器件、工具版本和报告来源，也没人拦得住把 xc7z020 的 74% 和 xc7z010 的 48% 写成"利用率下降"。本工具把溯源绑在每个数字上，并拒绝没有意义的对比。

全部为标准库，读已保存的 `.rpt` 文本，不启动 Vivado、不接触硬件。

## 用法

```bash
# 1. 各自采集一轮（Vivado 跑完，报告已存盘）
python -B scripts/build_report.py collect \
    --utilization before/utilization.rpt \
    --timing before/timing_summary.rpt \
    --drc before/drc.rpt \
    --label "基线 2026-10-29" --output before.json

python -B scripts/build_report.py collect \
    --utilization after/utilization.rpt \
    --timing after/timing_summary.rpt \
    --drc after/drc.rpt \
    --label "V4 2026-10-30" --output after.json

# 2. 对比，直接产出报告可用的表格
python -B scripts/build_report.py compare before.json after.json \
    --markdown comparison.md --json comparison.json \
    --title "优化前后对比"
```

作为库使用：

```python
from build_report import collect, compare, render_markdown
before = collect('before/utilization.rpt', 'before/timing_summary.rpt', 'before/drc.rpt', '基线')
after  = collect('after/utilization.rpt',  'after/timing_summary.rpt',  'after/drc.rpt',  'V4')
print(render_markdown(compare(before, after)))
```

报告所需的 Vivado 命令（本工具只读产物）：

```tcl
report_utilization      -file utilization.rpt
report_timing_summary   -file timing_summary.rpt
report_drc              -file drc.rpt
```

## 采集到的指标

| 键 | 名称 | 单位 | 好方向 |
|---|---|---|---|
| `lut` / `lut_logic` / `lut_memory` | Slice LUTs / Logic / Memory | 个 | 越低越好 |
| `ff` | Slice Registers | 个 | 越低越好 |
| `bram` / `ramb36` / `ramb18` | Block RAM Tile / RAMB36 / RAMB18 | 个 | 越低越好 |
| `dsp` | DSPs | 个 | 越低越好 |
| `io` | Bonded IOB | 个 | 越低越好 |
| `wns` / `whs` | 建立/保持最差余量 | ns | 越高越好 |
| `failing` | 失败端点 | 个 | 越低越好 |

"好方向"是度量本身的属性（余量越大越好、占用越少越好），不是对设计的评价。时序变好而资源变差时，表里会同时出现"改善"和"变差"，由作者决定这个交换值不值。

## 三条硬性拒绝

工具会在这些情况下停下来，而不是给出一个看起来能用的表：

1. **器件不同** → 抛 `ValueError`。占用率和余量都是器件的属性，跨器件比"少用 47% BRAM"没有意义。
2. **实现状态不同**（`Routed` vs `Synthesized`）→ 警告。综合后时序不是布完线的时序，两者不能并排。
3. **设计名不同** → 警告。改名或换顶层是合法的，所以只提醒不拦。

另外，任何在两轮中**没有同时测得**的指标会保持 `n/a` 并列进"未在两轮中同时测得"一行，**绝不以 0 填充**。缺一个数就是缺一个数。

## 失效条件

- 只认 Vivado 的 ASCII 报告格式。ISE、Quartus、Vitis HLS 的报告字段不同，需要另写解析。
- `report_utilization` 的层级模式（`-hierarchical`）另有一张按模块的表，本工具只取顶层汇总表；要按模块比较得自己扩展。
- 时序只读 Design Timing Summary 一段。按路径组、按跨时钟域的分解在 `report_timing -max_paths` 的输出里，本工具不解析。
- DRC 只统计规则条数与错误数，不判断这些 warning 在设计上是否可以忽略。

## 适用范围

与题目无关：任何 Vivado 工程、任何器件、任何板卡都可以用，只要交付里有这三份报告。换工程只需要换文件路径。

## 验证范围

`tests/test_build_report.py` 共 28 项，全部离线：

- 解析：真实报告里的 `<NA>`、单位数、星号脚注（`RAMB36/FIFO*`）、个位数计数后紧跟的空列，都要读对。
- 溯源：器件/工具/实现状态从报告头部取出并随数字一起保存。
- 护栏：跨器件必须抛异常；综合 vs 布线必须警告；未测指标必须为 `n/a` 且不得被当成 0；基线为 0 时不得除零。
- 真实数据：`examples/` 下是本项目基线与优化后的**实际报告原文**，测试直接解析它们并断言 BRAM 从 104 降到 55（−47.1%）。只通过合成夹具不算数。

未验证：跨 Vivado 大版本的格式变化（只测过 2026.1）、层级报告的按模块解析、与真实工程之外的报告。

## 来源

本工具是在写本项目第 4 章"优化过程"时发现缺一环而补的：指南 §3.3.5.2 点名要求"性能与资源数据自动采集并生成报告的工具"，而原包里只有 `pynq_toolkit.parse_vivado` 能抠出几个数，没有对比、没有溯源、没有护栏。真实使用中先踩到 `RAMB36/FIFO*` 的星号和 `<NA>` 的空值处理，才写成现在这样。
