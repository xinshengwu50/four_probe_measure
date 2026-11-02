`timescale 1ns/1ps

module tb_all_final_analog;
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

    logic [23:0] dac_captured = 24'd0;
    integer dac_falling_edges = 0;

    always #10 clk = ~clk;
    always @(posedge CS) begin
        RVS <= 1'b0;
        repeat (4) @(posedge clk);
        RVS <= 1'b1;
    end


    always @(negedge dac_sclk) begin
        if (!dac_sync_n) begin
            dac_captured <= {dac_captured[22:0], dac_din};
            dac_falling_edges <= dac_falling_edges + 1;
        end
    end

    ALL_Final #(
        .STEPS_FORWARD(4), .PULSE_HALF(2), .SLOW_DIV(1), .PAUSE_CLKS(4),
        .BACK_MAX_STEP(4), .READY_WAIT_CNT(2), .SEN_DELAY_CNT(1),
        .BACK_FAIL_WAIT(8), .x_PUL_NUM(2), .x_HALF_PERIOD(1),
        .x_DEBOUNCE_CNT(1), .R_PULSE_HALF(2), .R_SLOW_DIV(1),
        .R_DIR_SETUP_CYCLES(2), .R_HOME_DEBOUNCE_CYCLES(1),
        .R_TIMEOUT_CYCLES(2000), .Z_DIR_SETUP_CYCLES(2),
        .Z_TIMEOUT_CYCLES(2000), .Z_MAX_STEPS(100), .WAIT_CYCLE(2),
        .STATS_WINDOW_CYCLES(4), .TOTAL_CHAR(4),
        .ANALOG_SETTLE_CYCLES(2), .DAC_HALF_CYCLES(1)
    ) dut (
        .RVS, .SDO0, .S_AXI_ACLK(clk), .S_AXI_ARESETN(reset_n), .sensor,
        .SDI, .SCLK, .CS, .RST, .uart_tx, .step_pulse, .dir, .ena,
        .err_flag, .cycle_done, .x_trig_in, .x_pul_out, .x_dir_out,
        .r_pul_out, .r_dir_out, .r_ena_out, .r_sensor,
        .start, .led_meas_cnt0,
        .range0_ctrl, .range1_ctrl, .range2_ctrl, .range3_ctrl,
        .pol_i_ctrl, .pol_v_ctrl, .current_en,
        .dac_sclk, .dac_din, .dac_sync_n,
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

    task automatic check_safe_outputs;
        begin
            if ({range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl,
                 pol_i_ctrl, pol_v_ctrl, current_en} !== 7'b0000000)
                $fatal(1, "Analog outputs are not in safe state: %b",
                       {range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl,
                        pol_i_ctrl, pol_v_ctrl, current_en});
            if ({dac_sclk, dac_sync_n} !== 2'b11)
                $fatal(1, "DAC idle state wrong: sclk=%b sync_n=%b", dac_sclk, dac_sync_n);
        end
    endtask

    integer wait_cycles;
    logic [31:0] seq_before;
    initial begin
        repeat (4) @(posedge clk);
        reset_n <= 1'b1;
        repeat (3) @(posedge clk);
        check_safe_outputs();

        // Direct test mode: K2 and the ADC polarity relay only.
        axi_write(32'hD4, 32'h8000_0022);
        repeat (2) @(posedge clk);
        if ({range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl} !== 4'b0100)
            $fatal(1, "Direct K2 range mask failed: %b",
                   {range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl});
        if ({pol_i_ctrl, pol_v_ctrl} !== 2'b01)
            $fatal(1, "Direct polarity mask failed: %b", {pol_i_ctrl, pol_v_ctrl});

        // Multiple range relays are rejected, even in test mode.
        axi_write(32'hD4, 32'h8000_0103);
        repeat (2) @(posedge clk);
        if ({range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl, current_en} !== 5'b00000)
            $fatal(1, "Multiple range relays were not rejected");
        if (!dut.analog_error) $fatal(1, "Range interlock error flag missing");

        // A live test current prevents hot relay switching. Exit test mode first.
        axi_write(32'hD4, 32'h8000_0101);
        repeat (2) @(posedge clk);
        if (!current_en) $fatal(1, "Direct test current did not assert");
        axi_write(32'hD4, 32'h8000_0102);
        repeat (2) @(posedge clk);
        if ({range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl, current_en} !== 5'b10001)
            $fatal(1, "Hot direct-test relay change was not rejected");

        axi_write(32'hD4, 32'h0000_0000);
        repeat (2) @(posedge clk);
        check_safe_outputs();

        // Normal sequence: disable -> wait -> range/polarity -> wait -> current.
        axi_read(32'hE8, seq_before);
        axi_write(32'hD0, 32'h0000_003D); // start, enable, range3, reverse
        wait_cycles = 0;
        while (!current_en && wait_cycles < 20) begin
            @(posedge clk);
            wait_cycles = wait_cycles + 1;
        end
        if (!current_en) $fatal(1, "Current enable did not assert");
        if ({range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl} !== 4'b0001)
            $fatal(1, "Normal range3 selection failed: %b",
                   {range0_ctrl, range1_ctrl, range2_ctrl, range3_ctrl});
        if ({pol_i_ctrl, pol_v_ctrl} !== 2'b11)
            $fatal(1, "Normal polarity pair failed: %b", {pol_i_ctrl, pol_v_ctrl});
        axi_read(32'hE8, read_value);
        if ((read_value & 32'hFFFF) !== ((seq_before + 1) & 32'hFFFF))
            $fatal(1, "Analog sequence did not advance: before=%0d after=%0d", seq_before, read_value);

        axi_write(32'hD0, 32'h0000_0002);
        repeat (2) @(posedge clk);
        check_safe_outputs();

        // DAC8562 frame: command 011, address DAC-A, code 0x6666.
        axi_read(32'hE4, seq_before);
        axi_write(32'hD8, 32'h0000_6666);
        axi_write(32'hDC, 32'h0000_0001);
        wait_cycles = 0;
        while (dut.dac_seq_reg == seq_before[15:0] && wait_cycles < 200) begin
            @(posedge clk);
            wait_cycles = wait_cycles + 1;
        end
        if (dut.dac_seq_reg == seq_before[15:0]) $fatal(1, "DAC sequence timeout");
        @(negedge clk);
        if (dac_falling_edges != 24) $fatal(1, "DAC falling edges=%0d", dac_falling_edges);
        if (dac_captured !== 24'h186666)
            $fatal(1, "DAC frame mismatch: captured=%h", dac_captured);
        check_safe_outputs();

        $display("PASS: analog control and DAC serializer simulation completed");
        $finish;
    end
endmodule
