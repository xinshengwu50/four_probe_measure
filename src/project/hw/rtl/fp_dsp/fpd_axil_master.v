// Single-outstanding AXI4-Lite master for FP_DSP (module K of 自动选择量程方案).
//
// FP_DSP drives the analog front end ONLY through registers ALL_Final already exposes
// (ANALOG_CONTROL / CONTROL / STATUS / ANALOG_SEQ / ADC_CFG_SEQ).  ALL_Final's reset
// latch, heartbeat watchdog and relay sequencer therefore keep the final word: this
// master can ask for current, it cannot bypass them.
//
// Protocol: one command at a time.  cmd_valid is accepted only while busy == 0; done is
// a one-clock pulse with err/rdata valid in the same cycle.  BREADY/RREADY are raised
// together with the address phase (legal: a manager may assert READY before VALID).
//
// TIMEOUT: an interconnect that never answers is a broken system, not a retryable
// condition, and AXI forbids withdrawing VALID before its handshake.  The master
// therefore reports err+done once and then stays in HUNG (valid held) until reset;
// `hung` tells the sequencer to stop issuing commands.
module fpd_axil_master #(
    parameter integer TIMEOUT_CYCLES = 65535
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        cmd_valid,
    input  wire        cmd_write,
    input  wire [31:0] cmd_addr,
    input  wire [31:0] cmd_wdata,
    output reg         busy,
    output reg         done,
    output reg         err,
    output reg         hung,
    output reg  [31:0] rdata,

    output reg  [31:0] m_axi_awaddr,
    output wire [2:0]  m_axi_awprot,
    output reg         m_axi_awvalid,
    input  wire        m_axi_awready,
    output reg  [31:0] m_axi_wdata,
    output wire [3:0]  m_axi_wstrb,
    output reg         m_axi_wvalid,
    input  wire        m_axi_wready,
    input  wire [1:0]  m_axi_bresp,
    input  wire        m_axi_bvalid,
    output reg         m_axi_bready,
    output reg  [31:0] m_axi_araddr,
    output wire [2:0]  m_axi_arprot,
    output reg         m_axi_arvalid,
    input  wire        m_axi_arready,
    input  wire [31:0] m_axi_rdata,
    input  wire [1:0]  m_axi_rresp,
    input  wire        m_axi_rvalid,
    output reg         m_axi_rready
);

  localparam [1:0] M_IDLE = 2'd0,
                   M_WR   = 2'd1,
                   M_RD   = 2'd2,
                   M_HUNG = 2'd3;

  reg [1:0]  mstate;
  reg [31:0] tmo;

  assign m_axi_awprot = 3'b000;
  assign m_axi_arprot = 3'b000;
  assign m_axi_wstrb  = 4'hF;

  always @(posedge clk) begin
      if (!rst_n) begin
          mstate        <= M_IDLE;
          tmo           <= 32'd0;
          busy          <= 1'b0;
          done          <= 1'b0;
          err           <= 1'b0;
          hung          <= 1'b0;
          rdata         <= 32'd0;
          m_axi_awaddr  <= 32'd0;
          m_axi_awvalid <= 1'b0;
          m_axi_wdata   <= 32'd0;
          m_axi_wvalid  <= 1'b0;
          m_axi_bready  <= 1'b0;
          m_axi_araddr  <= 32'd0;
          m_axi_arvalid <= 1'b0;
          m_axi_rready  <= 1'b0;
      end else begin
          done <= 1'b0;
          case (mstate)
              M_IDLE: begin
                  if (cmd_valid) begin
                      busy <= 1'b1;
                      err  <= 1'b0;
                      tmo  <= 32'd0;
                      if (cmd_write) begin
                          m_axi_awaddr  <= cmd_addr;
                          m_axi_awvalid <= 1'b1;
                          m_axi_wdata   <= cmd_wdata;
                          m_axi_wvalid  <= 1'b1;
                          m_axi_bready  <= 1'b1;
                          mstate        <= M_WR;
                      end else begin
                          m_axi_araddr  <= cmd_addr;
                          m_axi_arvalid <= 1'b1;
                          m_axi_rready  <= 1'b1;
                          mstate        <= M_RD;
                      end
                  end
              end

              M_WR: begin
                  tmo <= tmo + 32'd1;
                  if (m_axi_awvalid && m_axi_awready) m_axi_awvalid <= 1'b0;
                  if (m_axi_wvalid && m_axi_wready)   m_axi_wvalid  <= 1'b0;
                  if (m_axi_bvalid && m_axi_bready) begin
                      // A response can only follow both handshakes (AXI rule), so the
                      // transaction is complete here.
                      m_axi_bready <= 1'b0;
                      err          <= (m_axi_bresp != 2'b00);
                      done         <= 1'b1;
                      busy         <= 1'b0;
                      mstate       <= M_IDLE;
                  end else if (tmo >= TIMEOUT_CYCLES) begin
                      err    <= 1'b1;
                      done   <= 1'b1;
                      hung   <= 1'b1;
                      mstate <= M_HUNG;
                  end
              end

              M_RD: begin
                  tmo <= tmo + 32'd1;
                  if (m_axi_arvalid && m_axi_arready) m_axi_arvalid <= 1'b0;
                  if (m_axi_rvalid && m_axi_rready) begin
                      m_axi_rready <= 1'b0;
                      rdata        <= m_axi_rdata;
                      err          <= (m_axi_rresp != 2'b00);
                      done         <= 1'b1;
                      busy         <= 1'b0;
                      mstate       <= M_IDLE;
                  end else if (tmo >= TIMEOUT_CYCLES) begin
                      err    <= 1'b1;
                      done   <= 1'b1;
                      hung   <= 1'b1;
                      mstate <= M_HUNG;
                  end
              end

              default: begin
                  // M_HUNG: hold everything until reset (see header).
                  busy <= 1'b1;
              end
          endcase
      end
  end

endmodule
