// One forward window followed by one reverse window; no repeated sequence.
// FULL pilots ranges; VERIFY checks the acquired pair and reselects on drift.
// Safety/reset/ownership checks and current-off exits are retained.






































module fpd_autorange #(
    parameter integer TICK_CYCLES = 50000,   
    parameter integer POLL_CYCLES = 64       
) (
    input  wire          clk,
    input  wire          rst_n,

    
    input  wire          cmd_start,
    input  wire          cmd_abort,
    input  wire          cmd_clear,
    input  wire          cmd_claim,
    input  wire          cmd_release,
    input  wire [1:0]    cmd_mode,          
    input  wire [1:0]    cmd_range,         

    
    input  wire [3:0]    cfg_range_mask,
    input  wire [15:0]   cfg_s_hi,           
    input  wire [15:0]   cfg_s_lo,           
    input  wire [15:0]   cfg_raw_sat,        
    input  wire [15:0]   cfg_lin_min,        
    input  wire [15:0]   cfg_open_vmax,      
    input  wire [15:0]   cfg_noise_floor,    
    input  wire [23:0]   cfg_lin_tol_q16,
    input  wire [23:0]   cfg_open_iratio_q16,
    input  wire [23:0]   cfg_open_vratio_q16,
    input  wire [23:0]   cfg_hyst_q16,
    input  wire [23:0]   cfg_eps_rel_q16,
    input  wire [15:0]   cfg_eps_abs_q8,
    input  wire [15:0]   cfg_pilot_win_ms,
    input  wire [15:0]   cfg_meas_win_ms,
    input  wire [3:0]    cfg_pair_mode,    
    input  wire [15:0]   cfg_t_min_ms,
    input  wire [15:0]   cfg_t_max_ms,
    input  wire [15:0]   cfg_warmup_ms,
    input  wire [15:0]   cfg_t_skip_ms,
    input  wire [15:0]   cfg_seg_ms,
    input  wire [3:0]    cfg_settle_k,
    input  wire [15:0]   cfg_cfg_timeout_ms,
    input  wire          cfg_settle_enable,
    input  wire          cfg_reinit,
    input  wire [127:0]  cfg_center_flat,    
    input  wire [111:0]  cfg_if_flat,        
    input  wire [111:0]  cfg_ir_flat,        

    
    input  wire          smp_valid,
    input  wire [15:0]   smp_code,
    input  wire [3:0]    pin_range,
    input  wire          pin_pol_i,
    input  wire          pin_pol_v,
    input  wire          pin_current_en,

    
    output reg           m_valid,
    output reg           m_write,
    output reg  [11:0]   m_addr,
    output reg  [31:0]   m_wdata,
    input  wire          m_busy,
    input  wire          m_done,
    input  wire          m_err,
    input  wire          m_hung,
    input  wire [31:0]   m_rdata,

    
    output reg           busy,
    output reg           done,
    output reg           error,
    output reg           owned,
    output reg           result_valid,
    output reg  [5:0]    state,
    output reg  [7:0]    reason,
    output reg  [7:0]    flags,
    output reg  [31:0]   mismatch_count,

    
    output wire          meas_add,
    output wire          meas_pol,
    output wire signed [17:0] meas_delta,
    output wire          meas_clear,         
    
    output wire          meas_tick,
    output wire          meas_win_active,
    output wire          meas_win_bnd,

    
    input  wire [5:0]    res_addr,
    output reg  [31:0]   res_data
);

  
  localparam [11:0] AF_CONTROL        = 12'h000;  
  localparam [11:0] AF_STATUS         = 12'h004;  
  localparam [11:0] AF_ANALOG_CONTROL = 12'h0D0;
  localparam [11:0] AF_ANALOG_SEQ     = 12'h0E8;
  localparam [11:0] AF_ADC_CFG_SEQ    = 12'h0EC;
  localparam [31:0] AF_ANALOG_ABORT   = 32'h0000_0002;

  
  localparam [7:0] R_OK                   = 8'd0;
  localparam [7:0] R_OK_TOP               = 8'd1;
  localparam [7:0] R_OK_SAT_BACKOFF       = 8'd2;
  localparam [7:0] R_OK_NONLINEAR_BACKOFF = 8'd3;
  localparam [7:0] R_OPEN_LOOP            = 8'd8;
  localparam [7:0] R_OVER_RANGE_AT_MIN    = 8'd9;
  localparam [7:0] R_NO_SAMPLES           = 8'd10;
  localparam [7:0] R_ANALOG_SEQ_ERROR     = 8'd11;
  localparam [7:0] R_SAFETY_ABORT         = 8'd12;
  localparam [7:0] R_OWNERSHIP_CONFLICT   = 8'd13;
  localparam [7:0] R_PS_ABORT             = 8'd14;
  localparam [7:0] R_AXI_ERROR            = 8'd15;
  localparam [7:0] R_CONFIG_ERROR         = 8'd16;

  
  localparam [7:0] F_LOW_SIGNAL          = 8'h01;
  localparam [7:0] F_ABOVE_TARGET_AT_MIN = 8'h02;
  localparam [7:0] F_RERANGED            = 8'h04;
  localparam [7:0] F_SETTLE_TIMEOUT      = 8'h08;

  localparam [1:0] MODE_FULL   = 2'd0;
  localparam [1:0] MODE_VERIFY = 2'd1;
  localparam [1:0] MODE_FORCED = 2'd2;

  localparam PH_PILOT = 1'b0;
  localparam PH_MEAS  = 1'b1;

  localparam [5:0] S_IDLE       = 6'd0,
                   S_CAP_BEGIN  = 6'd1,
                   S_CAP_STAT   = 6'd2,
                   S_CAP_SEQ0   = 6'd3,
                   S_CAP_WCTL   = 6'd4,
                   S_CAP_POLL   = 6'd5,
                   S_CAP_POLLW  = 6'd6,
                   S_CAP_CHK    = 6'd7,
                   S_CAP_ADC0   = 6'd8,
                   S_CAP_ADCW   = 6'd9,
                   S_CAP_ADCP   = 6'd10,
                   S_CAP_ADCPW  = 6'd11,
                   S_SETTLE     = 6'd12,
                   S_SEG_DIV    = 6'd13,
                   S_SEG_MUL    = 6'd14,
                   S_SEG_CMP    = 6'd15,
                   S_INT        = 6'd16,
                   S_WIN_DIV    = 6'd17,
                   S_WIN_STAT   = 6'd18,
                   S_WIN_DONE   = 6'd19,
                   S_EVAL0      = 6'd20,
                   S_EVAL1      = 6'd21,
                   S_EV_O1      = 6'd22,
                   S_EV_O2      = 6'd23,
                   S_EV_OC      = 6'd24,
                   S_EV_L1      = 6'd25,
                   S_EV_L2      = 6'd26,
                   S_EV_L3      = 6'd27,
                   S_EV_L4      = 6'd28,
                   S_EV_LC      = 6'd29,
                   S_EV_N1      = 6'd30,
                   S_EV_N2      = 6'd31,
                   S_EV_NC      = 6'd32,
                   S_VER0       = 6'd33,
                   S_VER_V1     = 6'd34,
                   S_VER_V1C    = 6'd35,
                   S_VER_V2     = 6'd36,
                   S_VER_V3     = 6'd37,
                   S_VER_V4     = 6'd38,
                   S_VER_C      = 6'd39,
                   S_FIN_F      = 6'd40,
                   S_FIN_R      = 6'd41,
                   S_FIN_PAIR   = 6'd42,
                   S_SAFE_WAIT  = 6'd43,
                   S_SAFE_OFFW  = 6'd44,
                   S_PINFAIL    = 6'd45,
                   S_PINFAIL_W  = 6'd46,
                   S_END        = 6'd47,
                   S_CAP_ISSUE  = 6'd48,
                   S_EV_OPEN0   = 6'd49;

  
  
  
  function [1:0] lowest_of;
      input [3:0] m;
      begin
          if (m[0])      lowest_of = 2'd0;
          else if (m[1]) lowest_of = 2'd1;
          else if (m[2]) lowest_of = 2'd2;
          else           lowest_of = 2'd3;
      end
  endfunction

  
  function [2:0] next_of;
      input [3:0] m;
      input [1:0] r;
      begin
          next_of = 3'b000;
          if (r == 2'd0) begin
              if (m[1])      next_of = 3'b101;
              else if (m[2]) next_of = 3'b110;
              else if (m[3]) next_of = 3'b111;
          end else if (r == 2'd1) begin
              if (m[2])      next_of = 3'b110;
              else if (m[3]) next_of = 3'b111;
          end else if (r == 2'd2) begin
              if (m[3])      next_of = 3'b111;
          end
      end
  endfunction

  function [31:0] abs32;
      input [31:0] x;
      begin
          abs32 = x[31] ? (~x + 32'd1) : x;
      end
  endfunction

  
  
  
  wire [28:0] isum0 = {1'b0, cfg_if_flat[ 0 +: 28]} + {1'b0, cfg_ir_flat[ 0 +: 28]};
  wire [28:0] isum1 = {1'b0, cfg_if_flat[28 +: 28]} + {1'b0, cfg_ir_flat[28 +: 28]};
  wire [28:0] isum2 = {1'b0, cfg_if_flat[56 +: 28]} + {1'b0, cfg_ir_flat[56 +: 28]};
  wire [28:0] isum3 = {1'b0, cfg_if_flat[84 +: 28]} + {1'b0, cfg_ir_flat[84 +: 28]};
  wire [115:0] isum_flat = {isum3, isum2, isum1, isum0};

  wire [23:0] hi8  = {cfg_s_hi, 8'd0};
  wire [23:0] lo8  = {cfg_s_lo, 8'd0};
  wire [23:0] sat8 = {cfg_raw_sat, 8'd0};
  wire [23:0] lm8  = {cfg_lin_min, 8'd0};
  wire [23:0] ov8  = {cfg_open_vmax, 8'd0};
  wire [23:0] nf8  = {cfg_noise_floor, 8'd0};

  wire [3:0] cur_ok = {(isum3 != 29'd0), (isum2 != 29'd0), (isum1 != 29'd0), (isum0 != 29'd0)};
  wire       currents_ok = &(~cfg_range_mask | cur_ok);
  wire       cfg_ok = (cfg_range_mask != 4'd0) && currents_ok &&
                      (cfg_pilot_win_ms != 16'd0) && (cfg_meas_win_ms != 16'd0) &&
                      (cfg_seg_ms != 16'd0) && (cfg_t_max_ms != 16'd0) &&
                      (cfg_t_min_ms <= cfg_t_max_ms) &&
                      (cfg_pair_mode == 4'd1) &&
                      (cfg_cfg_timeout_ms != 16'd0) &&
                      (cmd_mode != 2'd3) &&
                      ((cmd_mode == MODE_FULL) || cfg_range_mask[cmd_range]);
  localparam [4:0] two_n = 5'd1;

  
  
  
  reg [31:0] tick_cnt;
  reg        ms_tick;
  always @(posedge clk) begin
      if (!rst_n) begin
          tick_cnt <= 32'd0;
          ms_tick  <= 1'b0;
      end else if (tick_cnt >= TICK_CYCLES - 1) begin
          tick_cnt <= 32'd0;
          ms_tick  <= 1'b1;
      end else begin
          tick_cnt <= tick_cnt + 32'd1;
          ms_tick  <= 1'b0;
      end
  end

  
  
  
  reg        pin_watch;       
  reg [1:0]  cap_range;
  reg        cap_pol;
  reg        phase;
  reg        seg_run;
  reg        seg_restart;     
  reg        seg_ack;         
  reg        win_start;       
  reg        win_stop;        
  reg        win_ack;         
  reg [1:0]  win_nwin;
  reg [15:0] win_len_ms;
  reg        agg_clear;       

  wire pins_ok = pin_current_en &&
                 (pin_range == (4'b0001 << cap_range)) &&
                 (pin_pol_i == cap_pol) && (pin_pol_v == cap_pol);
  wire [15:0] center_sel = cfg_center_flat[{cap_pol, cap_range}*16 +: 16];

  
  
  
  reg        s_pend;
  reg [15:0] s_code;
  reg [31:0] s_sq;
  reg        s_ok;
  reg        s_bad;

  always @(posedge clk) begin
      if (!rst_n) begin
          s_pend <= 1'b0;
          s_code <= 16'd0;
          s_sq   <= 32'd0;
          s_ok   <= 1'b0;
          s_bad  <= 1'b0;
      end else begin
          s_pend <= smp_valid;
          if (smp_valid) begin
              s_code <= smp_code;
              s_sq   <= smp_code * smp_code;
              s_ok   <= pin_watch && pins_ok;
              s_bad  <= pin_watch && !pins_ok;
          end
      end
  end

  wire signed [17:0] s_delta = $signed({2'b00, s_code}) - $signed({2'b00, center_sel});
  wire signed [47:0] s_dext  = {{30{s_delta[17]}}, s_delta};
  wire               s_add   = s_pend && s_ok;

  reg signed [47:0] seg_sum;
  reg        [31:0] seg_n;
  reg        [15:0] seg_ms_cnt;
  reg signed [47:0] seg_snap_sum;
  reg        [31:0] seg_snap_n;
  reg               seg_ready;

  reg signed [47:0] win_sum;
  reg        [31:0] win_n;
  reg        [15:0] win_ms_cnt;
  reg        [1:0]  win_left;
  reg               win_active;
  reg signed [47:0] win_snap_sum;
  reg        [31:0] win_snap_n;
  reg               win_ready;

  reg [47:0] agg_sum   [0:1];
  reg [63:0] agg_sumsq [0:1];
  reg [31:0] agg_n     [0:1];
  reg [15:0] agg_min   [0:1];
  reg [15:0] agg_max   [0:1];

  wire seg_add = s_add && seg_run;
  wire signed [47:0] seg_sum_nx = seg_sum + (seg_add ? s_dext : 48'sd0);
  wire        [31:0] seg_n_nx   = seg_n + (seg_add ? 32'd1 : 32'd0);
  wire seg_bnd = seg_run && ms_tick && (seg_ms_cnt >= cfg_seg_ms - 16'd1);

  wire win_add = s_add && win_active;

  assign meas_add   = win_add && (phase == PH_MEAS);
  assign meas_pol   = cap_pol;
  assign meas_delta = s_delta;
  assign meas_clear = agg_clear;
  wire signed [47:0] win_sum_nx = win_sum + (win_add ? s_dext : 48'sd0);
  wire        [31:0] win_n_nx   = win_n + (win_add ? 32'd1 : 32'd0);
  wire win_bnd = win_active && ms_tick && (win_ms_cnt >= win_len_ms - 16'd1);

  assign meas_tick       = ms_tick;
  assign meas_win_active = win_active && (phase == PH_MEAS);
  assign meas_win_bnd    = win_bnd && (phase == PH_MEAS);

  always @(posedge clk) begin
      if (!rst_n) begin
          seg_sum      <= 48'sd0;
          seg_n        <= 32'd0;
          seg_ms_cnt   <= 16'd0;
          seg_snap_sum <= 48'sd0;
          seg_snap_n   <= 32'd0;
          seg_ready    <= 1'b0;
      end else begin
          if (seg_ack) seg_ready <= 1'b0;
          if (seg_restart || !seg_run) begin
              seg_sum    <= 48'sd0;
              seg_n      <= 32'd0;
              seg_ms_cnt <= 16'd0;
              if (seg_restart) seg_ready <= 1'b0;
          end else if (seg_bnd) begin
              seg_snap_sum <= seg_sum_nx;
              seg_snap_n   <= seg_n_nx;
              seg_ready    <= 1'b1;
              seg_sum      <= 48'sd0;
              seg_n        <= 32'd0;
              seg_ms_cnt   <= 16'd0;
          end else begin
              seg_sum <= seg_sum_nx;
              seg_n   <= seg_n_nx;
              if (ms_tick) seg_ms_cnt <= seg_ms_cnt + 16'd1;
          end
      end
  end

  always @(posedge clk) begin
      if (!rst_n) begin
          win_sum      <= 48'sd0;
          win_n        <= 32'd0;
          win_ms_cnt   <= 16'd0;
          win_left     <= 2'd0;
          win_active   <= 1'b0;
          win_snap_sum <= 48'sd0;
          win_snap_n   <= 32'd0;
          win_ready    <= 1'b0;
      end else begin
          if (win_ack) win_ready <= 1'b0;
          if (win_stop) begin
              win_active <= 1'b0;
              win_ready  <= 1'b0;
          end else if (win_start) begin
              win_active <= 1'b1;
              win_left   <= win_nwin;
              win_sum    <= 48'sd0;
              win_n      <= 32'd0;
              win_ms_cnt <= 16'd0;
              win_ready  <= 1'b0;
          end else if (win_active) begin
              if (win_bnd) begin
                  win_snap_sum <= win_sum_nx;
                  win_snap_n   <= win_n_nx;
                  win_ready    <= 1'b1;
                  win_sum      <= 48'sd0;
                  win_n        <= 32'd0;
                  win_ms_cnt   <= 16'd0;
                  win_left     <= win_left - 2'd1;
                  if (win_left == 2'd1) win_active <= 1'b0;
              end else begin
                  win_sum <= win_sum_nx;
                  win_n   <= win_n_nx;
                  if (ms_tick) win_ms_cnt <= win_ms_cnt + 16'd1;
              end
          end
      end
  end

  
  
  integer ai;
  always @(posedge clk) begin
      if (!rst_n || agg_clear) begin
          for (ai = 0; ai < 2; ai = ai + 1) begin
              agg_sum[ai]   <= 48'd0;
              agg_sumsq[ai] <= 64'd0;
              agg_n[ai]     <= 32'd0;
              agg_min[ai]   <= 16'hFFFF;
              agg_max[ai]   <= 16'd0;
          end
      end else if (win_add && (phase == PH_MEAS)) begin
          agg_sum[cap_pol]   <= agg_sum[cap_pol] + {32'd0, s_code};
          agg_sumsq[cap_pol] <= agg_sumsq[cap_pol] + {32'd0, s_sq};
          agg_n[cap_pol]     <= agg_n[cap_pol] + 32'd1;
          if (s_code < agg_min[cap_pol]) agg_min[cap_pol] <= s_code;
          if (s_code > agg_max[cap_pol]) agg_max[cap_pol] <= s_code;
      end
  end

  always @(posedge clk) begin
      if (!rst_n)
          mismatch_count <= 32'd0;
      else if (s_pend && s_bad && (mismatch_count != 32'hFFFF_FFFF))
          mismatch_count <= mismatch_count + 32'd1;
  end

  
  
  
  reg  signed [39:0] mul_a;
  reg  signed [39:0] mul_b;
  wire signed [79:0] mul_p;
  reg                mul_pend;
  reg         [2:0]  mul_cnt;
  fpd_mul u_mul (.clk(clk), .a(mul_a), .b(mul_b), .p(mul_p));
  wire mul_ready = mul_pend && (mul_cnt == 3'd4);

  reg         div_start;
  reg  [55:0] div_num;
  reg  [31:0] div_den;
  reg         div_neg;
  reg         div_issued;
  wire        div_busy;
  wire        div_done;
  wire [55:0] div_quo;
  fpd_div #(.NW(56), .DW(32)) u_div (
      .clk(clk), .rst_n(rst_n), .start(div_start), .num(div_num), .den(div_den),
      .busy(div_busy), .done(div_done), .quo(div_quo));
  
  wire [31:0] div_mag = div_quo[31:0];
  wire [31:0] div_res = div_neg ? (~div_mag + 32'd1) : div_mag;

  
  
  
  reg        run_failed;
  reg [7:0]  fail_reason;
  reg [1:0]  run_mode;
  reg [3:0]  tested;
  reg [1:0]  sel_range;
  reg [1:0]  cur_i;
  reg        j_valid;
  reg [1:0]  j_idx;
  reg [31:0] s_j;
  reg [31:0] abs_j;
  reg        f_valid;         
  reg [1:0]  f_idx;
  reg [31:0] abs_f;
  reg [7:0]  pend_reason;     
  reg [31:0] s_max;
  reg [31:0] mf_cur;
  reg [31:0] mr_cur;
  reg [31:0] s_i;
  reg [31:0] abs_i;
  reg [31:0] p_i;
  reg        n_valid;
  reg [1:0]  n_idx;
  reg [1:0]  cap_nwin;
  reg [1:0]  seg_wins_done;
  reg [4:0]  seg_idx;
  reg        first_meas_seg;
  reg        verify_pending;
  reg [15:0] elapsed_ms;
  reg [15:0] tmo_ms;
  reg [15:0] seq0;
  reg [15:0] aseq0;
  reg [7:0]  poll_cnt;
  reg        have_prev;
  reg [31:0] m_prev;
  reg [31:0] m_now;
  reg [3:0]  consec;
  reg [15:0] settle_ms_now;
  reg [31:0] wm;
  reg [31:0] lat_win_n;
  reg [39:0] wm_sum_f;
  reg [39:0] wm_sum_r;
  reg [4:0]  wins_f;
  reg [4:0]  wins_r;
  reg        have_first_f;
  reg [31:0] mf_first;
  reg [31:0] mf_last;
  reg [31:0] mf_avg;
  reg [31:0] mr_avg;
  reg [31:0] s_meas;
  reg [31:0] e_meas;
  reg [15:0] meas_settle_max;
  reg [15:0] settle_timeouts;
  reg [31:0] run_ms;
  reg signed [79:0] p_a;
  reg signed [79:0] p_b;
  reg signed [79:0] p_c;

  reg [31:0] pr_mf     [0:3];
  reg [31:0] pr_mr     [0:3];
  reg [15:0] pr_set_f  [0:3];
  reg [15:0] pr_set_r  [0:3];
  reg [15:0] pr_n_f    [0:3];
  reg [15:0] pr_n_r    [0:3];

  wire [28:0] isum_cur = isum_flat[cur_i * 29 +: 29];
  wire [28:0] isum_j   = isum_flat[j_idx * 29 +: 29];
  wire [28:0] isum_f   = isum_flat[f_idx * 29 +: 29];
  wire [28:0] isum_n   = isum_flat[n_idx * 29 +: 29];
  wire [28:0] isum_sel = isum_flat[sel_range * 29 +: 29];
  wire [1:0]  lowest   = lowest_of(cfg_range_mask);
  wire [15:0] t_min_eff = (first_meas_seg && (cfg_warmup_ms > cfg_t_min_ms))
                          ? cfg_warmup_ms : cfg_t_min_ms;

  wire in_fail_path = (state == S_SAFE_WAIT) || (state == S_SAFE_OFFW) ||
                      (state == S_PINFAIL)   || (state == S_PINFAIL_W) ||
                      (state == S_END)       || (state == S_IDLE);

  
  wire [32:0] pair_sum  = {mf_cur[31], mf_cur} + {mr_cur[31], mr_cur};
  
  wire [39:0] wm_sum_f_nx = wm_sum_f + {{8{wm[31]}}, wm};
  wire [31:0] amf       = abs32(mf_cur);
  wire [31:0] amr       = abs32(mr_cur);
  wire [32:0] ver_sum   = {mf_first[31], mf_first} + {wm[31], wm};
  wire [31:0] avf       = abs32(mf_first);
  wire [31:0] avr       = abs32(wm);

  
  function [7:0] flags_for;
      input [1:0]  r;
      input [31:0] a;
      input [1:0]  low;
      input [23:0] lo;
      input [23:0] hi;
      begin
          flags_for = 8'h00;
          if (a < {8'd0, lo})              flags_for = flags_for | F_LOW_SIGNAL;
          if ((r == low) && (a > {8'd0, hi})) flags_for = flags_for | F_ABOVE_TARGET_AT_MIN;
      end
  endfunction

  
  task issue_rd;
      input [11:0] addr;
      begin
          m_valid <= 1'b1;
          m_write <= 1'b0;
          m_addr  <= addr;
          m_wdata <= 32'd0;
      end
  endtask

  task issue_wr;
      input [11:0] addr;
      input [31:0] data;
      begin
          m_valid <= 1'b1;
          m_write <= 1'b1;
          m_addr  <= addr;
          m_wdata <= data;
      end
  endtask

  task go_fail;
      input [7:0] r;
      begin
          fail_reason <= r;
          run_failed  <= 1'b1;
          pin_watch   <= 1'b0;
          seg_run     <= 1'b0;
          win_stop    <= 1'b1;
          mul_pend    <= 1'b0;
          div_issued  <= 1'b0;
          state       <= S_SAFE_WAIT;
      end
  endtask

  
  task begin_capture;
      input [1:0] r;
      input       pol;
      input [1:0] nwin;
      begin
          cap_range     <= r;
          cap_pol       <= pol;
          cap_nwin      <= nwin;
          seg_wins_done <= 2'd0;
          pin_watch     <= 1'b0;
          state         <= S_CAP_BEGIN;
      end
  endtask

  
  
  
  task begin_measurement;
      input [1:0] r;
      input       warm;
      begin
          phase          <= PH_MEAS;
          sel_range      <= r;
          seg_idx        <= 5'd0;
          first_meas_seg <= warm;
          agg_clear      <= 1'b1;
          wm_sum_f       <= 40'd0;
          wm_sum_r       <= 40'd0;
          wins_f         <= 5'd0;
          wins_r         <= 5'd0;
          have_first_f   <= 1'b0;
          win_len_ms     <= cfg_meas_win_ms;
          begin_capture(r, 1'b0, 2'd1);
      end
  endtask

  task finish_pair;
      begin
          div_num <= {16'd0, (wm_sum_f[39] ? (~wm_sum_f + 40'd1) : wm_sum_f)};
          div_den <= 32'd1;
          div_neg <= wm_sum_f[39];
          div_issued <= 1'b0;
          pin_watch <= 1'b0;
          state <= S_FIN_F;
      end
  endtask

  task begin_full_pilot;
      begin
          phase          <= PH_PILOT;
          tested         <= 4'd0;
          j_valid        <= 1'b0;
          f_valid        <= 1'b0;
          s_max          <= 32'd0;
          cur_i          <= lowest;
          first_meas_seg <= 1'b0;
          agg_clear      <= 1'b1;
          win_len_ms     <= cfg_pilot_win_ms;
          begin_capture(lowest, 1'b0, 2'd1);
      end
  endtask

  task start_integrate;
      begin
          seg_run       <= 1'b0;
          settle_ms_now <= elapsed_ms;
          win_nwin      <= cap_nwin;
          win_start     <= 1'b1;
          if (phase == PH_MEAS && elapsed_ms > meas_settle_max)
              meas_settle_max <= elapsed_ms;
          state         <= S_INT;
      end
  endtask

  
  
  
  integer pi;
  always @(posedge clk) begin
      if (!rst_n) begin
          state           <= S_IDLE;
          busy            <= 1'b0;
          done            <= 1'b0;
          error           <= 1'b0;
          owned           <= 1'b0;
          result_valid    <= 1'b0;
          reason          <= 8'd0;
          flags           <= 8'd0;
          run_failed      <= 1'b0;
          fail_reason     <= 8'd0;
          run_mode        <= 2'd0;
          tested          <= 4'd0;
          sel_range       <= 2'd0;
          cur_i           <= 2'd0;
          j_valid         <= 1'b0;
          j_idx           <= 2'd0;
          s_j             <= 32'd0;
          abs_j           <= 32'd0;
          f_valid         <= 1'b0;
          f_idx           <= 2'd0;
          abs_f           <= 32'd0;
          pend_reason     <= 8'd0;
          s_max           <= 32'd0;
          mf_cur          <= 32'd0;
          mr_cur          <= 32'd0;
          s_i             <= 32'd0;
          abs_i           <= 32'd0;
          p_i             <= 32'd0;
          n_valid         <= 1'b0;
          n_idx           <= 2'd0;
          cap_range       <= 2'd0;
          cap_pol         <= 1'b0;
          cap_nwin        <= 2'd1;
          seg_wins_done   <= 2'd0;
          seg_idx         <= 5'd0;
          first_meas_seg  <= 1'b0;
          verify_pending  <= 1'b0;
          phase           <= PH_PILOT;
          pin_watch       <= 1'b0;
          elapsed_ms      <= 16'd0;
          tmo_ms          <= 16'd0;
          seq0            <= 16'd0;
          aseq0           <= 16'd0;
          poll_cnt        <= 8'd0;
          have_prev       <= 1'b0;
          m_prev          <= 32'd0;
          m_now           <= 32'd0;
          consec          <= 4'd0;
          settle_ms_now   <= 16'd0;
          wm              <= 32'd0;
          lat_win_n       <= 32'd0;
          wm_sum_f        <= 40'd0;
          wm_sum_r        <= 40'd0;
          wins_f          <= 5'd0;
          wins_r          <= 5'd0;
          have_first_f    <= 1'b0;
          mf_first        <= 32'd0;
          mf_last         <= 32'd0;
          mf_avg          <= 32'd0;
          mr_avg          <= 32'd0;
          s_meas          <= 32'd0;
          e_meas          <= 32'd0;
          meas_settle_max <= 16'd0;
          settle_timeouts <= 16'd0;
          run_ms          <= 32'd0;
          seg_run         <= 1'b0;
          seg_restart     <= 1'b0;
          seg_ack         <= 1'b0;
          win_start       <= 1'b0;
          win_stop        <= 1'b0;
          win_ack         <= 1'b0;
          win_nwin        <= 2'd1;
          win_len_ms      <= 16'd1;
          agg_clear       <= 1'b0;
          m_valid         <= 1'b0;
          m_write         <= 1'b0;
          m_addr          <= 12'd0;
          m_wdata         <= 32'd0;
          mul_a           <= 40'sd0;
          mul_b           <= 40'sd0;
          mul_pend        <= 1'b0;
          mul_cnt         <= 3'd0;
          p_a             <= 80'sd0;
          p_b             <= 80'sd0;
          p_c             <= 80'sd0;
          div_start       <= 1'b0;
          div_num         <= 56'd0;
          div_den         <= 32'd0;
          div_neg         <= 1'b0;
          div_issued      <= 1'b0;
          for (pi = 0; pi < 4; pi = pi + 1) begin
              pr_mf[pi]    <= 32'd0;
              pr_mr[pi]    <= 32'd0;
              pr_set_f[pi] <= 16'd0;
              pr_set_r[pi] <= 16'd0;
              pr_n_f[pi]   <= 16'd0;
              pr_n_r[pi]   <= 16'd0;
          end
      end else begin
          
          m_valid     <= 1'b0;
          seg_restart <= 1'b0;
          seg_ack     <= 1'b0;
          win_start   <= 1'b0;
          win_stop    <= 1'b0;
          win_ack     <= 1'b0;
          agg_clear   <= 1'b0;
          div_start   <= 1'b0;

          if (mul_pend && mul_cnt != 3'd4) mul_cnt <= mul_cnt + 3'd1;
          if (busy && ms_tick && run_ms != 32'hFFFF_FFFF) run_ms <= run_ms + 32'd1;
          if (pin_watch && ms_tick && elapsed_ms != 16'hFFFF) elapsed_ms <= elapsed_ms + 16'd1;
          if (ms_tick && tmo_ms != 16'hFFFF) tmo_ms <= tmo_ms + 16'd1;

          if (busy && !in_fail_path && cmd_abort) begin
              go_fail(R_PS_ABORT);
          end else if (busy && !in_fail_path && pin_watch && !pins_ok) begin
              
              
              pin_watch  <= 1'b0;
              seg_run    <= 1'b0;
              win_stop   <= 1'b1;
              mul_pend   <= 1'b0;
              div_issued <= 1'b0;
              state      <= S_PINFAIL;
          end else begin
              case (state)
              
              S_IDLE: begin
                  busy <= 1'b0;
                  if (cmd_claim)   owned <= 1'b1;
                  if (cmd_release) owned <= 1'b0;
                  if (cmd_clear) begin
                      done         <= 1'b0;
                      error        <= 1'b0;
                      result_valid <= 1'b0;
                      reason       <= R_OK;
                      flags        <= 8'h00;
                  end
                  if (cmd_start) begin
                      done         <= 1'b0;
                      error        <= 1'b0;
                      result_valid <= 1'b0;
                      reason       <= R_OK;
                      flags        <= 8'h00;
                      run_failed   <= 1'b0;
                      fail_reason  <= R_OK;
                      run_mode     <= cmd_mode;
                      run_ms       <= 32'd0;
                      meas_settle_max <= 16'd0;
                      settle_timeouts <= 16'd0;
                      tested       <= 4'd0;
                      s_meas       <= 32'd0;
                      e_meas       <= 32'd0;
                      mf_avg       <= 32'd0;
                      mr_avg       <= 32'd0;
                      mf_first     <= 32'd0;
                      mf_last      <= 32'd0;
                      for (pi = 0; pi < 4; pi = pi + 1) begin
                          pr_mf[pi]    <= 32'd0;
                          pr_mr[pi]    <= 32'd0;
                          pr_set_f[pi] <= 16'd0;
                          pr_set_r[pi] <= 16'd0;
                          pr_n_f[pi]   <= 16'd0;
                          pr_n_r[pi]   <= 16'd0;
                      end
                      if (!owned || !cfg_ok || m_hung) begin
                          
                          done   <= 1'b1;
                          error  <= 1'b1;
                          reason <= m_hung ? R_AXI_ERROR : R_CONFIG_ERROR;
                      end else begin
                          busy <= 1'b1;
                          if (cmd_mode == MODE_FULL) begin
                              verify_pending <= 1'b0;
                              begin_full_pilot;
                          end else begin
                              verify_pending <= (cmd_mode == MODE_VERIFY);
                              begin_measurement(cmd_range, 1'b0);
                          end
                      end
                  end
              end

              
              S_CAP_BEGIN: begin
                  pin_watch <= 1'b0;
                  if (!m_busy) begin
                      issue_rd(AF_STATUS);
                      state <= S_CAP_STAT;
                  end
              end

              S_CAP_STAT: begin
                  if (m_done) begin
                      if (m_err)
                          go_fail(R_AXI_ERROR);
                      else if (m_rdata[16] || m_rdata[17])
                          go_fail(R_SAFETY_ABORT);
                      else begin
                          issue_rd(AF_ANALOG_SEQ);
                          state <= S_CAP_SEQ0;
                      end
                  end
              end

              S_CAP_SEQ0: begin
                  if (m_done) begin
                      if (m_err) go_fail(R_AXI_ERROR);
                      else begin
                          seq0  <= m_rdata[15:0];
                          state <= S_CAP_ISSUE;
                      end
                  end
              end

              S_CAP_ISSUE: begin
                  
                  
                  issue_wr(AF_ANALOG_CONTROL,
                           {26'd0, cap_pol, cap_range, 1'b1, 1'b0, 1'b1});
                  state <= S_CAP_WCTL;
              end

              S_CAP_WCTL: begin
                  if (m_done) begin
                      if (m_err) go_fail(R_AXI_ERROR);
                      else begin
                          tmo_ms   <= 16'd0;
                          poll_cnt <= 8'd0;
                          state    <= S_CAP_POLL;
                      end
                  end
              end

              S_CAP_POLL: begin
                  if (tmo_ms >= cfg_cfg_timeout_ms)
                      go_fail(R_ANALOG_SEQ_ERROR);
                  else if (poll_cnt >= POLL_CYCLES - 1) begin
                      poll_cnt <= 8'd0;
                      issue_rd(AF_ANALOG_SEQ);
                      state <= S_CAP_POLLW;
                  end else
                      poll_cnt <= poll_cnt + 8'd1;
              end

              S_CAP_POLLW: begin
                  if (m_done) begin
                      if (m_err) go_fail(R_AXI_ERROR);
                      else if (m_rdata[15:0] != seq0) begin
                          issue_rd(AF_ANALOG_CONTROL);
                          state <= S_CAP_CHK;
                      end else
                          state <= S_CAP_POLL;
                  end
              end

              S_CAP_CHK: begin
                  if (m_done) begin
                      
                      if (m_err)
                          go_fail(R_AXI_ERROR);
                      else if (m_rdata[2] || !m_rdata[7] ||
                               (m_rdata[4:3] != cap_range) || (m_rdata[5] != cap_pol))
                          go_fail(R_ANALOG_SEQ_ERROR);
                      else begin
                          pin_watch  <= 1'b1;
                          elapsed_ms <= 16'd0;
                          have_prev  <= 1'b0;
                          consec     <= 4'd0;
                          seg_run    <= 1'b0;
                          if (cfg_reinit) begin
                              issue_rd(AF_ADC_CFG_SEQ);
                              state <= S_CAP_ADC0;
                          end else
                              state <= S_SETTLE;
                      end
                  end
              end

              S_CAP_ADC0: begin
                  if (m_done) begin
                      if (m_err) go_fail(R_AXI_ERROR);
                      else begin
                          aseq0 <= m_rdata[15:0];
                          issue_wr(AF_CONTROL, 32'h0000_0010);
                          state <= S_CAP_ADCW;
                      end
                  end
              end

              S_CAP_ADCW: begin
                  if (m_done) begin
                      if (m_err) go_fail(R_AXI_ERROR);
                      else begin
                          tmo_ms   <= 16'd0;
                          poll_cnt <= 8'd0;
                          state    <= S_CAP_ADCP;
                      end
                  end
              end

              S_CAP_ADCP: begin
                  if (tmo_ms >= cfg_cfg_timeout_ms)
                      go_fail(R_ANALOG_SEQ_ERROR);
                  else if (poll_cnt >= POLL_CYCLES - 1) begin
                      poll_cnt <= 8'd0;
                      issue_rd(AF_ADC_CFG_SEQ);
                      state <= S_CAP_ADCPW;
                  end else
                      poll_cnt <= poll_cnt + 8'd1;
              end

              S_CAP_ADCPW: begin
                  if (m_done) begin
                      if (m_err) go_fail(R_AXI_ERROR);
                      else if (m_rdata[15:0] != aseq0) state <= S_SETTLE;
                      else                             state <= S_CAP_ADCP;
                  end
              end

              
              S_SETTLE: begin
                  if (elapsed_ms >= cfg_t_max_ms) begin
                      
                      
                      flags <= flags | F_SETTLE_TIMEOUT;
                      if (settle_timeouts != 16'hFFFF)
                          settle_timeouts <= settle_timeouts + 16'd1;
                      start_integrate;
                  end else if (!cfg_settle_enable) begin
                      if (elapsed_ms >= t_min_eff) start_integrate;
                  end else if ((consec >= cfg_settle_k) && (elapsed_ms >= t_min_eff)) begin
                      start_integrate;
                  end else if (!seg_run) begin
                      if (elapsed_ms >= cfg_t_skip_ms) begin
                          seg_run     <= 1'b1;
                          seg_restart <= 1'b1;
                      end
                  end else if (seg_ready) begin
                      seg_ack <= 1'b1;
                      if (seg_snap_n == 32'd0) begin
                          
                          
                          have_prev <= 1'b0;
                          consec    <= 4'd0;
                      end else begin
                          div_num    <= {(seg_snap_sum[47] ? (~seg_snap_sum[47:0] + 48'd1)
                                                           : seg_snap_sum[47:0]), 8'd0};
                          div_den    <= seg_snap_n;
                          div_neg    <= seg_snap_sum[47];
                          div_issued <= 1'b0;
                          state      <= S_SEG_DIV;
                      end
                  end
              end

              S_SEG_DIV: begin
                  if (!div_issued) begin
                      if (!div_busy) begin
                          div_start  <= 1'b1;
                          div_issued <= 1'b1;
                      end
                  end else if (div_done) begin
                      div_issued <= 1'b0;
                      m_now      <= div_res;
                      state      <= S_SEG_MUL;
                  end
              end

              S_SEG_MUL: begin
                  if (!mul_pend) begin
                      mul_a    <= $signed({16'd0, cfg_eps_rel_q16});
                      mul_b    <= $signed({8'd0, abs32(m_now)});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_a      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_SEG_CMP;
                  end
              end

              S_SEG_CMP: begin
                  
                  
                  if (have_prev &&
                      ({2'b00, abs32(m_now - m_prev)} <=
                       ({1'b0, p_a[48:16]} + {18'd0, cfg_eps_abs_q8}))) begin
                      if (consec != 4'hF) consec <= consec + 4'd1;
                  end else begin
                      consec <= 4'd0;
                  end
                  m_prev    <= m_now;
                  have_prev <= 1'b1;
                  state     <= S_SETTLE;
              end

              
              S_INT: begin
                  if (win_ready) begin
                      win_ack   <= 1'b1;
                      lat_win_n <= win_snap_n;
                      if (win_snap_n == 32'd0)
                          go_fail(R_NO_SAMPLES);
                      else begin
                          div_num    <= {(win_snap_sum[47] ? (~win_snap_sum[47:0] + 48'd1)
                                                           : win_snap_sum[47:0]), 8'd0};
                          div_den    <= win_snap_n;
                          div_neg    <= win_snap_sum[47];
                          div_issued <= 1'b0;
                          state      <= S_WIN_DIV;
                      end
                  end
              end

              S_WIN_DIV: begin
                  if (!div_issued) begin
                      if (!div_busy) begin
                          div_start  <= 1'b1;
                          div_issued <= 1'b1;
                      end
                  end else if (div_done) begin
                      div_issued <= 1'b0;
                      wm         <= div_res;
                      if (!m_busy) begin
                          issue_rd(AF_STATUS);
                          state <= S_WIN_STAT;
                      end else
                          state <= S_WIN_STAT;   
                  end
              end

              S_WIN_STAT: begin
                  if (m_done) begin
                      if (m_err)
                          go_fail(R_AXI_ERROR);
                      else if (m_rdata[16] || m_rdata[17])
                          go_fail(R_SAFETY_ABORT);
                      else
                          state <= S_WIN_DONE;
                  end else if (!m_busy && !m_valid) begin
                      issue_rd(AF_STATUS);
                  end
              end

              S_WIN_DONE: begin
                  seg_wins_done <= seg_wins_done + 2'd1;
                  if (phase == PH_PILOT) begin
                      if (!cap_pol) begin
                          mf_cur          <= wm;
                          pr_mf[cur_i]    <= wm;
                          pr_set_f[cur_i] <= settle_ms_now;
                          pr_n_f[cur_i]   <= (lat_win_n > 32'hFFFF) ? 16'hFFFF : lat_win_n[15:0];
                          begin_capture(cur_i, 1'b1, 2'd1);
                      end else begin
                          mr_cur          <= wm;
                          pr_mr[cur_i]    <= wm;
                          pr_set_r[cur_i] <= settle_ms_now;
                          pr_n_r[cur_i]   <= (lat_win_n > 32'hFFFF) ? 16'hFFFF : lat_win_n[15:0];
                          pin_watch       <= 1'b0;
                          state           <= S_EVAL0;
                      end
                  end else begin
                      if (!cap_pol) begin
                          wm_sum_f <= wm_sum_f + {{8{wm[31]}}, wm};
                          wins_f   <= wins_f + 5'd1;
                          if (!have_first_f) begin
                              mf_first     <= wm;
                              have_first_f <= 1'b1;
                          end
                          mf_last <= wm;
                      end else begin
                          wm_sum_r <= wm_sum_r + {{8{wm[31]}}, wm};
                          wins_r   <= wins_r + 5'd1;
                      end

                      if (verify_pending && cap_pol && (wins_r == 5'd0)) begin
                          
                          state <= S_VER0;
                      end else if (cap_pol) begin
                          finish_pair;
                      end else begin
                          first_meas_seg <= 1'b0;
                          begin_capture(sel_range, 1'b1, 2'd1);
                      end
                  end
              end

              
              S_EVAL0: begin
                  s_i     <= pair_sum[32:1];                 
                  abs_i   <= abs32(pair_sum[32:1]);
                  p_i     <= (amf > amr) ? amf : amr;
                  tested  <= tested | (4'b0001 << cur_i);
                  {n_valid, n_idx} <= next_of(cfg_range_mask, cur_i);
                  if (!f_valid) begin
                      f_valid <= 1'b1;
                      f_idx   <= cur_i;
                      abs_f   <= abs32(pair_sum[32:1]);
                  end
                  state   <= S_EVAL1;
              end

              
              
              
              
              
              S_EVAL1: begin
                  if (abs_i > s_max) s_max <= abs_i;
                  if (p_i > {8'd0, sat8}) begin
                      if (j_valid) begin
                          reason <= R_OK_SAT_BACKOFF;
                          flags  <= flags | flags_for(j_idx, abs_j, lowest, lo8, hi8);
                          begin_measurement(j_idx, 1'b1);
                      end else
                          go_fail(R_OVER_RANGE_AT_MIN);
                  end else if (j_valid && (abs_i >= {8'd0, lm8}) && (abs_j >= {8'd0, lm8}))
                      state <= S_EV_L1;
                  else
                      state <= S_EV_N1;
              end

              
              S_EV_L1: begin
                  if (!mul_pend) begin
                      mul_a    <= {{8{s_i[31]}}, s_i};
                      mul_b    <= $signed({11'd0, isum_j});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_a      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_EV_L2;
                  end
              end

              S_EV_L2: begin
                  if (!mul_pend) begin
                      mul_a    <= {{8{s_j[31]}}, s_j};
                      mul_b    <= $signed({11'd0, isum_cur});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_b      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_EV_L3;
                  end
              end

              S_EV_L3: begin
                  if (!mul_pend) begin
                      mul_a    <= $signed({8'd0, abs_j});
                      mul_b    <= $signed({11'd0, isum_cur});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_c      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_EV_L4;
                  end
              end

              S_EV_L4: begin
                  if (!mul_pend) begin
                      mul_a    <= p_c[55:16];                 
                      mul_b    <= $signed({16'd0, cfg_lin_tol_q16});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_c      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_EV_LC;
                  end
              end

              S_EV_LC: begin
                  if ((((p_a - p_b) < 0) ? (p_b - p_a) : (p_a - p_b)) > p_c) begin
                      reason <= R_OK_NONLINEAR_BACKOFF;
                      flags  <= flags | flags_for(j_idx, abs_j, lowest, lo8, hi8);
                      begin_measurement(j_idx, 1'b1);
                  end else
                      state <= S_EV_N1;
              end

              
              S_EV_N1: begin
                  if (!n_valid) begin
                      pend_reason <= R_OK_TOP;
                      state       <= S_EV_OPEN0;
                  end else if (!mul_pend) begin
                      mul_a    <= $signed({8'd0, abs_i});
                      mul_b    <= $signed({11'd0, isum_n});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_a      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_EV_N2;
                  end
              end

              S_EV_N2: begin
                  if (!mul_pend) begin
                      mul_a    <= $signed({16'd0, hi8});
                      mul_b    <= $signed({11'd0, isum_cur});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_b      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_EV_NC;
                  end
              end

              S_EV_NC: begin
                  if (p_a <= p_b) begin
                      j_valid <= 1'b1;
                      j_idx   <= cur_i;
                      s_j     <= s_i;
                      abs_j   <= abs_i;
                      cur_i   <= n_idx;
                      begin_capture(n_idx, 1'b0, 2'd1);
                  end else begin
                      pend_reason <= R_OK;
                      state       <= S_EV_OPEN0;
                  end
              end

              
              
              
              S_EV_OPEN0: begin
                  if (f_valid && (f_idx != cur_i))
                      state <= S_EV_O1;
                  else begin
                      reason <= pend_reason;
                      flags  <= flags | flags_for(cur_i, abs_i, lowest, lo8, hi8);
                      begin_measurement(cur_i, 1'b1);
                  end
              end

              S_EV_O1: begin
                  if (!mul_pend) begin
                      mul_a    <= $signed({16'd0, cfg_open_iratio_q16});
                      mul_b    <= $signed({11'd0, isum_f});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_a      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_EV_O2;
                  end
              end

              S_EV_O2: begin
                  if (!mul_pend) begin
                      mul_a    <= $signed({16'd0, cfg_open_vratio_q16});
                      mul_b    <= $signed({8'd0, ((abs_f > {8'd0, nf8}) ? abs_f : {8'd0, nf8})});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_b      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_EV_OC;
                  end
              end

              S_EV_OC: begin
                  if ((s_max < {8'd0, ov8}) &&
                      ($signed({35'd0, isum_cur, 16'd0}) >= p_a) &&
                      ($signed({32'd0, abs_i, 16'd0}) < p_b))
                      go_fail(R_OPEN_LOOP);
                  else begin
                      reason <= pend_reason;
                      flags  <= flags | flags_for(cur_i, abs_i, lowest, lo8, hi8);
                      begin_measurement(cur_i, 1'b1);
                  end
              end

              
              S_VER0: begin
                  s_i   <= ver_sum[32:1];
                  abs_i <= abs32(ver_sum[32:1]);
                  p_i   <= (avf > avr) ? avf : avr;
                  {n_valid, n_idx} <= next_of(cfg_range_mask, sel_range);
                  cur_i <= sel_range;
                  state <= S_VER_V1;
              end

              S_VER_V1: begin
                  if (p_i > {8'd0, sat8} || abs_i < {8'd0, ov8}) begin
                      state <= S_VER_C;            
                      p_a   <= 80'sd1;
                      p_b   <= 80'sd0;
                  end else if (!mul_pend) begin
                      mul_a    <= $signed({16'd0, hi8});
                      mul_b    <= $signed({16'd0, cfg_hyst_q16});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_c      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_VER_V1C;
                  end
              end

              S_VER_V1C: begin
                  if ($signed({32'd0, abs_i, 16'd0}) > p_c) begin
                      p_a   <= 80'sd1;            
                      p_b   <= 80'sd0;
                      state <= S_VER_C;
                  end else if (!n_valid) begin
                      p_a   <= 80'sd0;            
                      p_b   <= 80'sd1;
                      state <= S_VER_C;
                  end else
                      state <= S_VER_V2;
              end

              S_VER_V2: begin
                  if (!mul_pend) begin
                      mul_a    <= $signed({8'd0, abs_i});
                      mul_b    <= $signed({11'd0, isum_n});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_c      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_VER_V3;
                  end
              end

              S_VER_V3: begin
                  if (!mul_pend) begin
                      mul_a    <= p_c[55:16];
                      mul_b    <= $signed({16'd0, cfg_hyst_q16});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      p_c      <= mul_p;
                      mul_pend <= 1'b0;
                      state    <= S_VER_V4;
                  end
              end

              S_VER_V4: begin
                  if (!mul_pend) begin
                      mul_a    <= $signed({16'd0, hi8});
                      mul_b    <= $signed({11'd0, isum_sel});
                      mul_pend <= 1'b1;
                      mul_cnt  <= 3'd0;
                  end else if (mul_ready) begin
                      
                      if (p_c <= mul_p) begin
                          p_a <= 80'sd1;
                          p_b <= 80'sd0;
                      end else begin
                          p_a <= 80'sd0;
                          p_b <= 80'sd1;
                      end
                      mul_pend <= 1'b0;
                      state    <= S_VER_C;
                  end
              end

              S_VER_C: begin
                  verify_pending <= 1'b0;
                  if (p_a > p_b) begin
                      
                      flags     <= flags | F_RERANGED;
                      win_stop  <= 1'b1;
                      pin_watch <= 1'b0;
                      begin_full_pilot;
                  end else begin
                      reason <= n_valid ? R_OK : R_OK_TOP;
                      flags  <= flags | flags_for(sel_range, abs_i, lowest, lo8, hi8);
                      finish_pair;
                  end
              end

              
              S_FIN_F: begin
                  if (!div_issued) begin
                      if (!div_busy) begin
                          div_start  <= 1'b1;
                          div_issued <= 1'b1;
                      end
                  end else if (div_done) begin
                      mf_avg     <= div_res;
                      div_num    <= {16'd0, (wm_sum_r[39] ? (~wm_sum_r + 40'd1) : wm_sum_r)};
                      div_den    <= {27'd0, two_n};
                      div_neg    <= wm_sum_r[39];
                      div_issued <= 1'b0;
                      state      <= S_FIN_R;
                  end
              end

              S_FIN_R: begin
                  if (!div_issued) begin
                      if (!div_busy) begin
                          div_start  <= 1'b1;
                          div_issued <= 1'b1;
                      end
                  end else if (div_done) begin
                      mr_avg     <= div_res;
                      div_issued <= 1'b0;
                      state      <= S_FIN_PAIR;
                  end
              end

              S_FIN_PAIR: begin
                  s_meas      <= ({mf_avg[31], mf_avg} + {mr_avg[31], mr_avg}) >> 1;
                  e_meas      <= ({mf_avg[31], mf_avg} - {mr_avg[31], mr_avg}) >> 1;
                  run_failed  <= 1'b0;
                  state       <= S_SAFE_WAIT;
              end

              
              S_SAFE_WAIT: begin
                  pin_watch <= 1'b0;
                  seg_run   <= 1'b0;
                  if (m_hung)
                      state <= S_END;
                  else if (!m_busy && !m_valid) begin
                      issue_wr(AF_ANALOG_CONTROL, AF_ANALOG_ABORT);
                      state <= S_SAFE_OFFW;
                  end
              end

              S_SAFE_OFFW: begin
                  if (m_done) begin
                      if (m_err && !run_failed) begin
                          run_failed  <= 1'b1;
                          fail_reason <= R_AXI_ERROR;
                      end
                      state <= S_END;
                  end
              end

              S_PINFAIL: begin
                  if (m_hung)
                      go_fail(R_AXI_ERROR);
                  else if (!m_busy && !m_valid) begin
                      issue_rd(AF_STATUS);
                      state <= S_PINFAIL_W;
                  end
              end

              S_PINFAIL_W: begin
                  if (m_done) begin
                      if (m_err)
                          go_fail(R_AXI_ERROR);
                      else if (m_rdata[16] || m_rdata[17])
                          go_fail(R_SAFETY_ABORT);
                      else
                          go_fail(R_OWNERSHIP_CONFLICT);
                  end
              end

              S_END: begin
                  busy <= 1'b0;
                  done <= 1'b1;
                  if (run_failed) begin
                      error        <= 1'b1;
                      reason       <= fail_reason;
                      result_valid <= 1'b0;
                  end else begin
                      error        <= 1'b0;
                      result_valid <= 1'b1;
                  end
                  state <= S_IDLE;
              end

              default: state <= S_IDLE;
              endcase
          end
      end
  end

  
  
  
  always @* begin
      res_data = 32'd0;
      case (res_addr)
          6'd0:  res_data = {21'd0, phase, run_mode, tested, 2'd0, sel_range};
          6'd1:  res_data = {16'd0, flags, reason};
          6'd2:  res_data = run_ms;
          6'd3:  res_data = mismatch_count;
          6'd4:  res_data = pr_mf[0];
          6'd5:  res_data = pr_mr[0];
          6'd6:  res_data = {pr_set_r[0], pr_set_f[0]};
          6'd7:  res_data = {pr_n_r[0], pr_n_f[0]};
          6'd8:  res_data = pr_mf[1];
          6'd9:  res_data = pr_mr[1];
          6'd10: res_data = {pr_set_r[1], pr_set_f[1]};
          6'd11: res_data = {pr_n_r[1], pr_n_f[1]};
          6'd12: res_data = pr_mf[2];
          6'd13: res_data = pr_mr[2];
          6'd14: res_data = {pr_set_r[2], pr_set_f[2]};
          6'd15: res_data = {pr_n_r[2], pr_n_f[2]};
          6'd16: res_data = pr_mf[3];
          6'd17: res_data = pr_mr[3];
          6'd18: res_data = {pr_set_r[3], pr_set_f[3]};
          6'd19: res_data = {pr_n_r[3], pr_n_f[3]};
          6'd32: res_data = s_meas;
          6'd33: res_data = e_meas;
          6'd34: res_data = mf_avg;
          6'd35: res_data = mr_avg;
          6'd36: res_data = mf_first;
          6'd37: res_data = mf_last;
          6'd38: res_data = {settle_timeouts, meas_settle_max};
          6'd39: res_data = {11'd0, wins_r, 11'd0, wins_f};
          6'd40: res_data = agg_sum[0][31:0];
          6'd41: res_data = {16'd0, agg_sum[0][47:32]};
          6'd42: res_data = agg_sumsq[0][31:0];
          6'd43: res_data = agg_sumsq[0][63:32];
          6'd44: res_data = agg_n[0];
          6'd45: res_data = {agg_max[0], agg_min[0]};
          6'd48: res_data = agg_sum[1][31:0];
          6'd49: res_data = {16'd0, agg_sum[1][47:32]};
          6'd50: res_data = agg_sumsq[1][31:0];
          6'd51: res_data = agg_sumsq[1][63:32];
          6'd52: res_data = agg_n[1];
          6'd53: res_data = {agg_max[1], agg_min[1]};
          default: res_data = 32'd0;
      endcase
  end

endmodule
