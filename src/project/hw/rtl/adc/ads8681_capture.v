// ADS8681 capture chain, extracted verbatim from ALL_Final: SPI clock generation, RVS
// synchroniser, configuration/sampling state machine, 32/33-bit SPI core, code -> mV.
//
// Protocol constants (device register addresses, the range word, frame geometry, state
// encodings) are localparam ON PURPOSE.  They encode the configuration frame -- including
// the input range.  If they were overridable, a wrong override would change the range and
// corrupt every v_mv conversion, while the equivalence testbench (same override on both
// sides) would still report 0 mismatches: nothing would catch it.  Only the two timing /
// tunable values below are parameters.
module ads8681_capture #(
    parameter integer RVS_TIMEOUT_CYCLES     = 200,          // 4 us at 50 MHz
    parameter [31:0]  ADC_PWRUP_DELAY_CYCLES = 32'd2000000   // 40 ms at 50 MHz
) (
    input  wire        clk,
    input  wire        reset_n,
    input  wire        RVS,
    input  wire        SDO0,
    input  wire        reinit,      // = axi_adc_reinit_pulse
    output reg         SDI,
    output reg         SCLK,
    output reg         CS,
    output reg         RST,
    output reg  [31:0] rx_reg,
    output reg         rx_valid,
    output reg  [15:0] v_mv,
    output reg  [15:0] cfg_seq
);

  localparam SPI_IDLE         = 2'd0;
  localparam SPI_START_TX     = 2'd1;
  localparam SPI_WAIT_DONE    = 2'd2;
  localparam CFG_Reset        = 4'd0;
  localparam CFG_Delay        = 4'd1;
  localparam CFG_Init         = 4'd2;
  localparam CFG_WAIT         = 4'd3;
  localparam CFG_READ_DATA    = 4'd4;
  localparam CFG_READ_DONE    = 4'd5;
  localparam CFG_WAIT_RVS     = 4'd6;
  localparam DEVICE_ID_REG    = 16'h0000;
  localparam RST_PWRCTL_REG   = 16'h0004;
  localparam SDI_CTL_REG      = 16'h0008;
  localparam SDO_CTL_REG      = 16'h000C;
  localparam DATAOUT_CTL_REG  = 16'h0010;
  localparam RANGE_SEL_REG    = 16'h0014;
  localparam ALARM_REG        = 16'h0020;
  localparam ALARM_H_TH_REG   = 16'h0024;
  localparam ALARM_L_TH_REG   = 16'h0028;
  localparam RANGE_5120MV     = 16'h0003;
  localparam SPI_DATA_WIDTH   = 32;
  localparam SPI_FRAME_WIDTH  = 33; // read frame: one leading dummy bit
  localparam SPI_CONFIG_WIDTH = 32; // config frame stays 32 bits
  localparam CPOL             = 1'b0;
  localparam CPHA             = 1'b0;
  localparam SPI_S_IDLE       = 2'd0;
  localparam SPI_S_PREPARE    = 2'd1;
  localparam SPI_S_TRANSFER   = 2'd2;
  localparam SPI_S_FINISH     = 2'd3;

  wire [31:0] SPI_TX_Data;
  wire        SPI_Start;
  reg  [31:0] SPI_RX_Data;
  reg         SPI_Busy;
  reg         SPI_Done;
  reg  [31:0] Delay_Cnt;
  reg  [3:0]  cfg_state;
  reg  [31:0] TX_REG;
  reg         Send_Flag;
  reg         rvs_meta;
  reg         rvs_sync;
  reg         rvs_seen_low;
  reg [15:0]  rvs_wait_count;
  reg [1:0]               spi_state;
  reg [SPI_FRAME_WIDTH-1:0] tx_shift;
  reg [SPI_FRAME_WIDTH-1:0] rx_shift;
  reg        spi_frame_33;
  reg [5:0]  spi_frame_bits;
  reg                     clk_cnt_spi;
  reg [7:0]               bit_cnt_spi;
  reg [31:0] step1_adc;
  reg [15:0] raw_v_mv;
  wire [15:0] ADC_Data;

  //==================== 1. SPI时钟生成逻辑 ==========
  always @(posedge clk) begin
      if (!reset_n)
          SCLK <= CPOL;
      else if (spi_state == SPI_S_FINISH || CS)
          SCLK <= CPOL;
      else
          SCLK <= clk_cnt_spi;
  end
  
  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          rvs_meta <= 1'b1;
          rvs_sync <= 1'b1;
      end else begin
          rvs_meta <= RVS;
          rvs_sync <= rvs_meta;
      end
  end

  //==================== 2. ADC配置与采样控制状态机 ==========
  always @(posedge clk) begin
      if (!reset_n) begin
          cfg_state  <= CFG_Reset;
          Delay_Cnt  <= 32'd0;
          RST        <= 1'b1;
          Send_Flag  <= 1'b0;
          TX_REG     <= 32'd0;
          rvs_seen_low <= 1'b0;
          rvs_wait_count <= 16'd0;
          spi_frame_33 <= 1'b0;
          cfg_seq <= 16'd0;
      end else if (reinit) begin
          cfg_state <= CFG_Reset;
          Delay_Cnt <= 32'd0;
          RST <= 1'b1;
          Send_Flag <= 1'b0;
          TX_REG <= 32'd0;
          rvs_seen_low <= 1'b0;
          rvs_wait_count <= 16'd0;
          spi_frame_33 <= 1'b0;
      end else begin
          case (cfg_state)
              CFG_Reset: begin
                  RST <= 1'b1;
                  Delay_Cnt <= 32'd0;
                  cfg_state <= CFG_Delay;
              end
  
              CFG_Delay: begin
                  Delay_Cnt <= Delay_Cnt + 1'd1;
                  // RST is asserted unconditionally in this state: all three branches of
                  // the original two-level comparison assigned RST <= 1'b1, so the
                  // 1,000,000 mid-point had no observable effect.  The wait length is now
                  // the parameter ADC_PWRUP_DELAY_CYCLES (default unchanged, 40 ms at
                  // 50 MHz) instead of hard-coded literals.
                  RST <= 1'b1;
                  if(Delay_Cnt >= ADC_PWRUP_DELAY_CYCLES) begin
                      Delay_Cnt <= 32'd0;
                      cfg_state <= CFG_Init;
                  end
              end
  
              CFG_Init: begin
                  TX_REG <= {(16'hD000 | RANGE_SEL_REG), RANGE_5120MV};
                  spi_frame_33 <= 1'b0;
                  Send_Flag <= 1'b1;
                  cfg_state <= CFG_WAIT;
              end
  
              CFG_WAIT: begin
                  Send_Flag <= 1'b0;
                  if(SPI_Done) begin
                      cfg_seq <= cfg_seq + 16'd1;
                      rvs_seen_low <= 1'b0;
                      rvs_wait_count <= 16'd0;
                      cfg_state <= CFG_WAIT_RVS;
                  end
              end
  
              CFG_READ_DATA: begin
                  TX_REG <= 32'h00000000;
                  spi_frame_33 <= 1'b1;
                  Send_Flag <= 1'b1;
                  cfg_state <= CFG_READ_DONE;
              end
  
              CFG_READ_DONE: begin
                  Send_Flag <= 1'b0;
                  if(SPI_Done) begin
                      rx_reg <= SPI_RX_Data;
                      rvs_seen_low <= 1'b0;
                      rvs_wait_count <= 16'd0;
                      cfg_state <= CFG_WAIT_RVS;
                  end
              end

              CFG_WAIT_RVS: begin
                  Send_Flag <= 1'b0;
                  if (rvs_seen_low) begin
                      if (rvs_sync) begin
                          rvs_seen_low <= 1'b0;
                          rvs_wait_count <= 16'd0;
                          cfg_state <= CFG_READ_DATA;
                      end else if (rvs_wait_count >= RVS_TIMEOUT_CYCLES - 1) begin
                          rvs_seen_low <= 1'b0;
                          rvs_wait_count <= 16'd0;
                          cfg_state <= CFG_READ_DATA;
                      end else begin
                          rvs_wait_count <= rvs_wait_count + 16'd1;
                      end
                  end else begin
                      if (!rvs_sync)
                          rvs_seen_low <= 1'b1;
                      if (rvs_wait_count >= RVS_TIMEOUT_CYCLES - 1) begin
                          rvs_seen_low <= 1'b0;
                          rvs_wait_count <= 16'd0;
                          cfg_state <= CFG_READ_DATA;
                      end else begin
                          rvs_wait_count <= rvs_wait_count + 16'd1;
                      end
                  end
              end
          endcase
      end
  end
  
  //==================== 3. SPI主机核心收发状态机 ==========
  always @(posedge clk) begin
      if (!reset_n) begin
          spi_state   <= SPI_S_IDLE;
          CS          <= 1'b1;
          SPI_Busy    <= 1'b0;
          SPI_Done    <= 1'b0;
          clk_cnt_spi <= 1'b0;
          bit_cnt_spi <= 8'd0;
          tx_shift    <= 32'd0;
          rx_shift    <= 32'd0;
          SDI         <= 1'b0;
          SPI_RX_Data <= 32'd0;
      end else begin
          SPI_Done <= 1'b0;
          clk_cnt_spi <= clk_cnt_spi + 1'b1;
  
          case (spi_state)
              SPI_S_IDLE: begin
                  CS <= 1'b1;
                  SPI_Busy <= 1'b0;
                  if (SPI_Start && !SPI_Busy) begin
                      spi_state <= SPI_S_PREPARE;
                      SPI_Busy  <= 1'b1;
                      spi_frame_bits <= spi_frame_33 ? SPI_FRAME_WIDTH[5:0] : SPI_CONFIG_WIDTH[5:0];
                      tx_shift  <= spi_frame_33 ? {1'b0, SPI_TX_Data} : {SPI_TX_Data, 1'b0};
                      clk_cnt_spi <= 1'b0;
                  end
              end
  
              SPI_S_PREPARE: begin
                  CS        <= 1'b0;
                  spi_state <= SPI_S_TRANSFER;
                  clk_cnt_spi <= 1'b0;
                  bit_cnt_spi <= 8'd0;
              end
  
              SPI_S_TRANSFER: begin
                  if ((CPHA == 0 && clk_cnt_spi == CPOL) ||
                      (CPHA == 1 && clk_cnt_spi == ~CPOL)) begin
                      SDI <= tx_shift[SPI_FRAME_WIDTH-1];
                      tx_shift <= {tx_shift[SPI_FRAME_WIDTH-2:0], 1'b0};
                  end else begin
                      rx_shift <= {rx_shift[SPI_FRAME_WIDTH-2:0], SDO0};
                  end
  
                  if (clk_cnt_spi == 1'b1) begin
                      clk_cnt_spi <= 1'b0;
                      if (bit_cnt_spi == spi_frame_bits - 6'd1)
                          spi_state <= SPI_S_FINISH;
                      else
                          bit_cnt_spi <= bit_cnt_spi + 1'b1;
                  end
              end
  
              SPI_S_FINISH: begin
                  if (clk_cnt_spi == 1'b1) begin
                      CS          <= 1'b1;
                      SPI_Done    <= 1'b1;
                      SPI_RX_Data <= rx_shift[SPI_DATA_WIDTH-1:0];
                      spi_state   <= SPI_S_IDLE;
                  end
              end
          endcase
      end
  end
  
  //==================== 4. ADC码值转实际电压 ==========
  always @(posedge clk or negedge reset_n) begin
      if(!reset_n) begin
          step1_adc <= 32'd0;
          raw_v_mv <= 16'd0;
      end else begin
          if (ADC_Data < 32768) begin
              step1_adc <= 32'd0;
              raw_v_mv <= 16'd0;
          end else begin
              step1_adc <= (ADC_Data - 32768) * 50;
              raw_v_mv  <= step1_adc[20:5];
          end
      end
  end
  
  always @(posedge clk or negedge reset_n) begin
      if(!reset_n) begin
          v_mv <= 16'd0;
      end else begin
          // 直接跟随转换结果，避免窄门限导致电压长时间保持为0
          if(raw_v_mv >= 16'd50 && raw_v_mv <= 16'd5000)
              v_mv <= raw_v_mv;
          else
              v_mv <= 16'd0;
      end
  end
  


  always @(posedge clk or negedge reset_n) begin
      if (!reset_n) begin
          rx_valid <= 1'b0;
      end else begin
          rx_valid <= 1'b0;
          if (cfg_state == CFG_READ_DONE && SPI_Done)
              rx_valid <= 1'b1;
      end
  end
  assign ADC_Data    = rx_reg[31:16];
  assign SPI_Start   = Send_Flag;
  assign SPI_TX_Data = TX_REG;

endmodule
