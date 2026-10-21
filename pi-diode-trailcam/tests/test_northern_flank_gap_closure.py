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
        """Verify Initiative #4 FIN-SIG-LIB v1.0 -30 C 5-class signature library (Gap A: 2/4 -> 3/4)."""
        sig = gap_solver.evaluate_nordic_winter_signature_library()
        self.assertAlmostEqual(sig.speed_of_sound_mps, 312.58, delta=0.1)
        self.assertGreaterEqual(sig.decoy_vs_threat_accuracy, 0.95)
        self.assertLessEqual(sig.node_to_c2_latency_s, 2.0)

    def test_02_corridor_non_rf_sensing_belt(self):
        """Verify Initiative #7 [P12-BELT] non-RF rotorcraft corridor & substation belt (Gap J: 1/4 -> 2/4 ceiling)."""
        fpv = gap_solver.evaluate_border_counter_fpv_belt()
        self.assertGreaterEqual(fpv.corridor_detection_range_m, 500.0)
        self.assertGreaterEqual(fpv.zero_rf_fpv_detection_prob, 0.90)
        self.assertLessEqual(fpv.passive_net_trigger_ms, 150.0)

    def test_03_fin_lab_06_coastal_seabed_usv(self):
        """Verify Initiative #12 FIN-LAB-06 [P12-USV] 100% China-free coastal USV (Gap K: 2/4 -> 3/4)."""
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


if __name__ == "__main__":
    unittest.main()
