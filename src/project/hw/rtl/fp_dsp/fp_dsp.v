// Compact FP_DSP v5: native ADC codes, autonomous range selection and one F/R pair.
// AXI master can access ALL_Final only; its interlocks remain authoritative.
// Former advanced diagnostic register ranges read zero and are not implemented.






















module fp_dsp #(
    parameter integer TICK_CYCLES        = 50000,   
    parameter integer POLL_CYCLES        = 64,
    parameter integer AXI_TIMEOUT_CYCLES = 65535
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi:m_axi, ASSOCIATED_RESET aresetn" *)
    input  wire        aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire        aresetn,

    
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 16" *)
    input  wire [15:0] s_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWPROT" *)
    input  wire [2:0]  s_axi_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWVALID" *)
    input  wire        s_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWREADY" *)
    output wire        s_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WDATA" *)
    input  wire [31:0] s_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WSTRB" *)
    input  wire [3:0]  s_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WVALID" *)
    input  wire        s_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WREADY" *)
    output wire        s_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BRESP" *)
    output wire [1:0]  s_axi_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BVALID" *)
    output wire        s_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BREADY" *)
    input  wire        s_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARADDR" *)
    input  wire [15:0] s_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARPROT" *)
    input  wire [2:0]  s_axi_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARVALID" *)
    input  wire        s_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARREADY" *)
    output wire        s_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RDATA" *)
    output wire [31:0] s_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RRESP" *)
    output wire [1:0]  s_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RVALID" *)
    output wire        s_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RREADY" *)
    input  wire        s_axi_rready,

    
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 32" *)
    output wire [31:0] m_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWPROT" *)
    output wire [2:0]  m_axi_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWVALID" *)
    output wire        m_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWREADY" *)
    input  wire        m_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WDATA" *)
    output wire [31:0] m_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WSTRB" *)
    output wire [3:0]  m_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WVALID" *)
    output wire        m_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WREADY" *)
    input  wire        m_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi BRESP" *)
    input  wire [1:0]  m_axi_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi BVALID" *)
    input  wire        m_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi BREADY" *)
    output wire        m_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARADDR" *)
    output wire [31:0] m_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARPROT" *)
    output wire [2:0]  m_axi_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARVALID" *)
    output wire        m_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARREADY" *)
    input  wire        m_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RDATA" *)
    input  wire [31:0] m_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RRESP" *)
    input  wire [1:0]  m_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RVALID" *)
    input  wire        m_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RREADY" *)
    output wire        m_axi_rready,

    
    input  wire        spi_cs,          
    input  wire        spi_sclk,        
    input  wire        spi_sdo,         
    input  wire        range0_pin,      
    input  wire        range1_pin,
    input  wire        range2_pin,
    input  wire        range3_pin,
    input  wire        pol_i_pin,
    input  wire        pol_v_pin,
    input  wire        current_en_pin
);

  localparam [31:0] FPD_ID      = 32'h4650_4431;   
  localparam [31:0] FPD_VERSION = 32'd5;
  
  
  
  localparam [31:0] FPD_CAPS    = 32'h0000_0417;

  wire clk   = aclk;
  wire rst_n = aresetn;

  
  
  
  reg [31:0] t_cnt;
  reg        t_ms;
  reg [9:0]  t_ms_cnt;
  always @(posedge clk) begin
      if (!rst_n) begin
          t_cnt    <= 32'd0;
          t_ms     <= 1'b0;
          t_ms_cnt <= 10'd0;
      end else begin
          t_ms <= 1'b0;
          if (t_cnt >= TICK_CYCLES - 1) begin
              t_cnt <= 32'd0;
              t_ms  <= 1'b1;
          end else
              t_cnt <= t_cnt + 32'd1;
          if (t_ms) t_ms_cnt <= (t_ms_cnt == 10'd999) ? 10'd0 : t_ms_cnt + 10'd1;
      end
  end

  
  
  
  wire        smp_valid;
  wire [15:0] smp_code;
  wire        cfg_frame;
  wire        bad_frame;
  fpd_spi_sniffer u_sniffer (
      .clk(clk), .rst_n(rst_n),
      .spi_cs(spi_cs), .spi_sclk(spi_sclk), .spi_sdo(spi_sdo),
      .sample_valid(smp_valid), .sample_code(smp_code),
      .cfg_frame(cfg_frame), .bad_frame(bad_frame));

  wire [3:0] pin_range = {range3_pin, range2_pin, range1_pin, range0_pin};
  wire       pin_onehot = (pin_range == 4'b0001) || (pin_range == 4'b0010) ||
                          (pin_range == 4'b0100) || (pin_range == 4'b1000);
  wire [1:0] pin_idx = pin_range[3] ? 2'd3 : pin_range[2] ? 2'd2 : pin_range[1] ? 2'd1 : 2'd0;
  wire       pin_label_valid = current_en_pin && pin_onehot && (pol_i_pin == pol_v_pin);

  reg [31:0] sample_count;
  reg [15:0] cfg_frames;
  reg [15:0] bad_frames;
  reg [31:0] rate_acc;
  reg [31:0] rate_last;
  reg [15:0] last_code;
  reg [2:0]  last_label;
  reg        last_label_valid;
  always @(posedge clk) begin
      if (!rst_n) begin
          sample_count     <= 32'd0;
          cfg_frames       <= 16'd0;
          bad_frames       <= 16'd0;
          rate_acc         <= 32'd0;
          rate_last        <= 32'd0;
          last_code        <= 16'd0;
          last_label       <= 3'd0;
          last_label_valid <= 1'b0;
      end else begin
          if (smp_valid) begin
              sample_count     <= sample_count + 32'd1;
              last_code        <= smp_code;
              last_label       <= {pol_i_pin, pin_idx};
              last_label_valid <= pin_label_valid;
          end
          if (cfg_frame && cfg_frames != 16'hFFFF) cfg_frames <= cfg_frames + 16'd1;
          if (bad_frame && bad_frames != 16'hFFFF) bad_frames <= bad_frames + 16'd1;
          if (t_ms && t_ms_cnt == 10'd999) begin
              rate_last <= rate_acc + (smp_valid ? 32'd1 : 32'd0);
              rate_acc  <= 32'd0;
          end else if (smp_valid)
              rate_acc <= rate_acc + 32'd1;
      end
  end

  
  
  
  reg [3:0]  cfg_range_mask;
  reg [15:0] cfg_s_hi, cfg_s_lo, cfg_raw_sat, cfg_lin_min, cfg_open_vmax, cfg_noise_floor;
  reg [23:0] cfg_lin_tol_q16, cfg_open_iratio_q16, cfg_open_vratio_q16, cfg_hyst_q16;
  reg [23:0] cfg_eps_rel_q16;
  reg [15:0] cfg_eps_abs_q8;
  reg [15:0] cfg_pilot_win_ms, cfg_meas_win_ms, cfg_t_min_ms, cfg_t_max_ms, cfg_warmup_ms;
  reg [15:0] cfg_t_skip_ms, cfg_seg_ms, cfg_cfg_timeout_ms;
  reg [3:0]  cfg_pair_mode, cfg_settle_k;
  reg        cfg_settle_enable, cfg_reinit;
  reg [15:0] cfg_center [0:7];
  reg [27:0] cfg_if     [0:3];
  reg [27:0] cfg_ir     [0:3];
  reg [31:0] allf_base;

  reg        cmd_start, cmd_abort, cmd_clear, cmd_claim, cmd_release;
  reg [1:0]  cmd_mode, cmd_range;

  wire [127:0] cfg_center_flat = {cfg_center[7], cfg_center[6], cfg_center[5], cfg_center[4],
                                  cfg_center[3], cfg_center[2], cfg_center[1], cfg_center[0]};
  wire [111:0] cfg_if_flat = {cfg_if[3], cfg_if[2], cfg_if[1], cfg_if[0]};
  wire [111:0] cfg_ir_flat = {cfg_ir[3], cfg_ir[2], cfg_ir[1], cfg_ir[0]};

  
  wire        ar_busy, ar_done, ar_error, ar_owned, ar_result_valid;
  wire [5:0]  ar_state;
  wire [7:0]  ar_reason, ar_flags;
  wire [31:0] ar_mismatch;
  wire [31:0] ar_res_data;
  wire        mc_valid, mc_write;
  wire [11:0] mc_addr;
  wire [31:0] mc_wdata;
  wire        mc_busy, mc_done, mc_err, mc_hung;
  wire [31:0] mc_rdata;
  reg  [5:0]  res_addr;
  wire               ms_add, ms_pol, ms_clear;     
  wire               ms_tick, ms_win_active, ms_win_bnd;   
  wire signed [17:0] ms_delta;

  fpd_autorange #(.TICK_CYCLES(TICK_CYCLES), .POLL_CYCLES(POLL_CYCLES)) u_autorange (
      .clk(clk), .rst_n(rst_n),
      .cmd_start(cmd_start), .cmd_abort(cmd_abort), .cmd_clear(cmd_clear),
      .cmd_claim(cmd_claim), .cmd_release(cmd_release),
      .cmd_mode(cmd_mode), .cmd_range(cmd_range),
      .cfg_range_mask(cfg_range_mask),
      .cfg_s_hi(cfg_s_hi), .cfg_s_lo(cfg_s_lo), .cfg_raw_sat(cfg_raw_sat),
      .cfg_lin_min(cfg_lin_min), .cfg_open_vmax(cfg_open_vmax), .cfg_noise_floor(cfg_noise_floor),
      .cfg_lin_tol_q16(cfg_lin_tol_q16), .cfg_open_iratio_q16(cfg_open_iratio_q16),
      .cfg_open_vratio_q16(cfg_open_vratio_q16), .cfg_hyst_q16(cfg_hyst_q16),
      .cfg_eps_rel_q16(cfg_eps_rel_q16), .cfg_eps_abs_q8(cfg_eps_abs_q8),
      .cfg_pilot_win_ms(cfg_pilot_win_ms), .cfg_meas_win_ms(cfg_meas_win_ms),
      .cfg_pair_mode(cfg_pair_mode), .cfg_t_min_ms(cfg_t_min_ms), .cfg_t_max_ms(cfg_t_max_ms),
      .cfg_warmup_ms(cfg_warmup_ms), .cfg_t_skip_ms(cfg_t_skip_ms), .cfg_seg_ms(cfg_seg_ms),
      .cfg_settle_k(cfg_settle_k), .cfg_cfg_timeout_ms(cfg_cfg_timeout_ms),
      .cfg_settle_enable(cfg_settle_enable), .cfg_reinit(cfg_reinit),
      .cfg_center_flat(cfg_center_flat), .cfg_if_flat(cfg_if_flat), .cfg_ir_flat(cfg_ir_flat),
      .smp_valid(smp_valid), .smp_code(smp_code),
      .pin_range(pin_range), .pin_pol_i(pol_i_pin), .pin_pol_v(pol_v_pin),
      .pin_current_en(current_en_pin),
      .m_valid(mc_valid), .m_write(mc_write), .m_addr(mc_addr), .m_wdata(mc_wdata),
      .m_busy(mc_busy), .m_done(mc_done), .m_err(mc_err), .m_hung(mc_hung), .m_rdata(mc_rdata),
      .busy(ar_busy), .done(ar_done), .error(ar_error), .owned(ar_owned),
      .result_valid(ar_result_valid), .state(ar_state), .reason(ar_reason), .flags(ar_flags),
      .mismatch_count(ar_mismatch),
      .meas_add(ms_add), .meas_pol(ms_pol), .meas_delta(ms_delta), .meas_clear(ms_clear),
      .meas_tick(ms_tick), .meas_win_active(ms_win_active), .meas_win_bnd(ms_win_bnd),
      .res_addr(res_addr), .res_data(ar_res_data));

  fpd_axil_master #(.TIMEOUT_CYCLES(AXI_TIMEOUT_CYCLES)) u_master (
      .clk(clk), .rst_n(rst_n),
      .cmd_valid(mc_valid), .cmd_write(mc_write),
      .cmd_addr(allf_base + {20'd0, mc_addr}), .cmd_wdata(mc_wdata),
      .busy(mc_busy), .done(mc_done), .err(mc_err), .hung(mc_hung), .rdata(mc_rdata),
      .m_axi_awaddr(m_axi_awaddr), .m_axi_awprot(m_axi_awprot),
      .m_axi_awvalid(m_axi_awvalid), .m_axi_awready(m_axi_awready),
      .m_axi_wdata(m_axi_wdata), .m_axi_wstrb(m_axi_wstrb),
      .m_axi_wvalid(m_axi_wvalid), .m_axi_wready(m_axi_wready),
      .m_axi_bresp(m_axi_bresp), .m_axi_bvalid(m_axi_bvalid), .m_axi_bready(m_axi_bready),
      .m_axi_araddr(m_axi_araddr), .m_axi_arprot(m_axi_arprot),
      .m_axi_arvalid(m_axi_arvalid), .m_axi_arready(m_axi_arready),
      .m_axi_rdata(m_axi_rdata), .m_axi_rresp(m_axi_rresp),
      .m_axi_rvalid(m_axi_rvalid), .m_axi_rready(m_axi_rready));

  reg [15:0] axi_err_count;
  always @(posedge clk) begin
      if (!rst_n)
          axi_err_count <= 16'd0;
      else if (mc_done && mc_err && axi_err_count != 16'hFFFF)
          axi_err_count <= axi_err_count + 16'd1;
  end

  
  
  
  reg        aw_pending, w_pending;
  reg [15:0] awaddr_q;
  reg [31:0] wdata_q;
  reg        bvalid_q;
  reg        rvalid_q;
  reg [31:0] rdata_q;

  assign s_axi_awready = !aw_pending && !bvalid_q;
  assign s_axi_wready  = !w_pending && !bvalid_q;
  assign s_axi_bresp   = 2'b00;
  assign s_axi_bvalid  = bvalid_q;
  assign s_axi_arready = !rvalid_q;
  assign s_axi_rresp   = 2'b00;
  assign s_axi_rvalid  = rvalid_q;
  assign s_axi_rdata   = rdata_q;

  integer k;
  always @(posedge clk) begin
      if (!rst_n) begin
          aw_pending <= 1'b0;
          w_pending  <= 1'b0;
          awaddr_q   <= 16'd0;
          wdata_q    <= 32'd0;
          bvalid_q   <= 1'b0;
          cmd_start  <= 1'b0;
          cmd_abort  <= 1'b0;
          cmd_clear  <= 1'b0;
          cmd_claim  <= 1'b0;
          cmd_release<= 1'b0;
          cmd_mode   <= 2'd0;
          cmd_range  <= 2'd0;
          
          cfg_range_mask      <= 4'b0111;      
          cfg_s_hi            <= 16'd3200;      
          cfg_s_lo            <= 16'd128;       
          cfg_raw_sat         <= 16'd10240;     
          cfg_lin_min         <= 16'd80;       
          cfg_open_vmax       <= 16'd96;       
          cfg_noise_floor     <= 16'd2;
          cfg_lin_tol_q16     <= 24'd1311;     
          cfg_open_iratio_q16 <= 24'd327680;   
          cfg_open_vratio_q16 <= 24'd131072;   
          cfg_hyst_q16        <= 24'd81920;    
          cfg_eps_rel_q16     <= 24'd66;       
          cfg_eps_abs_q8      <= 16'd256;      
          cfg_pilot_win_ms    <= 16'd100;
          cfg_meas_win_ms     <= 16'd400;
          cfg_pair_mode     <= 4'd1;
          cfg_t_min_ms        <= 16'd200;
          cfg_t_max_ms        <= 16'd5000;
          cfg_warmup_ms       <= 16'd0;
          cfg_t_skip_ms       <= 16'd50;
          cfg_seg_ms          <= 16'd100;
          cfg_settle_k        <= 4'd3;
          cfg_cfg_timeout_ms  <= 16'd200;
          cfg_settle_enable   <= 1'b1;
          cfg_reinit          <= 1'b1;
          for (k = 0; k < 8; k = k + 1) cfg_center[k] <= 16'd48768;   
          for (k = 0; k < 4; k = k + 1) begin
              cfg_if[k] <= 28'd0;      
              cfg_ir[k] <= 28'd0;
          end
          allf_base <= 32'h4000_0000;
      end else begin
          cmd_start   <= 1'b0;
          cmd_abort   <= 1'b0;
          cmd_clear   <= 1'b0;
          cmd_claim   <= 1'b0;
          cmd_release <= 1'b0;

          if (bvalid_q && s_axi_bready) bvalid_q <= 1'b0;
          if (s_axi_awvalid && s_axi_awready) begin
              aw_pending <= 1'b1;
              awaddr_q   <= s_axi_awaddr;
          end
          if (s_axi_wvalid && s_axi_wready) begin
              w_pending <= 1'b1;
              wdata_q   <= s_axi_wdata;
          end

          if (aw_pending && w_pending && !bvalid_q) begin
              aw_pending <= 1'b0;
              w_pending  <= 1'b0;
              bvalid_q   <= 1'b1;
              if (awaddr_q[11:0] == 12'h010) begin
                  cmd_start   <= wdata_q[0];
                  cmd_abort   <= wdata_q[1];
                  cmd_clear   <= wdata_q[2];
                  cmd_claim   <= wdata_q[3];
                  cmd_release <= wdata_q[4];
                  if (!ar_busy) begin
                      cmd_mode  <= wdata_q[9:8];
                      cmd_range <= wdata_q[13:12];
                  end
              end else if (!ar_busy) begin
                  case (awaddr_q[11:0])
                      12'h02C: allf_base           <= wdata_q;
                      12'h040: cfg_range_mask      <= wdata_q[3:0];
                      12'h044: cfg_s_hi            <= wdata_q[15:0];
                      12'h048: cfg_s_lo            <= wdata_q[15:0];
                      12'h04C: cfg_raw_sat         <= wdata_q[15:0];
                      12'h050: cfg_lin_tol_q16     <= wdata_q[23:0];
                      12'h054: cfg_lin_min         <= wdata_q[15:0];
                      12'h058: cfg_open_vmax       <= wdata_q[15:0];
                      12'h05C: cfg_open_iratio_q16 <= wdata_q[23:0];
                      12'h060: cfg_open_vratio_q16 <= wdata_q[23:0];
                      12'h064: cfg_noise_floor     <= wdata_q[15:0];
                      12'h068: cfg_hyst_q16        <= wdata_q[23:0];
                      12'h06C: cfg_pilot_win_ms    <= wdata_q[15:0];
                      12'h070: cfg_meas_win_ms     <= wdata_q[15:0];
                      12'h074: cfg_pair_mode     <= wdata_q[3:0];
                      12'h078: cfg_t_min_ms        <= wdata_q[15:0];
                      12'h07C: cfg_t_max_ms        <= wdata_q[15:0];
                      12'h080: cfg_eps_rel_q16     <= wdata_q[23:0];
                      12'h084: cfg_eps_abs_q8      <= wdata_q[15:0];
                      12'h088: cfg_warmup_ms       <= wdata_q[15:0];
                      12'h08C: begin
                          cfg_settle_enable <= wdata_q[0];
                          cfg_reinit        <= wdata_q[1];
                      end
                      12'h090: cfg_t_skip_ms       <= wdata_q[15:0];
                      12'h094: cfg_seg_ms          <= wdata_q[15:0];
                      12'h098: cfg_settle_k        <= wdata_q[3:0];
                      12'h09C: cfg_cfg_timeout_ms  <= wdata_q[15:0];
                      12'h0A0: cfg_center[0]       <= wdata_q[15:0];
                      12'h0A4: cfg_center[1]       <= wdata_q[15:0];
                      12'h0A8: cfg_center[2]       <= wdata_q[15:0];
                      12'h0AC: cfg_center[3]       <= wdata_q[15:0];
                      12'h0B0: cfg_center[4]       <= wdata_q[15:0];
                      12'h0B4: cfg_center[5]       <= wdata_q[15:0];
                      12'h0B8: cfg_center[6]       <= wdata_q[15:0];
                      12'h0BC: cfg_center[7]       <= wdata_q[15:0];
                      12'h0C0: cfg_if[0]           <= wdata_q[27:0];
                      12'h0C4: cfg_if[1]           <= wdata_q[27:0];
                      12'h0C8: cfg_if[2]           <= wdata_q[27:0];
                      12'h0CC: cfg_if[3]           <= wdata_q[27:0];
                      12'h0D0: cfg_ir[0]           <= wdata_q[27:0];
                      12'h0D4: cfg_ir[1]           <= wdata_q[27:0];
                      12'h0D8: cfg_ir[2]           <= wdata_q[27:0];
                      12'h0DC: cfg_ir[3]           <= wdata_q[27:0];
                      default: begin end
                  endcase
              end
          end
      end
  end

  
  
  always @* res_addr = s_axi_araddr[7:2];

  always @(posedge clk) begin
      if (!rst_n) begin
          rvalid_q <= 1'b0;
          rdata_q  <= 32'd0;
      end else begin
          if (rvalid_q && s_axi_rready) rvalid_q <= 1'b0;
          if (s_axi_arvalid && s_axi_arready) begin
              rvalid_q <= 1'b1;
              if (s_axi_araddr[11:8] == 4'h1) begin
                  rdata_q <= ar_res_data;
              end else begin
                  case (s_axi_araddr[11:0])
                      12'h000: rdata_q <= FPD_ID;
                      12'h004: rdata_q <= FPD_VERSION;
                      12'h008: rdata_q <= FPD_CAPS;
                      12'h00C: rdata_q <= {ar_flags, ar_reason, 2'd0, ar_state,
                                           2'd0, mc_hung, ar_result_valid,
                                           ar_owned, ar_error, ar_done, ar_busy};
                      12'h010: rdata_q <= {18'd0, cmd_range, 2'd0, cmd_mode, 8'd0};
                      12'h014: rdata_q <= {16'd0, ar_flags, ar_reason};
                      12'h018: rdata_q <= sample_count;
                      12'h01C: rdata_q <= {bad_frames, cfg_frames};
                      12'h020: rdata_q <= rate_last;
                      12'h024: rdata_q <= ar_mismatch;
                      12'h028: rdata_q <= {8'd0, last_label_valid, 4'd0, last_label, last_code};
                      12'h02C: rdata_q <= allf_base;
                      12'h030: rdata_q <= {15'd0, mc_hung, axi_err_count};
                      12'h040: rdata_q <= {28'd0, cfg_range_mask};
                      12'h044: rdata_q <= {16'd0, cfg_s_hi};
                      12'h048: rdata_q <= {16'd0, cfg_s_lo};
                      12'h04C: rdata_q <= {16'd0, cfg_raw_sat};
                      12'h050: rdata_q <= {8'd0, cfg_lin_tol_q16};
                      12'h054: rdata_q <= {16'd0, cfg_lin_min};
                      12'h058: rdata_q <= {16'd0, cfg_open_vmax};
                      12'h05C: rdata_q <= {8'd0, cfg_open_iratio_q16};
                      12'h060: rdata_q <= {8'd0, cfg_open_vratio_q16};
                      12'h064: rdata_q <= {16'd0, cfg_noise_floor};
                      12'h068: rdata_q <= {8'd0, cfg_hyst_q16};
                      12'h06C: rdata_q <= {16'd0, cfg_pilot_win_ms};
                      12'h070: rdata_q <= {16'd0, cfg_meas_win_ms};
                      12'h074: rdata_q <= {28'd0, cfg_pair_mode};
                      12'h078: rdata_q <= {16'd0, cfg_t_min_ms};
                      12'h07C: rdata_q <= {16'd0, cfg_t_max_ms};
                      12'h080: rdata_q <= {8'd0, cfg_eps_rel_q16};
                      12'h084: rdata_q <= {16'd0, cfg_eps_abs_q8};
                      12'h088: rdata_q <= {16'd0, cfg_warmup_ms};
                      12'h08C: rdata_q <= {30'd0, cfg_reinit, cfg_settle_enable};
                      12'h090: rdata_q <= {16'd0, cfg_t_skip_ms};
                      12'h094: rdata_q <= {16'd0, cfg_seg_ms};
                      12'h098: rdata_q <= {28'd0, cfg_settle_k};
                      12'h09C: rdata_q <= {16'd0, cfg_cfg_timeout_ms};
                      12'h0A0: rdata_q <= {16'd0, cfg_center[0]};
                      12'h0A4: rdata_q <= {16'd0, cfg_center[1]};
                      12'h0A8: rdata_q <= {16'd0, cfg_center[2]};
                      12'h0AC: rdata_q <= {16'd0, cfg_center[3]};
                      12'h0B0: rdata_q <= {16'd0, cfg_center[4]};
                      12'h0B4: rdata_q <= {16'd0, cfg_center[5]};
                      12'h0B8: rdata_q <= {16'd0, cfg_center[6]};
                      12'h0BC: rdata_q <= {16'd0, cfg_center[7]};
                      12'h0C0: rdata_q <= {4'd0, cfg_if[0]};
                      12'h0C4: rdata_q <= {4'd0, cfg_if[1]};
                      12'h0C8: rdata_q <= {4'd0, cfg_if[2]};
                      12'h0CC: rdata_q <= {4'd0, cfg_if[3]};
                      12'h0D0: rdata_q <= {4'd0, cfg_ir[0]};
                      12'h0D4: rdata_q <= {4'd0, cfg_ir[1]};
                      12'h0D8: rdata_q <= {4'd0, cfg_ir[2]};
                      12'h0DC: rdata_q <= {4'd0, cfg_ir[3]};
                      12'h218: rdata_q <= TICK_CYCLES;
                      default: rdata_q <= 32'd0;
                  endcase
              end
          end
      end
  end

endmodule
