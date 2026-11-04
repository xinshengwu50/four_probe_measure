// Top-level integration testbench for the PL measurement arithmetic (CALC_* registers).
//
// WHY THIS EXISTS, AND WHY IT IS NOT PART OF tb_all_final_equiv
//   The equivalence testbench compares every DUT output -- S_AXI_RDATA included --
//   against a frozen reference every clock, and that reference has no CALC_*
//   registers.  Driving a CALC read there would therefore FAIL BY CONSTRUCTION.
//   So the CALC path needs its own stimulus, and this is it: the AXI decode, the
//   register file, the address map and the fail-closed gate path, driven end to
//   end through the real ALL_Final instance.
//
//   It deliberately does not emulate the ADS8681: the gates that matter here
//   (zero count, over-range coefficient) are reachable with an empty window, which
//   keeps the testbench fast and free of the SPI slave model.  The arithmetic
//   itself is covered by hw/tb/tb_meas_calc.sv against golden-model vectors.
//
//   Run:  powershell -File scripts/run_all_final_calc_xsim.ps1
`timescale 1ns/1ps

module tb_all_final_calc;
    localparam [11:0] REG_VERSION      = 12'h010;
    localparam [11:0] REG_STATS_STATUS = 12'h13C;
    localparam [11:0] REG_WATCHDOG     = 12'h140;
    localparam [11:0] REG_Z_SAFE       = 12'h148;
    localparam [11:0] REG_CALC_CONTROL = 12'h14C;
    localparam [11:0] REG_CALC_STATUS  = 12'h150;
    localparam [11:0] REG_CALC_RHO_LOW = 12'h154;
    localparam [11:0] REG_CALC_RHO_HIGH= 12'h158;
    localparam [11:0] REG_CALC_FLAGS   = 12'h15C;
    localparam [11:0] REG_CALC_COEFF_K = 12'h160;

    localparam [31:0] PL_VERSION  = 32'h414C_5835;
    localparam [31:0] COEFF_MAX   = 32'd268_435_455;
    localparam [31:0] CANARY_K_Q  = 32'd179_885;

    localparam [31:0] CALC_START = 32'h0000_0001;
    localparam [31:0] CALC_CLEAR = 32'h0000_0002;

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

    integer errors = 0;
    integer checks = 0;

    always #10 clk = ~clk;
    always @(posedge CS) begin
        RVS <= 1'b0;
        repeat (4) @(posedge clk);
        RVS <= 1'b1;
    end

    ALL_Final #(
        .STEPS_FORWARD(4), .PULSE_HALF(2), .SLOW_DIV(1), .PAUSE_CLKS(4),
        .BACK_MAX_STEP(4), .READY_WAIT_CNT(2), .SEN_DELAY_CNT(1), .BACK_FAIL_WAIT(8),
        .x_PUL_NUM(2), .x_HALF_PERIOD(1), .x_DEBOUNCE_CNT(1),
        .R_PULSE_HALF(2), .R_SLOW_DIV(1), .R_DIR_SETUP_CYCLES(2),
        .R_HOME_DEBOUNCE_CYCLES(1), .R_TIMEOUT_CYCLES(2000),
        .Z_DIR_SETUP_CYCLES(2), .Z_TIMEOUT_CYCLES(2000), .Z_MAX_STEPS(100),
        .WAIT_CYCLE(2), .TOTAL_CHAR(4)
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

    task automatic expect_eq(input [255:0] label, input [31:0] got, input [31:0] want);
        begin
            checks = checks + 1;
            if (got !== want) begin
                errors = errors + 1;
                $display("FAIL %0s: got 0x%08X want 0x%08X", label, got, want);
            end
        end
    endtask

    task automatic wait_calc_done(output [31:0] status, output [31:0] flags, output [63:0] rho);
        integer waited;
        logic [31:0] rd, hi;
        begin
            waited = 0;
            rd = 32'd0;
            while (!(rd & 32'h2) && waited < 400) begin
                axi_read(REG_CALC_STATUS, rd);
                waited = waited + 1;
            end
            checks = checks + 1;
            if (waited >= 400) begin
                errors = errors + 1;
                $display("FAIL: CALC_STATUS.DONE never asserted");
            end
            status = rd;
            axi_read(REG_CALC_FLAGS, flags);
            axi_read(REG_CALC_RHO_LOW, rd);
            axi_read(REG_CALC_RHO_HIGH, hi);
            rho = ({32'd0, hi} << 32) | {32'd0, rd};
        end
    endtask

    logic [31:0] rd, status, flags;
    logic [63:0] rho;

    initial begin
        repeat (6) @(negedge clk);
        reset_n = 1'b1;
        repeat (4) @(negedge clk);

        axi_read(REG_VERSION, rd);
        expect_eq("VERSION", rd, PL_VERSION);

        axi_write(REG_CALC_COEFF_K, CANARY_K_Q);
        axi_read(REG_CALC_COEFF_K, rd);
        expect_eq("CALC_COEFF_K readback", rd, CANARY_K_Q);
        axi_write(REG_CALC_COEFF_K, 32'h0000_0000);
        axi_read(REG_CALC_COEFF_K, rd);
        expect_eq("CALC_COEFF_K zero", rd, 32'd0);
        axi_write(REG_CALC_COEFF_K, 32'hFFFFFFFF);
        axi_read(REG_CALC_COEFF_K, rd);
        expect_eq("CALC_COEFF_K all ones", rd, 32'hFFFFFFFF);

        axi_write(REG_Z_SAFE, 32'h0000_1234);
        axi_write(REG_CALC_COEFF_K, CANARY_K_Q);
        axi_read(REG_Z_SAFE, rd);
        expect_eq("Z_SAFE_TRAVEL unaffected", rd, 32'h0000_1234);
        axi_read(REG_STATS_STATUS, rd);
        checks = checks + 1;
        axi_read(REG_WATCHDOG, rd);
        checks = checks + 1;
        axi_write(REG_Z_SAFE, 32'h0000_0000);

        axi_write(REG_CALC_COEFF_K, COEFF_MAX + 1);
        axi_write(REG_CALC_CONTROL, CALC_START);
        wait_calc_done(status, flags, rho);
        expect_eq("empty window VALID", status & 32'h4, 32'd0);
        expect_eq("empty window rho_low", rho[31:0], 32'd0);
        expect_eq("empty window rho_high", rho[63:32], 32'd0);
        checks = checks + 1;
        if (!(flags & 32'h1)) begin
            errors = errors + 1;
            $display("FAIL: zero_count flag not latched (flags=0x%08X)", flags);
        end
        checks = checks + 1;
        if (!(flags & 32'h8)) begin
            errors = errors + 1;
            $display("FAIL: coeff_invalid flag not latched (flags=0x%08X)", flags);
        end

        axi_write(REG_CALC_CONTROL, CALC_CLEAR);
        repeat (4) @(negedge clk);
        axi_read(REG_CALC_STATUS, rd);
        expect_eq("CLEAR: DONE", rd & 32'h2, 32'd0);
        expect_eq("CLEAR: VALID", rd & 32'h4, 32'd0);
        axi_read(REG_CALC_FLAGS, rd);
        expect_eq("CLEAR: flags", rd, 32'd0);

        axi_write(REG_CALC_COEFF_K, CANARY_K_Q);
        axi_write(REG_CALC_CONTROL, CALC_START);
        wait_calc_done(status, flags, rho);
        expect_eq("count gate VALID", status & 32'h4, 32'd0);
        checks = checks + 1;
        if (!(flags & 32'h1)) begin
            errors = errors + 1;
            $display("FAIL: count gate did not latch zero_count (flags=0x%08X)", flags);
        end

        $display("tb_all_final_calc: checks=%0d errors=%0d", checks, errors);
        if (errors == 0) $display("PASS: tb_all_final_calc checks=%0d", checks);
        else $fatal(1, "FAIL: tb_all_final_calc errors=%0d", errors);
        $finish;
    end
endmodule
