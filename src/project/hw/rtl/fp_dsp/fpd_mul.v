// Pipelined signed 40 x 40 -> 80 multiplier for FP_DSP.
//
// Every cross-multiplied range comparison (5.5.4 of 自动选择量程方案) goes through this
// one instance, issued sequentially by the range state machine.  Operand register,
// product register and output register let Vivado map it onto cascaded DSP48E1 slices
// with MREG/PREG at 50 MHz.  Latency: p reflects a/b four clocks after they change.
module fpd_mul (
    input  wire               clk,
    input  wire signed [39:0] a,
    input  wire signed [39:0] b,
    output reg  signed [79:0] p
);

  reg signed [39:0] a_r;
  reg signed [39:0] b_r;
  reg signed [79:0] m_r;

  always @(posedge clk) begin
      a_r <= a;
      b_r <= b;
      m_r <= a_r * b_r;
      p   <= m_r;
  end

endmodule
