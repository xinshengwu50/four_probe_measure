`timescale 1ns/1ps

module tb_all_final_decel;
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
    initial begin
        repeat (4) @(negedge clk);
        reset_n <= 1'b1;

        wait_main_idle(100);

        axi_write(32'h7C, 32'd6000);
        axi_read(32'h7C, read_value);
        if (read_value !== 32'd6000)
            $fatal(1, "Z step interval register mismatch: got %0d", read_value);

        // R axis primitive tests.
        r_sensor = 1'b1;
        axi_write(32'h2C, 32'h0000_0001);
        axi_write(32'h28, 32'h0000_0001);
        repeat (5) @(posedge clk);
        r_sensor = 1'b0;
        wait_r_done(100);
        axi_read(32'h38, read_value);
        if (read_value !== 32'd0) $fatal(1, "R_HOME position mismatch: %0d", read_value);
        axi_write(32'h30, 32'd8);
        axi_write(32'h2C, 32'h0000_0002);
        axi_write(32'h28, 32'h0000_0001);
        wait_r_done(200);
        axi_read(32'h38, read_value);
        if (read_value !== 32'd8) $fatal(1, "R MOVE_TO 8 mismatch: %0d", read_value);
        if (dut.r_dir_out !== 1'b1) $fatal(1, "R extend direction mismatch");
        axi_write(32'h30, 32'd3);
        axi_write(32'h2C, 32'h0000_0002);
        axi_write(32'h28, 32'h0000_0001);
        wait_r_done(200);
        axi_read(32'h38, read_value);
        if (read_value !== 32'd3) $fatal(1, "R MOVE_TO 3 mismatch: %0d", read_value);
        if (dut.r_dir_out !== 1'b0) $fatal(1, "R retract direction mismatch");
        axi_write(32'h30, 32'hFFFF_FFFD);
        axi_write(32'h2C, 32'h0000_0003);
        axi_write(32'h28, 32'h0000_0001);
        wait_r_done(200);
        axi_read(32'h38, read_value);
        if (read_value !== 32'd0) $fatal(1, "R MOVE_REL mismatch: %0d", read_value);
        axi_write(32'h30, 32'd40001);
        axi_write(32'h2C, 32'h0000_0002);
        axi_write(32'h28, 32'h0000_0001);
        wait_r_fault(20);
        axi_read(32'h3C, read_value);
        if (read_value !== 32'd3) $fatal(1, "R range error mismatch: %0d", read_value);
        axi_write(32'h28, 32'h0000_0004);
        repeat (2) @(posedge clk);

        // Z axis primitive tests.
        sensor = 1'b0;
        axi_write(32'h44, 32'h0000_0001);
        axi_write(32'h40, 32'h0000_0001);
        wait_z_done(20);
        axi_read(32'h50, read_value);
        if (read_value !== 32'd0) $fatal(1, "Z_HOME position mismatch: %0d", read_value);
        axi_write(32'h48, 32'd8);
        axi_write(32'h44, 32'h0000_0002);
        axi_write(32'h40, 32'h0000_0001);
        wait_z_done(200);
        axi_read(32'h50, read_value);
        if (read_value !== 32'd8) $fatal(1, "Z MOVE_TO 8 mismatch: %0d", read_value);
        if (dut.z_dir_reg !== 1'b0) $fatal(1, "Z down direction mismatch");
        axi_write(32'h48, 32'd3);
        axi_write(32'h44, 32'h0000_0002);
        axi_write(32'h40, 32'h0000_0001);
        wait_z_done(200);
        axi_read(32'h50, read_value);
        if (read_value !== 32'd3) $fatal(1, "Z MOVE_TO 3 mismatch: %0d", read_value);
        if (dut.z_dir_reg !== 1'b1) $fatal(1, "Z up direction mismatch");
        axi_write(32'h48, 32'hFFFF_FFFD);
        axi_write(32'h44, 32'h0000_0004);
        axi_write(32'h40, 32'h0000_0001);
        wait_z_done(200);
        axi_read(32'h50, read_value);
        if (read_value !== 32'd0) $fatal(1, "Z MOVE_REL mismatch: %0d", read_value);
        axi_write(32'h48, 32'd8);
        axi_write(32'h44, 32'h0000_0003);
        axi_write(32'h40, 32'h0000_0001);
        wait_z_done(200);
        wait_meas_active(20);
        wait_meas_done(100);
        axi_read(32'h5C, read_value);
        if ((read_value & 32'h2) == 0) $fatal(1, "Measurement done flag not set: %h", read_value);

        // Complete five-point sequence with small simulation targets.
        axi_write(32'h64, 32'd20);
        axi_write(32'h58, 32'h0000_0004);
        r_sensor = 1'b1;
        axi_write(32'h2C, 32'h0000_0001);
        axi_write(32'h28, 32'h0000_0001);
        repeat (5) @(posedge clk);
        r_sensor = 1'b0;
        wait_r_done(200);
        sensor = 1'b1;
        axi_write(32'h44, 32'h0000_0001);
        axi_write(32'h40, 32'h0000_0001);
        repeat (5) @(posedge clk);
        sensor = 1'b0;
        wait_z_done(200);
        for (integer point = 0; point < 5; point = point + 1) begin
            if (point == 1) begin
                axi_write(32'h48, 32'd5);
                axi_write(32'h44, 32'h0000_0002);
                axi_write(32'h40, 32'h0000_0001);
                wait_z_done(200);
                axi_write(32'h30, 32'd4);
                axi_write(32'h2C, 32'h0000_0002);
                axi_write(32'h28, 32'h0000_0001);
                wait_r_done(200);
            end else if (point > 1) begin
                axi_write(32'h48, 32'd5);
                axi_write(32'h44, 32'h0000_0002);
                axi_write(32'h40, 32'h0000_0001);
                wait_z_done(200);
                axi_write(32'h00, 32'h0000_0008);
                wait_x_done(200);
            end
            axi_write(32'h48, 32'd8);
            axi_write(32'h44, 32'h0000_0003);
            axi_write(32'h40, 32'h0000_0001);
            wait_z_done(200);
            wait_meas_active(20);
            wait_meas_done(100);
        end
        sensor = 1'b1;
        axi_write(32'h44, 32'h0000_0001);
        axi_write(32'h40, 32'h0000_0001);
        repeat (5) @(posedge clk);
        sensor = 1'b0;
        wait_z_done(200);
        r_sensor = 1'b1;
        axi_write(32'h2C, 32'h0000_0001);
        axi_write(32'h28, 32'h0000_0001);
        repeat (5) @(posedge clk);
        r_sensor = 1'b0;
        wait_r_done(200);
        axi_read(32'h74, x_position_before);
        axi_write(32'h6C, 32'd5);
        axi_write(32'h78, 32'h0000_0001);
        wait_x_done(200);
        axi_read(32'h74, read_value);
        if (read_value !== (x_position_before + 32'd5))
            $fatal(1, "X position mismatch: got %0d", read_value);
        axi_read(32'h70, read_value);
        if ((read_value & 32'h3) !== 32'h2)
            $fatal(1, "X status mismatch: got %h", read_value);

        axi_read(32'h10, read_value);
        if (read_value !== 32'h414C_5831)
            $fatal(1, "VERSION mismatch: got %h", read_value);

        axi_write(32'h00, 32'h0000_0001);
        repeat (2) @(negedge clk);
        axi_write(32'h00, 32'h0000_0002);
        repeat (2) @(negedge clk);
        axi_write_aw_first(32'h00, 32'h0000_0001);
        repeat (2) @(negedge clk);
        axi_write_w_first(32'h00, 32'h0000_0002);
        repeat (3) @(negedge clk);
        if (start_commands != 2 || xtrig_commands != 2)
            $fatal(1, "AXI command pulse mismatch: start=%0d xtrig=%0d",
                   start_commands, xtrig_commands);

        axi_read(32'h04, read_value);
        if (read_value[4:0] !== dut.main_state)
            $fatal(1, "STATUS state mismatch: status=%h state=%0d", read_value, dut.main_state);

        // ADC valid-code 10 ms window accumulator test (window shortened to 4 cycles).
        axi_write(32'hB4, 32'd320);
        axi_write(32'hB8, 32'd32000);
        axi_write(32'hBC, 32'h0000_0001);
        axi_write(32'hBC, 32'h0000_0002);

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
        repeat (3) @(posedge clk);

        axi_read(32'hAC, read_value);
        if (read_value !== 32'd1) $fatal(1, "window seq mismatch: %0d", read_value);
        axi_read(32'hA8, read_value);
        if (read_value !== 32'd2) $fatal(1, "window count mismatch: %0d", read_value);
        axi_read(32'hA0, read_value);
        if (read_value !== 32'd900) $fatal(1, "window sum low mismatch: %0d", read_value);
        axi_read(32'hA4, read_value);
        if (read_value !== 32'd0) $fatal(1, "window sum high mismatch: %0d", read_value);
        axi_read(32'hB0, read_value);
        if ((read_value & 32'h1) !== 32'h1) $fatal(1, "window ready missing: %h", read_value);
        axi_write(32'hBC, 32'h0000_0004);
        repeat (2) @(posedge clk);
        // New bit3 must survive AXI write/read and enable ordinary MOVE/HOME.
        axi_write(32'h80, 32'h0F);
        axi_read(32'h80, read_value);
        if (read_value !== 32'h0F) $fatal(1, "all-moves decel bit3 not readable");
        force dut.z_after_setup_measure = 1'b0;
        force dut.z_after_setup_return_home = 1'b0;
        force dut.z_position = 32'd2;
        force dut.u_axis_z.z_target_active = 32'd0;
        force dut.u_axis_z.z_state = 3'd2; // Z_STATE_MOVE
        #1;
        if (!dut.z_decel_active) $fatal(1, "ordinary MOVE missing decel");
        force dut.z_home_position_valid = 1'b1;
        force dut.z_after_setup_home = 1'b1;
        force dut.u_axis_z.z_state = 3'd3; // Z_STATE_HOME
        #1;
        if (!dut.z_decel_active) $fatal(1, "HOME missing decel");
        axi_write(32'h80, 32'h07);
        #1;
        if (dut.z_decel_active) $fatal(1, "HOME decel must require bit3");
        release dut.z_home_position_valid;
        release dut.z_after_setup_home;
        release dut.u_axis_z.z_state;
        release dut.u_axis_z.z_target_active;
        release dut.z_position;
        release dut.z_after_setup_measure;
        release dut.z_after_setup_return_home;
        $display("PASS: decel bit3 ordinary MOVE/HOME gating");
        $display("PASS: ALL_Final AXI Z/R/measurement version=%h start=%0d xtrig=%0d status=%h",
                 32'h414C_5831, start_commands, xtrig_commands, read_value);
        $finish;
    end
endmodule
