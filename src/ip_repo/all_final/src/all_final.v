module ALL_Final(
input wire RVS,
input wire SDO0,
input wire S_AXI_ACLK,
input wire S_AXI_ARESETN,
input wire sensor,
output wire SDI,
output wire SCLK,
output wire CS,
output wire RST,
output wire uart_tx,
output wire step_pulse,
output wire dir,
output wire ena,
output wire err_flag,
output wire cycle_done,
input wire x_trig_in,
output wire x_pul_out,
output wire x_dir_out,
output wire r_pul_out,
output wire r_dir_out,
output wire r_ena_out,
input wire start,
input wire r_sensor,
output wire led_meas_cnt0,

// Custom relay current-source PCB control interface.
output wire range0_ctrl,
output wire range1_ctrl,
output wire range2_ctrl,
output wire range3_ctrl,
output wire pol_i_ctrl,
output wire pol_v_ctrl,
output wire current_en,
output wire dac_sclk,
output wire dac_din,
output wire dac_sync_n,

// AXI4-Lite slave interface. The AXI clock/reset also drive the legacy PL logic.
input wire [31:0] S_AXI_AWADDR,
input wire        S_AXI_AWVALID,
output wire       S_AXI_AWREADY,
input wire [31:0] S_AXI_WDATA,
input wire [3:0]  S_AXI_WSTRB,
input wire        S_AXI_WVALID,
output wire       S_AXI_WREADY,
output wire [1:0] S_AXI_BRESP,
output wire       S_AXI_BVALID,
input wire        S_AXI_BREADY,
input wire [31:0] S_AXI_ARADDR,
input wire        S_AXI_ARVALID,
output wire       S_AXI_ARREADY,
output wire [31:0] S_AXI_RDATA,
output wire [1:0] S_AXI_RRESP,
output wire       S_AXI_RVALID,
input wire        S_AXI_RREADY
);

  // Keep the original implementation body clock/reset names unchanged.
  wire clk;
  wire reset_n;
  assign clk     = S_AXI_ACLK;
  assign reset_n = S_AXI_ARESETN;

  //----Code starts here: integrated by Robei-----
  //----Code starts here: integrated by Robei-----
  //==================== 参数定义（分模块重命名避免冲突） ====================
  // ---------- ALL(ADC SPI采集)模块参数 ----------
  

  // Power-up delay before the ADS8681 configuration frame is sent.  This replaces
  // the pair of hard-coded literals 32'd1000000 / 32'd2000000 (whose mid-point had
  // no observable effect).  Default value is unchanged: 2,000,000 cycles = 40 ms at
  // 50 MHz.  A testbench can shrink it to exercise the ADC SPI path in a short run.
  
  
  parameter STATS_WINDOW_CYCLES = 1000000;   // 20 ms at 50 MHz
  
  
  
  // ---------- ADS8681 采集链可调时序（其余协议常量已随模块搬到
  // hw/rtl/adc/ads8681_capture.v，在那里是 localparam、不可覆盖） ----------
  parameter integer RVS_TIMEOUT_CYCLES = 200; // 4 us at 50 MHz
  parameter [31:0] ADC_PWRUP_DELAY_CYCLES = 32'd2000000; // 40 ms at 50 MHz

  // ---------- Update定时触发模块参数 ----------
  parameter MCNT_DELAY = 25_000_000 - 1;
  
  // ---------- All_rho计算模块参数 ----------
  parameter RHO_FD     = 4532;
  parameter RHO_FW     = 1050;
  parameter RHO_FSP    = 12'd1001;
  parameter RHO_DIV_1K = 12'd1000;
  parameter W_mm       = 645;
  
  // ---------- 串口数据打包控制模块参数 ----------
  parameter WAIT_CYCLE  = 58000;
  parameter TOTAL_CHAR  = 785;
  parameter sel_sample  = 1;
  parameter sel_doping  = 1;
  
  parameter UART_IDLE   = 0;
  parameter UART_SEND   = 1;
  parameter UART_WAIT   = 2;
  parameter UART_NEXT   = 3;
  
  // ---------- UART底层发送模块参数 ----------
  parameter BAUD       = 9600;
  parameter CLOCK_FREQ = 50_000_000;
  parameter MCNT_BAUD  = CLOCK_FREQ / BAUD - 1;
  parameter MCNT_BIT   = 9;
  
  //==================== Z轴电机参数 ====================
  parameter CLK_FREQ       = 50_000_000;
  parameter integer ANALOG_SETTLE_CYCLES = CLK_FREQ / 50; // 20 ms relay/path settling
  parameter integer DAC_HALF_CYCLES      = 10;            // 2.5 MHz DAC SCLK at 50 MHz
  parameter PULSE_HALF     = 500;
  parameter SLOW_DIV       = 6;
  parameter PAUSE_CLKS     = 250_000_000;  // 下压保持5s
  parameter STEPS_FORWARD  = 7700;        // 全行程下压总步数
  parameter SEN_DELAY_CNT  = 50_000;       // 传感器消抖计数
  parameter BACK_MAX_STEP  = 20000;        // 上电回零最大后退步数
  parameter READY_WAIT_CNT = 10000;        // 原点稳定延时
  parameter BACK_FAIL_WAIT = 500_000;      // 返程原点超时计数
  parameter DIR_SETUP_CNT  = 100;          // 换向建立延时
  
  //==================== X旋转平台参数 ====================
  parameter x_PUL_NUM      = 3000;         // 旋转90°脉冲数
  parameter x_SYS_FREQ     = 50000000;

  // R axis radial stepper
  parameter R_PULSES_PER_REV = 1600;
  parameter R_STEPS_PER_MM   = 800;
  parameter R_MAX_STEPS      = 40000;
  parameter R_PULSE_HALF     = 500;
  parameter R_SLOW_DIV       = 6;
  parameter R_PULSE_PERIOD   = 2 * R_PULSE_HALF;
  parameter R_DIR_SETUP_CYCLES = 5000;
  parameter R_HOME_DEBOUNCE_CYCLES = 50000;
  parameter R_TIMEOUT_CYCLES = 750_000_000;

  // Measured radial driver polarity: 1 extends, 0 retracts.
  localparam R_CMD_MOVE_TO   = 32'd2;
  localparam R_CMD_MOVE_REL  = 32'd3;



  // Z axis atomic motion and measurement window
  // Hard mechanical travel limit in steps from HOME.  The Z controller rejects
  // every target above this value and also clamps the mover at this position,
  // so a wrong software target can never drive the stage past the safe travel.
  // Do NOT tie this back to the legacy STEPS_FORWARD full-stroke constant.
  // 2026-10-16: raised 8000 -> 10000 (operator decision; measured hand-press
// contact on the 645 um wafer is ~7800 steps).  MUST stay equal to
// Z_HARD_LIMIT_STEPS in sw/four_probe_sw/final_four_probe_system.py.
parameter Z_MAX_STEPS = 10000;

  // The PS (Notebook 16) is the only Z motion planner in the final system.
  // The legacy automatic sequencer is NOT covered by the Z driver interlock and
  // can issue a full-stroke STEPS_FORWARD down press from the external start or
  // x_trig pins, so it is disabled by construction.
  parameter LEGACY_AUTO_SEQUENCER_ENABLE = 1'b0;
  parameter Z_DIR_SETUP_CYCLES = 5000;
  parameter Z_TIMEOUT_CYCLES = 750_000_000;

  //--------------------------------------------------------------------------
  // Legacy interface-compatibility parameters (2026-10-13).
  //
  // These 47 knobs are no longer USED here: the ADC SPI / configuration FSM and
  // the rho-Rs calculator that consumed them were extracted into
  // hw/rtl/adc/ads8681_capture.v and hw/rtl/measurement/meas_chain.v, and their
  // state encodings and device registers became localparams inside those modules.
  //
  // They are kept declared (and declared as parameters, not localparams) ONLY
  // because the packaged IP advertises them and the Block Design still passes an
  // override for every parameter the IP advertises.  Removing them makes synthesis
  // fail with "parameter 'SPI_IDLE' used as named parameter override, does not exist".
  //
  // This is rule 2 read correctly: a parameter overridden by an EXTERNAL CONSUMER
  // must stay declared in the parent.  check_tb_coupling.py only scans testbenches,
  // which is why the BD was missed -- see WORKLOG P53/P54.
  // Replacing these with a re-packaged IP whose parameter list matches the RTL is
  // the clean fix, and is tracked as a follow-up.
  //
  // NOTE: values below are copied verbatim from the frozen pre-split revision.
  //--------------------------------------------------------------------------
  parameter ALARM_H_TH_REG   = 16'h0024;
  parameter ALARM_L_TH_REG   = 16'h0028;
  parameter ALARM_REG        = 16'h0020;
  parameter CALC_DIV10000_MUL= 5'd8;
  parameter CALC_DIV10000_SHIFT=5'd9;
  parameter CALC_DIV1000_MUL = 5'd5;
  parameter CALC_DIV1000_SHIFT=5'd6;
  parameter CALC_DIV100_MUL  = 5'd11;
  parameter CALC_DIV100_SHIFT= 5'd12;
  parameter CALC_DIV10_MUL   = 5'd2;
  parameter CALC_DIV10_SHIFT = 5'd3;
  parameter CALC_MUL1        = 5'd1;
  parameter CALC_MUL2        = 5'd4;
  parameter CALC_MUL3        = 5'd7;
  parameter CALC_MUL4        = 5'd10;
  parameter CALC_RS_DIV100_MUL =5'd14;
  parameter CALC_RS_DIV100_SHIFT=5'd15;
  parameter CALC_RS_DONE     = 5'd20;
  parameter CALC_RS_MUL1     = 5'd13;
  parameter CALC_RS_MUL2     = 5'd16;
  parameter CALC_RS_MUL3     = 5'd17;
  parameter CALC_RS_SHIFT_MUL= 5'd18;
  parameter CALC_RS_SHIFT_SHIFT=5'd19;
  parameter CFG_Delay        = 4'd1;
  parameter CFG_Init         = 4'd2;
  parameter CFG_READ_DATA    = 4'd4;
  parameter CFG_READ_DONE    = 4'd5;
  parameter CFG_Reset        = 4'd0;
  parameter CFG_WAIT         = 4'd3;
  parameter CPHA             = 1'b0;
  parameter CPOL             = 1'b0;
  parameter DATAOUT_CTL_REG  = 16'h0010;
  parameter DEVICE_ID_REG    = 16'h0000;
  parameter MEAS_DELAY_50MS = 25_000_00 - 1;
  parameter RANGE_5120MV     = 16'h0003;
  parameter RANGE_SEL_REG    = 16'h0014;
  parameter RST_PWRCTL_REG   = 16'h0004;
  parameter SDI_CTL_REG      = 16'h0008;
  parameter SDO_CTL_REG      = 16'h000C;
  parameter SPI_DATA_WIDTH   = 32;
  parameter SPI_IDLE         = 2'd0;
  parameter SPI_START_TX     = 2'd1;
  parameter SPI_S_FINISH     = 2'd3;
  parameter SPI_S_IDLE       = 2'd0;
  parameter SPI_S_PREPARE    = 2'd1;
  parameter SPI_S_TRANSFER   = 2'd2;
  parameter SPI_WAIT_DONE    = 2'd2;

  // The Z direction / state / error encodings moved with the controller into
  // hw/rtl/motion/axis_z.v.  Only the Z command codes that the top-level refusal
  // predicates still compare against stay here.
  localparam Z_CMD_HOME            = 32'd1;
  localparam Z_CMD_MOVE_TO         = 32'd2;
  localparam Z_CMD_MOVE_TO_MEASURE = 32'd3;
  localparam Z_CMD_MOVE_REL        = 32'd4;
  localparam Z_CMD_RETURN_HOME_SAFE = 32'd6;


  localparam MEAS_STATE_IDLE   = 2'd0;
  localparam MEAS_STATE_ACTIVE = 2'd1;
  localparam MEAS_STATE_DONE   = 2'd2;
  localparam MEAS_STATE_ERROR  = 2'd3;

  localparam MEAS_ERR_NONE     = 3'd0;
  localparam MEAS_ERR_BUSY     = 3'd1;
  localparam MEAS_ERR_CONFLICT = 3'd2;
  localparam MEAS_ERR_TIMEOUT  = 3'd3;
  parameter x_PUL_FREQ     = 1000;         // 旋转脉冲频率
  parameter x_HALF_PERIOD  = x_SYS_FREQ / x_PUL_FREQ / 2;
  parameter x_DEBOUNCE_CNT = x_SYS_FREQ / 100; // 10ms消抖
  
  //==================== 模式二专用参数 ====================
  parameter HALF_LIFT_STEP = 10000;         // 半程抬升/下压步数
  
  //==================== 主状态机状态定义 ====================
  parameter S_IDLE         = 5'd0;   // 空闲待机
  parameter S_PWR_HOME     = 5'd1;   // 上电自动回原点
  parameter S_READY        = 5'd2;   // 原点就绪稳定
  parameter S_MODE1_GO     = 5'd3;   // 模式一：下压
  parameter S_MODE1_PAUSE  = 5'd4;   // 模式一：保持测量
  parameter S_MODE1_DIR    = 5'd5;   // 模式一：换向延时
  parameter S_MODE1_BACK   = 5'd6;   // 模式一：上升回原点
  parameter S_M2_GO1       = 5'd7;   // 模式二：第一次全下压
  parameter S_M2_PAUSE1    = 5'd8;   // 模式二：第一次保持
  parameter S_M2_DIR1      = 5'd9;   // 模式二：抬升方向换向延时
  parameter S_M2_LIFT_HALF = 5'd10;  // 模式二：半程抬升5000步
  parameter S_M2_WAIT_ROT  = 5'd11;  // 模式二：启动旋转并等待旋转完成
  parameter S_M2_DIR2      = 5'd12;  // 模式二：下压方向换向延时
  parameter S_M2_GO2       = 5'd13;  // 模式二：半程下压5000步
  parameter S_M2_PAUSE2    = 5'd14;  // 模式二：循环中保持测量
  parameter S_M2_DIR3      = 5'd15;  // 模式二：回原点方向换向延时
  parameter S_M2_BACK      = 5'd16;  // 模式二：全行程上升回原点
  parameter S_ERR          = 5'd17;  // 故障锁存态
  parameter S_M2_FINAL_ROT = 5'd18;  // 模式二：回原点后末次旋转等待
  
  //==================== 内部信号声明 ====================
  // 脉冲底层
  parameter PULSE_PERIOD = 10'd2 * PULSE_HALF;
  //==================== 内部信号声明 ====================
  // ---------- ADC SPI模块内部互联 ----------
  
  
  
  // ---------- 电压转换模块内部信号 ----------
  
  // ---------- 定时触发模块内部信号 ----------
  reg [29:0] delay_cnt_update;
  wire        send_go_update;
  
  // ---------- 电阻率/方块电阻计算模块内部信号 ----------
  wire [31:0] rho;
  wire [31:0] Rs;
  wire [31:0] rho_S, rho_1, rho_2, rho_3, rho_4;
  wire [31:0] RS_S, RS_1, RS_2, RS_3, RS_4;
  
  // ---------- 串口数据打包模块内部信号 ----------
  wire [3:0] v0,v1,v2,v3,v4;
  
  reg [3:0] di0=0,di1=5,di2=0,di3=0;
  reg [3:0] t0=5,t1=4,t2=6,t3=0;
  reg [3:0] p0=1,p1=0;
  reg [3:0] c0=0,c1=1,c2=0;
  
  reg [3:0] r0,r1,r2,r3,r4,r5,r6,r7,r8,r9;
  reg [3:0] rs0,rs1,rs2,rs3,rs4,rs5,rs6,rs7,rs8,rs9;
  reg [3:0] n0=0,n1=0,n2=0,n3=0,n4=0;
  
  //==================== 组合逻辑赋值 ====================
  assign uart_tx     = 1'b1;   // legacy Bluetooth UART chain removed 2026-10-15: pin + constraint kept, driven idle (mark)
  
  
  
  // 运动控制与计数
  reg [4:0] main_state;
  reg [17:0] step_cnt;        // 全行程步数计数器
  reg [17:0] half_step_cnt;   // 模式二半程专用计数器
  reg [29:0] pause_cnt;
  reg [9:0] dir_setup_cnt;
  reg [17:0] back_limit_cnt;
  reg [18:0] back_err_cnt;
  reg [13:0] ready_wait_cnt;
  reg [1:0]  m2_cycle_cnt;    // 模式二半程循环次数计数器（0~2，共3次循环）
  
  reg dir_r, ena_r;
  reg sen_capture;
  reg err_latch;
  reg cycle_done_r;
  reg rot_start_flag;         // 旋转启动标记
  reg rot_busy_seen;          // 已检测到旋转台忙信号拉高
  
  // 由 motion_sync 例化驱动的输出（原为内部信号）
  wire pulse_tick;
  wire sen_stable;
  wire slow_step_en;
  wire start_edge;
  wire x_trig_edge;
  
  // X旋转台内部
  wire x_busy;
  reg x_start_internal;
  reg [31:0] x_target_reg;
  wire [31:0] x_position;
  wire        x_done_reg;
  // R axis registers
  reg [31:0] r_command_reg;
  reg [31:0] r_target_reg;

  // R 轴输出（由 hw/rtl/motion/axis_r.v 例化驱动）
  wire        r_sensor_stable;
  wire [2:0]  r_state;
  wire        r_done_reg;
  wire        r_fault;
  wire        r_homed;
  wire [31:0] r_position;
  wire [3:0]  r_error_code;
  wire        r_pulse_tick;
  wire        r_busy;        // driven by the u_axis_r instance

  // Z axis atomic registers.  The AXI-written registers stay here (rule 1); the
  // controller state moved into hw/rtl/motion/axis_z.v and is read back as wires
  // driven by the u_axis_z instance.
  reg [31:0] z_command_reg;
  reg [31:0] z_target_reg;
  wire [31:0] z_position;
  wire [3:0]  z_error_code;
  wire        z_dir_reg;
  wire        z_done_reg;
  wire        z_fault;
  wire        z_homed;
  reg        z_driver_armed;
  reg [31:0] z_step_interval_cycles;
  reg        z_decel_enable;
  reg        z_decel_measure_enable;
  reg        z_decel_return_enable;
  reg        z_decel_all_enable;
  reg [31:0] z_decel_window_steps;
  reg [31:0] z_decel_seg_steps;
  reg [4:0]  z_decel_lut_index;
  reg [31:0] z_decel_period_lut[0:15];
  integer    z_decel_lut_i;
  wire z_direct_busy;   // driven by the u_axis_z instance
  wire [31:0] z_home_step_cnt;   // AXI read-back of the Z homing step counter

  // Unified measurement window registers
  reg [31:0] meas_hold_cycles_reg;
  reg [31:0] meas_hold_cnt;
  reg [31:0] meas_point_index_reg;
  reg [1:0]  meas_state;
  reg [2:0]  meas_error_code;
  reg        meas_legacy_active_d;
  reg        meas_source_legacy;
  wire       z_measure_start_pulse;
  // Lateral-motion safety height + sticky "a motion command was refused" flag
  // (2026-10-11).  The flag is driven by exactly one always block (section 12).
  reg [31:0] z_safe_travel_reg;
  wire       motion_refused_sticky;

  wire legacy_measure_active = (main_state == S_MODE1_PAUSE) ||
                               (main_state == S_M2_PAUSE1) ||
                               (main_state == S_M2_PAUSE2);
  wire meas_active = (meas_state == MEAS_STATE_ACTIVE);

                          
  // 模式二测量计数器（0~8）
  reg [3:0] meas_cnt;
  
  reg [15:0] hold_V_mV;              // 锁存电压
  reg        voltage_latched;        // 电压已锁存标志
  reg [24:0] meas_delay_cnt;        // 500ms 计时器
  reg [4:0]  prev_main_state;       // 上一状态，用于边沿检测
  reg        calc_trigger;           // 计算触发脉冲
  reg        calc_done;              // 计算完成锁存
  reg [2:0]  m2_calc_cnt;            // 模式二已触发次数
  wire [2:0]  calc_slot;             // 0: 模式一，1~4: 模式二四次结果
  
  reg [4:0] main_state_d;   // 延迟一拍 main_state，用于生成回原点脉冲
  
  // 用于采集5个有效电压值
  reg [15:0] v_sample0, v_sample1, v_sample2, v_sample3, v_sample4;
  wire [79:0] median_arr_packed;
  reg [1:0]  median_pass;
  reg        median_busy;
  reg [2:0]  sample_cnt;          // 0~5，记录已采集的有效值个数
  reg        sampling_active;     // 500ms等待结束后置1，进入采集阶段
  
  assign led_meas_cnt0 = meas_cnt[0];

  //==================== AXI-Lite control/status interface ====================
  // 0x00 CONTROL: bit0=start mode-1 pulse, bit1=start mode-2 pulse,
  //               bit2=clear latched fault when the state machine is in S_ERR,
  //               bit3=start the X rotation platform directly while in S_IDLE.
  // 0x04 STATUS : main_state[4:0], fault, cycle_done, x_busy and outputs.
  // 0x08 INPUTS : RVS, SDO0, sensor and external trigger levels.
  // 0x0C OUTPUTS: SPI/motion/UART-visible PL output levels.
// 0x10 VERSION: fixed interface signature 0x414C5835 ("ALX5").
  //  0x140 WATCHDOG_COUNT (R), 0x144 STATS_ACK_SEQ (W), 0x148 Z_SAFE_TRAVEL (R/W);
  //  STATUS[19] = a motion command was refused since the last CLEAR_FAULTS.
  // 0x14 MEAS_COUNT, 0x18 MAIN_STATE, 0x1C ADC_RAW, 0x20 RHO, 0x24 RS.
  localparam [11:0] AXI_REG_CONTROL   = 8'h00;
  localparam [11:0] AXI_REG_STATUS    = 8'h04;
  localparam [11:0] AXI_REG_INPUTS    = 8'h08;
  localparam [11:0] AXI_REG_OUTPUTS   = 8'h0C;
  localparam [11:0] AXI_REG_VERSION   = 8'h10;
  localparam [11:0] AXI_REG_MEAS_CNT  = 8'h14;
  localparam [11:0] AXI_REG_MAIN_STATE= 8'h18;
  localparam [11:0] AXI_REG_ADC_RAW   = 8'h1C;
  localparam [11:0] AXI_REG_RHO       = 8'h20;
  localparam [11:0] AXI_REG_RS        = 8'h24;
  localparam [11:0] AXI_REG_R_CONTROL = 8'h28;
  localparam [11:0] AXI_REG_R_COMMAND = 8'h2C;
  localparam [11:0] AXI_REG_R_TARGET  = 8'h30;
  localparam [11:0] AXI_REG_R_STATUS  = 8'h34;
  localparam [11:0] AXI_REG_R_POSITION= 8'h38;
  localparam [11:0] AXI_REG_R_ERROR   = 8'h3C;
  localparam [11:0] AXI_REG_Z_CONTROL = 8'h40;
  localparam [11:0] AXI_REG_Z_COMMAND = 8'h44;
  localparam [11:0] AXI_REG_Z_TARGET  = 8'h48;
  localparam [11:0] AXI_REG_Z_STATUS  = 8'h4C;
  localparam [11:0] AXI_REG_Z_POSITION= 8'h50;
  localparam [11:0] AXI_REG_Z_ERROR   = 8'h54;
  localparam [11:0] AXI_REG_M_CONTROL = 8'h58;
  localparam [11:0] AXI_REG_M_STATUS  = 8'h5C;
  localparam [11:0] AXI_REG_M_POINT   = 8'h60;
  localparam [11:0] AXI_REG_M_HOLD    = 8'h64;
  localparam [11:0] AXI_REG_M_ERROR   = 8'h68;
  localparam [11:0] AXI_REG_X_TARGET  = 8'h6C;
  localparam [11:0] AXI_REG_X_STATUS  = 8'h70;
  localparam [11:0] AXI_REG_X_POSITION= 8'h74;
  localparam [11:0] AXI_REG_X_CONTROL = 8'h78;
  // Banked 20 ms validity statistics.  Bank index = {reverse, range[1:0]}.
  localparam [11:0] AXI_REG_STATS_SUM_LOW      = 12'h100;
  localparam [11:0] AXI_REG_STATS_SUM_HIGH     = 12'h104;
  localparam [11:0] AXI_REG_STATS_VALID_COUNT  = 12'h108;
  localparam [11:0] AXI_REG_STATS_SUM_SQ_LOW   = 12'h10C;
  localparam [11:0] AXI_REG_STATS_SUM_SQ_HIGH  = 12'h110;
  localparam [11:0] AXI_REG_STATS_RX_COUNT     = 12'h114;
  localparam [11:0] AXI_REG_STATS_MIN_CODE     = 12'h118;
  localparam [11:0] AXI_REG_STATS_MAX_CODE     = 12'h11C;
  localparam [11:0] AXI_REG_STATS_SEQ          = 12'h120;
  localparam [11:0] AXI_REG_STATS_FLAGS        = 12'h124;
  localparam [11:0] AXI_REG_STATS_BANK_SELECT  = 12'h128;
  localparam [11:0] AXI_REG_STATS_CENTER_CODE  = 12'h12C;
  localparam [11:0] AXI_REG_STATS_MAG_MIN      = 12'h130;
  localparam [11:0] AXI_REG_STATS_MAG_MAX      = 12'h134;
  localparam [11:0] AXI_REG_STATS_CONTROL      = 12'h138;
  localparam [11:0] AXI_REG_STATS_STATUS       = 12'h13C;
  localparam integer STATS_COUNT_BITS = (STATS_WINDOW_CYCLES <= 1) ? 1 : $clog2(STATS_WINDOW_CYCLES);
  localparam [11:0] AXI_REG_Z_STEP_INTERVAL = 8'h7C;
  localparam [11:0] AXI_REG_Z_DECEL_CONTROL = 8'hA8;
  localparam [11:0] AXI_REG_Z_DECEL_WINDOW = 8'hAC;
  localparam [11:0] AXI_REG_Z_DECEL_SEG_STEPS = 8'hB0;
  localparam [11:0] AXI_REG_Z_DECEL_LUT_INDEX = 8'hB4;
  localparam [11:0] AXI_REG_Z_DECEL_LUT_DATA = 8'hB8;
  // Read-only diagnostics added 2026-10-09.
  localparam [11:0] AXI_REG_Z_HOME_STEPS     = 8'hF0;
  localparam [11:0] AXI_REG_Z_TIMEOUT_CYCLES = 8'hF4;
  localparam [11:0] AXI_REG_R_TIMEOUT_CYCLES = 8'hF8;
  localparam [11:0] AXI_REG_HEARTBEAT        = 8'hFC;
  localparam [11:0] AXI_REG_WATCHDOG_COUNT = 12'h140;
  localparam [11:0] AXI_REG_STATS_ACK_SEQ  = 12'h144;
  // PS-writable lateral-motion safety height (2026-10-11).  Lateral (R / X)
  // commands are refused while z_homed == 0 or z_position > this value, so an
  // unconfigured PL refuses them (power-on default 0 = fail-closed).
  localparam [11:0] AXI_REG_Z_SAFE_TRAVEL = 12'h148;

  // PL measurement arithmetic (meas_calc).  CALC_COUNT_MAX / CALC_COEFF_MAX are the
  // width budget of that module (see hw/rtl/measurement/meas_calc.v): COUNT_MAX
  // bounds |d| <= 2^33 and COEFF_MAX bounds q*K_q to 62 bits.  Raising either
  // requires re-checking those bounds, not just editing the number.
  //
  // WHY VERSION IS *NOT* BUMPED WITH THESE REGISTERS (2026-10-15):
  //   the documented pairing protocol is a VERSION bump, but the equivalence
  //   testbench compares every DUT output -- including S_AXI_RDATA bits 63:32 --
  //   on every clock (hw/tb/tb_all_final_equiv.sv:197-210,286-307) and it reads
  //   0x10 itself (:744).  scripts/check_baseline.ps1:257-258 additionally asserts
  //   hw/tb/all_final_ref.v is byte-identical to this file apart from the module
  //   rename, and pins its sha256 (:242).  So the bump is a coordinated re-freeze
  //   (reference + two testbenches + two pins), i.e. its own deliberate phase.
  //   Until then the pairing is detected the fail-closed way instead: the PS writes
  //   CALC_COEFF_K and requires an EQUAL read-back (a missing register reads 0), so
  //   a new PS still refuses to run against a bitstream without these registers.
  localparam [11:0] AXI_REG_CALC_CONTROL  = 12'h14C;
  localparam [11:0] AXI_REG_CALC_STATUS   = 12'h150;
  localparam [11:0] AXI_REG_CALC_RHO_LOW  = 12'h154;
  localparam [11:0] AXI_REG_CALC_RHO_HIGH = 12'h158;
  localparam [11:0] AXI_REG_CALC_FLAGS    = 12'h15C;
  localparam [11:0] AXI_REG_CALC_COEFF_K  = 12'h160;
  localparam [11:0] AXI_REG_CALC_COEFF_RS = 12'h164;
  localparam [11:0] AXI_REG_CALC_RS_LOW   = 12'h168;
  localparam [11:0] AXI_REG_CALC_RS_HIGH  = 12'h16C;
  localparam [11:0] AXI_REG_CALC_MIN_COUNT = 12'h170;
  localparam [11:0] AXI_REG_CALC_MAX_SPAN  = 12'h174;
  localparam [31:0] CALC_COUNT_MAX = 32'd65536;      // == COUNT_MAX in meas_calc
  localparam [31:0] CALC_COEFF_MAX = 32'd268_435_455; // == COEFF_MAX in meas_calc
  localparam [31:0] WATCHDOG_CYCLES = 32'd50_000_000;   // 1 s at 50 MHz

  // Custom analog-frontend registers, kept above the legacy map.
  localparam [11:0] AXI_REG_ANALOG_CONTROL      = 8'hD0;
  localparam [11:0] AXI_REG_ANALOG_TEST_CONTROL = 8'hD4;
  localparam [11:0] AXI_REG_DAC_CODE            = 8'hD8;
  localparam [11:0] AXI_REG_DAC_CONTROL         = 8'hDC;
  localparam [11:0] AXI_REG_DAC_STATUS          = 8'hE0;
  localparam [11:0] AXI_REG_DAC_SEQ             = 8'hE4;
  localparam [11:0] AXI_REG_ANALOG_SEQ          = 8'hE8;
  localparam [11:0] AXI_REG_ADC_CFG_SEQ         = 8'hEC;

  // The analog front-end state encodings moved with the sequencer into
  // hw/rtl/analog/analog_seq.v.


  reg axi_aw_pending;
  reg axi_w_pending;
  reg [31:0] axi_awaddr_reg;
  reg [31:0] axi_wdata_reg;
  reg [3:0]  axi_wstrb_reg;
  reg axi_bvalid_reg;
  reg [1:0] axi_bresp_reg;
  reg axi_rvalid_reg;
  reg [31:0] axi_rdata_reg;
  reg [1:0] axi_rresp_reg;
  reg axi_start_pulse;
  reg axi_x_trig_pulse;
  reg axi_x_start_pulse;
  reg axi_x_var_start_pulse;
  reg axi_clear_error_pulse;
  reg axi_r_start_pulse;
  reg axi_r_stop_pulse;
  reg axi_r_clear_pulse;
  reg axi_z_start_pulse;
  reg axi_z_stop_pulse;
  reg axi_z_clear_pulse;
  reg axi_m_start_pulse;
  reg axi_m_abort_pulse;
  reg axi_m_clear_pulse;
  reg        axi_stats_clear_pulse;
  reg        axi_stats_arm_pulse;
  reg        axi_stats_ack_pulse;
  reg        axi_stats_disarm_pulse;
  reg        axi_stats_clear_all_pulse;
  reg [2:0]  stats_bank_select;
  // ACK_SEQ protocol: the PS writes the SEQ it consumed to 0x144, then ACKs.
  reg [31:0] stats_ack_seq_value;
  // stats_ack_seq_value/stats_ack_seq_set are driven by the AXI write
  // block; stats_ack_seq_pending is driven by the statistics block.
  // Keeping one driver per register avoids a multiply-driven net.
  reg        stats_ack_seq_set;
  reg [16:0] stats_center_code[0:7];
  reg [16:0] stats_mag_min[0:7];
  reg [16:0] stats_mag_max[0:7];
  // Driven by the extracted stats_window instance.  The ten per-bank snapshot arrays
  // live inside that module now; only the slice selected by stats_bank_select comes
  // out, because that is all the AXI readback ever looks at (rule 4).
  wire [2:0]  stats_active_bank;
  wire        stats_window_enable;
  wire        stats_window_busy;
  wire        stats_ack_seq_pending;
  wire [63:0] stats_sum_snapshot_sel;
  wire [63:0] stats_sum_sq_snapshot_sel;
  wire [31:0] stats_valid_count_snapshot_sel;
  wire [31:0] stats_rx_count_snapshot_sel;
  wire [16:0] stats_min_snapshot_sel;
  wire [16:0] stats_max_snapshot_sel;
  wire [31:0] stats_seq_sel;
  wire        stats_ready_sel;
  wire        stats_empty_sel;
  wire        stats_overflow_sel;
  integer    stats_config_i;

  // ---- PL measurement arithmetic (meas_calc, 2026-10-15) ----------------------
  // rho = (mean_code - center_code) * K, computed in PL.  The snapshot inputs are
  // the stats_*_sel slice that stats_window already exports for stats_bank_select,
  // so the module needs no array ports (rule 4 in hw/rtl/README.md) and shares no
  // logic with the dead legacy meas_chain rho pipeline.
  reg         mcalc_start_pulse;
  reg         mcalc_clear_pulse;
  reg  [31:0] mcalc_coeff_k_reg;
  wire        mcalc_busy;
  wire        mcalc_done;
  wire        mcalc_result_valid;
  wire [63:0] mcalc_rho_q;
  wire        mcalc_flag_zero_count;
  wire        mcalc_flag_count_over_max;
  wire        mcalc_flag_sum_overflow;
  wire        mcalc_flag_coeff_invalid;
  wire        mcalc_flag_negative;
  wire        mcalc_pair_valid;
  wire        mcalc_flag_pair_missing;
  wire [63:0] mcalc_rs_q;
  reg  [31:0] mcalc_coeff_rs_reg;
  // Phase C quality limits (0 = limit disabled) and the resulting flags.
  reg  [31:0] mcalc_min_count_reg;
  reg  [16:0] mcalc_max_span_reg;
  wire        mcalc_quality_ok;
  wire        mcalc_flag_quality_low_count;
  wire        mcalc_flag_quality_wide_span;
  // CALC_CONTROL.AVERAGE_PAIR is a LEVEL bit, not a pulse: it selects pair mode for
  // the following computes (bits 0/1 above remain one-shot pulses).
  reg         mcalc_pair_enable_reg;

  // Analog-frontend state and DAC serializer.
  reg        axi_analog_start_pulse;
  reg        axi_adc_reinit_pulse;
  // System reset / watchdog (2026-10-09).  These are written only inside the
  // AXI register always block so every signal has a single driver.
  reg        sys_reset_wr, clr_faults_wr, heartbeat_wr;
  reg        watchdog_disarm_wr;
  // driven by the extracted session_guard instance
  wire       reset_latched, watchdog_tripped, watchdog_armed;
  wire [31:0] watchdog_cnt;
  // Motion inhibit for SYSTEM_RESET / watchdog (2026-10-11).
  //   motion_stop_pulse: one-cycle stop when a latch first sets, so an
  //                      in-flight move halts without permanently blocking the
  //                      HOME retract that safe_shutdown() issues afterwards.
  //   motion_move_lock : MOVE_TO / MOVE_REL / MOVE_TO_MEASURE are refused while
  //                      a latch is set.
  //   motion_all_lock  : after a watchdog trip nothing may move at all (the PS
  //                      is gone; only an operator clear restores motion).
  reg        motion_latch_d;
  wire       motion_latch_now  = reset_latched || watchdog_tripped;
  wire       motion_stop_pulse = motion_latch_now && !motion_latch_d;
  wire       motion_move_lock  = reset_latched || watchdog_tripped;
  wire       motion_all_lock   = reset_latched || watchdog_tripped;
  reg        axi_analog_abort_pulse;
  reg        axi_dac_start_pulse;
  reg        axi_dac_abort_pulse;
  reg [1:0]  analog_range_sel_reg;
  reg        analog_polarity_reg;
  reg        analog_current_req_reg;
  // driven by the extracted analog_seq instance
  wire [3:0]  analog_range_ctrl_reg;
  wire        analog_pol_i_reg;
  wire        analog_pol_v_reg;
  wire        analog_current_en_reg;
  wire [2:0]  analog_state_reg;
  wire        analog_busy;
  wire        analog_done;
  wire        analog_error;
  wire        analog_test_enable;
  wire [5:0]  analog_test_relay_mask;
  wire        analog_test_current_en;
  wire [15:0] analog_seq_reg;
  reg        analog_test_cmd_enable;
  reg [5:0]  analog_test_cmd_mask;
  reg        analog_test_cmd_current_en;
  reg [15:0] dac_code_reg;
  reg        dac_code_loaded;
  // driven by the extracted dac8562_serializer instance
  wire       dac_busy;
  wire       dac_done;
  wire [15:0] dac_seq_reg;

  wire [3:0] analog_test_range_masked;
  wire        analog_test_mask_valid;
  wire        analog_test_current_ok;
  wire        analog_test_current_active;

  assign analog_test_mask_valid = ((analog_test_relay_mask[3:0] &
                                   (analog_test_relay_mask[3:0] - 4'd1)) == 4'd0);
  assign analog_test_range_masked = analog_test_mask_valid ? analog_test_relay_mask[3:0] : 4'b0000;
  assign analog_test_current_ok = analog_test_mask_valid && (analog_test_relay_mask[3:0] != 4'd0);
  assign analog_test_current_active = analog_test_enable && analog_test_current_en && analog_test_current_ok;

  assign S_AXI_AWREADY = !axi_aw_pending && !axi_bvalid_reg;
  assign S_AXI_WREADY  = !axi_w_pending  && !axi_bvalid_reg;
  assign S_AXI_BVALID  = axi_bvalid_reg;
  assign S_AXI_BRESP   = axi_bresp_reg;
  assign S_AXI_ARREADY = !axi_rvalid_reg;
  assign S_AXI_RVALID  = axi_rvalid_reg;
  assign S_AXI_RDATA   = axi_rdata_reg;
  assign S_AXI_RRESP   = axi_rresp_reg;

  // AXI commands are ORed with the original external trigger inputs. Both
  // paths subsequently pass through the original synchronizers/edge detectors.
  wire start_request;
  wire x_trig_request;
  wire x_direct_start;
  wire x_var_direct_start;
  assign start_request  = start | axi_start_pulse;
  assign x_trig_request = x_trig_in | axi_x_trig_pulse;
  assign x_direct_start = axi_x_start_pulse && (main_state == S_IDLE) && !err_latch;
  // Lateral (R / X) motion is only allowed when the probe is known to be clear:
  // the home sensor confirmed a home (z_homed) AND the counted position is at or
  // above the PS-programmed safe height.  Fail-closed by construction: a PL
  // reset clears z_homed, so lateral motion is refused until a real HOME.
  wire z_probe_clear = z_homed && (z_position <= z_safe_travel_reg);
  // Z commands whose only possible direction is "up" may always run: lifting can
  // never drag the probe, so a retract must never be blocked by another axis.
  wire z_cmd_retract_only = (z_command_reg == Z_CMD_HOME) ||
                            (z_command_reg == Z_CMD_RETURN_HOME_SAFE);
  wire z_cmd_move_kind = (z_command_reg == Z_CMD_MOVE_TO) ||
                         (z_command_reg == Z_CMD_MOVE_REL) ||
                         (z_command_reg == Z_CMD_MOVE_TO_MEASURE);
  wire r_cmd_move_kind = (r_command_reg == R_CMD_MOVE_TO) ||
                         (r_command_reg == R_CMD_MOVE_REL);
  // One-cycle "this command was refused" pulses feeding the sticky status bit.
  wire z_refused_now = axi_z_start_pulse && !z_cmd_retract_only &&
                       (z_direct_busy || z_fault || motion_all_lock ||
                        (motion_move_lock && z_cmd_move_kind) ||
                        (main_state != S_IDLE) || x_busy || r_busy || err_latch);
  wire r_refused_now = axi_r_start_pulse &&
                       (r_busy || r_fault || motion_all_lock ||
                        (motion_move_lock && r_cmd_move_kind) ||
                        !z_probe_clear ||
                        (main_state != S_IDLE) || x_busy || z_direct_busy || err_latch);
  wire x_refused_now = (x_start_internal || x_direct_start || x_var_direct_start) &&
                       (x_busy || motion_all_lock || !z_probe_clear ||
                        z_direct_busy || r_busy);

  assign x_var_direct_start = axi_x_var_start_pulse && (main_state == S_IDLE) && !err_latch;
  
  
  // 中值计算函数：对5个16位数排序，返回中间值（索引2）
  // One bubble-sort pass for five 16-bit samples. Four clocked passes
  // replace the old fully combinational sort tree and close timing.
  function [79:0] bubble_pass_5;
      input [15:0] a0, a1, a2, a3, a4;
      reg [15:0] arr[0:4];
      integer j;
      reg [15:0] temp;
      begin
          arr[0] = a0; arr[1] = a1; arr[2] = a2; arr[3] = a3; arr[4] = a4;
          for(j = 0; j < 4; j = j + 1) begin
              if(arr[j] > arr[j+1]) begin
                  temp = arr[j];
                  arr[j] = arr[j+1];
                  arr[j+1] = temp;
              end
          end
          bubble_pass_5 = {arr[0], arr[1], arr[2], arr[3], arr[4]};
      end
  endfunction

  wire [79:0] median_after_pass = bubble_pass_5(
      median_arr_packed[79:64], median_arr_packed[63:48],
      median_arr_packed[47:32], median_arr_packed[31:16],
      median_arr_packed[15:0]);


  // ADS8681 采集链（SPI 时钟 / 配置状态机 / SPI 核 / 码值转 mV）已提取到
  // hw/rtl/adc/ads8681_capture.v；协议常量在该模块内是 localparam（不可覆盖）。
  // 下面这些 wire 即原内部信号，现由例化驱动。
  wire [31:0] RX_REG;
  wire        rx_reg_update_pulse;
  wire [15:0] V_mV;
  wire [15:0] adc_cfg_seq_reg;

  ads8681_capture #(
      .RVS_TIMEOUT_CYCLES     (RVS_TIMEOUT_CYCLES),
      .ADC_PWRUP_DELAY_CYCLES (ADC_PWRUP_DELAY_CYCLES)
  ) u_ads8681_capture (
      .clk      (clk),
      .reset_n  (reset_n),
      .RVS      (RVS),
      .SDO0     (SDO0),
      .reinit   (axi_adc_reinit_pulse),
      .SDI      (SDI),
      .SCLK     (SCLK),
      .CS       (CS),
      .RST      (RST),
      .rx_reg   (RX_REG),
      .rx_valid (rx_reg_update_pulse),
      .v_mv     (V_mV),
      .cfg_seq  (adc_cfg_seq_reg)
  );


  //==================== Banked 20 ms validity statistics ====================
  //==================== Banked 20 ms validity statistics ====================
  // The window itself (binning, SUM/SUMSQ/MIN/MAX, the SEQ-ACK protocol and the eight
  // per-bank snapshots) moved into hw/rtl/measurement/stats_window.v.
  //
  // Rule 4, both directions: the three arrays the module READS stay here (the AXI write
  // port owns them) and are handed over as flattened read-only copies, entry k in bits
  // [k*17 +: 17]; the ten arrays the module WRITES stay inside it and only the slice
  // selected by stats_bank_select is exported.
  wire [135:0] stats_center_code_flat = {
      stats_center_code[7], stats_center_code[6], stats_center_code[5], stats_center_code[4],
      stats_center_code[3], stats_center_code[2], stats_center_code[1], stats_center_code[0]};
  wire [135:0] stats_mag_min_flat = {
      stats_mag_min[7], stats_mag_min[6], stats_mag_min[5], stats_mag_min[4],
      stats_mag_min[3], stats_mag_min[2], stats_mag_min[1], stats_mag_min[0]};
  wire [135:0] stats_mag_max_flat = {
      stats_mag_max[7], stats_mag_max[6], stats_mag_max[5], stats_mag_max[4],
      stats_mag_max[3], stats_mag_max[2], stats_mag_max[1], stats_mag_max[0]};

  stats_window #(
      .STATS_WINDOW_CYCLES      (STATS_WINDOW_CYCLES)
  ) u_stats_window (
      .clk                      (clk),
      .reset_n                  (reset_n),
      .RX_REG                   (RX_REG),
      .rx_reg_update_pulse      (rx_reg_update_pulse),
      .analog_polarity_reg      (analog_polarity_reg),
      .analog_range_sel_reg     (analog_range_sel_reg),
      .axi_stats_clear_pulse    (axi_stats_clear_pulse),
      .axi_stats_arm_pulse      (axi_stats_arm_pulse),
      .axi_stats_disarm_pulse   (axi_stats_disarm_pulse),
      .axi_stats_ack_pulse      (axi_stats_ack_pulse),
      .axi_stats_clear_all_pulse(axi_stats_clear_all_pulse),
      .stats_ack_seq_set        (stats_ack_seq_set),
      .stats_ack_seq_value      (stats_ack_seq_value),
      .stats_bank_select        (stats_bank_select),
      .stats_center_code_flat   (stats_center_code_flat),
      .stats_mag_min_flat       (stats_mag_min_flat),
      .stats_mag_max_flat       (stats_mag_max_flat),
      .stats_active_bank        (stats_active_bank),
      .stats_window_enable      (stats_window_enable),
      .stats_window_busy        (stats_window_busy),
      .stats_ack_seq_pending    (stats_ack_seq_pending),
      .stats_sum_snapshot_sel   (stats_sum_snapshot_sel),
      .stats_sum_sq_snapshot_sel(stats_sum_sq_snapshot_sel),
      .stats_valid_count_snapshot_sel(stats_valid_count_snapshot_sel),
      .stats_rx_count_snapshot_sel   (stats_rx_count_snapshot_sel),
      .stats_min_snapshot_sel   (stats_min_snapshot_sel),
      .stats_max_snapshot_sel   (stats_max_snapshot_sel),
      .stats_seq_sel            (stats_seq_sel),
      .stats_ready_sel          (stats_ready_sel),
      .stats_empty_sel          (stats_empty_sel),
      .stats_overflow_sel       (stats_overflow_sel)
  );

  // PL measurement arithmetic: one bank per trigger.  PS writes CALC_COEFF_K (for the
  // bank selected by STATS_BANK_SELECT), pulses CALC_CONTROL.START, then polls
  // CALC_STATUS.DONE and reads CALC_RHO_LOW/HIGH + CALC_FLAGS.  Every gate inside is
  // fail-closed: an invalid compute reports VALID=0, zeroes rho and latches a reason
  // bit, so "not known" is never read back as a measurement.
  meas_calc #(
      .MEAN_FRAC   (16),
      .COEFF_FRAC  (23),
      .OUT_FRAC    (32),
      .COUNT_MAX   (CALC_COUNT_MAX),
      .COEFF_MAX   (CALC_COEFF_MAX)
  ) u_meas_calc (
      .clk                 (clk),
      .reset_n             (reset_n),
      .start_pulse         (mcalc_start_pulse),
      .clear_pulse         (mcalc_clear_pulse),
      .sum_snapshot        (stats_sum_snapshot_sel),
      .valid_count         (stats_valid_count_snapshot_sel),
      .snapshot_overflow   (stats_overflow_sel),
      .center_code         (stats_center_code[stats_bank_select]),
      .coeff_k_q           (mcalc_coeff_k_reg),
      .coeff_rs_q          (mcalc_coeff_rs_reg),
      .min_valid_count     (mcalc_min_count_reg),
      .max_span            (mcalc_max_span_reg),
      .min_code            (stats_min_snapshot_sel),
      .max_code            (stats_max_snapshot_sel),
      .busy                (mcalc_busy),
      .done                (mcalc_done),
      .result_valid        (mcalc_result_valid),
      .rho_q               (mcalc_rho_q),
      .flag_zero_count     (mcalc_flag_zero_count),
      .flag_count_over_max (mcalc_flag_count_over_max),
      .flag_sum_overflow   (mcalc_flag_sum_overflow),
      .flag_coeff_invalid  (mcalc_flag_coeff_invalid),
      .flag_negative       (mcalc_flag_negative),
      .pair_enable         (mcalc_pair_enable_reg),
      .pair_valid          (mcalc_pair_valid),
      .flag_pair_missing   (mcalc_flag_pair_missing),
      .rs_q                (mcalc_rs_q),
      .quality_ok          (mcalc_quality_ok),
      .flag_quality_low_count (mcalc_flag_quality_low_count),
      .flag_quality_wide_span (mcalc_flag_quality_wide_span)
  );

  //==================== 5. 定时触发模块 ==========
  //==================== Legacy measurement chain -> hw/rtl/measurement/meas_chain.v ====
  // 50 ms trigger + 5-sample median + rho/Rs pipeline + decimal split, extracted as ONE
  // module: they are a pipeline, and splitting further would only move wires across the
  // boundary.  The two state encodings below stay here because the BCD blocks still
  // compare against them.
  parameter CALC_IDLE = 5'd0;
  parameter CALC_DONE = 5'd21;
  wire [4:0]     calc_state;   // driven by the meas_chain instance

  meas_chain #(
      .MCNT_DELAY     (MCNT_DELAY),
      .RHO_FD         (RHO_FD),
      .RHO_FSP        (RHO_FSP),
      .RHO_FW         (RHO_FW),
      .S_IDLE         (S_IDLE),
      .S_M2_DIR1      (S_M2_DIR1),
      .S_M2_DIR3      (S_M2_DIR3),
      .S_M2_PAUSE1    (S_M2_PAUSE1),
      .S_M2_PAUSE2    (S_M2_PAUSE2),
      .S_MODE1_BACK   (S_MODE1_BACK),
      .S_MODE1_PAUSE  (S_MODE1_PAUSE),
      .W_mm           (W_mm),
      .CALC_IDLE      (CALC_IDLE),
      .CALC_DONE      (CALC_DONE)
  ) u_meas_chain (
      .clk                (clk),
      .reset_n            (reset_n),
      .start_edge         (start_edge),
      .x_trig_edge        (x_trig_edge),
      .V_mV               (V_mV),
      .median_after_pass  (median_after_pass),
      .main_state         (main_state),
      .send_go_update     (send_go_update),
      .median_arr_packed  (median_arr_packed),
      .calc_state         (calc_state),
      .rho                (rho),
      .Rs                 (Rs),
      .rho_S              (rho_S),
      .RS_S               (RS_S),
      .rho_1              (rho_1),
      .RS_1               (RS_1),
      .rho_2              (rho_2),
      .RS_2               (RS_2),
      .rho_3              (rho_3),
      .RS_3               (RS_3),
      .rho_4              (rho_4),
      .RS_4               (RS_4),
      .calc_slot          (calc_slot),
      .v0                 (v0),
      .v1                 (v1),
      .v2                 (v2),
      .v3                 (v3),
      .v4                 (v4)
  );
  
  
  // ==================== 锁存结果 BCD 拆分输出位 ====================
  reg [3:0] rS_r0, rS_r1, rS_r2, rS_r3, rS_r4, rS_r5, rS_r6, rS_r7, rS_r8, rS_r9;
  reg [3:0] rsS_r0, rsS_r1, rsS_r2, rsS_r3, rsS_r4, rsS_r5, rsS_r6, rsS_r7, rsS_r8, rsS_r9;
  reg [3:0] r1_r0, r1_r1, r1_r2, r1_r3, r1_r4, r1_r5, r1_r6, r1_r7, r1_r8, r1_r9;
  reg [3:0] rs1_r0, rs1_r1, rs1_r2, rs1_r3, rs1_r4, rs1_r5, rs1_r6, rs1_r7, rs1_r8, rs1_r9;
  reg [3:0] r2_r0, r2_r1, r2_r2, r2_r3, r2_r4, r2_r5, r2_r6, r2_r7, r2_r8, r2_r9;
  reg [3:0] rs2_r0, rs2_r1, rs2_r2, rs2_r3, rs2_r4, rs2_r5, rs2_r6, rs2_r7, rs2_r8, rs2_r9;
  reg [3:0] r3_r0, r3_r1, r3_r2, r3_r3, r3_r4, r3_r5, r3_r6, r3_r7, r3_r8, r3_r9;
  reg [3:0] rs3_r0, rs3_r1, rs3_r2, rs3_r3, rs3_r4, rs3_r5, rs3_r6, rs3_r7, rs3_r8, rs3_r9;
  reg [3:0] r4_r0, r4_r1, r4_r2, r4_r3, r4_r4, r4_r5, r4_r6, r4_r7, r4_r8, r4_r9;
  reg [3:0] rs4_r0, rs4_r1, rs4_r2, rs4_r3, rs4_r4, rs4_r5, rs4_r6, rs4_r7, rs4_r8, rs4_r9;
  
  // ==================== 拆分过程中间变量 ====================
  // rho_S
  reg [39:0] rho_S_bcd;
  reg [31:0] rho_S_bin;
  reg [5:0]  rho_S_conv_cnt;
  reg        rho_S_conv_active;
  reg        rho_S_digits_ready;
  reg [4:0]  rho_calc_state_d_S;
  reg [39:0] rho_S_bcd_next;
  reg [31:0] rho_S_bin_next;
  integer    rho_S_digit_idx;
  
  // rho_1
  reg [39:0] rho_1_bcd;
  reg [31:0] rho_1_bin;
  reg [5:0]  rho_1_conv_cnt;
  reg        rho_1_conv_active;
  reg        rho_1_digits_ready;
  reg [4:0]  rho_calc_state_d_1;
  reg [39:0] rho_1_bcd_next;
  reg [31:0] rho_1_bin_next;
  integer    rho_1_digit_idx;
  
  // rho_2
  reg [39:0] rho_2_bcd;
  reg [31:0] rho_2_bin;
  reg [5:0]  rho_2_conv_cnt;
  reg        rho_2_conv_active;
  reg        rho_2_digits_ready;
  reg [4:0]  rho_calc_state_d_2;
  reg [39:0] rho_2_bcd_next;
  reg [31:0] rho_2_bin_next;
  integer    rho_2_digit_idx;
  
  // rho_3
  reg [39:0] rho_3_bcd;
  reg [31:0] rho_3_bin;
  reg [5:0]  rho_3_conv_cnt;
  reg        rho_3_conv_active;
  reg        rho_3_digits_ready;
  reg [4:0]  rho_calc_state_d_3;
  reg [39:0] rho_3_bcd_next;
  reg [31:0] rho_3_bin_next;
  integer    rho_3_digit_idx;
  
  // rho_4
  reg [39:0] rho_4_bcd;
  reg [31:0] rho_4_bin;
  reg [5:0]  rho_4_conv_cnt;
  reg        rho_4_conv_active;
  reg        rho_4_digits_ready;
  reg [4:0]  rho_calc_state_d_4;
  reg [39:0] rho_4_bcd_next;
  reg [31:0] rho_4_bin_next;
  integer    rho_4_digit_idx;
  
  // RS_S
  reg [39:0] RS_S_bcd;
  reg [31:0] RS_S_bin;
  reg [5:0]  RS_S_conv_cnt;
  reg        RS_S_conv_active;
  reg        RS_S_digits_ready;
  reg [4:0]  RS_calc_state_d_S;
  reg [39:0] RS_S_bcd_next;
  reg [31:0] RS_S_bin_next;
  integer    RS_S_digit_idx;
  
  // RS_1
  reg [39:0] RS_1_bcd;
  reg [31:0] RS_1_bin;
  reg [5:0]  RS_1_conv_cnt;
  reg        RS_1_conv_active;
  reg        RS_1_digits_ready;
  reg [4:0]  RS_calc_state_d_1;
  reg [39:0] RS_1_bcd_next;
  reg [31:0] RS_1_bin_next;
  integer    RS_1_digit_idx;
  
  // RS_2
  reg [39:0] RS_2_bcd;
  reg [31:0] RS_2_bin;
  reg [5:0]  RS_2_conv_cnt;
  reg        RS_2_conv_active;
  reg        RS_2_digits_ready;
  reg [4:0]  RS_calc_state_d_2;
  reg [39:0] RS_2_bcd_next;
  reg [31:0] RS_2_bin_next;
  integer    RS_2_digit_idx;
  
  // RS_3
  reg [39:0] RS_3_bcd;
  reg [31:0] RS_3_bin;
  reg [5:0]  RS_3_conv_cnt;
  reg        RS_3_conv_active;
  reg        RS_3_digits_ready;
  reg [4:0]  RS_calc_state_d_3;
  reg [39:0] RS_3_bcd_next;
  reg [31:0] RS_3_bin_next;
  integer    RS_3_digit_idx;
  
  // RS_4
  reg [39:0] RS_4_bcd;
  reg [31:0] RS_4_bin;
  reg [5:0]  RS_4_conv_cnt;
  reg        RS_4_conv_active;
  reg        RS_4_digits_ready;
  reg [4:0]  RS_calc_state_d_4;
  reg [39:0] RS_4_bcd_next;
  reg [31:0] RS_4_bin_next;
  integer    RS_4_digit_idx;
  
  //==================== rho_S BCD 拆分 ====================
  
  //=========================================================================
  wire is_moving = (main_state == S_MODE1_GO) || (main_state == S_MODE1_BACK) ||
                   (main_state == S_M2_GO1)  || (main_state == S_M2_LIFT_HALF) ||
                   (main_state == S_M2_GO2)  || (main_state == S_M2_BACK) ||
                   (main_state == S_PWR_HOME);

  // 传感器消抖 / 触发边沿 / 步进节拍计数 -- 已提取到 hw/rtl/common/motion_sync.v。
  motion_sync #(
      .PULSE_HALF     (PULSE_HALF),
      .SLOW_DIV       (SLOW_DIV),
      .SEN_DELAY_CNT  (SEN_DELAY_CNT),
      .x_DEBOUNCE_CNT (x_DEBOUNCE_CNT)
  ) u_motion_sync (
      .clk            (clk),
      .reset_n        (reset_n),
      .sensor         (sensor),
      .start_request  (start_request),
      .x_trig_request (x_trig_request),
      .is_moving      (is_moving),
      .sen_stable     (sen_stable),
      .pulse_tick     (pulse_tick),
      .slow_step_en   (slow_step_en),
      .start_edge     (start_edge),
      .x_trig_edge    (x_trig_edge)
  );
  
  //=========================================================================
  // X 旋转台脉冲驱动已提取到 hw/rtl/motion/axis_x.v；互锁信号由顶层/其它轴模块提供。
  axis_x #(
      .x_PUL_NUM     (x_PUL_NUM),
      .x_HALF_PERIOD (x_HALF_PERIOD)
  ) u_axis_x (
      .clk              (clk),
      .reset_n          (reset_n),
      .start_internal   (x_start_internal),
      .direct_start     (x_direct_start),
      .var_direct_start (x_var_direct_start),
      .target           (x_target_reg),
      .motion_all_lock  (motion_all_lock),
      .motion_stop_pulse(motion_stop_pulse),
      .z_probe_clear    (z_probe_clear),
      .z_direct_busy    (z_direct_busy),
      .r_busy           (r_busy),
      .busy             (x_busy),
      .pul_out          (x_pul_out),
      .dir_out          (x_dir_out),
      .position         (x_position),
      .done_reg         (x_done_reg)
  );
  
  //=========================================================================
  // 8. 主状态机：上电回零+双模式全流程调度
  //    新增 meas_cnt_r 测量计数器（0~8）
  //=========================================================================
  // R 轴已提取到 hw/rtl/motion/axis_r.v；互锁全部作为输入传入。

  axis_r #(
      .R_PULSE_HALF (R_PULSE_HALF),
      .R_SLOW_DIV (R_SLOW_DIV),
      .R_MAX_STEPS (R_MAX_STEPS),
      .R_DIR_SETUP_CYCLES (R_DIR_SETUP_CYCLES),
      .R_HOME_DEBOUNCE_CYCLES (R_HOME_DEBOUNCE_CYCLES),
      .R_TIMEOUT_CYCLES (R_TIMEOUT_CYCLES)
  ) u_axis_r (
      .clk(clk),
      .reset_n(reset_n),
      .r_sensor(r_sensor),
      .axi_r_start_pulse(axi_r_start_pulse),
      .axi_r_stop_pulse(axi_r_stop_pulse),
      .axi_r_clear_pulse(axi_r_clear_pulse),
      .r_command_reg(r_command_reg),
      .r_target_reg(r_target_reg),
      .z_probe_clear(z_probe_clear),
      .main_state(main_state),
      .x_busy(x_busy),
      .z_direct_busy(z_direct_busy),
      .err_latch(err_latch),
      .motion_all_lock(motion_all_lock),
      .motion_move_lock(motion_move_lock),
      .motion_stop_pulse(motion_stop_pulse),
      .r_sensor_stable(r_sensor_stable),
      .r_pulse_tick(r_pulse_tick),
      .r_pul_out(r_pul_out),
      .r_dir_out(r_dir_out),
      .r_ena_out(r_ena_out),
      .r_state(r_state),
      .r_done_reg(r_done_reg),
      .r_fault(r_fault),
      .r_homed(r_homed),
      .r_position(r_position),
      .r_error_code(r_error_code),
      .r_busy(r_busy)
  );

  //=========================================================================
  // Z axis controller -- moved verbatim into hw/rtl/motion/axis_z.v.
  // The instance below owns the STEP pulse generator, the primitive Z command
  // state machine and the physical STEP/DIR/ENA output stage.  The top level only
  // forwards the interlocks, the AXI-written configuration and a read-only copy of
  // the deceleration LUT, and reads the Z state back out of it.
  //=========================================================================
  // 512-bit read-only replica of the AXI-written deceleration LUT.  The AXI write
  // port keeps ownership of z_decel_period_lut (rule 1) and the module only reads a
  // copy, so the data always flows top -> module and no module -> top -> module
  // combinational feedback path can appear.
  wire [511:0] z_decel_lut_flat = {
      z_decel_period_lut[15], z_decel_period_lut[14], z_decel_period_lut[13], z_decel_period_lut[12],
      z_decel_period_lut[11], z_decel_period_lut[10], z_decel_period_lut[9],  z_decel_period_lut[8],
      z_decel_period_lut[7],  z_decel_period_lut[6],  z_decel_period_lut[5],  z_decel_period_lut[4],
      z_decel_period_lut[3],  z_decel_period_lut[2],  z_decel_period_lut[1],  z_decel_period_lut[0]};

  axis_z #(
      .PULSE_HALF         (PULSE_HALF),
      .SLOW_DIV           (SLOW_DIV),
      .PULSE_PERIOD       (PULSE_PERIOD),
      .Z_MAX_STEPS        (Z_MAX_STEPS),
      .Z_DIR_SETUP_CYCLES (Z_DIR_SETUP_CYCLES),
      .Z_TIMEOUT_CYCLES   (Z_TIMEOUT_CYCLES)
  ) u_axis_z (
      .clk                    (clk),
      .reset_n                (reset_n),
      .axi_z_start_pulse      (axi_z_start_pulse),
      .axi_z_stop_pulse       (axi_z_stop_pulse),
      .axi_z_clear_pulse      (axi_z_clear_pulse),
      .motion_all_lock        (motion_all_lock),
      .motion_move_lock       (motion_move_lock),
      .motion_stop_pulse      (motion_stop_pulse),
      .main_state             (main_state),
      .x_busy                 (x_busy),
      .r_busy                 (r_busy),
      .err_latch              (err_latch),
      .cycle_done_r           (cycle_done_r),
      .z_command_reg          (z_command_reg),
      .z_target_reg           (z_target_reg),
      .z_cmd_retract_only     (z_cmd_retract_only),
      .z_driver_armed         (z_driver_armed),
      .sen_stable             (sen_stable),
      .z_step_interval_cycles (z_step_interval_cycles),
      .z_decel_enable         (z_decel_enable),
      .z_decel_measure_enable (z_decel_measure_enable),
      .z_decel_return_enable  (z_decel_return_enable),
      .z_decel_all_enable     (z_decel_all_enable),
      .z_decel_window_steps   (z_decel_window_steps),
      .z_decel_seg_steps      (z_decel_seg_steps),
      .z_decel_lut_flat       (z_decel_lut_flat),
      .step_pulse             (step_pulse),
      .dir                    (dir),
      .ena                    (ena),
      .err_flag               (err_flag),
      .cycle_done             (cycle_done),
      .z_direct_busy          (z_direct_busy),
      .z_position             (z_position),
      .z_homed                (z_homed),
      .z_fault                (z_fault),
      .z_done_reg             (z_done_reg),
      .z_dir_reg              (z_dir_reg),
      .z_error_code           (z_error_code),
      .z_measure_start_pulse  (z_measure_start_pulse),
      .z_home_step_cnt        (z_home_step_cnt)
  );
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin meas_state<=MEAS_STATE_IDLE; meas_hold_cnt<=0; meas_error_code<=MEAS_ERR_NONE; meas_legacy_active_d<=0; meas_source_legacy<=0; end
      else begin
          meas_legacy_active_d<=legacy_measure_active;
          if (axi_m_clear_pulse) begin meas_error_code<=MEAS_ERR_NONE; if (meas_state!=MEAS_STATE_ACTIVE) meas_state<=MEAS_STATE_IDLE; end
          if (axi_m_abort_pulse && meas_state==MEAS_STATE_ACTIVE) begin meas_state<=MEAS_STATE_IDLE; meas_hold_cnt<=0; meas_error_code<=MEAS_ERR_NONE; end
          else if (legacy_measure_active) begin if (!meas_legacy_active_d) begin meas_state<=MEAS_STATE_ACTIVE; meas_source_legacy<=1; meas_hold_cnt<=meas_hold_cycles_reg; meas_error_code<=MEAS_ERR_NONE; end end
          else if (meas_legacy_active_d && meas_source_legacy) begin meas_state<=MEAS_STATE_DONE; meas_source_legacy<=0; end
          else if (z_measure_start_pulse || axi_m_start_pulse) begin
              if (meas_state==MEAS_STATE_ACTIVE) begin meas_state<=MEAS_STATE_ERROR; meas_error_code<=MEAS_ERR_BUSY; end
              else begin meas_state<=MEAS_STATE_ACTIVE; meas_source_legacy<=0; meas_hold_cnt<=meas_hold_cycles_reg; meas_error_code<=MEAS_ERR_NONE; end
          end else if (meas_state==MEAS_STATE_ACTIVE && !meas_source_legacy) begin
              if (meas_hold_cnt==0) meas_state<=MEAS_STATE_DONE; else meas_hold_cnt<=meas_hold_cnt-1;
          end
      end
  end
  always @(posedge clk) begin
      if (!reset_n) begin
          main_state     <= LEGACY_AUTO_SEQUENCER_ENABLE ? S_PWR_HOME : S_IDLE;
          step_cnt       <= 18'd0;
          half_step_cnt  <= 18'd0;
          pause_cnt      <= 30'd0;
          dir_setup_cnt  <= 10'd0;
          back_limit_cnt <= 18'd0;
          back_err_cnt   <= 19'd0;
          ready_wait_cnt <= 14'd0;
          m2_cycle_cnt   <= 2'd0;
          dir_r          <= 1'b0;
          ena_r          <= 1'b1;
          sen_capture    <= 1'b0;
          err_latch      <= 1'b0;
          cycle_done_r   <= 1'b0;
          x_start_internal <= 1'b0;
          rot_start_flag   <= 1'b0;
          rot_busy_seen    <= 1'b0;
          meas_cnt     <= 4'd0;      // 测量计数器复位清零
      end else begin
          // 默认值：脉冲触发信号仅单周期有效
          x_start_internal <= 1'b0;
          cycle_done_r     <= 1'b0;
  
          case (main_state)
              //------------------------------------------
              // 上电自动回原点
              //------------------------------------------
              S_PWR_HOME: begin
                  dir_r <= 1'b1;
                  ena_r <= 1'b0;
  
                  if (sen_stable == 1'b0) begin
                      ready_wait_cnt <= 14'd0;
                      main_state     <= S_READY;
                  end else if(back_limit_cnt >= BACK_MAX_STEP - 18'd1) begin
                      ena_r     <= 1'b1;
                      err_latch <= 1'b1;
                      main_state <= S_ERR;
                  end else if (pulse_tick && slow_step_en) begin
                      back_limit_cnt <= back_limit_cnt + 18'd1;
                  end
              end
  
              //------------------------------------------
              // 原点就绪稳定
              //------------------------------------------
              S_READY: begin
                  ena_r          <= 1'b1;
                  dir_r          <= 1'b0;
                  ready_wait_cnt <= ready_wait_cnt + 14'd1;
                  back_limit_cnt <= 18'd0;
                  step_cnt       <= 18'd0;
                  sen_capture    <= 1'b0;
  
                  if(ready_wait_cnt >= READY_WAIT_CNT) begin
                      main_state <= S_IDLE;
                  end
              end
  
              //------------------------------------------
              // 空闲待机态：等待模式一/模式二触发
              //------------------------------------------
              S_IDLE: begin
                  ena_r       <= 1'b1;
                  dir_r       <= 1'b0;
                  step_cnt    <= 18'd0;
                  half_step_cnt <= 18'd0;
                  sen_capture <= 1'b0;
                  back_err_cnt <= 19'd0;
                  rot_start_flag <= 1'b0;
                  rot_busy_seen  <= 1'b0;
                  m2_cycle_cnt   <= 2'd0;
  
                  if(LEGACY_AUTO_SEQUENCER_ENABLE && start_edge) begin
                      main_state <= S_MODE1_GO;
                      ena_r      <= 1'b0;
                      step_cnt   <= 18'd0;
                      meas_cnt <= 4'd0;      // 触发时计数器清零
                  end else if(LEGACY_AUTO_SEQUENCER_ENABLE && x_trig_edge) begin
                      main_state <= S_M2_GO1;
                      ena_r      <= 1'b0;
                      step_cnt   <= 18'd0;
                      meas_cnt <= 4'd0;      // 触发时计数器清零
                  end
              end
  
              //------------------------------------------
              // 模式一：下压阶段
              //------------------------------------------
              S_MODE1_GO: begin
                  dir_r <= 1'b0;
                  ena_r <= 1'b0;
  
                  if (pulse_tick && slow_step_en) begin
                      if (step_cnt >= STEPS_FORWARD - 18'd1) begin
                          pause_cnt  <= PAUSE_CLKS;
                          main_state <= S_MODE1_PAUSE;
                      end else begin
                          step_cnt <= step_cnt + 18'd1;
                      end
                  end
              end
  
              //------------------------------------------
              // 模式一：保持测量阶段
              //------------------------------------------
              S_MODE1_PAUSE: begin
                  ena_r <= 1'b0;
  
                  if(pause_cnt == 30'd0) begin
                      dir_r         <= 1'b1;
                      dir_setup_cnt <= 10'd0;
                      main_state    <= S_MODE1_DIR;
                  end else begin
                      pause_cnt <= pause_cnt - 30'd1;
                  end
              end
  
              //------------------------------------------
              // 模式一：换向建立延时
              //------------------------------------------
              S_MODE1_DIR: begin
                  ena_r         <= 1'b0;
                  dir_setup_cnt <= dir_setup_cnt + 10'd1;
                  sen_capture   <= 1'b0;
                  step_cnt      <= STEPS_FORWARD;
  
                  if(dir_setup_cnt >= DIR_SETUP_CNT) begin
                      main_state <= S_MODE1_BACK;
                  end
              end
  
              //------------------------------------------
              // 模式一：上升回原点
              //------------------------------------------
              S_MODE1_BACK: begin
                  dir_r <= 1'b1;
                  ena_r <= 1'b0;
  
                  if(sen_stable == 1'b0)
                      sen_capture <= 1'b1;
  
                  if (step_cnt == 18'd0) begin
                      if(sen_capture) begin
                          ena_r        <= 1'b1;
                          cycle_done_r <= 1'b1;
                          main_state   <= S_IDLE;
                      end else begin
                          back_err_cnt <= back_err_cnt + 19'd1;
                          if(back_err_cnt >= BACK_FAIL_WAIT) begin
                              ena_r     <= 1'b1;
                              err_latch <= 1'b1;
                              main_state <= S_ERR;
                          end
                      end
                  end else if (pulse_tick && slow_step_en) begin
                      step_cnt <= step_cnt - 18'd1;
                  end
              end
  
              //------------------------------------------
              // 模式二阶段1：第一次全行程下压
              //------------------------------------------
              S_M2_GO1: begin
                  dir_r <= 1'b0;
                  ena_r <= 1'b0;
  
                  if (pulse_tick && slow_step_en) begin
                      if (step_cnt >= STEPS_FORWARD - 18'd1) begin
                          pause_cnt  <= PAUSE_CLKS;
                          main_state <= S_M2_PAUSE1;
                          meas_cnt <= 4'd1;      // 进入第一次测量（压住保持）
                      end else begin
                          step_cnt <= step_cnt + 18'd1;
                      end
                  end
              end
  
              //------------------------------------------
              // 模式二阶段2：第一次保持测量
              //------------------------------------------
              S_M2_PAUSE1: begin
                  ena_r <= 1'b0;
  
                  if(pause_cnt == 30'd0) begin
                      dir_r         <= 1'b1;
                      dir_setup_cnt <= 10'd0;
                      half_step_cnt <= 18'd0;
                      m2_cycle_cnt  <= 2'd0;
                      main_state    <= S_M2_DIR1;
                      meas_cnt    <= 4'd2;      // 结束第一次测量
                  end else begin
                      pause_cnt <= pause_cnt - 30'd1;
                  end
              end
  
              //------------------------------------------
              // 模式二阶段3：抬升方向换向延时
              //------------------------------------------
              S_M2_DIR1: begin
                  ena_r         <= 1'b0;
                  dir_setup_cnt <= dir_setup_cnt + 10'd1;
  
                  if(dir_setup_cnt >= DIR_SETUP_CNT) begin
                      main_state <= S_M2_LIFT_HALF;
                  end
              end
  
              //------------------------------------------
              // 模式二阶段4：半程抬升（独立计数）
              //------------------------------------------
              S_M2_LIFT_HALF: begin
                  dir_r <= 1'b1;
                  ena_r <= 1'b0;
  
                  if (pulse_tick && slow_step_en) begin
                      if (half_step_cnt >= HALF_LIFT_STEP - 18'd1) begin
                          ena_r      <= 1'b1;
                          main_state <= S_M2_WAIT_ROT;
                          rot_start_flag <= 1'b0;
                          rot_busy_seen  <= 1'b0;
                      end else begin
                          half_step_cnt <= half_step_cnt + 18'd1;
                          step_cnt <= step_cnt - 18'd1;
                      end
                  end
              end
  
              //------------------------------------------
              // 模式二阶段5：启动旋转 + 等待旋转完全完成
              //------------------------------------------
              S_M2_WAIT_ROT: begin
                  ena_r <= 1'b1;
  
                  if(!rot_start_flag) begin
                      x_start_internal <= 1'b1;
                      rot_start_flag   <= 1'b1;
                  end
  
                  if(rot_start_flag && x_busy) begin
                      rot_busy_seen <= 1'b1;
                  end
  
                  if(rot_busy_seen && x_busy == 1'b0) begin
                      dir_r         <= 1'b0;
                      dir_setup_cnt <= 10'd0;
                      half_step_cnt <= 18'd0;
                      main_state    <= S_M2_DIR2;
                  end
              end
  
              //------------------------------------------
              // 模式二阶段6：下压方向换向延时
              //------------------------------------------
              S_M2_DIR2: begin
                  ena_r         <= 1'b0;
                  dir_setup_cnt <= dir_setup_cnt + 10'd1;
  
                  if(dir_setup_cnt >= DIR_SETUP_CNT) begin
                      main_state <= S_M2_GO2;
                  end
              end
  
              //------------------------------------------
              // 模式二阶段7：半程下压
              //------------------------------------------
              S_M2_GO2: begin
                  dir_r <= 1'b0;
                  ena_r <= 1'b0;
  
                  if (pulse_tick && slow_step_en) begin
                      if (half_step_cnt >= HALF_LIFT_STEP - 18'd1) begin
                          pause_cnt  <= PAUSE_CLKS;
                          main_state <= S_M2_PAUSE2;
                          // 进入第2/3/4次测量（压住保持）
                          case (m2_cycle_cnt)
                              2'd0: meas_cnt <= 4'd3;   // 进入第二次测量
                              2'd1: meas_cnt <= 4'd5;   // 进入第三次测量
                              2'd2: meas_cnt <= 4'd7;   // 进入第四次测量
                              default: meas_cnt <= 4'd3;
                          endcase
                      end else begin
                          half_step_cnt <= half_step_cnt + 18'd1;
                          step_cnt <= step_cnt + 18'd1;
                      end
                  end
              end
  
              //------------------------------------------
              // 模式二阶段8：循环中保持测量 + 循环次数判断
              //------------------------------------------
              S_M2_PAUSE2: begin
                  ena_r <= 1'b0;
  
                  if(pause_cnt == 30'd0) begin
                      if(m2_cycle_cnt >= 2'd2) begin
                          // 3次半程循环全部完成，共4次下压，准备回原点
                          dir_r         <= 1'b1;
                          dir_setup_cnt <= 10'd0;
                          sen_capture   <= 1'b0;
                          step_cnt      <= STEPS_FORWARD;
                          main_state    <= S_M2_DIR3;
                          meas_cnt    <= 4'd8;      // 结束第四次测量
                      end else begin
                          // 未完成3次循环，继续下一轮抬升-旋转-下压
                          dir_r         <= 1'b1;
                          dir_setup_cnt <= 10'd0;
                          half_step_cnt <= 18'd0;
                          m2_cycle_cnt  <= m2_cycle_cnt + 2'd1;
                          main_state    <= S_M2_DIR1;
                          // 结束第2/3次测量
                          case (m2_cycle_cnt)
                              2'd0: meas_cnt <= 4'd4;   // 结束第二次测量
                              2'd1: meas_cnt <= 4'd6;   // 结束第三次测量
                              default: meas_cnt <= 4'd4;
                          endcase
                      end
                  end else begin
                      pause_cnt <= pause_cnt - 30'd1;
                  end
              end
  
              //------------------------------------------
              // 模式二阶段9：回原点方向换向延时
              //------------------------------------------
              S_M2_DIR3: begin
                  ena_r         <= 1'b0;
                  dir_setup_cnt <= dir_setup_cnt + 10'd1;
  
                  if(dir_setup_cnt >= DIR_SETUP_CNT) begin
                      main_state <= S_M2_BACK;
                  end
              end
  
              //------------------------------------------
              // 模式二阶段10：全行程上升回原点
              //------------------------------------------
              S_M2_BACK: begin
                  dir_r <= 1'b1;
                  ena_r <= 1'b0;
  
                  if(sen_stable == 1'b0)
                      sen_capture <= 1'b1;
  
                  if (step_cnt == 18'd0) begin
                      if(sen_capture) begin
                          main_state     <= S_M2_FINAL_ROT;
                          rot_start_flag <= 1'b0;
                          rot_busy_seen  <= 1'b0;
                      end else begin
                          back_err_cnt <= back_err_cnt + 19'd1;
                          if(back_err_cnt >= BACK_FAIL_WAIT) begin
                              ena_r     <= 1'b1;
                              err_latch <= 1'b1;
                              main_state <= S_ERR;
                          end
                      end
                  end else if (pulse_tick && slow_step_en) begin
                      step_cnt <= step_cnt - 18'd1;
                  end
              end
  
              //------------------------------------------
              // 模式二阶段11：回原点后末次旋转等待
              //------------------------------------------
              S_M2_FINAL_ROT: begin
                  ena_r <= 1'b1;
  
                  if(!rot_start_flag) begin
                      x_start_internal <= 1'b1;
                      rot_start_flag   <= 1'b1;
                  end
  
                  if(rot_start_flag && x_busy) begin
                      rot_busy_seen <= 1'b1;
                  end
  
                  if(rot_busy_seen && x_busy == 1'b0) begin
                      cycle_done_r <= 1'b1;
                      main_state   <= S_IDLE;
                  end
              end
  
              //------------------------------------------
              // 故障锁存态
              //------------------------------------------
              S_ERR: begin
                  ena_r <= 1'b1;
                  if (axi_clear_error_pulse) begin
                      err_latch  <= 1'b0;
                      main_state <= S_IDLE;
                  end else begin
                      err_latch <= 1'b1;
                  end
              end
  
              default: main_state <= S_IDLE;
          endcase
      end
  end
  
  //=========================================================================
  // 9. Output-register / output-pin stage -> hw/rtl/motion/axis_z.v
  //    step_pulse / dir / ena / err_flag / cycle_done are driven by u_axis_z now
  //    (rule 1: the writer of those registers moved, so they moved with it).
  //    ALL_Final declares them as output wires.
  //=========================================================================

  //=========================================================================
  // 10. Relay range/polarity control and DAC8562 serializer
  //=========================================================================
  assign range0_ctrl = analog_test_enable ? analog_test_range_masked[0] : analog_range_ctrl_reg[0];
  assign range1_ctrl = analog_test_enable ? analog_test_range_masked[1] : analog_range_ctrl_reg[1];
  assign range2_ctrl = analog_test_enable ? analog_test_range_masked[2] : analog_range_ctrl_reg[2];
  assign range3_ctrl = analog_test_enable ? analog_test_range_masked[3] : analog_range_ctrl_reg[3];
  assign pol_i_ctrl  = analog_test_enable ? analog_test_relay_mask[4] : analog_pol_i_reg;
  assign pol_v_ctrl  = analog_test_enable ? analog_test_relay_mask[5] : analog_pol_v_reg;
  assign current_en  = analog_test_enable ? (analog_test_current_en && analog_test_current_ok)
                                          : analog_current_en_reg;

  //=========================================================================
  // 10b. Analog front-end command sequencer -> hw/rtl/analog/analog_seq.v
  //      current off -> 20 ms settle -> relay/polarity change -> 20 ms settle ->
  //      current on, plus the PS test-mode relay/polarity mask path.  The relay
  //      output muxes above stay here (they drive board pins and read the
  //      AXI-written registers), so they now read the instance outputs as wires.
  //=========================================================================
  analog_seq #(
      .ANALOG_SETTLE_CYCLES (ANALOG_SETTLE_CYCLES)
  ) u_analog_seq (
      .clk                        (clk),
      .reset_n                    (reset_n),
      .axi_analog_start_pulse     (axi_analog_start_pulse),
      .axi_analog_abort_pulse     (axi_analog_abort_pulse),
      .analog_test_cmd_enable     (analog_test_cmd_enable),
      .analog_test_cmd_mask       (analog_test_cmd_mask),
      .analog_test_cmd_current_en (analog_test_cmd_current_en),
      .analog_test_mask_valid     (analog_test_mask_valid),
      .analog_range_sel_reg       (analog_range_sel_reg),
      .analog_polarity_reg        (analog_polarity_reg),
      .analog_current_req_reg     (analog_current_req_reg),
      .reset_latched              (reset_latched),
      .watchdog_tripped           (watchdog_tripped),
      .analog_range_ctrl_reg      (analog_range_ctrl_reg),
      .analog_pol_i_reg           (analog_pol_i_reg),
      .analog_pol_v_reg           (analog_pol_v_reg),
      .analog_current_en_reg      (analog_current_en_reg),
      .analog_state_reg           (analog_state_reg),
      .analog_busy                (analog_busy),
      .analog_done                (analog_done),
      .analog_error               (analog_error),
      .analog_test_enable         (analog_test_enable),
      .analog_test_relay_mask     (analog_test_relay_mask),
      .analog_test_current_en     (analog_test_current_en),
      .analog_seq_reg             (analog_seq_reg)
  );

  // DAC8562 24-bit frame serializer -- extracted to hw/rtl/analog/dac8562_serializer.v.
  dac8562_serializer #(
      .DAC_HALF_CYCLES (DAC_HALF_CYCLES)
  ) u_dac8562_serializer (
      .clk     (clk),
      .reset_n (reset_n),
      .code    (dac_code_reg),
      .start   (axi_dac_start_pulse),
      .abort   (axi_dac_abort_pulse),
      .busy    (dac_busy),
      .done    (dac_done),
      .seq     (dac_seq_reg),
      .sclk    (dac_sclk),
      .din     (dac_din),
      .sync_n  (dac_sync_n)
  );

  //==================== AXI-Lite protocol engine ============================
  // AW and W are accepted independently; the write commits only after both
  // channels have arrived, and B/R responses remain asserted until accepted.
  always @(posedge S_AXI_ACLK or negedge S_AXI_ARESETN) begin
      if (!S_AXI_ARESETN) begin
          axi_aw_pending       <= 1'b0;
          axi_w_pending        <= 1'b0;
          axi_awaddr_reg       <= 32'd0;
          axi_wdata_reg        <= 32'd0;
          axi_wstrb_reg        <= 4'd0;
          axi_bvalid_reg       <= 1'b0;
          axi_bresp_reg        <= 2'b00;
          axi_rvalid_reg       <= 1'b0;
          axi_rdata_reg        <= 32'd0;
          axi_rresp_reg        <= 2'b00;
          axi_start_pulse      <= 1'b0;
          axi_x_trig_pulse     <= 1'b0;
          axi_x_start_pulse    <= 1'b0;
          axi_x_var_start_pulse<= 1'b0;
          axi_clear_error_pulse<= 1'b0;
          axi_r_start_pulse    <= 1'b0;
          axi_r_stop_pulse     <= 1'b0;
          axi_r_clear_pulse    <= 1'b0;
          axi_z_start_pulse    <= 1'b0;
          axi_z_stop_pulse     <= 1'b0;
          axi_z_clear_pulse    <= 1'b0;
          axi_m_start_pulse    <= 1'b0;
          axi_m_abort_pulse    <= 1'b0;
          axi_m_clear_pulse    <= 1'b0;
          axi_stats_clear_pulse <= 1'b0;
          axi_stats_arm_pulse <= 1'b0;
          axi_stats_ack_pulse <= 1'b0;
          axi_stats_disarm_pulse <= 1'b0;
          axi_stats_clear_all_pulse <= 1'b0;
          watchdog_disarm_wr <= 1'b0;
          stats_ack_seq_set <= 1'b0;
          mcalc_start_pulse <= 1'b0;
          mcalc_clear_pulse <= 1'b0;
          mcalc_pair_enable_reg <= 1'b0;
          mcalc_coeff_k_reg     <= 32'd0;
          mcalc_coeff_rs_reg    <= 32'd0;
          mcalc_min_count_reg   <= 32'd0;
          mcalc_max_span_reg    <= 17'd0;
          r_command_reg        <= 32'd0;
          r_target_reg         <= 32'd0;
          z_command_reg        <= 32'd0;
          z_target_reg         <= 32'd0;
          z_driver_armed       <= 1'b0;
          z_safe_travel_reg    <= 32'd0;   // fail-closed until the PS programs it
          x_target_reg         <= x_PUL_NUM;
          z_step_interval_cycles <= PULSE_PERIOD * SLOW_DIV;
          z_decel_enable <= 1'b0; z_decel_measure_enable <= 1'b0; z_decel_return_enable <= 1'b0; z_decel_all_enable <= 1'b0;
          z_decel_window_steps <= 32'd500; z_decel_seg_steps <= 32'd32; z_decel_lut_index <= 5'd0;
          for (z_decel_lut_i=0; z_decel_lut_i<16; z_decel_lut_i=z_decel_lut_i+1)
              z_decel_period_lut[z_decel_lut_i] <= PULSE_PERIOD * SLOW_DIV;
          meas_hold_cycles_reg <= PAUSE_CLKS;
          meas_point_index_reg <= 32'd0;
          stats_bank_select    <= 3'd0;
          for (stats_config_i = 0; stats_config_i < 8; stats_config_i = stats_config_i + 1) begin
              stats_center_code[stats_config_i] <= 17'd32768;
              // Fail-closed default: mag_min = 0x10000 can never be satisfied
              // by a 17-bit delta, so an unconfigured bank reports
              // valid_count = 0 instead of silently accepting every sample.
              stats_mag_min[stats_config_i] <= 17'h10000;
              stats_mag_max[stats_config_i] <= 17'd0;
          end
          axi_analog_start_pulse <= 1'b0;
          axi_adc_reinit_pulse   <= 1'b0;
          axi_analog_abort_pulse <= 1'b0;
          axi_dac_start_pulse    <= 1'b0;
          axi_dac_abort_pulse    <= 1'b0;
          analog_range_sel_reg   <= 2'd0;
          analog_polarity_reg    <= 1'b0;
          analog_current_req_reg <= 1'b0;
          analog_test_cmd_enable     <= 1'b0;
          analog_test_cmd_mask       <= 6'd0;
          analog_test_cmd_current_en <= 1'b0;
          dac_code_reg               <= 16'd0;
          dac_code_loaded            <= 1'b0;
      end else begin
          axi_start_pulse       <= 1'b0;
          axi_x_trig_pulse      <= 1'b0;
          sys_reset_wr          <= 1'b0;
          clr_faults_wr         <= 1'b0;
          heartbeat_wr          <= 1'b0;
          axi_x_start_pulse     <= 1'b0;
          axi_x_var_start_pulse <= 1'b0;
          axi_clear_error_pulse <= 1'b0;
          axi_r_start_pulse     <= 1'b0;
          axi_r_stop_pulse      <= 1'b0;
          axi_r_clear_pulse     <= 1'b0;
          axi_z_start_pulse     <= 1'b0;
          axi_z_stop_pulse      <= 1'b0;
          axi_z_clear_pulse     <= 1'b0;
          axi_m_start_pulse     <= 1'b0;
          axi_m_abort_pulse     <= 1'b0;
          axi_m_clear_pulse     <= 1'b0;
          axi_stats_clear_pulse <= 1'b0;
          axi_stats_arm_pulse <= 1'b0;
          axi_stats_ack_pulse <= 1'b0;
          axi_stats_disarm_pulse <= 1'b0;
          axi_stats_clear_all_pulse <= 1'b0;
          watchdog_disarm_wr <= 1'b0;
          stats_ack_seq_set <= 1'b0;
          mcalc_start_pulse <= 1'b0;
          mcalc_clear_pulse <= 1'b0;
          axi_analog_start_pulse <= 1'b0;
          axi_adc_reinit_pulse   <= 1'b0;
          axi_analog_abort_pulse <= 1'b0;
          axi_dac_start_pulse    <= 1'b0;
          axi_dac_abort_pulse    <= 1'b0;

          if (axi_bvalid_reg && S_AXI_BREADY)
              axi_bvalid_reg <= 1'b0;
          if (axi_rvalid_reg && S_AXI_RREADY)
              axi_rvalid_reg <= 1'b0;

          if (S_AXI_AWVALID && S_AXI_AWREADY) begin
              axi_aw_pending <= 1'b1;
              axi_awaddr_reg <= S_AXI_AWADDR;
          end
          if (S_AXI_WVALID && S_AXI_WREADY) begin
              axi_w_pending  <= 1'b1;
              axi_wdata_reg  <= S_AXI_WDATA;
              axi_wstrb_reg  <= S_AXI_WSTRB;
          end

          if (axi_aw_pending && axi_w_pending && !axi_bvalid_reg) begin
              axi_aw_pending <= 1'b0;
              axi_w_pending  <= 1'b0;
              axi_bvalid_reg <= 1'b1;
              axi_bresp_reg  <= 2'b00;

              case (axi_awaddr_reg[11:0])
                  AXI_REG_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          if (axi_wdata_reg[0]) axi_start_pulse        <= 1'b1;
                          if (axi_wdata_reg[1]) axi_x_trig_pulse       <= 1'b1;
                          if (axi_wdata_reg[2]) axi_clear_error_pulse  <= 1'b1;
                          if (axi_wdata_reg[3]) axi_x_start_pulse      <= 1'b1;
                          if (axi_wdata_reg[4]) axi_adc_reinit_pulse    <= 1'b1;
                          if (axi_wdata_reg[5]) sys_reset_wr   <= 1'b1;
                          if (axi_wdata_reg[6]) clr_faults_wr  <= 1'b1;
                          if (axi_wdata_reg[7]) watchdog_disarm_wr <= 1'b1;
                      end
                  end
                  AXI_REG_R_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          if (axi_wdata_reg[0]) axi_r_start_pulse <= 1'b1;
                          if (axi_wdata_reg[1]) axi_r_stop_pulse  <= 1'b1;
                          if (axi_wdata_reg[2]) axi_r_clear_pulse <= 1'b1;
                      end
                  end
                  AXI_REG_R_COMMAND: begin
                      if (axi_wstrb_reg[0]) r_command_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) r_command_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) r_command_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) r_command_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_R_TARGET: begin
                      if (axi_wstrb_reg[0]) r_target_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) r_target_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) r_target_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) r_target_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_Z_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          if (axi_wdata_reg[0]) axi_z_start_pulse <= 1'b1;
                          if (axi_wdata_reg[1]) axi_z_stop_pulse  <= 1'b1;
                          if (axi_wdata_reg[2]) axi_z_clear_pulse <= 1'b1;
                          if (axi_wdata_reg[3]) z_driver_armed <= 1'b1;
                          if (axi_wdata_reg[4]) z_driver_armed <= 1'b0;
                      end
                  end
                  AXI_REG_Z_COMMAND: begin
                      if (axi_wstrb_reg[0]) z_command_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) z_command_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) z_command_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) z_command_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_Z_TARGET: begin
                      if (axi_wstrb_reg[0]) z_target_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) z_target_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) z_target_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) z_target_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_X_TARGET: begin
                      if (axi_wstrb_reg[0]) x_target_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) x_target_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) x_target_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) x_target_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_X_CONTROL: begin
                      if (axi_wstrb_reg[0] && axi_wdata_reg[0])
                          axi_x_var_start_pulse <= 1'b1;
                  end
                  AXI_REG_HEARTBEAT: begin
                      if (axi_wstrb_reg[0]) heartbeat_wr <= 1'b1;
                  end
                  AXI_REG_Z_STEP_INTERVAL: begin
                      if (axi_wstrb_reg[0]) z_step_interval_cycles[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) z_step_interval_cycles[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) z_step_interval_cycles[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) z_step_interval_cycles[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_Z_DECEL_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          z_decel_enable <= axi_wdata_reg[0];
                          z_decel_measure_enable <= axi_wdata_reg[1];
                          z_decel_return_enable <= axi_wdata_reg[2];
                          z_decel_all_enable <= axi_wdata_reg[3];
                      end
                  end
                  AXI_REG_Z_DECEL_WINDOW: begin
                      if (axi_wstrb_reg[0]) z_decel_window_steps[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) z_decel_window_steps[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) z_decel_window_steps[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) z_decel_window_steps[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_Z_DECEL_SEG_STEPS: begin
                      if (axi_wstrb_reg[0]) z_decel_seg_steps[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) z_decel_seg_steps[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) z_decel_seg_steps[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) z_decel_seg_steps[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_Z_DECEL_LUT_INDEX: begin
                      if (axi_wstrb_reg[0]) z_decel_lut_index <= axi_wdata_reg[4:0];
                  end
                  AXI_REG_Z_DECEL_LUT_DATA: begin
                      if (axi_wstrb_reg[0]) z_decel_period_lut[z_decel_lut_index[3:0]][7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) z_decel_period_lut[z_decel_lut_index[3:0]][15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) z_decel_period_lut[z_decel_lut_index[3:0]][23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) z_decel_period_lut[z_decel_lut_index[3:0]][31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_M_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          if (axi_wdata_reg[0]) axi_m_start_pulse <= 1'b1;
                          if (axi_wdata_reg[1]) axi_m_abort_pulse <= 1'b1;
                          if (axi_wdata_reg[2]) axi_m_clear_pulse <= 1'b1;
                      end
                  end
                  AXI_REG_M_POINT: begin
                      if (axi_wstrb_reg[0]) meas_point_index_reg[7:0] <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) meas_point_index_reg[15:8] <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) meas_point_index_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) meas_point_index_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_M_HOLD: begin
                      if (axi_wstrb_reg[0]) meas_hold_cycles_reg[7:0] <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) meas_hold_cycles_reg[15:8] <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) meas_hold_cycles_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) meas_hold_cycles_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_ANALOG_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          analog_range_sel_reg       <= axi_wdata_reg[4:3];
                          analog_polarity_reg        <= axi_wdata_reg[5];
                          analog_current_req_reg     <= axi_wdata_reg[2];
                          analog_test_cmd_enable     <= 1'b0;
                          analog_test_cmd_mask       <= 6'd0;
                          analog_test_cmd_current_en <= 1'b0;
                          if (axi_wdata_reg[0]) axi_analog_start_pulse <= 1'b1;
                          if (axi_wdata_reg[1]) axi_analog_abort_pulse <= 1'b1;
                      end
                  end
                  AXI_REG_ANALOG_TEST_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          if (axi_wdata_reg[31] && !analog_busy && !analog_current_en_reg && !analog_test_current_active) begin
                              analog_test_cmd_enable     <= 1'b1;
                              analog_test_cmd_mask       <= axi_wdata_reg[5:0];
                              analog_test_cmd_current_en <= axi_wdata_reg[8];
                          end else if (!axi_wdata_reg[31]) begin
                              analog_test_cmd_enable     <= 1'b0;
                              analog_test_cmd_mask       <= 6'd0;
                              analog_test_cmd_current_en <= 1'b0;
                          end
                      end
                  end
                  AXI_REG_DAC_CODE: begin
                      if (!dac_busy) begin
                          if (axi_wstrb_reg[0]) dac_code_reg[7:0]   <= axi_wdata_reg[7:0];
                          if (axi_wstrb_reg[1]) dac_code_reg[15:8]  <= axi_wdata_reg[15:8];
                          dac_code_loaded <= 1'b1;
                      end
                  end
                  AXI_REG_DAC_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          if (axi_wdata_reg[0]) axi_dac_start_pulse <= 1'b1;
                          if (axi_wdata_reg[1]) axi_dac_abort_pulse <= 1'b1;
                      end
                  end
                  AXI_REG_STATS_BANK_SELECT: begin
                      if (axi_wstrb_reg[0]) stats_bank_select <= axi_wdata_reg[2:0];
                  end
                  AXI_REG_STATS_CENTER_CODE: begin
                      if (axi_wstrb_reg[0]) stats_center_code[stats_bank_select][7:0] <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) stats_center_code[stats_bank_select][15:8] <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) stats_center_code[stats_bank_select][16] <= axi_wdata_reg[16];
                  end
                  AXI_REG_STATS_MAG_MIN: begin
                      if (axi_wstrb_reg[0]) stats_mag_min[stats_bank_select][7:0] <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) stats_mag_min[stats_bank_select][15:8] <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) stats_mag_min[stats_bank_select][16] <= axi_wdata_reg[16];
                  end
                  AXI_REG_STATS_MAG_MAX: begin
                      if (axi_wstrb_reg[0]) stats_mag_max[stats_bank_select][7:0] <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) stats_mag_max[stats_bank_select][15:8] <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) stats_mag_max[stats_bank_select][16] <= axi_wdata_reg[16];
                  end
                  AXI_REG_STATS_CONTROL: begin
                      if (axi_wstrb_reg[0]) begin
                          if (axi_wdata_reg[0]) axi_stats_clear_pulse <= 1'b1;
                          if (axi_wdata_reg[1]) axi_stats_arm_pulse <= 1'b1;
                          if (axi_wdata_reg[2]) axi_stats_ack_pulse <= 1'b1;
                          if (axi_wdata_reg[3]) axi_stats_disarm_pulse <= 1'b1;
                          if (axi_wdata_reg[4]) axi_stats_clear_all_pulse <= 1'b1;
                  end
                  end
                  AXI_REG_STATS_ACK_SEQ: begin
                      // Write-only: value = SEQ the following ACK acknowledges.
                      if (axi_wstrb_reg[0]) stats_ack_seq_value[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) stats_ack_seq_value[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) stats_ack_seq_value[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) stats_ack_seq_value[31:24] <= axi_wdata_reg[31:24];
                      if (|axi_wstrb_reg)   stats_ack_seq_set          <= 1'b1;
                      end
                  AXI_REG_Z_SAFE_TRAVEL: begin
                      if (axi_wstrb_reg[0]) z_safe_travel_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) z_safe_travel_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) z_safe_travel_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) z_safe_travel_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_CALC_CONTROL: begin
                      // bit0 START (compute the selected bank), bit1 CLEAR (drop result),
                      // bit2 AVERAGE_PAIR (level: average this result with the previous
                      // one, so the forward/reverse combination happens in PL too).
                      if (axi_wstrb_reg[0]) begin
                          if (axi_wdata_reg[0]) mcalc_start_pulse <= 1'b1;
                          if (axi_wdata_reg[1]) mcalc_clear_pulse <= 1'b1;
                          mcalc_pair_enable_reg <= axi_wdata_reg[2];
                      end
                  end
                  AXI_REG_CALC_COEFF_K: begin
                      // K_q = round(K * 2^23) for the selected bank.  The PS must read
                      // this back and compare for equality before starting a compute
                      // (AGENTS.md numeric-gate rule).
                      if (axi_wstrb_reg[0]) mcalc_coeff_k_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) mcalc_coeff_k_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) mcalc_coeff_k_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) mcalc_coeff_k_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_CALC_MIN_COUNT: begin
                      // Phase C quality floor; 0 disables the check.
                      if (axi_wstrb_reg[0]) mcalc_min_count_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) mcalc_min_count_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) mcalc_min_count_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) mcalc_min_count_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  AXI_REG_CALC_MAX_SPAN: begin
                      // Phase C span ceiling; 0 disables the check.
                      if (axi_wstrb_reg[0]) mcalc_max_span_reg[7:0]  <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) mcalc_max_span_reg[15:8] <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) mcalc_max_span_reg[16]   <= axi_wdata_reg[16];
                  end
                  AXI_REG_CALC_COEFF_RS: begin
                      // K_rs = round(K_rs * 2^23); PS must read it back and compare for
                      // equality, and must also check K_rs == K_rho / W_cm.
                      if (axi_wstrb_reg[0]) mcalc_coeff_rs_reg[7:0]   <= axi_wdata_reg[7:0];
                      if (axi_wstrb_reg[1]) mcalc_coeff_rs_reg[15:8]  <= axi_wdata_reg[15:8];
                      if (axi_wstrb_reg[2]) mcalc_coeff_rs_reg[23:16] <= axi_wdata_reg[23:16];
                      if (axi_wstrb_reg[3]) mcalc_coeff_rs_reg[31:24] <= axi_wdata_reg[31:24];
                  end
                  default: begin
                      // Read-only and unimplemented writes are accepted.
                  end
              endcase
          end

          if (S_AXI_ARVALID && S_AXI_ARREADY) begin
              axi_rvalid_reg <= 1'b1;
              axi_rresp_reg  <= 2'b00;
              axi_rdata_reg  <= 32'd0;
              case (S_AXI_ARADDR[11:0])
                  AXI_REG_CONTROL: begin
                      axi_rdata_reg <= 32'd0;
                  end
                  AXI_REG_STATUS: begin
                      axi_rdata_reg       <= 32'd0;
                      axi_rdata_reg[4:0]  <= main_state;
                      axi_rdata_reg[8]    <= err_latch;
                      axi_rdata_reg[9]    <= cycle_done;
                      axi_rdata_reg[10]   <= x_busy;
                      axi_rdata_reg[11]   <= ena;
                      axi_rdata_reg[12]   <= step_pulse;
                      axi_rdata_reg[13]   <= x_pul_out;
                      axi_rdata_reg[14]   <= x_dir_out;
                      axi_rdata_reg[15]   <= dir;
                      axi_rdata_reg[16]   <= reset_latched;
                      axi_rdata_reg[17]   <= watchdog_tripped;
                      axi_rdata_reg[18]   <= watchdog_armed;
                      axi_rdata_reg[19]   <= motion_refused_sticky;
                  end
                  AXI_REG_INPUTS: begin
                      axi_rdata_reg <= {27'd0, x_trig_in, start, sensor, SDO0, RVS};
                  end
                  AXI_REG_OUTPUTS: begin
                      axi_rdata_reg <= {21'd0, cycle_done, err_flag, ena,
                                         x_dir_out, x_pul_out, step_pulse,
                                         dir, SCLK, CS, RST, SDI};
                  end
                  AXI_REG_VERSION: begin
                      axi_rdata_reg <= 32'h414C_5835;
                  end
                  AXI_REG_MEAS_CNT: begin
                      axi_rdata_reg <= {28'd0, meas_cnt};
                  end
                  AXI_REG_MAIN_STATE: begin
                      axi_rdata_reg <= {27'd0, main_state};
                  end
                  AXI_REG_ADC_RAW: begin
                      axi_rdata_reg <= RX_REG;
                  end
                  AXI_REG_RHO: begin
                      axi_rdata_reg <= rho;
                  end
                  AXI_REG_RS: begin
                      axi_rdata_reg <= Rs;
                  end
                  AXI_REG_R_CONTROL: begin
                      axi_rdata_reg <= {31'd0, r_busy};
                  end
                  AXI_REG_R_COMMAND: begin
                      axi_rdata_reg <= r_command_reg;
                  end
                  AXI_REG_R_TARGET: begin
                      axi_rdata_reg <= r_target_reg;
                  end
                  AXI_REG_R_STATUS: begin
                      axi_rdata_reg <= {26'd0,
                                        r_dir_out,
                                        r_homed,
                                        r_fault,
                                        (r_sensor_stable == 1'b0),
                                        r_done_reg,
                                        r_busy};
                  end
                  AXI_REG_R_POSITION: begin
                      axi_rdata_reg <= r_position;
                  end
                  AXI_REG_R_ERROR: begin
                      axi_rdata_reg <= {28'd0, r_error_code};
                  end
                  AXI_REG_Z_CONTROL: begin axi_rdata_reg <= {30'd0, z_driver_armed, z_direct_busy}; end
                  AXI_REG_Z_COMMAND: begin axi_rdata_reg <= z_command_reg; end
                  AXI_REG_Z_TARGET: begin axi_rdata_reg <= z_target_reg; end
                  AXI_REG_Z_STATUS: begin
                      axi_rdata_reg <= {24'd0,(meas_state==MEAS_STATE_DONE),meas_active,z_dir_reg,z_homed,z_fault,(sen_stable==0),z_done_reg,z_direct_busy};
                  end
                  AXI_REG_Z_POSITION: begin axi_rdata_reg <= z_position; end
                  AXI_REG_Z_ERROR: begin axi_rdata_reg <= {28'd0,z_error_code}; end
                  AXI_REG_M_CONTROL: begin axi_rdata_reg <= {31'd0,meas_active}; end
                  AXI_REG_M_STATUS: begin
                      axi_rdata_reg <= {27'd0,meas_source_legacy,(meas_error_code==MEAS_ERR_TIMEOUT),(meas_state==MEAS_STATE_ERROR),(meas_state==MEAS_STATE_DONE),meas_active};
                  end
                  AXI_REG_M_POINT: begin axi_rdata_reg <= meas_point_index_reg; end
                  AXI_REG_M_HOLD: begin axi_rdata_reg <= meas_hold_cycles_reg; end
                  AXI_REG_M_ERROR: begin axi_rdata_reg <= {29'd0,meas_error_code}; end
                  AXI_REG_X_TARGET: begin axi_rdata_reg <= x_target_reg; end
                  AXI_REG_X_STATUS: begin
                      axi_rdata_reg <= {29'd0, x_dir_out, x_done_reg, x_busy};
                  end
                  AXI_REG_X_POSITION: begin axi_rdata_reg <= x_position; end
                  AXI_REG_X_CONTROL: begin axi_rdata_reg <= {31'd0, x_busy}; end
                  AXI_REG_Z_STEP_INTERVAL: begin axi_rdata_reg <= z_step_interval_cycles; end
                  AXI_REG_Z_DECEL_CONTROL: begin
                      axi_rdata_reg <= {28'd0, z_decel_all_enable, z_decel_return_enable, z_decel_measure_enable, z_decel_enable};
                  end
                  AXI_REG_Z_DECEL_WINDOW: begin axi_rdata_reg <= z_decel_window_steps; end
                  AXI_REG_Z_DECEL_SEG_STEPS: begin axi_rdata_reg <= z_decel_seg_steps; end
                  AXI_REG_Z_DECEL_LUT_INDEX: begin axi_rdata_reg <= {27'd0, z_decel_lut_index}; end
                  AXI_REG_Z_DECEL_LUT_DATA: begin axi_rdata_reg <= z_decel_period_lut[z_decel_lut_index[3:0]]; end
                  AXI_REG_ANALOG_CONTROL: begin
                      axi_rdata_reg <= {21'd0, analog_state_reg, analog_current_en_reg,
                                        analog_current_req_reg, analog_polarity_reg,
                                        analog_range_sel_reg, analog_error, analog_done, analog_busy};
                  end
                  AXI_REG_ANALOG_TEST_CONTROL: begin
                      axi_rdata_reg <= {analog_test_enable, 22'd0, analog_test_current_en,
                                        2'd0, analog_test_relay_mask};
                  end
                  AXI_REG_DAC_CODE: begin axi_rdata_reg <= {16'd0, dac_code_reg}; end
                  AXI_REG_DAC_CONTROL: begin axi_rdata_reg <= 32'd0; end
                  AXI_REG_DAC_STATUS: begin
                      axi_rdata_reg <= {29'd0, dac_code_loaded, dac_done, dac_busy};
                  end
                  AXI_REG_DAC_SEQ: begin axi_rdata_reg <= {16'd0, dac_seq_reg}; end
                  AXI_REG_ANALOG_SEQ: begin axi_rdata_reg <= {16'd0, analog_seq_reg}; end
                  AXI_REG_ADC_CFG_SEQ: begin axi_rdata_reg <= {16'd0, adc_cfg_seq_reg}; end
                  AXI_REG_Z_HOME_STEPS: begin axi_rdata_reg <= z_home_step_cnt; end
                  AXI_REG_Z_TIMEOUT_CYCLES: begin axi_rdata_reg <= Z_TIMEOUT_CYCLES; end
                  AXI_REG_R_TIMEOUT_CYCLES: begin axi_rdata_reg <= R_TIMEOUT_CYCLES; end
                  AXI_REG_STATS_SUM_LOW: begin
                      axi_rdata_reg <= stats_sum_snapshot_sel[31:0];
                  end
                  AXI_REG_STATS_SUM_HIGH: begin
                      axi_rdata_reg <= stats_sum_snapshot_sel[63:32];
                  end
                  AXI_REG_STATS_VALID_COUNT: begin
                      axi_rdata_reg <= stats_valid_count_snapshot_sel;
                  end
                  AXI_REG_STATS_SUM_SQ_LOW: begin
                      axi_rdata_reg <= stats_sum_sq_snapshot_sel[31:0];
                  end
                  AXI_REG_STATS_SUM_SQ_HIGH: begin
                      axi_rdata_reg <= stats_sum_sq_snapshot_sel[63:32];
                  end
                  AXI_REG_STATS_RX_COUNT: begin
                      axi_rdata_reg <= stats_rx_count_snapshot_sel;
                  end
                  AXI_REG_STATS_MIN_CODE: begin
                      axi_rdata_reg <= {15'd0, stats_min_snapshot_sel};
                  end
                  AXI_REG_STATS_MAX_CODE: begin
                      axi_rdata_reg <= {15'd0, stats_max_snapshot_sel};
                  end
                  AXI_REG_STATS_SEQ: begin
                      axi_rdata_reg <= stats_seq_sel;
                  end
                  AXI_REG_STATS_FLAGS: begin
                      axi_rdata_reg <= {28'd0, stats_window_busy,
                                        stats_overflow_sel,
                                        stats_empty_sel,
                                        stats_ready_sel};
                  end
                  AXI_REG_STATS_BANK_SELECT: begin
                      axi_rdata_reg <= {29'd0, stats_bank_select};
                  end
                  AXI_REG_STATS_CENTER_CODE: begin
                      axi_rdata_reg <= {15'd0, stats_center_code[stats_bank_select]};
                  end
                  AXI_REG_STATS_MAG_MIN: begin
                      axi_rdata_reg <= {15'd0, stats_mag_min[stats_bank_select]};
                  end
                  AXI_REG_STATS_MAG_MAX: begin
                      axi_rdata_reg <= {15'd0, stats_mag_max[stats_bank_select]};
                  end
                  AXI_REG_STATS_CONTROL: begin
                      axi_rdata_reg <= {31'd0, stats_window_enable};
                  end
                  AXI_REG_WATCHDOG_COUNT: begin
                      // Watchdog counter in 50 MHz cycles (20 ns each).
                      axi_rdata_reg <= watchdog_cnt;
                  end
                  AXI_REG_STATS_ACK_SEQ: begin
                      axi_rdata_reg <= stats_ack_seq_pending ? stats_ack_seq_value : 32'd0;
                  end
                  AXI_REG_Z_SAFE_TRAVEL: begin
                      axi_rdata_reg <= z_safe_travel_reg;
                  end
                  AXI_REG_STATS_STATUS: begin
                      axi_rdata_reg <= {26'd0, stats_active_bank, stats_bank_select,
                                        stats_window_busy, stats_window_enable};
                  end
                  AXI_REG_CALC_STATUS: begin
                      axi_rdata_reg <= {27'd0, mcalc_quality_ok, mcalc_pair_valid,
                                        mcalc_result_valid, mcalc_done, mcalc_busy};
                  end
                  AXI_REG_CALC_RHO_LOW: begin
                      axi_rdata_reg <= mcalc_rho_q[31:0];
                  end
                  AXI_REG_CALC_RHO_HIGH: begin
                      axi_rdata_reg <= mcalc_rho_q[63:32];
                  end
                  AXI_REG_CALC_FLAGS: begin
                      axi_rdata_reg <= {24'd0, mcalc_flag_quality_wide_span,
                                        mcalc_flag_quality_low_count,
                                        mcalc_flag_pair_missing, mcalc_flag_negative,
                                        mcalc_flag_coeff_invalid,
                                        mcalc_flag_sum_overflow, mcalc_flag_count_over_max,
                                        mcalc_flag_zero_count};
                  end
                  AXI_REG_CALC_COEFF_K: begin
                      axi_rdata_reg <= mcalc_coeff_k_reg;
                  end
                  AXI_REG_CALC_COEFF_RS: begin
                      axi_rdata_reg <= mcalc_coeff_rs_reg;
                  end
                  AXI_REG_CALC_MIN_COUNT: begin
                      axi_rdata_reg <= mcalc_min_count_reg;
                  end
                  AXI_REG_CALC_MAX_SPAN: begin
                      axi_rdata_reg <= {15'd0, mcalc_max_span_reg};
                  end
                  AXI_REG_CALC_RS_LOW: begin
                      axi_rdata_reg <= mcalc_rs_q[31:0];
                  end
                  AXI_REG_CALC_RS_HIGH: begin
                      axi_rdata_reg <= mcalc_rs_q[63:32];
                  end
                  default: begin
                      axi_rdata_reg <= 32'd0;
                  end
              endcase
          end
      end
  end

  //=========================================================================
  // 11. System reset latch + PS heartbeat watchdog + sticky refusal flag
  //     -> hw/rtl/common/session_guard.v (2026-10-13).
  //     WATCHDOG_CYCLES stays declared here because the reset/watchdog testbench
  //     reads dut.WATCHDOG_CYCLES through the ALL_Final instance.
  //=========================================================================
  session_guard #(
      .WATCHDOG_CYCLES (WATCHDOG_CYCLES)
  ) u_session_guard (
      .clk                   (clk),
      .reset_n               (reset_n),
      .sys_reset_wr          (sys_reset_wr),
      .clr_faults_wr         (clr_faults_wr),
      .heartbeat_wr          (heartbeat_wr),
      .watchdog_disarm_wr    (watchdog_disarm_wr),
      .z_refused_now         (z_refused_now),
      .r_refused_now         (r_refused_now),
      .x_refused_now         (x_refused_now),
      .reset_latched         (reset_latched),
      .watchdog_tripped      (watchdog_tripped),
      .watchdog_armed        (watchdog_armed),
      .watchdog_cnt          (watchdog_cnt),
      .motion_refused_sticky (motion_refused_sticky)
  );

  //=========================================================================
  // 12. Motion inhibit tracker (2026-10-11)
  //=========================================================================
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) motion_latch_d <= 1'b0;
      else          motion_latch_d <= motion_latch_now;
  end


  // 12b. Lateral-motion safety height + sticky motion-refusal flag
  //      The sticky flag itself moved into hw/rtl/common/session_guard.v;
  //      z_safe_travel_reg (the height threshold) stays here - it is
  //      AXI-written configuration and z_probe_clear is computed from it.


endmodule    //ALL_Final
