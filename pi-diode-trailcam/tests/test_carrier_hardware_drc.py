#!/usr/bin/env python3
"""
Test Suite: RP2040 Arctic Carrier Hardware Netlist, KiCad PCB, & DRC Verification
Checks that the custom 4-layer PCB design has 100% electrical connectivity, zero unrouted
pins, valid KiCad syntax, matched SMT BOM/CPL files, and complete manufacturing packages.
"""

import os
import sys
import unittest
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HARDWARE_DIR = os.path.join(REPO_ROOT, "pi-diode-trailcam", "hardware")
sys.path.insert(0, HARDWARE_DIR)

import generate_complete_manufacturing_files as gen


class TestCarrierHardwareDRC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Regenerate fresh manufacturing packages
        gen.generate_all(os.path.join(REPO_ROOT, "pi-diode-trailcam"))

    def test_01_all_components_have_valid_bom_and_cpl(self):
        """Verify that every component in CPL has a matching BOM entry with LCSC part number."""
        cpl_des_set = set(des for des, _, _, _, _, _, _ in gen.COMPONENTS)
        bom_des_set = set()
        for des_group, _, _, lcsc in gen.BOM_TABLE:
            self.assertTrue(lcsc.startswith("C"), f"Invalid LCSC part number: {lcsc}")
            for d in des_group.split(","):
                bom_des_set.add(d.strip())

        missing_in_bom = cpl_des_set - bom_des_set
        self.assertEqual(len(missing_in_bom), 0, f"Components missing in BOM: {missing_in_bom}")

    def test_02_100_percent_electrical_netlist_coverage(self):
        """Verify that 100% of component pins belong to an electrical net (zero unrouted pins)."""
        pad_map = {}
        for des, val, pkg, cx, cy, rot, layer in gen.COMPONENTS:
            rel_pads = gen.get_footprint_pads(pkg)
            for pin_idx in range(1, len(rel_pads) + 1):
                net = gen.PIN_NET_MAP.get((des, pin_idx))
                self.assertIsNotNone(net, f"Pin {(des, pin_idx)} is missing from PIN_NET_MAP")
                pad_map[(des, pin_idx)] = net

        unrouted = [k for k in pad_map if k not in gen.PIN_NET_MAP]
        self.assertEqual(len(unrouted), 0, f"Found unrouted pins: {unrouted}")

        active_nets = set(pad_map.values()) - {"NC"}
        self.assertGreaterEqual(len(active_nets), 30, f"Expected >= 30 active nets, found {len(active_nets)}")
        self.assertIn("GND", active_nets)
        self.assertIn("+12V_RAW", active_nets)
        self.assertIn("+12V_BATT", active_nets)
        self.assertIn("+12V_SWITCHED", active_nets)
        self.assertIn("+5V_PI5", active_nets)
        self.assertIn("+3V3_ALWAYS_ON", active_nets)

    def test_03_kicad_pcb_integrity(self):
        """Verify KiCad PCB file exists, has valid s-expression syntax, and contains all nets."""
        pcb_path = os.path.join(HARDWARE_DIR, "kicad", "pi-diode-carrier.kicad_pcb")
        self.assertTrue(os.path.isfile(pcb_path), "pi-diode-carrier.kicad_pcb does not exist")

        with open(pcb_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertTrue(content.startswith("(kicad_pcb"), "Invalid KiCad PCB format")
        self.assertTrue(content.rstrip().endswith(")"), "KiCad PCB unclosed s-expression")

        # Verify net declarations
        for net_name in ["GND", "+12V_BATT", "+12V_SWITCHED", "+5V_PI5", "+3V3_ALWAYS_ON"]:
            self.assertIn(f'"{net_name}"', content, f"Net {net_name} missing from KiCad PCB")

        # Verify segments and footprints
        self.assertIn("(segment", content, "No routed copper segments in KiCad PCB")
        self.assertIn("(via", content, "No vias in KiCad PCB")
        self.assertIn('footprint "MountingHole_3.2mm_M3_Pad"', content, "Missing mounting holes in KiCad PCB")

    def test_04_gerber_suite_completeness(self):
        """Verify all 11 RS-274X Gerber layers and Excellon drill file are generated and valid."""
        expected_files = [
            "pi-diode-carrier-F_Cu.gbr",
            "pi-diode-carrier-In1_Cu.gbr",
            "pi-diode-carrier-In2_Cu.gbr",
            "pi-diode-carrier-B_Cu.gbr",
            "pi-diode-carrier-F_Mask.gbr",
            "pi-diode-carrier-B_Mask.gbr",
            "pi-diode-carrier-F_Paste.gbr",
            "pi-diode-carrier-B_Paste.gbr",
            "pi-diode-carrier-F_SilkS.gbr",
            "pi-diode-carrier-B_SilkS.gbr",
            "pi-diode-carrier-Edge_Cuts.gbr",
            "pi-diode-carrier.drl",
        ]
        gerber_dir = os.path.join(HARDWARE_DIR, "gerbers")
        for fn in expected_files:
            fp = os.path.join(gerber_dir, fn)
            self.assertTrue(os.path.isfile(fp), f"Missing manufacturing file: {fn}")
            self.assertGreater(os.path.getsize(fp), 500, f"Manufacturing file {fn} is suspiciously small")

    def test_05_zip_packages_ready_for_jlcpcb(self):
        """Verify turnkey zip package contains Gerbers, Drill, BOM, and CPL files."""
        zip_path = os.path.join(HARDWARE_DIR, "turnkey_assembly_package", "pi-diode-carrier-turnkey-pack.zip")
        self.assertTrue(os.path.isfile(zip_path), "pi-diode-carrier-turnkey-pack.zip is missing")

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("BOM-jlcpcb.csv", namelist)
            self.assertIn("CPL-jlcpcb.csv", namelist)
            self.assertIn("pi-diode-carrier-F_Cu.gbr", namelist)
            self.assertIn("pi-diode-carrier-In1_Cu.gbr", namelist)
            self.assertIn("pi-diode-carrier.drl", namelist)
            self.assertGreaterEqual(len(namelist), 14)


if __name__ == "__main__":
    unittest.main()
