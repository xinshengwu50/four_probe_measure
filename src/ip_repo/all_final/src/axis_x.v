// X rotation stage pulse driver, extracted verbatim from ALL_Final (section 7).
// Owns only the counter/state of the bare pulse generator; every interlock is an input:
// motion_all_lock / motion_stop_pulse (reset + watchdog) and z_probe_clear / z_direct_busy /
// r_busy (cross-axis safety) are produced by the top level or by the other axis modules.
module axis_x #(
    parameter integer x_PUL_NUM     = 3000,
    parameter integer x_HALF_PERIOD = 50000000 / 1000 / 2
) (
    input  wire        clk,
    input  wire        reset_n,
    input  wire        start_internal,    // from the legacy auto sequencer
    input  wire        direct_start,      // = x_direct_start
    input  wire        var_direct_start,  // = x_var_direct_start
    input  wire [31:0] target,            // = x_target_reg (AXI)
    input  wire        motion_all_lock,
    input  wire        motion_stop_pulse,
    input  wire        z_probe_clear,
    input  wire        z_direct_busy,
    input  wire        r_busy,
    output reg         busy,
    output reg         pul_out,
    output reg         dir_out,
    output reg  [31:0] position,
    output reg         done_reg
);

  reg [31:0] timer_cnt;
  reg [31:0] pulse_cnt;
  reg [31:0] target_active;

  always @(posedge clk) begin
      if(!reset_n) begin
          busy          <= 1'b0;
          pul_out       <= 1'b0;
          dir_out       <= 1'b1;
          timer_cnt     <= 32'd0;
          pulse_cnt     <= 32'd0;
          target_active <= x_PUL_NUM;
          position      <= 32'd0;
          done_reg      <= 1'b0;
      end else begin
          if(!busy) begin
              pul_out   <= 1'b0;
              timer_cnt <= 32'd0;
              pulse_cnt <= 32'd0;
              if((start_internal || direct_start || var_direct_start) && !motion_all_lock &&
                 z_probe_clear && !z_direct_busy && !r_busy) begin
                  target_active <= var_direct_start ? target : x_PUL_NUM;
                  done_reg      <= 1'b0;
                  if ((var_direct_start ? target : x_PUL_NUM) == 0) begin
                      done_reg <= 1'b1;
                  end else begin
                      busy <= 1'b1;
                  end
              end
          end else if (motion_stop_pulse) begin
              // Abort the X move: keep the pulse/position counters so the PS
              // can detect the shortfall, stop stepping and report done.
              busy      <= 1'b0;
              pul_out   <= 1'b0;
              timer_cnt <= 32'd0;
              done_reg  <= 1'b1;
          end else begin
              timer_cnt <= timer_cnt + 1'b1;
              if(timer_cnt >= x_HALF_PERIOD) begin
                  timer_cnt <= 32'd0;
                  pul_out <= ~pul_out;
                  if(pul_out == 1'b1) begin
                      pulse_cnt <= pulse_cnt + 1'b1;
                      position  <= position + 1'b1;
                      if(pulse_cnt >= target_active - 1'b1) begin
                          busy <= 1'b0;
                          done_reg <= 1'b1;
                      end
                  end
              end
          end
      end
  end

endmodule
