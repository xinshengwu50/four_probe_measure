# PS-PL 寄存器映射（`ALL_Final` · PL `0x414C5835`）

> 本包串口主线覆盖说明：寄存器地址/位域与33 同版，但本地motion_all_lock包含reset_latched和watchdog_tripped。因此SYSTEM_RESET后HOME也被锁定，不允许源版的自动撤回；人工CLEAR后才可Z/RHOME。旧文中“RESET后HOME可执行”仅描述源版，不适用于本交付。机械生成表由build/scripts/gen_register_map.py依据本包RTL生成，手写安全语义以本说明及system_reset_interface.md为准。

本文件是**当前部署设计**的寄存器基线：`all_design.bd` 中的用户 IP
`xilinx.com:user:ALL_Final:1.0`，源文件 `hw/rtl/all/all_final.v`
（综合时由 `ip_repo/all_final/src/all_final.v` 提供，两者必须一致）。
外设基地址由 Vivado Address Editor 分配；AXI 数据宽度 32 bit；AXI 时钟与 ADC
采样时钟共用，若将来分离必须增加显式 CDC 处理。

## ⚠️ 历史说明：`0x00`–`0x1C` 曾经属于另一个外设（M2）

在 **M2 里程碑**里，`0x00`–`0x1C` 属于 `ads8681_axi_lite`（`hw/rtl/adc/`，
`VERSION = 0x0002_0000`），寄存器为
`CONTROL / STATUS / ERROR_CODE / VERSION / TX_DATA / RX_DATA / SAMPLE_COUNT / TIMEOUT_COUNT`。
`ALL_Final` 接管**同一段地址**并全部重新定义（`0x08` 变成 `INPUTS`、`0x10` 变成
`VERSION`、`0x20` 以上不再是"未实现"……）。

- M2 的模块与测试台**仍然保留**，作为模块级回归：
  `hw/rtl/adc/{ads8681_spi_master,adc_sample_ctrl,ads8681_axi_lite}.sv`、
  `hw/tb/tb_ads8681_*.sv`、`hw/tb/tb_adc_sample_ctrl*.sv`、`scripts/run_m2_*.ps1`、
  `scripts/check_m2_axi_synth.tcl`。
- 但 M2 **不在部署设计中**：`all_design.bd` 里没有任何 `ads8681` 实例。
- 本文件曾停在 M2 时期不再更新，长期与 RTL 冲突（这正是它被重写的原因）。
  **写 PS 代码请只按本文件的当前映射，不要参考 M2 的旧映射。**

## 与 RTL 保持同步的方式

```text
py -3 build/scripts/gen_register_map.py           # 重新生成下面的"自动生成块"
py -3 build/scripts/gen_register_map.py --check    # 只校验；不一致时退出码 1
```

下面的自动生成块完全由 `hw/rtl/all/all_final.v` 派生：寄存器地址取自 localparam 表，
访问方向取自该地址是否出现在 AXI 写译码 / 读译码的 case 项，
CONTROL/STATUS 位取自两个译码块的赋值，错误码取自 localparam，
"PS 常量"列取自 `sw/four_probe_sw/*.py` 的 `REG_* = 0x..`。

> **不要手工编辑标记之间的内容** —— 下一次生成会覆盖，`--check` 也会报警。

## 自动生成的寄存器定义

<!-- BEGIN GENERATED: 寄存器映射（由 scripts/gen_register_map.py 从 hw/rtl/all/all_final.v 生成，请勿手工编辑；79 个寄存器）-->

> Counting rule: this generated block contains 79 unique AXI_REG addresses; manual tables elsewhere may repeat the same address under alias names.

### 寄存器总表

| 偏移 | RTL 名称 | 访问 | PS 常量（模块） |
|---:|---|---|---|
| `0x000` | `AXI_REG_CONTROL` | R/W | REG_CONTROL / REG_ID (analog_frontend.py, final_four_probe_system.py, pl_autorange.py, system_reset.py) |
| `0x004` | `AXI_REG_STATUS` | R | REG_STATUS / REG_VERSION (final_four_probe_system.py, pl_autorange.py, system_reset.py) |
| `0x008` | `AXI_REG_INPUTS` | R | REG_CAPS (pl_autorange.py) |
| `0x00C` | `AXI_REG_OUTPUTS` | R | REG_STATUS (pl_autorange.py) |
| `0x010` | `AXI_REG_VERSION` | R | REG_CONTROL / REG_VERSION (analog_frontend_hw_test.py, final_four_probe_system.py, pl_autorange.py) |
| `0x014` | `AXI_REG_MEAS_CNT` | R | REG_REASON (pl_autorange.py) |
| `0x018` | `AXI_REG_MAIN_STATE` | R | REG_SAMPLE_COUNT (pl_autorange.py) |
| `0x01C` | `AXI_REG_ADC_RAW` | R | REG_FRAME_DIAG (pl_autorange.py) |
| `0x020` | `AXI_REG_RHO` | R | REG_SAMPLE_RATE (pl_autorange.py) |
| `0x024` | `AXI_REG_RS` | R | REG_MISMATCH (pl_autorange.py) |
| `0x028` | `AXI_REG_R_CONTROL` | R/W | REG_LAST_SAMPLE / REG_R_CONTROL (final_four_probe_system.py, pl_autorange.py) |
| `0x02C` | `AXI_REG_R_COMMAND` | R/W | REG_ALLF_BASE / REG_R_COMMAND (final_four_probe_system.py, pl_autorange.py) |
| `0x030` | `AXI_REG_R_TARGET` | R/W | REG_AXI_DIAG / REG_R_TARGET (final_four_probe_system.py, pl_autorange.py) |
| `0x034` | `AXI_REG_R_STATUS` | R | REG_R_STATUS (final_four_probe_system.py) |
| `0x038` | `AXI_REG_R_POSITION` | R | REG_R_POSITION (final_four_probe_system.py) |
| `0x03C` | `AXI_REG_R_ERROR` | R | REG_R_ERROR (final_four_probe_system.py) |
| `0x040` | `AXI_REG_Z_CONTROL` | R/W | REG_Z_CONTROL (final_four_probe_system.py) |
| `0x044` | `AXI_REG_Z_COMMAND` | R/W | REG_Z_COMMAND (final_four_probe_system.py) |
| `0x048` | `AXI_REG_Z_TARGET` | R/W | REG_Z_TARGET (final_four_probe_system.py) |
| `0x04C` | `AXI_REG_Z_STATUS` | R | REG_Z_STATUS (final_four_probe_system.py) |
| `0x050` | `AXI_REG_Z_POSITION` | R | REG_Z_POSITION (final_four_probe_system.py) |
| `0x054` | `AXI_REG_Z_ERROR` | R | REG_Z_ERROR (final_four_probe_system.py) |
| `0x058` | `AXI_REG_M_CONTROL` | R/W | REG_MEAS_CONTROL (final_four_probe_system.py) |
| `0x05C` | `AXI_REG_M_STATUS` | R | REG_MEAS_STATUS (final_four_probe_system.py) |
| `0x060` | `AXI_REG_M_POINT` | R/W | REG_MEAS_POINT (final_four_probe_system.py) |
| `0x064` | `AXI_REG_M_HOLD` | R/W | REG_MEAS_HOLD (final_four_probe_system.py) |
| `0x068` | `AXI_REG_M_ERROR` | R | REG_MEAS_ERROR (final_four_probe_system.py) |
| `0x06C` | `AXI_REG_X_TARGET` | R/W | REG_X_TARGET (final_four_probe_system.py) |
| `0x070` | `AXI_REG_X_STATUS` | R | REG_X_STATUS (final_four_probe_system.py) |
| `0x074` | `AXI_REG_X_POSITION` | R | REG_X_POSITION (final_four_probe_system.py) |
| `0x078` | `AXI_REG_X_CONTROL` | R/W | REG_X_CONTROL (final_four_probe_system.py) |
| `0x07C` | `AXI_REG_Z_STEP_INTERVAL` | R/W | REG_Z_STEP_INTERVAL (final_four_probe_system.py) |
| `0x0A8` | `AXI_REG_Z_DECEL_CONTROL` | R/W | REG_Z_DECEL_CONTROL (final_four_probe_system.py) |
| `0x0AC` | `AXI_REG_Z_DECEL_WINDOW` | R/W | REG_Z_DECEL_WINDOW (final_four_probe_system.py) |
| `0x0B0` | `AXI_REG_Z_DECEL_SEG_STEPS` | R/W | REG_Z_DECEL_SEG_STEPS (final_four_probe_system.py) |
| `0x0B4` | `AXI_REG_Z_DECEL_LUT_INDEX` | R/W | REG_Z_DECEL_LUT_INDEX (final_four_probe_system.py) |
| `0x0B8` | `AXI_REG_Z_DECEL_LUT_DATA` | R/W | REG_Z_DECEL_LUT_DATA (final_four_probe_system.py) |
| `0x0D0` | `AXI_REG_ANALOG_CONTROL` | R/W | REG_ANALOG_CONTROL / REG_IR_BASE (analog_frontend.py, pl_autorange.py) |
| `0x0D4` | `AXI_REG_ANALOG_TEST_CONTROL` | R/W | REG_ANALOG_TEST_CONTROL (analog_frontend.py) |
| `0x0D8` | `AXI_REG_DAC_CODE` | R/W | REG_DAC_CODE (analog_frontend.py, analog_frontend_hw_test.py) |
| `0x0DC` | `AXI_REG_DAC_CONTROL` | R/W | REG_DAC_CONTROL (analog_frontend.py) |
| `0x0E0` | `AXI_REG_DAC_STATUS` | R | REG_DAC_STATUS (analog_frontend.py, analog_frontend_hw_test.py) |
| `0x0E4` | `AXI_REG_DAC_SEQ` | R | REG_DAC_SEQ (analog_frontend.py, analog_frontend_hw_test.py) |
| `0x0E8` | `AXI_REG_ANALOG_SEQ` | R | REG_ANALOG_SEQ (analog_frontend.py, analog_frontend_hw_test.py) |
| `0x0EC` | `AXI_REG_ADC_CFG_SEQ` | R | REG_ADC_CFG_SEQ (analog_frontend.py) |
| `0x0F0` | `AXI_REG_Z_HOME_STEPS` | R | REG_Z_HOME_STEPS (final_four_probe_system.py) |
| `0x0F4` | `AXI_REG_Z_TIMEOUT_CYCLES` | R | REG_Z_TIMEOUT_CYCLES (final_four_probe_system.py) |
| `0x0F8` | `AXI_REG_R_TIMEOUT_CYCLES` | R | REG_R_TIMEOUT_CYCLES (final_four_probe_system.py) |
| `0x0FC` | `AXI_REG_HEARTBEAT` | W | REG_HEARTBEAT (final_four_probe_system.py, system_reset.py) |
| `0x100` | `AXI_REG_STATS_SUM_LOW` | R | REG_STATS_SUM_LOW (pl_window_stats.py) |
| `0x104` | `AXI_REG_STATS_SUM_HIGH` | R | REG_STATS_SUM_HIGH (pl_window_stats.py) |
| `0x108` | `AXI_REG_STATS_VALID_COUNT` | R | REG_STATS_VALID_COUNT (pl_window_stats.py) |
| `0x10C` | `AXI_REG_STATS_SUM_SQ_LOW` | R | REG_STATS_SUM_SQ_LOW (pl_window_stats.py) |
| `0x110` | `AXI_REG_STATS_SUM_SQ_HIGH` | R | REG_STATS_SUM_SQ_HIGH (pl_window_stats.py) |
| `0x114` | `AXI_REG_STATS_RX_COUNT` | R | REG_STATS_RX_UPDATE_COUNT (pl_window_stats.py) |
| `0x118` | `AXI_REG_STATS_MIN_CODE` | R | REG_STATS_MIN_CODE (pl_window_stats.py) |
| `0x11C` | `AXI_REG_STATS_MAX_CODE` | R | REG_STATS_MAX_CODE (pl_window_stats.py) |
| `0x120` | `AXI_REG_STATS_SEQ` | R | REG_STATS_SEQ (pl_window_stats.py) |
| `0x124` | `AXI_REG_STATS_FLAGS` | R | REG_STATS_FLAGS (pl_window_stats.py) |
| `0x128` | `AXI_REG_STATS_BANK_SELECT` | R/W | REG_STATS_BANK_SELECT (pl_window_stats.py) |
| `0x12C` | `AXI_REG_STATS_CENTER_CODE` | R/W | REG_STATS_CENTER_CODE (pl_window_stats.py) |
| `0x130` | `AXI_REG_STATS_MAG_MIN` | R/W | REG_STATS_MAG_MIN (pl_window_stats.py) |
| `0x134` | `AXI_REG_STATS_MAG_MAX` | R/W | REG_STATS_MAG_MAX (pl_window_stats.py) |
| `0x138` | `AXI_REG_STATS_CONTROL` | R/W | REG_STATS_CONTROL (pl_window_stats.py) |
| `0x13C` | `AXI_REG_STATS_STATUS` | R | REG_STATS_STATUS (pl_window_stats.py) |
| `0x140` | `AXI_REG_WATCHDOG_COUNT` | R | REG_WATCHDOG_COUNT (final_four_probe_system.py) |
| `0x144` | `AXI_REG_STATS_ACK_SEQ` | R/W | REG_STATS_ACK_SEQ (pl_window_stats.py) |
| `0x148` | `AXI_REG_Z_SAFE_TRAVEL` | R/W | REG_Z_SAFE_TRAVEL (final_four_probe_system.py) |
| `0x14C` | `AXI_REG_CALC_CONTROL` | W | REG_CALC_CONTROL (pl_resistivity.py) |
| `0x150` | `AXI_REG_CALC_STATUS` | R | REG_CALC_STATUS (pl_resistivity.py) |
| `0x154` | `AXI_REG_CALC_RHO_LOW` | R | REG_CALC_RHO_LOW (pl_resistivity.py) |
| `0x158` | `AXI_REG_CALC_RHO_HIGH` | R | REG_CALC_RHO_HIGH (pl_resistivity.py) |
| `0x15C` | `AXI_REG_CALC_FLAGS` | R | REG_CALC_FLAGS (pl_resistivity.py) |
| `0x160` | `AXI_REG_CALC_COEFF_K` | R/W | REG_CALC_COEFF_K (pl_resistivity.py) |
| `0x164` | `AXI_REG_CALC_COEFF_RS` | R/W | REG_CALC_COEFF_RS (pl_resistivity.py) |
| `0x168` | `AXI_REG_CALC_RS_LOW` | R | REG_CALC_RS_LOW (pl_resistivity.py) |
| `0x16C` | `AXI_REG_CALC_RS_HIGH` | R | REG_CALC_RS_HIGH (pl_resistivity.py) |
| `0x170` | `AXI_REG_CALC_MIN_COUNT` | R/W | REG_CALC_MIN_COUNT (pl_resistivity.py) |
| `0x174` | `AXI_REG_CALC_MAX_SPAN` | R/W | REG_CALC_MAX_SPAN (pl_resistivity.py) |

> 访问方向由该地址是否出现在 AXI 写译码 / 读译码的 case 项推出；
> `PS 常量` 列由 `sw/four_probe_sw/*.py` 的 `REG_* = 0x..` 汇总，
> `—` 表示当前 PS 未直接引用（可能由其它模块或仅诊断用）。

### `0x00 CONTROL` 写位

| bit | 目标信号 |
|---:|---|
| 0 | `axi_start_pulse` |
| 1 | `axi_x_trig_pulse` |
| 2 | `axi_clear_error_pulse` |
| 3 | `axi_x_start_pulse` |
| 4 | `axi_adc_reinit_pulse` |
| 5 | `sys_reset_wr` |
| 6 | `clr_faults_wr` |
| 7 | `watchdog_disarm_wr` |

### `0x04 STATUS` 读位

| bit | 信号 |
|---:|---|
| 8 | `err_latch` |
| 9 | `cycle_done` |
| 10 | `x_busy` |
| 11 | `ena` |
| 12 | `step_pulse` |
| 13 | `x_pul_out` |
| 14 | `x_dir_out` |
| 15 | `dir` |
| 16 | `reset_latched` |
| 17 | `watchdog_tripped` |
| 18 | `watchdog_armed` |
| 19 | `motion_refused_sticky` |

### 轴错误码（RTL localparam）

| MEAS | 值 |
|---|---:|
| `MEAS_ERR_NONE` | 0 |
| `MEAS_ERR_BUSY` | 1 |
| `MEAS_ERR_CONFLICT` | 2 |
| `MEAS_ERR_TIMEOUT` | 3 |

<!-- END GENERATED -->






## 语义说明（手工维护）

### PL banked validity statistics (0x100–0x13C)

Bank index = `{reverse, range[1:0]}`; 0-3 = forward, 4-7 = reverse.  Each bank stores a magnitude window around a configurable center code.

| Offset | Name | Access | Meaning |
|---:|---|---|---|
| `0x100` | `STATS_SUM_LOW` | `R` | selected bank valid raw-code sum, low 32 bits |
| `0x104` | `STATS_SUM_HIGH` | `R` | selected bank valid raw-code sum, high 32 bits |
| `0x108` | `STATS_VALID_COUNT` | `R` | number of valid raw-code samples |
| `0x10C` | `STATS_SUM_SQ_LOW` | `R` | sum of squared codes, low 32 bits |
| `0x110` | `STATS_SUM_SQ_HIGH` | `R` | sum of squared codes, high 32 bits |
| `0x114` | `STATS_RX_COUNT` | `R` | all RX_REG updates during the window |
| `0x118` | `STATS_MIN_CODE` | `R` | minimum valid raw code |
| `0x11C` | `STATS_MAX_CODE` | `R` | maximum valid raw code |
| `0x120` | `STATS_SEQ` | `R` | bank snapshot sequence |
| `0x124` | `STATS_FLAGS` | `R` | bit0 ready, bit1 empty, bit2 overflow, bit3 busy |
| `0x128` | `STATS_BANK_SELECT` | `R/W` | selected bank 0..7 |
| `0x12C` | `STATS_CENTER_CODE` | `R/W` | magnitude-window center code for selected bank |
| `0x130` | `STATS_MAG_MIN` | `R/W` | minimum abs(code-center) for selected bank |
| `0x134` | `STATS_MAG_MAX` | `R/W` | maximum abs(code-center) for selected bank |
| `0x138` | `STATS_CONTROL` | `W` | bit0 clear bank, bit1 arm, bit2 ack, bit3 disarm, bit4 clear all |
| `0x13C` | `STATS_STATUS` | `R` | enable/busy and selected/active bank status |

The accumulator counts only `RX_REG` updates, not 50 MHz clock cycles.  The default PL window is 20 ms (`STATS_WINDOW_CYCLES = 1,000,000`).

### ACK_SEQ and the fail-closed default window (PL 0x414C5835)

* `0x140` `WATCHDOG_COUNT` (`R`): watchdog counter in 50 MHz cycles (20 ns each).
  It is zeroed by every heartbeat, counts up while armed and trips at
  `50_000_000` (1 s).  Use it to see whether the PS really is feeding the
  watchdog: `(50_000_000 - value) * 20 ns` is the time left before a trip.
* `0x144` `STATS_ACK_SEQ` (`W`, write-only): the `STATS_SEQ` value the following
  `STATS_CONTROL.ACK` acknowledges.  The ACK then clears `READY` only when the
  bank's `STATS_SEQ` still equals that value.  Without this a late ACK silently
  cleared the READY flag of a *newer* window, and that snapshot was lost.
  An ACK without writing `0x144` first is still accepted (it clears
  unconditionally) so older PS code keeps working.
* Power-on `STATS_MAG_MIN = 0x10000` and `STATS_MAG_MAX = 0`: an unconfigured
  bank can never satisfy `mag_min <= |code - center| <= mag_max`, so it reports
  `valid_count = 0` / `empty = 1` instead of silently accepting every sample
  (fail-closed).  Software must configure the window before arming.
* `STATUS[18]` (`watchdog_armed`) is the read-only armed flag; `STATUS[16]` and
  `STATUS[17]` remain the reset and watchdog-trip latches.
* `CONTROL[7]` = `WATCHDOG_DISARM`: zeroes the watchdog counter and the armed
  flag **without** touching `reset_latched` / `watchdog_tripped`.
* `0x148` `Z_SAFE_TRAVEL` (`R/W`): lateral-motion height gate.  R and X are
  refused while `z_homed == 0` or `z_position > Z_SAFE_TRAVEL`; the R refusal
  records `R_ERR_NOT_CLEAR = 10` and the X refusal is silent.  Power-on default
  is 0 (fail-closed), so software must program it (the clear height,
  `full_down - half_up`) before any lateral motion.  `Z_CMD_HOME` and
  `Z_CMD_RETURN_HOME_SAFE` are exempt from the conflict check and always allowed.
* `STATUS[19]` = `motion refused`: sticky, set when any axis refuses a motion
  command (self busy / fault / motion lock / conflict / probe not clear), cleared
  only by `CLEAR_FAULTS`.  It makes the otherwise silent X refusal visible.

### Refusal precedence and what each code means (PL 0x414C5835)

The two axes evaluate their gates in a different order, and only one of the codes
latches a fault.  Do not assume a single global priority:

| Order | R axis | Z axis | Latches a fault? | PS notices via |
|---:|---|---|---|---|
| 1 | `r_busy` -> 1 `R_ERR_BUSY` | `z_direct_busy` -> 1 `Z_ERR_BUSY` | no (code only) | axis timeout |
| 2 | `r_fault` -> 1 | `z_fault` -> 1 | - | fault bit |
| 3 | **`!z_probe_clear` -> 10 `R_ERR_NOT_CLEAR`** | `motion_all_lock` -> 9 | no (code only) | axis timeout |
| 4 | conflict -> 8 | `motion_move_lock && move` -> 9 | no for 8 / **yes for 9** | timeout / fault |
| 5 | `motion_all_lock` -> 9 | **conflict -> 8** (retract commands skipped) | yes for 9 / no for 8 | fault / timeout |
| 6 | `motion_move_lock && move` -> 9 | command decoder | yes | fault |

Consequences worth remembering:

* On the R axis the height gate (10) is evaluated **before** the conflict (8) and
  **before** the motion locks (9), so "watchdog tripped AND probe not clear" reports
  10, not 9.  The latches must therefore be read from `STATUS[16]`/`STATUS[17]`
  (and `STATUS[19]` for the refusal flag), never inferred from the error code.
* 10 (`NOT_CLEAR`) and 8 (`CONFLICT`) drop the command and record a code without
  latching a fault, so the PS only notices through an axis timeout; 9
  (`MOTION_LOCKED`) additionally sets the axis fault and is reported immediately.
* **Rule: error codes are for diagnosis only, never for control flow.**  All
  decisions (abort, safe shutdown, retry, refusal detection) read status bits
  (`STATUS[16..19]` and the per-axis fault bits), so reordering the gates cannot
  change the software behaviour.


Important coordinate note: under the current `direct_adc_measurement` mapping,
`code_to_adc_voltage_v()` returns `(code - 0x8000) * 5.12 / 32768`, while the
probe zero is reached at `ADC_IN = 2.5 V`, so the zero-probe code is
`0xBE80` (48768), not `0x8000`.  The PS writes `center_code =
probe_voltage_to_code(offset_v)` for each bank.

Pilot range selection is non-strict: a low-count snapshot becomes an
ineligible candidate so the sweep can continue to the next range.  Fixed-range
bidirectional measurement is strict: a count below `pl_stats_min_valid_samples`
causes retry/failure instead of silently using a weak result.
