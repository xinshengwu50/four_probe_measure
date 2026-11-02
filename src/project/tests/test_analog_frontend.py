# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest

from four_probe_sw.analog_frontend import (
    ANALOG_CTRL_ABORT,
    ANALOG_CTRL_CURRENT_ENABLE,
    ANALOG_CTRL_POLARITY,
    ANALOG_CTRL_RANGE_SHIFT,
    ANALOG_CTRL_START,
    AnalogFrontendController,
    ANALOG_STATUS_DONE,
    ANALOG_STATUS_ERROR,
    CONTROL_ADC_REINIT,
    DAC_CONTROL_START,
    DAC_WRITE_UPDATE_A,
    REG_ADC_CFG_SEQ,
    REG_ANALOG_CONTROL,
    REG_CONTROL,
    REG_ANALOG_SEQ,
    REG_ANALOG_TEST_CONTROL,
    REG_DAC_CODE,
    REG_DAC_CONTROL,
    REG_DAC_SEQ,
    dac_code_to_voltage,
    expected_current_a,
    validate_range_index,
    voltage_to_dac_code,
)


class FakeMmio:
    def __init__(self):
        self.regs = {REG_ANALOG_CONTROL: ANALOG_STATUS_DONE}
        self.writes = []

    def write(self, offset, value):
        offset = int(offset)
        value = int(value) & 0xFFFF_FFFF
        self.writes.append((offset, value))
        if offset == REG_ANALOG_CONTROL:
            if value == ANALOG_CTRL_ABORT:
                self.regs[REG_ANALOG_CONTROL] = 0
            else:
                self.regs[REG_ANALOG_CONTROL] = ANALOG_STATUS_DONE | (value & 0x38) | ((value & ANALOG_CTRL_CURRENT_ENABLE) << 5)
                self.regs[REG_ANALOG_SEQ] = (self.regs.get(REG_ANALOG_SEQ, 0) + 1) & 0xFFFF
        elif offset == REG_CONTROL:
            if value & CONTROL_ADC_REINIT:
                self.regs[REG_ADC_CFG_SEQ] = (self.regs.get(REG_ADC_CFG_SEQ, 0) + 1) & 0xFFFF
        elif offset == REG_ANALOG_TEST_CONTROL:
            range_mask = value & 0x0F
            if value & (1 << 31) and bin(range_mask).count("1") > 1:
                self.regs[REG_ANALOG_CONTROL] = ANALOG_STATUS_ERROR
            else:
                self.regs[REG_ANALOG_CONTROL] = ANALOG_STATUS_DONE
            self.regs[offset] = value
        elif offset == REG_DAC_CONTROL and value & DAC_CONTROL_START:
            self.regs[REG_DAC_SEQ] = (self.regs.get(REG_DAC_SEQ, 0) + 1) & 0xFFFF
            self.regs[offset] = value
        else:
            self.regs[offset] = value

    def read(self, offset):
        return self.regs.get(int(offset), 0)


class AnalogFrontendTests(unittest.TestCase):
    def test_range_validation(self):
        for value in range(4):
            self.assertEqual(validate_range_index(value), value)
        with self.assertRaises(ValueError):
            validate_range_index(4)

    def test_dac_voltage_conversion(self):
        self.assertEqual(voltage_to_dac_code(0.0), 0x0000)
        self.assertEqual(voltage_to_dac_code(1.0), 0x6666)
        self.assertEqual(voltage_to_dac_code(2.5), 0xFFFF)
        self.assertAlmostEqual(dac_code_to_voltage(0x8000), 1.250019, places=6)

    def test_expected_nominal_currents(self):
        self.assertAlmostEqual(expected_current_a(1.0, 0), 100e-6)
        self.assertAlmostEqual(expected_current_a(1.0, 1), 1e-3)
        self.assertAlmostEqual(expected_current_a(1.0, 2), 10e-3)
        self.assertAlmostEqual(expected_current_a(1.0, 3), 100e-3)

    def test_configure_encodes_safe_command(self):
        mmio = FakeMmio()
        controller = AnalogFrontendController(mmio)
        controller.configure(2, reverse=True, enable_current=True)
        command = mmio.writes[-1][1]
        self.assertTrue(command & ANALOG_CTRL_START)
        self.assertTrue(command & ANALOG_CTRL_CURRENT_ENABLE)
        self.assertTrue(command & ANALOG_CTRL_POLARITY)
        self.assertEqual((command >> ANALOG_CTRL_RANGE_SHIFT) & 0x3, 2)

    def test_reconfigure_adc_waits_for_sequence(self):
        mmio = FakeMmio()
        controller = AnalogFrontendController(mmio)
        seq = controller.reconfigure_adc()
        self.assertEqual(seq, 1)
        self.assertIn((REG_CONTROL, CONTROL_ADC_REINIT), mmio.writes)

    def test_safe_off_uses_abort_path(self):
        mmio = FakeMmio()
        controller = AnalogFrontendController(mmio)
        controller.safe_off()
        self.assertEqual(mmio.writes[-1], (REG_ANALOG_CONTROL, ANALOG_CTRL_ABORT))

    def test_direct_test_rejects_multiple_range_relays(self):
        controller = AnalogFrontendController(FakeMmio())
        with self.assertRaises(ValueError):
            controller.enter_direct_test(relay_mask=0x03, enable_current=True)

    def test_direct_test_accepts_one_range_and_two_polarity_relays(self):
        mmio = FakeMmio()
        controller = AnalogFrontendController(mmio)
        controller.enter_direct_test(relay_mask=0x22, pol_i=False, pol_v=True)
        value = mmio.regs[REG_ANALOG_TEST_CONTROL]
        self.assertTrue(value & (1 << 31))
        self.assertEqual(value & 0x3F, 0x22)

    def test_set_dac_voltage_writes_expected_frame_code(self):
        mmio = FakeMmio()
        controller = AnalogFrontendController(mmio)
        code = controller.set_dac_voltage(1.0)
        self.assertEqual(code, 0x6666)
        self.assertIn((REG_DAC_CODE, 0x6666), mmio.writes)
        self.assertIn((REG_DAC_CONTROL, DAC_CONTROL_START), mmio.writes)
        self.assertEqual(0x180000 | code, DAC_WRITE_UPDATE_A | code)


if __name__ == "__main__":
    unittest.main()
