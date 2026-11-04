// Passive ADS8681 frame decoder for FP_DSP (module A of 自动选择量程方案).
//
// WHY PASSIVE
//   ALL_Final owns the ADC SPI bus.  This block only LISTENS to the same three nets the
//   board sees (CS, SCLK from ALL_Final, SDO0 from the ADC), so adding FP_DSP to the
//   Block Design changes nothing inside ALL_Final; the equivalence testbench and the
//   ALX5 version word stay valid.  The FP_DSP structural anchor is
//   fp_dsp_structure.json (11 files / 11 modules at this revision).
//
// BIT ALIGNMENT (cycle-exact with hw/rtl/adc/ads8681_capture.v)
//   ALL_Final samples SDO0 on the clock edge where clk_cnt_spi == 1, and the SAME edge
//   loads SCLK <= 1.  This block registers SDO0 on every edge (sdo_q), so on the edge
//   that ALL_Final samples, sdo_q captures the identical value; one edge later SCLK reads
//   1 while sclk_q still reads 0, and the bit shifted in here is that sdo_q.  Every frame
//   therefore delivers exactly the bits ALL_Final's rx_shift received.
//   SDO0 is not synchronised -- deliberately the same as ALL_Final, so that both flops
//   see the same sample; the metastability exposure is the original design's.
//
// FRAME TYPES
//   33 SCLK rising edges = data frame (leading dummy bit + 32 bits).  ALL_Final keeps
//   rx_shift[31:0] and the code is bits [31:16] of that, i.e. sh[31:16] here.
//   32 edges = configuration frame (counted, no sample).  Anything else = bad frame.
module fpd_spi_sniffer (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        spi_cs,
    input  wire        spi_sclk,
    input  wire        spi_sdo,
    output reg         sample_valid,   // one clock wide, per data frame
    output reg  [15:0] sample_code,
    output reg         cfg_frame,      // one clock wide, per configuration frame
    output reg         bad_frame       // one clock wide, per frame of unexpected length
);

  reg        cs_q;
  reg        sclk_q;
  reg        sdo_q;
  reg [32:0] sh;
  reg [5:0]  nbits;

  always @(posedge clk) begin
      if (!rst_n) begin
          cs_q         <= 1'b1;
          sclk_q       <= 1'b0;
          sdo_q        <= 1'b0;
          sh           <= 33'd0;
          nbits        <= 6'd0;
          sample_valid <= 1'b0;
          sample_code  <= 16'd0;
          cfg_frame    <= 1'b0;
          bad_frame    <= 1'b0;
      end else begin
          cs_q         <= spi_cs;
          sclk_q       <= spi_sclk;
          sdo_q        <= spi_sdo;
          sample_valid <= 1'b0;
          cfg_frame    <= 1'b0;
          bad_frame    <= 1'b0;

          if (!spi_cs && cs_q) begin
              // CS falling edge: a new frame starts.
              nbits <= 6'd0;
          end else if (!spi_cs && spi_sclk && !sclk_q) begin
              sh <= {sh[31:0], sdo_q};
              if (nbits != 6'd63)
                  nbits <= nbits + 6'd1;
          end

          if (spi_cs && !cs_q) begin
              // CS rising edge: the frame is complete.
              if (nbits == 6'd33) begin
                  sample_valid <= 1'b1;
                  sample_code  <= sh[31:16];
              end else if (nbits == 6'd32) begin
                  cfg_frame <= 1'b1;
              end else begin
                  bad_frame <= 1'b1;
              end
          end
      end
  end

endmodule
