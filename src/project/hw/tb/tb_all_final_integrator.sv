`timescale 1ns/1ps

module tb_all_final_integrator;
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

    logic [31:0] awaddr = '0;
    logic awvalid = 1'b0;
    wire awready;
    logic [31:0] wdata = '0;
    logic [3:0] wstrb = 4'hF;
    logic wvalid = 1'b0;
    wire wready;
    wire [1:0] bresp;
    wire bvalid;
    logic bready = 1'b0;
    logic [31:0] araddr = '0;
    logic arvalid = 1'b0;
    wire arready;
    wire [31:0] rdata;
    wire [1:0] rresp;
    wire rvalid;
    logic rready = 1'b0;
    logic [31:0] rv;
    logic [31:0] seq_now;

    always #10 clk = ~clk;

    ALL_Final #(
        .STEPS_FORWARD(8), .PULSE_HALF(2), .SLOW_DIV(1), .PAUSE_CLKS(4),
        .BACK_MAX_STEP(4), .READY_WAIT_CNT(2), .SEN_DELAY_CNT(1),
        .BACK_FAIL_WAIT(8), .x_PUL_NUM(2), .x_HALF_PERIOD(1),
        .x_DEBOUNCE_CNT(1), .R_PULSE_HALF(2), .R_SLOW_DIV(1),
        .R_DIR_SETUP_CYCLES(2), .R_HOME_DEBOUNCE_CYCLES(1),
        .R_TIMEOUT_CYCLES(2000), .Z_DIR_SETUP_CYCLES(2),
        .Z_TIMEOUT_CYCLES(4000), .Z_MAX_STEPS(40), .WAIT_CYCLE(2),
        // 400 cycles: long enough that the register read burst for one
        // snapshot finishes before the next window can overwrite it.
        .STATS_WINDOW_CYCLES(400),
        .TOTAL_CHAR(4), .ANALOG_SETTLE_CYCLES(2)
    ) dut (
        .RVS, .SDO0, .S_AXI_ACLK(clk), .S_AXI_ARESETN(reset_n), .sensor,
        .SDI, .SCLK, .CS, .RST, .uart_tx, .step_pulse, .dir, .ena,
        .err_flag, .cycle_done, .x_trig_in, .x_pul_out, .x_dir_out,
        .r_pul_out, .r_dir_out, .r_ena_out, .r_sensor,
        .range0_ctrl, .range1_ctrl, .range2_ctrl, .range3_ctrl,
        .pol_i_ctrl, .pol_v_ctrl, .current_en,
        .dac_sclk, .dac_din, .dac_sync_n, .start, .led_meas_cnt0,
        .S_AXI_AWADDR(awaddr), .S_AXI_AWVALID(awvalid), .S_AXI_AWREADY(awready),
        .S_AXI_WDATA(wdata), .S_AXI_WSTRB(wstrb), .S_AXI_WVALID(wvalid), .S_AXI_WREADY(wready),
        .S_AXI_BRESP(bresp), .S_AXI_BVALID(bvalid), .S_AXI_BREADY(bready),
        .S_AXI_ARADDR(araddr), .S_AXI_ARVALID(arvalid), .S_AXI_ARREADY(arready),
        .S_AXI_RDATA(rdata), .S_AXI_RRESP(rresp), .S_AXI_RVALID(rvalid), .S_AXI_RREADY(rready)
    );

    task automatic axi_write(input [31:0] addr, input [31:0] data);
        begin
            @(negedge clk);
            awaddr <= addr; awvalid <= 1'b1;
            wdata <= data; wstrb <= 4'hF; wvalid <= 1'b1;
            while (!awready || !wready) @(negedge clk);
            @(negedge clk);
            awvalid <= 1'b0; wvalid <= 1'b0; bready <= 1'b1;
            while (!bvalid) @(negedge clk);
            if (bresp !== 2'b00) $fatal(1, "AXI write error");
            @(negedge clk); bready <= 1'b0;
        end
    endtask

    task automatic axi_read(input [31:0] addr, output [31:0] data);
        begin
            @(negedge clk);
            araddr <= addr; arvalid <= 1'b1;
            while (!arready) @(negedge clk);
            @(negedge clk); arvalid <= 1'b0; rready <= 1'b1;
            while (!rvalid) @(negedge clk);
            if (rresp !== 2'b00) $fatal(1, "AXI read error");
            data = rdata;
            @(negedge clk); rready <= 1'b0;
        end
    endtask

    task automatic inject_code(input [15:0] code);
        begin
            @(negedge clk);
            dut.RX_REG = {code, 16'h0000};
            dut.rx_reg_update_pulse = 1'b1;
            @(posedge clk);
        end
    endtask

    task automatic wait_ready();
        integer i;
        begin
            for (i = 0; i < 2000; i = i + 1) begin
                if (dut.stats_ready[dut.stats_bank_select]) return;
                @(posedge clk);
            end
            $fatal(1, "stats window did not become ready");
        end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        reset_n <= 1'b1;
        repeat (4) @(posedge clk);

        // Bank 0: range 0, forward. Configure a +/- magnitude window.
        dut.analog_range_sel_reg = 2'd0;
        dut.analog_polarity_reg = 1'b0;
        axi_write(32'h128, 32'd0);
        axi_write(32'h12C, 32'd32768);
        axi_write(32'h130, 32'd10);
        axi_write(32'h134, 32'd100);
        axi_write(32'h138, 32'h0001); // CLEAR
        axi_write(32'h138, 32'h0002); // ARM

        inject_code(16'd32818); // +50 valid
        inject_code(16'd32718); // -50 valid
        inject_code(16'd32773); // +5 invalid
        inject_code(16'd32968); // +200 invalid
        wait_ready();

        axi_read(32'h108, rv);
        if (rv !== 32'd2) $fatal(1, "bank0 valid_count=%0d", rv);
        axi_read(32'h114, rv);
        if (rv !== 32'd4) $fatal(1, "bank0 rx_count=%0d", rv);
        axi_read(32'h100, rv);
        if (rv !== 32'd65536) $fatal(1, "bank0 sum_low=%0d", rv);
        axi_read(32'h104, rv);
        if (rv !== 32'd0) $fatal(1, "bank0 sum_high=%0d", rv);
        // SUM_SQUARES regression: 32818^2 + 32718^2 = 2147488648.  The old RTL
        // truncated each product to 17 bits, which would have read 5000 here.
        axi_read(32'h10C, rv);
        if (rv !== 32'd2147488648) $fatal(1, "bank0 sum_sq_low=%0d", rv);
        axi_read(32'h110, rv);
        if (rv !== 32'd0) $fatal(1, "bank0 sum_sq_high=%0d", rv);
        axi_read(32'h118, rv);
        if (rv !== 32'd32718) $fatal(1, "bank0 min=%0d", rv);
        axi_read(32'h11C, rv);
        if (rv !== 32'd32818) $fatal(1, "bank0 max=%0d", rv);
        axi_read(32'h124, rv);
        if ((rv & 32'h1) !== 32'h1) $fatal(1, "bank0 ready missing: %h", rv);
        axi_read(32'h120, seq_now);
        if (seq_now !== 32'd1) $fatal(1, "bank0 seq=%0d", seq_now);

        // ACK_SEQ: an ACK that carries a stale SEQ must NOT clear READY.
        axi_write(32'h144, seq_now + 32'd1);
        axi_write(32'h138, 32'h0004); // ACK with the wrong SEQ
        repeat (2) @(posedge clk);
        axi_read(32'h124, rv);
        if ((rv & 32'h1) !== 32'h1)
            $fatal(1, "stale ACK cleared READY: %h", rv);
        // ... and the ACK carrying the consumed SEQ does clear it.
        axi_write(32'h144, seq_now);
        axi_write(32'h138, 32'h0004); // ACK with the matching SEQ
        repeat (2) @(posedge clk);
        axi_read(32'h124, rv);
        if ((rv & 32'h1) !== 32'h0)
            $fatal(1, "matching ACK did not clear READY: %h", rv);

        // Bank 5: range 1, reverse, different magnitude window.
        dut.analog_range_sel_reg = 2'd1;
        dut.analog_polarity_reg = 1'b1;
        axi_write(32'h128, 32'd5);
        axi_write(32'h12C, 32'd32768);
        axi_write(32'h130, 32'd200);
        axi_write(32'h134, 32'd300);
        axi_write(32'h138, 32'h0001); // CLEAR
        axi_write(32'h138, 32'h0002); // ARM

        inject_code(16'd33018); // +250 valid
        inject_code(16'd32868); // +100 invalid
        wait_ready();

        axi_read(32'h108, rv);
        if (rv !== 32'd1) $fatal(1, "bank5 valid_count=%0d", rv);
        axi_read(32'h118, rv);
        if (rv !== 32'd33018) $fatal(1, "bank5 min=%0d", rv);
        axi_read(32'h11C, rv);
        if (rv !== 32'd33018) $fatal(1, "bank5 max=%0d", rv);
        axi_read(32'h10C, rv);
        if (rv !== ((32'd33018 * 32'd33018) & 32'hFFFF_FFFF))
            $fatal(1, "bank5 sum_sq_low=%0d", rv);
        // A legacy ACK without writing 0x144 still clears READY.
        axi_write(32'h138, 32'h0004);
        repeat (2) @(posedge clk);
        axi_read(32'h124, rv);
        if ((rv & 32'h1) !== 32'h0) $fatal(1, "legacy ACK did not clear READY: %h", rv);

        // FAIL-CLOSED default window: bank 7 was never configured.  Its power-on
        // window must reject every sample instead of accepting them all.
        dut.analog_range_sel_reg = 2'd3;
        dut.analog_polarity_reg = 1'b1;
        axi_write(32'h128, 32'd7);
        axi_read(32'h130, rv);
        if (rv !== 32'h0001_0000) $fatal(1, "bank7 default mag_min=%0d", rv);
        axi_read(32'h134, rv);
        if (rv !== 32'd0) $fatal(1, "bank7 default mag_max=%0d", rv);
        axi_write(32'h12C, 32'd32768); // a center, but no valid magnitude window
        axi_write(32'h138, 32'h0001); // CLEAR
        axi_write(32'h138, 32'h0002); // ARM
        inject_code(16'd32768);
        inject_code(16'd33000);
        wait_ready();
        axi_read(32'h108, rv);
        if (rv !== 32'd0) $fatal(1, "fail-closed bank7 accepted %0d samples", rv);
        axi_read(32'h114, rv);
        if (rv !== 32'd2) $fatal(1, "bank7 rx_count=%0d", rv);
        axi_read(32'h124, rv);
        if ((rv & 32'h2) !== 32'h2) $fatal(1, "bank7 empty flag missing: %h", rv);

        axi_write(32'h138,32'h8); // DISARM
        axi_read(32'h14C,rv);
        if (rv!==32'h49574E31) $fatal(1,"IWN1 absent");
        axi_write(32'h148,32'd0);
        axi_read(32'h148,rv);
        if (rv!==32'd400) $fatal(1,"invalid zero window accepted");
        axi_write(32'h148,32'd1000000);
        axi_read(32'h148,rv);
        if (rv!==32'd1000000) $fatal(1,"20ms not stored");
        // Absolute ADC code interval accepts low probe signals (no 5mV clipping).
        axi_write(32'h12C,32'd0);
        axi_write(32'h130,32'd32769);
        axi_write(32'h134,32'd65534);
        axi_write(32'h138,32'h1);
        axi_write(32'h138,32'h2);
        inject_code(16'd50000);
        inject_code(16'd50001);
        axi_write(32'h148,32'd5000000); // ignored while BUSY
        axi_read(32'h148,rv);
        if (rv!==32'd1000000) $fatal(1,"busy config mutated");
        if (dut.stats_window_cycles_active!==32'd1000000) $fatal(1,"duration not latched");
        // Advance only the test time counter, not the accumulators/data path.
        @(negedge clk);dut.stats_cycle_count=32'd999999;
        wait_ready();
        axi_read(32'h108,rv);
        if (rv!==32'd2) $fatal(1,"absolute ADC gate dropped samples");
        axi_write(32'h138,32'h8);
        axi_write(32'h148,32'd2000000);
        axi_read(32'h148,rv);
        if (rv!==32'd2000000) $fatal(1,"40ms not stored");
        axi_write(32'h148,32'd5000000);
        axi_read(32'h148,rv);
        if (rv!==32'd5000000) $fatal(1,"100ms not stored");
        axi_write(32'h148,32'd5000001);
        axi_read(32'h148,rv);
        if (rv!==32'd5000000) $fatal(1,"oversize window accepted");
        $display("PASS: integrator durations, idle writes, safe-code mean, legacy statistics");
        $finish;
    end
endmodule
