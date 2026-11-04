// Analog front-end command sequencer, extracted verbatim from ALL_Final:
// current off -> 20 ms settle -> relay/polarity change -> 20 ms settle -> current on,
// plus the PS test-mode relay/polarity mask path recorded in analog_seq_reg.
//
// Ownership follows hw/rtl/README.md:
//   * rule 1 (who writes, keeps): ALL_Final keeps every AXI-written register (the
//     commanded range / polarity / current request and the test-mode command); this
//     module only reads them and reports its relay/polarity/current state back out.
//   * rule 2 (TB-overridden parameters stay on top): ANALOG_SETTLE_CYCLES is
//     overridden by four testbenches through the ALL_Final instance, so ALL_Final
//     still declares it and only forwards the value.  Keeping the name identical
//     means the moved body needs no edit at all.
//   * rule 3 (interlocks are inputs): the reset latch and the heartbeat watchdog
//     arrive as inputs - this module never instantiates a peer and never holds policy.
//
// The relay output muxes (range0..3_ctrl / pol_i / pol_v / current_en) stay in
// ALL_Final: they drive board pins and read the AXI-written registers, so they now
// consume this module's outputs as ordinary wires.
module analog_seq #(
    parameter integer ANALOG_SETTLE_CYCLES = 1_000_000
) (
    input  wire        clk,
    input  wire        reset_n,
    // AXI command pulses.
    input  wire        axi_analog_start_pulse,
    input  wire        axi_analog_abort_pulse,
    // AXI-written configuration, forwarded read-only.
    input  wire        analog_test_cmd_enable,
    input  wire [5:0]  analog_test_cmd_mask,
    input  wire        analog_test_cmd_current_en,
    input  wire        analog_test_mask_valid,
    input  wire [1:0]  analog_range_sel_reg,
    input  wire        analog_polarity_reg,
    input  wire        analog_current_req_reg,
    // Safety interlocks (rule 3).
    input  wire        reset_latched,
    input  wire        watchdog_tripped,
    // Relay / polarity / current state, read back by the AXI register file.
    output reg  [3:0]  analog_range_ctrl_reg,
    output reg         analog_pol_i_reg,
    output reg         analog_pol_v_reg,
    output reg         analog_current_en_reg,
    output reg  [2:0]  analog_state_reg,
    output reg         analog_busy,
    output reg         analog_done,
    output reg         analog_error,
    output reg         analog_test_enable,
    output reg  [5:0]  analog_test_relay_mask,
    output reg         analog_test_current_en,
    output reg  [15:0] analog_seq_reg
);

  localparam [2:0] ANALOG_STATE_IDLE       = 3'd0;
  localparam [2:0] ANALOG_STATE_WAIT_SAFE  = 3'd1;
  localparam [2:0] ANALOG_STATE_WAIT_READY = 3'd2;
  localparam [2:0] ANALOG_STATE_ACTIVE     = 3'd3;

  // Settle counter: private to this module (nothing outside the block reads it).
  reg [31:0] analog_settle_count;

  // Normal command sequence:
  // current off -> 20 ms -> relay/polarity change -> 20 ms -> current on.
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          analog_range_ctrl_reg <= 4'b0000;
          analog_pol_i_reg      <= 1'b0;
          analog_pol_v_reg      <= 1'b0;
          analog_current_en_reg <= 1'b0;
          analog_state_reg      <= ANALOG_STATE_IDLE;
          analog_settle_count   <= 32'd0;
          analog_busy           <= 1'b0;
          analog_done           <= 1'b0;
          analog_error          <= 1'b0;
          analog_test_enable    <= 1'b0;
          analog_test_relay_mask<= 6'd0;
          analog_test_current_en<= 1'b0;
          analog_seq_reg         <= 16'd0;
      end else begin
          if (axi_analog_abort_pulse || reset_latched || watchdog_tripped) begin
              analog_range_ctrl_reg <= 4'b0000;
              analog_pol_i_reg      <= 1'b0;
              analog_pol_v_reg      <= 1'b0;
              analog_current_en_reg <= 1'b0;
              analog_state_reg      <= ANALOG_STATE_IDLE;
              analog_settle_count   <= 32'd0;
              analog_busy           <= 1'b0;
              analog_done           <= 1'b0;
              analog_error          <= 1'b0;
              analog_test_enable    <= 1'b0;
              analog_test_relay_mask<= 6'd0;
              analog_test_current_en<= 1'b0;
          end else if (analog_test_cmd_enable) begin
              analog_test_enable     <= 1'b1;
              analog_test_relay_mask <= analog_test_cmd_mask;
              analog_test_current_en <= analog_test_cmd_current_en;
              analog_range_ctrl_reg <= 4'b0000;
              analog_pol_i_reg      <= 1'b0;
              analog_pol_v_reg      <= 1'b0;
              analog_current_en_reg <= 1'b0;
              analog_state_reg      <= ANALOG_STATE_IDLE;
              analog_settle_count   <= 32'd0;
              analog_busy           <= 1'b0;
              analog_done           <= 1'b0;
              analog_error          <= analog_test_mask_valid ? 1'b0 : 1'b1;
          end else if (analog_test_enable) begin
              analog_test_enable     <= 1'b0;
              analog_test_relay_mask <= 6'd0;
              analog_test_current_en <= 1'b0;
              analog_range_ctrl_reg <= 4'b0000;
              analog_pol_i_reg      <= 1'b0;
              analog_pol_v_reg      <= 1'b0;
              analog_current_en_reg <= 1'b0;
              analog_state_reg      <= ANALOG_STATE_IDLE;
              analog_settle_count   <= 32'd0;
              analog_busy           <= 1'b0;
              analog_done           <= 1'b0;
          end else if (axi_analog_start_pulse) begin
              analog_test_enable     <= 1'b0;
              analog_test_relay_mask <= 6'd0;
              analog_test_current_en <= 1'b0;
              analog_range_ctrl_reg <= 4'b0000;
              analog_pol_i_reg      <= 1'b0;
              analog_pol_v_reg      <= 1'b0;
              analog_current_en_reg <= 1'b0;
              analog_state_reg      <= ANALOG_STATE_WAIT_SAFE;
              analog_settle_count   <= 32'd0;
              analog_busy           <= 1'b1;
              analog_done           <= 1'b0;
              analog_error          <= 1'b0;
          end else begin
              case (analog_state_reg)
                  ANALOG_STATE_WAIT_SAFE: begin
                      if (analog_settle_count >= (ANALOG_SETTLE_CYCLES - 1)) begin
                          analog_settle_count   <= 32'd0;
                          analog_range_ctrl_reg <= (4'b0001 << analog_range_sel_reg);
                          analog_pol_i_reg      <= analog_polarity_reg;
                          analog_pol_v_reg      <= analog_polarity_reg;
                          analog_state_reg      <= ANALOG_STATE_WAIT_READY;
                      end else begin
                          analog_settle_count <= analog_settle_count + 32'd1;
                      end
                  end
                  ANALOG_STATE_WAIT_READY: begin
                      if (analog_settle_count >= (ANALOG_SETTLE_CYCLES - 1)) begin
                          analog_settle_count   <= 32'd0;
                          analog_current_en_reg <= analog_current_req_reg;
                          analog_busy           <= 1'b0;
                          analog_done           <= 1'b1;
                          analog_seq_reg        <= analog_seq_reg + 16'd1;
                          analog_state_reg      <= analog_current_req_reg ? ANALOG_STATE_ACTIVE
                                                                          : ANALOG_STATE_IDLE;
                      end else begin
                          analog_settle_count <= analog_settle_count + 32'd1;
                      end
                  end
                  ANALOG_STATE_ACTIVE: begin
                      analog_busy <= 1'b0;
                  end
                  default: begin
                      analog_state_reg <= ANALOG_STATE_IDLE;
                  end
              endcase
          end
      end
  end

endmodule
