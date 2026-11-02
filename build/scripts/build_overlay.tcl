# Reproducible project; do not hand-edit .xpr.
set root [file normalize [file join [file dirname [info script]] ../..]]
open_project [file join $root build vivado four_probe_measure.xpr]
reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {error "Synthesis failed"}
reset_run impl_1
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {error "Implementation failed"}
open_run impl_1
set out [file join $root build rebuilt]
file mkdir $out
report_timing_summary -file [file join $out timing_summary.rpt]
report_utilization -file [file join $out utilization.rpt]
report_drc -file [file join $out drc.rpt]
file copy -force [file join [get_property DIRECTORY [get_runs impl_1]] all_design_wrapper.bit] [file join $out all_design.bit]
set hwh [glob -nocomplain [file join $root build vivado four_probe_measure.gen sources_1 bd all_design hw_handoff *.hwh]]
if {[llength $hwh] != 1} {error "Matching generated HWH missing"}
file copy -force [lindex $hwh 0] [file join $out all_design.hwh]
puts "PASS_BUILD_OVERLAY $out; actual board loading still required"
close_project
exit 0
