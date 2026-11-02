// PS session guard, extracted verbatim from ALL_Final: the system-reset latch, the
// PS heartbeat watchdog and the sticky "a motion command was refused" status bit.
//
// Why it is one module: all three answer the same question - "is the PS still in
// control of this scan?".  The watchdog cuts the excitation current on heartbeat
// expiry (it never moves an axis), the reset latch records that the panel asked for
// a stop, and the sticky bit keeps the cause of the last refusal visible until
// CLEAR_FAULTS.
//
// Ownership follows hw/rtl/README.md:
//   * rule 1 (who writes, keeps): the AXI register file keeps the write strobes
//     (sys_reset_wr / clr_faults_wr / heartbeat_wr / watchdog_disarm_wr) and hands
//     them in; the latches and the counter live here and are read back out.
//   * rule 2 (TB-overridden parameters stay on top): WATCHDOG_CYCLES stays declared
//     in ALL_Final (tb_all_final_reset_watchdog.sv reads dut.WATCHDOG_CYCLES) and is
//     forwarded here; the name is unchanged so the moved body needs no edit.
//   * rule 3 (interlocks are inputs): the three "this command was refused" pulses
//     arrive as inputs; the module never instantiates a peer.
//
// NOTE: the 4-line "motion inhibit tracker" (motion_latch_d) deliberately stays in
// ALL_Final: it derives motion_stop_pulse, which is motion POLICY, and rule 3 keeps
// policy on top.  For the same reason motion_all_lock / motion_move_lock / z_probe_clear
// stay there too.
module session_guard #(
    parameter [31:0] WATCHDOG_CYCLES = 32'd50_000_000
) (
    input  wire        clk,
    input  wire        reset_n,
    // AXI write strobes.
    input  wire        sys_reset_wr,
    input  wire        clr_faults_wr,
    input  wire        heartbeat_wr,
    input  wire        watchdog_disarm_wr,
    // Refusal pulses feeding the sticky status bit.
    input  wire        z_refused_now,
    input  wire        r_refused_now,
    input  wire        x_refused_now,
    // Latches, heartbeat counter and sticky status, all read back by the AXI file.
    output reg         reset_latched,
    output reg         watchdog_tripped,
    output reg         watchdog_armed,
    output reg  [31:0] watchdog_cnt,
    output reg         motion_refused_sticky
);

  // ---- system reset latch + PS heartbeat watchdog (2026-10-09) ----------------
  // CONTROL bit5 requests a system reset, bit6 clears the latches.
  // REG_HEARTBEAT 0xFC must be written at least once per second; on expiry only the
  // excitation current is cut, no axis is moved.
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          reset_latched <= 1'b0; watchdog_tripped <= 1'b0;
          watchdog_cnt <= 32'd0; watchdog_armed <= 1'b0;
      end else if (watchdog_disarm_wr) begin
          // Disarm the watchdog WITHOUT touching the fault latches.  This is the
          // race-free "stop feeding me" command: a SYSTEM_RESET latched at the
          // same moment stays visible instead of being cleared by accident.
          watchdog_cnt <= 32'd0; watchdog_armed <= 1'b0;
      end else if (clr_faults_wr) begin
          reset_latched <= 1'b0; watchdog_tripped <= 1'b0;
          watchdog_cnt <= 32'd0; watchdog_armed <= 1'b0;
      end else begin
          if (sys_reset_wr) reset_latched <= 1'b1;
          if (heartbeat_wr) begin
              watchdog_cnt <= 32'd0; watchdog_armed <= 1'b1;
          end else if (watchdog_armed && !watchdog_tripped) begin
              if (watchdog_cnt >= WATCHDOG_CYCLES) begin
                  watchdog_tripped <= 1'b1; watchdog_armed <= 1'b0;
              end else begin
                  watchdog_cnt <= watchdog_cnt + 32'd1;
              end
          end
      end
  end

  // ---- sticky "a motion command was refused" flag (STATUS[19]) ----------------
  // A refused motion command sets STATUS[19]; only CLEAR_FAULTS clears it (CONTROL
  // bit2 must not, because prepare_z_power_up() uses it on every scan and would
  // erase the previous cause).
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n)                 motion_refused_sticky <= 1'b0;
      else if (clr_faults_wr)       motion_refused_sticky <= 1'b0;
      else if (z_refused_now || r_refused_now || x_refused_now)
                                    motion_refused_sticky <= 1'b1;
  end

endmodule
