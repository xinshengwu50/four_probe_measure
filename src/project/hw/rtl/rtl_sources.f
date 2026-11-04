# ALL_Final RTL source list -- the single source of truth for every build and
# verification script and for ip_repo/all_final (asserted by
# tests/test_final_four_probe_system.py).
#
# Rules:
#   * one path per line, relative to the project root (four_probe_pynq/)
#   * '#' starts a comment; blank lines are ignored
#   * entry order matters: the FIRST entry is the top level the Block Design
#     instantiates (ALL_Final)
#   * basenames must be unique -- ip_repo/all_final/src/ is a flat directory
#
hw/rtl/all/all_final.v
hw/rtl/analog/dac8562_serializer.v
hw/rtl/common/motion_sync.v
hw/rtl/adc/ads8681_capture.v
hw/rtl/motion/axis_x.v
hw/rtl/motion/axis_r.v
hw/rtl/motion/axis_z.v
hw/rtl/analog/analog_seq.v
hw/rtl/common/session_guard.v
hw/rtl/measurement/stats_window.v
hw/rtl/measurement/meas_calc.v
hw/rtl/measurement/meas_chain.v
