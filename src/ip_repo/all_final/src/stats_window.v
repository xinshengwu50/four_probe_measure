// Banked 20 ms validity-window statistics, extracted from ALL_Final.
// Binning of the ADC sample magnitude against a per-bank window, SUM / SUMSQ / MIN /
// MAX / RX counters, the SEQ-ACK protocol and the eight per-bank snapshots.
//
// Ownership follows hw/rtl/README.md:
//   * rule 1 (who writes, keeps): the AXI register file keeps the write strobes and
//     the three configuration arrays (stats_center_code / stats_mag_min / stats_mag_max
//     are written by the AXI write block).  The ACK_SEQ comment in ALL_Final already
//     said this before the rules were written down: "stats_ack_seq_value /
//     stats_ack_seq_set are driven by the AXI write block; stats_ack_seq_pending is
//     driven by the statistics block.  Keeping one driver per register avoids a
//     multiply-driven net."
//   * rule 2 (TB-overridden parameters stay on top): STATS_WINDOW_CYCLES is overridden
//     by tb_all_final_stats_bank and tb_all_final_equiv, so ALL_Final keeps it and
//     forwards the value.  STATS_COUNT_BITS is derived here from it so the two cannot
//     drift apart.
//   * rule 4 (arrays): the three arrays this block READS stay in the parent and arrive
//     as flattened read-only copies (entry k = bits [k*17 +: 17]).  The ten snapshot
//     arrays this block WRITES stay inside it and only the slice selected by the
//     readback index (stats_bank_select) is exported -- the top level observes exactly
//     one bank at a time, so exporting the whole arrays would cost 8x the wiring.
module stats_window #(
    parameter STATS_WINDOW_CYCLES = 1000000
) (
    input  wire         clk,
    input  wire         reset_n,
    // Sample stream, from the extracted ADC capture instance.
    input  wire [31:0]  RX_REG,
    input  wire         rx_reg_update_pulse,
    // Which bank the analog front end is on (AXI-written configuration).
    input  wire         analog_polarity_reg,
    input  wire [1:0]   analog_range_sel_reg,
    // AXI write strobes and the ACK_SEQ protocol.
    input  wire         axi_stats_clear_pulse,
    input  wire         axi_stats_arm_pulse,
    input  wire         axi_stats_disarm_pulse,
    input  wire         axi_stats_ack_pulse,
    input  wire         axi_stats_clear_all_pulse,
    input  wire         stats_ack_seq_set,
    input  wire [31:0]  stats_ack_seq_value,
    // Readback index: the parent reads one bank per access.
    input  wire [2:0]   stats_bank_select,
    // Read-only flattened copies of the three AXI-written window arrays.
    input  wire [135:0] stats_center_code_flat,
    input  wire [135:0] stats_mag_min_flat,
    input  wire [135:0] stats_mag_max_flat,
    // What the parent reads back.
    output reg  [2:0]   stats_active_bank,
    output reg          stats_window_enable,
    output reg          stats_window_busy,
    output reg          stats_ack_seq_pending,
    output wire [63:0]  stats_sum_snapshot_sel,
    output wire [63:0]  stats_sum_sq_snapshot_sel,
    output wire [31:0]  stats_valid_count_snapshot_sel,
    output wire [31:0]  stats_rx_count_snapshot_sel,
    output wire [16:0]  stats_min_snapshot_sel,
    output wire [16:0]  stats_max_snapshot_sel,
    output wire [31:0]  stats_seq_sel,
    output wire         stats_ready_sel,
    output wire         stats_empty_sel,
    output wire         stats_overflow_sel
);

  // Derived here (not forwarded) so it can never disagree with the window length.
  localparam integer STATS_COUNT_BITS = (STATS_WINDOW_CYCLES <= 1) ? 1 : $clog2(STATS_WINDOW_CYCLES);

  // ---- state that never leaves the module -------------------------------------
  reg [63:0] stats_sum_live;
  reg [63:0] stats_sum_sq_live;
  reg [31:0] stats_valid_count_live;
  reg [31:0] stats_rx_count_live;
  reg [16:0] stats_min_live;
  reg [16:0] stats_max_live;
  reg [STATS_COUNT_BITS-1:0] stats_cycle_count;
  integer    stats_bank_i;
  reg [63:0] stats_sum_snapshot[0:7];
  reg [63:0] stats_sum_sq_snapshot[0:7];
  reg [31:0] stats_valid_count_snapshot[0:7];
  reg [31:0] stats_rx_count_snapshot[0:7];
  reg [16:0] stats_min_snapshot[0:7];
  reg [16:0] stats_max_snapshot[0:7];
  reg [31:0] stats_seq[0:7];
  reg        stats_ready[0:7];
  reg        stats_empty[0:7];
  reg        stats_overflow[0:7];

  // ---- the slice the parent reads back ----------------------------------------
  assign stats_sum_snapshot_sel        = stats_sum_snapshot[stats_bank_select];
  assign stats_sum_sq_snapshot_sel     = stats_sum_sq_snapshot[stats_bank_select];
  assign stats_valid_count_snapshot_sel= stats_valid_count_snapshot[stats_bank_select];
  assign stats_rx_count_snapshot_sel   = stats_rx_count_snapshot[stats_bank_select];
  assign stats_min_snapshot_sel        = stats_min_snapshot[stats_bank_select];
  assign stats_max_snapshot_sel        = stats_max_snapshot[stats_bank_select];
  assign stats_seq_sel                 = stats_seq[stats_bank_select];
  assign stats_ready_sel               = stats_ready[stats_bank_select];
  assign stats_empty_sel               = stats_empty[stats_bank_select];
  assign stats_overflow_sel            = stats_overflow[stats_bank_select];

  wire [16:0] stats_code = {1'b0, RX_REG[31:16]};
  wire [2:0]  stats_analog_bank = {analog_polarity_reg, analog_range_sel_reg};
  wire [16:0] stats_center = stats_center_code_flat[stats_active_bank*17 +: 17];
  wire [16:0] stats_delta = (stats_code >= stats_center)
                          ? (stats_code - stats_center)
                          : (stats_center - stats_code);
  wire        stats_bank_matches = (stats_analog_bank == stats_active_bank);
  wire        stats_code_valid = stats_window_enable && stats_bank_matches &&
                                 (stats_delta >= stats_mag_min_flat[stats_active_bank*17 +: 17]) &&
                                 (stats_delta <= stats_mag_max_flat[stats_active_bank*17 +: 17]);
  wire        stats_add_valid = rx_reg_update_pulse && stats_code_valid;
  wire        stats_add_rx = rx_reg_update_pulse && stats_window_enable && stats_bank_matches;
  wire [64:0] stats_sum_next = {1'b0, stats_sum_live} +
                               (stats_add_valid ? {48'd0, stats_code} : 65'd0);
  // 17x17 product with an EXPLICIT 34-bit width.  Without the named wire the
  // self-determined width of (stats_code * stats_code) is only 17 bits, so the
  // product was truncated before being zero-extended - that is what produced
  // impossible "min != max but std == 0" snapshots on the board.
  wire [33:0] stats_code_sq = stats_code * stats_code;
  wire [64:0] stats_sum_sq_next = {1'b0, stats_sum_sq_live} +
                                  (stats_add_valid ?
                                   {31'd0, stats_code_sq} : 65'd0);
  wire [32:0] stats_count_next = {1'b0, stats_valid_count_live} +
                                 (stats_add_valid ? 33'd1 : 33'd0);
  wire [32:0] stats_rx_count_next = {1'b0, stats_rx_count_live} +
                                    (stats_add_rx ? 33'd1 : 33'd0);
  wire [16:0] stats_min_next = (!stats_add_valid || stats_code >= stats_min_live)
                             ? stats_min_live : stats_code;
  wire [16:0] stats_max_next = (!stats_add_valid || stats_code <= stats_max_live)
                             ? stats_max_live : stats_code;
  wire        stats_period_end = stats_window_enable &&
                                 (stats_cycle_count >= STATS_WINDOW_CYCLES - 1);
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          stats_active_bank <= 3'd0;
          stats_sum_live <= 64'd0;
          stats_sum_sq_live <= 64'd0;
          stats_valid_count_live <= 32'd0;
          stats_rx_count_live <= 32'd0;
          stats_min_live <= 17'h1FFFF;
          stats_max_live <= 17'd0;
          stats_cycle_count <= {STATS_COUNT_BITS{1'b0}};
          stats_window_enable <= 1'b0;
          stats_window_busy <= 1'b0;
          stats_ack_seq_pending <= 1'b0;
          for (stats_bank_i = 0; stats_bank_i < 8; stats_bank_i = stats_bank_i + 1) begin
              stats_sum_snapshot[stats_bank_i] <= 64'd0;
              stats_sum_sq_snapshot[stats_bank_i] <= 64'd0;
              stats_valid_count_snapshot[stats_bank_i] <= 32'd0;
              stats_rx_count_snapshot[stats_bank_i] <= 32'd0;
              stats_min_snapshot[stats_bank_i] <= 17'd0;
              stats_max_snapshot[stats_bank_i] <= 17'd0;
              stats_seq[stats_bank_i] <= 32'd0;
              stats_ready[stats_bank_i] <= 1'b0;
              stats_empty[stats_bank_i] <= 1'b1;
              stats_overflow[stats_bank_i] <= 1'b0;
          end
      end else begin
          // ACK_SEQ: latch the SEQ the PS wrote to 0x144; the ACK below
          // consumes it (this block is the only driver of the pending flag).
          if (stats_ack_seq_set) stats_ack_seq_pending <= 1'b1;
          if (axi_stats_clear_all_pulse) begin
              for (stats_bank_i = 0; stats_bank_i < 8; stats_bank_i = stats_bank_i + 1) begin
                  stats_sum_snapshot[stats_bank_i] <= 64'd0;
                  stats_sum_sq_snapshot[stats_bank_i] <= 64'd0;
                  stats_valid_count_snapshot[stats_bank_i] <= 32'd0;
                  stats_rx_count_snapshot[stats_bank_i] <= 32'd0;
                  stats_min_snapshot[stats_bank_i] <= 17'd0;
                  stats_max_snapshot[stats_bank_i] <= 17'd0;
                  stats_seq[stats_bank_i] <= 32'd0;
                  stats_ready[stats_bank_i] <= 1'b0;
                  stats_empty[stats_bank_i] <= 1'b1;
                  stats_overflow[stats_bank_i] <= 1'b0;
              end
              stats_sum_live <= 64'd0;
              stats_sum_sq_live <= 64'd0;
              stats_valid_count_live <= 32'd0;
              stats_rx_count_live <= 32'd0;
              stats_min_live <= 17'h1FFFF;
              stats_max_live <= 17'd0;
              stats_cycle_count <= {STATS_COUNT_BITS{1'b0}};
              stats_window_enable <= 1'b0;
              stats_window_busy <= 1'b0;
          end else if (axi_stats_clear_pulse) begin
              stats_sum_snapshot[stats_bank_select] <= 64'd0;
              stats_sum_sq_snapshot[stats_bank_select] <= 64'd0;
              stats_valid_count_snapshot[stats_bank_select] <= 32'd0;
              stats_rx_count_snapshot[stats_bank_select] <= 32'd0;
              stats_min_snapshot[stats_bank_select] <= 17'd0;
              stats_max_snapshot[stats_bank_select] <= 17'd0;
              stats_seq[stats_bank_select] <= 32'd0;
              stats_ready[stats_bank_select] <= 1'b0;
              stats_empty[stats_bank_select] <= 1'b1;
              stats_overflow[stats_bank_select] <= 1'b0;
          end else if (axi_stats_disarm_pulse) begin
              stats_window_enable <= 1'b0;
              stats_window_busy <= 1'b0;
              stats_sum_live <= 64'd0;
              stats_sum_sq_live <= 64'd0;
              stats_valid_count_live <= 32'd0;
              stats_rx_count_live <= 32'd0;
              stats_min_live <= 17'h1FFFF;
              stats_max_live <= 17'd0;
              stats_cycle_count <= {STATS_COUNT_BITS{1'b0}};
          end else if (axi_stats_arm_pulse) begin
              stats_active_bank <= stats_analog_bank;
              stats_window_enable <= 1'b1;
              stats_window_busy <= 1'b1;
              stats_sum_live <= 64'd0;
              stats_sum_sq_live <= 64'd0;
              stats_valid_count_live <= 32'd0;
              stats_rx_count_live <= 32'd0;
              stats_min_live <= 17'h1FFFF;
              stats_max_live <= 17'd0;
              stats_cycle_count <= {STATS_COUNT_BITS{1'b0}};
          end else if (axi_stats_ack_pulse) begin
              // Only clear READY when no newer window has completed in the
              // meantime; otherwise the ACK would swallow that window's flag.
              if (!stats_ack_seq_pending ||
                  stats_ack_seq_value == stats_seq[stats_bank_select]) begin
                  stats_ready[stats_bank_select] <= 1'b0;
              end
              stats_ack_seq_pending <= 1'b0;
          end else if (stats_window_enable) begin
              stats_sum_live <= stats_sum_next[63:0];
              stats_sum_sq_live <= stats_sum_sq_next[63:0];
              stats_valid_count_live <= stats_count_next[31:0];
              stats_rx_count_live <= stats_rx_count_next[31:0];
              if (stats_add_valid) begin
                  if (stats_code < stats_min_live)
                      stats_min_live <= stats_code;
                  if (stats_code > stats_max_live)
                      stats_max_live <= stats_code;
              end

              if (stats_add_valid &&
                  (stats_sum_next[64] || stats_sum_sq_next[64] ||
                   stats_count_next[32] || stats_rx_count_next[32]))
                  stats_overflow[stats_active_bank] <= 1'b1;

              if (stats_period_end) begin
                  stats_sum_snapshot[stats_active_bank] <= stats_sum_next[63:0];
                  stats_sum_sq_snapshot[stats_active_bank] <= stats_sum_sq_next[63:0];
                  stats_valid_count_snapshot[stats_active_bank] <= stats_count_next[31:0];
                  stats_rx_count_snapshot[stats_active_bank] <= stats_rx_count_next[31:0];
                  stats_min_snapshot[stats_active_bank] <=
                      (stats_count_next[31:0] == 0) ? 17'd0 : stats_min_next;
                  stats_max_snapshot[stats_active_bank] <=
                      (stats_count_next[31:0] == 0) ? 17'd0 : stats_max_next;
                  stats_seq[stats_active_bank] <= stats_seq[stats_active_bank] + 32'd1;
                  stats_empty[stats_active_bank] <= (stats_count_next[31:0] == 0);
                  if (stats_ready[stats_active_bank] && !axi_stats_ack_pulse)
                      stats_overflow[stats_active_bank] <= 1'b1;
                  stats_ready[stats_active_bank] <= 1'b1;
                  stats_sum_live <= 64'd0;
                  stats_sum_sq_live <= 64'd0;
                  stats_valid_count_live <= 32'd0;
                  stats_rx_count_live <= 32'd0;
                  stats_min_live <= 17'h1FFFF;
                  stats_max_live <= 17'd0;
                  stats_cycle_count <= {STATS_COUNT_BITS{1'b0}};
              end else begin
                  stats_cycle_count <= stats_cycle_count + 1'b1;
              end
          end
      end
  end

endmodule
