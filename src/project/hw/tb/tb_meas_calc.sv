// Self-checking testbench for hw/rtl/measurement/meas_calc.v (module level).
//
// Adapted from vendor-generated vectors: corrected CLEAR sequencing and valid-first
// expectations; do not clear away a paired result before checking it. Every expected
// value comes from the bit-accurate model in sw/four_probe_sw/pl_resistivity.py, which
// tests/test_pl_resistivity.py compares against multi_material_model on the same
// snapshot (max relative error 7.44e-06 over the swept domain).
//
// Covers: single-shot arithmetic, both fail-closed gates that need no window, the
// signed pair mode (same sign / opposite sign must CANCEL / pair without a first
// half), and CLEAR.

`timescale 1ns/1ps

module tb_meas_calc;
    localparam integer MEAN_FRAC  = 16;
    localparam integer COEFF_FRAC = 23;
    localparam integer OUT_FRAC   = 32;
    localparam [31:0]  COUNT_MAX  = 32'd65536;
    localparam [31:0]  COEFF_MAX  = 32'd268_435_455;
    localparam [31:0]  K_Q        = 32'd179885;
    localparam [31:0]  K_RS_Q     = 32'd2788922;
    localparam [16:0]  CENTER     = 17'h0BE80;

    reg         clk = 1'b0;
    reg         reset_n = 1'b0;
    reg         start_pulse = 1'b0;
    reg         clear_pulse = 1'b0;
    reg         pair_enable = 1'b0;
    reg  [63:0] sum_snapshot = 64'd0;
    reg  [31:0] valid_count = 32'd0;
    reg         snapshot_overflow = 1'b0;
    reg  [16:0] center_code = CENTER;
    reg  [31:0] coeff_k_q = K_Q;
    reg  [31:0] coeff_rs_q = K_RS_Q;
    reg  [31:0] min_valid_count = 32'd0;
    reg  [16:0] max_span = 17'd0;
    reg  [16:0] min_code = 17'd0;
    reg  [16:0] max_code = 17'd0;
    wire        busy, done, result_valid, pair_valid, flag_zero_count;
    wire        flag_count_over_max, flag_sum_overflow, flag_coeff_invalid;
    wire        flag_negative, flag_pair_missing;
    wire        quality_ok, flag_quality_low_count, flag_quality_wide_span;
    wire [63:0] rho_q;
    wire [63:0] rs_q;

    always #10 clk = ~clk;     // 50 MHz

    meas_calc #(
        .MEAN_FRAC (MEAN_FRAC), .COEFF_FRAC (COEFF_FRAC), .OUT_FRAC (OUT_FRAC),
        .COUNT_MAX (COUNT_MAX),  .COEFF_MAX  (COEFF_MAX)
    ) dut (
        .clk(clk), .reset_n(reset_n), .start_pulse(start_pulse),
        .clear_pulse(clear_pulse), .pair_enable(pair_enable),
        .sum_snapshot(sum_snapshot), .valid_count(valid_count),
        .snapshot_overflow(snapshot_overflow), .center_code(center_code),
        .coeff_k_q(coeff_k_q), .coeff_rs_q(coeff_rs_q),
        .min_valid_count(min_valid_count), .max_span(max_span),
        .min_code(min_code), .max_code(max_code),
        .busy(busy), .done(done),
        .result_valid(result_valid), .rho_q(rho_q),
        .flag_zero_count(flag_zero_count), .flag_count_over_max(flag_count_over_max),
        .flag_sum_overflow(flag_sum_overflow), .flag_coeff_invalid(flag_coeff_invalid),
        .flag_negative(flag_negative), .pair_valid(pair_valid),
        .flag_pair_missing(flag_pair_missing), .rs_q(rs_q),
        .quality_ok(quality_ok), .flag_quality_low_count(flag_quality_low_count),
        .flag_quality_wide_span(flag_quality_wide_span)
    );

    integer errors = 0;
    integer checks = 0;

    wire [4:0] flags_bus = {flag_negative, flag_coeff_invalid, flag_sum_overflow,
                            flag_count_over_max, flag_zero_count};

    task automatic run_case(input [63:0] sum_i, input [31:0] count_i, input overflow_i,
                            input [31:0] kq_i, input pair_i, input [63:0] exp_rho,
                            input exp_valid, input exp_pair, input [4:0] exp_flags,
                            input [191:0] label);
        integer waited;
        begin
            sum_snapshot = sum_i; valid_count = count_i;
            snapshot_overflow = overflow_i; coeff_k_q = kq_i; coeff_rs_q = K_RS_Q;
            pair_enable = pair_i;
            @(negedge clk); start_pulse = 1'b1;
            @(negedge clk); start_pulse = 1'b0;
            waited = 0;
            while (!done && waited < 500) begin @(posedge clk); #1; waited = waited + 1; end
            checks = checks + 1;
            if (waited >= 500) begin
                errors = errors + 1; $display("FAIL %0s: DONE never asserted", label);
            end else begin
                if (result_valid !== exp_valid) begin
                    errors = errors + 1;
                    $display("FAIL %0s: result_valid=%b expected %b", label, result_valid, exp_valid);
                end
                if (pair_valid !== exp_pair) begin
                    errors = errors + 1;
                    $display("FAIL %0s: pair_valid=%b expected %b", label, pair_valid, exp_pair);
                end
                if (exp_valid && rho_q !== exp_rho) begin
                    errors = errors + 1;
                    $display("FAIL %0s: rho_q=%0d expected %0d", label, rho_q, exp_rho);
                end
                if (flags_bus !== exp_flags) begin
                    errors = errors + 1;
                    $display("FAIL %0s: flags=%b expected %b", label, flags_bus, exp_flags);
                end
                if (!exp_valid && rho_q !== 64'd0) begin
                    errors = errors + 1;
                    $display("FAIL %0s: invalid result must report rho_q=0, got %0d", label, rho_q);
                end
            end
        end
    endtask

    task automatic clear_result;
        begin
            @(negedge clk); clear_pulse = 1'b1;
            @(negedge clk); clear_pulse = 1'b0;
            #1;
            if (done || result_valid || pair_valid) begin
                errors = errors + 1; $display("FAIL: CLEAR did not drop done/valid");
            end
        end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        reset_n = 1'b1;
        repeat (2) @(negedge clk);
        checks = checks + 1;
        if (rho_q !== 64'd0 || rs_q !== 64'd0 || result_valid !== 1'b0) begin
            errors = errors + 1; $display("FAIL: reset must initialize both results invalid/zero");
        end

        run_case(64'd589260000, 32'd12000, 1'b0, 32'd179885, 1'b0,
                 64'd31038077440, 1'b1, 1'b0, 5'b00000, "ok_offset_337");
        run_case(64'd585228000, 32'd12000, 1'b0, 32'd179885, 1'b0,
                 64'd92101120, 1'b1, 1'b0, 5'b00000, "ok_offset_1");
        run_case(64'd24342000, 32'd500, 1'b0, 32'd179885, 1'b0,
                 64'd7736494080, 1'b1, 1'b0, 5'b10000, "ok_negative_offset");
        run_case(64'd7490961408, 32'd65536, 1'b0, 32'd179885, 1'b0,
                 64'd6035846899200, 1'b1, 1'b0, 5'b00000, "ok_max_delta");
        run_case(64'd48769, 32'd1, 1'b0, 32'd179885, 1'b0,
                 64'd92101120, 1'b1, 1'b0, 5'b00000, "ok_single_sample");
        run_case(64'd114303, 32'd1, 1'b0, 32'd179885, 1'b0,
                 64'd6035846899200, 1'b1, 1'b0, 5'b00000, "ok_count_1_offset_max");

        // --- Rs: the SAME q with the second coefficient; must equal rho/W_cm ---
        run_case(64'd589260000, 32'd12000, 1'b0, 32'd179885, 1'b0,
                 64'd31038077440, 1'b1, 1'b0, 5'b00000, "rs_probe");
        checks = checks + 1;
        if (rs_q !== 64'd481211757568) begin
            errors = errors + 1;
            $display("FAIL: rs_q=%0d expected %0d (K_rs must be K_rho without W_cm)", rs_q, 64'd481211757568);
        end

        // --- phase C: quality is REPORTED, never used to veto the result ---
        min_code = 17'd48700; max_code = 17'd49000;
        min_valid_count = 32'd20000; max_span = 17'd400;
        run_case(64'd589260000, 32'd12000, 1'b0, 32'd179885, 1'b0,
                 64'd31038077440, 1'b1, 1'b0, 5'b00000, "quality_low_count");
        checks = checks + 1;
        if (!flag_quality_low_count || flag_quality_wide_span || quality_ok) begin
            errors = errors + 1;
            $display("FAIL: quality flags wrong (low=%b wide=%b ok=%b)", flag_quality_low_count, flag_quality_wide_span, quality_ok);
        end
        max_span = 17'd100;   // span 300 > 100 now
        run_case(64'd589260000, 32'd12000, 1'b0, 32'd179885, 1'b0,
                 64'd31038077440, 1'b1, 1'b0, 5'b00000, "quality_wide_span");
        checks = checks + 1;
        if (!flag_quality_wide_span || quality_ok) begin
            errors = errors + 1;
            $display("FAIL: wide-span flag not set (wide=%b ok=%b)", flag_quality_wide_span, quality_ok);
        end
        min_valid_count = 32'd0; max_span = 17'd0;   // limits off again

        // --- pair mode: the first half then the averaged second half ---
        // START without PAIR stores the first result; do not CLEAR between halves.
        run_case(64'd589260000, 32'd12000, 1'b0, 32'd179885, 1'b0, 64'd31038077440, 1'b1, 1'b0, 5'b00000, "pair_same_sign_first");
        run_case(64'd589260000, 32'd12000, 1'b0, 32'd179885, 1'b1,
                 64'd31038077440, 1'b1, 1'b1, 5'b00000, "pair_same_sign");
        run_case(64'd586224000, 32'd12000, 1'b0, 32'd179885, 1'b0, 64'd7736494080, 1'b1, 1'b0, 5'b00000, "pair_opposite_sign_cancels_first");
        run_case(64'd584208000, 32'd12000, 1'b0, 32'd179885, 1'b1,
                 64'd0, 1'b1, 1'b1, 5'b00000, "pair_opposite_sign_cancels");
        run_case(64'd48868000, 32'd1000, 1'b0, 32'd179885, 1'b0, 64'd9210112000, 1'b1, 1'b0, 5'b00000, "pair_second_half_differs_first");
        run_case(64'd196072000, 32'd4000, 1'b0, 32'd179885, 1'b1,
                 64'd16117696000, 1'b1, 1'b1, 5'b00000, "pair_second_half_differs");

        clear_result();  // discard the successful preceding pair explicitly
        // pair asked without a first half: refused, not averaged
        run_case(64'd589260000, 32'd12000, 1'b0, 32'd179885, 1'b1, 64'd0, 1'b0, 1'b0, 5'b00000, "pair_missing");
        // and the missing-first-half flag must be visible
        if (flag_pair_missing !== 1'b1) begin
            errors = errors + 1; $display("FAIL: PAIR without a first half did not set flag_pair_missing");
        end
        checks = checks + 1;

        // A rejected pair must not become the first half of another pair.
        run_case(64'd589260000, 32'd12000, 1'b0, 32'd179885, 1'b1,
                 64'd0, 1'b0, 1'b0, 5'b00000, "pair_missing_repeated");
        if (flag_pair_missing !== 1'b1) begin
            errors = errors + 1; $display("FAIL: rejected pair seeded a later pair");
        end

        // --- fail-closed cases that need no window ---
        run_case(64'd0, 32'd0, 1'b0, 32'd179885, 1'b0, 64'd0, 1'b0, 1'b0, 5'b00001, "zero_count");
        run_case(64'd3196108416, 32'd65537, 1'b0, 32'd179885, 1'b0, 64'd0, 1'b0, 1'b0, 5'b00010, "count_over_max");
        run_case(64'd585216000, 32'd12000, 1'b1, 32'd179885, 1'b0, 64'd0, 1'b0, 1'b0, 5'b00100, "sum_overflow");
        run_case(64'd585216000, 32'd12000, 1'b0, 32'd0, 1'b0, 64'd0, 1'b0, 1'b0, 5'b01000, "coeff_zero");
        run_case(64'd585216000, 32'd12000, 1'b0, 32'd268435456, 1'b0, 64'd0, 1'b0, 1'b0, 5'b01000, "coeff_over_max");

        clear_result();
        $display("tb_meas_calc: checks=%0d errors=%0d", checks, errors);
        if (errors == 0) $display("PASS: tb_meas_calc checks=%0d", checks);
        else $fatal(1, "FAIL: tb_meas_calc errors=%0d", errors);
        $finish;
    end

endmodule
