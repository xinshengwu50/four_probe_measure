# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

import unittest

from four_probe_sw.adc_conversion import AdcConfig
from four_probe_sw.materials import CalculationMode, MaterialProfile, MaterialRegistry


def make_bulk_profile(material_id: str = "test_bulk") -> MaterialProfile:
    return MaterialProfile(
        material_id=material_id,
        name="Synthetic bulk sample",
        mode=CalculationMode.BULK,
        adc=AdcConfig(bits=16, full_scale_v=5.12),
        excitation_current_a=0.01,
        probe_spacing_m=1e-3,
        geometry_factor=2.0,
        valid_voltage_min_v=0.001,
        valid_voltage_max_v=4.9,
        resistivity_min_ohm_m=1e-6,
        resistivity_max_ohm_m=1e3,
    )


class MaterialProfileTests(unittest.TestCase):
    def test_bulk_profile_requires_spacing_and_geometry(self) -> None:
        with self.assertRaises(ValueError):
            MaterialProfile(
                material_id="broken",
                name="Broken",
                mode=CalculationMode.BULK,
                adc=AdcConfig(),
                excitation_current_a=0.01,
            )

    def test_thin_film_profile_requires_thickness(self) -> None:
        with self.assertRaises(ValueError):
            MaterialProfile(
                material_id="broken",
                name="Broken",
                mode=CalculationMode.THIN_FILM,
                adc=AdcConfig(),
                excitation_current_a=0.01,
            )

    def test_registry_rejects_duplicate_ids_and_round_trips(self) -> None:
        profile = make_bulk_profile()
        registry = MaterialRegistry([profile])

        self.assertIs(registry.get("test_bulk"), profile)
        with self.assertRaises(ValueError):
            registry.add(profile)

        restored = MaterialRegistry.from_dict(registry.to_dict())
        self.assertEqual(restored.get("test_bulk"), profile)
        self.assertEqual(restored.ids(), ("test_bulk",))

    def test_registry_can_replace_explicitly(self) -> None:
        first = make_bulk_profile()
        second = make_bulk_profile()
        second = MaterialProfile(
            **{**second.to_dict(), "name": "Updated synthetic sample"}
        )
        registry = MaterialRegistry([first])

        registry.add(second, replace=True)

        self.assertEqual(registry.get("test_bulk").name, "Updated synthetic sample")


if __name__ == "__main__":
    unittest.main()
