// Sequential unsigned restoring divider for FP_DSP: quo = num / den.
//
// One quotient bit per clock (NW clocks per division).  FP_DSP divides at most a few
// times per millisecond-scale window, so a 56-cycle divider costs nothing and keeps the
// arithmetic exact and easy to mirror in the Python golden model (floor division).
// Same structure as the divider in hw/rtl/measurement/meas_calc.v.
//
// `start` is accepted only while busy == 0.  den == 0 is never issued by the sequencer
// (it checks the sample count first); the result would be all ones.
module fpd_div #(
    parameter integer NW = 56,   // numerator / quotient width
    parameter integer DW = 32    // denominator width
) (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          start,
    input  wire [NW-1:0] num,
    input  wire [DW-1:0] den,
    output reg           busy,
    output reg           done,
    output reg  [NW-1:0] quo
);

  reg [NW-1:0] n_sh;
  reg [DW:0]   rem;
  reg [DW-1:0] d;
  reg [6:0]    cnt;

  wire [DW:0] rem_sh = {rem[DW-1:0], n_sh[NW-1]};
  wire        ge     = (rem_sh >= {1'b0, d});

  always @(posedge clk) begin
      if (!rst_n) begin
          busy <= 1'b0;
          done <= 1'b0;
          quo  <= {NW{1'b0}};
          n_sh <= {NW{1'b0}};
          rem  <= {(DW+1){1'b0}};
          d    <= {DW{1'b0}};
          cnt  <= 7'd0;
      end else begin
          done <= 1'b0;
          if (start && !busy) begin
              n_sh <= num;
              rem  <= {(DW+1){1'b0}};
              d    <= den;
              quo  <= {NW{1'b0}};
              cnt  <= 7'd0;
              busy <= 1'b1;
          end else if (busy) begin
              rem  <= ge ? (rem_sh - {1'b0, d}) : rem_sh;
              quo  <= {quo[NW-2:0], ge};
              n_sh <= {n_sh[NW-2:0], 1'b0};
              if (cnt == NW - 1) begin
                  busy <= 1'b0;
                  done <= 1'b1;
              end else begin
                  cnt <= cnt + 7'd1;
              end
          end
      end
  end

endmodule
