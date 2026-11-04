// Generic, single-transaction SPI master for the ADS8681 data path.
//
// The default is a 32-bit MSB-first SPI mode-0 frame, matching the legacy
// wiring baseline.  Frame semantics and analog-code interpretation are kept
// outside this block; this module only moves bits and reports transport
// errors.
module ads8681_spi_master #(
    parameter int unsigned FRAME_BITS = 32,
    parameter int unsigned CLK_DIV = 4,
    parameter int unsigned TIMEOUT_CYCLES = 0,
    parameter logic CPOL = 1'b0,
    parameter logic CPHA = 1'b0
) (
    input  logic                    clk,
    input  logic                    reset_n,
    input  logic                    start,
    input  logic [FRAME_BITS-1:0]   tx_data,
    input  logic                    miso,
    output logic                    cs_n,
    output logic                    sclk,
    output logic                    mosi,
    output logic                    busy,
    output logic                    done,
    output logic                    timeout,
    output logic                    frame_error,
    output logic                    start_rejected,
    output logic [FRAME_BITS-1:0]   rx_data
);

    localparam int DIV_COUNT_BITS = (CLK_DIV <= 1) ? 1 : $clog2(CLK_DIV);
    localparam int BIT_COUNT_BITS = (FRAME_BITS <= 1) ? 1 : $clog2(FRAME_BITS + 1);
    localparam int TIMEOUT_COUNT_BITS = (TIMEOUT_CYCLES <= 1) ? 1 : $clog2(TIMEOUT_CYCLES + 1);

    typedef enum logic {IDLE, TRANSFER} state_t;
    state_t state;

    logic [DIV_COUNT_BITS-1:0] div_count;
    logic [BIT_COUNT_BITS-1:0] bits_remaining;
    logic [TIMEOUT_COUNT_BITS-1:0] timeout_count;
    logic [FRAME_BITS-1:0] tx_shift;
    logic [FRAME_BITS-1:0] rx_shift;

    initial begin
        if (FRAME_BITS == 0) $error("FRAME_BITS must be greater than zero");
        if (CLK_DIV == 0) $error("CLK_DIV must be greater than zero");
        if (CPHA !== 1'b0 && CPHA !== 1'b1) $error("CPHA must be 0 or 1");
    end

    always_ff @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            state          <= IDLE;
            div_count      <= '0;
            bits_remaining <= '0;
            timeout_count  <= '0;
            tx_shift       <= '0;
            rx_shift       <= '0;
            rx_data        <= '0;
            cs_n           <= 1'b1;
            sclk           <= CPOL;
            mosi           <= 1'b0;
            busy           <= 1'b0;
            done           <= 1'b0;
            timeout        <= 1'b0;
            frame_error    <= 1'b0;
            start_rejected <= 1'b0;
        end else begin
            done           <= 1'b0;
            timeout        <= 1'b0;
            frame_error    <= 1'b0;
            start_rejected <= 1'b0;

            if (state == IDLE) begin
                busy      <= 1'b0;
                cs_n      <= 1'b1;
                sclk      <= CPOL;
                mosi      <= 1'b0;
                div_count <= '0;

                if (start) begin
                    state          <= TRANSFER;
                    busy           <= 1'b1;
                    cs_n           <= 1'b0;
                    sclk           <= CPOL;
                    tx_shift       <= tx_data;
                    rx_shift       <= '0;
                    bits_remaining <= FRAME_BITS;
                    timeout_count  <= '0;
                    // In CPHA=0 the first bit is valid before the first
                    // leading edge.  CPHA=1 changes it on that edge.
                    mosi           <= (CPHA == 1'b0) ? tx_data[FRAME_BITS-1] : 1'b0;
                end
            end else begin
                busy <= 1'b1;
                cs_n <= 1'b0;

                if (start) begin
                    start_rejected <= 1'b1;
                end

                if (TIMEOUT_CYCLES != 0) begin
                    if (timeout_count >= TIMEOUT_CYCLES - 1) begin
                        state         <= IDLE;
                        busy          <= 1'b0;
                        cs_n          <= 1'b1;
                        sclk          <= CPOL;
                        mosi          <= 1'b0;
                        timeout       <= 1'b1;
                        timeout_count <= '0;
                    end else begin
                        timeout_count <= timeout_count + 1'b1;
                    end
                end

                if (state == TRANSFER && div_count == CLK_DIV - 1 &&
                    !(TIMEOUT_CYCLES != 0 && timeout_count >= TIMEOUT_CYCLES - 1)) begin
                    div_count <= '0;
                    if (sclk == CPOL) begin
                        // Leading edge.  Mode 0 samples here; mode 1 shifts
                        // the next output bit here.
                        sclk <= ~CPOL;
                        if (CPHA == 1'b0) begin
                            rx_shift <= (rx_shift << 1) | miso;
                            tx_shift <= tx_shift << 1;
                        end else begin
                            mosi     <= tx_shift[FRAME_BITS-1];
                            tx_shift <= tx_shift << 1;
                        end
                    end else begin
                        // Trailing edge.  Mode 0 changes output here; mode 1
                        // samples the input here.
                        sclk <= CPOL;
                        if (CPHA == 1'b0) begin
                            if (bits_remaining == 1) begin
                                state   <= IDLE;
                                busy    <= 1'b0;
                                cs_n    <= 1'b1;
                                mosi    <= 1'b0;
                                done    <= 1'b1;
                                rx_data <= rx_shift;
                            end else begin
                                bits_remaining <= bits_remaining - 1'b1;
                                mosi           <= tx_shift[FRAME_BITS-1];
                            end
                        end else begin
                            rx_shift <= (rx_shift << 1) | miso;
                            if (bits_remaining == 1) begin
                                state   <= IDLE;
                                busy    <= 1'b0;
                                cs_n    <= 1'b1;
                                mosi    <= 1'b0;
                                done    <= 1'b1;
                                rx_data <= (rx_shift << 1) | miso;
                            end else begin
                                bits_remaining <= bits_remaining - 1'b1;
                            end
                        end
                    end
                end else if (state == TRANSFER && div_count != CLK_DIV - 1) begin
                    div_count <= div_count + 1'b1;
                end
            end
        end
    end
endmodule

