`timescale 1ns/1ps

module tb_all_final_window_product;
    logic clk = 1'b0;
    logic reset_n = 1'b0;
    logic RVS = 1'b0;
    logic SDO0 = 1'b0;
    logic sensor = 1'b0;
    logic r_sensor = 1'b1;
    logic x_trig_in = 1'b0;
    logic start = 1'b0;
    wire SDI, SCLK, CS, RST, uart_tx;
    wire step_pulse, dir, ena, err_flag, cycle_done;
    wire x_pul_out, x_dir_out, led_meas_cnt0;
    wire r_pul_out, r_dir_out, r_ena_out;

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

    ALL_Final #(
        .STEPS_FORWARD(4), .PULSE_HALF(2), .SLOW_DIV(1), .PAUSE_CLKS(4),
        .BACK_MAX_STEP(4), .READY_WAIT_CNT(2), .SEN_DELAY_CNT(1),
        .BACK_FAIL_WAIT(8), .x_PUL_NUM(2), .x_HALF_PERIOD(1),
        .x_DEBOUNCE_CNT(1), .R_PULSE_HALF(2), .R_SLOW_DIV(1),
        .R_DIR_SETUP_CYCLES(2), .R_HOME_DEBOUNCE_CYCLES(1),
        .R_TIMEOUT_CYCLES(2000), .Z_DIR_SETUP_CYCLES(2),
        .Z_TIMEOUT_CYCLES(2000), .Z_MAX_STEPS(100), .WAIT_CYCLE(2),
        .STATS_WINDOW_CYCLES(20), .TOTAL_CHAR(4)
    ) dut (
        .RVS, .SDO0, .S_AXI_ACLK(clk), .S_AXI_ARESETN(reset_n), .sensor,
        .SDI, .SCLK, .CS, .RST, .uart_tx, .step_pulse, .dir, .ena,
        .err_flag, .cycle_done, .x_trig_in, .x_pul_out, .x_dir_out,
        .r_pul_out, .r_dir_out, .r_ena_out, .r_sensor,
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
        end
    endtask

    initial begin
        repeat (4) @(posedge clk);
        reset_n <= 1'b1;
        repeat (2) @(posedge clk);

        axi_write(32'hB4, 32'd320);
        axi_write(32'hC0, 32'd2);
        axi_write(32'hD0, 32'h2); // commit coefficient

        axi_write(32'hB8, 32'd32000);
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
        axi_write(32'hBC, 32'h8); // stop window before the long AXI read sequence
        while (!dut.window_product_ready) @(posedge clk);
        axi_read(32'hD4, read_value);
        if ((read_value & 32'h2) !== 32'h2) $fatal(1, "product ready missing: %h", read_value);
        axi_read(32'hC4, read_value);
        if (read_value !== 32'd1800) $fatal(1, "product low=%0d", read_value);
        axi_read(32'hC8, read_value);
        if (read_value !== 32'd0) $fatal(1, "product mid=%0d", read_value);
        axi_read(32'hCC, read_value);
        if (read_value !== 32'd0) $fatal(1, "product high=%0d", read_value);
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

        $display("PASS: ADC window Q8.24 product seq=1 sum=900 coeff=2 product=1800");
        $finish;
    end
endmodule
