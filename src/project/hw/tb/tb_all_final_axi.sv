`timescale 1ns/1ps

module tb_all_final_axi;
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

    integer start_commands = 0;
    integer xtrig_commands = 0;

    always #10 clk = ~clk;
    always @(posedge CS) begin
        RVS <= 1'b0;
        repeat (4) @(posedge clk);
        RVS <= 1'b1;
    end


    ALL_Final #(
        .STEPS_FORWARD(4),
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
        .Z_TIMEOUT_CYCLES(2000),
        .Z_MAX_STEPS(100),
        .WAIT_CYCLE(2),
        .STATS_WINDOW_CYCLES(4),
        .TOTAL_CHAR(4)
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

    always @(posedge clk) begin
        #1;
        if (dut.axi_start_pulse)
            start_commands = start_commands + 1;
        if (dut.axi_x_trig_pulse)
            xtrig_commands = xtrig_commands + 1;
    end

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

    task automatic axi_write_aw_first(input [31:0] addr, input [31:0] data);
        begin
            @(negedge clk);
            awaddr <= addr; awvalid <= 1'b1;
            while (!awready) @(negedge clk);
            @(negedge clk);
            awvalid <= 1'b0;
            wdata <= data; wstrb <= 4'hF; wvalid <= 1'b1;
            while (!wready) @(negedge clk);
            @(negedge clk);
            wvalid <= 1'b0; bready <= 1'b1;
            while (!bvalid) @(negedge clk);
            if (bresp !== 2'b00) $fatal(1, "AW-first write response error: %b", bresp);
            @(negedge clk);
            bready <= 1'b0;
        end
    endtask

    task automatic axi_write_w_first(input [31:0] addr, input [31:0] data);
        begin
            @(negedge clk);
            wdata <= data; wstrb <= 4'hF; wvalid <= 1'b1;
            while (!wready) @(negedge clk);
            @(negedge clk);
            wvalid <= 1'b0;
            awaddr <= addr; awvalid <= 1'b1;
            while (!awready) @(negedge clk);
            @(negedge clk);
            awvalid <= 1'b0; bready <= 1'b1;
            while (!bvalid) @(negedge clk);
            if (bresp !== 2'b00) $fatal(1, "W-first write response error: %b", bresp);
            @(negedge clk);
            bready <= 1'b0;
        end
    endtask

    task automatic wait_main_idle(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.main_state == 5'd0) return;
                @(posedge clk);
            end
            $fatal(1, "Timeout waiting for main_state IDLE");
        end
    endtask
    task automatic wait_r_done(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.r_fault) $fatal(1, "Unexpected R fault code=%0d", dut.r_error_code);
                if (!dut.r_busy && dut.r_done_reg) return;
                @(posedge clk);
            end
            $fatal(1, "Timeout waiting for R done");
        end
    endtask
    task automatic wait_r_fault(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.r_fault) return;
                @(posedge clk);
            end
            $fatal(1, "Timeout waiting for R fault");
        end
    endtask
    task automatic wait_z_done(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.z_fault) $fatal(1, "Unexpected Z fault code=%0d", dut.z_error_code);
                if (!dut.z_direct_busy && dut.z_done_reg) return;
                @(posedge clk);
            end
            $fatal(1, "Timeout waiting for Z done state=%0d pos=%0d target=%0d busy=%b done=%b",
                   dut.u_axis_z.z_state, dut.z_position, dut.u_axis_z.z_target_active,
                   dut.z_direct_busy, dut.z_done_reg);
        end
    endtask
    task automatic wait_z_fault(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.z_fault) return;
                @(posedge clk);
            end
            $fatal(1, "Timeout waiting for Z fault");
        end
    endtask
    task automatic wait_meas_done(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.meas_state == dut.MEAS_STATE_ERROR) $fatal(1, "Measurement error");
                if (dut.meas_state == dut.MEAS_STATE_DONE) return;
                @(posedge clk);
            end
            $fatal(1, "Timeout waiting for measurement done");
        end
    endtask
    task automatic wait_meas_active(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.meas_state == dut.MEAS_STATE_ERROR) $fatal(1, "Measurement error");
                if (dut.meas_state == dut.MEAS_STATE_ACTIVE) return;
                @(posedge clk);
            end
            $fatal(1, "Timeout waiting for measurement active");
        end
    endtask
    task automatic wait_x_done(input integer limit_cycles);
        integer i; logic saw_busy;
        begin
            saw_busy = 0;
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.x_busy) saw_busy = 1;
                if (saw_busy && !dut.x_busy) return;
                @(posedge clk);
            end
            $fatal(1, "Timeout waiting for X rotation");
        end
    endtask

    logic [31:0] read_value;
    logic [31:0] x_position_before;
    // Current-ABI bus test. Mechanical safety/trajectory are tested separately;
    // a bus fixture must not issue lateral moves before HOME/clear-height prerequisites.
    initial begin
        repeat (4) @(negedge clk);
        reset_n <= 1'b1;
        wait_main_idle(100);
        axi_read(32'h10,read_value);
        if(read_value!==32'h414C5835) $fatal(1,"VERSION mismatch %h",read_value);
        axi_write(32'h7C,32'd6000);
        axi_read(32'h7C,read_value);
        if(read_value!==6000) $fatal(1,"step period roundtrip %h",read_value);
        axi_write_aw_first(32'h6C,32'd5);
        axi_read(32'h6C,read_value);
        if(read_value!==5) $fatal(1,"AW-before-W lost data %h",read_value);
        axi_write_w_first(32'h6C,32'd7);
        axi_read(32'h6C,read_value);
        if(read_value!==7) $fatal(1,"W-before-AW lost data %h",read_value);
        axi_read(32'h04,read_value);
        if(read_value[4:0]!==dut.main_state) $fatal(1,"STATUS state mismatch");
        axi_read(32'hFFFC,read_value);
        if(read_value!==0) $fatal(1,"reserved register not zero %h",read_value);
        if(current_en!==0 || dut.z_driver_armed!==0) $fatal(1,"bus reads/config unexpectedly enabled current/motion");
        $display("PASS: current AXI ABI, register roundtrip, AW/W independence, safe defaults");
        $finish;
    end
endmodule
