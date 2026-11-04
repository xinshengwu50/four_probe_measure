// Z axis controller, extracted verbatim from ALL_Final: the atomic STEP pulse
// generator, the primitive Z command state machine (HOME / MOVE_TO / MOVE_REL /
// RETURN_HOME_SAFE / ZERO), the deceleration ramp and the physical STEP/DIR/ENA
// output stage, plus the exported Z "direct busy" flag.
//
// Ownership follows hw/rtl/README.md:
//   * rule 1 (who writes, keeps): ALL_Final keeps every AXI-written register --
//     the command/target registers, the deceleration configuration and the 16x32
//     deceleration LUT -- and hands this module read-only copies.
//   * rule 2 (TB-overridden parameters stay on top): every parameter below is
//     overridden by a testbench through the ALL_Final instance, so ALL_Final
//     still declares it and only forwards the value.
//   * rule 3 (interlocks are inputs): motion_all_lock, motion_move_lock,
//     main_state, x_busy, r_busy, err_latch and the refusal predicate
//     z_cmd_retract_only arrive as inputs; the module never instantiates a peer
//     and never holds policy.
//       NOTE: main_state is a CONSTANT input in the shipped configuration
//       (LEGACY_AUTO_SEQUENCER_ENABLE = 0); no test may rely on it.
//   * z_probe_clear stays on top.  The top level keeps that fail-closed policy and
//     derives it from the Z state exported here (z_homed / z_position), so reset
//     and STOP still clear z_homed and "do not know" keeps meaning "not safe".
module axis_z #(
    parameter integer PULSE_HALF = 500,
    parameter integer SLOW_DIV = 6,
    parameter integer PULSE_PERIOD = 2 * PULSE_HALF,
    // Standalone default; ALL_Final forwards its own Z_MAX_STEPS into this
    // module (200 -> 10000 on 2026-10-16).
    parameter integer Z_MAX_STEPS = 10000,
    parameter integer Z_DIR_SETUP_CYCLES = 5000,
    parameter integer Z_TIMEOUT_CYCLES = 750_000_000
) (
    input  wire        clk,
    input  wire        reset_n,
    // AXI command pulses plus the top-level interlocks / policy predicates.
    input  wire        axi_z_start_pulse,
    input  wire        axi_z_stop_pulse,
    input  wire        axi_z_clear_pulse,
    input  wire        motion_all_lock,
    input  wire        motion_move_lock,
    input  wire        motion_stop_pulse,
    input  wire [4:0]  main_state,
    input  wire        x_busy,
    input  wire        r_busy,
    input  wire        err_latch,
    input  wire        cycle_done_r,
    input  wire [31:0] z_command_reg,
    input  wire [31:0] z_target_reg,
    input  wire        z_cmd_retract_only,
    input  wire        z_driver_armed,
    input  wire        sen_stable,
    // AXI-written deceleration configuration, forwarded read-only.
    input  wire [31:0] z_step_interval_cycles,
    input  wire        z_decel_enable,
    input  wire        z_decel_measure_enable,
    input  wire        z_decel_return_enable,
    input  wire        z_decel_all_enable,
    input  wire [31:0] z_decel_window_steps,
    input  wire [31:0] z_decel_seg_steps,
    input  wire [511:0] z_decel_lut_flat,
    // Physical Z driver pins and the Z state the top level reads back.
    output reg         step_pulse,
    output reg         dir,
    output reg         ena,
    output reg         err_flag,
    output reg         cycle_done,
    output wire        z_direct_busy,
    output reg  [31:0] z_position,
    output reg         z_homed,
    output reg         z_fault,
    output reg         z_done_reg,
    output reg         z_dir_reg,
    output reg  [3:0]  z_error_code,
    output reg         z_measure_start_pulse,
    output reg  [31:0] z_home_step_cnt
);

  // Z axis direction / command / state / error encodings (module-local copies of
  // the ALL_Final constants, exactly as done for axis_x and axis_r).
  localparam Z_DIR_DOWN = 1'b0;
  localparam Z_DIR_UP   = 1'b1;

  localparam Z_CMD_NOP             = 32'd0;
  localparam Z_CMD_HOME            = 32'd1;
  localparam Z_CMD_MOVE_TO         = 32'd2;
  localparam Z_CMD_MOVE_TO_MEASURE = 32'd3;
  localparam Z_CMD_MOVE_REL        = 32'd4;
  localparam Z_CMD_ZERO            = 32'd5;
  localparam Z_CMD_RETURN_HOME_SAFE = 32'd6;

  localparam Z_STATE_IDLE      = 3'd0;
  localparam Z_STATE_DIR_SETUP = 3'd1;
  localparam Z_STATE_MOVE      = 3'd2;
  localparam Z_STATE_HOME      = 3'd3;
  localparam Z_STATE_ERROR     = 3'd4;

  localparam Z_ERR_NONE          = 4'd0;
  localparam Z_ERR_BUSY          = 4'd1;
  localparam Z_ERR_INVALID_CMD   = 4'd2;
  localparam Z_ERR_TARGET_RANGE  = 4'd3;
  localparam Z_ERR_NOT_HOMED     = 4'd4;
  localparam Z_ERR_HOME_TIMEOUT  = 4'd5;
  localparam Z_ERR_MOVE_TIMEOUT  = 4'd6;
  localparam Z_ERR_ZERO_NOT_HOME = 4'd7;
  localparam Z_ERR_CONFLICT      = 4'd8;
  localparam Z_ERR_MOTION_LOCKED = 4'd9;

  localparam [4:0] S_IDLE = 5'd0;   // top-level main-state encoding (only S_IDLE used here)

  // Z state that never leaves the module.
  reg        z_pul_out;
  reg [31:0] z_target_active;
  reg [31:0] z_timeout_cnt;
  reg [2:0]  z_state;
  reg        z_after_setup_home;
  reg        z_after_setup_measure;
  reg [15:0] z_dir_setup_cnt;
  reg        z_step_tick;
  reg        z_pulse_phase;
  reg [31:0] z_pulse_phase_cnt;
  reg [31:0] z_interval_active;
  reg        z_after_setup_return_home;
  reg [3:0]  z_decel_seg;
  reg [31:0] z_decel_seg_cnt;
  reg        z_decel_started;

  assign z_direct_busy  = (z_state == Z_STATE_DIR_SETUP) ||
                          (z_state == Z_STATE_MOVE) ||
                          (z_state == Z_STATE_HOME);

  // Read-only view of the AXI-written deceleration LUT.  "z_decel_seg*32 +: 32"
  // selects entry z_decel_seg of the 512-bit flat replica (entry 0 in the LSBs),
  // which synthesises to the same 16:1 / 32-bit mux as the original array read.
  wire [31:0] z_decel_period_lut_sel = z_decel_lut_flat[z_decel_seg*32 +: 32];

  wire z_pulse_active = z_driver_armed && ((z_state == Z_STATE_MOVE) || (z_state == Z_STATE_HOME));
  wire [31:0] z_motion_remaining = (z_target_active > z_position) ? (z_target_active - z_position) : (z_position - z_target_active);
  wire z_decel_cmd = z_decel_all_enable ||
                     (z_after_setup_measure && z_decel_measure_enable) ||
                     (z_after_setup_return_home && z_decel_return_enable);
  wire z_decel_state_active = (z_state == Z_STATE_MOVE) ||
                              (z_decel_all_enable && (z_state == Z_STATE_HOME));
  wire z_decel_active = z_decel_enable && z_decel_cmd && z_decel_state_active &&
                        (z_motion_remaining <= z_decel_window_steps) && (z_motion_remaining != 0);
  wire [31:0] z_interval_selected = z_decel_active ? z_decel_period_lut_sel : z_step_interval_cycles;
  wire [31:0] z_interval_cfg = (z_interval_selected >= PULSE_PERIOD) ? z_interval_selected : PULSE_PERIOD;
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          z_pulse_phase<=1'b0; z_pulse_phase_cnt<=32'd0; z_step_tick<=1'b0;
          z_pul_out<=1'b0; z_interval_active<=PULSE_PERIOD*SLOW_DIV;
      end
      else begin
          z_step_tick<=1'b0;
          if (!z_pulse_active) begin
              z_pulse_phase<=1'b0; z_pulse_phase_cnt<=32'd0; z_pul_out<=1'b0;
              z_interval_active<=z_interval_cfg;
          end else if (z_pulse_phase==1'b0) begin
              if (z_pulse_phase_cnt >= z_interval_active - PULSE_HALF - 1'b1) begin
                  z_pulse_phase<=1'b1;
                  z_pulse_phase_cnt<=32'd0;
                  z_pul_out<=1'b1;
                  z_step_tick<=1'b1;
                  z_interval_active<=z_interval_cfg;
              end else begin
                  z_pulse_phase_cnt<=z_pulse_phase_cnt+1'b1;
              end
          end else begin
              if (z_pulse_phase_cnt >= PULSE_HALF - 1'b1) begin
                  z_pulse_phase<=1'b0;
                  z_pulse_phase_cnt<=32'd0;
                  z_pul_out<=1'b0;
              end else begin
                  z_pulse_phase_cnt<=z_pulse_phase_cnt+1'b1;
              end
          end
      end
  end
  reg [31:0] z_rel_mag; reg [31:0] z_calc_target;
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          z_state<=Z_STATE_IDLE; z_after_setup_home<=0; z_after_setup_measure<=0; z_after_setup_return_home<=0; z_dir_reg<=Z_DIR_UP;
          z_decel_seg<=0; z_decel_seg_cnt<=0; z_decel_started<=0;
          z_done_reg<=0; z_fault<=0; z_homed<=0; z_position<=0; z_target_active<=0; z_timeout_cnt<=0;
          z_dir_setup_cnt<=0; z_error_code<=Z_ERR_NONE; z_measure_start_pulse<=0; z_home_step_cnt<=0;
      end else begin
          z_measure_start_pulse<=0;
          if (axi_z_clear_pulse) begin z_fault<=0; z_error_code<=Z_ERR_NONE; z_done_reg<=0; if (!z_direct_busy) z_state<=Z_STATE_IDLE; end
          if ((axi_z_stop_pulse || motion_stop_pulse) && z_direct_busy) begin z_state<=Z_STATE_IDLE; z_timeout_cnt<=0; z_done_reg<=0; z_homed<=0; end
          else if (axi_z_start_pulse) begin
              z_done_reg<=0; z_timeout_cnt<=0; z_dir_setup_cnt<=0; z_after_setup_return_home<=0;
              z_home_step_cnt<=0;
              z_decel_seg<=0; z_decel_seg_cnt<=0; z_decel_started<=0;
              if (z_direct_busy) z_error_code<=Z_ERR_BUSY;
              else if (z_fault) z_error_code<=Z_ERR_BUSY;
              else if (motion_all_lock) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_MOTION_LOCKED; end
              else if (motion_move_lock && (z_command_reg==Z_CMD_MOVE_TO || z_command_reg==Z_CMD_MOVE_REL || z_command_reg==Z_CMD_MOVE_TO_MEASURE))
                  begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_MOTION_LOCKED; end
              // Restored 2026-10-11: the Batch 3 motion-lock edit dropped this line.
              // (a) 2026-10-11: HOME / RETURN_HOME_SAFE can only move the probe
              // away from the sample, so they skip the conflict check - a retract
              // must never be blocked by another axis still moving.
              else if (!z_cmd_retract_only && ((main_state!=S_IDLE)||x_busy||r_busy||err_latch)) z_error_code<=Z_ERR_CONFLICT;
              else case (z_command_reg)
                  Z_CMD_HOME: begin
                      if (sen_stable==0) begin z_position<=0; z_homed<=1; z_done_reg<=1; z_state<=Z_STATE_IDLE; z_error_code<=Z_ERR_NONE; end
                      else begin z_dir_reg<=Z_DIR_UP; z_after_setup_home<=1; z_after_setup_measure<=0; z_after_setup_return_home<=0; z_state<=Z_STATE_DIR_SETUP; z_error_code<=Z_ERR_NONE; end
                  end
                  Z_CMD_MOVE_TO, Z_CMD_MOVE_TO_MEASURE: begin
                      if (!z_homed) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_NOT_HOMED; end
                      else if (z_target_reg>Z_MAX_STEPS) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_TARGET_RANGE; end
                      else if (z_target_reg==z_position) begin z_done_reg<=1; z_state<=Z_STATE_IDLE; z_measure_start_pulse<=(z_command_reg==Z_CMD_MOVE_TO_MEASURE); z_error_code<=Z_ERR_NONE; end
                      else begin z_dir_reg<=(z_target_reg>z_position)?Z_DIR_DOWN:Z_DIR_UP; z_target_active<=z_target_reg; z_after_setup_home<=0; z_after_setup_measure<=(z_command_reg==Z_CMD_MOVE_TO_MEASURE); z_after_setup_return_home<=0; z_state<=Z_STATE_DIR_SETUP; z_error_code<=Z_ERR_NONE; end
                  end
                  Z_CMD_MOVE_REL: begin
                      if (!z_homed) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_NOT_HOMED; end
                      else if (z_target_reg[31]) begin
                          z_rel_mag=(~z_target_reg)+1;
                          if (z_rel_mag>z_position) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_TARGET_RANGE; end
                                  else begin z_calc_target=z_position-z_rel_mag; z_target_active<=z_calc_target; z_dir_reg<=Z_DIR_UP; z_after_setup_home<=0; z_after_setup_measure<=0; z_after_setup_return_home<=0; z_state<=Z_STATE_DIR_SETUP; z_error_code<=Z_ERR_NONE; end
                      end else if (z_target_reg>(Z_MAX_STEPS-z_position)) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_TARGET_RANGE; end
                              else begin z_calc_target=z_position+z_target_reg; z_target_active<=z_calc_target; z_dir_reg<=(z_calc_target>z_position)?Z_DIR_DOWN:Z_DIR_UP; z_after_setup_home<=0; z_after_setup_measure<=0; z_after_setup_return_home<=0; z_state<=Z_STATE_DIR_SETUP; z_error_code<=Z_ERR_NONE; end
                          end
                  Z_CMD_RETURN_HOME_SAFE: begin
                      if (!z_homed) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_NOT_HOMED; end
                      else if (z_position==0 && sen_stable==0) begin z_position<=0; z_homed<=1; z_done_reg<=1; z_state<=Z_STATE_IDLE; z_error_code<=Z_ERR_NONE; end
                      else begin z_target_active<=0; z_dir_reg<=Z_DIR_UP; z_after_setup_home<=0; z_after_setup_measure<=0; z_after_setup_return_home<=1; z_state<=Z_STATE_DIR_SETUP; z_error_code<=Z_ERR_NONE; end
                  end
                  Z_CMD_ZERO: begin
                      if (sen_stable==0) begin z_position<=0; z_homed<=1; z_done_reg<=1; z_state<=Z_STATE_IDLE; z_error_code<=Z_ERR_NONE; end
                      else begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_ZERO_NOT_HOME; end
                  end
                  default: begin z_state<=Z_STATE_ERROR; z_fault<=1; z_error_code<=Z_ERR_INVALID_CMD; end
              endcase
          end else begin
              case (z_state)
                  Z_STATE_DIR_SETUP: if (z_dir_setup_cnt>=Z_DIR_SETUP_CYCLES-1) z_state<=z_after_setup_home?Z_STATE_HOME:Z_STATE_MOVE; else z_dir_setup_cnt<=z_dir_setup_cnt+1;
                  Z_STATE_MOVE: begin
                      if (z_after_setup_return_home && sen_stable==0) begin z_position<=0; z_homed<=1; z_done_reg<=1; z_state<=Z_STATE_IDLE; z_error_code<=Z_ERR_NONE; z_decel_started<=0; end
                      else if (z_position==z_target_active) begin z_done_reg<=1; z_state<=Z_STATE_IDLE; z_measure_start_pulse<=z_after_setup_measure; z_error_code<=Z_ERR_NONE; z_decel_started<=0; end
                      else if (z_step_tick) begin
                          if (z_dir_reg==Z_DIR_DOWN) begin
                              if (z_position>=Z_MAX_STEPS) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_homed<=0; z_error_code<=Z_ERR_TARGET_RANGE; end
                              else z_position<=z_position+1;
                          end
                          else if (z_position!=0) z_position<=z_position-1;
                          else begin z_state<=Z_STATE_ERROR; z_fault<=1; z_homed<=0; z_error_code<=Z_ERR_TARGET_RANGE; end
                          if (z_decel_active) begin
                              if (!z_decel_started) begin
                                  z_decel_started<=1'b1; z_decel_seg<=4'd0; z_decel_seg_cnt<=32'd1;
                              end else if (z_decel_seg < 4'hF) begin
                                  if ((z_decel_seg_cnt + 1'b1) >= z_decel_seg_steps) begin
                                      z_decel_seg<=z_decel_seg+1'b1; z_decel_seg_cnt<=32'd0;
                                  end else begin
                                      z_decel_seg_cnt<=z_decel_seg_cnt+1'b1;
                                  end
                              end
                          end else begin
                              z_decel_started<=1'b0; z_decel_seg<=4'd0; z_decel_seg_cnt<=32'd0;
                          end
                      end
                  end
                  Z_STATE_HOME: begin
                      if (sen_stable==0) begin
                          z_position<=0; z_homed<=1; z_done_reg<=1; z_state<=Z_STATE_IDLE; z_error_code<=Z_ERR_NONE;
                          z_decel_started<=1'b0; z_decel_seg<=4'd0; z_decel_seg_cnt<=32'd0;
                      end else if (z_home_step_cnt>=Z_MAX_STEPS) begin
                          z_state<=Z_STATE_ERROR; z_fault<=1; z_homed<=0; z_error_code<=Z_ERR_HOME_TIMEOUT;
                      end else if (z_step_tick) begin
                          z_home_step_cnt<=z_home_step_cnt+32'd1;
                          if (z_decel_active) begin
                              if (!z_decel_started) begin
                                  z_decel_started<=1'b1; z_decel_seg<=4'd0; z_decel_seg_cnt<=32'd1;
                              end else if (z_decel_seg < 4'hF) begin
                                  if ((z_decel_seg_cnt + 1'b1) >= z_decel_seg_steps) begin
                                      z_decel_seg<=z_decel_seg+1'b1; z_decel_seg_cnt<=32'd0;
                                  end else begin
                                      z_decel_seg_cnt<=z_decel_seg_cnt+1'b1;
                                  end
                              end
                          end else begin
                              z_decel_started<=1'b0; z_decel_seg<=4'd0; z_decel_seg_cnt<=32'd0;
                          end
                      end
                  end
                  default: z_state<=Z_STATE_IDLE;
              endcase
          end
          if (z_direct_busy) begin
              if (z_timeout_cnt>=Z_TIMEOUT_CYCLES-1) begin z_state<=Z_STATE_ERROR; z_fault<=1; z_homed<=0; z_error_code<=(z_state==Z_STATE_HOME)?Z_ERR_HOME_TIMEOUT:Z_ERR_MOVE_TIMEOUT; end
              else z_timeout_cnt<=z_timeout_cnt+1;
          end
      end
  end
  always @(posedge clk) begin
      if(!reset_n) begin
          step_pulse <= 1'b0;
          dir        <= 1'b0;
          // ena is ACTIVE LOW: 1 keeps the Z driver disabled while reset is asserted.
          ena        <= 1'b1;
          err_flag   <= 1'b0;
          cycle_done <= 1'b0;
      end else begin
          // The physical Z STEP/DIR/ENA pins are owned exclusively by the AXI Z
          // controller and stay disabled unless the driver is armed and a
          // commanded move is in progress.  The legacy automatic sequencer must
          // never drive these pins: it is outside the ARM interlock and can
          // issue a full-stroke STEPS_FORWARD down press.
          step_pulse <= (z_driver_armed && z_direct_busy) ? z_pul_out : 1'b0;
          // Park DIR at UP while idle: a stray STEP edge can then never
          // push the probe further into the sample.
          dir        <= (z_driver_armed && z_direct_busy) ? z_dir_reg : 1'b1;
          // Hold torque for the whole armed window, not only while stepping:
          // an unpowered vertical axis must not be able to slide down.
          ena        <= z_driver_armed ? 1'b0 : 1'b1;
          err_flag   <= err_latch;
          cycle_done <= cycle_done_r;
      end
  end

endmodule
