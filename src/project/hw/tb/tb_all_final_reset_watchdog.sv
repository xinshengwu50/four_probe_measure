`timescale 1ns/1ps

// Focused regression for CONTROL.SYSTEM_RESET / CLEAR_FAULTS and the PS
// heartbeat watchdog.  The watchdog counter is loaded near its threshold so
// the test remains short while exercising the real expiry comparator.
module tb_all_final_reset_watchdog;
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
        .Z_MAX_STEPS(40),
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
        repeat (4) @(negedge clk);
        reset_n <= 1'b1;
        repeat (4) @(posedge clk);

        if (dut.reset_latched !== 1'b0 || dut.watchdog_tripped !== 1'b0)
            $fatal(1, "fault latches were not clear after reset");
        if (dut.watchdog_armed !== 1'b0)
            $fatal(1, "watchdog armed before the first heartbeat");
        if (dut.WATCHDOG_CYCLES !== 32'd50_000_000)
            $fatal(1, "watchdog timeout is not 50,000,000 cycles");

        // SYSTEM_RESET must cut current/relays, set bit16, and not step an axis.
        axi_write(32'hD0, 32'h0000_0005);   // START | CURRENT_REQ, range 0
        wait_current_on(100);
        steps_before = step_count;
        axi_write(32'h00, 32'h0000_0020);   // CONTROL.SYSTEM_RESET
        repeat (4) @(posedge clk);
        axi_read(32'h04, status);
        if (status[16] !== 1'b1 || status[17] !== 1'b0)
            $fatal(1, "SYSTEM_RESET status mismatch: 0x%08x", status);
        check_current_off();
        if (step_count != steps_before)
            $fatal(1, "SYSTEM_RESET moved an axis");

        axi_write(32'h00, 32'h0000_0040);   // CONTROL.CLEAR_FAULTS
        repeat (2) @(posedge clk);
        axi_read(32'h04, status);
        if ((status & 32'h0003_0000) !== 32'd0)
            $fatal(1, "CLEAR_FAULTS did not clear latches: 0x%08x", status);

        // A heartbeat arms the watchdog; refreshing it reloads the counter.
        axi_write(32'hFC, 32'd1);
        repeat (2) @(posedge clk);
        if (dut.watchdog_armed !== 1'b1 || dut.watchdog_tripped !== 1'b0)
            $fatal(1, "heartbeat did not arm the watchdog");
        @(negedge clk);
        dut.watchdog_cnt = 32'd123;
        axi_write(32'hFC, 32'd1);
        repeat (2) @(posedge clk);
        if (dut.watchdog_cnt > 32'd1)
            $fatal(1, "heartbeat did not reload watchdog counter: %0d", dut.watchdog_cnt);

        // Turn current on again, then load the real threshold into the counter.
        axi_write(32'hD0, 32'h0000_0005);
        wait_current_on(100);
        steps_before = step_count;
        @(negedge clk);
        dut.watchdog_cnt = 32'd50_000_000;
        repeat (4) @(posedge clk);
        axi_read(32'h04, status);
        if (status[17] !== 1'b1 || status[16] !== 1'b0)
            $fatal(1, "watchdog status mismatch: 0x%08x", status);
        if (dut.watchdog_armed !== 1'b0)
            $fatal(1, "watchdog remained armed after expiry");
        check_current_off();
        if (step_count != steps_before)
            $fatal(1, "watchdog expiry moved an axis");

        axi_write(32'h00, 32'h0000_0040);
        repeat (2) @(posedge clk);
        axi_read(32'h04, status);
        if ((status & 32'h0003_0000) !== 32'd0)
            $fatal(1, "CLEAR_FAULTS did not clear watchdog latch: 0x%08x", status);

        // ------------------------------------------------------------------
        // Watchdog observability and WATCHDOG_DISARM (2026-10-11)
        // ------------------------------------------------------------------
        axi_write(32'hFC, 32'd1);                 // arm the watchdog
        repeat (4) @(posedge clk);
        axi_read(32'h04, status);
        if (status[18] !== 1'b1)
            $fatal(1, "STATUS bit18 (watchdog_armed) not set: 0x%08x", status);
        axi_read(32'h140, rv_a);
        repeat (20) @(posedge clk);
        axi_read(32'h140, rv_b);
        if (rv_b <= rv_a)
            $fatal(1, "WATCHDOG_COUNT did not advance: %0d -> %0d", rv_a, rv_b);
        if (rv_b > 32'd50_000_000)
            $fatal(1, "WATCHDOG_COUNT out of range: %0d", rv_b);

        // WATCHDOG_DISARM must disarm without touching the fault latches.
        axi_write(32'h00, 32'h0000_0020);         // SYSTEM_RESET -> latch
        repeat (4) @(posedge clk);
        axi_write(32'h00, 32'h0000_0080);         // WATCHDOG_DISARM (CONTROL bit7)
        repeat (4) @(posedge clk);
        if (dut.watchdog_armed !== 1'b0)
            $fatal(1, "WATCHDOG_DISARM left the watchdog armed");
        if (dut.watchdog_cnt !== 32'd0)
            $fatal(1, "WATCHDOG_DISARM did not clear the counter");
        axi_read(32'h04, status);
        if (status[16] !== 1'b1)
            $fatal(1, "WATCHDOG_DISARM cleared reset_latched: 0x%08x", status);
        if (status[18] !== 1'b0)
            $fatal(1, "STATUS bit18 still reports armed: 0x%08x", status);
        axi_write(32'h00, 32'h0000_0040);         // CLEAR_FAULTS
        repeat (4) @(posedge clk);
        axi_read(32'h04, status);
        if ((status & 32'h0003_0000) !== 32'd0)
            $fatal(1, "CLEAR_FAULTS after disarm failed: 0x%08x", status);

        // ------------------------------------------------------------------
        // SYSTEM_RESET stops an in-flight move; HOME still retracts
        // ------------------------------------------------------------------
        arm_z_home();
        wait_z_done(400);
        axi_write(32'h48, 32'd30);
        axi_write(32'h44, 32'h0000_0002);         // MOVE_TO
        axi_write(32'h40, 32'h0000_0009);         // START | ARM
        for (i = 0; i < 200; i = i + 1) begin
            if (dut.z_position != 32'd0) break;
            @(posedge clk);
        end
        if (dut.z_position == 32'd0)
            $fatal(1, "Z move never started");
        if (dut.z_position >= 32'd30)
            $fatal(1, "Z move completed before the reset could be tested");
        pos_a = dut.z_position;
        axi_write(32'h00, 32'h0000_0020);         // SYSTEM_RESET mid-move
        repeat (40) @(posedge clk);
        pos_b = dut.z_position;
        // The latch is registered, so at most one further STEP can be issued
        // while the stop propagates through the axis state machine.
        if (pos_b > pos_a + 32'd1)
            $fatal(1, "SYSTEM_RESET did not stop the moving axis: %0d -> %0d",
                   pos_a, pos_b);
        if (dut.z_direct_busy)
            $fatal(1, "Z stayed busy after SYSTEM_RESET");
        // The real property: no further motion at all after the stop settles.
        repeat (300) @(posedge clk);
        if (dut.z_position !== pos_b)
            $fatal(1, "axis kept stepping after SYSTEM_RESET: %0d -> %0d",
                   pos_b, dut.z_position);

        // HOME must be refused while reset is latched.
        arm_z_home();
        wait_z_fault(60);
        if (dut.z_error_code !== 4'd9) $fatal(1,"HOME must remain locked");

        // With the latch still set, MOVE_TO must be refused with code 9.
        axi_write(32'h48, 32'd10);
        axi_write(32'h44, 32'h0000_0002);
        axi_write(32'h40, 32'h0000_0009);
        wait_z_fault(60);
        if (dut.z_error_code !== 4'd9)
            $fatal(1, "locked MOVE_TO error code=%0d", dut.z_error_code);

        // Clearing the latch restores MOVE_TO.
        axi_write(32'h00, 32'h0000_0040);         // CLEAR_FAULTS
        axi_write(32'h40, 32'h0000_000C);         // ARM | CLEAR Z fault
        repeat (4) @(posedge clk);
        axi_write(32'h48, 32'd10);
        axi_write(32'h44, 32'h0000_0002);
        axi_write(32'h40, 32'h0000_0009);
        wait_z_done(400);
        axi_read(32'h50, rv_a);
        if (rv_a !== 32'd10)
            $fatal(1, "MOVE_TO after clearing the latch moved to %0d", rv_a);

        // ------------------------------------------------------------------
        // A watchdog trip locks every motion command until it is cleared
        // ------------------------------------------------------------------
        axi_write(32'hFC, 32'd1);
        @(negedge clk);
        dut.watchdog_cnt = 32'd50_000_000;
        repeat (8) @(posedge clk);
        axi_read(32'h04, status);
        if (status[17] !== 1'b1)
            $fatal(1, "watchdog did not trip: 0x%08x", status);
        axi_write(32'h44, 32'h0000_0001);         // HOME
        axi_write(32'h40, 32'h0000_0009);
        wait_z_fault(60);
        if (dut.z_error_code !== 4'd9)
            $fatal(1, "watchdog motion lock error code=%0d", dut.z_error_code);
        if (dut.z_position != 32'd10 && dut.z_position != 32'd0)
            $fatal(1, "watchdog trip moved the axis: %0d", dut.z_position);
        axi_write(32'h00, 32'h0000_0040);         // CLEAR_FAULTS
        axi_write(32'h40, 32'h0000_000C);         // ARM | CLEAR Z fault

        $display("PASS: reset/watchdog latch, clear, heartbeat, disarm, motion inhibit, current-off");
        $finish;
    end
endmodule
