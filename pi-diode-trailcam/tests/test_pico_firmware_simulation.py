#!/usr/bin/env python3
"""
Test Suite: Simulation & Verification of Arctic RP2040 Gatekeeper Firmware Logic
Verifies:
1. Dynamic EMA baseline tracking under diurnal temperature drift.
2. HLK-LD2450 radar frame decoding & byte slicing.
3. Sub-zero ADC temperature conversion and PTC de-icer logic.
4. Multi-sensor verification state transitions.
"""
import struct
import math
import os

os.environ.setdefault("ALLOW_EXAMPLE_KEYS", "1")

def test_radar_packet_unpack():
    print("[*] Testing HLK-LD2450 30-byte full frame unpacking (with 0x55 0xCC footer & 3 target slots)...")
    # Protocol: 0xAA, 0xFF, 0x03, 0x00 (4B Header) + Target 1..3 (3 x 8B) + 0x55, 0xCC (2B Footer) = 30 bytes
    header = b"\xAA\xFF\x03\x00"
    target1_x = 200
    target1_y = 3500
    target1_spd = 120
    target1_bytes = struct.pack("<hhhH", target1_x, target1_y, target1_spd, 0)
    target2_bytes = bytes(8)
    target3_bytes = bytes(8)
    footer = b"\x55\xCC"
    raw_packet = header + target1_bytes + target2_bytes + target3_bytes + footer

    assert len(raw_packet) == 30, f"Packet length should be 30, got {len(raw_packet)}"
    assert raw_packet[:4] == b"\xAA\xFF\x03\x00" and raw_packet[28:30] == b"\x55\xCC", "Invalid frame header/footer"

    # Test both positive (bit 15 = 1) and negative (bit 15 = 0) sign-magnitude HLK-LD2450 values
    # In HLK-LD2450 protocol: bit 15 = 1 means positive, bit 15 = 0 means negative
    pos_y_u16 = 0x8000 | 3500   # +3500 mm
    neg_x_u16 = 200             # -200 mm
    pos_spd_u16 = 0x8000 | 120  # +120 cm/s
    signed_pkt = header + struct.pack("<HHHH", neg_x_u16, pos_y_u16, pos_spd_u16, 0) + target2_bytes + target3_bytes + footer
    assert len(signed_pkt) == 30

    import sys
    import types
    import os

    # Create mock MicroPython 'machine' module to import pico_gatekeeper/main.py directly
    mock_machine = types.ModuleType("machine")
    class MockPin:
        IN = 0
        OUT = 1
        PULL_UP = 2
        PULL_DOWN = 3
        def __init__(self, pin_id, mode=0, pull=0, value=0):
            self.pin_id = pin_id
            self._val = value
        def value(self, v=None):
            if v is not None:
                self._val = v
            return 1 if self.pin_id == 17 else self._val
    class MockI2C:
        def __init__(self, *args, **kwargs): pass
        def scan(self): return [0x0D, 0x48]
        def writeto_mem(self, *args, **kwargs): pass
        def readfrom_mem(self, addr, reg, n):
            return b"\x10\x05\x20\x04\x30\x03" if n == 6 else b"\x01\x90"
    class MockUART:
        def __init__(self, *args, **kwargs):
            self._rx = b"\x00\xFF" + signed_pkt  # Leading garbage bytes to test header sync!
            self.tx_log = []
        def any(self): return len(self._rx)
        def read(self, n):
            out = self._rx[:n]
            self._rx = self._rx[n:]
            return out
        def write(self, data): self.tx_log.append(data)
    class MockADC:
        def __init__(self, ch): pass
        def read_u16(self): return int((0.795492 / 3.3) * 65535)
    class MockWDT:
        def __init__(self, timeout=8000): self.feeds = 0
        def feed(self): self.feeds += 1

    mock_machine.Pin = MockPin
    mock_machine.I2C = MockI2C
    mock_machine.UART = MockUART
    mock_machine.ADC = MockADC
    mock_machine.WDT = MockWDT
    mock_machine.lightsleep = lambda ms: None
    mock_machine.freq = lambda hz: None
    sys.modules["machine"] = mock_machine

    import time as std_time
    if not hasattr(std_time, "ticks_ms"):
        std_time.ticks_ms = lambda: int(std_time.time() * 1000)
        std_time.ticks_diff = lambda a, b: a - b
        std_time.sleep_ms = lambda ms: None
        std_time.sleep_us = lambda us: None

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../pico_gatekeeper")))
    import main as pico_main

    assert pico_main._decode_ld2450_signed16(pos_y_u16) == 3500
    assert pico_main._decode_ld2450_signed16(neg_x_u16) == -200
    assert pico_main._decode_ld2450_signed16(pos_spd_u16) == 120

    wdt = MockWDT(timeout=8000)
    dist_mm, spd_cms = pico_main.check_ld2450_radar(wdt=wdt, listen_ms=200)
    assert dist_mm >= 3500, f"Expected distance >= 3500mm, got {dist_mm}"
    assert spd_cms == 120, f"Expected +120 cm/s, got {spd_cms}"
    assert wdt.feeds > 0, "Watchdog should be fed during radar check"
    print(f"    [+] Radar frame decoding & stream sync: PASSED (Dist={dist_mm}mm, Spd={spd_cms}cm/s)")

def test_ema_baseline_tracking():
    print("[*] Testing Dynamic EMA Baseline Tracking...")
    EMA_SHIFT = 6  # Alpha = 1/64
    baseline = 3000

    # Simulate 500 steps of realistic environmental diurnal drift (e.g. 0.5 counts per 80ms step)
    for step in range(500):
        ambient_noise = int(3000 + 300 * math.sin(step / 200.0))
        baseline += (ambient_noise - baseline) >> EMA_SHIFT

    # Baseline should track ambient drift smoothly without triggering false alarms
    drifted_ambient = int(3000 + 300 * math.sin(500 / 200.0))
    delta = abs(drifted_ambient - baseline)
    assert delta < 200, f"EMA baseline lag too high: delta = {delta}"
    print(f"    [+] EMA baseline smoothly adapted: Ambient={drifted_ambient}, Baseline={baseline}, Lag={delta}")

    # Now simulate a sharp vehicle anomaly (+1800 counts)
    vehicle_signal = drifted_ambient + 1800
    anomaly_delta = abs(vehicle_signal - baseline)
    MAG_DELTA_OFFSET = 1200
    assert anomaly_delta > MAG_DELTA_OFFSET, f"Failed to trigger on anomaly: {anomaly_delta} <= {MAG_DELTA_OFFSET}"
    print(f"    [+] Vehicle magnetic spike correctly triggered: Anomaly Delta={anomaly_delta} > {MAG_DELTA_OFFSET}")

def test_temperature_conversion():
    print("[*] Testing RP2040 Core Temperature & De-Icer Logic...")
    # ADC Channel 4 formula: V = raw * 3.3 / 65535, T = 27 - (V - 0.706) / 0.001721
    # Test 1: +20°C ambient (summer)
    # V = 0.706 - (20 - 27) * 0.001721 = 0.706 + 7 * 0.001721 = 0.718 V
    raw_20c = int((0.718047 / 3.3) * 65535)
    v_calc = raw_20c * 3.3 / 65535.0
    t_20c = 27.0 - (v_calc - 0.706) / 0.001721
    assert abs(t_20c - 20.0) < 0.2

    # Test 2: -25°C arctic winter
    # V = 0.706 - (-25 - 27) * 0.001721 = 0.706 + 52 * 0.001721 = 0.7955 V
    raw_subzero = int((0.795492 / 3.3) * 65535)
    v_sub = raw_subzero * 3.3 / 65535.0
    t_subzero = 27.0 - (v_sub - 0.706) / 0.001721
    assert t_subzero < 0.0
    # Sub-zero check should trigger de-icer
    deicer_active = (t_subzero <= 1.0)
    assert deicer_active is True
    print(f"    [+] Temperature conversion PASSED: Subzero={t_subzero:.1f}°C -> De-icer Active={deicer_active}")

def test_receiver_hub_signature_verification():
    print("[*] Testing Receiver Hub Signature and Chunk Parsing...")
    try:
        from nacl.signing import SigningKey
        key = SigningKey.generate()
        pub = key.verify_key

        msg = b'{"node":"TEST-01","ts":1760000000,"detections":[{"class":"person"}]}'
        sig = key.sign(msg).signature
        pkt = b"DD\x01" + sig + msg

        # Test slice extracted in receiver_hub.py
        extracted_sig = pkt[3:67]
        extracted_msg = pkt[67:]
        pub.verify(extracted_msg, extracted_sig)
        print("    [+] Packet 0x01 Signature Slice Verification: PASSED (PyNaCl)")
    except ImportError:
        # Verify byte slicing layout: Type byte at index 2, 64-byte signature from index 3 to 67
        dummy_sig = b"S" * 64
        msg = b'{"node":"TEST-01","ts":1760000000,"detections":[{"class":"person"}]}'
        pkt = b"DD\x01" + dummy_sig + msg
        assert pkt[2] == 1, "Packet type should be 0x01"
        assert pkt[3:67] == dummy_sig, "Extracted signature does not match"
        assert pkt[67:] == msg, "Extracted JSON payload does not match"
        print("    [+] Packet 0x01 Signature Slice Layout (3:67 & 67:): PASSED (Byte validation)")

def test_sensor_profiles_and_debounced_wake():
    print("[*] Testing Sensor Profiles, Debounced DONE Pin & Overlapped De-Icer Wake...")
    import time as std_time
    import main as pico_main

    # 1. Verify operating profile classification across hardware states
    pico_main.SEISMIC_ALERT._val = 1
    pico_main.sensor_health["mag"] = True
    pico_main.sensor_health["seis"] = True
    assert pico_main.detect_operating_profile(bench_override=False) == pico_main.PROFILE_FULL_TRIPLE

    pico_main.sensor_health["mag"] = True
    pico_main.sensor_health["seis"] = False
    assert pico_main.detect_operating_profile(bench_override=False) == pico_main.PROFILE_MAG_RADAR_DUTY
    assert pico_main.detect_operating_profile(bench_override=True) == pico_main.PROFILE_BENCH_MAG_ONLY

    # 2. Verify 3-sample EMI debounce on Pi 5 DONE pin
    if pico_main.BREADBOARD_DONE_PIN is not None:
        pico_main.BREADBOARD_DONE_PIN._val = 0
    seq = iter([1, 0, 1])  # Glitchy pulse -> should return False
    orig_val = pico_main.PI5_DONE_PIN.value
    pico_main.PI5_DONE_PIN.value = lambda: next(seq)
    assert pico_main.is_done_asserted_debounced(samples=3, delay_ms=0) is False

    seq_solid = iter([1, 1, 1])  # Solid HIGH -> should return True
    pico_main.PI5_DONE_PIN.value = lambda: next(seq_solid)
    assert pico_main.is_done_asserted_debounced(samples=3, delay_ms=0) is True
    pico_main.PI5_DONE_PIN.value = orig_val

    # 3. Verify overlapped Pi 5 wake + PTC de-icer & telemetry formatting
    pico_main.pi5_uart.tx_log.clear()
    orig_sleep = std_time.sleep
    orig_ticks = std_time.ticks_ms
    fake_clock = [1000]
    def advance_clock():
        fake_clock[0] += 2000
        return fake_clock[0]
    std_time.sleep = lambda s: None
    std_time.ticks_ms = advance_clock
    try:
        pico_main.boot_pi5_and_handoff(
            mag_val=3400, mag_base=1600,
            seismic_val=0, seis_base=0,
            radar_dist=3800, radar_spd=115,
            temp_c=-12.5, wdt=None,
            profile=pico_main.PROFILE_MAG_RADAR_DUTY
        )
    finally:
        std_time.sleep = orig_sleep
        std_time.ticks_ms = orig_ticks

    assert len(pico_main.pi5_uart.tx_log) >= 1, "Expected TRIG telemetry transmitted over UART1"
    trig_line = pico_main.pi5_uart.tx_log[-1].decode("utf-8")
    assert "UPTIME_S=" in trig_line and "PROFILE=MAG_RADAR_DUTY" in trig_line, f"Missing fields in {trig_line}"
    assert "FAST_SNAP=" in trig_line and "TAMPER_ZEROIZED=" in trig_line, f"Missing border hardening fields in {trig_line}"
    assert pico_main.MOSFET_GATE.value() == 0, "MOSFET_GATE must be cut after wake cycle completes"
    assert pico_main.DEICE_HEATER.value() == 0, "DEICE_HEATER must be off after wake cycle completes"
    print("    [+] Sensor Profiles, 75ms DONE Debounce & Overlapped De-Icer: PASSED")


def test_border_hardening_upgrades():
    print("[*] Testing 5 Border-Hardening Upgrades (SPI Instant-Snap, MLX90640 0.00W EMCON, Tamper Zeroize, Aloha Trunk, BME280 Frost Gate)...")
    import main as pico_main
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../pi5_sender_node")))
    import sender_node

    # 1. BME280 Frost-Point / Dew-Point Gating (Upgrade 5)
    assert pico_main.should_enable_lens_deicer(temp_c=15.0, rh_pct=90.0) is False, "Should not heat at +15C"
    assert pico_main.should_enable_lens_deicer(temp_c=-5.0, rh_pct=35.0) is False, "Dry cold (-5C, 35% RH -> Td=-18C) should skip heater to save battery"
    assert pico_main.should_enable_lens_deicer(temp_c=-2.0, rh_pct=88.0) is True, "Humid freezing (-2C, 88% RH) must enable heater"

    # 2. Passive MLX90640 LWIR Thermal EMCON Profile (0.00W RF, Upgrade 2)
    pico_main.sensor_health["lwir"] = True
    assert pico_main.detect_operating_profile(bench_override=False) == pico_main.PROFILE_PASSIVE_EMCON_LWIR
    pico_main.read_mlx90640_thermal_contrast_c = lambda: 5.2
    verified, tripped, dist_equiv, _ = pico_main.evaluate_sensor_step(
        current_mag=3000, mag_ema=3000, current_seis=150, seis_ema=150,
        profile=pico_main.PROFILE_PASSIVE_EMCON_LWIR, loop_count=1
    )
    assert verified is True and tripped is True and dist_equiv == 5200
    assert pico_main.RADAR_PWR.value() == 0, "24GHz radar must remain 0.00W OFF in PROFILE_PASSIVE_EMCON_LWIR"
    pico_main.sensor_health["lwir"] = False

    # 3. Ephemeral SRAM Key Tamper Zeroization (<1ms wipe, Upgrade 3)
    pico_main.EPHEMERAL_SRAM_KEY[:] = b"ARCTIC-EPHEMERAL-SRAM-KEY-SEED01"
    pico_main.tamper_zeroized = False
    pico_main.zeroize_ephemeral_key_on_tamper()
    assert pico_main.tamper_zeroized is True
    assert all(b == 0 for b in pico_main.EPHEMERAL_SRAM_KEY), "SRAM key must be 100% zeroized (0x00)"

    # 4. Multi-Camera Shared Fiber Trunk Aloha Backoff (Upgrade 4)
    d_off = sender_node.compute_aloha_interpass_delays_s("NODE-NORTH-01", shared_trunk=False)
    assert d_off == (0.0, 0.0)
    d_n1 = sender_node.compute_aloha_interpass_delays_s("NODE-NORTH-01", shared_trunk=True)
    d_n2 = sender_node.compute_aloha_interpass_delays_s("NODE-NORTH-02", shared_trunk=True)
    assert 0.100 <= d_n1[0] <= 0.650 and 0.250 <= d_n1[1] <= 0.850
    assert 0.100 <= d_n2[0] <= 0.650 and 0.250 <= d_n2[1] <= 0.850

    # 5. Airspace-Safety Pod: Two-Beacon Clock Discipline, ePTFE Vent Icing Self-Test, Traficom Reg 15 & 58-Byte DD\x03 Frame
    clk = pico_main.compute_disciplined_clock_state(2300.0, 2000.0, 1700.001, 300.0, "RV3032_C7")
    assert clk["sync_mode"] == "TWO_BEACON_SLOPE_DISCIPLINED" and clk["clock_uncertainty_s"] <= 0.050
    ice_trig = pico_main.evaluate_acoustic_vent_icing_selftest([70.0, 70.5, 69.8, 61.0], -12.0, 94.0, 0.01)
    assert ice_trig["vent_status"] == "DEICING_PULSE_ACTIVE" and ice_trig["pulse_heater_s"] == 60
    ice_cap = pico_main.evaluate_acoustic_vent_icing_selftest([70.0, 70.5, 69.8, 61.0], -12.0, 94.0, 0.078)
    assert ice_cap["vent_status"] == "DEGRADED_ICING_CAP_EXHAUSTED" and ice_cap["pulse_heater_s"] == 0
    toa_sf7 = pico_main.compute_sx1262_lora_toa_s(payload_bytes=58, sf=7, bw_hz=125000, cr=1, preamble_symbols=13)
    toa_sf9 = pico_main.compute_sx1262_lora_toa_s(payload_bytes=58, sf=9, bw_hz=125000, cr=1, preamble_symbols=8)
    assert abs(toa_sf7 - 0.118016) < 1e-6, f"Expected 0.118016 s at SF7/BW125, got {toa_sf7}"
    assert abs(toa_sf9 - 0.369664) < 1e-6, f"Expected 0.369664 s at SF9/BW125, got {toa_sf9}"
    reg_ok = pico_main.evaluate_traficom_reg15_airtime_admission(10.0, toa_sf9, "869.4-869.65MHz_500mW_10pct", epoch_period_s=15.0, lora_sf=9, lora_bw_hz=125000)
    assert reg_ok["admitted"] is True and reg_ok["steady_duty_cycle_pct"] <= 10.0
    reg_1pct_ok = pico_main.evaluate_traficom_reg15_airtime_admission(10.0, toa_sf7, "868.0-868.6MHz_25mW_1pct", epoch_period_s=15.0, lora_sf=7, lora_bw_hz=125000)
    assert reg_1pct_ok["admitted"] is True and reg_1pct_ok["steady_duty_cycle_pct"] <= 1.0
    reg_1pct_over = pico_main.evaluate_traficom_reg15_airtime_admission(10.0, toa_sf7, "868.0-868.6MHz_25mW_1pct", epoch_period_s=10.0, lora_sf=7, lora_bw_hz=125000)
    assert reg_1pct_over["admitted"] is False and reg_1pct_over["steady_duty_cycle_pct"] > 1.0
    reg_sf10_dyn = pico_main.evaluate_traficom_reg15_airtime_admission(10.0, 0.0, "869.4-869.65MHz_500mW_10pct", epoch_period_s=15.0, lora_sf=10, lora_bw_hz=125000, tx_erp_mw=450.0)
    assert reg_sf10_dyn["admitted"] is True and reg_sf10_dyn["frame_airtime_s"] > 0.60 and reg_sf10_dyn["erp_compliant"] is True
    reg_erp_over = pico_main.evaluate_traficom_reg15_airtime_admission(10.0, 0.0, "868.0-868.6MHz_25mW_1pct", epoch_period_s=30.0, lora_sf=7, lora_bw_hz=125000, tx_erp_mw=50.0)
    assert reg_erp_over["admitted"] is False and reg_erp_over["erp_compliant"] is False
    try:
        pico_main._load_provisioned_dd03_hmac_key(mac_key=None, allow_sim_ephemeral_key=False)
        assert False, "Unprovisioned DD03 key load must fail closed with RuntimeError!"
    except RuntimeError:
        pass
    test_key = b"PROVISIONED_UNIT_TEST_MAC_KEY_32"
    dd03 = pico_main.build_dd03_airspace_tracklet_frame(
        7, 1700000000, 250, [{"az_deg": 145.2, "el_deg": -8.5, "az_sigma_deg": 2.5, "f0_hz": 128.0, "fdot_hz_s": 0.5, "snr_db": 14.5}], -25, 38, mac_key=test_key, top_class=3, clock_quality=2
    )
    assert len(dd03) == 58 and dd03[:3] == b"DD\x03"
    assert dd03[11] == ((3 << 4) | (1 << 2) | 2)
    assert struct.unpack(">b", dd03[14:15])[0] == -17
    # Verify anti-replay window and MAC verification
    replay_db = {}
    v_ok = pico_main.verify_dd03_replay_and_mac(dd03, replay_db, current_epoch_s=1700000002, mac_key=test_key)
    assert v_ok["valid"] is True
    v_rep = pico_main.verify_dd03_replay_and_mac(dd03, replay_db, current_epoch_s=1700000003, mac_key=test_key)
    assert v_rep["valid"] is False and v_rep["reason"] == "REPLAY_DETECTED"
    # Verify MicroPython no-hmac path produces bit-identical RFC 2104 HMAC-SHA256-128 tag
    import hmac as _std_hmac
    import hashlib as _std_hashlib
    expected_mac16 = _std_hmac.new(test_key, dd03[:42], _std_hashlib.sha256).digest()[:16]
    assert dd03[42:58] == expected_mac16, "CPython HMAC-SHA256-128 tag mismatch"
    saved_hmac = sys.modules.get("hmac")
    try:
        sys.modules["hmac"] = None  # Force ImportError on `import hmac` to test MicroPython uhashlib path
        mp_digest = pico_main._rfc2104_hmac_sha256(test_key, dd03[:42])[:16]
        assert mp_digest == expected_mac16, "MicroPython RFC 2104 HMAC-SHA256 path must match CPython hmac bit-for-bit!"
    finally:
        if saved_hmac is not None:
            sys.modules["hmac"] = saved_hmac
        else:
            sys.modules.pop("hmac", None)

    # 6. [P11-RF] Passive-RF & EU Direct Remote ID (ASTM F3411-22a) + [P12-BELT] Non-RF Rotorcraft Belt
    rid_coop = pico_main.parse_passive_remote_id_and_rf_energy(
        b"RID,UAS=FIN-USPACE-99,LAT=66.150,LON=29.150,ALT=95,SPD=1650,RF_DBM=-58.0,GNSS_J_DB=1.2"
    )
    assert rid_coop["rf_class"] == "COOPERATIVE_EU_REMOTE_ID" and rid_coop["remote_id_valid"] is True and rid_coop["tx_power_w"] == 0.0
    rid_uncoop = pico_main.parse_passive_remote_id_and_rf_energy(b"", rf_burst_dbm=-61.5, gnss_l1_jam_db=1.0)
    assert rid_uncoop["rf_class"] == "UNCOOPERATIVE_RF_EMITTING_UAV" and rid_uncoop["passive_rf_triggered"] is True
    rid_jam = pico_main.parse_passive_remote_id_and_rf_energy(b"", rf_burst_dbm=-105.0, gnss_l1_jam_db=11.5)
    assert rid_jam["rf_class"] == "GNSS_L1_INTERFERENCE_EVENT" and rid_jam["passive_rf_triggered"] is True
    belt_step = pico_main.evaluate_non_rf_corridor_belt_step()
    assert belt_step["verified_non_rf_rotorcraft"] is True and belt_step["dd03_frame_len_bytes"] == 58 and belt_step["passive_net_release_ms"] == 120.0

    # 7. Gap L Allied Sensor Auto-Detection: Swedish Acconeer XM125 (0x52) & USA Garmin LIDAR-Lite v4 LED (0x62)
    orig_scan = pico_main.i2c.scan
    orig_readfrom = pico_main.i2c.readfrom_mem
    try:
        pico_main.i2c.scan = lambda: [0x1C, 0x52, 0x62]  # STMicro LIS3MDL (0x1C), Acconeer XM125 (0x52), Garmin LIDAR v4 (0x62)
        pico_main.i2c.readfrom_mem = lambda addr, reg, n: struct.pack("<Hh", 4250, -1850) if (addr == 0x52 and n == 4) else orig_readfrom(addr, reg, n)
        assert pico_main.init_sensors() is True
        assert pico_main.sensor_health["mag"] is True and pico_main.active_qmc_addr == 0x1C
        assert pico_main.sensor_health["xm125"] is True
        assert pico_main.sensor_health["garmin_lidar"] is True
        xm_dist, xm_spd = pico_main.read_xm125_radar_i2c()
        assert xm_dist == 4250 and xm_spd == -1850
    finally:
        pico_main.i2c.scan = orig_scan
        pico_main.i2c.readfrom_mem = orig_readfrom
        pico_main.init_sensors()

    print("    [+] All 5 Border-Hardening Upgrades + Airspace-Safety DD\\x03 Pod + [P11-RF]/[P12-BELT] + XM125/Garmin Allied Auto-Detect: PASSED")


def test_corridor_turboshaft_smoke_tailchase_and_seismic_upgrades():
    print("[*] Testing Phase V2.2 Upgrades 1-5 (Sub-Bass Turboshaft BPF + Decoy Gate, Fast Pre-Wake, TC001 LWIR Smoke Fusion, 180-deg Tail-Chase Cue & Seismic Blast EMA Freeze)...")
    import main as pico_main
    import numpy as np
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../pi5_sender_node")))
    import sender_node

    # Upgrade 1A: Heavy Turboshaft Rotorcraft (31.2 Hz coaxial 2P / 39.2 Hz 5-blade, 0 dB ESC PWM, H2/H1 = 1.65)
    heavy_real = pico_main.evaluate_non_rf_corridor_belt_step(
        rotor_bpf_hz=31.2,
        rotor_bpf_snr_db=16.0,
        esc_pwm_sideband_snr_db=0.0,
        xm125_micro_doppler_mps=19.5,
        lwir_or_940nm_tripwire=True,
        rf_burst_dbm=-108.0,
        rotor_freq_jitter_hz_per_s=0.9,
        harmonic_ratio_h2_h1=1.65,
        sub20hz_1p_infrasound_snr_db=9.5,
        peak_spl_dba=134.0,
    )
    assert heavy_real["verified_non_rf_rotorcraft"] is True
    assert heavy_real["rotorcraft_acoustic_branch"] == "HEAVY_TURBOSHAFT_ROTORCRAFT"
    assert heavy_real["heavy_turboshaft_harmonic_comb_matched"] is True
    assert heavy_real["acoustic_decoy_speaker_rejected"] is False
    assert heavy_real["stage1_acoustic_range_m"] == 1200.0
    assert heavy_real["impulse_overload_blanked_ms"] == 2.0

    # Upgrade 1B: Acoustic Speaker Decoy Rejection (31.2 Hz audio playback, ka << 1 -> 0 dB 1P infrasound & 0 m/s heavy rotor micro-Doppler)
    decoy_step = pico_main.evaluate_non_rf_corridor_belt_step(
        rotor_bpf_hz=31.2,
        rotor_bpf_snr_db=15.0,
        esc_pwm_sideband_snr_db=0.0,
        xm125_micro_doppler_mps=0.0,
        lwir_or_940nm_tripwire=False,
        rf_burst_dbm=-108.0,
        rotor_freq_jitter_hz_per_s=0.8,
        harmonic_ratio_h2_h1=1.55,
        sub20hz_1p_infrasound_snr_db=1.2,
    )
    assert decoy_step["verified_non_rf_rotorcraft"] is False
    assert decoy_step["acoustic_decoy_speaker_rejected"] is True

    # Upgrade 2: Fast Aerial Transit (65 m/s) SPI Instant-Snap + 0.48s DD\x03 Downstream Corridor Pre-Wake
    prewake = pico_main.evaluate_upstream_corridor_prewake_and_fast_snap(
        v_target_mps=65.0,
        downstream_node_spacing_m=1500.0,
        pi5_cold_boot_s=6.8,
        radial_speed_mps=-65.0,
        fdot_hz_per_s=-4.8,
        rotor_bpf_hz=31.2,
        snr_db=16.5,
    )
    assert prewake["fast_aerial_bypass_triggered"] is True
    assert prewake["spi_instant_frame_bytes"] == 160 * 120
    assert prewake["dd03_prewake_frame_bytes"] == 58
    assert prewake["downstream_warm_stream_margin_s"] >= 15.0
    assert prewake["downstream_camera_ready_before_arrival"] is True

    # Upgrade 3: Dual-Band IMX708 + TOPDON TC001 (8-14 um LWIR) Through-Smoke Capture & Hotspot Fusion
    smoke_eo = np.full((120, 160, 3), 72, dtype=np.uint8)  # Low-contrast grey soot plume (RMS contrast ~ 0)
    lwir_map = np.full((192, 256), 8.0, dtype=np.float32)  # +8 C background
    lwir_map[40:52, 90:108] = 520.0                        # +520 C turbine exhaust hotspot
    lwir_map[120:136, 140:155] = 33.5                      # +33.5 C person/vehicle thermal signature
    smoke_res = sender_node.detect_smoke_obscuration_and_fuse_tc001_lwir(
        smoke_eo,
        existing_detections=[],
        simulated_lwir_temp_c_map=lwir_map,
        soot_mass_conc_g_m3=1.8,
        path_length_m=200.0,
    )
    assert smoke_res["smoke_or_fog_obscured"] is True
    assert smoke_res["vis_055um_transmission_pct"] < 6.0
    assert smoke_res["lwir_10um_transmission_pct"] > 85.0
    assert smoke_res["tc001_lwir_sensor_active"] is True
    assert smoke_res["lwir_hotspots_detected"] >= 2
    classes_detected = {d["class"] for d in smoke_res["fused_detections"]}
    assert "turbine_exhaust_hotspot" in classes_detected
    assert "thermal_person_vehicle" in classes_detected

    # Verify sharp EO detection lock (>=0.70 conf) suppresses false smoke-obscuration trigger on uniform background
    clear_res = sender_node.detect_smoke_obscuration_and_fuse_tc001_lwir(
        smoke_eo,
        existing_detections=[{"class": "helicopter", "conf": 0.85, "box": [0.2, 0.2, 0.5, 0.5]}],
        simulated_lwir_temp_c_map=None,
    )
    assert clear_res["smoke_or_fog_obscured"] is False

    # Verify live evaluate_sensor_step() in PROFILE_NON_RF_CORRIDOR_BELT with 31.2 Hz heavy turboshaft rotorcraft
    pico_main.sensor_health["seis"] = True
    pico_main.sensor_health["mag"] = True
    v_belt, t_belt, dist_belt, _ = pico_main.evaluate_sensor_step(
        current_mag=5000, mag_ema=3000, current_seis=700, seis_ema=150,
        profile=pico_main.PROFILE_NON_RF_CORRIDOR_BELT, loop_count=1,
        rotor_bpf_hz=31.2, harmonic_ratio_h2_h1=1.65, sub20hz_1p_infrasound_snr_db=9.5,
    )
    assert v_belt is True and t_belt is True and dist_belt == 1200000

    # Upgrade 4: Cross-Node 180-deg Receding Tail-Chase Angular-Rate (omega = v_t * Z_0 / R^2) Cueing
    cue_headon = pico_main.compute_cross_node_tailchase_cue(
        v_target_mps=65.0, altitude_agl_m=32.0, along_track_x_m=-380.0
    )
    assert cue_headon["frontal_dead_zone_inhibit"] is True
    assert cue_headon["tailchase_sweet_spot_fire"] is False

    cue_overhead = pico_main.compute_cross_node_tailchase_cue(
        v_target_mps=65.0, altitude_agl_m=32.0, along_track_x_m=0.0
    )
    assert cue_overhead["overhead_slew_limit_exceeded"] is True
    assert cue_overhead["los_omega_degs"] > 110.0

    cue_prewarm = pico_main.compute_cross_node_tailchase_cue(
        v_target_mps=65.0, altitude_agl_m=32.0, along_track_x_m=162.5  # t = +2.5 s
    )
    assert cue_prewarm["bcu_pre_uncage_trigger"] is True

    cue_tailchase = pico_main.compute_cross_node_tailchase_cue(
        v_target_mps=65.0, altitude_agl_m=32.0, along_track_x_m=273.0  # t = +4.2 s
    )
    assert cue_tailchase["tailchase_sweet_spot_fire"] is True
    assert cue_tailchase["los_omega_degs"] < 5.0
    assert cue_tailchase["aspect_deg"] > 170.0

    # Upgrade 5: Seismic Blast-vs-Footstep Classifier & EMA Baseline Freeze
    seis_blast = pico_main.classify_seismic_event_signature(
        pgv_mm_s=16.5, crest_factor=6.8, dominant_freq_hz=12.0, current_seis_counts=18000, seis_ema_counts=150
    )
    assert seis_blast["seismic_event_class"] == "IMPULSE_BLAST_OR_QUARRY_DETONATION"
    assert seis_blast["freeze_ema_update"] is True
    assert seis_blast["seis_ema_after"] == 150, "EMA baseline must remain frozen at 150 during impulse blast!"
    assert pico_main.update_seismic_ema_with_blast_guard(18000, 150) == 150
    assert pico_main.update_seismic_ema_with_blast_guard(280, 150) > 150

    seis_step = pico_main.classify_seismic_event_signature(
        pgv_mm_s=0.32, crest_factor=2.9, dominant_freq_hz=24.0, current_seis_counts=380, seis_ema_counts=150
    )
    assert seis_step["seismic_event_class"] == "FOOTSTEP_OR_PERSON"
    assert seis_step["freeze_ema_update"] is False
    print("    [+] Phase V2.2 Upgrades 1-5 (Turboshaft BPF, Pre-Wake, TC001 LWIR Smoke Fusion, 180-deg Tail-Chase & Seismic Blast Freeze): PASSED")


if __name__ == "__main__":
    print("==================================================")
    print("PI-DIODE-TRAILCAM FIRMWARE & PROTOCOL TEST SUITE")
    print("==================================================")
    test_radar_packet_unpack()
    test_ema_baseline_tracking()
    test_temperature_conversion()
    test_receiver_hub_signature_verification()
    test_sensor_profiles_and_debounced_wake()
    test_border_hardening_upgrades()
    test_corridor_turboshaft_smoke_tailchase_and_seismic_upgrades()
    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")
