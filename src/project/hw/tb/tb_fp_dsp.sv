// Native-voltage compact FP_DSP + ALL_Final end-to-end self-check.
`timescale 1ns/1ps












module tb_fp_dsp;
    logic clk = 1'b0;
    logic reset_n = 1'b0;
    logic RVS = 1'b1;
    logic SDO0 = 1'b0;
    logic sensor = 1'b0;
    logic r_sensor = 1'b1;
    logic x_trig_in = 1'b0;
    logic start = 1'b0;

    wire SDI, SCLK, CS, RST, uart_tx;
    wire step_pulse, dir, ena, err_flag, cycle_done;
    wire x_pul_out, x_dir_out, led_meas_cnt0;
    wire r_pul_out, r_dir_out, r_ena_out;
    wire range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl;
    wire pol_i_ctrl, pol_v_ctrl, current_en;
    wire dac_sclk, dac_din, dac_sync_n;

    always #10 clk = ~clk;   

    
    localparam real VPC    = 156.25e-6;      
    localparam int  CENTER = 48768;                
    real if_a [0:3] = '{106.7675194836567e-6, 949.6196325972225e-6,
                        8.955403978230587e-3, 86.57217119232472e-3};
    real ir_a [0:3] = '{101.53005040316653e-6, 884.0039433859044e-6,
                        8.277879981034422e-3, 80.88461584683777e-3};
    real    model_ohm = 99.7;
    real    model_e_v = 0.003;
    bit     model_open = 1'b0;
    bit     model_noise = 1'b0;     
    int     frame_no = 0;
    
    
    localparam int  TB_TICK   = 400;
    localparam real SINE_T_NS = 20.0 * TB_TICK * 20.0;
    real    model_sine_amp = 0.0;   
    
    
    localparam real TR_TAU_NS = 30.0 * TB_TICK * 20.0;
    real    model_tr_amp = 0.0;     
    realtime t_on = 0;
    always @(current_en or pol_i_ctrl or range0_ctrl or range1_ctrl or range2_ctrl or range3_ctrl)
        if (current_en) t_on = $realtime;

    function automatic int delta_code(int r, bit rev);
        real v;
        begin
            v = model_open ? 0.0 : ((rev ? ir_a[r] : if_a[r]) * model_ohm);
            v = v + (rev ? -model_e_v : model_e_v);
            delta_code = $rtoi(v / VPC + ((v >= 0.0) ? 0.5 : -0.5));
        end
    endfunction

    function automatic int pin_code();
        int r;
        begin
            pin_code = CENTER;
            if (current_en) begin
                r = range0_ctrl ? 0 : range1_ctrl ? 1 : range2_ctrl ? 2 : 3;
                pin_code = CENTER + delta_code(r, pol_i_ctrl);
                if (model_tr_amp != 0.0)
                    pin_code = pin_code + $rtoi($floor(model_tr_amp *
                               $exp(-($realtime - t_on) / TR_TAU_NS) + 0.5));
            end
            if (model_noise) pin_code = pin_code + (frame_no % 7) - 3;
            if (model_sine_amp != 0.0)
                pin_code = pin_code + $rtoi($floor(model_sine_amp *
                           $sin(2.0 * 3.14159265358979 * $realtime / SINE_T_NS) + 0.5));
        end
    endfunction

    logic [32:0] adc_sh;
    logic [15:0] adc_code;
    always @(negedge CS) begin
        frame_no = frame_no + 1;
        adc_code = pin_code();
        adc_sh   = {1'b0, adc_code, 16'h0000};   
        SDO0     = adc_sh[32];
    end
    always @(negedge SCLK) begin
        if (!CS) begin
            adc_sh = {adc_sh[31:0], 1'b0};
            SDO0   = adc_sh[32];
        end
    end
    always @(posedge CS) begin
        RVS <= 1'b0;
        repeat (4) @(posedge clk);
        RVS <= 1'b1;
    end

    
    logic [15:0] p_awaddr = '0; logic p_awvalid = 0; wire p_awready;
    logic [31:0] p_wdata = '0;  logic p_wvalid = 0;  wire p_wready;
    wire [1:0] p_bresp; wire p_bvalid; logic p_bready = 0;
    logic [15:0] p_araddr = '0; logic p_arvalid = 0; wire p_arready;
    wire [31:0] p_rdata; wire [1:0] p_rresp; wire p_rvalid; logic p_rready = 0;

    
    wire [31:0] f_awaddr; wire [2:0] f_awprot; wire f_awvalid; wire f_awready;
    wire [31:0] f_wdata;  wire [3:0] f_wstrb;  wire f_wvalid;  wire f_wready;
    wire [1:0] f_bresp; wire f_bvalid; wire f_bready;
    wire [31:0] f_araddr; wire [2:0] f_arprot; wire f_arvalid; wire f_arready;
    wire [31:0] f_rdata; wire [1:0] f_rresp; wire f_rvalid; wire f_rready;

    
    logic [31:0] t_awaddr = '0; logic t_awvalid = 0; wire t_awready;
    logic [31:0] t_wdata = '0;  logic t_wvalid = 0;  wire t_wready;
    wire [1:0] t_bresp; wire t_bvalid; logic t_bready = 0;
    logic [31:0] t_araddr = '0; logic t_arvalid = 0; wire t_arready;
    wire [31:0] t_rdata; wire [1:0] t_rresp; wire t_rvalid; logic t_rready = 0;

    
    wire [31:0] s_awaddr, s_wdata, s_araddr, s_rdata;
    wire s_awvalid, s_awready, s_wvalid, s_wready, s_bvalid, s_bready;
    wire s_arvalid, s_arready, s_rvalid, s_rready;
    wire [1:0] s_bresp, s_rresp;

    
    logic g_valid = 0, g_tb = 0;
    always @(posedge clk) begin
        if (!reset_n) begin
            g_valid <= 0; g_tb <= 0;
        end else if (!g_valid) begin
            if (f_awvalid || f_arvalid)      begin g_valid <= 1; g_tb <= 0; end
            else if (t_awvalid || t_arvalid) begin g_valid <= 1; g_tb <= 1; end
        end else if ((s_bvalid && s_bready) || (s_rvalid && s_rready)) begin
            g_valid <= 0;
        end
    end
    wire gf = g_valid && !g_tb;
    wire gt = g_valid &&  g_tb;
    assign s_awaddr  = g_tb ? t_awaddr : f_awaddr;
    assign s_wdata   = g_tb ? t_wdata  : f_wdata;
    assign s_araddr  = g_tb ? t_araddr : f_araddr;
    assign s_awvalid = (gf && f_awvalid) || (gt && t_awvalid);
    assign s_wvalid  = (gf && f_wvalid)  || (gt && t_wvalid);
    assign s_arvalid = (gf && f_arvalid) || (gt && t_arvalid);
    assign s_bready  = (gf && f_bready)  || (gt && t_bready);
    assign s_rready  = (gf && f_rready)  || (gt && t_rready);
    assign f_awready = gf && s_awready;  assign t_awready = gt && s_awready;
    assign f_wready  = gf && s_wready;   assign t_wready  = gt && s_wready;
    assign f_arready = gf && s_arready;  assign t_arready = gt && s_arready;
    assign f_bvalid  = gf && s_bvalid;   assign t_bvalid  = gt && s_bvalid;
    assign f_rvalid  = gf && s_rvalid;   assign t_rvalid  = gt && s_rvalid;
    assign f_bresp = s_bresp; assign t_bresp = s_bresp;
    assign f_rresp = s_rresp; assign t_rresp = s_rresp;
    assign f_rdata = s_rdata; assign t_rdata = s_rdata;

    ALL_Final #(
        .STEPS_FORWARD(4), .PULSE_HALF(2), .SLOW_DIV(1), .PAUSE_CLKS(4),
        .BACK_MAX_STEP(4), .READY_WAIT_CNT(2), .SEN_DELAY_CNT(1),
        .BACK_FAIL_WAIT(8), .x_PUL_NUM(2), .x_HALF_PERIOD(1),
        .x_DEBOUNCE_CNT(1), .R_PULSE_HALF(2), .R_SLOW_DIV(1),
        .R_DIR_SETUP_CYCLES(2), .R_HOME_DEBOUNCE_CYCLES(1),
        .R_TIMEOUT_CYCLES(2000), .Z_DIR_SETUP_CYCLES(2),
        .Z_TIMEOUT_CYCLES(2000), .Z_MAX_STEPS(100), .WAIT_CYCLE(2),
        .TOTAL_CHAR(4),
        .ANALOG_SETTLE_CYCLES(20), .DAC_HALF_CYCLES(1),
        .ADC_PWRUP_DELAY_CYCLES(32'd100)
    ) u_all (
        .RVS, .SDO0, .S_AXI_ACLK(clk), .S_AXI_ARESETN(reset_n), .sensor,
        .SDI, .SCLK, .CS, .RST, .uart_tx, .step_pulse, .dir, .ena,
        .err_flag, .cycle_done, .x_trig_in, .x_pul_out, .x_dir_out,
        .r_pul_out, .r_dir_out, .r_ena_out, .r_sensor,
        .start, .led_meas_cnt0,
        .range0_ctrl, .range1_ctrl, .range2_ctrl, .range3_ctrl,
        .pol_i_ctrl, .pol_v_ctrl, .current_en,
        .dac_sclk, .dac_din, .dac_sync_n,
        .S_AXI_AWADDR(s_awaddr), .S_AXI_AWVALID(s_awvalid), .S_AXI_AWREADY(s_awready),
        .S_AXI_WDATA(s_wdata), .S_AXI_WSTRB(4'hF), .S_AXI_WVALID(s_wvalid), .S_AXI_WREADY(s_wready),
        .S_AXI_BRESP(s_bresp), .S_AXI_BVALID(s_bvalid), .S_AXI_BREADY(s_bready),
        .S_AXI_ARADDR(s_araddr), .S_AXI_ARVALID(s_arvalid), .S_AXI_ARREADY(s_arready),
        .S_AXI_RDATA(s_rdata), .S_AXI_RRESP(s_rresp), .S_AXI_RVALID(s_rvalid), .S_AXI_RREADY(s_rready)
    );

    fp_dsp #(.TICK_CYCLES(TB_TICK), .POLL_CYCLES(8), .AXI_TIMEOUT_CYCLES(4000)) u_fp (
        .aclk(clk), .aresetn(reset_n),
        .s_axi_awaddr(p_awaddr), .s_axi_awprot(3'b000), .s_axi_awvalid(p_awvalid),
        .s_axi_awready(p_awready), .s_axi_wdata(p_wdata), .s_axi_wstrb(4'hF),
        .s_axi_wvalid(p_wvalid), .s_axi_wready(p_wready), .s_axi_bresp(p_bresp),
        .s_axi_bvalid(p_bvalid), .s_axi_bready(p_bready), .s_axi_araddr(p_araddr),
        .s_axi_arprot(3'b000), .s_axi_arvalid(p_arvalid), .s_axi_arready(p_arready),
        .s_axi_rdata(p_rdata), .s_axi_rresp(p_rresp), .s_axi_rvalid(p_rvalid),
        .s_axi_rready(p_rready),
        .m_axi_awaddr(f_awaddr), .m_axi_awprot(f_awprot), .m_axi_awvalid(f_awvalid),
        .m_axi_awready(f_awready), .m_axi_wdata(f_wdata), .m_axi_wstrb(f_wstrb),
        .m_axi_wvalid(f_wvalid), .m_axi_wready(f_wready), .m_axi_bresp(f_bresp),
        .m_axi_bvalid(f_bvalid), .m_axi_bready(f_bready), .m_axi_araddr(f_araddr),
        .m_axi_arprot(f_arprot), .m_axi_arvalid(f_arvalid), .m_axi_arready(f_arready),
        .m_axi_rdata(f_rdata), .m_axi_rresp(f_rresp), .m_axi_rvalid(f_rvalid),
        .m_axi_rready(f_rready),
        .spi_cs(CS), .spi_sclk(SCLK), .spi_sdo(SDO0),
        .range0_pin(range0_ctrl), .range1_pin(range1_ctrl), .range2_pin(range2_ctrl),
        .range3_pin(range3_ctrl), .pol_i_pin(pol_i_ctrl), .pol_v_pin(pol_v_ctrl),
        .current_en_pin(current_en)
    );

    
    task automatic fp_write(input [15:0] addr, input [31:0] value);
        begin
            @(negedge clk);
            p_awaddr <= addr; p_awvalid <= 1; p_wdata <= value; p_wvalid <= 1;
            while (!p_awready || !p_wready) @(negedge clk);
            @(negedge clk);
            p_awvalid <= 0; p_wvalid <= 0; p_bready <= 1;
            while (!p_bvalid) @(negedge clk);
            if (p_bresp !== 2'b00) $fatal(1, "fp_dsp write response error");
            @(negedge clk);
            p_bready <= 0;
        end
    endtask

    task automatic fp_read(input [15:0] addr, output [31:0] value);
        begin
            @(negedge clk);
            p_araddr <= addr; p_arvalid <= 1;
            while (!p_arready) @(negedge clk);
            @(negedge clk);
            p_arvalid <= 0; p_rready <= 1;
            while (!p_rvalid) @(negedge clk);
            value = p_rdata;
            @(negedge clk);
            p_rready <= 0;
        end
    endtask

    task automatic af_write(input [31:0] addr, input [31:0] value);
        begin
            @(negedge clk);
            t_awaddr <= addr; t_awvalid <= 1; t_wdata <= value; t_wvalid <= 1;
            while (!(t_awready && t_wready)) @(negedge clk);
            @(negedge clk);
            t_awvalid <= 0; t_wvalid <= 0; t_bready <= 1;
            while (!t_bvalid) @(negedge clk);
            @(negedge clk);
            t_bready <= 0;
        end
    endtask

    task automatic wait_done(output [31:0] st);
        int n;
        begin
            n = 0;
            do begin
                repeat (500) @(posedge clk);
                fp_read(16'h00C, st);
                n++;
                if (n > 20000) $fatal(1, "FP_DSP run did not finish, status=%h", st);
            end while (st[0] || !st[1]);
        end
    endtask

    task automatic wait_state(input [5:0] s);
        logic [31:0] st;
        int n;
        begin
            n = 0;
            do begin
                repeat (50) @(posedge clk);
                fp_read(16'h00C, st);
                n++;
                if (n > 50000) $fatal(1, "FP_DSP never reached state %0d", s);
            end while (st[13:8] != s);
        end
    endtask

    task automatic check_safe(input string where);
        begin
            if ({range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl,
                 pol_i_ctrl, pol_v_ctrl, current_en} !== 7'b0)
                $fatal(1, "%s: analog outputs not safe after the run", where);
        end
    endtask

    task automatic start_run(input [1:0] mode, input [1:0] range);
        begin
            fp_write(16'h010, 32'h4);                                   
            fp_write(16'h010, 32'h1 | (mode << 8) | (range << 12));     
        end
    endtask

    logic [31:0] st, v, n_f, n_r, lo, hi, w;
    longint      sum_f;
    int          dF1, dR1, s_exp;
    int          k, total, found_e;
    real         amp50, amp75, amp100;
    int          nwin, nlen;
    int          fit0, fit1, e, fits_r1, a_codes, v_exp;
    logic [31:0] fw0, fwv, fwa;
    localparam [5:0] S_SETTLE = 6'd12;

    initial begin
        repeat (5) @(posedge clk);
        reset_n <= 1;
        repeat (5) @(posedge clk);

        fp_read(16'h000, v);
        if (v !== 32'h4650_4431) $fatal(1, "FP_DSP ID %h", v);
        fp_read(16'h008, v);
        if (v[4] !== 1'b1 || v[10] !== 1'b1) $fatal(1, "CAPS %h", v);

        
        fp_write(16'h06C, 20);    
        fp_write(16'h070, 40);    
        fp_write(16'h078, 40);    
        fp_write(16'h07C, 2000);  
        fp_write(16'h090, 10);    
        fp_write(16'h094, 20);    
        fp_write(16'h09C, 50);    
        fp_write(16'h0C0, 106768);   fp_write(16'h0D0, 101530);
        fp_write(16'h0C4, 949620);   fp_write(16'h0D4, 884004);
        fp_write(16'h0C8, 8955404);  fp_write(16'h0D8, 8277880);
        fp_write(16'h0CC, 86572171); fp_write(16'h0DC, 80884616);
        fp_read(16'h0C8, v);
        if (v !== 32'd8955404) $fatal(1, "current register read back %0d", v);

        
        repeat (5000) @(posedge clk);
        fp_read(16'h018, v);
        if (v == 0) $fatal(1, "sniffer saw no ADC data frames");
        fp_read(16'h01C, v);
        if (v[31:16] != 0) $fatal(1, "sniffer saw %0d bad frames", v[31:16]);

        
        start_run(2'd0, 2'd0);
        wait_done(st);
        if (!st[2] || st[23:16] != 8'd16) $fatal(1, "unclaimed START: status %h", st);
        check_safe("unclaimed");
        fp_write(16'h010, 32'h8);                                       
        fp_read(16'h00C, st);
        if (!st[3]) $fatal(1, "CLAIM not accepted");

        
        model_ohm = 99.7; model_e_v = 0.003; model_open = 0;
        dF1 = delta_code(1, 0); dR1 = delta_code(1, 1);
        s_exp = ((dF1 + dR1) * 256) >>> 1;
        start_run(2'd0, 2'd0);
        wait_done(st);
        if (st[2] || !st[4]) $fatal(1, "FULL 99.7 ohm failed: status %h", st);
        if (st[23:16] != 8'd0) $fatal(1, "FULL 99.7 ohm reason %0d", st[23:16]);
        fp_read(16'h100, v);
        if (v[1:0] != 2'd1 || v[7:4] != 4'b0011) $fatal(1, "FULL selection word %h", v);
        fp_read(16'h180, v);
        if ($signed(v) != s_exp) $fatal(1, "S = %0d, expected %0d", $signed(v), s_exp);
        fp_read(16'h19C, w);
        if (w[4:0] != 5'd1 || w[20:16] != 5'd1) $fatal(1, "ABBA windows %h", w);
        fp_read(16'h1A0, lo); fp_read(16'h1A4, hi); fp_read(16'h1B0, n_f);
        sum_f = {hi[15:0], lo};
        if (n_f == 0 || sum_f != longint'(n_f) * (CENTER + dF1))
            $fatal(1, "forward aggregate sum %0d over %0d samples", sum_f, n_f);
        fp_read(16'h1D0, n_r);
        if (n_r == 0) $fatal(1, "reverse aggregate empty");
        fp_read(16'h024, v);
        if (v != 0) $fatal(1, "%0d samples outside the commanded relay state", v);
        check_safe("FULL");

        
        start_run(2'd1, 2'd1);
        wait_done(st);
        if (st[2] || st[23:16] != 8'd0 || st[26]) $fatal(1, "VERIFY keep: status %h", st);
        fp_read(16'h100, v);
        if (v[1:0] != 2'd1) $fatal(1, "VERIFY keep selected %0d", v[1:0]);
        check_safe("VERIFY keep");

        
        start_run(2'd1, 2'd2);
        wait_done(st);
        if (st[2] || !st[26]) $fatal(1, "VERIFY rerange: status %h", st);
        fp_read(16'h100, v);
        if (v[1:0] != 2'd1) $fatal(1, "VERIFY rerange selected %0d", v[1:0]);
        check_safe("VERIFY rerange");

        
        model_open = 1; model_e_v = 0.008;
        start_run(2'd0, 2'd0);
        wait_done(st);
        if (!st[2] || st[23:16] != 8'd8) $fatal(1, "open loop: status %h", st);
        fp_read(16'h100, v);
        if (v[7:4] != 4'b0111) $fatal(1, "open loop tested %b", v[7:4]);
        check_safe("open loop");
        
        
        model_e_v = 0.8;
        start_run(2'd0, 2'd0);
        wait_done(st);
        if (!st[2] || st[23:16] != 8'd8)
            $fatal(1, "open loop with 0.8 V EMF: status %h", st);
        check_safe("open loop high EMF");
        fp_read(16'h100, v);
        if (v[7:4] != 4'b0111) $fatal(1, "high-EMF open loop tested %b", v[7:4]);
        
        
        start_run(2'd1, 2'd1);
        wait_done(st);
        if (!st[2] || st[23:16] != 8'd8)
            $fatal(1, "VERIFY high-EMF open loop: status %h", st);
        check_safe("VERIFY high-EMF open loop");
        model_open = 0; model_e_v = 0.003;

        
        start_run(2'd0, 2'd0);
        wait_state(S_SETTLE);
        af_write(32'h4000_00D0, 32'h2);                                 
        wait_done(st);
        if (!st[2] || st[23:16] != 8'd13) $fatal(1, "ownership conflict: status %h", st);
        check_safe("ownership");

        
        start_run(2'd2, 2'd1);
        wait_done(st);
        if (st[2] || !st[4]) $fatal(1, "FORCED failed %h",st);
        fp_read(16'h19C,w);
        if(w[4:0]!=1 || w[20:16]!=1) $fatal(1,"pair windows %h",w);
        check_safe("FORCED");
        fp_read(16'h008,v);
        if(v != 32'h417) $fatal(1,"unexpected compact CAPS %h",v);
        fp_read(16'h004,v);
        if(v != 5) $fatal(1,"unexpected compact version %h",v);
        fp_read(16'h300,v);
        if(v != 0) $fatal(1,"removed diagnostics must read zero");

        
        start_run(2'd0, 2'd0);
        wait_state(S_SETTLE);
        af_write(32'h4000_0000, 32'h20);                                
        wait_done(st);
        if (!st[2] || st[23:16] != 8'd12) $fatal(1, "reset: status %h", st);
        check_safe("reset");
        start_run(2'd0, 2'd0);
        wait_done(st);
        if (!st[2] || st[23:16] != 8'd12) $fatal(1, "START while latched: status %h", st);
        check_safe("latched");

        $display("PASS: compact FP_DSP FULL/VERIFY/FORCED, one F/R pair, native voltage, open-loop/ownership/reset");
        $finish;
    end
endmodule
