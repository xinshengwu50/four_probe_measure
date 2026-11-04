// PL-side four-probe resistivity arithmetic for one banked 20 ms statistics window.
//
// WHY THIS MODULE EXISTS
//   The deployed PS path turns a PL window into rho in Python:
//       raw_v      = ((mean_code - 0x8000) * LSB_V - 2.5) * probe_voltage_scale
//       filtered_v = raw_v - probe_voltage_offset_v   (== (mean_code - center_code) * LSB_V * scale)
//       R          = |filtered_v| / I
//       rho        = R * FD * FW * W_cm * Fsp
//   That is the product of *parameters* (LSB, scale, per-bank current, geometry)
//   with the single *measurement* (mean_code - center_code), so the whole model
//   collapses into one per-bank coefficient K:
//       rho = (mean_code - center_code) * K ,  K = LSB_V*scale*FD*FW*W_cm*Fsp / I
//   and K is exactly the kind of value that belongs in "PS configures, PL computes".
//
// WHAT IT DOES (one bank per trigger, on demand)
//   d     = SUM - center_code*COUNT            (signed; the sign is reported as a flag)
//   q     = (|d| << MEAN_FRAC) / COUNT         (restoring integer division)
//   rho_q = (q * K_q) >> (MEAN_FRAC + COEFF_FRAC - OUT_FRAC)
//   with K_q = round(K * 2^COEFF_FRAC)  ->  rho_q = rho * 2^OUT_FRAC.
//
// WHY COEFF_FRAC IS 23 AND NOT SMALLER (2026-10-15, found by
// tests/test_pl_resistivity.py, not by inspection)
//   K is small here: ADC_LSB_V*scale/I*geometry is 0.0214 ohm*cm per code for the
//   deployed 10 mA/scale-4.0 setup and ~0.002 in the highest current range.  A
//   coefficient quantized to COEFF_FRAC bits carries an ABSOLUTE resolution of
//   2^-COEFF_FRAC, so its RELATIVE error is 0.5*2^-COEFF_FRAC/K -- at K = 0.0214
//   and COEFF_FRAC = 17 that is 1.0e-4, i.e. the whole budget on its own, and the
//   same budget evaluated at the LARGEST K (19.2) hides it completely.  COEFF_FRAC
//   = 23 makes it 3.0e-5 at K = 0.002 and 6.0e-5 at the enforced floor K_q >= 2^13.
//
// WHY THE DIVISION KEEPS FRACTIONAL BITS (this is not cosmetic)
//   The measured quantity is the offset of the mean code from the *centre* code,
//   so the honest error metric divides by that offset, not by the absolute code.
//   Rounding the mean to an integer code would cost 1 LSB / offset: at the
//   deployed setting (52.6 mV probe, scale 4.0 -> 84 code offset) that is 1.2e-2,
//   i.e. 120x worse than the 1e-4 target.  Keeping MEAN_FRAC fractional bits
//   makes that truncation 2^-MEAN_FRAC/offset (1.5e-5 at a 1-code offset) instead.
//
// WIDTH BUDGET (COUNT_MAX is a shift budget, not just a sanity gate)
//   COUNT <= COUNT_MAX = 2^16, center_code is a 17-bit register, so
//   |d| <= 2^33  ->  numerator = |d| << 16 <= 2^49  (DIV_W = 50 bits)
//   q   <= 2^33 and K_q <= COEFF_MAX = 2^28-1, so q*K_q <= 2^62 (PROD_W = 64).
//   Widening COUNT_MAX or COEFF_MAX requires re-checking those bounds; that is why
//   they are named parameters and why over-count / over-coefficient are hard gates
//   rather than saturations.
//
// FAIL-CLOSED (AGENTS.md rule: "unknown" is unsafe)
//   Zero count, count over COUNT_MAX, a latched window overflow and a coefficient
//   outside (0, COEFF_MAX] all produce VALID=0 with rho_q = 0 **and** a latched
//   reason flag.  A previous result is dropped when a new compute starts, so a
//   stale rho can never be read as fresh: 0 ohm is never reported as a
//   measurement, the flag is the authority.
//
// PHASE C (2026-10-15): the window's own quality numbers are judged here too, with
// two PS-programmed limits and pure comparisons (no divider, no new state):
//     count_ok = valid_count >= min_valid_count        (0 = no floor configured)
//     span_ok  = (max_code - min_code) <= max_span     (0 = no ceiling configured)
// They are REPORTED (status/flag bits) but deliberately do NOT gate VALID: whether a
// wide span or a thin window should void the point is an operator policy that the PS
// already owns (pl_stats_min_valid_samples, strict captures), and PL pretending to
// know it would turn a diagnostic into a silent veto.  A gate that fails for another
// reason still reports VALID=0 as before.
//
// PHASE B (2026-10-15): the module also produces the sheet resistance Rs.  It needs
// no second divider, because W_cm is a parameter:
//     rho = offset*K_rho,  K_rho = LSB*scale*FD*FW*W_cm*Fsp/I
//     Rs  = rho/W_cm = offset*K_rs,  K_rs = LSB*scale*FD*FW*Fsp/I   (K_rho without W_cm)
// so the SAME q feeds a second coefficient multiply.  Both results are Q32, both are
// gated, and both go through the same signed pair averaging.
//
// PAIR MODE (2026-10-15, A2): with pair_enable=1 the module returns the average of
// the current result and the previous successful one, so the forward/reverse
// combination -- the last piece of measurement arithmetic that used to live in the
// PS -- also happens in PL.  It is exactly equivalent because the geometry factor G
// is common to both polarities:
//     rho_f = (|V_f|/I_f)*G,  rho_r = (|V_r|/I_r)*G,
// The pairing is done on the SIGNED values and the magnitude is taken afterwards,
// because that is what the deployed PS model does:
//     combined_v = 0.5*(+V_f - V_r) ... rho = |combined_v|/I_eq*G
// so PL must report |0.5*(+rho_f - rho_r)|, not 0.5*(|rho_f| + |rho_r|).  The two
// agree only while both polarities have the same sign; taking the magnitude first
// would silently diverge exactly when the measurement is suspect.
// Fail-closed: PAIR without a previous successful result reports VALID=0 plus
// flag_pair_missing instead of returning a lone half as if it were a pair, and ANY
// failed compute clears have_prev, so a pair can never join two different points.
//
// The parent supplies the snapshot of the bank selected by stats_bank_select, so
// this module has no array ports and no dependency on stats_window internals.  It
// also deliberately shares nothing with the legacy meas_chain rho pipeline, which
// is dead in the deployed configuration.
module meas_calc #(
    parameter integer MEAN_FRAC  = 16,            // fractional bits kept in the mean quotient
    parameter integer COEFF_FRAC = 23,            // K_q = round(K * 2^COEFF_FRAC)
    parameter integer OUT_FRAC   = 32,            // rho_q = rho * 2^OUT_FRAC
    parameter [31:0]  COUNT_MAX  = 32'd65536,     // fail-closed gate; also the width budget
    parameter [31:0]  COEFF_MAX  = 32'd268_435_455 // 2^28-1: bounds q*K_q to 62 bits
) (
    input  wire        clk,
    input  wire        reset_n,
    // AXI write pulses (one clock wide).
    input  wire        start_pulse,
    input  wire        clear_pulse,
    // Snapshot of the selected bank (from stats_window).
    input  wire [63:0] sum_snapshot,
    input  wire [31:0] valid_count,
    input  wire        snapshot_overflow,
    input  wire [16:0] center_code,
    // Configuration (AXI register).
    input  wire [31:0] coeff_k_q,
    input  wire [31:0] coeff_rs_q,      // K_rs = round(K_rs * 2^COEFF_FRAC)
    // Phase C quality limits and the window's own code extremes.
    input  wire [31:0] min_valid_count, // 0 = no floor
    input  wire [16:0] max_span,        // 0 = no ceiling
    input  wire [16:0] min_code,
    input  wire [16:0] max_code,
    input  wire        pair_enable,     // CALC_CONTROL.AVERAGE_PAIR (level, not a pulse)
    // Read back by the AXI register file.
    output reg         busy,
    output reg         done,
    output reg         result_valid,
    output reg  [63:0] rho_q,
    output reg         flag_zero_count,
    output reg         flag_count_over_max,
    output reg         flag_sum_overflow,
    output reg         flag_coeff_invalid,
    output reg         flag_negative,
    output reg         pair_valid,        // result is the averaged forward/reverse pair
    output reg         flag_pair_missing, // PAIR asked without a previous success
    output reg  [63:0] rs_q,              // sheet resistance, Q32 magnitude
    output reg         quality_ok,        // count and span within the programmed limits
    output reg         flag_quality_low_count,
    output reg         flag_quality_wide_span
);

  localparam integer DIV_W   = 50;   // numerator / remainder / quotient width
  localparam integer PROD_W  = 64;   // q[33:0] * K_q[27:0] = 34 x 28 bits
  localparam integer POST_SH = MEAN_FRAC + COEFF_FRAC - OUT_FRAC;   // == 7
  localparam [5:0]   DIV_LAST = DIV_W - 1;                          // == 49

  localparam [2:0] S_IDLE    = 3'd0,
                   S_MULC    = 3'd1,   // center_code * COUNT
                   S_DIFF    = 3'd2,   // d = SUM - center*COUNT
                   S_DIVLOAD = 3'd3,
                   S_DIVRUN  = 3'd4,
                   S_POST    = 3'd5,
                   S_FAIL    = 3'd6;

  reg [2:0]  state;
  reg [31:0] count_q;      // latched COUNT
  reg [16:0] center_q;     // latched centre code
  reg [31:0] coeff_q;      // latched K_q
  reg [63:0] sum_q;        // latched SUM
  reg        gate_fail_q;  // a gate failed at start -> skip the arithmetic

  reg [33:0] center_prod;  // center_q * count_q, only [33:0] is reachable
  reg [33:0] diff_mag;      // |d|
  reg        d_neg_q;       // sign of d, latched (read by the pair path in S_POST)
  reg [63:0] rho_prev_s;    // previous successful rho, two's complement (pair mode)
  reg [63:0] rs_prev_s;     // previous successful Rs, same convention
  reg [31:0] coeff_rs_lat;  // latched K_rs
  reg        have_prev;     // a previous successful result exists
  reg        pair_enable_q; // latched at start, like the other configuration


  reg [DIV_W-1:0] div_num;      // shifted numerator, then zeros
  reg [DIV_W:0]   div_rem;      // DIV_W+1 bits: the compare needs no overflow bit
  reg [DIV_W-1:0] div_quo;
  reg [5:0]       div_cnt;
  reg [DIV_W-1:0] div_divisor;  // COUNT zero-extended to DIV_W

  wire [DIV_W:0] div_rem_sh = {div_rem[DIV_W-1:0], div_num[DIV_W-1]};
  wire           div_ge     = (div_rem_sh >= {1'b0, div_divisor});

  // |d| <= 2^33 with the COUNT_MAX gate, so 35-bit unsigned arithmetic is exact:
  // sum_q <= COUNT_MAX*65535 < 2^33 and center_code*COUNT < 2^33.
  wire [34:0] diff_a     = {2'b00, sum_q[32:0]};
  wire [34:0] diff_b     = {1'b0,  center_prod};
  wire        diff_neg_w = (diff_a < diff_b);
  wire [34:0] diff_mag_w = diff_neg_w ? (diff_b - diff_a) : (diff_a - diff_b);

  wire [PROD_W-1:0] post_prod = div_quo[33:0] * coeff_q[27:0];

  // Signed view of the fresh result, used only by the pair path.
  wire [63:0] rho_new_mag = post_prod >> POST_SH;
  wire signed [63:0] rho_new_s = d_neg_q
                                 ? -$signed({1'b0, rho_new_mag[62:0]})
                                 :  $signed({1'b0, rho_new_mag[62:0]});
  wire signed [63:0] rho_avg_s = ($signed(rho_prev_s) + rho_new_s) >>> 1;
  wire [63:0] rho_avg_mag = rho_avg_s[63] ? (~rho_avg_s[63:0] + 64'd1) : rho_avg_s[63:0];
  wire [63:0] rs_new_mag = (div_quo[33:0] * coeff_rs_lat[27:0]) >> POST_SH;
  wire signed [63:0] rs_new_s = d_neg_q ? -$signed({1'b0, rs_new_mag[62:0]})
                                        :  $signed({1'b0, rs_new_mag[62:0]});
  wire signed [63:0] rs_avg_s = ($signed(rs_prev_s) + rs_new_s) >>> 1;
  wire [63:0] rs_avg_mag = rs_avg_s[63] ? (~rs_avg_s[63:0] + 64'd1) : rs_avg_s[63:0];

  always @(posedge clk) begin
      if (!reset_n) begin
          state               <= S_IDLE;
          busy                <= 1'b0;
          done                <= 1'b0;
          result_valid        <= 1'b0;
          rho_q               <= 64'd0;
          rs_q                <= 64'd0;
          flag_zero_count     <= 1'b0;
          flag_count_over_max <= 1'b0;
          flag_sum_overflow   <= 1'b0;
          flag_coeff_invalid  <= 1'b0;
          flag_negative       <= 1'b0;
          count_q             <= 32'd0;
          center_q            <= 17'd0;
          coeff_q             <= 32'd0;
          sum_q               <= 64'd0;
          gate_fail_q         <= 1'b0;
          center_prod         <= 34'd0;
          diff_mag            <= 34'd0;
          d_neg_q             <= 1'b0;
          rs_prev_s           <= 64'd0;
          coeff_rs_lat        <= 32'd0;
          quality_ok          <= 1'b0;
          flag_quality_low_count  <= 1'b0;
          flag_quality_wide_span  <= 1'b0;
          rho_prev_s          <= 64'd0;
          have_prev           <= 1'b0;
          pair_enable_q       <= 1'b0;
          pair_valid          <= 1'b0;
          flag_pair_missing   <= 1'b0;
          div_num             <= {DIV_W{1'b0}};
          div_rem             <= {(DIV_W+1){1'b0}};
          div_quo             <= {DIV_W{1'b0}};
          div_cnt             <= 6'd0;
          div_divisor         <= {DIV_W{1'b0}};
      end else begin
          // CLEAR drops the sticky result and the reason flags.  It never touches
          // an arithmetic in flight.
          if (clear_pulse) begin
              done                <= 1'b0;
              result_valid        <= 1'b0;
              rho_q               <= 64'd0;
              rs_q                <= 64'd0;
              flag_zero_count     <= 1'b0;
              flag_count_over_max <= 1'b0;
              flag_sum_overflow   <= 1'b0;
              flag_coeff_invalid  <= 1'b0;
              flag_negative       <= 1'b0;
              flag_pair_missing   <= 1'b0;
              pair_valid          <= 1'b0;
              rho_prev_s          <= 64'd0;
              rs_prev_s           <= 64'd0;
              have_prev           <= 1'b0;   // CLEAR opens a fresh pair window
          end

          case (state)
              S_IDLE: begin
                  busy <= 1'b0;
                  if (start_pulse) begin
                      busy                <= 1'b1;
                      done                <= 1'b0;
                      result_valid        <= 1'b0;
                      rho_q               <= 64'd0;
                      count_q             <= valid_count;
                      center_q            <= center_code;
                      coeff_q             <= coeff_k_q;
                      coeff_rs_lat        <= coeff_rs_q;
                      // Judged at the same instant the snapshot is latched, so the
                      // flags always describe THIS window.
                      flag_quality_low_count <= (min_valid_count != 32'd0) &&
                                                (valid_count < min_valid_count);
                      flag_quality_wide_span <= (max_span != 17'd0) &&
                                                ((max_code - min_code) > max_span);
                      quality_ok             <= !((min_valid_count != 32'd0) &&
                                                  (valid_count < min_valid_count)) &&
                                                !((max_span != 17'd0) &&
                                                  ((max_code - min_code) > max_span));
                      sum_q               <= sum_snapshot;
                      flag_zero_count     <= (valid_count == 32'd0);
                      flag_count_over_max <= (valid_count > COUNT_MAX);
                      flag_sum_overflow   <= snapshot_overflow;
                      // Either coefficient outside (0, COEFF_MAX] makes BOTH results unusable:
                      // the caller configures the pair together.
                      flag_coeff_invalid  <= (coeff_k_q == 32'd0) || (coeff_k_q > COEFF_MAX) ||
                                             (coeff_rs_q == 32'd0) || (coeff_rs_q > COEFF_MAX);
                      pair_enable_q       <= pair_enable;
                      flag_pair_missing   <= 1'b0;
                      pair_valid          <= 1'b0;
                      gate_fail_q         <= (valid_count == 32'd0) ||
                                             (valid_count > COUNT_MAX) ||
                                             snapshot_overflow ||
                                             (coeff_k_q == 32'd0) ||
                                             (coeff_k_q > COEFF_MAX) ||
                                             (coeff_rs_q == 32'd0) ||
                                             (coeff_rs_q > COEFF_MAX);
                      state               <= S_MULC;
                  end
              end

              // center_code * COUNT: 17 x 17 meaningful bits, one DSP, one cycle.
              S_MULC: begin
                  center_prod <= center_q * count_q[16:0];
                  state       <= S_DIFF;
              end

              // d = SUM - center*COUNT; keep the magnitude and the sign.
              S_DIFF: begin
                  // The sign of d is reported, never used by the arithmetic: the
                  // result is a magnitude, which is what the PS model consumes
                  // (abs(voltage)).  This used to be written into a scratch register
                  // that nothing read, and Vivado removed it as
                  // "Unused sequential element diff_neg_reg" -- the flag then stayed
                  // 0 forever.  Found by synthesis, not by inspection.
                  flag_negative <= (!gate_fail_q) && diff_neg_w;   // single-result path
                  d_neg_q       <= (!gate_fail_q) && diff_neg_w;
                  diff_mag      <= gate_fail_q ? 34'd0 : diff_mag_w[33:0];
                  state         <= gate_fail_q ? S_FAIL : S_DIVLOAD;
              end

              // numerator = |d| << MEAN_FRAC; remainder and quotient cleared.
              S_DIVLOAD: begin
                  div_num     <= diff_mag << MEAN_FRAC;      // <= 2^49, exactly DIV_W bits
                  div_rem     <= {(DIV_W+1){1'b0}};
                  div_quo     <= {DIV_W{1'b0}};
                  div_cnt     <= 6'd0;
                  div_divisor <= {{(DIV_W-32){1'b0}}, count_q};
                  state       <= S_DIVRUN;
              end

              // One quotient bit per clock: DIV_W = 50 clocks = 1 us at 50 MHz, once
              // per window.  Deliberately not pipelined and not shared with
              // stats_window, which currently owns the critical path (WNS 1.716 ns).
              // At div_cnt == DIV_LAST the final quotient bit is registered on the
              // same edge that enters S_POST, so div_quo is complete there.
              S_DIVRUN: begin
                  div_rem <= div_ge ? (div_rem_sh - {1'b0, div_divisor}) : div_rem_sh;
                  div_quo <= {div_quo[DIV_W-2:0], div_ge};
                  div_num <= {div_num[DIV_W-2:0], 1'b0};
                  if (div_cnt == DIV_LAST) begin
                      state <= S_POST;
                  end else begin
                      div_cnt <= div_cnt + 6'd1;
                  end
              end

              // rho_q = (q * K_q) >> POST_SH  ==  rho * 2^OUT_FRAC
              S_POST: begin
                  if (pair_enable_q && !have_prev) begin
                      // Refuse to present a lone half as a pair (fail-closed).
                      rho_q             <= 64'd0;
                      rs_q              <= 64'd0;
                      result_valid      <= 1'b0;
                      pair_valid        <= 1'b0;
                      flag_pair_missing <= 1'b1;
                      flag_negative     <= d_neg_q;
                      have_prev         <= 1'b0;
                      rho_prev_s        <= 64'd0;
                      rs_prev_s         <= 64'd0;
                  end else if (pair_enable_q) begin
                      // |0.5*(signed first + signed second)| -- matches the deployed model.
                      rho_q        <= rho_avg_mag;
                      rs_q         <= rs_avg_mag;
                      result_valid <= 1'b1;
                      pair_valid   <= 1'b1;
                      flag_negative <= rho_avg_s[63];
                      have_prev    <= 1'b1;
                      rho_prev_s   <= rho_new_s;
                      rs_prev_s    <= rs_new_s;
                  end else begin
                      rho_q        <= rho_new_mag;
                      rs_q         <= rs_new_mag;
                      result_valid <= 1'b1;
                      pair_valid   <= 1'b0;
                      flag_negative <= d_neg_q;
                      have_prev    <= 1'b1;
                      rho_prev_s   <= rho_new_s;
                      rs_prev_s    <= rs_new_s;
                  end
                  done         <= 1'b1;
                  busy         <= 1'b0;
                  state        <= S_IDLE;
              end

              S_FAIL: begin
                  rho_q        <= 64'd0;
                  rs_q         <= 64'd0;
                  result_valid <= 1'b0;
                  pair_valid   <= 1'b0;
                  // A failed compute must not leave a pairing candidate behind: a
                  // pair may only ever join two consecutive successful computes.
                  have_prev    <= 1'b0;
                  done         <= 1'b1;
                  busy         <= 1'b0;
                  state        <= S_IDLE;
              end

              default: state <= S_IDLE;
          endcase
      end
  end

endmodule
