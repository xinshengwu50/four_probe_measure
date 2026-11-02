# Add FP_DSP (PL auto-ranging) to the recreated all_design Block Design.
#
# Sourced by build/scripts/create_project.tcl AFTER recreate_bd.tcl, with the BD open and
# the FP_DSP sources already added to sources_1.  ALL_Final_0 is not modified: FP_DSP
#   * gets its own AXI-Lite slave at 0x43C1_0000 (64 KB),
#   * adds an AXI-Lite master on axi_smc whose address space maps ALL_Final_0 ONLY,
#   * taps CS / SCLK / SDO0 and the relay / current pins as extra loads on existing nets.
set fp_root [file normalize [file join [file dirname [info script]] ..]]

if {[llength [get_bd_cells -quiet ALL_Final_0]] != 1} {error "add_fp_dsp: ALL_Final_0 missing"}
if {[llength [get_bd_cells -quiet fp_dsp_0]] != 0} {error "add_fp_dsp: fp_dsp_0 already present"}

set fp_dsp_0 [create_bd_cell -type module -reference fp_dsp fp_dsp_0]

# Interconnect: PS (S00) + FP_DSP master (S01); ALL_Final, UART, GPIO, FP_DSP slave.
set_property -dict [list CONFIG.NUM_SI {2} CONFIG.NUM_MI {4}] [get_bd_cells axi_smc]
connect_bd_intf_net [get_bd_intf_pins fp_dsp_0/m_axi] [get_bd_intf_pins axi_smc/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_smc/M03_AXI] [get_bd_intf_pins fp_dsp_0/s_axi]

connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins fp_dsp_0/aclk]
connect_bd_net [get_bd_pins rst_ps7_0_100M/peripheral_aresetn] [get_bd_pins fp_dsp_0/aresetn]

# Passive taps (read-only loads on nets that already exist).
connect_bd_net [get_bd_pins ALL_Final_0/CS]          [get_bd_pins fp_dsp_0/spi_cs]
connect_bd_net [get_bd_pins ALL_Final_0/SCLK]        [get_bd_pins fp_dsp_0/spi_sclk]
connect_bd_net [get_bd_ports SDO0_0]                 [get_bd_pins fp_dsp_0/spi_sdo]
connect_bd_net [get_bd_pins ALL_Final_0/range0_ctrl] [get_bd_pins fp_dsp_0/range0_pin]
connect_bd_net [get_bd_pins ALL_Final_0/range1_ctrl] [get_bd_pins fp_dsp_0/range1_pin]
connect_bd_net [get_bd_pins ALL_Final_0/range2_ctrl] [get_bd_pins fp_dsp_0/range2_pin]
connect_bd_net [get_bd_pins ALL_Final_0/range3_ctrl] [get_bd_pins fp_dsp_0/range3_pin]
connect_bd_net [get_bd_pins ALL_Final_0/pol_i_ctrl]  [get_bd_pins fp_dsp_0/pol_i_pin]
connect_bd_net [get_bd_pins ALL_Final_0/pol_v_ctrl]  [get_bd_pins fp_dsp_0/pol_v_pin]
connect_bd_net [get_bd_pins ALL_Final_0/current_en]  [get_bd_pins fp_dsp_0/current_en_pin]

# Address map.  The PS sees FP_DSP beside the existing slaves; FP_DSP's master sees
# ALL_Final_0 at the same 0x4000_0000 (FP_DSP register 0x02C defaults to it) and nothing
# else -- no UART, no GPIO, not itself.
set ps_space [get_bd_addr_spaces processing_system7_0/Data]
assign_bd_address -offset 0x43C10000 -range 0x00010000 -target_address_space $ps_space \
    [get_bd_addr_segs fp_dsp_0/s_axi/reg0] -force
set fp_space [get_bd_addr_spaces fp_dsp_0/m_axi]
assign_bd_address -offset 0x40000000 -range 0x00010000 -target_address_space $fp_space \
    [get_bd_addr_segs ALL_Final_0/S_AXI/reg0] -force
# Everything else stays out of the FP_DSP master's space, explicitly.
foreach slave {axi_uartlite_0/S_AXI/Reg probe_gpio/S_AXI/Reg fp_dsp_0/s_axi/reg0} {
    set seg [get_bd_addr_segs -quiet $slave]
    if {[llength $seg] == 1} {
        exclude_bd_addr_seg -target_address_space $fp_space $seg
    }
}
puts "FP_DSP master address map:"
foreach seg [get_bd_addr_segs -quiet -of_objects $fp_space] {
    puts "  [get_property PATH $seg] offset=[get_property OFFSET $seg] excluded=[get_property -quiet EXCLUDED $seg]"
}

validate_bd_design
save_bd_design
puts "PASS_ADD_FP_DSP fp_dsp_0 at 0x43C10000; master -> ALL_Final_0 only"
