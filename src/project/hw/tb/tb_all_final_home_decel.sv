`timescale 1ns/1ps

module tb_all_final_home_decel;
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
    integer previous_position;
    integer i;
    task automatic wait_home_busy;
        integer j;
        begin
            for (j=0;j<100;j=j+1) begin
                @(negedge clk);
                if (dut.u_axis_z.z_state==dut.Z_STATE_HOME) return;
            end
            $fatal(1,"HOME did not become busy");
        end
    endtask
    task automatic configure_decel;
        integer j;
        begin
            axi_write(32'h7C,32'd16);
            axi_write(32'h84,32'd4);
            axi_write(32'h88,32'd1);
            for(j=0;j<16;j=j+1) begin
                axi_write(32'h8C,j);
                axi_write(32'h90,16+j*3);
            end
            axi_write(32'h8C,32'd15);
            axi_write(32'h90,32'd64);
            axi_write(32'h80,32'h0F);
        end
    endtask
    task automatic start_home;
        begin
            axi_write(32'h44,32'd1);
            axi_write(32'h40,32'd1);
        end
    endtask
    task automatic establish_home_and_move(input integer position);
        begin
            force dut.sen_stable=1'b0;
            start_home();
            wait_z_done(100);
            force dut.sen_stable=1'b1;
            axi_write(32'h48,position);
            axi_write(32'h44,32'd2);
            axi_write(32'h40,32'd1);
            wait_z_done(1500);
            if(dut.z_position!=position) $fatal(1,"setup MOVE mismatch");
        end
    endtask
    initial begin
        repeat(4) @(negedge clk);
        reset_n=1'b1;
        wait_main_idle(100);
        configure_decel();
        axi_read(32'hF8,read_value);
        if(read_value!=1) $fatal(1,"HOME fix capability missing");

        // Unknown position: FIRST HOME pulse is low-speed, no false completion.
        force dut.sen_stable=1'b1;
        start_home();
        wait_home_busy();
        if(dut.z_home_position_valid) $fatal(1,"reset position must be untrusted");
        if(!dut.z_home_slow_search || dut.z_interval_cfg!=64)
            $fatal(1,"unknown HOME must select tail speed");
        repeat(100) @(negedge clk);
        if(dut.z_interval_active!=64 || dut.z_done_reg) $fatal(1,"unknown HOME first pulse speed/done");
        force dut.sen_stable=1'b0;
        wait_z_done(100);

        // Trusted HOME after MOVE: discard stale target, count down, enter ramp.
        establish_home_and_move(12);
        start_home();
        wait_home_busy();
        if(dut.u_axis_z.z_target_active!=0 || !dut.z_home_position_valid) $fatal(1,"HOME target/validity");
        previous_position=12;
        for(i=0;i<1500 && dut.z_position!=0;i=i+1) begin
            @(negedge clk);
            if(dut.z_position>previous_position) $fatal(1,"HOME counter increased/underflowed");
            previous_position=dut.z_position;
            if(dut.z_position<=4 && dut.z_position!=0 && !dut.z_decel_active)
                $fatal(1,"trusted HOME last steps missing decel");
            if(dut.z_fault) $fatal(1,"unexpected HOME fault");
        end
        if(dut.z_position!=0) $fatal(1,"HOME counter failed to reach zero");
        repeat(150) @(negedge clk);
        if(dut.z_position!=0 || dut.z_done_reg || dut.u_axis_z.z_state!=dut.Z_STATE_HOME)
            $fatal(1,"estimated zero must NOT finish without the sensor");
        if(!dut.z_home_slow_search || dut.z_interval_active!=64)
            $fatal(1,"zero estimate must keep tail speed");
        force dut.sen_stable=1'b0;
        wait_z_done(100);
        if(!dut.z_homed) $fatal(1,"sensor did not establish HOME");

        // STOP invalidates estimate. Retrying HOME must use slow search.
        establish_home_and_move(8);
        start_home();wait_home_busy();
        axi_write(32'h40,32'd2);
        repeat(5) @(negedge clk);
        if(dut.z_homed || dut.z_home_position_valid || dut.z_direct_busy)
            $fatal(1,"STOP must invalidate HOME estimate");
        start_home();wait_home_busy();
        if(!dut.z_home_slow_search) $fatal(1,"retry after STOP must be slow");
        // No sensor: original timeout must still latch a HOME fault.
        wait_z_fault(2500);
        if(dut.z_error_code!=dut.Z_ERR_HOME_TIMEOUT) $fatal(1,"HOME timeout code");
        axi_write(32'h40,32'd4);
        repeat(5) @(negedge clk);
        force dut.sen_stable=1'b0;
        start_home();wait_z_done(100);
        $display("PASS: HOME known/unknown/ramp/zero/sensor/STOP/timeout/capability");
        $finish;
    end
    initial begin
        #1000000;
        $fatal(1,"testbench global timeout");
    end
endmodule
