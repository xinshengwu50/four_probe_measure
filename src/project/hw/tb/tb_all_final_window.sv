`timescale 1ns/1ps

module tb_all_final_window;
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
    logic [31:0] read_value;

    always #10 clk = ~clk;
    always @(posedge CS) begin
        RVS <= 1'b0;
        repeat (4) @(posedge clk);
        RVS <= 1'b1;
    end


    ALL_Final #(
        .STEPS_FORWARD(4), .PULSE_HALF(2), .SLOW_DIV(1), .PAUSE_CLKS(4),
        .BACK_MAX_STEP(4), .READY_WAIT_CNT(2), .SEN_DELAY_CNT(1),
        .BACK_FAIL_WAIT(8), .x_PUL_NUM(2), .x_HALF_PERIOD(1),
        .x_DEBOUNCE_CNT(1), .R_PULSE_HALF(2), .R_SLOW_DIV(1),
        .R_DIR_SETUP_CYCLES(2), .R_HOME_DEBOUNCE_CYCLES(1),
        .R_TIMEOUT_CYCLES(2000), .Z_DIR_SETUP_CYCLES(2),
        .Z_TIMEOUT_CYCLES(2000), .Z_MAX_STEPS(100), .WAIT_CYCLE(2),
        .STATS_WINDOW_CYCLES(200), .RVS_TIMEOUT_CYCLES(16), .TOTAL_CHAR(4)
    ) dut (
        .RVS, .SDO0, .S_AXI_ACLK(clk), .S_AXI_ARESETN(reset_n), .sensor,
        .SDI, .SCLK, .CS, .RST, .uart_tx, .step_pulse, .dir, .ena,
        .err_flag, .cycle_done, .x_trig_in, .x_pul_out, .x_dir_out,
        .r_pul_out, .r_dir_out, .r_ena_out, .r_sensor,
        .range0_ctrl, .range1_ctrl, .range2_ctrl, .range3_ctrl,
        .pol_i_ctrl, .pol_v_ctrl, .current_en,
        .dac_sclk, .dac_din, .dac_sync_n,
        .start, .led_meas_cnt0,
        .S_AXI_AWADDR(awaddr), .S_AXI_AWVALID(awvalid), .S_AXI_AWREADY(awready),
        .S_AXI_WDATA(wdata), .S_AXI_WSTRB(wstrb), .S_AXI_WVALID(wvalid), .S_AXI_WREADY(wready),
        .S_AXI_BRESP(bresp), .S_AXI_BVALID(bvalid), .S_AXI_BREADY(bready),
        .S_AXI_ARADDR(araddr), .S_AXI_ARVALID(arvalid), .S_AXI_ARREADY(arready),
        .S_AXI_RDATA(rdata), .S_AXI_RRESP(rresp), .S_AXI_RVALID(rvalid), .S_AXI_RREADY(rready)
    );

    task automatic axi_write(input [31:0] addr, input [31:0] value);
        begin
            @(negedge clk);
            awaddr <= addr; awvalid <= 1'b1;
            wdata <= value; wstrb <= 4'hF; wvalid <= 1'b1;
            while (!awready || !wready) @(negedge clk);
            @(negedge clk);
            awvalid <= 1'b0; wvalid <= 1'b0; bready <= 1'b1;
            while (!bvalid) @(negedge clk);
            if (bresp !== 2'b00) $fatal(1, "AXI write response error");
            @(negedge clk);
            bready <= 1'b0;
        end
    endtask

    task automatic axi_read(input [31:0] addr, output [31:0] value);
        begin
            @(negedge clk);
            araddr <= addr; arvalid <= 1'b1;
            while (!arready) @(negedge clk);
            @(negedge clk);
            arvalid <= 1'b0; rready <= 1'b1;
            while (!rvalid) @(negedge clk);
            if (rresp !== 2'b00) $fatal(1, "AXI read response error");
            value = rdata;
            @(negedge clk);
            rready <= 1'b0;
            while (rvalid) @(negedge clk);
        end
    endtask

    initial begin
        repeat (4) @(posedge clk);
        reset_n <= 1'b1;
        repeat (2) @(posedge clk);

        // Exercise the four-cycle bubble-sort pipeline through the real
        // sampling state. Median(5,1,4,2,3) must be 3.
        force dut.main_state = 5'd4;
        repeat (2) @(posedge clk);
        force dut.v_sample0 = 16'd5;
        force dut.v_sample1 = 16'd1;
        force dut.v_sample2 = 16'd4;
        force dut.v_sample3 = 16'd2;
        force dut.v_sample4 = 16'd3;
        force dut.sample_cnt = 3'd5;
        force dut.sampling_active = 1'b1;
        wait (dut.voltage_latched);
        if (dut.hold_V_mV !== 16'd3) $fatal(1, "median pipeline value=%0d", dut.hold_V_mV);
        release dut.v_sample0;
        release dut.v_sample1;
        release dut.v_sample2;
        release dut.v_sample3;
        release dut.v_sample4;
        release dut.sample_cnt;
        release dut.sampling_active;
        force dut.main_state = 5'd0;
        @(posedge clk);
        release dut.main_state;

        axi_read(32'hB4, read_value);
        if (read_value !== 32'd0) $fatal(1, "default code min=%0d", read_value);
        axi_read(32'hB8, read_value);
        if (read_value !== 32'd65535) $fatal(1, "default code max=%0d", read_value);

        axi_write(32'hB4, 32'd320);
        axi_write(32'hB8, 32'd32000);
        axi_write(32'hC0, 32'h0100_0000);  // Q8.24 coefficient = 1.0
        axi_write(32'hF0, 32'h2);
        axi_write(32'hBC, 32'h1);
        axi_write(32'hBC, 32'h2);

        force dut.RX_REG = {16'd400, 16'h0000};
        force dut.rx_reg_update_pulse = 1'b1;
        @(posedge clk);
        force dut.RX_REG = {16'd500, 16'h0000};
        @(posedge clk);
        force dut.RX_REG = {16'd100, 16'h0000};
        @(posedge clk);
        force dut.RX_REG = {16'd40000, 16'h0000};
        @(posedge clk);
        release dut.RX_REG;
        release dut.rx_reg_update_pulse;

        while (dut.window_seq == 32'd0) @(posedge clk);
        @(posedge clk);
        axi_read(32'hAC, read_value);
        if (read_value !== 32'd1) $fatal(1, "window seq=%0d", read_value);
        axi_read(32'hA8, read_value);
        if (read_value !== 32'd2) $fatal(1, "window count=%0d", read_value);
        axi_read(32'hA0, read_value);
        if (read_value !== 32'd900) $fatal(1, "window sum low=%0d", read_value);
        axi_read(32'hA4, read_value);
        if (read_value !== 32'd0) $fatal(1, "window sum high=%0d", read_value);
        axi_read(32'hB0, read_value);
        if ((read_value & 32'h1) !== 32'h1) $fatal(1, "window ready missing: %h", read_value);

        // The multiplier pipeline commits the product two clocks after the
        // window boundary.
        while (!dut.window_product_ready) @(posedge clk);
        @(posedge clk);

        axi_read(32'hF4, read_value);
        if ((read_value & 32'h2) !== 32'h2) $fatal(1, "product ready missing: %h", read_value);

        axi_read(32'hC4, read_value);
        if (read_value !== 32'h8400_0000) $fatal(1, "window product low=%0d", read_value);
        axi_read(32'hC8, read_value);
        if (read_value !== 32'd3) $fatal(1, "window product mid=%0d", read_value);
        axi_read(32'hCC, read_value);
        if (read_value !== 32'd0) $fatal(1, "window product high=%0d", read_value);

        $display("PASS: ADC window accumulator seq=1 count=2 sum=900");
        $finish;
    end
endmodule
