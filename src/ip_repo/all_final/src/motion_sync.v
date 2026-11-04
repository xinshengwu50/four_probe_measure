// Sensor debounce, external trigger edge detection and the legacy step pacing
// counters, extracted verbatim from ALL_Final (sections 1-6 of the motion block).
// The body is unchanged; the ports are named exactly like the top-level signals so
// the extraction needed no renaming at all.
//
// is_moving comes from the legacy main state machine (which stays in the top level)
// and gates the pulse/slow counters.
//
// 2026-10-15: the "step pulse generation" block was deleted.  It only ever wrote
// step_pulse_r, which nothing read (the extraction carried it along verbatim as dead
// code, and synthesis reported "Unused sequential element" in every run).  Unlike the
// legacy sequencer's registers this deletion is safe in EVERY configuration: the signal
// had no readers at all, not merely none in the deployed configuration.
module motion_sync #(
    parameter integer PULSE_HALF     = 500,
    parameter integer SLOW_DIV       = 6,
    parameter integer SEN_DELAY_CNT  = 50_000,
    parameter integer x_DEBOUNCE_CNT = 50_000_000 / 100
) (
    input  wire        clk,
    input  wire        reset_n,
    input  wire        sensor,
    input  wire        start_request,
    input  wire        x_trig_request,
    input  wire        is_moving,
    output reg         sen_stable,
    output reg         pulse_tick,
    output wire        slow_step_en,
    output wire        start_edge,
    output wire        x_trig_edge
);

  localparam [31:0] PULSE_PERIOD = 10'd2 * PULSE_HALF;

  reg [9:0]  pulse_cnt;
  reg [3:0]  slow_cnt;
  reg        sen_sync1, sen_sync2;
  reg [15:0] sen_delay_cnt;
  reg        start_sync, start_r;
  reg        x_trig_sync0, x_trig_sync1;
  reg [31:0] x_debounce_cnt;
  reg        x_trig_stable;

  assign slow_step_en = (slow_cnt == SLOW_DIV - 4'd1);

  // 1. 原点传感器两级同步 + 计时消抖
  //=========================================================================
  always @(posedge clk) begin
      if(!reset_n) begin
          sen_sync1    <= 1'b1;
          sen_sync2    <= 1'b1;
          sen_delay_cnt<= 16'd0;
          sen_stable   <= 1'b1;
      end else begin
          sen_sync1 <= sensor;
          sen_sync2 <= sen_sync1;
          if(sen_sync2 != sen_stable) begin
              sen_delay_cnt <= sen_delay_cnt + 16'd1;
              if(sen_delay_cnt >= SEN_DELAY_CNT) begin
                  sen_stable    <= sen_sync2;
                  sen_delay_cnt <= 16'd0;
              end
          end else begin
              sen_delay_cnt <= 16'd0;
          end
      end
  end
  
  //=========================================================================
  // 2. 脉冲周期计数器
  //=========================================================================
  
  always @(posedge clk) begin
      if (!reset_n) begin
          pulse_cnt  <= 10'd0;
          pulse_tick <= 1'b0;
      end else if (!is_moving) begin
          pulse_cnt  <= 10'd0;
          pulse_tick <= 1'b0;
      end else begin
          pulse_tick <= 1'b0;
          if (pulse_cnt >= PULSE_PERIOD - 10'd1) begin
              pulse_cnt  <= 10'd0;
              pulse_tick <= 1'b1;
          end else begin
              pulse_cnt <= pulse_cnt + 10'd1;
          end
      end
  end
  
  //=========================================================================
  // 3. 低速分频计数器
  //=========================================================================
  always @(posedge clk) begin
      if(!reset_n) begin
          slow_cnt <= 4'd0;
      end else if(!is_moving) begin
          slow_cnt <= 4'd0;
      end else begin
          if(pulse_tick) begin
              if(slow_step_en)
                  slow_cnt <= 4'd0;
              else
                  slow_cnt <= slow_cnt + 4'd1;
          end
      end
  end
  
  
  //=========================================================================
  // 5. 模式一触发信号边沿检测（上升沿）
  //=========================================================================
  always @(posedge clk) begin
      if(!reset_n) begin
          start_sync <= 1'b0;
          start_r    <= 1'b0;
      end else begin
          start_sync <= start_request;
          start_r    <= start_sync;
      end
  end
  assign start_edge = start_sync & (~start_r);
  
  //=========================================================================
  // 6. X旋转台触发消抖与边沿检测（模式二触发，上升沿）
  //=========================================================================
  always @(posedge clk) begin
      if(!reset_n) begin
          x_trig_sync0 <= 1'b0;
          x_trig_sync1 <= 1'b0;
          x_debounce_cnt <= 32'd0;
          x_trig_stable <= 1'b0;
      end else begin
          x_trig_sync0 <= x_trig_request;
          x_trig_sync1 <= x_trig_sync0;
          if(x_trig_sync1 != x_trig_stable) begin
              x_debounce_cnt <= x_debounce_cnt + 1'b1;
              if(x_debounce_cnt >= x_DEBOUNCE_CNT) begin
                  x_trig_stable <= x_trig_sync1;
                  x_debounce_cnt <= 32'd0;
              end
          end else begin
              x_debounce_cnt <= 32'd0;
          end
      end
  end
  assign x_trig_edge = x_trig_stable & (~x_trig_sync1);

endmodule
