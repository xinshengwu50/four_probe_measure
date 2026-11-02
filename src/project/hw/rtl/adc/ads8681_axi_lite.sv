// AXI4-Lite register wrapper for the single-shot ADS8681 sampler.
//
// AXI and ADC transactions intentionally share one clock.  The wrapper keeps
// the ADC raw frame and status in the PL; voltage conversion remains in PS
// software until the ADS8681 frame semantics and analog calibration are fixed.
module ads8681_axi_lite #(
    parameter int unsigned FRAME_BITS = 32,
    parameter int unsigned CLK_DIV = 4,
    parameter int unsigned SPI_TIMEOUT_CYCLES = 0,
    parameter logic [31:0] VERSION = 32'h0002_0000
) (
    input  logic        s_axi_aclk,
    input  logic        s_axi_aresetn,
    input  logic [31:0] s_axi_awaddr,
    input  logic        s_axi_awvalid,
    output logic        s_axi_awready,
    input  logic [31:0] s_axi_wdata,
    input  logic [3:0]  s_axi_wstrb,
    input  logic        s_axi_wvalid,
    output logic        s_axi_wready,
    output logic [1:0]  s_axi_bresp,
    output logic        s_axi_bvalid,
    input  logic        s_axi_bready,
    input  logic [31:0] s_axi_araddr,
    input  logic        s_axi_arvalid,
    output logic        s_axi_arready,
    output logic [31:0] s_axi_rdata,
    output logic [1:0]  s_axi_rresp,
    output logic        s_axi_rvalid,
    input  logic        s_axi_rready,
    output logic        adc_cs_n,
    output logic        adc_sclk,
    output logic        adc_mosi,
    input  logic        adc_miso
);

    localparam logic [7:0] REG_CONTROL       = 8'h00;
    localparam logic [7:0] REG_STATUS        = 8'h04;
    localparam logic [7:0] REG_ERROR_CODE    = 8'h08;
    localparam logic [7:0] REG_VERSION       = 8'h0C;
    localparam logic [7:0] REG_TX_DATA       = 8'h10;
    localparam logic [7:0] REG_RX_DATA       = 8'h14;
    localparam logic [7:0] REG_SAMPLE_COUNT  = 8'h18;
    localparam logic [7:0] REG_TIMEOUT_COUNT = 8'h1C;

    localparam logic [1:0] AXI_OKAY = 2'b00;

    logic aw_pending;
    logic w_pending;
    logic [31:0] awaddr_reg;
    logic [31:0] wdata_reg;
    logic [3:0] wstrb_reg;
    logic bvalid_reg;
    logic [1:0] bresp_reg;
    logic rvalid_reg;
    logic [31:0] rdata_reg;
    logic [1:0] rresp_reg;

    logic enable_reg;
    logic [31:0] tx_data_reg;
    logic start_pulse;
    logic clear_error_pulse;
    logic result_valid_reg;

    logic adc_busy;
    logic adc_ready;
    logic adc_done;
    logic adc_data_valid;
    logic adc_timeout;
    logic adc_frame_error;
    logic adc_start_rejected;
    logic adc_error;
    logic [2:0] adc_error_code;
    logic [FRAME_BITS-1:0] adc_rx_data;
    logic [31:0] adc_sample_count;
    logic [31:0] adc_timeout_count;

    assign s_axi_awready = !aw_pending && !bvalid_reg;
    assign s_axi_wready  = !w_pending && !bvalid_reg;
    assign s_axi_bvalid  = bvalid_reg;
    assign s_axi_bresp   = bresp_reg;
    assign s_axi_arready = !rvalid_reg;
    assign s_axi_rvalid  = rvalid_reg;
    assign s_axi_rdata   = rdata_reg;
    assign s_axi_rresp   = rresp_reg;

    adc_sample_ctrl #(
        .FRAME_BITS(FRAME_BITS),
        .CLK_DIV(CLK_DIV),
        .SPI_TIMEOUT_CYCLES(SPI_TIMEOUT_CYCLES)
    ) adc_sample_ctrl_i (
        .clk(s_axi_aclk),
        .reset_n(s_axi_aresetn),
        .enable(enable_reg),
        .start(start_pulse),
        .clear_error(clear_error_pulse),
        .tx_data(tx_data_reg),
        .miso(adc_miso),
        .cs_n(adc_cs_n),
        .sclk(adc_sclk),
        .mosi(adc_mosi),
        .busy(adc_busy),
        .ready(adc_ready),
        .done(adc_done),
        .data_valid(adc_data_valid),
        .timeout(adc_timeout),
        .frame_error(adc_frame_error),
        .start_rejected(adc_start_rejected),
        .error(adc_error),
        .error_code(adc_error_code),
        .rx_data(adc_rx_data),
        .sample_count(adc_sample_count),
        .timeout_count(adc_timeout_count)
    );

    always_ff @(posedge s_axi_aclk or negedge s_axi_aresetn) begin
        if (!s_axi_aresetn) begin
            aw_pending       <= 1'b0;
            w_pending        <= 1'b0;
            awaddr_reg       <= '0;
            wdata_reg        <= '0;
            wstrb_reg        <= '0;
            bvalid_reg       <= 1'b0;
            bresp_reg        <= AXI_OKAY;
            rvalid_reg       <= 1'b0;
            rdata_reg        <= '0;
            rresp_reg        <= AXI_OKAY;
            enable_reg       <= 1'b0;
            tx_data_reg      <= '0;
            start_pulse      <= 1'b0;
            clear_error_pulse <= 1'b0;
            result_valid_reg <= 1'b0;
        end else begin
            start_pulse       <= 1'b0;
            clear_error_pulse <= 1'b0;

            if (bvalid_reg && s_axi_bready) begin
                bvalid_reg <= 1'b0;
            end
            if (rvalid_reg && s_axi_rready) begin
                rvalid_reg <= 1'b0;
            end

            if (s_axi_awvalid && s_axi_awready) begin
                aw_pending <= 1'b1;
                awaddr_reg <= s_axi_awaddr;
            end
            if (s_axi_wvalid && s_axi_wready) begin
                w_pending <= 1'b1;
                wdata_reg <= s_axi_wdata;
                wstrb_reg <= s_axi_wstrb;
            end

            if (adc_data_valid) begin
                result_valid_reg <= 1'b1;
            end

            if (aw_pending && w_pending && !bvalid_reg) begin
                aw_pending <= 1'b0;
                w_pending  <= 1'b0;
                bvalid_reg <= 1'b1;
                bresp_reg  <= AXI_OKAY;

                case (awaddr_reg[7:0])
                    REG_CONTROL: begin
                        if (wstrb_reg[0]) begin
                            enable_reg <= wdata_reg[0];
                            if (wdata_reg[1]) begin
                                start_pulse <= 1'b1;
                                result_valid_reg <= 1'b0;
                            end
                            if (wdata_reg[2]) begin
                                clear_error_pulse <= 1'b1;
                            end
                        end
                    end
                    REG_TX_DATA: begin
                        if (wstrb_reg[0]) tx_data_reg[7:0]   <= wdata_reg[7:0];
                        if (wstrb_reg[1]) tx_data_reg[15:8]  <= wdata_reg[15:8];
                        if (wstrb_reg[2]) tx_data_reg[23:16] <= wdata_reg[23:16];
                        if (wstrb_reg[3]) tx_data_reg[31:24] <= wdata_reg[31:24];
                    end
                    default: begin
                        // Unimplemented writes are accepted and ignored.
                    end
                endcase
            end

            if (s_axi_arvalid && s_axi_arready) begin
                rvalid_reg <= 1'b1;
                rresp_reg  <= AXI_OKAY;
                case (s_axi_araddr[7:0])
                    REG_CONTROL: begin
                        rdata_reg <= {31'd0, enable_reg};
                    end
                    REG_STATUS: begin
                        rdata_reg <= {
                            23'd0,
                            adc_start_rejected,
                            adc_frame_error,
                            adc_timeout,
                            adc_error,
                            adc_done,
                            result_valid_reg,
                            adc_ready,
                            adc_busy
                        };
                    end
                    REG_ERROR_CODE: begin
                        rdata_reg <= {29'd0, adc_error_code};
                    end
                    REG_VERSION: begin
                        rdata_reg <= VERSION;
                    end
                    REG_TX_DATA: begin
                        rdata_reg <= tx_data_reg;
                    end
                    REG_RX_DATA: begin
                        rdata_reg <= adc_rx_data;
                    end
                    REG_SAMPLE_COUNT: begin
                        rdata_reg <= adc_sample_count;
                    end
                    REG_TIMEOUT_COUNT: begin
                        rdata_reg <= adc_timeout_count;
                    end
                    default: begin
                        rdata_reg <= 32'd0;
                    end
                endcase
            end

        end
    end

    initial begin
        if (FRAME_BITS != 32) begin
            $error("ads8681_axi_lite currently requires FRAME_BITS=32");
        end
    end
endmodule
