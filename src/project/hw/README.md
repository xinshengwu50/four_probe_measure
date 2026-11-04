# Hardware source

rtl/rtl_sources.f is the ALL_Final modular source list; rtl/fp_dsp/fp_dsp_sources.f is FP_DSP v5. Constraints retain existing verified wiring, not a new wiring proposal. Preserve safety priority, synchronizers, ADC framing and units when editing.

Use build/scripts/create_project.tcl from the package root; no hand-editedxpr. FPGA testbenches are undertb and are run bysim/scripts/run_hdl.py through command-lineXSim. Register/control ABI and board acceptance boundaries are described inreport.
