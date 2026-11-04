`timescale 1ns/1ps

// Focused regression for the Z-axis hardware interlock.
//
// It proves four properties of the final system:
//   1. The legacy automatic sequencer never drives the physical Z pins, even
//      when the external start / x_trig inputs are pulsed.
//   2. A commanded Z move produces no STEP pulses and keeps the driver
//      disabled while Z_CONTROL.bit1 (ARM) is clear.
//   3. With ARM set, an absolute move reaches exactly its target and then
//      parks the driver disabled again.
//   4. A target above the RTL hard travel limit faults instead of moving.
module tb_all_final_z_safety;
    logic clk = 1'b0;
    logic reset_n = 1'b0;
    logic RVS = 1'b1;
    logic SDO0 = 1'b0;
    logic sensor = 1'b0;   // active-low home sensor: 0 = parked at HOME
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

    integer disarmed_steps = 0;
    integer armed_steps = 0;
    integer enabled_cycles_ungated = 0;
    integer i_cycle;
    logic [31:0] x_pos_before;
    logic [31:0] rv;

    always #10 clk = ~clk;

    // Count every rising STEP edge and flag any driver-enable low period that
    // is not covered by the ARM interlock.
    always @(posedge step_pulse) begin
        if (!dut.z_driver_armed) disarmed_steps = disarmed_steps + 1;
        else armed_steps = armed_steps + 1;
    end

    always @(posedge clk) begin
        if (!dut.z_driver_armed && (ena === 1'b0)) enabled_cycles_ungated = enabled_cycles_ungated + 1;
    end

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

    task automatic wait_z_done(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.z_fault)
                    $fatal(1, "unexpected Z fault code=%0d", dut.z_error_code);
                if (!dut.z_direct_busy && dut.z_done_reg) return;
                @(posedge clk);
            end
            $fatal(1, "timeout waiting for Z done state=%0d pos=%0d target=%0d",
                   dut.u_axis_z.z_state, dut.z_position, dut.u_axis_z.z_target_active);
        end
    endtask

    task automatic wait_z_fault(input integer limit_cycles);
        integer i;
        begin
            for (i = 0; i < limit_cycles; i = i + 1) begin
                if (dut.z_fault) return;
                @(posedge clk);
            end
            $fatal(1, "timeout waiting for Z fault");
        end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        reset_n <= 1'b1;
        repeat (4) @(posedge clk);

        // 1. The legacy sequencer is inert and the Z pins are parked.
        if (dut.main_state !== dut.S_IDLE)
            $fatal(1, "legacy sequencer left S_IDLE after reset: %0d", dut.main_state);
        if (ena !== 1'b1 || step_pulse !== 1'b0)
            $fatal(1, "Z pins not parked after reset: ena=%b step=%b", ena, step_pulse);

        start = 1'b1;
        repeat (4) @(posedge clk);
        start = 1'b0;
        x_trig_in = 1'b1;
        repeat (4) @(posedge clk);
        x_trig_in = 1'b0;
        repeat (8) @(posedge clk);
        if (dut.main_state !== dut.S_IDLE)
            $fatal(1, "legacy start/x_trig moved the sequencer: %0d", dut.main_state);
        if (dut.z_position !== 32'd0)
            $fatal(1, "legacy start/x_trig moved the Z axis: pos=%0d", dut.z_position);

        // 2. A command while disarmed must not step the motor.
        axi_write(32'h44, 32'h0000_0001);   // HOME command
        axi_write(32'h40, 32'h0000_0009);   // START | ARM
        wait_z_done(40);
        axi_read(32'h50, rv);
        if (rv !== 32'd0) $fatal(1, "Z_HOME position mismatch: %0d", rv);

        axi_write(32'h40, 32'h0000_0010);   // DISARM
        axi_write(32'h48, 32'd10);
        axi_write(32'h44, 32'h0000_0002);   // MOVE_TO
        axi_write(32'h40, 32'h0000_0001);   // START only, still disarmed
        repeat (40) @(posedge clk);
        if (dut.z_position !== 32'd0)
            $fatal(1, "disarmed move stepped the motor: pos=%0d", dut.z_position);
        if (!dut.z_direct_busy)
            $fatal(1, "disarmed move did not enter the busy state");
        axi_write(32'h40, 32'h0000_0016);   // DISARM | STOP | CLEAR
        repeat (4) @(posedge clk);
        if (dut.z_direct_busy) $fatal(1, "Z stop/clear did not return to idle");
        if (disarmed_steps !== 0)
            $fatal(1, "STEP pulses escaped while disarmed: %0d", disarmed_steps);

        // 3. An armed absolute move stops exactly on target.
        axi_write(32'h44, 32'h0000_0001);   // HOME
        axi_write(32'h40, 32'h0000_0009);   // START | ARM
        wait_z_done(40);
        axi_write(32'h48, 32'd12);
        axi_write(32'h44, 32'h0000_0002);   // MOVE_TO
        axi_write(32'h40, 32'h0000_0009);   // START | ARM
        wait_z_done(400);
        axi_read(32'h50, rv);
        if (rv !== 32'd12) $fatal(1, "armed move position mismatch: %0d", rv);
        if (armed_steps !== 12)
            $fatal(1, "armed move issued %0d STEP pulses, expected 12", armed_steps);
        // The driver now stays ENABLED (ena low) for the whole armed window so
        // the screw keeps holding torque; only a disarm may release it.
        if (ena !== 1'b0)
            $fatal(1, "Z driver dropped holding torque while still armed");

        // 4. A target above the hard travel limit must fault, not move.
        axi_write(32'h48, 32'd41);
        axi_write(32'h44, 32'h0000_0002);
        axi_write(32'h40, 32'h0000_0009);
        wait_z_fault(40);
        axi_read(32'h54, rv);
        if (rv !== 32'd3) $fatal(1, "hard-limit error code mismatch: %0d", rv);
        axi_read(32'h50, rv);
        if (rv !== 32'd12) $fatal(1, "hard-limit target moved the axis: %0d", rv);

        // `ena` is a registered output, so a DISARM issued while a move is
        // still running leaves the enable low for 1-2 clocks. Anything more
        // than that would mean the enable is not gated by ARM at all.
        if (enabled_cycles_ungated > 2)
            $fatal(1, "Z driver enable was low while disarmed for %0d cycles", enabled_cycles_ungated);

        // 5. A Z command issued while X is moving must be dropped, not executed.
        //    (Batch 3 briefly lost this interlock when the motion-lock checks
        //    were inserted; this assertion keeps it from disappearing again.)
        axi_write(32'h40, 32'h0000_000C);   // ARM | CLEAR (drop the hard-limit fault)
        axi_write(32'h44, 32'h0000_0001);   // HOME
        axi_write(32'h40, 32'h0000_0009);   // START | ARM
        wait_z_done(40);
        axi_write(32'h6C, 32'd40);          // X target: 40 pulses
        axi_write(32'h78, 32'h0000_0001);   // X start (direct, main_state is idle)
        repeat (6) @(posedge clk);
        if (!dut.x_busy) $fatal(1, "X move did not start");
        axi_write(32'h48, 32'd12);
        axi_write(32'h44, 32'h0000_0002);   // Z MOVE_TO while X is busy
        axi_write(32'h40, 32'h0000_0009);
        repeat (30) @(posedge clk);
        if (dut.z_position !== 32'd0)
            $fatal(1, "Z moved while X was busy: pos=%0d", dut.z_position);
        if (dut.z_direct_busy)
            $fatal(1, "Z entered a busy state while X was busy");
        if (dut.z_error_code !== 4'd8)
            $fatal(1, "Z conflict error code=%0d", dut.z_error_code);
        for (i_cycle = 0; i_cycle < 400; i_cycle = i_cycle + 1) begin
            if (!dut.x_busy) break;
            @(posedge clk);
        end
        if (dut.z_position !== 32'd0)
            $fatal(1, "Z moved after X finished: pos=%0d", dut.z_position);

        // 6. Interlock matrix: no axis may start while another one is moving.
        //    (2026-10-11: R only checked x_busy and X checked nothing at all,
        //    which is the mirror image of the Z conflict bug.)
        axi_write(32'h40, 32'h0000_000C);   // ARM | CLEAR
        // (a') 2026-10-11: give the height gate a generous threshold so the
        // conflict interlock below is exercised in isolation, and establish a
        // real Z home (lateral motion requires z_homed).
        axi_write(32'h148, 32'd40);
        axi_write(32'h44, 32'h0000_0001);   // Z HOME
        axi_write(32'h40, 32'h0000_0009);   // START | ARM
        wait_z_done(40);
        if (dut.z_homed !== 1'b1) $fatal(1, "Z home did not set z_homed");
        r_sensor = 1'b0;                    // pretend the R home sensor is active
        repeat (12) @(posedge clk);
        axi_write(32'h2C, 32'h0000_0001);   // R HOME
        axi_write(32'h28, 32'h0000_0001);   // R start
        for (i_cycle = 0; i_cycle < 200; i_cycle = i_cycle + 1) begin
            if (dut.r_homed) break;
            @(posedge clk);
        end
        if (!dut.r_homed) $fatal(1, "R did not home");
        r_sensor = 1'b1;

        // 6a. Z moving -> an R MOVE_TO must be refused with R_ERR_CONFLICT (8).
        axi_write(32'h48, 32'd30);
        axi_write(32'h44, 32'h0000_0002);   // Z MOVE_TO
        axi_write(32'h40, 32'h0000_0009);   // START | ARM
        for (i_cycle = 0; i_cycle < 200; i_cycle = i_cycle + 1) begin
            if (dut.z_position != 32'd0) break;
            @(posedge clk);
        end
        if (dut.z_position == 32'd0) $fatal(1, "Z move never started");
        axi_write(32'h30, 32'd10);
        axi_write(32'h2C, 32'h0000_0002);   // R MOVE_TO while Z moves
        axi_write(32'h28, 32'h0000_0001);
        repeat (40) @(posedge clk);
        if (dut.r_busy) $fatal(1, "R entered busy while Z was moving");
        axi_read(32'h38, rv);
        if (rv !== 32'd0) $fatal(1, "R moved while Z was moving: pos=%0d", rv);
        axi_read(32'h3C, rv);
        if (rv !== 32'd8) $fatal(1, "R conflict error code=%0d (expected 8)", rv);
        if (dut.r_fault) $fatal(1, "R conflict latched a fault");

        // 6b. Z still moving -> an X rotation must not step.
        axi_read(32'h74, rv);
        x_pos_before = rv;
        axi_write(32'h6C, 32'd40);          // X target
        axi_write(32'h78, 32'h0000_0001);   // X start
        repeat (40) @(posedge clk);
        if (dut.x_busy) $fatal(1, "X entered busy while Z was moving");
        axi_read(32'h74, rv);
        if (rv !== x_pos_before)
            $fatal(1, "X moved while Z was moving: %0d -> %0d", x_pos_before, rv);
        // let Z finish, then prove R can move once nothing else is busy
        for (i_cycle = 0; i_cycle < 600; i_cycle = i_cycle + 1) begin
            if (!dut.z_direct_busy) break;
            @(posedge clk);
        end
        axi_write(32'h30, 32'd10);
        axi_write(32'h2C, 32'h0000_0002);
        axi_write(32'h28, 32'h0000_0001);
        for (i_cycle = 0; i_cycle < 400; i_cycle = i_cycle + 1) begin
            if (!dut.r_busy) break;
            @(posedge clk);
        end
        axi_read(32'h38, rv);
        if (rv !== 32'd10)
            $fatal(1, "R did not move once Z was idle: pos=%0d", rv);

        // 6c. R moving -> an X rotation must not step.
        axi_write(32'h30, 32'd200);
        axi_write(32'h2C, 32'h0000_0002);   // R MOVE_TO (long)
        axi_write(32'h28, 32'h0000_0001);
        for (i_cycle = 0; i_cycle < 200; i_cycle = i_cycle + 1) begin
            if (dut.r_busy) break;
            @(posedge clk);
        end
        if (!dut.r_busy) $fatal(1, "long R move did not start");
        axi_read(32'h74, rv);
        x_pos_before = rv;
        axi_write(32'h6C, 32'd40);
        axi_write(32'h78, 32'h0000_0001);   // X start while R moves
        repeat (40) @(posedge clk);
        if (dut.x_busy) $fatal(1, "X entered busy while R was moving");
        axi_read(32'h74, rv);
        if (rv !== x_pos_before)
            $fatal(1, "X moved while R was moving: %0d -> %0d", x_pos_before, rv);
        axi_write(32'h28, 32'h0000_0002);   // R STOP

        // 7. (a') lateral height gate, sticky refusal status, retract exemption.
        axi_write(32'h148, 32'd0);           // require a fully retracted probe
        if (dut.z_position < 32'd10)
            $fatal(1, "7a needs the probe down, pos=%0d", dut.z_position);
        // 7a. Probe down -> R refused with R_ERR_NOT_CLEAR, X silently dropped.
        axi_write(32'h30, 32'd10);
        axi_write(32'h2C, 32'h0000_0002);    // R MOVE_TO with the probe down
        axi_write(32'h28, 32'h0000_0001);
        repeat (40) @(posedge clk);
        if (dut.r_busy) $fatal(1, "R started while the probe was down");
        axi_read(32'h3C, rv);
        if (rv !== 32'd10) $fatal(1, "R not-clear code=%0d (expected 10)", rv);
        if (dut.r_fault) $fatal(1, "R not-clear latched a fault");
        axi_read(32'h74, rv);
        x_pos_before = rv;
        axi_write(32'h6C, 32'd40);
        axi_write(32'h78, 32'h0000_0001);    // X start with the probe down
        repeat (40) @(posedge clk);
        if (dut.x_busy) $fatal(1, "X started while the probe was down");
        axi_read(32'h74, rv);
        if (rv !== x_pos_before)
            $fatal(1, "X moved while the probe was down: %0d -> %0d", x_pos_before, rv);
        axi_read(32'h04, rv);
        if (rv[19] !== 1'b1) $fatal(1, "STATUS[19] not set after a refusal: %h", rv);
        // 7b. The sticky bit survives CONTROL bit2 and is cleared by CLEAR_FAULTS.
        axi_write(32'h40, 32'h0000_0004);    // Z_CONTROL CLEAR must NOT clear it
        repeat (4) @(posedge clk);
        axi_read(32'h04, rv);
        if (rv[19] !== 1'b1) $fatal(1, "CONTROL bit2 cleared the sticky bit");
        axi_write(32'h00, 32'h0000_0040);    // CLEAR_FAULTS
        repeat (4) @(posedge clk);
        axi_read(32'h04, rv);
        if (rv[19] !== 1'b0) $fatal(1, "CLEAR_FAULTS kept the sticky bit: %h", rv);
        // 7c. (a) retract exemption: with a generous thr and X busy, a Z MOVE_TO
        //     is refused (8) but Z HOME is accepted and lifts the probe.
        axi_write(32'h148, 32'd40);
        axi_read(32'h74, rv);
        x_pos_before = rv;
        axi_write(32'h6C, 32'd60);           // long enough to stay busy
        axi_write(32'h78, 32'h0000_0001);
        for (i_cycle = 0; i_cycle < 200; i_cycle = i_cycle + 1) begin
            if (dut.x_busy) break;
            @(posedge clk);
        end
        if (!dut.x_busy) $fatal(1, "X did not start for the retract-exemption test");
        axi_write(32'h48, 32'd35);
        axi_write(32'h44, 32'h0000_0002);    // Z MOVE_TO while X is busy
        axi_write(32'h40, 32'h0000_0009);
        repeat (20) @(posedge clk);
        if (dut.z_direct_busy) $fatal(1, "Z moved while X was busy");
        axi_read(32'h54, rv);
        if (rv !== 32'd8) $fatal(1, "Z conflict code=%0d (expected 8)", rv);
        axi_read(32'h50, rv);
        if (rv !== 32'd30) $fatal(1, "the refused Z move changed the position: %0d", rv);
        axi_write(32'h40, 32'h0000_000C);    // ARM | CLEAR the Z error code
        axi_write(32'h44, 32'h0000_0001);    // Z HOME - the retract must be accepted
        axi_write(32'h40, 32'h0000_0009);
        for (i_cycle = 0; i_cycle < 400; i_cycle = i_cycle + 1) begin
            if (dut.z_homed && dut.z_position == 32'd0) break;
            @(posedge clk);
        end
        if (!(dut.z_homed && dut.z_position == 32'd0))
            $fatal(1, "Z HOME was blocked while X was busy: pos=%0d homed=%b",
                   dut.z_position, dut.z_homed);
        if (dut.z_fault) $fatal(1, "Z HOME latched a fault");
        for (i_cycle = 0; i_cycle < 2000; i_cycle = i_cycle + 1) begin
            if (!dut.x_busy) break;
            @(posedge clk);
        end
        // 7d. Fail-closed: after a stop clears z_homed, lateral motion stays
        //     refused even with a generous thr and the counter back near 0.
        axi_write(32'h148, 32'd40);
        axi_write(32'h48, 32'd30);
        axi_write(32'h44, 32'h0000_0002);    // Z MOVE_TO down again
        axi_write(32'h40, 32'h0000_0009);
        for (i_cycle = 0; i_cycle < 200; i_cycle = i_cycle + 1) begin
            if (dut.z_position != 32'd0) break;
            @(posedge clk);
        end
        if (dut.z_position == 32'd0) $fatal(1, "7d: the Z move never started");
        axi_write(32'h00, 32'h0000_0020);    // SYSTEM_RESET -> the stop clears z_homed
        repeat (40) @(posedge clk);
        if (dut.z_homed !== 1'b0) $fatal(1, "the stop did not clear z_homed");
        axi_write(32'h30, 32'd10);
        axi_write(32'h2C, 32'h0000_0002);    // R MOVE_TO after the stop
        axi_write(32'h28, 32'h0000_0001);
        repeat (40) @(posedge clk);
        if (dut.r_busy) $fatal(1, "R started while z_homed was clear");
        axi_read(32'h3C, rv);
        if (rv !== 32'd10) $fatal(1, "fail-closed R code=%0d (expected 10)", rv);
        axi_write(32'h00, 32'h0000_0040);    // CLEAR_FAULTS

        $display("PASS: motion interlock (conflict matrix, retract exemption, height gate, sticky bit, fail-closed)");
        $finish;
    end
endmodule
