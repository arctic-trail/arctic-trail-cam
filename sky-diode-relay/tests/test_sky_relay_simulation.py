#!/usr/bin/env python3
"""
Test Suite: End-to-End Simulation & Finnish Climate Qualification of Sky-Diode-Relay
Validates:
1. Self-Consistent Cloud-Bounce Geometry & Beer-Lambert Extinction.
2. 8-PPM Symbol Encoding, Pulse Formatting & Demodulation.
3. End-to-End Jittered Transmission.
4. Asynchronous Preamble Lock under Pre-Burst Noise & Dropped Pulses.
5. Bit-Interleaved Extended Hamming(8,4) SECDED + Erasure FEC Repair.
6. CRC32 Data Integrity & Uncoded Corruption Rejection.
7. Ed25519 Signed Camera Alert Bridge & Collector Hub Handoff.
8. Continuous Midnight-Sun Background Stream Acquisition (>500 pre-burst noise pulses).
9. Worst-Case 3-Bit (`0b111`) Symbol Erasure, Length-Header Corruption & 12-Symbol Burst Fade Repair.
10. Finnish Winter -30°C Crystal Clock Skew (+/-200 ppm) Recovery via Decision-Directed DLL.
11. Winter Snowflake Beam Occultation & Multi-Pass Carousel Erasure Combining.
12. RP2040 PIO Hardware FIFO Word Packing, TDC Unpacking & Duty-Cycle Safety Interlock.
13. Finnish Climate Multi-Regime Physics (Etendue A*Omega, Polar Night, Snow, Fog, Thermal Drift).
"""
import sys
import os
import math
import random

# Add transmitter and receiver paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../transmitter")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../receiver")))

from sky_transmitter import (
    encode_bytes_to_8ppm,
    create_sky_frame,
    format_ppm_pulse_train,
    transmit_simulated_burst,
    transmit_carousel_bursts,
    create_signed_sky_alert,
    pack_pio_timing_words,
    unpack_pio_timing_words,
    package_udp_datagrams_for_optical,
    compute_sky_relay_energy_budget,
    derive_fhss_carrier_schedule,
    encode_vk7mo_lockin_frame,
    calculate_troposcatter_link_budget,
)
from sky_receiver import (
    decode_8ppm_symbols_to_bytes,
    demodulate_pulse_train,
    parse_sky_frame,
    process_incoming_pulse_stream,
    verify_signed_sky_alert,
    unpack_pio_rx_timestamps,
    forward_verified_sky_alert,
    reassemble_udp_datagrams_from_optical,
    simulate_physical_detector_channel,
    evaluate_link_health_diagnostics,
    simulate_vk7mo_scatter_channel,
    demodulate_vk7mo_lockin_stream,
)


def compute_self_consistent_link_budget(H_c, theta_1_deg, theta_2_deg, alpha_ext_per_m=1.2e-4):
    """
    Computes a physically self-consistent cloud-bounce optical link budget:
      D   = H_c / tan(theta_1) + H_c / tan(theta_2)
      R_1 = H_c / sin(theta_1)
      R_2 = H_c / sin(theta_2)
      T_atm = exp(-alpha_ext * (R_1 + R_2))
    """
    P_tx = 75.0          # Watts peak optical pulse power
    pulse_width = 50e-9  # 50 ns pulse
    theta_1 = math.radians(theta_1_deg)
    theta_2 = math.radians(theta_2_deg)

    baseline_m = (H_c / math.tan(theta_1)) + (H_c / math.tan(theta_2))
    R_1 = H_c / math.sin(theta_1)
    R_2 = H_c / math.sin(theta_2)
    T_atm = math.exp(-alpha_ext_per_m * (R_1 + R_2))

    A_rx = math.pi * (0.10 ** 2)  # 200mm diameter collector aperture
    rho_cloud = 0.75              # Cloud base diffuse reflectance
    eta_total = 0.50              # TX * RX * bandpass filter optical efficiency

    geom_loss = (A_rx * math.cos(theta_2)) / (math.pi * (R_2 ** 2))
    P_rx = P_tx * eta_total * rho_cloud * geom_loss * T_atm
    pulse_energy_rx = P_rx * pulse_width

    h = 6.626e-34
    c = 3.0e8
    lambda_m = 1.55e-6
    E_photon = (h * c) / lambda_m
    photons_per_pulse = pulse_energy_rx / E_photon
    return {
        "baseline_m": baseline_m,
        "R_1": R_1,
        "R_2": R_2,
        "T_atm": T_atm,
        "P_rx_nw": P_rx * 1e9,
        "photons_per_pulse": photons_per_pulse,
    }


def evaluate_finnish_climate_link_modes(
    temp_c=-20.0,
    visibility_km=10.0,
    rain_mm_hr=0.0,
    snow_visibility_km=None,
    cloud_reflectance=0.0,
    cloud_height_shift_m=0.0,
    solar_irradiance_w_m2=0.0,
    use_dfb_laser=True,
):
    """
    Evaluates the three optical link architectures under realistic Finnish seasonal conditions:
      1. 1550 nm Cloud-Bounce NLOS (shows Lagrange etendue FOV loss, clear-sky outage, and thermal drift)
      2. 1550 nm Collimated FSO / Treetop Relay (1.0 km range, Thorlabs F280FC + APD430C InGaAs APD)
      3. 265 nm Solar-Blind UV-C Over-the-Trees NLOS Scatter (150 m range, 4-pulse integration + R7154 PMT)
    """
    # 1. Thermal wavelength shift relative to +25C nominal calibration
    delta_t = temp_c - 25.0
    drift_nm = delta_t * (0.08 if use_dfb_laser else 0.50)
    filter_half_bw_nm = 6.0 if use_dfb_laser else 5.0  # 12nm DFB filter vs 10nm narrow filter on uncooled FP
    filter_pass = 1.0 if abs(drift_nm) <= filter_half_bw_nm else 0.0

    # 2. Atmospheric extinction coefficient (dB/km -> per meter)
    # Kruse/Kim visibility model at 1550 nm + Carbonneau rain + Nordic snow
    q_vis = 1.3 if visibility_km >= 6.0 else (0.16 * visibility_km + 0.34 if visibility_km >= 1.0 else 0.0)
    gamma_haze_1550_db_km = (17.0 / max(visibility_km, 0.05)) * ((1.55 / 0.55) ** (-q_vis))
    gamma_rain_db_km = 1.076 * (rain_mm_hr ** 0.67) if rain_mm_hr > 0 else 0.0
    gamma_snow_db_km = (14.0 / snow_visibility_km) if snow_visibility_km else 0.0
    total_1550_db_km = gamma_haze_1550_db_km + gamma_rain_db_km + gamma_snow_db_km
    alpha_1550_per_m = (total_1550_db_km / 1000.0) * (math.log(10.0) / 10.0)

    # Mode A: 1550 nm Cloud-Bounce at 1847.5 m (H_c=800m, 200mm lens f=200mm, 200um InGaAs APD -> FOV=1 mrad)
    fov_spot_radius_m = 1600.0 * (0.0002 / 0.200) * 0.5  # ~0.8 m radius on cloud
    beam_spot_radius_m = 923.8 * 0.002  # 2 mrad beam -> ~1.85 m radius
    overlap_ok = 1.0 if abs(cloud_height_shift_m) <= (fov_spot_radius_m + beam_spot_radius_m) else 0.0
    cb_base = compute_self_consistent_link_budget(800.0, 60.0, 30.0, alpha_ext_per_m=alpha_1550_per_m)
    cb_photons = cb_base["photons_per_pulse"] * (cloud_reflectance / 0.75) * overlap_ok * filter_pass

    # Mode B: 1550 nm Line-of-Sight / Treetop Mirror FSO at R = 1000 m
    # Eye-safe Class 1 40 mW peak (200 ns pulse), 2 mrad divergence (2.0 m spot @ 1 km), 50 mm RX lens
    R_fso = 1000.0
    P_tx_fso = 0.040
    t_pulse_fso = 200e-9
    spot_area_fso = math.pi * ((R_fso * 0.001) ** 2)
    rx_area_fso = math.pi * (0.025 ** 2)
    T_atm_fso = math.exp(-alpha_1550_per_m * R_fso)
    P_rx_fso = P_tx_fso * 0.55 * min(1.0, rx_area_fso / spot_area_fso) * T_atm_fso * filter_pass
    # InGaAs APD (NEP = 0.25 pW/sqrt(Hz) @ 5 MHz + solar background through 4:1 sun baffle)
    nep_noise_w = 0.25e-12 * math.sqrt(5e6)
    solar_bg_w = solar_irradiance_w_m2 * 1e-7 * rx_area_fso
    noise_floor_w = math.sqrt(nep_noise_w ** 2 + (solar_bg_w * 0.1) ** 2)
    fso_snr_db = 10.0 * math.log10(max(P_rx_fso, 1e-15) / noise_floor_w)

    # Mode C: 265 nm Solar-Blind UV-C Over-the-Trees NLOS Scatter at R = 150 m (H_scatter = 25 m)
    # Works in clear sky (Rayleigh molecular scatter) AND mist/snow (enhanced Mie scatter), 0 solar background!
    R_uvc = 150.0
    beta_rayleigh_per_m = 2.4e-4  # Molecular Rayleigh scatter at 265 nm
    beta_mie_per_m = min(2.5e-3, 1.8e-3 / max(visibility_km, 0.2))
    beta_total_scatter = beta_rayleigh_per_m + (0.40 * beta_mie_per_m)
    alpha_uvc_per_m = 7.5e-4 + (1.2e-3 / max(visibility_km, 0.2))
    P_tx_uvc = 1.200  # 1.2 W pulsed 265 nm UV-C LED array (12x 100 mW Nichia NCSU434C)
    t_pulse_uvc = 2.0e-6  # 2.0 us sub-pulse inside 20 us UV-C chip
    pulses_per_sym = 4
    A_rx_pmt = math.pi * (0.025 ** 2)  # 50 mm UV fused-silica condenser onto Hamamatsu R7154 192 mm^2 PMT
    T_atm_uvc = math.exp(-alpha_uvc_per_m * R_uvc)
    scatter_vol_eff = (beta_total_scatter * 35.0) * (A_rx_pmt / (4.0 * math.pi * ((R_uvc * 0.55) ** 2)))
    E_rx_uvc_sym = P_tx_uvc * t_pulse_uvc * pulses_per_sym * 0.35 * scatter_vol_eff * T_atm_uvc
    E_photon_uvc = (6.626e-34 * 3.0e8) / 265e-9
    uvc_detected_photoelectrons = (E_rx_uvc_sym / E_photon_uvc) * 0.25  # 25% Cs-Te PMT quantum efficiency

    return {
        "temp_c": temp_c,
        "laser_drift_nm": round(drift_nm, 2),
        "filter_pass": filter_pass,
        "loss_1550_db_km": round(total_1550_db_km, 2),
        "cloud_bounce_photons": round(cb_photons, 1),
        "fso_1km_snr_db": round(fso_snr_db, 1),
        "uvc_150m_photoelectrons_per_sym": round(uvc_detected_photoelectrons, 1),
    }


def test_link_budget_math():
    print("[*] 1. Validating Self-Consistent Atmospheric Link Budget & Geometry...")
    # Case A: H_c = 800m, theta_1 = 60 deg, theta_2 = 30 deg -> exact baseline is 1847.52 m
    case_a = compute_self_consistent_link_budget(800.0, 60.0, 30.0)
    assert abs(case_a["baseline_m"] - 1847.52) < 1.0, f"Expected 1847.5m baseline, got {case_a['baseline_m']:.2f}m"
    print(
        f"    - Case A (H_c=800m, 60°/30°): Exact Baseline = {case_a['baseline_m']:.1f} m | "
        f"T_atm = {case_a['T_atm']:.2f} | Photons/Pulse = {case_a['photons_per_pulse']:.0f}"
    )

    # Case B: True 5.0 km (5000 m) baseline at H_c = 1000m (theta_1 = 21.801°, theta_2 = 21.801°)
    theta_5km = math.degrees(math.atan(1000.0 / 2500.0))
    case_b = compute_self_consistent_link_budget(1000.0, theta_5km, theta_5km)
    assert abs(case_b["baseline_m"] - 5000.0) < 1.0
    print(
        f"    - Case B (H_c=1000m, {theta_5km:.1f}°/{theta_5km:.1f}°): Exact Baseline = {case_b['baseline_m']:.1f} m | "
        f"T_atm = {case_b['T_atm']:.2f} | Photons/Pulse = {case_b['photons_per_pulse']:.0f}"
    )

    assert case_a["photons_per_pulse"] > 5000 and case_b["photons_per_pulse"] > 500
    print("    [+] Self-Consistent Link Budget & Beer-Lambert Extinction: PASSED")


def test_8ppm_codec_roundtrip():
    print("[*] 2. Validating 8-PPM Symbol Codec Round-Trip...")
    test_payload = b"Hello Atmospheric Sky Diode Relay! 2026-Boreal"
    symbols = encode_bytes_to_8ppm(test_payload)
    reconstructed = decode_8ppm_symbols_to_bytes(symbols)

    assert len(symbols) == len(test_payload) * 3, "Each byte must yield exactly 3 8-PPM symbols"
    assert reconstructed == test_payload, "Decoded bytes must exactly match input payload"
    print(f"    - Encoded {len(test_payload)} bytes into {len(symbols)} 8-PPM symbols")
    print("    [+] 8-PPM Codec Round-Trip: PASSED")


def test_end_to_end_transmission_with_jitter():
    print("[*] 3. Validating End-to-End Packet Transmission with Channel Jitter...")
    original_data = b'{"node":"NODE-NORTH-01","alert":"PERSON_VERIFIED","ts":1760380000,"conf":0.94}'

    tx_meta = transmit_simulated_burst(original_data)
    pulse_train = tx_meta["pulse_train_us"]

    random.seed(42)
    jittered_pulses = [t + random.uniform(-0.15, 0.15) for t in pulse_train]

    rx_result = process_incoming_pulse_stream(jittered_pulses)

    assert rx_result["status"] == "OK", f"Receiver failed: {rx_result['status']}"
    assert rx_result["payload"] == original_data, "Payload mismatch after jittered channel transmission"
    print(f"    - Frame Size: {tx_meta['frame_len']} B | Symbols: {tx_meta['symbol_count']}")
    print("    [+] End-to-End Jittered Transmission: PASSED (100% Fidelity)")


def test_async_preamble_lock_with_background_noise_and_dropped_pulses():
    print("[*] 4. Validating Asynchronous Preamble Lock under Pre-Burst Noise & Dropped Pulses...")
    original_data = b'{"node":"NODE-NORTH-01","event":"ASYNC_LOCK_OK"}'
    tx_meta = transmit_simulated_burst(original_data, enable_fec=True)

    # Shift entire burst to start at T0 = +412.7 us, prepend 7 random dark-count noise pulses,
    # and drop 3 of the 16 preamble pulses!
    t_offset = 412.7
    shifted = [t + t_offset for t in tx_meta["pulse_train_us"]]
    del shifted[12]
    del shifted[5]
    del shifted[0]
    pre_noise = [14.2, 58.9, 103.1, 179.4, 244.0, 311.8, 389.5]
    noisy_stream = pre_noise + shifted

    rx_result = process_incoming_pulse_stream(noisy_stream)
    assert rx_result["status"] == "OK", f"Async acquisition failed: {rx_result['status']}"
    assert rx_result["payload"] == original_data
    print("    - Recovered T0 lock across 7 pre-burst noise pulses and 3 dropped preamble pulses")
    print("    [+] Asynchronous Preamble Acquisition: PASSED")


def test_fec_symbol_error_and_erasure_repair():
    print("[*] 5. Validating Bit-Interleaved Extended Hamming(8,4) FEC Symbol Corruption & Erasure Repair...")
    original_data = b'{"node":"NODE-NORTH-01","fec":"REPAIRED"}'
    tx_meta = transmit_simulated_burst(original_data, enable_fec=True)
    pulses = list(tx_meta["pulse_train_us"])

    # Shift one data pulse by +1 chip (+2.0 us -> 1-bit error) and drop another data pulse completely!
    pulses[35] += 2.0
    del pulses[48]

    rx_result = process_incoming_pulse_stream(pulses)
    assert rx_result["status"] == "OK", f"FEC repair failed: {rx_result['status']}"
    assert rx_result["payload"] == original_data
    print("    - Repaired 1 shifted symbol + 1 erased optical pulse via Bit-Interleaved Extended Hamming(8,4) FEC")
    print("    [+] FEC Symbol Corruption & Erasure Repair: PASSED")


def test_corrupt_packet_rejection():
    print("[*] 6. Validating CRC32 Data Integrity & Uncoded Corruption Rejection...")
    original_data = b'{"test":"safe"}'
    tx_meta = transmit_simulated_burst(original_data, enable_fec=False)
    pulses = list(tx_meta["pulse_train_us"])

    pulses[25] += 6.0  # Shift by 3 slots on non-FEC frame

    rx_result = process_incoming_pulse_stream(pulses)
    assert rx_result["status"] != "OK" or rx_result["payload"] is None, "Corrupted packet should be rejected"
    print(f"    - Corrupted Pulse Caught: {rx_result['status']}")
    print("    [+] CRC32 Corruption Rejection: PASSED")


def test_signed_camera_alert_bridge():
    print("[*] 7. Validating Ed25519 Signed Camera Alert Bridge Over 8-PPM Optical Channel...")
    from nacl.signing import SigningKey
    sk = SigningKey.generate()
    sk_hex = sk.encode().hex()
    vk_hex = sk.verify_key.encode().hex()

    camera_alert = {
        "node": "NODE-NORTH-01",
        "ts": 1760550000,
        "nonce": "a1b2c3d4e5f60718",
        "detections": [{"label": "person", "confidence": 0.93}],
        "pico_trig": "TRIG,MAG=85,SEIS=180,RADAR_M=4.2,UPTIME_S=1420",
        "img_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    }
    signed_payload = create_signed_sky_alert(camera_alert, sk_hex)
    tx_meta = transmit_simulated_burst(signed_payload, enable_fec=True)
    rx_result = process_incoming_pulse_stream(tx_meta["pulse_train_us"])
    assert rx_result["status"] == "OK"

    verified_alert, ok = verify_signed_sky_alert(rx_result["payload"], vk_hex)
    assert ok is True and verified_alert["node"] == "NODE-NORTH-01"
    assert verified_alert["nonce"] == "a1b2c3d4e5f60718"

    hub_rec, hub_ok = forward_verified_sky_alert(rx_result["payload"], vk_hex, send_udp=False)
    assert hub_ok is True and hub_rec["transport"] == "SKY_OPTICAL_8PPM"
    print("    [+] Ed25519 Signed Camera Alert Bridge & Collector Hub Handoff: PASSED")


def test_midnight_sun_continuous_background_acquisition():
    print("[*] 8. Validating Continuous Midnight-Sun Background Stream (>500 Pre-Burst Noise Pulses)...")
    original_data = b'{"node":"NODE-SAIMAA-02","season":"MIDSUMMER_24H_SUN"}'
    tx_meta = transmit_simulated_burst(original_data, enable_fec=True)

    # Generate 600 Poisson solar/dark background pulses before T0 = 150,000 us (150 ms)
    random.seed(2026)
    bg_pulses = sorted(random.uniform(10.0, 149500.0) for _ in range(600))
    t0_offset = 150000.0
    burst_pulses = [t + t0_offset for t in tx_meta["pulse_train_us"]]
    # Also drop first 4 preamble pulses!
    del burst_pulses[0:4]

    stream = bg_pulses + burst_pulses
    rx_result = process_incoming_pulse_stream(stream)
    assert rx_result["status"] == "OK", f"Failed after 600 background pulses: {rx_result['status']}"
    assert rx_result["payload"] == original_data
    print(f"    - Locked onto preamble at T0={t0_offset} us after 600 pre-burst background pulses & 4 dropped preamble teeth")
    print("    [+] Continuous Midnight-Sun Background Acquisition: PASSED")


def test_worst_case_3bit_erasure_and_burst_fade_repair():
    print("[*] 9. Validating Worst-Case 3-Bit (`0b111`) Erasure, Header Damage & 12-Symbol Burst Fade Repair...")
    # 0xFF bytes guarantee `s0 = 7 (0b111)` and `s1 = 7 (0b111)` symbols where erasing 1 pulse flips 3 bits at once!
    original_data = b"\xff\xff\xaa\x55" + b'{"node":"NODE-NORTH-01","burst_fade":"SURVIVED"}'
    tx_meta = transmit_simulated_burst(original_data, enable_fec=True)
    pulses = list(tx_meta["pulse_train_us"])

    # 1. Corrupt a pulse inside the FEC-encoded length header (data symbol index 14 -> pulse index 16 + 14 = 30)
    pulses[30] += 4.0
    # 2. Completely erase 12 consecutive data symbols in a row (pulses 60..71 = 192 us turbulence fade!)
    del pulses[60:72]

    rx_result = process_incoming_pulse_stream(pulses)
    assert rx_result["status"] == "OK", f"Burst fade repair failed: {rx_result['status']}"
    assert rx_result["payload"] == original_data
    print("    - Repaired corrupted length-header pulse + 12 consecutive erased 8-PPM symbols (192 us fade)")
    print("    [+] Worst-Case 3-Bit Symbol Erasure & Burst Fade Repair: PASSED")


def test_arctic_winter_crystal_clock_drift_dll_recovery():
    print("[*] 10. Validating -30°C Arctic Crystal Clock Skew (+/-200 ppm) Recovery via Decision-Directed DLL...")
    from nacl.signing import SigningKey
    sk = SigningKey.generate()
    signed_payload = create_signed_sky_alert(
        {"node": "NODE-LAPLAND-01", "ts": 1765000000, "nonce": "f0e1d2c3b4a59687", "detections": [{"label": "vehicle", "confidence": 0.97}]},
        sk.encode().hex(),
    )
    tx_meta = transmit_simulated_burst(signed_payload, enable_fec=True)

    # Apply +200 ppm clock stretch (at 22,000 us burst end, +200 ppm shifts pulses by +4.4 us = 2.2 full chip slots!)
    clock_scale = 1.0 + 200e-6
    drifted_pulses = [t * clock_scale + 1250.0 for t in tx_meta["pulse_train_us"]]

    rx_result = process_incoming_pulse_stream(drifted_pulses)
    assert rx_result["status"] == "OK", f"DLL clock recovery failed at +200 ppm: {rx_result['status']}"
    assert rx_result["payload"] == signed_payload
    print(f"    - Tracked +200 ppm crystal drift (+{tx_meta['pulse_train_us'][-1] * 200e-6:.2f} us cumulative shift) across {tx_meta['symbol_count']} symbols")
    print("    [+] Arctic -30°C Crystal Clock Drift DLL Recovery: PASSED")


def test_snowflake_beam_occultation_carousel_combining():
    print("[*] 11. Validating Winter Falling Snowflake Beam Occultation & 3-Pass Carousel Erasure Combining...")
    original_data = b'{"node":"NODE-NORTH-01","weather":"HEAVY_SNOWFALL_SAIMAA","temp_c":-14}'
    carousel_pulses = transmit_carousel_bursts(original_data, enable_fec=True, passes=2, inter_pass_gap_ms=35.0)

    # Pass 1 occupies roughly [0 .. 8100 us], Pass 2 occupies roughly [43100 .. 51200 us].
    # Simulate Giant Snowflake #1 blocking >50% of Pass 1 [1000 .. 5200 us] (262 symbols wiped out!)
    # and Giant Snowflake #2 blocking the complementary >50% of Pass 2 [45200 .. 51000 us].
    occulted_stream = [
        t for t in carousel_pulses
        if not (1000.0 <= t <= 5200.0) and not (45200.0 <= t <= 51000.0)
    ]

    rx_result = process_incoming_pulse_stream(occulted_stream)
    assert rx_result["status"] == "OK", f"Carousel snowflake combining failed: {rx_result['status']}"
    assert rx_result["payload"] == original_data
    assert rx_result.get("pass_used") == "CAROUSEL_COMBINED"
    print("    - Reconstructed 100% of frame by combining complementary snowflake-occulted passes")
    print("    [+] Winter Snowflake Beam Occultation Carousel Combining: PASSED")


def test_rp2040_pio_hardware_words_and_safety_interlock():
    print("[*] 12. Validating RP2040 PIO FIFO Timing Words, TDC Unpacker & Laser Safety Interlock...")
    original_data = b'{"pio":"HARDWARE_CYCLE_EXACT"}'
    tx_meta = transmit_simulated_burst(original_data, enable_fec=True)
    fifo_words = pack_pio_timing_words(tx_meta["pulse_train_us"], pulse_duration_ns=200)
    emitted_ts_us, width_ns = unpack_pio_timing_words(fifo_words)

    assert width_ns == 200.0
    max_err_us = max(abs(a - b) for a, b in zip(tx_meta["pulse_train_us"], emitted_ts_us))
    assert max_err_us < 1e-6, f"PIO timing drift {max_err_us} us"

    # Emulate receiver `pio_pulse_receiver.pio` 20ns TDC counter ticks
    rx_ticks = [int(round(t * 1000.0 / 20.0)) + 50000 for t in emitted_ts_us]
    rx_ts_us = unpack_pio_rx_timestamps(rx_ticks, tick_ns=20.0)
    rx_result = process_incoming_pulse_stream(rx_ts_us)
    assert rx_result["status"] == "OK" and rx_result["payload"] == original_data

    # Verify hardware safety interlock blocks unsafe >2.5% duty cycle bursts
    unsafe_blocked = False
    try:
        pack_pio_timing_words([0.0, 2.0, 4.0, 6.0], pulse_duration_ns=800, max_duty_cycle=0.025)
    except ValueError:
        unsafe_blocked = True
    assert unsafe_blocked is True, "Hardware duty-cycle safety interlock failed to block excessive duty cycle"
    print("    - Verified 0.0 ns cumulative PIO timing drift & blocked unsafe laser duty-cycle envelope")
    print("    [+] RP2040 PIO Hardware Timing & Safety Interlock: PASSED")


def test_finnish_climate_multi_regime_physics():
    print("[*] 13. Validating Finnish Climate Multi-Regime Physics (Polar Night, Midnight Sun, Snow & Etendue)...")
    # 1. Polar Night Clear Sky (-30C, no clouds): 1550nm cloud-bounce gets 0 photons, while 1550nm FSO & 265nm UV-C succeed!
    kaamos_clear = evaluate_finnish_climate_link_modes(
        temp_c=-30.0, visibility_km=30.0, cloud_reflectance=0.0, use_dfb_laser=True
    )
    assert kaamos_clear["cloud_bounce_photons"] == 0.0, "Clear starry night has 0 cloud bounce"
    assert kaamos_clear["fso_1km_snr_db"] > 20.0 and kaamos_clear["uvc_150m_photoelectrons_per_sym"] > 8.0

    # 2. Unstabilized Fabry-Perot 1550nm laser at -30C shifts by -27.5 nm and gets blocked by a 10nm filter
    kaamos_fp_blocked = evaluate_finnish_climate_link_modes(
        temp_c=-30.0, visibility_km=30.0, cloud_reflectance=0.75, use_dfb_laser=False
    )
    assert kaamos_fp_blocked["filter_pass"] == 0.0 and abs(kaamos_fp_blocked["laser_drift_nm"] - (-27.5)) < 0.1

    # 3. Cloud ceiling shift of +50m violates Lagrange etendue FOV overlap (0 photons for fixed narrow telescopes)
    cloud_shifted = evaluate_finnish_climate_link_modes(
        temp_c=-5.0, visibility_km=10.0, cloud_reflectance=0.75, cloud_height_shift_m=50.0, use_dfb_laser=True
    )
    assert cloud_shifted["cloud_bounce_photons"] == 0.0

    # 4. Midsummer 24h Sun (+25C, 800 W/m^2) + Winter Snowfall (-12C, V=1.2 km)
    midsummer = evaluate_finnish_climate_link_modes(
        temp_c=25.0, visibility_km=25.0, solar_irradiance_w_m2=800.0, use_dfb_laser=True
    )
    winter_snow = evaluate_finnish_climate_link_modes(
        temp_c=-12.0, visibility_km=10.0, snow_visibility_km=1.2, use_dfb_laser=True
    )
    assert midsummer["fso_1km_snr_db"] > 15.0 and midsummer["uvc_150m_photoelectrons_per_sym"] > 8.0
    assert winter_snow["fso_1km_snr_db"] > 12.0 and winter_snow["uvc_150m_photoelectrons_per_sym"] > 5.0
    print(
        f"    - Kaamos -30°C Clear Sky: CloudBounce={kaamos_clear['cloud_bounce_photons']} ph | "
        f"1km FSO SNR=+{kaamos_clear['fso_1km_snr_db']} dB | 150m UV-C NLOS={kaamos_clear['uvc_150m_photoelectrons_per_sym']} pe/sym"
    )
    print(
        f"    - Winter Snowfall (-12°C, V=1.2km): Loss={winter_snow['loss_1550_db_km']} dB/km | "
        f"1km FSO SNR=+{winter_snow['fso_1km_snr_db']} dB | 150m UV-C NLOS={winter_snow['uvc_150m_photoelectrons_per_sym']} pe/sym"
    )
    print("    [+] Finnish Climate Multi-Regime Physics & Etendue Verification: PASSED")


def test_physical_quantum_detector_channel():
    print("[*] 14. Validating Physical Quantum Detector Channel (Poisson Shot Noise, Dead Time & Background)...")
    original_data = b'{"node":"NODE-NORTH-01","detector":"APD430C_POISSON_DEADTIME_OK"}'
    tx_meta = transmit_simulated_burst(original_data, enable_fec=True)

    rx_pulses, stats = simulate_physical_detector_channel(
        tx_meta["pulse_train_us"],
        mean_signal_pe=14.0,
        threshold_pe=3,
        bg_dark_rate_hz=2500.0,
        dead_time_ns=400.0,
        clock_drift_ppm=-135.0,
        jitter_rms_ns=35.0,
        pre_window_us=45000.0,
        post_window_us=4000.0,
        seed=2026,
    )
    rx_result = process_incoming_pulse_stream(rx_pulses)
    assert rx_result["status"] == "OK", f"Quantum channel decode failed: {rx_result['status']}"
    assert rx_result["payload"] == original_data
    print(
        f"    - Decoded across {stats['background_pulses_injected']} Poisson bg counts, "
        f"{stats['deadtime_blinding_losses']} dead-time blindings & -135 ppm drift"
    )
    print("    [+] Physical Quantum Detector Channel Simulation: PASSED")


def test_end_to_end_trailcam_jpeg_optical_bridge_to_receiver_hub():
    print("[*] 15. Validating Full Trailcam DD01 + DD02 Target-Crop JPEG Optical Bridge into receiver_hub.py...")
    import hashlib
    import json
    import shutil
    import struct
    import tempfile
    from nacl.signing import SigningKey, VerifyKey

    hub_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../pi-diode-trailcam/collector_hub"))
    if hub_dir not in sys.path:
        sys.path.insert(0, hub_dir)
    import receiver_hub

    tmp_out = tempfile.mkdtemp(prefix="sky_hub_verify_")
    try:
        sk = SigningKey.generate()
        sk_hex = sk.encode().hex()
        vk = sk.verify_key

        # Configure receiver_hub state in isolated temporary directory
        old_out_dir = receiver_hub.OUT_DIR
        receiver_hub.OUT_DIR = tmp_out
        receiver_hub.KNOWN_NODE_PUBKEYS["NODE-SKY-FIN-01"] = vk

        # Create synthetic 1,500-byte JPEG target crop + signed DD\x01 + two DD\x02 chunks
        fake_jpeg = b"\xff\xd8\xff\xe0" + (b"BOREAL_INTRUDER_CROP_" * 70) + b"\xff\xd9"
        img_sha256 = hashlib.sha256(fake_jpeg).hexdigest()
        nonce_hex = "c0ffee2026f1a099"
        nonce_bytes = bytes.fromhex(nonce_hex)

        dd01_pkt = create_signed_sky_alert(
            {
                "node": "NODE-SKY-FIN-01",
                "ts": int(1760551234),
                "nonce": nonce_hex,
                "detections": [{"label": "person", "confidence": 0.96}],
                "pico_trig": "TRIG,MAG=92,SEIS=210,RADAR_M=3.8,UPTIME_S=8800",
                "img_sha256": img_sha256,
            },
            sk_hex,
        )
        chunks = [fake_jpeg[i:i + 1024] for i in range(0, len(fake_jpeg), 1024)]
        total_chunks = len(chunks)

        # Simulate sender_node.py emitting 3x redundant UDP carousel packets
        udp_stream_from_sender = []
        for _ in range(3):
            udp_stream_from_sender.append(dd01_pkt)
            for idx, ch in enumerate(chunks):
                hdr = b"DD\x02" + nonce_bytes + struct.pack(">HH", idx, total_chunks)
                udp_stream_from_sender.append(hdr + ch)

        # 1. Transmitter bridges UDP stream into fragmented SKFG/SKYF optical bursts
        optical_bursts = package_udp_datagrams_for_optical(
            udp_stream_from_sender, max_frag_bytes=360, enable_fec=True
        )

        # 2. Pass every optical burst through the physical quantum detector channel
        noisy_optical_streams = []
        for b_idx, burst in enumerate(optical_bursts):
            rx_pulses, _ = simulate_physical_detector_channel(
                burst["pulse_train_us"],
                mean_signal_pe=16.0,
                threshold_pe=3,
                bg_dark_rate_hz=1500.0,
                dead_time_ns=400.0,
                clock_drift_ppm=95.0,
                jitter_rms_ns=25.0,
                pre_window_us=8000.0,
                post_window_us=1000.0,
                seed=5000 + b_idx,
            )
            noisy_optical_streams.append(rx_pulses)

        # 3. Receiver reassembles exact DD\x01 + DD\x02 UDP datagrams from optical bursts
        reconstructed_dgrams, stats = reassemble_udp_datagrams_from_optical(noisy_optical_streams)
        assert stats["frames_failed"] == 0, f"Optical frame failed: {stats}"
        assert len(reconstructed_dgrams) == 1 + total_chunks

        # 4. Feed reconstructed UDP datagrams directly into receiver_hub.process_datagram()
        for dgram in reconstructed_dgrams:
            receiver_hub.process_datagram(dgram, now=1760551235.0, strict_clock_skew=False)

        saved_jpg = os.path.join(tmp_out, f"NODE-SKY-FIN-01_1760551234_{nonce_hex[:8]}.jpg")
        journal_file = os.path.join(tmp_out, "alerts_journal.jsonl")
        assert os.path.isfile(saved_jpg), "receiver_hub failed to reconstruct and save JPEG from optical bridge"
        with open(saved_jpg, "rb") as f:
            assert f.read() == fake_jpeg, "Saved JPEG bytes do not match original camera target crop"
        with open(journal_file, "r", encoding="utf-8") as jf:
            j_entry = json.loads(jf.readline())
            assert j_entry["verified"] is True and j_entry["image_sha256"] == img_sha256
            assert j_entry["detections"][0]["label"] == "person"
    finally:
        receiver_hub.OUT_DIR = old_out_dir
        shutil.rmtree(tmp_out, ignore_errors=True)

    print(
        f"    - Bridged DD01 + {len(fake_jpeg)}B JPEG ({len(optical_bursts)} optical bursts) -> "
        f"Verified SHA-256 & logged to receiver_hub.py"
    )
    print("    [+] End-to-End Trailcam DD01+DD02 Optical Bridge into receiver_hub: PASSED")


def test_nordic_winter_energy_budget():
    print("[*] 16. Validating Sub-Zero Nordic Field Node Energy Budget vs Fiber Converter...")
    winter_e = compute_sky_relay_energy_budget(250, jpeg_crop_bytes_len=2048, temp_c=-25.0, profile="FAST_FSO_1550")
    summer_e = compute_sky_relay_energy_budget(250, jpeg_crop_bytes_len=2048, temp_c=18.0, profile="FAST_FSO_1550")
    assert winter_e["total_energy_wh"] < 0.0065 and winter_e["savings_vs_fiber_converter_pct"] > 40.0
    assert summer_e["total_energy_wh"] < 0.0001
    print(
        f"    - Winter (-25°C w/ PTC window heater): {winter_e['total_energy_wh']:.5f} Wh/event "
        f"({winter_e['savings_vs_fiber_converter_pct']}% less than StarTech fiber converter)"
    )
    print(f"    - Summer (+18°C): {summer_e['total_energy_wh']:.6f} Wh/event ({summer_e['emitter_energy_mj']} mJ optical driver)")
    print("    [+] Nordic Field Node Energy Budget Verification: PASSED")


def test_field_alignment_and_link_health_diagnostics():
    print("[*] 17. Validating Field Alignment & Link Health Telemetry Diagnostics...")
    original_data = b'{"node":"NODE-NORTH-01","mode":"ALIGNMENT_BEACON"}'
    tx_meta = transmit_simulated_burst(original_data, enable_fec=True)
    rx_pulses, _ = simulate_physical_detector_channel(
        tx_meta["pulse_train_us"],
        mean_signal_pe=18.0,
        threshold_pe=3,
        bg_dark_rate_hz=2000.0,
        dead_time_ns=400.0,
        clock_drift_ppm=-110.0,
        jitter_rms_ns=30.0,
        pre_window_us=50000.0,
        post_window_us=2000.0,
        seed=777,
    )
    diag = evaluate_link_health_diagnostics(rx_pulses)
    assert diag["go_no_go"] == "GO" and diag["status"] == "OK"
    assert diag["preamble_matches"] >= 14
    assert diag["symbol_erasure_pct"] < 5.0
    print(
        f"    - Verdict={diag['go_no_go']} | Preamble={diag['preamble_matches']}/16 | "
        f"ClockSkew={diag['clock_skew_ppm']} ppm | Jitter={diag['timing_jitter_rms_ns']} ns | "
        f"BgRate={diag['estimated_bg_rate_hz']} Hz"
    )
    print("    [+] Field Alignment & Link Health Telemetry Diagnostics: PASSED")


def test_vk7mo_ka7oei_weak_signal_lockin_single_pass():
    print("[*] 18. Validating VK7MO/KA7OEI 8-FSK Quadrature Lock-In Scatter Mode (-10 dB Wideband SNR + 50Hz Hum)...")
    from nacl.signing import SigningKey
    sk = SigningKey.generate()
    vk_hex = sk.verify_key.encode().hex()
    signed_payload = create_signed_sky_alert(
        {
            "node": "NODE-FARM-NORTH",
            "ts": 1766000123,
            "nonce": "a1b2c3d4e5f60718",
            "detections": [{"label": "person", "confidence": 0.94}],
            "pico_trig": "PIR+RADAR",
        },
        sk.encode().hex(),
    )

    tx_lockin = encode_vk7mo_lockin_frame(signed_payload, symbol_ms=16.0, enable_fec=True)
    rx_samples, ch_meta = simulate_vk7mo_scatter_channel(
        tx_lockin["waveform"],
        snr_db=-10.0,
        mains_hum_50hz_amp=3.0,
        dc_sunlight_offset=15.0,
        cloud_multipath_phase_rad=1.42,
        seed=2026,
    )
    rx_res = demodulate_vk7mo_lockin_stream(rx_samples, symbol_ms=16.0)
    assert rx_res["status"] == "OK", f"VK7MO single-pass lock-in failed at -10 dB SNR: {rx_res['status']}"
    assert rx_res["payload"] == signed_payload
    verified_alert, is_valid = verify_signed_sky_alert(rx_res["payload"], vk_hex)
    assert is_valid is True and verified_alert["node"] == "NODE-FARM-NORTH"
    print(
        f"    - Decoded {len(signed_payload)}B Ed25519 alert in {tx_lockin['tx_duration_s']}s at -10.0 dB wideband SNR "
        f"(Noise RMS={ch_meta['noise_rms']}, Repaired erasures={rx_res['erased_symbols_repaired']})"
    )
    print("    [+] VK7MO/KA7OEI Single-Pass Weak-Signal Lock-In (-10 dB SNR): PASSED")


def test_vk7mo_multi_pass_noncoherent_energy_combining():
    print("[*] 19. Validating VK7MO 3-Pass Non-Coherent Quadrature Energy Combining at -13.5 dB Deep Scatter SNR...")
    alert_payload = b'{"node":"NODE-COUSIN-LAKE-2KM","mode":"CLOUD_AND_AEROSOL_SCATTER","snr_db":-13.5}'
    tx_lockin = encode_vk7mo_lockin_frame(alert_payload, symbol_ms=16.0, enable_fec=True)

    # Generate 3 independent deep-scatter passes at -13.5 dB wideband SNR with different cloud multipath phases
    passes = []
    for p_idx, phase_rad in enumerate((0.4, 1.9, 2.8)):
        rx_pass, _ = simulate_vk7mo_scatter_channel(
            tx_lockin["waveform"],
            snr_db=-13.5,
            mains_hum_50hz_amp=3.5,
            dc_sunlight_offset=20.0,
            cloud_multipath_phase_rad=phase_rad,
            seed=5000 + p_idx,
        )
        passes.append(rx_pass)

    rx_combined = demodulate_vk7mo_lockin_stream(passes, symbol_ms=16.0)
    assert rx_combined["status"] == "OK", f"VK7MO 3-pass combining failed at -13.5 dB SNR: {rx_combined['status']}"
    assert rx_combined["payload"] == alert_payload
    assert rx_combined["passes_combined"] == 3
    print(
        f"    - Combined 3 passes at -13.5 dB SNR (random cloud phases 0.4, 1.9, 2.8 rad) -> "
        f"100% payload match (Repaired erasures={rx_combined['erased_symbols_repaired']})"
    )
    print("    [+] VK7MO 3-Pass Non-Coherent Energy Combining (-13.5 dB SNR): PASSED")


def test_vk7mo_anti_jamming_fhss_and_tone_notch():
    print("[*] 20. Validating Keyed FHSS Tone Hopping & Anti-Jamming Spectral Whitening against +20 dB Tone Jammer...")
    alert_payload = b'{"node":"NODE-EAST-BORDER-01","ew_status":"JAMMER_NOTCHED","alert":"INTRUSION"}'
    secret_fhss_key = "FINLAND-OPTICAL-FHSS-KEY-2026"
    tx_lockin = encode_vk7mo_lockin_frame(
        alert_payload, symbol_ms=16.0, enable_fec=True, fhss_key=secret_fhss_key
    )
    rx_samples, _ = simulate_vk7mo_scatter_channel(
        tx_lockin["waveform"],
        snr_db=-8.0,
        mains_hum_50hz_amp=3.0,
        dc_sunlight_offset=15.0,
        cloud_multipath_phase_rad=1.1,
        seed=8888,
    )

    # Inject a hostile +20 dB (10x amplitude = 100x power!) continuous optical jammer directly on Tone 3 (1875 Hz)
    jammer_freq_hz = tx_lockin["tone_frequencies_hz"][3]
    two_pi_over_fs = (2.0 * math.pi) / float(tx_lockin["sample_rate_hz"])
    jammed_stream = [
        s + 10.0 * math.cos(two_pi_over_fs * jammer_freq_hz * idx + 0.7)
        for idx, s in enumerate(rx_samples)
    ]

    # 1. Verify that naive demodulation without anti-jamming whitening is blinded by the +20 dB jammer
    naive_res = demodulate_vk7mo_lockin_stream(
        jammed_stream, symbol_ms=16.0, fhss_key=secret_fhss_key, anti_jam_whitening=False
    )
    assert naive_res["status"] != "OK", "Naive receiver without whitening should fail under +20 dB in-band tone jammer"

    # 2. Verify that an eavesdropper/attacker without `fhss_key` cannot decode the frame
    wrong_key_res = demodulate_vk7mo_lockin_stream(
        jammed_stream, symbol_ms=16.0, fhss_key="WRONG-KEY", anti_jam_whitening=True
    )
    assert wrong_key_res["status"] != "OK", "Receiver with wrong FHSS key must not decode frame"

    # 3. Verify that our hardened receiver with `fhss_key` + `anti_jam_whitening=True` detects & notches Tone 3 and recovers 100%
    hardened_res = demodulate_vk7mo_lockin_stream(
        jammed_stream, symbol_ms=16.0, fhss_key=secret_fhss_key, anti_jam_whitening=True
    )
    assert hardened_res["status"] == "OK", f"Anti-jamming FHSS receiver failed: {hardened_res['status']}"
    assert hardened_res["payload"] == alert_payload
    assert 3 in hardened_res["jammed_tones_notched"]
    print(
        f"    - Automatically detected & notched +20 dB optical jammer on Tone {hardened_res['jammed_tones_notched']} "
        f"(1875 Hz), repaired {hardened_res['erased_symbols_repaired']} hopped erasures -> 100% match!"
    )
    print("    [+] Keyed FHSS Tone Hopping & Anti-Jamming Spectral Whitening: PASSED")


def test_100km_troposcatter_rain_scatter_all_weather_link():
    print("[*] 21. Validating 100 km Beyond-Line-of-Sight Troposcatter, Rain/Snow Scatter & 2D Costas CFO Lock (No GPSDO)...")
    # Evaluate 100 km NLOS link (2.4 / 5.8 GHz, 10 W SSPA, 60 cm dishes pointed 0.5° above horizon/trees)
    clear_100km = calculate_troposcatter_link_budget(
        distance_km=100.0, freq_ghz=5.8, tx_power_w=10.0, weather_regime="CLEAR_TROPOSCATTER"
    )
    arctic_100km = calculate_troposcatter_link_budget(
        distance_km=100.0, freq_ghz=5.8, tx_power_w=10.0, weather_regime="DRY_ARCTIC_WINTER"
    )
    rain_snow_100km = calculate_troposcatter_link_budget(
        distance_km=100.0, freq_ghz=5.8, tx_power_w=10.0, weather_regime="RAIN_SNOW_SCATTER"
    )

    assert clear_100km["all_weather_viable"] is True
    assert arctic_100km["all_weather_viable"] is True
    assert rain_snow_100km["all_weather_viable"] is True
    assert rain_snow_100km["median_link_margin_db"] > clear_100km["median_link_margin_db"]
    assert clear_100km["median_link_margin_db"] > arctic_100km["median_link_margin_db"] >= 20.0

    # Simulate a +342.0 Hz SDR local-oscillator thermal drift + wind/rain Doppler shift (2.74 tone bins off!) without GPSDO
    payload = b'{"node":"NODE-TROPO-100KM","mode":"SHF_SCATTER","cfo_hz":342}'
    fhss_key = "TROPO-100KM-KEY-2026"
    true_cfo_hz = 342.0
    tx_drifted = encode_vk7mo_lockin_frame(
        payload, symbol_ms=16.0, base_tone_hz=1500.0 + true_cfo_hz, enable_fec=True, fhss_key=fhss_key
    )
    rx_tropo, _ = simulate_vk7mo_scatter_channel(
        tx_drifted["waveform"], snr_db=-9.0, mains_hum_50hz_amp=0.5, dc_sunlight_offset=0.0, seed=4242
    )
    # 1. Verify fixed-frequency receiver without 2D Costas CFO search fails under +342 Hz SDR drift
    no_cfo_res = demodulate_vk7mo_lockin_stream(
        rx_tropo, symbol_ms=16.0, base_tone_hz=1500.0, fhss_key=fhss_key, cfo_search_range_hz=0.0
    )
    assert no_cfo_res["status"] != "OK", "Receiver without 2D Costas CFO search should fail under +342 Hz SDR drift"

    # 2. Verify 2D Costas Time-Frequency receiver locks onto +342 Hz CFO & decodes 100% without GPSDO
    cfo_locked_res = demodulate_vk7mo_lockin_stream(
        rx_tropo, symbol_ms=16.0, base_tone_hz=1500.0, fhss_key=fhss_key, cfo_search_range_hz=450.0
    )
    assert cfo_locked_res["status"] == "OK", f"2D Costas CFO lock failed: {cfo_locked_res['status']}"
    assert cfo_locked_res["payload"] == payload
    assert abs(cfo_locked_res["estimated_cfo_hz"] - true_cfo_hz) <= 8.0

    print(
        f"    - 100 km Clear Day/Night: ScatterAlt={clear_100km['scatter_altitude_m']} m | "
        f"Loss={clear_100km['total_path_loss_db']} dB | RX={clear_100km['rx_power_dbm']} dBm | "
        f"99% Fade Margin=+{clear_100km['fade_margin_99pct_db']} dB"
    )
    print(
        f"    - 100 km -30°C Dry Arctic: 99% Fade Margin=+{arctic_100km['fade_margin_99pct_db']} dB | "
        f"Rain/Snow Scatter: +{rain_snow_100km['fade_margin_99pct_db']} dB"
    )
    print(
        f"    - 2D Costas Time-Frequency Acquisition (No GPSDO): Locked CFO={cfo_locked_res['estimated_cfo_hz']} Hz "
        f"(true +{true_cfo_hz} Hz) at -9.0 dB SNR -> 100% payload match!"
    )
    print("    [+] 100 km Beyond-Line-of-Sight Troposcatter, Rain/Snow Scatter & 2D Costas CFO Lock: PASSED")


def test_simultaneous_cfo_jammer_and_rayleigh_multipath_fade():
    print("[*] 22. Validating Combined +290 Hz CFO Drift, +20 dB In-Band Jammer & 8-Symbol Rayleigh Multipath Fade Null...")
    payload = b'{"node":"NODE-TROPO-EW-01","status":"SURVIVED_CFO_JAMMER_AND_RAYLEIGH_FADE"}'
    fhss_key = "FINLAND-TROPO-EW-2026"
    true_cfo_hz = 290.0
    tx_pkt = encode_vk7mo_lockin_frame(
        payload, symbol_ms=16.0, base_tone_hz=1500.0 + true_cfo_hz, enable_fec=True, fhss_key=fhss_key
    )
    sps = tx_pkt["samples_per_symbol"]
    wf = list(tx_pkt["waveform"])

    # Apply an 8-symbol (128 ms) deep Rayleigh multipath fade null (-26 dB = 0.05x amplitude) across data symbols 45..52
    fade_start_sample = (16 + 45) * sps
    fade_end_sample = (16 + 53) * sps
    for idx in range(fade_start_sample, min(len(wf), fade_end_sample)):
        wf[idx] *= 0.05

    rx_faded, _ = simulate_vk7mo_scatter_channel(
        wf, snr_db=-7.5, mains_hum_50hz_amp=2.0, dc_sunlight_offset=5.0, seed=9001
    )

    # Also test 2D Costas CFO lock under a simultaneous +20 dB continuous jammer on shifted Tone 5
    jammer_hz = tx_pkt["tone_frequencies_hz"][5]
    two_pi_over_fs = (2.0 * math.pi) / float(tx_pkt["sample_rate_hz"])
    rx_cfo_jammed, _ = simulate_vk7mo_scatter_channel(
        tx_pkt["waveform"], snr_db=-7.5, mains_hum_50hz_amp=2.0, dc_sunlight_offset=5.0, seed=9002
    )
    rx_cfo_jammed = [
        s + 10.0 * math.cos(two_pi_over_fs * jammer_hz * i + 0.3)
        for i, s in enumerate(rx_cfo_jammed)
    ]

    res_faded = demodulate_vk7mo_lockin_stream(
        rx_faded, symbol_ms=16.0, base_tone_hz=1500.0, fhss_key=fhss_key, cfo_search_range_hz=400.0
    )
    assert res_faded["status"] == "OK", f"Failed under +290 Hz CFO + 8-symbol Rayleigh fade: {res_faded['status']}"
    assert res_faded["payload"] == payload

    res_cfo_jam = demodulate_vk7mo_lockin_stream(
        rx_cfo_jammed, symbol_ms=16.0, base_tone_hz=1500.0, fhss_key=fhss_key, cfo_search_range_hz=400.0
    )
    assert res_cfo_jam["status"] == "OK", f"Failed under simultaneous +290 Hz CFO + +20 dB jammer: {res_cfo_jam['status']}"
    assert res_cfo_jam["payload"] == payload
    assert 5 in res_cfo_jam["jammed_tones_notched"]

    print(
        f"    - Survived +290 Hz CFO + 8-symbol Rayleigh deep fade (CFO lock={res_faded['estimated_cfo_hz']} Hz, "
        f"repaired erasures={res_faded['erased_symbols_repaired']})"
    )
    print(
        f"    - Survived simultaneous +290 Hz CFO + +20 dB jammer on Tone {res_cfo_jam['jammed_tones_notched']} "
        f"(CFO lock={res_cfo_jam['estimated_cfo_hz']} Hz) -> 100% match!"
    )
    print("    [+] Combined CFO Drift, +20 dB Jammer & Rayleigh Deep-Fade Recovery: PASSED")


def test_broadband_barrage_and_pulsed_chirp_jammer_immunity():
    print("[*] 23. Validating Wideband Carrier Hopping, +26 dB Barrage Jammer Gate & Pulsed/Chirp Jammer Recovery...")
    fhss_key = "EAST-FINLAND-ANTI-BARRAGE-KEY-2026"
    hops_mhz = derive_fhss_carrier_schedule(fhss_key, num_passes=3)
    assert len(hops_mhz) == 3
    # Verify Pass 0 and Pass 1 hop into the lower (2372-2396 MHz) and upper (2485-2498 MHz) guard bands
    # outside standard 2400-2483.5 MHz Wi-Fi / consumer drone barrage jammers
    assert 2372.0 <= hops_mhz[0] <= 2396.0, f"Unexpected lower guard hop: {hops_mhz[0]}"
    assert 2485.0 <= hops_mhz[1] <= 2498.0, f"Unexpected upper guard hop: {hops_mhz[1]}"
    assert abs(hops_mhz[1] - hops_mhz[0]) >= 85.0

    payload = b'{"node":"NODE-CABIN-20KM","alert":"PERSON","jam_test":"BARRAGE_AND_PULSED_IMMUNE"}'
    cfo_hz = 310.0
    tx_pkt = encode_vk7mo_lockin_frame(
        payload, symbol_ms=16.0, base_tone_hz=1500.0 + cfo_hz, fhss_key=fhss_key
    )
    wf = tx_pkt["waveform"]

    # 1. Multi-pass wideband barrage jammer test:
    # Pass 0 is blasted by a +26 dB wideband barrage jammer (snr_db = -26.0 dB), while
    # Pass 1 and Pass 2 hopped to clean guard channels (snr_db = -8.5 dB, +310 Hz CFO).
    pass0_barrage, _ = simulate_vk7mo_scatter_channel(wf, snr_db=-26.0, seed=9300)
    pass1_clean, _ = simulate_vk7mo_scatter_channel(wf, snr_db=-8.5, seed=9301)
    pass2_clean, _ = simulate_vk7mo_scatter_channel(wf, snr_db=-8.5, seed=9302)

    res_barrage = demodulate_vk7mo_lockin_stream(
        [pass0_barrage, pass1_clean, pass2_clean],
        symbol_ms=16.0,
        base_tone_hz=1500.0,
        fhss_key=fhss_key,
        cfo_search_range_hz=400.0,
    )
    assert res_barrage["status"] == "OK", f"Failed under Pass 0 +26 dB barrage jammer: {res_barrage['status']}"
    assert res_barrage["payload"] == payload
    assert 0 in res_barrage["barrage_jammed_passes_rejected"]

    # 2. Pulsed wideband / swept chirp / Wi-Fi burst collision test on a single pass:
    # Inject a +25 dB broadband multi-tone/chirp burst across 8 consecutive data symbols (w=25..32)
    rx_pulsed, ch_meta = simulate_vk7mo_scatter_channel(wf, snr_db=-7.0, seed=9305)
    sps = tx_pkt["samples_per_symbol"]
    burst_start = ch_meta["pre_samples"] + (16 + 25) * sps
    burst_end = burst_start + 8 * sps
    rng = random.Random(9306)
    for idx in range(burst_start, min(len(rx_pulsed), burst_end)):
        rx_pulsed[idx] += rng.gauss(0.0, 18.0)

    res_pulsed = demodulate_vk7mo_lockin_stream(
        rx_pulsed,
        symbol_ms=16.0,
        base_tone_hz=1500.0,
        fhss_key=fhss_key,
        cfo_search_range_hz=400.0,
    )
    assert res_pulsed["status"] == "OK", f"Failed under 8-symbol pulsed wideband jammer: {res_pulsed['status']}"
    assert res_pulsed["payload"] == payload
    assert res_pulsed["pulsed_jammer_erasures"] >= 6

    print(
        f"    - Wideband Carrier Schedule: {hops_mhz} MHz (out-of-ISM guard hops) | "
        f"Rejected barrage-jammed Pass {res_barrage['barrage_jammed_passes_rejected']} (CFO lock={res_barrage['estimated_cfo_hz']} Hz)"
    )
    print(
        f"    - Repaired 8-symbol +25 dB pulsed/chirp wideband jammer burst "
        f"(flagged {res_pulsed['pulsed_jammer_erasures']} pulsed erasures) -> 100% match!"
    )
    print("    [+] Wideband Carrier Hopping, Barrage Gate & Pulsed/Chirp Jammer Immunity: PASSED")


if __name__ == "__main__":
    print("==================================================")
    print("SKY-DIODE-RELAY OPTICAL PROPAGATION TEST SUITE")
    print("==================================================")
    test_link_budget_math()
    test_8ppm_codec_roundtrip()
    test_end_to_end_transmission_with_jitter()
    test_async_preamble_lock_with_background_noise_and_dropped_pulses()
    test_fec_symbol_error_and_erasure_repair()
    test_corrupt_packet_rejection()
    test_signed_camera_alert_bridge()
    test_midnight_sun_continuous_background_acquisition()
    test_worst_case_3bit_erasure_and_burst_fade_repair()
    test_arctic_winter_crystal_clock_drift_dll_recovery()
    test_snowflake_beam_occultation_carousel_combining()
    test_rp2040_pio_hardware_words_and_safety_interlock()
    test_finnish_climate_multi_regime_physics()
    test_physical_quantum_detector_channel()
    test_end_to_end_trailcam_jpeg_optical_bridge_to_receiver_hub()
    test_nordic_winter_energy_budget()
    test_field_alignment_and_link_health_diagnostics()
    test_vk7mo_ka7oei_weak_signal_lockin_single_pass()
    test_vk7mo_multi_pass_noncoherent_energy_combining()
    test_vk7mo_anti_jamming_fhss_and_tone_notch()
    test_100km_troposcatter_rain_scatter_all_weather_link()
    test_simultaneous_cfo_jammer_and_rayleigh_multipath_fade()
    test_broadband_barrage_and_pulsed_chirp_jammer_immunity()
    print("\n[ALL 23 SKY RELAY SIMULATION & FINNISH CLIMATE TESTS PASSED SUCCESSFULLY!]")




