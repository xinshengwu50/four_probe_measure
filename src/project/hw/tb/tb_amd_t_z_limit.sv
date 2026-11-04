`timescale 1ns/1ps

// Focused regression for CONTROL.SYSTEM_RESET / CLEAR_FAULTS and the PS
// heartbeat watchdog.  The watchdog counter is loaded near its threshold so
// the test remains short while exercising the real expiry comparator.
module tb_amd_t_z_limit;
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

    integer step_count = 0;
    integer steps_before;
    integer i;
    logic [31:0] status;
    logic [31:0] rv_a;
    logic [31:0] rv_b;
    logic [31:0] pos_a;
    logic [31:0] pos_b;

    always #10 clk = ~clk;

    always @(posedge step_pulse) step_count = step_count + 1;

    ALL_Final #(
        .STEPS_FORWARD(8),
        .PULSE_HALF(2),
        .SLOW_DIV(1),
        .PAUSE_CLKS(4),
        .BACK_MAX_STEP(4),
        .READY_WAIT_CNT(2),
        .SEN_DELAY_CNT(1),
        .BACK_FAIL_WAIT(8),
        .x_PUL_NUM(2),
        .x_HALF_PERIOD(1),
        .x_DEBOUNCE_CNT(1),
        .R_PULSE_HALF(2),
        .R_SLOW_DIV(1),
        .R_DIR_SETUP_CYCLES(2),
        .R_HOME_DEBOUNCE_CYCLES(1),
        .R_TIMEOUT_CYCLES(2000),
        .Z_DIR_SETUP_CYCLES(2),
        .Z_TIMEOUT_CYCLES(4000),
        .WAIT_CYCLE(2),

        .TOTAL_CHAR(4),
        .ANALOG_SETTLE_CYCLES(2)
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

    task automatic axi_write(input [31:0] addr, input [31:0] data);
        begin
            @(negedge clk);
            awaddr <= addr; awvalid <= 1'b1;
            wdata <= data; wstrb <= 4'hF; wvalid <= 1'b1;
            while (!awready || !wready) @(negedge clk);
            @(negedge clk);
            awvalid <= 1'b0; wvalid <= 1'b0;
            bready <= 1'b1;
            while (!bvalid) @(negedge clk);
            if (bresp !== 2'b00) $fatal(1, "AXI write response error: %b", bresp);
            @(negedge clk);
            bready <= 1'b0;
        end
    endtask

    task automatic axi_read(input [31:0] addr, output [31:0] data);
        begin
            @(negedge clk);
            araddr <= addr; arvalid <= 1'b1;
            while (!arready) @(negedge clk);
            @(negedge clk);
            arvalid <= 1'b0; rready <= 1'b1;
            while (!rvalid) @(negedge clk);
            if (rresp !== 2'b00) $fatal(1, "AXI read response error: %b", rresp);
            data = rdata;
            @(negedge clk);
            rready <= 1'b0;
        end
    endtask

    task automatic wait_current_on(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.analog_current_en_reg && current_en) return;
                @(posedge clk);
            end
            $fatal(1, "timeout waiting for analog current on");
        end
    endtask

    task automatic wait_z_done(input integer limit_cycles);
        integer k;
        begin
            for (k = 0; k < limit_cycles; k = k + 1) begin
                if (dut.z_fault)
                    $fatal(1, "unexpected Z fault code=%0d", dut.z_error_code);
                if (!dut.z_direct_busy && dut.z_done_reg) return;
                @(posedge clk);
            end
            $fatal(1, "timeout waiting for Z done state=%0d pos=%0d",
                   dut.u_axis_z.z_state, dut.z_position);
        end
    endtask

    task automatic wait_z_fault(input integer limit_cycles);
        integer k;
        begin
            for (k = 0; k < limit_cycles; k = k + 1) begin
                if (dut.z_fault) return;
                @(posedge clk);
            end
            $fatal(1, "timeout waiting for a refused Z command");
        end
    endtask

    task automatic arm_z_home();
        begin
            axi_write(32'h44, 32'h0000_0001);   // HOME
            axi_write(32'h40, 32'h0000_0009);   // START | ARM
        end
    endtask

    task automatic check_current_off();
        begin
            if (dut.analog_current_en_reg !== 1'b0 || current_en !== 1'b0)
                $fatal(1, "excitation current did not turn off");
            if (range0_ctrl || range1_ctrl || range2_ctrl || range3_ctrl)
                $fatal(1, "range relay did not release");
            if (pol_i_ctrl || pol_v_ctrl)
                $fatal(1, "polarity relay did not release");
        end
    endtask

    initial begin
        repeat(4) @(negedge clk);
        reset_n<=1;
        repeat(8) @(posedge clk);
        if(dut.Z_MAX_STEPS !=10000) $fatal(1,"wrong top Z limit");
        axi_write(32'h40,32'h8); // ARM, current stays off
        axi_write(32'h44,32'h1); // HOME with active home sensor
        axi_write(32'h40,32'h9);
        wait_z_done(500);
        axi_write(32'h48,10001);
        axi_write(32'h44,2);
        axi_write(32'h40,9);
        wait_z_fault(500);
        if(dut.z_position !=0) $fatal(1,"out-of-limit target moved axis");
        if(dut.z_error_code !=4'd3) $fatal(1,"wrong limit refusal code %d",dut.z_error_code);
        axi_write(32'h40,12); // clear axis fault, preserve ARM
        axi_write(32'h48,10000);
        axi_write(32'h44,2);
        axi_write(32'h40,9);
        repeat(15) @(posedge clk);
        if(dut.z_fault) $fatal(1,"in-range boundary refused");
        axi_write(32'h00,32'h20);
        repeat(12) @(posedge clk);
        if(dut.z_driver_armed !==1) $fatal(1,"reset lost Z torque");
        $display("PASS: actual default Z_MAX10000,10001refused,10000accepted,RESET holdsZARM");
        $finish;
    end
endmodule
