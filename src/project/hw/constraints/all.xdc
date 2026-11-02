## ============================================================================
## ALL_Final four-probe controller - PYNQ-Z2
##
## Physical interface used:
##   Raspberry Pi 40-pin header for PL signals
##   On-board LED0/LED1/LED2 for status indicators
##
## All PL IO: LVCMOS33
##
## PS clock, PS reset, DDR and MIO are handled by the Zynq Processing System.
## Do not assign PACKAGE_PIN to S_AXI_*, FCLK_CLK0 or peripheral_aresetn here.
##
## Important:
##   The port names below assume the generated Block Design wrapper really
##   contains the "_0" suffix. Verify with:
##
##       get_ports
##       get_ports -filter {NAME =~ "*SDI*"}
##
## ============================================================================


## ============================================================================
## 1. ADS8681 SPI interface
##    Raspberry Pi header pins:
##      SDI_0  -> RPi pin 37
##      SDO0_0 -> RPi pin 35
##      SCLK_0 -> RPi pin 33
##      CS_0  -> RPi pin 31
##      RST_0 -> RPi pin 29
##      RVS_0 -> RPi pin 27
##
## Note:
##   RPi pins 3/5/27/29/31/33/35/37 are PL-connected GPIO pins on PYNQ-Z2.
##   Do not simultaneously use the shared Pmod A functions.
## ============================================================================

# SPI MOSI: FPGA -> ADS8681
set_property PACKAGE_PIN Y14 [get_ports SDI_0]
set_property IOSTANDARD LVCMOS33 [get_ports SDI_0]

# SPI MISO: ADS8681 -> FPGA
set_property PACKAGE_PIN W13 [get_ports SDO0_0]
set_property IOSTANDARD LVCMOS33 [get_ports SDO0_0]

# SPI clock: FPGA -> ADS8681
set_property PACKAGE_PIN V12 [get_ports SCLK_0]
set_property IOSTANDARD LVCMOS33 [get_ports SCLK_0]

# SPI chip select, active low
set_property PACKAGE_PIN V16 [get_ports CS_0]
set_property IOSTANDARD LVCMOS33 [get_ports CS_0]

# ADS8681 reset output
set_property PACKAGE_PIN T10 [get_ports RST_0]
set_property IOSTANDARD LVCMOS33 [get_ports RST_0]

# ADS8681 ready/status input
set_property PACKAGE_PIN T11 [get_ports RVS_0]
set_property IOSTANDARD LVCMOS33 [get_ports RVS_0]


## ============================================================================
## 2. Z-axis stepper motor interface
##    Raspberry Pi header pins:
##      step_pulse_0 -> RPi pin 21
##      dir_0        -> RPi pin 19
##      ena_0        -> RPi pin 23
##      sensor_0     -> RPi pin 15
##
## sensor_0 has no internal pull-up in this version.
## An external bias resistor or a driven sensor output is required.
## ============================================================================

# Z-axis step pulse
set_property PACKAGE_PIN V10 [get_ports step_pulse_0]
set_property IOSTANDARD LVCMOS33 [get_ports step_pulse_0]

# Z-axis direction
set_property PACKAGE_PIN V8 [get_ports dir_0]
set_property IOSTANDARD LVCMOS33 [get_ports dir_0]

# Z-axis driver enable
set_property PACKAGE_PIN W10 [get_ports ena_0]
set_property IOSTANDARD LVCMOS33 [get_ports ena_0]

# Z-axis home/limit sensor input
set_property PACKAGE_PIN U8 [get_ports sensor_0]
set_property IOSTANDARD LVCMOS33 [get_ports sensor_0]


## ============================================================================
## 3. X-axis rotation platform interface
##    Raspberry Pi header pins:
##      x_pul_out_0  -> RPi pin 13
##      x_dir_out_0  -> RPi pin 11
##      x_trig_in_0  -> RPi pin 7
##
## x_trig_in_0 has no internal pull-up in this version.
## An external bias resistor or a driven trigger output is required.
## ============================================================================

# X-axis rotation pulse
set_property PACKAGE_PIN V7 [get_ports x_pul_out_0]
set_property IOSTANDARD LVCMOS33 [get_ports x_pul_out_0]

# X-axis rotation direction
set_property PACKAGE_PIN U7 [get_ports x_dir_out_0]
set_property IOSTANDARD LVCMOS33 [get_ports x_dir_out_0]

# X-axis external trigger input
set_property PACKAGE_PIN W14 [get_ports x_trig_in_0]
set_property IOSTANDARD LVCMOS33 [get_ports x_trig_in_0]


## ============================================================================
## 4. Status outputs and UART ports
##
## The physical start_0 port has been removed. Single-point start is driven
## through AXI CONTROL bit 0.
## ============================================================================

# PL UART output to Raspberry Pi header pin 3
# This is not the board's PS USB-UART interface.
## UARTLite TX
set_property PACKAGE_PIN T14 [get_ports {tx_0}]
set_property IOSTANDARD LVCMOS33 [get_ports {tx_0}]

## UARTLite RX
set_property PACKAGE_PIN U12 [get_ports {rx_0}]
set_property IOSTANDARD LVCMOS33 [get_ports {rx_0}]


## ============================================================================
## 5. On-board status LEDs
## ============================================================================

# LED0: fault indication, high level turns LED on
set_property PACKAGE_PIN R14 [get_ports err_flag_0]
set_property IOSTANDARD LVCMOS33 [get_ports err_flag_0]

# LED1: measurement-cycle completion
set_property PACKAGE_PIN P14 [get_ports cycle_done_0]
set_property IOSTANDARD LVCMOS33 [get_ports cycle_done_0]

# LED2: measurement counter bit 0
set_property PACKAGE_PIN N16 [get_ports led_meas_cnt0_0]
set_property IOSTANDARD LVCMOS33 [get_ports led_meas_cnt0_0]

## ============================================================================
## 5.1 R-axis radial motor interface
##
## These are wrapper port names, including the _0 suffix generated by the
## Block Design. PUL keeps Y18 for compatibility with the existing radial
## wiring. The physical start input was removed; start is AXI-only.
##
## r_sensor_0 is active-low. The internal pull-up keeps it inactive when the
## sensor is unconnected; it is released when the home flag pulls the pin low.
## ============================================================================

set_property PACKAGE_PIN Y9 [get_ports r_pul_out_0]
set_property IOSTANDARD LVCMOS33 [get_ports r_pul_out_0]

set_property PACKAGE_PIN A20 [get_ports r_dir_out_0]
set_property IOSTANDARD LVCMOS33 [get_ports r_dir_out_0]

set_property PACKAGE_PIN B19 [get_ports r_ena_out_0]
set_property IOSTANDARD LVCMOS33 [get_ports r_ena_out_0]

set_property PACKAGE_PIN Y16 [get_ports r_sensor_0]
set_property IOSTANDARD LVCMOS33 [get_ports r_sensor_0]
set_property PULLUP true [get_ports r_sensor_0]

## ============================================================================
## 6. Optional SPI timing constraints
##
## Leave disabled until:
##   1. The ADS8681 SPI timing parameters are confirmed.
##   2. SCLK is declared as a generated clock.
##   3. SDO0/RVS external setup and hold timing is known.
##
## The following commands are intentionally commented out.
## ============================================================================

# set_output_delay \
#     -clock [get_clocks -of_objects [get_ports SCLK_0]] \
#     -max 2 \
#     [get_ports {SDI_0 CS_0 RST_0}]

# set_input_delay \
#     -clock [get_clocks -of_objects [get_ports SCLK_0]] \
#     -max 2 \
#     [get_ports {SDO0_0 RVS_0}]

## ============================================================================
## 7. Four-probe board control bus on Arduino AR2..AR13
##
## bit 0..11 of probe_ctrl map to the board J_CTRL control signals:
##   bit0 CURRENT_EN, bit1 DAC_SCK, bit2 DAC_DATA, bit3 DAC_SYNC,
##   bit4..7 RANGE0..RANGE3, bit8 POL_I_CTRL, bit9 POL_V_CTRL,
##   bit10..11 reserved (leave unconnected on the board).
##
## The circuit board 5V and 3.3V are externally powered. Connect grounds
## between the board and PYNQ; do not use these FPGA outputs as power rails.
## ============================================================================
set_property PACKAGE_PIN U13 [get_ports {probe_ctrl[0]}]  ;# AR2 CURRENT_EN
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[0]}]
set_property PACKAGE_PIN H15 [get_ports {probe_ctrl[1]}]  ;# AR3 DAC_SCK
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[1]}]
set_property PACKAGE_PIN T12 [get_ports {probe_ctrl[2]}]  ;# AR4 DAC_DATA
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[2]}]
set_property PACKAGE_PIN F16 [get_ports {probe_ctrl[3]}]  ;# AR5 DAC_SYNC
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[3]}]
set_property PACKAGE_PIN R16 [get_ports {probe_ctrl[4]}]  ;# AR6 RANGE0_CTRL
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[4]}]
set_property PACKAGE_PIN U17 [get_ports {probe_ctrl[5]}]  ;# AR7 RANGE1_CTRL
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[5]}]
set_property PACKAGE_PIN V17 [get_ports {probe_ctrl[6]}]  ;# AR8 RANGE2_CTRL
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[6]}]
set_property PACKAGE_PIN V18 [get_ports {probe_ctrl[7]}]  ;# AR9 RANGE3_CTRL
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[7]}]
set_property PACKAGE_PIN T16 [get_ports {probe_ctrl[8]}]  ;# AR10 POL_I_CTRL
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[8]}]
set_property PACKAGE_PIN R17 [get_ports {probe_ctrl[9]}]  ;# AR11 POL_V_CTRL
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[9]}]
set_property PACKAGE_PIN P18 [get_ports {probe_ctrl[10]}] ;# AR12 reserved
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[10]}]
set_property PACKAGE_PIN N17 [get_ports {probe_ctrl[11]}] ;# AR13 reserved
set_property IOSTANDARD LVCMOS33 [get_ports {probe_ctrl[11]}]
