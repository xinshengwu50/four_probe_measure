// Single-shot sampling wrapper around ads8681_spi_master.
// AXI-Lite is intentionally not mixed into this transaction-level block.
module adc_sample_ctrl #(
    parameter int unsigned FRAME_BITS = 32,
    parameter int unsigned CLK_DIV = 4,
    parameter int unsigned SPI_TIMEOUT_CYCLES = 0
) (
    input  logic                    clk,
    input  logic                    reset_n,
    input  logic                    enable,
    input  logic                    start,
    input  logic                    clear_error,
    input  logic [FRAME_BITS-1:0]   tx_data,
    input  logic                    miso,
    output logic                    cs_n,
    output logic                    sclk,
    output logic                    mosi,
    output logic                    busy,
    output logic                    ready,
    output logic                    done,
    output logic                    data_valid,
    output logic                    timeout,
    output logic                    frame_error,
    output logic                    start_rejected,
    output logic                    error,
    output logic [2:0]              error_code,
    output logic [FRAME_BITS-1:0]   rx_data,
    output logic [31:0]             sample_count,
    output logic [31:0]             timeout_count
 
);

    localparam logic [2:0] ERR_NONE           = 3'd0;
    localparam logic [2:0] ERR_DISABLED_START = 3'd1;
    localparam logic [2:0] ERR_BUSY_START    = 3'd2;
    localparam logic [2:0] ERR_TIMEOUT       = 3'd3;
    localparam logic [2:0] ERR_FRAME         = 3'd4;

    logic spi_start;
    logic spi_busy;
    logic spi_done;
    logic spi_timeout;
    logic spi_frame_error;
    logic spi_start_rejected;
    logic [FRAME_BITS-1:0] spi_rx_data;
    logic start_armed;

    assign busy = spi_busy;
    assign ready = enable && !spi_busy && !error;

    ads8681_spi_master #(
        .FRAME_BITS(FRAME_BITS),
        .CLK_DIV(CLK_DIV),
        .TIMEOUT_CYCLES(SPI_TIMEOUT_CYCLES),
        .CPOL(1'b0),
        .CPHA(1'b0)
    ) spi_master_i (
        .clk(clk),
        .reset_n(reset_n),
        .start(spi_start),
        .tx_data(tx_data),
        .miso(miso),
        .cs_n(cs_n),
        .sclk(sclk),
        .mosi(mosi),
        .busy(spi_busy),
        .done(spi_done),
        .timeout(spi_timeout),
        .frame_error(spi_frame_error),
        .start_rejected(spi_start_rejected),
        .rx_data(spi_rx_data)
    );

    always_ff @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            spi_start       <= 1'b0;
            start_armed     <= 1'b1;
            done            <= 1'b0;
            data_valid      <= 1'b0;
            timeout         <= 1'b0;
            frame_error     <= 1'b0;
            start_rejected  <= 1'b0;
            error           <= 1'b0;
            error_code      <= ERR_NONE;
            rx_data         <= '0;
            sample_count    <= 32'd0;
            timeout_count   <= 32'd0;
        end else begin
            spi_start      <= 1'b0;
            done           <= 1'b0;
            data_valid     <= 1'b0;
            timeout        <= 1'b0;
            frame_error    <= 1'b0;
            start_rejected <= 1'b0;

            if (!start) begin
                start_armed <= 1'b1;
            end

            if (clear_error) begin
                error      <= 1'b0;
                error_code <= ERR_NONE;
            end

            if (start && start_armed) begin
                start_armed <= 1'b0;
                if (!enable) begin
                    error      <= 1'b1;
                    error_code <= ERR_DISABLED_START;
                    start_rejected <= 1'b1;
                end else if (spi_busy || error) begin
                    error      <= 1'b1;
                    error_code <= ERR_BUSY_START;
                    start_rejected <= 1'b1;
                end else begin
                    spi_start <= 1'b1;
                end
            end

            if (spi_done) begin
                rx_data      <= spi_rx_data;
                done         <= 1'b1;
                data_valid   <= 1'b1;
                sample_count <= sample_count + 1'b1;
            end

            if (spi_timeout) begin
                timeout       <= 1'b1;
                error         <= 1'b1;
                error_code    <= ERR_TIMEOUT;
                timeout_count <= timeout_count + 1'b1;
            end

            if (spi_frame_error || spi_start_rejected) begin
                frame_error    <= spi_frame_error;
                start_rejected <= 1'b1;
                error          <= 1'b1;
                error_code     <= spi_frame_error ? ERR_FRAME : ERR_BUSY_START;
            end
        end
    end
endmodule

