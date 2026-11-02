# Reproducible project; do not hand-edit .xpr.
set root [file normalize [file join [file dirname [info script]] ../..]]
set project [file join $root build vivado four_probe_measure.xpr]
if {[file exists $project]} {error "Project already exists; use a fresh package copy or open it explicitly. No overwrite."}
set a [open [file join $root src project hw rtl all all_final.v] r];set rtl [read $a];close $a
set a [open [file join $root src ip_repo all_final src all_final.v] r];set packaged [read $a];close $a
if {$rtl ne $packaged} {error "Packaged RTL differs from source"}
create_project four_probe_measure [file join $root build vivado] -part xc7z020clg400-1
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list [file join $root src ip_repo]] [current_project]
update_ip_catalog
if {[llength [get_board_parts -quiet tul.com.tw:pynq-z2:part0:1.0]]} {
 set_property board_part tul.com.tw:pynq-z2:part0:1.0 [current_project]
} else {puts "WARNING: PYNQ-Z2 board files not installed; explicit exported PS configuration will be used."}
set fp_list [file join $root src project hw rtl fp_dsp fp_dsp_sources.f]
set f [open $fp_list r];set fp_lines [split [read $f] "\n"];close $f
foreach line $fp_lines {
 set line [string trim $line]
 if {$line eq "" || [string index $line 0] eq "#"} continue
 add_files -norecurse [file join $root src project $line]
}
update_compile_order -fileset sources_1
source [file join $root src project scripts recreate_bd.tcl]
set bd [get_files -quiet */all_design.bd]
if {[llength $bd] != 1} {error "BD recreation failed"}
open_bd_design $bd
if {[get_property CONFIG.C_BAUDRATE [get_bd_cells axi_uartlite_0]] != 115200} {error "Wrong UART baud"}
if {[llength [get_bd_ports -quiet uart_tx_0]] != 0} {
    error "Stale BD port uart_tx_0: recreate from a clean build/vivado directory"
}
if {[llength [get_bd_ports -quiet tx_0]] != 1} {
    error "Expected exactly one AXI UART Lite tx_0 port"
}
source [file join $root src project scripts add_fp_dsp.tcl]
validate_bd_design
save_bd_design
file copy -force [lindex $bd 0] [file join $root build vivado recreated.bd]
generate_target all $bd
set wrapper [make_wrapper -files $bd -top]
add_files -norecurse $wrapper
add_files -fileset constrs_1 -norecurse [file join $root src project hw constraints all.xdc]
set_property top all_design_wrapper [get_filesets sources_1]
update_compile_order -fileset sources_1
puts "PASS_RECREATE_PROJECT [get_property NAME [current_project]]"
close_project
exit 0
