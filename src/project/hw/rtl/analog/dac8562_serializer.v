// DAC8562 24-bit frame serializer, extracted verbatim from ALL_Final.
// Behaviour is unchanged: a 24-bit frame (DB23:DB22=00, command=011, address=000)
// shifted out MSB first, with SCLK/DIN/SYNC_N timing from DAC_HALF_CYCLES.
//
// dac_code_reg / dac_code_loaded stay in the top level (the AXI register file owns
// them); this module takes the code in and returns busy/done/seq for read-back.
module dac8562_serializer #(
    parameter integer DAC_HALF_CYCLES = 10   // 2.5 MHz DAC SCLK at 50 MHz
) (
    input  wire        clk,
    input  wire        reset_n,
    input  wire [15:0] code,
    input  wire        start,
    input  wire        abort,
    output reg         busy,
    output reg         done,
    output reg  [15:0] seq,
    output wire        sclk,
    output wire        din,
    output wire        sync_n
);

  localparam [1:0] DAC_STATE_IDLE  = 2'd0;
  localparam [1:0] DAC_STATE_SETUP = 2'd1;
  localparam [1:0] DAC_STATE_LOW   = 2'd2;
  localparam [1:0] DAC_STATE_HIGH  = 2'd3;

  reg [23:0] shift_reg;
  reg [4:0]  bits_remaining;
  reg [15:0] half_count;
  reg [1:0]  state_reg;

  wire [23:0] frame_word = 24'h180000 | {8'd0, code};

  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          shift_reg      <= 24'd0;
          bits_remaining <= 5'd0;
          half_count     <= 16'd0;
          state_reg      <= DAC_STATE_IDLE;
          busy           <= 1'b0;
          done           <= 1'b0;
          seq        <= 16'd0;
      end else if (abort) begin
          shift_reg      <= 24'd0;
          bits_remaining <= 5'd0;
          half_count     <= 16'd0;
          state_reg      <= DAC_STATE_IDLE;
          busy           <= 1'b0;
          done           <= 1'b0;
      end else begin
          case (state_reg)
              DAC_STATE_IDLE: begin
                  if (start) begin
                      shift_reg      <= frame_word;
                      bits_remaining <= 5'd24;
                      half_count     <= 16'd0;
                      state_reg      <= DAC_STATE_SETUP;
                      busy           <= 1'b1;
                      done           <= 1'b0;
                  end
              end
              DAC_STATE_SETUP: begin
                  if (half_count >= (DAC_HALF_CYCLES - 1)) begin
                      half_count <= 16'd0;
                      state_reg  <= DAC_STATE_LOW;
                  end else begin
                      half_count <= half_count + 16'd1;
                  end
              end
              DAC_STATE_LOW: begin
                  if (half_count >= (DAC_HALF_CYCLES - 1)) begin
                      half_count <= 16'd0;
                      if (bits_remaining == 5'd1) begin
                          state_reg <= DAC_STATE_IDLE;
                          busy      <= 1'b0;
                          done      <= 1'b1;
                          seq   <= seq + 16'd1;
                      end else begin
                          state_reg <= DAC_STATE_HIGH;
                      end
                  end else begin
                      half_count <= half_count + 16'd1;
                  end
              end
              DAC_STATE_HIGH: begin
                  if (half_count == 16'd0) begin
                      if (bits_remaining != 5'd1) begin
                          shift_reg      <= shift_reg << 1;
                          bits_remaining <= bits_remaining - 5'd1;
                      end
                      half_count <= 16'd1;
                  end else if (half_count >= (DAC_HALF_CYCLES - 1)) begin
                      half_count <= 16'd0;
                      state_reg  <= DAC_STATE_LOW;
                  end else begin
                      half_count <= half_count + 16'd1;
                  end
              end
              default: state_reg <= DAC_STATE_IDLE;
          endcase
      end
  end

  assign sclk   = busy ? ((state_reg == DAC_STATE_LOW) ? 1'b0 : 1'b1) : 1'b1;
  assign din    = busy ? shift_reg[23] : 1'b0;
  assign sync_n = busy ? 1'b0 : 1'b1;

endmodule
