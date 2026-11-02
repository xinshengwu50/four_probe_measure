// Legacy measurement chain, extracted from ALL_Final: the 50 ms sample trigger, the
// 5-sample median / hold, the rho & Rs fixed-point pipeline with its state machine and
// the decimal-split of hold_V_mV.  Extracted as ONE module because these blocks are a
// pipeline (the trigger feeds the sampler, the sampler feeds the median, the median feeds
// the calculator, the calculator feeds the splitters) and splitting it further would only
// move wires across the boundary.  The blocks still in ALL_Final (the BCD converters, the
// display path and the AXI register file) read rho/Rs/rho_*/RS_*/v0..v4 from here.
//
// Ownership follows hw/rtl/README.md: rule 2 keeps every TB-overridden parameter in the
// parent and forwards it (MCNT_DELAY is overridden by three testbenches), and the two state
// encodings CALC_IDLE / CALC_DONE are parameters that the BCD blocks still compare against,
// so ALL_Final keeps its own copy and this module declares its own.
module meas_chain #(
    parameter MCNT_DELAY = 50000,
    parameter RHO_FD = 0, RHO_FW = 0, RHO_FSP = 0, W_mm = 0,
    parameter CALC_IDLE = 5'd0, CALC_DONE = 5'd21,
    parameter S_IDLE = 5'd0, S_MODE1_PAUSE = 5'd4, S_MODE1_BACK = 5'd6,
    parameter S_M2_PAUSE1 = 5'd8, S_M2_PAUSE2 = 5'd14, S_M2_DIR1 = 5'd9, S_M2_DIR3 = 5'd15
) (
    input  wire         clk,
    input  wire         reset_n,
    input  wire         start_edge,
    input  wire         x_trig_edge,
    input  wire [15:0]  V_mV,
    input  wire [79:0]  median_after_pass,
    input  wire [4:0]   main_state,
    output reg            send_go_update,
    output reg  [79:0]    median_arr_packed,
    output reg  [4:0]     calc_state,
    output reg  [31:0]    rho,
    output reg  [31:0]    Rs,
    output reg  [31:0]    rho_S,
    output reg  [31:0]    RS_S,
    output reg  [31:0]    rho_1,
    output reg  [31:0]    RS_1,
    output reg  [31:0]    rho_2,
    output reg  [31:0]    RS_2,
    output reg  [31:0]    rho_3,
    output reg  [31:0]    RS_3,
    output reg  [31:0]    rho_4,
    output reg  [31:0]    RS_4,
    output reg  [2:0]     calc_slot,
    output reg  [3:0]     v0,
    output reg  [3:0]     v1,
    output reg  [3:0]     v2,
    output reg  [3:0]     v3,
    output reg  [3:0]     v4
);

  reg                  calc_done;   // was declared in the parent
  reg                  calc_trigger;   // was declared in the parent
  reg                  median_busy;   // was declared in the parent
  reg                  sampling_active;   // was declared in the parent
  reg                  voltage_latched;   // was declared in the parent
  reg        [15:0]    hold_V_mV;   // was declared in the parent
  reg        [15:0]    v_sample0;   // was declared in the parent
  reg        [15:0]    v_sample1;   // was declared in the parent
  reg        [15:0]    v_sample2;   // was declared in the parent
  reg        [15:0]    v_sample3;   // was declared in the parent
  reg        [15:0]    v_sample4;   // was declared in the parent
  reg        [1:0]     median_pass;   // was declared in the parent
  reg        [24:0]    meas_delay_cnt;   // was declared in the parent
  reg        [29:0]    delay_cnt_update;   // was declared in the parent
  reg        [2:0]     m2_calc_cnt;   // was declared in the parent
  reg        [2:0]     sample_cnt;   // was declared in the parent
  reg        [4:0]     main_state_d;   // was declared in the parent
  reg        [4:0]     prev_main_state;   // was declared in the parent

  always@(posedge clk)
      if(!reset_n) begin
          delay_cnt_update <= 0;
          send_go_update <= 0;
      end else begin
          if(delay_cnt_update == MCNT_DELAY) begin
              delay_cnt_update <= 0;
              send_go_update <= 1;
          end else begin
              delay_cnt_update <= delay_cnt_update + 1'd1;
              send_go_update <= 0;
          end
      end
  
  parameter MEAS_DELAY_50MS = 25_000_00 - 1;   // 放在其他参数定义附近
  //==================== 5.5 500ms等待 + 采集5个有效电压取中值 ==========
  always @(posedge clk) begin
      if(!reset_n) begin
          meas_delay_cnt  <= 25'd0;
          hold_V_mV       <= 16'd0;
          voltage_latched <= 1'b0;
          prev_main_state <= S_IDLE;
          sample_cnt      <= 3'd0;
          sampling_active <= 1'b0;
          v_sample0 <= 16'd0;
          v_sample1 <= 16'd0;
          v_sample2 <= 16'd0;
          v_sample3 <= 16'd0;
          v_sample4 <= 16'd0;
          median_arr_packed <= 80'd0;
          median_pass <= 2'd0;
          median_busy <= 1'b0;
      end else begin
          prev_main_state <= main_state;
  
          // 进入暂停态（上升沿）时复位所有状态
          if((main_state == S_MODE1_PAUSE || main_state == S_M2_PAUSE1 || main_state == S_M2_PAUSE2)
             && (prev_main_state != main_state)) begin
              meas_delay_cnt  <= 25'd0;
              voltage_latched <= 1'b0;
              sample_cnt      <= 3'd0;
              sampling_active <= 1'b0;
              v_sample0 <= 16'd0;
              v_sample1 <= 16'd0;
              v_sample2 <= 16'd0;
              v_sample3 <= 16'd0;
              v_sample4 <= 16'd0;
              hold_V_mV <= 16'd0;
              median_arr_packed <= 80'd0;
              median_pass <= 2'd0;
              median_busy <= 1'b0;
          end
  
          // 在暂停态且未锁存时处理
          else if((main_state == S_MODE1_PAUSE || main_state == S_M2_PAUSE1 || main_state == S_M2_PAUSE2)
                  && !voltage_latched) begin
              // ---------- 阶段1：等待500ms ----------
              if(!sampling_active) begin
                  if(meas_delay_cnt >= MEAS_DELAY_50MS) begin
                      sampling_active <= 1'b1;
                      meas_delay_cnt <= 25'd0;   // 清零，后续不再使用
                  end else begin
                      meas_delay_cnt <= meas_delay_cnt + 25'd1;
                  end
              end
              // ---------- 阶段2：采集5个有效值 ----------
              else begin
                  if(median_busy) begin
                      // One bubble-sort pass per clock; the median is valid after
                      // four passes. This keeps the comparator path below 20 ns.
                      median_arr_packed <= median_after_pass;
                      if(median_pass == 2'd3) begin
                          hold_V_mV       <= median_after_pass[47:32];
                          voltage_latched <= 1'b1;
                          sampling_active <= 1'b0;
                          median_busy     <= 1'b0;
                          median_pass     <= 2'd0;
                      end else begin
                          median_pass <= median_pass + 2'd1;
                      end
                  end else if(sample_cnt < 3'd5) begin
                      // Nonzero V_mV denotes a valid 490..650 mV sample.
                      if(V_mV != 16'd0) begin
                          case(sample_cnt)
                              3'd0: v_sample0 <= V_mV;
                              3'd1: v_sample1 <= V_mV;
                              3'd2: v_sample2 <= V_mV;
                              3'd3: v_sample3 <= V_mV;
                              3'd4: v_sample4 <= V_mV;
                              default: ;
                          endcase
                          sample_cnt <= sample_cnt + 3'd1;
                      end
                  end else begin
                      median_arr_packed <= {v_sample0, v_sample1, v_sample2, v_sample3, v_sample4};
                      median_pass       <= 2'd0;
                      median_busy       <= 1'b1;
                      sample_cnt        <= 3'd0;
                  end
              end
          end
          // 不在暂停态时，不清除任何状态，因为下次进入时会被复位
      end
  end
  
  // Rho 计算
  parameter CALC_MUL1        = 5'd1;
  parameter CALC_DIV10_MUL   = 5'd2;   // 乘法部分
  parameter CALC_DIV10_SHIFT = 5'd3;   // 移位部分
  parameter CALC_MUL2        = 5'd4;
  parameter CALC_DIV1000_MUL = 5'd5;
  parameter CALC_DIV1000_SHIFT=5'd6;
  parameter CALC_MUL3        = 5'd7;
  parameter CALC_DIV10000_MUL= 5'd8;
  parameter CALC_DIV10000_SHIFT=5'd9;
  parameter CALC_MUL4        = 5'd10;
  parameter CALC_DIV100_MUL  = 5'd11;
  parameter CALC_DIV100_SHIFT= 5'd12;
  // Rs 计算
  parameter CALC_RS_MUL1     = 5'd13;
  parameter CALC_RS_DIV100_MUL =5'd14;
  parameter CALC_RS_DIV100_SHIFT=5'd15;
  parameter CALC_RS_MUL2     = 5'd16;
  parameter CALC_RS_MUL3     = 5'd17;
  parameter CALC_RS_SHIFT_MUL= 5'd18;   // 乘 66
  parameter CALC_RS_SHIFT_SHIFT=5'd19;  // 右移 16
  parameter CALC_RS_DONE     = 5'd20;
  reg [47:0] calc_tmp;   // 48位中间寄存器，避免溢出
  //==================== 顺序状态机计算电阻率/方块电阻（彻底无除法器） ==========
  always @(posedge clk) begin
      if(!reset_n) begin
          calc_state <= CALC_IDLE;
          calc_tmp   <= 48'd0;
          rho        <= 32'd0;
          Rs         <= 32'd0;
      end else if (start_edge || x_trig_edge) begin
          calc_state <= CALC_IDLE;
      end else begin
          case(calc_state)
              CALC_IDLE: begin
                  if(calc_trigger)
                      calc_state <= CALC_MUL1;
              end
  
              // ------- Rho -------
              CALC_MUL1: begin
                  calc_tmp   <= hold_V_mV * RHO_FD;
                  calc_state <= CALC_DIV10_MUL;
              end
              CALC_DIV10_MUL: begin
                  calc_tmp   <= calc_tmp * 16'd6554;
                  calc_state <= CALC_DIV10_SHIFT;
              end
              CALC_DIV10_SHIFT: begin
                  calc_tmp   <= calc_tmp >> 16;
                  calc_state <= CALC_MUL2;
              end
  
              CALC_MUL2: begin
                  calc_tmp   <= calc_tmp * RHO_FW;
                  calc_state <= CALC_DIV1000_MUL;
              end
              CALC_DIV1000_MUL: begin
                  calc_tmp   <= calc_tmp * 16'd66;
                  calc_state <= CALC_DIV1000_SHIFT;
              end
              CALC_DIV1000_SHIFT: begin
                  calc_tmp   <= calc_tmp >> 16;
                  calc_state <= CALC_MUL3;
              end
  
              CALC_MUL3: begin
                  calc_tmp   <= calc_tmp * W_mm;
                  calc_state <= CALC_DIV10000_MUL;
              end
              CALC_DIV10000_MUL: begin
                  calc_tmp   <= calc_tmp * 17'd52429;
                  calc_state <= CALC_DIV10000_SHIFT;
              end
              CALC_DIV10000_SHIFT: begin
                  calc_tmp   <= calc_tmp >> 19;
                  calc_state <= CALC_MUL4;
              end
  
              CALC_MUL4: begin
                  calc_tmp   <= calc_tmp * RHO_FSP;
                  calc_state <= CALC_DIV100_MUL;
              end
              CALC_DIV100_MUL: begin
                  calc_tmp   <= calc_tmp * 16'd655;
                  calc_state <= CALC_DIV100_SHIFT;
              end
              CALC_DIV100_SHIFT: begin
                  calc_tmp   <= calc_tmp >> 16;
                  calc_state <= CALC_RS_MUL1;
              end
  
              // ------- Rs -------
              CALC_RS_MUL1: begin
                  rho        <= calc_tmp;
                  calc_tmp   <= hold_V_mV * RHO_FD;
                  calc_state <= CALC_RS_DIV100_MUL;
              end
              CALC_RS_DIV100_MUL: begin
                  calc_tmp   <= calc_tmp * 16'd655;
                  calc_state <= CALC_RS_DIV100_SHIFT;
              end
              CALC_RS_DIV100_SHIFT: begin
                  calc_tmp   <= calc_tmp >> 16;
                  calc_state <= CALC_RS_MUL2;
              end
  
              CALC_RS_MUL2: begin
                  calc_tmp   <= calc_tmp * RHO_FW;
                  calc_state <= CALC_RS_MUL3;
              end
              CALC_RS_MUL3: begin
                  calc_tmp   <= calc_tmp * RHO_FSP;
                  calc_state <= CALC_RS_SHIFT_MUL;
              end
              CALC_RS_SHIFT_MUL: begin
                  calc_tmp   <= calc_tmp * 16'd66;
                  calc_state <= CALC_RS_SHIFT_SHIFT;
              end
              CALC_RS_SHIFT_SHIFT: begin
                  calc_tmp   <= calc_tmp >> 16;
                  calc_state <= CALC_RS_DONE;
              end
              CALC_RS_DONE: begin
                  Rs <= calc_tmp;
                  // 根据 calc_slot 存入对应的锁存寄存器
                  case (calc_slot)
                      3'd0: begin rho_S <= rho; RS_S <= calc_tmp; end
                      3'd1: begin rho_1 <= rho; RS_1 <= calc_tmp; end
                      3'd2: begin rho_2 <= rho; RS_2 <= calc_tmp; end
                      3'd3: begin rho_3 <= rho; RS_3 <= calc_tmp; end
                      3'd4: begin rho_4 <= rho; RS_4 <= calc_tmp; end
                      default: ;
                  endcase
                  calc_state <= CALC_DONE;
              end
              CALC_DONE: begin
                  if(calc_trigger)
                      calc_state <= CALC_MUL1;
              end
              default: calc_state <= CALC_IDLE;
          endcase
      end
  end
  
  //==================== 新增：单次电阻率/方块电阻计算（使用锁存电压） ==========
  
  //==================== 新增：计算触发逻辑（内部边沿检测，可靠） ==========
  always @(posedge clk) begin
      if(!reset_n) begin
          calc_trigger <= 1'b0;
          calc_done    <= 1'b0;
          m2_calc_cnt  <= 3'd0;
          calc_slot    <= 3'd0;
          main_state_d <= S_IDLE;
      end else begin
          main_state_d <= main_state;
          calc_trigger <= 1'b0;
  
          // ---- 暂停状态入口清零 ----
          if ((main_state == S_MODE1_PAUSE || main_state == S_M2_PAUSE1 || main_state == S_M2_PAUSE2) &&
              !(main_state_d == S_MODE1_PAUSE || main_state_d == S_M2_PAUSE1 || main_state_d == S_M2_PAUSE2)) begin
              calc_done <= 1'b0;
              if (main_state == S_M2_PAUSE1)   // 第一次暂停，复位模式二计数器
                  m2_calc_cnt <= 3'd0;
          end
  
          // ---- 模式一触发 ----
          if (main_state == S_MODE1_BACK && main_state_d != S_MODE1_BACK) begin
              if (voltage_latched && !calc_done) begin
                  calc_trigger <= 1'b1;
                  calc_done    <= 1'b1;
                  calc_slot    <= 3'd0;        // 0 表示模式一
              end
          end
  
          // ---- 模式二触发（4次） ----
          else if ((main_state == S_M2_DIR1 || main_state == S_M2_DIR3) &&
                   !(main_state_d == S_M2_DIR1 || main_state_d == S_M2_DIR3)) begin
              if (voltage_latched && (m2_calc_cnt < 3'd4)) begin
                  calc_trigger <= 1'b1;
                  m2_calc_cnt  <= m2_calc_cnt + 3'd1;
                  // 根据当前 m2_calc_cnt 决定 calc_slot (1~4)
                  case (m2_calc_cnt)
                      3'd0: calc_slot <= 3'd1;
                      3'd1: calc_slot <= 3'd2;
                      3'd2: calc_slot <= 3'd3;
                      3'd3: calc_slot <= 3'd4;
                      default: calc_slot <= 3'd0;
                  endcase
              end
          end
  
          // 新测量启动，复位
          if (start_edge || x_trig_edge) begin
              calc_done    <= 1'b0;
              m2_calc_cnt  <= 3'd0;
              calc_slot    <= 3'd0;
          end
      end
  end
  
  //==================== 8. 串口数据打包控制 ==========
  // 电压数位拆分
  
  // 原代码（组合逻辑）
  // 删除原来的 reg [3:0] v0r,v1r,v2r,v3r,v4r; 及相关的 always 块
  // 新增中间寄存器
  // 2026-10-15 cleanup: the five quotient/remainder latches (hold_V_mV_mod10,
  // hold_V_mV_div10/100/1000/10000) were deleted -- they were written with non-blocking
  // assignments and never read (the BCD digits below recompute the divisions inline),
  // and synthesis reported them as "Unused sequential element" in every run.
  reg [3:0]  v0r, v1r, v2r, v3r, v4r;
  
  // 仅在锁存电压更新时做一次十进制拆分，避免每拍推大除法器
  always @(posedge clk) begin
      if(!reset_n) begin
          v0r <= 4'd0;
          v1r <= 4'd0;
          v2r <= 4'd0;
          v3r <= 4'd0;
          v4r <= 4'd0;
      end else if(voltage_latched) begin
          v0r <= hold_V_mV % 10;
          v1r <= (hold_V_mV / 10) % 10;
          v2r <= (hold_V_mV / 100) % 10;
          v3r <= (hold_V_mV / 1000) % 10;
          v4r <= (hold_V_mV / 10000) % 10;
      end
  end
  
  // 原有第三级（保持不变）
  always @(posedge clk) begin
      v0 <= v0r;
      v1 <= v1r;
      v2 <= v2r;
      v3 <= v3r;
      v4 <= v4r;
  end

endmodule
