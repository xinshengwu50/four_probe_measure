// R (radial) axis controller, extracted verbatim from ALL_Final: home-sensor debounce,
// pulse pacing, driver-enable output and the primitive command state machine.
//
// Every interlock is an INPUT (hw/rtl/README.md rule 3).  NOTE: main_state is a CONSTANT
// input in the shipped configuration (LEGACY_AUTO_SEQUENCER_ENABLE = 0); no test may rely on it.
module axis_r #(
    parameter integer R_PULSE_HALF = 500,
    parameter integer R_SLOW_DIV = 6,
    parameter integer R_MAX_STEPS = 40000,
    parameter integer R_DIR_SETUP_CYCLES = 5000,
    parameter integer R_HOME_DEBOUNCE_CYCLES = 50000,
    parameter integer R_TIMEOUT_CYCLES = 750_000_000
) (
    input  wire        clk,
    input  wire        reset_n,
    input  wire        r_sensor,
    input  wire        axi_r_start_pulse,
    input  wire        axi_r_stop_pulse,
    input  wire        axi_r_clear_pulse,
    input  wire [31:0] r_command_reg,
    input  wire [31:0] r_target_reg,
    input  wire        z_probe_clear,
    input  wire [4:0]  main_state,
    input  wire        x_busy,
    input  wire        z_direct_busy,
    input  wire        err_latch,
    input  wire        motion_all_lock,
    input  wire        motion_move_lock,
    input  wire        motion_stop_pulse,
    output reg         r_sensor_stable,
    output reg         r_pulse_tick,
    output reg         r_pul_out,
    output reg         r_dir_out,
    output reg         r_ena_out,
    output reg  [2:0]  r_state,
    output reg         r_done_reg,
    output reg         r_fault,
    output reg         r_homed,
    output reg  [31:0] r_position,
    output reg  [3:0]  r_error_code,
    output wire        r_busy
);

  localparam R_DIR_EXTEND    = 1'b1;
  localparam R_DIR_RETRACT   = 1'b0;
  localparam R_CMD_NOP       = 32'd0;
  localparam R_CMD_HOME      = 32'd1;
  localparam R_CMD_MOVE_TO   = 32'd2;
  localparam R_CMD_MOVE_REL  = 32'd3;
  localparam R_CMD_ZERO      = 32'd4;
  localparam R_STATE_IDLE      = 3'd0;
  localparam R_STATE_DIR_SETUP = 3'd1;
  localparam R_STATE_MOVE      = 3'd2;
  localparam R_STATE_HOME      = 3'd3;
  localparam R_STATE_ERROR     = 3'd4;
  localparam R_ERR_NONE          = 3'd0;
  localparam R_ERR_BUSY          = 3'd1;
  localparam R_ERR_INVALID_CMD   = 3'd2;
  localparam R_ERR_TARGET_RANGE  = 3'd3;
  localparam R_ERR_NOT_HOMED     = 3'd4;
  localparam R_ERR_HOME_TIMEOUT  = 3'd5;
  localparam R_ERR_MOVE_TIMEOUT  = 3'd6;
  localparam R_ERR_ZERO_NOT_HOME = 3'd7;
  localparam R_ERR_MOTION_LOCKED = 4'd9;
  localparam R_ERR_CONFLICT      = 4'd8;
  localparam R_ERR_NOT_CLEAR     = 4'd10;
  localparam R_PULSE_PERIOD = 2 * R_PULSE_HALF;
  localparam [4:0] S_IDLE = 5'd0;   // 顶层主状态机编码（本模块只用到 S_IDLE）

  reg        r_sensor_sync1;
  reg        r_sensor_sync2;
  reg [15:0] r_sensor_delay_cnt;
  reg [9:0]  r_pulse_cnt;
  reg [3:0]  r_slow_cnt;
  reg        r_after_setup_home;
  reg        r_dir_reg;
  reg [31:0] r_target_active;
  reg [31:0] r_timeout_cnt;
  reg [15:0] r_dir_setup_cnt;

  // R axis home sensor synchronizer and debounce
  wire r_slow_step_en = (r_slow_cnt == R_SLOW_DIV - 1'b1);
  wire r_step_tick    = r_pulse_tick && r_slow_step_en;
  assign r_busy = (r_state == R_STATE_DIR_SETUP) ||
                 (r_state == R_STATE_MOVE) ||
                 (r_state == R_STATE_HOME);

  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          r_sensor_sync1   <= 1'b1;
          r_sensor_sync2   <= 1'b1;
          r_sensor_delay_cnt <= 16'd0;
          r_sensor_stable  <= 1'b1;
      end else begin
          r_sensor_sync1 <= r_sensor;
          r_sensor_sync2 <= r_sensor_sync1;
          if (r_sensor_sync2 != r_sensor_stable) begin
              r_sensor_delay_cnt <= r_sensor_delay_cnt + 1'b1;
              if (r_sensor_delay_cnt >= R_HOME_DEBOUNCE_CYCLES) begin
                  r_sensor_stable    <= r_sensor_sync2;
                  r_sensor_delay_cnt <= 16'd0;
              end
          end else begin
              r_sensor_delay_cnt <= 16'd0;
          end
      end
  end

  // R axis pulse timing. Keep the Z-axis timing baseline: about 8.33 kHz.
  wire r_pulse_active = (r_state == R_STATE_MOVE) || (r_state == R_STATE_HOME);

  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          r_pulse_cnt  <= 10'd0;
          r_slow_cnt   <= 4'd0;
          r_pulse_tick <= 1'b0;
          r_pul_out    <= 1'b0;
      end else begin
          r_pulse_tick <= 1'b0;
          if (!r_pulse_active) begin
              r_pulse_cnt <= 10'd0;
              r_slow_cnt  <= 4'd0;
              r_pul_out   <= 1'b0;
          end else begin
              if (r_pulse_cnt >= R_PULSE_PERIOD - 1'b1) begin
                  r_pulse_cnt  <= 10'd0;
                  r_pulse_tick <= 1'b1;
              end else begin
                  r_pulse_cnt <= r_pulse_cnt + 1'b1;
              end

              if (r_pulse_tick) begin
                  if (r_slow_step_en)
                      r_slow_cnt <= 4'd0;
                  else
                      r_slow_cnt <= r_slow_cnt + 1'b1;
              end

              if (r_slow_step_en)
                  r_pul_out <= (r_pulse_cnt >= R_PULSE_HALF);
              else
                  r_pul_out <= 1'b0;
          end
      end
  end

  always @(posedge clk or negedge reset_n) begin
      if (!reset_n)
          r_ena_out <= 1'b1;
      else
          r_ena_out <= r_busy ? 1'b0 : 1'b1;
  end

  // R axis primitive command state machine
  reg [31:0] r_rel_mag;
  reg [31:0] r_calc_target;

  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          r_state            <= R_STATE_IDLE;
          r_after_setup_home <= 1'b0;
          r_dir_reg          <= R_DIR_RETRACT;
          r_dir_out          <= R_DIR_RETRACT;
          r_done_reg         <= 1'b0;
          r_fault            <= 1'b0;
          r_homed            <= 1'b0;
          r_position         <= 32'd0;
          r_target_active    <= 32'd0;
          r_timeout_cnt      <= 32'd0;
          r_dir_setup_cnt    <= 16'd0;
          r_error_code       <= R_ERR_NONE;
      end else begin
          if (axi_r_clear_pulse) begin
              r_fault      <= 1'b0;
              r_error_code <= R_ERR_NONE;
              r_done_reg   <= 1'b0;
              if (!r_busy)
                  r_state <= R_STATE_IDLE;
          end

if ((axi_r_stop_pulse || motion_stop_pulse) && r_busy) begin
              r_state       <= R_STATE_IDLE;
              r_timeout_cnt <= 32'd0;
              r_done_reg    <= 1'b0;
              r_homed       <= 1'b0;
          end else if (axi_r_start_pulse) begin
              r_done_reg    <= 1'b0;
              r_timeout_cnt <= 32'd0;
              r_dir_setup_cnt <= 16'd0;

              if (r_busy) begin
                  r_error_code <= R_ERR_BUSY;
              end else if (r_fault) begin
                  r_error_code <= R_ERR_BUSY;
              end else if (!z_probe_clear) begin
                  // Lateral motion with the probe possibly on the sample would
                  // drag it across the wafer.  Fail-closed: an unknown/cleared
                  // home state counts as "not clear".
                  r_error_code <= R_ERR_NOT_CLEAR;
              end else if ((main_state != S_IDLE) || x_busy || z_direct_busy || err_latch) begin
                  r_error_code <= R_ERR_CONFLICT;
              end else if (motion_all_lock) begin
                  r_state <= R_STATE_ERROR; r_fault <= 1'b1; r_error_code <= R_ERR_MOTION_LOCKED;
              end else if (motion_move_lock && (r_command_reg == R_CMD_MOVE_TO || r_command_reg == R_CMD_MOVE_REL)) begin
                  r_state <= R_STATE_ERROR; r_fault <= 1'b1; r_error_code <= R_ERR_MOTION_LOCKED;
              end else begin
                  case (r_command_reg)
                      R_CMD_HOME: begin
                          if (r_sensor_stable == 1'b0) begin
                              r_position  <= 32'd0;
                              r_homed     <= 1'b1;
                              r_done_reg  <= 1'b1;
                              r_state     <= R_STATE_IDLE;
                              r_error_code<= R_ERR_NONE;
                          end else begin
                              r_dir_reg    <= R_DIR_RETRACT;
                              r_dir_out    <= R_DIR_RETRACT;
                              r_after_setup_home <= 1'b1;
                              r_state      <= R_STATE_DIR_SETUP;
                              r_error_code <= R_ERR_NONE;
                          end
                      end
                      R_CMD_MOVE_TO: begin
                          if (!r_homed) begin
                              r_state      <= R_STATE_ERROR;
                              r_fault      <= 1'b1;
                              r_error_code <= R_ERR_NOT_HOMED;
                          end else if (r_target_reg > R_MAX_STEPS) begin
                              r_state      <= R_STATE_ERROR;
                              r_fault      <= 1'b1;
                              r_error_code <= R_ERR_TARGET_RANGE;
                          end else if (r_target_reg == r_position) begin
                              r_done_reg   <= 1'b1;
                              r_state      <= R_STATE_IDLE;
                              r_error_code <= R_ERR_NONE;
                          end else begin
                              r_dir_reg    <= (r_target_reg > r_position) ? R_DIR_EXTEND : R_DIR_RETRACT;
                              r_dir_out    <= (r_target_reg > r_position) ? R_DIR_EXTEND : R_DIR_RETRACT;
                              r_target_active <= r_target_reg;
                              r_after_setup_home <= 1'b0;
                              r_state      <= R_STATE_DIR_SETUP;
                              r_error_code <= R_ERR_NONE;
                          end
                      end
                      R_CMD_MOVE_REL: begin
                          if (!r_homed) begin
                              r_state      <= R_STATE_ERROR;
                              r_fault      <= 1'b1;
                              r_error_code <= R_ERR_NOT_HOMED;
                          end else if (r_target_reg[31]) begin
                              r_rel_mag = (~r_target_reg) + 1'b1;
                              if (r_rel_mag > r_position) begin
                                  r_state      <= R_STATE_ERROR;
                                  r_fault      <= 1'b1;
                                  r_error_code <= R_ERR_TARGET_RANGE;
                              end else begin
                                  r_calc_target = r_position - r_rel_mag;
                                  r_target_active <= r_calc_target;
                                  r_dir_reg    <= R_DIR_RETRACT;
                                  r_dir_out    <= R_DIR_RETRACT;
                                  r_after_setup_home <= 1'b0;
                                  r_state      <= R_STATE_DIR_SETUP;
                                  r_error_code <= R_ERR_NONE;
                              end
                          end else if (r_target_reg > (R_MAX_STEPS - r_position)) begin
                              r_state      <= R_STATE_ERROR;
                              r_fault      <= 1'b1;
                              r_error_code <= R_ERR_TARGET_RANGE;
                          end else begin
                              r_calc_target = r_position + r_target_reg;
                              r_target_active <= r_calc_target;
                              r_dir_reg    <= (r_calc_target > r_position) ? R_DIR_EXTEND : R_DIR_RETRACT;
                              r_dir_out    <= (r_calc_target > r_position) ? R_DIR_EXTEND : R_DIR_RETRACT;
                              r_after_setup_home <= 1'b0;
                              r_state      <= R_STATE_DIR_SETUP;
                              r_error_code <= R_ERR_NONE;
                          end
                      end
                      R_CMD_ZERO: begin
                          if (r_sensor_stable == 1'b0) begin
                              r_position   <= 32'd0;
                              r_homed      <= 1'b1;
                              r_done_reg   <= 1'b1;
                              r_state      <= R_STATE_IDLE;
                              r_error_code <= R_ERR_NONE;
                          end else begin
                              r_state      <= R_STATE_ERROR;
                              r_fault      <= 1'b1;
                              r_error_code <= R_ERR_ZERO_NOT_HOME;
                          end
                      end
                      default: begin
                          r_state      <= R_STATE_ERROR;
                          r_fault      <= 1'b1;
                          r_error_code <= R_ERR_INVALID_CMD;
                      end
                  endcase
              end
          end else begin
              case (r_state)
                  R_STATE_DIR_SETUP: begin
                      if (r_dir_setup_cnt >= R_DIR_SETUP_CYCLES - 1'b1)
                          r_state <= r_after_setup_home ? R_STATE_HOME : R_STATE_MOVE;
                      else
                          r_dir_setup_cnt <= r_dir_setup_cnt + 1'b1;
                  end
                  R_STATE_MOVE: begin
                      if (r_position == r_target_active) begin
                          r_done_reg   <= 1'b1;
                          r_state      <= R_STATE_IDLE;
                          r_error_code <= R_ERR_NONE;
                      end else if (r_step_tick) begin
                          if (r_dir_reg == R_DIR_EXTEND) begin
                              r_position <= r_position + 1'b1;
                          end else if (r_position != 32'd0) begin
                              r_position <= r_position - 1'b1;
                          end else begin
                              r_state      <= R_STATE_ERROR;
                              r_fault      <= 1'b1;
                              r_homed      <= 1'b0;
                              r_error_code <= R_ERR_TARGET_RANGE;
                          end
                      end
                  end
                  R_STATE_HOME: begin
                      if (r_sensor_stable == 1'b0) begin
                          r_position   <= 32'd0;
                          r_homed      <= 1'b1;
                          r_done_reg   <= 1'b1;
                          r_state      <= R_STATE_IDLE;
                          r_error_code <= R_ERR_NONE;
                      end
                  end
                  default: r_state <= R_STATE_IDLE;
              endcase
          end

          if (r_busy) begin
              if (r_timeout_cnt >= R_TIMEOUT_CYCLES - 1'b1) begin
                  r_state      <= R_STATE_ERROR;
                  r_fault      <= 1'b1;
                  r_homed      <= 1'b0;
                  r_error_code <= (r_state == R_STATE_HOME) ?
                                  R_ERR_HOME_TIMEOUT : R_ERR_MOVE_TIMEOUT;
              end else begin
                  r_timeout_cnt <= r_timeout_cnt + 1'b1;
              end
          end
      end
  end

endmodule
