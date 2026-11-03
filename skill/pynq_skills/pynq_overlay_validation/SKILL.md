---
name: pynq-overlay-validation
description: Validate PYNQ overlay releases and AXI register contracts, generate safe Python drivers/tests, compare golden outputs and produce provenance-labeled reports. Use for PYNQ bring-up or reusable verification; no topic-specific motion or material algorithms.
---

# PYNQ Overlay Validation

1. Read README.md and references/contract.md. Keep register addresses, units, permissions and effects in a supplied contract, not driver literals. Do not invent a version register for an IP that lacks one.
2. Use scripts/pynq_toolkit.py audit for offline release/HWH checks first. A matching file basename or PL.bitfile_name alone is not proof of correct hardware. Manifest hashes only establish integrity relative to a trusted build manifest, not authenticity or electrical compatibility.
3. For board operations obtain actual target-board identity and confirm external actuators/current sources safe; scripts never know application-specific shutdown. load_board requires explicit download and safety_confirmed. There is deliberately no automatic retry/reload or CLI hardware command.
4. Match overlay.ip_dict after download before reading contract-defined safe identity registers. No writes by default. Destructive reads, pulse/W1C/command writes and dangerous outputs need separate explicit opt-in. Never run a blanket register walking-bit test.
5. For generated code use generate and generate_test.py. Run the generated offline tests. The tests verify wrapping/permissions, not HDL semantics or AXI timing.
6. Keep reference calculations separate from actual outputs. Run run_examples.py only as MOCK demonstration. Preserve actual board output, contract/release hashes, versions and measurement conditions for BOARD evidence.
7. Unknown or unavailable resource/timing metrics stay null. Existing Vivado parser recognizes specified labels only; inspect reference/reporting.md before treating missing fields as failures or zeros.
8. Document scope, failure cause, reproduction and correction. No-network operation is supported; third-party packages are not needed offline. PYNQ is imported only in explicit load_board.

Troubleshooting: references/troubleshooting.md. Tested scope and reproduction: README.md. Do not claim cross-board verification without corresponding records.

## 经验增强入口
source_identity.py比较显式指定源码哈希；必须另从Tcl/日志确认实际综合源。
历史来源与验证边界见 ../../evidence/cases.md。
