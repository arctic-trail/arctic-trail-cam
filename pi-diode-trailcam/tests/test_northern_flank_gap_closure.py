#!/usr/bin/env python3
"""
Unit tests for Northern-Flank Low-Cost 100% Non-Chinese COTS Gap-Closure Enablers
in `arctic-trail-cam` (`FIN-SIG-LIB v1.0` `#4`, `[P12-BELT]` `#7`, and `FIN-LAB-06` `[P12-USV]` `#12`).
"""

import os
import sys
import unittest

PI5_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pi5_sender_node",
)
if PI5_DIR not in sys.path:
    sys.path.insert(0, PI5_DIR)

import northern_flank_red_gap_solver as gap_solver  # noqa: E402


class TestNorthernFlankGapClosureInTrailCam(unittest.TestCase):
    def test_01_fin_sig_lib_v1_acoustic_and_micro_doppler(self):
        """Verify Initiative #4 FIN-SIG-LIB v1.0 -30 C 5-class signature library & 200-sample winter dataset."""
        ds = gap_solver.generate_fin_sig_lib_v1_winter_dataset(samples_per_class=40, temp_c=-30.0)
        self.assertEqual(ds["total_samples"], 200)
        self.assertEqual(len(ds["prototypes"]), 5)
        self.assertGreaterEqual(ds["overall_5class_accuracy"], 0.95)
        self.assertGreaterEqual(ds["clutter_vs_aircraft_accuracy"], 0.95)
        sig = gap_solver.evaluate_nordic_winter_signature_library()
        self.assertAlmostEqual(sig.speed_of_sound_mps, 312.58, delta=0.1)
        self.assertGreaterEqual(sig.clutter_vs_aircraft_accuracy, 0.95)
        self.assertLessEqual(sig.node_to_c2_latency_s, 2.0)

    def test_02_corridor_non_rf_sensing_belt(self):
        """Verify Initiative #7 [P12-BELT] non-RF rotorcraft corridor & substation belt (Gap J: 1/4 -> 2/4 ceiling)."""
        sim = gap_solver.simulate_p12_belt_non_rf_rotorcraft_detection()
        self.assertEqual(sim["target_rf_emissions_w"], 0.0)
        self.assertGreaterEqual(sim["corridor_detection_range_m"], 550.0)
        self.assertGreaterEqual(sim["warning_lead_time_at_18_5mps_s"], 28.0)
        fpv = gap_solver.evaluate_corridor_non_rf_sensing_belt()
        self.assertGreaterEqual(fpv.corridor_detection_range_m, 500.0)
        self.assertGreaterEqual(fpv.zero_rf_rotorcraft_detection_prob, 0.90)
        self.assertLessEqual(fpv.passive_net_trigger_ms, 150.0)

    def test_03_fin_lab_06_coastal_seabed_usv(self):
        """Verify Initiative #12 FIN-LAB-06 [P12-USV] 100% China-free coastal USV (Gap K: 2/4 -> 3/4)."""
        sim = gap_solver.simulate_finlab06_coastal_cable_usv_mission()
        self.assertLessEqual(sim["rm3100_cable_tracking_cep_m"], 0.50)
        self.assertEqual(sim["optical_shore_handoff_rf_w"], 0.0)
        usv = gap_solver.evaluate_finlab06_coastal_usv()
        self.assertGreaterEqual(usv.fleet_availability_pct, 80.0)
        self.assertGreaterEqual(usv.endurance_hours, 30.0)
        self.assertTrue(usv.china_free_verified)

    def test_04_northern_flank_scorecard_lift(self):
        """Verify overall scorecard lifts from 54.2% (52/96) to 72.9% (70/96) in code/CAD today."""
        sc = gap_solver.compute_northern_flank_scorecard_progression()
        self.assertEqual(sc["cots_solved_now_pts"], 70)
        self.assertAlmostEqual(sc["cots_solved_now_pct"], 72.9, delta=0.2)
        self.assertEqual(sc["red_residual_cots_solved_now"], 14)
        self.assertEqual(sc["areas_at_3plus_now"], 11)
        apn = gap_solver.simulate_3d_apn_optical_rendezvous_and_soft_capture()
        self.assertLessEqual(apn.terminal_miss_distance_m, 0.85)
        self.assertTrue(apn.zero_firearms_zero_pyrotechnics)
        self.assertTrue(apn.captured_safely_without_lipo_puncture)


if __name__ == "__main__":
    unittest.main()
