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

    def test_05_urban_border_corridor_profile(self):
        """Verify [P12-URBAN] 65 dBA city/bridge profile with UPS power, 100 Hz comb notch & ESC PWM filtering."""
        urban = gap_solver.evaluate_urban_border_corridor_profile()
        self.assertEqual(urban.ambient_traffic_dba, 65.0)
        self.assertEqual(urban.substation_100hz_hum_dba, 72.0)
        self.assertEqual(urban.comb_notch_100hz_harmonics_count, 8)
        self.assertGreaterEqual(urban.comb_notch_attenuation_db, 40.0)
        self.assertLessEqual(urban.highband_8_16khz_residual_dba, 20.0)
        self.assertGreaterEqual(urban.blackout_ups_autonomy_hours, 72.0)
        self.assertEqual(urban.radar_azimuth_baffle_deg, 60.0)
        self.assertGreaterEqual(urban.radar_parallel_traffic_rejection_pct, 99.0)
        self.assertGreaterEqual(urban.urban_zero_rf_rotorcraft_range_m, 320.0)
        self.assertGreaterEqual(urban.urban_detection_prob, 0.90)
        self.assertTrue(urban.china_free_verified)

    def test_06_finlab06b_offshore_wave_piercing_usv(self):
        """Verify FIN-LAB-06B [P12-USV-HEAVY] 3.60 m Sea State 5 hydrostatics, Froude & Polar Night DMFC USV."""
        usv_b = gap_solver.evaluate_finlab06b_offshore_wave_piercing_usv()
        self.assertEqual(usv_b.hull_length_m, 3.60)
        self.assertLess(usv_b.froude_number_at_patrol, 0.45)
        self.assertGreaterEqual(usv_b.metacentric_height_gm_m, 0.25)
        self.assertLess(usv_b.inverted_metacentric_gm_180deg_m, 0.0)
        self.assertEqual(usv_b.angle_of_vanishing_stability_deg, 180.0)
        self.assertEqual(usv_b.max_sea_state, 5)
        self.assertLessEqual(usv_b.self_righting_180deg_time_s, 4.0)
        self.assertGreaterEqual(usv_b.polar_night_endurance_hours, 140.0)
        self.assertGreaterEqual(usv_b.sea_state_5_endurance_hours, 100.0)
        self.assertLess(usv_b.dmfc_subwaterline_condensate_port_depth_m, -0.15)
        self.assertGreaterEqual(usv_b.fleet_availability_pct, 90.0)
        self.assertTrue(usv_b.china_free_verified)

    def test_07_archipelago_2km_optical_strait_bridge(self):
        """Verify [P11-COAST-2KM] IEC 60825-1 Class 1 eye-safe gimbal-free 1-2 km 1550 nm strait bridge."""
        bridge = gap_solver.evaluate_archipelago_2km_optical_strait_bridge()
        self.assertEqual(bridge.rf_emissions_w, 0.0)
        self.assertEqual(bridge.moving_gimbal_parts, 0)
        self.assertLessEqual(bridge.exit_irradiance_mw_cm2, 10.0)
        self.assertTrue(bridge.iec_60825_class1_eye_safe)
        self.assertLessEqual(bridge.pointing_loss_at_1_5mrad_sway_db, 1.5)
        self.assertGreaterEqual(bridge.snr_clear_10mbps_at_1km_db, 20.0)
        self.assertGreaterEqual(bridge.snr_clear_10mbps_at_2km_db, 14.0)
        self.assertGreaterEqual(bridge.snr_heavy_fog_vk7mo_at_1_5km_db, 12.0)
        self.assertTrue(bridge.china_free_verified)

    def test_08_svalbard_permafrost_cairn_node(self):
        """Verify [P21-SVALBARD] treeless permafrost basalt-cairn thermal shell & 120-day Polar Night endurance."""
        sv = gap_solver.evaluate_svalbard_permafrost_cairn_node()
        self.assertEqual(sv.outside_air_temp_c, -35.0)
        self.assertGreaterEqual(sv.internal_vault_temp_c, -18.0)
        self.assertGreaterEqual(sv.thermal_resistance_k_per_w, 9.5)
        self.assertGreaterEqual(sv.thermal_time_constant_hours, 72.0)
        self.assertLessEqual(sv.supercap_cold_crank_droop_v, 0.25)
        self.assertEqual(sv.polar_night_days, 120)
        self.assertGreaterEqual(sv.total_battery_endurance_years, 2.0)
        self.assertEqual(sv.rf_emissions_w, 0.0)
        self.assertTrue(sv.svalbard_treaty_art9_compliant)
        self.assertTrue(sv.china_free_verified)

    def test_09_finlab02_ram_drag_and_speed_bounds(self):
        """Verify FIN-LAB-02 high-speed airframe includes intake ram drag (91.3 N @ 400 km/h, +40.7 N excess)."""
        f02 = gap_solver.evaluate_finlab02_high_speed_airframe()
        self.assertAlmostEqual(f02.drag_at_400kmh_n, 91.3, delta=0.5)
        self.assertAlmostEqual(f02.excess_thrust_at_400kmh_n, 40.7, delta=0.5)
        self.assertGreaterEqual(f02.max_level_speed_kmh, 450.0)
        self.assertLess(f02.max_level_speed_kmh, 520.0)
        self.assertTrue(f02.china_free_verified)

    def test_10_extreme_urban_noise_stress_test(self):
        """Verify [P12-URBAN] degrades gracefully under extreme 70 dBA bridge traffic & 80 dBA transformer hum."""
        urban_stress = gap_solver.evaluate_urban_border_corridor_profile(
            ambient_traffic_dba=70.0,
            substation_100hz_hum_dba=80.0,
        )
        self.assertLessEqual(urban_stress.highband_8_16khz_residual_dba, 25.0)
        self.assertGreaterEqual(urban_stress.urban_zero_rf_rotorcraft_range_m, 240.0)

    def test_11_optical_bridge_severe_post_sway_stress(self):
        """Verify [P11-COAST-2KM] maintains >=12 dB SNR at 2 km even under 2.5 mrad gale post deflection."""
        bridge_gale = gap_solver.evaluate_archipelago_2km_optical_strait_bridge(
            post_sway_mrad=2.5,
        )
        self.assertTrue(bridge_gale.iec_60825_class1_eye_safe)
        self.assertGreaterEqual(bridge_gale.snr_clear_10mbps_at_2km_db, 12.0)

    def test_12_heated_shelter_and_corridor_geometry(self):
        """Verify Benchmark H heated shelter & Benchmark I 3-gate head-on geometry."""
        climber = gap_solver.evaluate_heated_nest_and_fast_climber()
        geom = gap_solver.compute_corridor_rendezvous_geometry_timeline()
        self.assertLessEqual(climber.nest_lid_open_s, 10.0)
        self.assertGreaterEqual(geom.cumulative_id_prob_three_gates, 0.85)
        self.assertLess(geom.t_gate1_rendezvous_s, geom.t_uncurbed_arrival_s)

    def test_13_100pct_civilian_quick_wins(self):
        """Verify $24-$55 COTS quick wins closing Narva, Baltic & Svalbard to 100% civilian ceiling."""
        qw = gap_solver.evaluate_100pct_civilian_quick_wins()
        self.assertGreaterEqual(qw.narva_laser_dazzle_od_blocking, 6.0)
        self.assertLessEqual(qw.narva_pio_otdr_fiber_cut_precision_m, 1.5)
        self.assertEqual(qw.narva_civilian_coverage_pct, 100.0)
        self.assertGreaterEqual(qw.baltic_hydrophone_diver_anchor_range_m, 500.0)
        self.assertEqual(qw.baltic_civilian_coverage_pct, 100.0)
        self.assertGreaterEqual(qw.svalbard_auroral_gradiometer_rejection_db, 40.0)
        self.assertGreater(qw.svalbard_katabatic_wind_harvester_wh_per_day, qw.svalbard_node_draw_wh_per_day * 50)
        self.assertEqual(qw.svalbard_civilian_coverage_pct, 100.0)
        self.assertTrue(qw.all_three_scenarios_100pct_civilian_ceiling)
        self.assertTrue(qw.china_free_verified)

    def test_14_charter_6gap_cots_cost_performance_and_real_data_revalidation(self):
        """Verify Charter 6-Gap (J, A, H, I, K, L) COTS cost-performance gates & real-data signature re-validation."""
        reval = gap_solver.recalibrate_fin_sig_lib_on_real_trial_data()
        self.assertEqual(reval["evidence_tier"], "REAL_HARDWARE_TRIAL_REVALIDATED_4_OF_4")
        self.assertGreaterEqual(reval["real_trial_samples_ingested"], 5)
        self.assertGreaterEqual(reval["overall_5class_accuracy"], 0.95)
        self.assertGreaterEqual(reval["clutter_vs_aircraft_accuracy"], 0.95)

        charter = gap_solver.evaluate_charter_cots_cost_performance_and_trial_gates()
        self.assertTrue(charter["charter_scope_90_10_civilian_compliant"])
        self.assertTrue(charter["sovereign_11_points_excluded"])
        self.assertTrue(charter["all_6_charter_gaps_exit_criteria_met"])
        self.assertEqual(charter["honest_score_today_pts"], 56)
        self.assertEqual(charter["charter_6_gaps_points_gained"], 19)
        self.assertEqual(charter["green_enablers_gate2_3_points"], 10)
        self.assertEqual(charter["civilian_ceiling_pts"], 85)
        self.assertAlmostEqual(charter["civilian_ceiling_pct"], 88.5, places=1)
        self.assertLessEqual(
            charter["cost_performance_summary"]["arctic_trail_cots_surrogate_validation_usd"],
            1000.0,
        )
        self.assertGreaterEqual(
            charter["cost_performance_summary"]["cost_reduction_factor_vs_charter_min"],
            8000.0,
        )


if __name__ == "__main__":
    unittest.main()
