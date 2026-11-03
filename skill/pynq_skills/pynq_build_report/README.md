# 构建报告采集与优化前后对比

把 Vivado 的 `utilization.rpt` / `timing_summary.rpt` / `drc.rpt` 读成带溯源的记录，再生成优化报告要的对比表。

## 解决什么问题

写优化章节时，数字通常靠手抄。手抄有三处会出事：

1. **数字失去出处**。报告里写"BRAM 从 104 降到 55"，但没说哪个器件、哪个工具版本、哪次构建。读者无法核对。
2. **比较了不可比的东西**。把 xc7z020 的数字和 xc7z010 的数字，或者综合后的时序和布线后的时序，放在同一张表里。
3. **缺失变零**。某个指标这一轮没测到，表格里就悄悄少一行，或者填个 0 让它看起来是测过的。

本工具对应地做三件事：溯源随数字保存、不可比就拒绝、缺失一律 `n/a`。

## 快速开始

```bash
python -B scripts/build_report.py collect \
    --utilization before/utilization.rpt --timing before/timing_summary.rpt \
    --drc before/drc.rpt --label "基线" --output before.json

python -B scripts/build_report.py collect \
    --utilization after/utilization.rpt --timing after/timing_summary.rpt \
    --drc after/drc.rpt --label "优化后" --output after.json

python -B scripts/build_report.py compare before.json after.json \
    --markdown comparison.md --title "优化前后对比"
```

输出的 `comparison.md` 可以直接贴进设计报告：

```markdown
## 优化前后对比

- 前：`基线`
- 后：`优化后`
- 器件：`xc7z020clg400-1`（两轮相同）
- 工具版本：`Vivado v.2026.1 (win64) Build 6511674`（两轮相同）
- 实现状态：`Routed`（两轮相同）
- 报告时间：`Thu Oct 29 17:25:25 2026` → `Fri Oct 30 19:47:35 2026`

| 指标 | 基线 | 优化后 | 变化 | 判定 |
|---|---:|---:|---:|---|
| Slice LUTs | 25,157 | 24,976 | -181 (-0.7%) | 改善 |
| Slice Registers | 24,968 | 24,930 | -38 (-0.2%) | 改善 |
| Block RAM Tile | 104 | 55 | -49 (-47.1%) | 改善 |
| DSPs | 39 | 39 | +0 (+0.0%) | 持平 |
| WNS | +1.337 | +2.767 | +1.430 (+107.0%) | 改善 |
| WHS | +0.015 | +0.029 | +0.014 (+93.3%) | 改善 |
```

上面这段是 `examples/` 里两份**真实报告**跑出来的，不是编的示例。

## 报告从哪来

本工具只读，不启动 Vivado。先在 Vivado 里导出：

```tcl
report_utilization    -file utilization.rpt
report_timing_summary -file timing_summary.rpt
report_drc            -file drc.rpt
```

`report_utilization` 请用默认（顶层汇总）模式。加了 `-hierarchical` 是另一张按模块的表，本工具不解析。

## 设计的取舍

**为什么用 `|` 分列而不是固定字符偏移。** Vivado 的 ASCII 表靠空格对齐。数据从 6 位变成 5 位（比如 BRAM 104→55）时，后面每一列都会左移一格。按偏移切的解析器会读到错的列，而且只在大改动之后才暴露——正好是最需要数字可信的时候。按 `|` 切不受这个影响。

**为什么 `<NA>` 是 `None` 不是 0。** Vivado 在数值不适用时写 `<NA>`。转成 0 会凭空造出一个"测到 0"的结果，读者无从分辨。见 `tests/test_build_report.py` 的 `test_absent_value_is_none_not_zero`。

**为什么跨器件要抛异常而不是警告。** 占用率和时序余量是器件的物理属性。跨器件对比得到的百分比没有物理解释，任何读者都无法用它下判断。与其给一句没人会认真看的警告，不如让流程停下来。

**为什么综合 vs 布线只警告。** 有时候手头只有综合报告，作者仍然想先看个数。拦死会挡住合法用法，但必须让人知道这两个数不能并排。

## 失效条件

- 只认 Vivado ASCII 报告。Quartus / ISE / Vitis HLS 格式不同。
- 层级模式（`-hierarchical`）的按模块表不解析。
- 时序只读 Design Timing Summary；`report_timing -max_paths` 的逐路径分解不解析。
- DRC 只统计条数与错误数，不判断 warning 能否忽略。
- 只测过 Vivado 2026.1。大版本升级后表头或列序变化需要重新验证。

## 验证

```bash
python -B -m unittest discover -s tests -v     # 28 项
```

覆盖解析、溯源、三条护栏、缺失值处理、除零，以及直接解析 `examples/` 下的真实报告并断言 BRAM 104→55。全部离线，不需要 Vivado。

## 与本项目的关系

本项目在 `report/improve/` 里记录 V4 优化（BRAM 104→55，WNS +1.337→+2.767 ns）。这份技能包里的对比表就是同一套逻辑产出的，但工具本身不认识四探针：换任何 Vivado 工程、任何器件，只要有三份报告就能用。
