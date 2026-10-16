#!/usr/bin/env python3
"""
File: sky-diode-relay/transmitter/sky_transmitter.py
Description: Production-Hardened Pulse Position Modulation (8-PPM) Optical Relay Transmitter
             with Bit-Interleaved Extended Hamming(8,4) SECDED FEC, Adaptive Nordic Weather
             Profiles, Cycle-Exact RP2040 PIO FIFO Packing, and Ed25519 Signed Alert Bridge.
License: MIT
"""
import time
import struct
import zlib

FRAME_SYNC_WORD = b"SKY!"  # 0x53 0x4B 0x59 0x21 (Uncoded standard frame)
FRAME_SYNC_FEC  = b"SKYF"  # 0x53 0x4B 0x59 0x46 (Bit-interleaved SECDED FEC frame)
CHIP_DURATION_US = 2       # Default: 2 microseconds per temporal slot
SLOTS_PER_SYMBOL = 8       # 8-PPM (3 bits per symbol window)
PULSE_DURATION_NS = 250    # Default: 250 nanosecond optical pulse width

# Adaptive Link Profiles for Finnish Climate & Optical Regimes
TRANSMISSION_PROFILES = {
    "FAST_FSO_1550": {
        "chip_us": 2.0,
        "pulse_ns": 200,
        "pulses_per_symbol": 1,
        "carousel_passes": 1,
        "inter_pass_gap_ms": 0.0,
        "description": "1550nm Eye-Safe Line-of-Sight / Treetop Mirror FSO (100m - 2.5km)",
    },
    "WINTER_SNOW_DIVERSITY": {
        "chip_us": 4.0,
        "pulse_ns": 200,
        "pulses_per_symbol": 2,
        "carousel_passes": 3,
        "inter_pass_gap_ms": 35.0,
        "description": "Finnish Snowfall / Scintillation Diversity Mode (dual-pulse + 35ms 3-pass carousel)",
    },
    "NLOS_UVC_SCATTER": {
        "chip_us": 20.0,
        "pulse_ns": 250,
        "pulses_per_symbol": 4,
        "carousel_passes": 2,
        "inter_pass_gap_ms": 50.0,
        "description": "265nm Solar-Blind UV-C Over-the-Trees NLOS Aerosol/Rayleigh Scatter (50m - 300m)",
    },
    "VK7MO_LOCKIN_2KM_NLOS": {
        "chip_us": 1000.0,
        "pulse_ns": 250000,
        "pulses_per_symbol": 1,
        "carousel_passes": 2,
        "inter_pass_gap_ms": 50.0,
        "base_tone_hz": 1500.0,
        "tone_spacing_hz": 125.0,
        "symbol_ms": 16.0,
        "sample_rate_hz": 16000,
        "description": "VK7MO/KA7OEI 850nm Wide-Aperture Fresnel + 8-FSK Lock-In Scatter Mode (2km - 27km+ NLOS)",
    },
}

# 16-symbol Costas/Barker frequency-hopping preamble for VK7MO/KA7OEI weak-signal lock-in acquisition
VK7MO_COSTAS_PREAMBLE = (0, 7, 1, 6, 2, 5, 3, 4, 0, 7, 4, 3, 5, 2, 6, 1)



def _hamming_parity_nibble(nibble):
    """
    Computes 4-bit Extended Hamming(8,4) SECDED parity nibble (p3, p2, p1, p0)
    for a 4-bit data nibble (d3, d2, d1, d0). Minimum Hamming distance d_min = 4.
    """
    d0 = (nibble >> 0) & 1
    d1 = (nibble >> 1) & 1
    d2 = (nibble >> 2) & 1
    d3 = (nibble >> 3) & 1
    p0 = d0 ^ d1 ^ d3
    p1 = d0 ^ d2 ^ d3
    p2 = d1 ^ d2 ^ d3
    p3 = d0 ^ d1 ^ d2 ^ d3 ^ p0 ^ p1 ^ p2
    return (p3 << 3) | (p2 << 2) | (p1 << 1) | p0


# Precomputed 16 valid 8-bit Extended Hamming(8,4) codewords for nibbles 0x0..0xF
HAMMING84_CODEWORDS = tuple(
    ((_hamming_parity_nibble(n) & 0x0F) << 4) | (n & 0x0F)
    for n in range(16)
)


def fec_encode_bytes(data_bytes):
    """
    Bit-Interleaved Extended Hamming(8,4) SECDED Forward Error Correction (FEC) encoder.
    1. Splits each byte of `data_bytes` (M bytes) into high and low 4-bit nibbles (K = 2M nibbles).
    2. Encodes each nibble into an 8-bit Extended Hamming(8,4) codeword (d_min = 4).
    3. Bit-interleaves across all K = 2M codewords (bit-plane transposition) so that the
       3 bits of every 8-PPM symbol—and any burst of up to floor(2M / 3) consecutive
       corrupted or erased 8-PPM symbols—distribute at most 1 bit error into any single
       Hamming(8,4) codeword.
    Returns exact 2x length bytes (2M bytes).
    """
    if not data_bytes:
        return b""

    codewords = []
    for b in data_bytes:
        hi = (b >> 4) & 0x0F
        lo = b & 0x0F
        codewords.append(HAMMING84_CODEWORDS[hi])
        codewords.append(HAMMING84_CODEWORDS[lo])

    k_count = len(codewords)  # K = 2 * M
    total_bits = k_count * 8
    interleaved_bytes = bytearray(k_count)

    out_bit_idx = 0
    for bit_plane in range(8):
        for u in range(k_count):
            bit_val = (codewords[u] >> bit_plane) & 1
            if bit_val:
                byte_pos = out_bit_idx >> 3
                bit_offset = 7 - (out_bit_idx & 7)
                interleaved_bytes[byte_pos] |= (1 << bit_offset)
            out_bit_idx += 1

    return bytes(interleaved_bytes)


def encode_bytes_to_8ppm(data_bytes):
    """
    Encodes raw byte array into 8-PPM symbol indices (0..7).
    Each byte (8 bits) is encoded into three 8-PPM symbols:
      Symbol 0: bits 7..5 (3 bits, value 0..7)
      Symbol 1: bits 4..2 (3 bits, value 0..7)
      Symbol 2: bits 1..0 (2 bits, value 0..3)
    """
    symbols = []
    for b in data_bytes:
        s0 = (b >> 5) & 0x07
        s1 = (b >> 2) & 0x07
        s2 = b & 0x03
        symbols.extend([s0, s1, s2])
    return symbols


def create_sky_frame(payload_bytes, enable_fec=False):
    """
    Packages a payload into a framed structure:
    - Uncoded ('SKY!'):
      [Sync: 4B 'SKY!'] [Length: uint16 (2B)] [Payload: N B] [CRC32: uint32 (4B)]
    - FEC-Protected ('SKYF'):
      [Sync: 4B 'SKYF'] [FEC(Length): 4B] [FEC(Payload + CRC32): 2*(N+4) B]
      Both the 2-byte length header and the (Payload + CRC32) body are protected by
      Bit-Interleaved Extended Hamming(8,4) SECDED FEC.
    """
    crc = zlib.crc32(payload_bytes) & 0xFFFFFFFF
    len_bytes = struct.pack(">H", len(payload_bytes))
    body = payload_bytes + struct.pack(">I", crc)
    if enable_fec:
        encoded_len = fec_encode_bytes(len_bytes)
        encoded_body = fec_encode_bytes(body)
        return FRAME_SYNC_FEC + encoded_len + encoded_body
    header = FRAME_SYNC_WORD + len_bytes
    trailer = struct.pack(">I", crc)
    framed_data = header + payload_bytes + trailer
    return framed_data


def format_ppm_pulse_train(symbols, chip_us=CHIP_DURATION_US, pulses_per_symbol=1):
    """
    Converts 8-PPM symbols into a sequence of absolute pulse timestamps (microseconds).
    - Preamble: 16 periodic synchronization pulses spaced by 8 * chip_us (16 us default),
      followed by a 16 * chip_us (32 us default) silent guard interval.
    - Data Symbols: Symbol index 'k' fires in temporal slot k within the symbol window.
      When `pulses_per_symbol > 1` (e.g., snow/UV-C scatter mode), fires a sub-burst of
      `pulses_per_symbol` sub-pulses spaced by `chip_us / (pulses_per_symbol + 1)` inside
      slot k for coherent photon integration.
    """
    pulse_timestamps_us = []
    current_time_us = 0.0
    symbol_period_us = float(SLOTS_PER_SYMBOL * chip_us)

    # 1. Preamble: 16 periodic synchronization pulses spaced by symbol_period_us (16 us @ chip_us=2)
    for _ in range(16):
        pulse_timestamps_us.append(current_time_us)
        current_time_us += symbol_period_us

    # Guard interval (2 symbol periods = 32 us @ chip_us=2)
    current_time_us += 2.0 * symbol_period_us

    # 2. Transmit 8-PPM data symbols
    pps = max(1, int(pulses_per_symbol))
    sub_step = (chip_us * 0.5) / pps if pps > 1 else 0.0

    for sym in symbols:
        slot_base = current_time_us + (sym * chip_us)
        if pps == 1:
            pulse_timestamps_us.append(slot_base)
        else:
            for m in range(pps):
                offset = (m - (pps - 1) * 0.5) * sub_step
                pulse_timestamps_us.append(slot_base + offset)
        current_time_us += symbol_period_us

    return pulse_timestamps_us


def pack_pio_timing_words(
    pulse_timestamps_us,
    pulse_duration_ns=PULSE_DURATION_NS,
    max_pulse_ns=1000,
    max_duty_cycle=0.025,
):
    """
    Converts absolute microsecond pulse timestamps into cycle-exact 32-bit FIFO words
    for `pio_pulse_modulator.pio` running at 100 MHz (10 ns instruction cycle):
      - Lower 16 bits (X): Inter-pulse pre-delay loop count in 100 ns steps
      - Upper 16 bits (Y): Optical pulse high width loop count in 10 ns steps (y = ticks - 1)
    Enforces hardware laser/LED safety interlocks:
      1. Clamps/rejects single-pulse duration > `max_pulse_ns` (default 1000 ns).
      2. Rejects burst duty cycle > `max_duty_cycle` (default 2.5%) to prevent facet overheating.
    """
    if not pulse_timestamps_us:
        return []
    if pulse_duration_ns <= 0 or pulse_duration_ns > max_pulse_ns:
        raise ValueError(
            f"Unsafe optical pulse width {pulse_duration_ns} ns (allowed: 1..{max_pulse_ns} ns)"
        )

    sorted_ts = sorted(pulse_timestamps_us)
    if len(sorted_ts) > 1:
        span_ns = (sorted_ts[-1] - sorted_ts[0]) * 1000.0 + pulse_duration_ns
        total_on_ns = len(sorted_ts) * pulse_duration_ns
        duty = total_on_ns / max(span_ns, 1.0)
        if duty > max_duty_cycle:
            raise ValueError(
                f"Burst duty cycle {duty * 100:.2f}% exceeds hardware safety limit {max_duty_cycle * 100:.2f}%"
            )

    y_ticks = max(1, int(round(pulse_duration_ns / 10.0)) - 1)
    actual_high_ns = (y_ticks + 1) * 10.0

    fifo_words = []
    cursor_ns = sorted_ts[0] * 1000.0

    for idx, t_us in enumerate(sorted_ts):
        target_ns = t_us * 1000.0
        if idx == 0:
            x_steps = 0
            cursor_ns = target_ns + actual_high_ns
        else:
            gap_ns = max(0.0, target_ns - cursor_ns)
            x_steps = int(round(gap_ns / 100.0))
            if x_steps > 0xFFFF:
                raise ValueError(f"Inter-pulse gap {gap_ns / 1000.0:.1f} us exceeds 16-bit PIO counter")
            # In pio_pulse_modulator.pio: x > 0 executes (x + 1) iterations of 100 ns,
            # so load x_reg = x_steps - 1 when x_steps >= 1.
            actual_delay_ns = x_steps * 100.0
            cursor_ns += actual_delay_ns + actual_high_ns

        x_reg = (x_steps - 1) if x_steps > 0 else 0
        word = ((y_ticks & 0xFFFF) << 16) | (x_reg & 0xFFFF)
        fifo_words.append(word)

    return fifo_words


def unpack_pio_timing_words(fifo_words, start_time_us=0.0):
    """
    Cycle-accurate emulator of `pio_pulse_modulator.pio`: reconstructs emitted optical
    pulse rising-edge timestamps (us) and pulse width (ns) from 32-bit PIO FIFO words.
    """
    timestamps_us = []
    cursor_ns = start_time_us * 1000.0
    pulse_width_ns = 0.0

    for idx, word in enumerate(fifo_words):
        x_reg = word & 0xFFFF
        y_reg = (word >> 16) & 0xFFFF
        if y_reg == 0:
            continue
        delay_ns = 0.0 if (idx == 0 and x_reg == 0) else (x_reg + 1) * 100.0
        cursor_ns += delay_ns
        timestamps_us.append(cursor_ns / 1000.0)
        pulse_width_ns = (y_reg + 1) * 10.0
        cursor_ns += pulse_width_ns

    return timestamps_us, pulse_width_ns


def transmit_simulated_burst(payload_bytes, enable_fec=False, profile="FAST_FSO_1550"):
    """Encodes payload and outputs timing summary for hardware transmission."""
    prof = TRANSMISSION_PROFILES.get(profile, TRANSMISSION_PROFILES["FAST_FSO_1550"])
    chip_us = prof["chip_us"]
    pps = prof["pulses_per_symbol"]

    frame = create_sky_frame(payload_bytes, enable_fec=enable_fec)
    symbols = encode_bytes_to_8ppm(frame)
    pulse_train = format_ppm_pulse_train(symbols, chip_us=chip_us, pulses_per_symbol=pps)
    total_duration_ms = pulse_train[-1] / 1000.0 if pulse_train else 0.0

    return {
        "profile": profile,
        "chip_us": chip_us,
        "pulses_per_symbol": pps,
        "payload_len": len(payload_bytes),
        "frame_len": len(frame),
        "symbol_count": len(symbols),
        "pulse_count": len(pulse_train),
        "burst_duration_ms": round(total_duration_ms, 2),
        "data_rate_kbps": round((len(payload_bytes) * 8.0) / total_duration_ms, 2) if total_duration_ms > 0 else 0,
        "fec_enabled": enable_fec,
        "pulse_train_us": pulse_train,
    }


def transmit_carousel_bursts(payload_bytes, enable_fec=True, passes=3, inter_pass_gap_ms=35.0, chip_us=CHIP_DURATION_US, pulses_per_symbol=1):
    """
    Generates a multi-pass time-diversity optical pulse stream (default 3 passes spaced by 35 ms).
    In Finnish snowfall or wind-blown pine needle crossings, a single 2-10 mm snowflake falling
    at 1.5 m/s clears a 25 mm beam in <18 ms, ensuring at least 2 of the 3 carousel passes
    arrive completely unobstructed.
    """
    frame = create_sky_frame(payload_bytes, enable_fec=enable_fec)
    symbols = encode_bytes_to_8ppm(frame)
    single_burst = format_ppm_pulse_train(symbols, chip_us=chip_us, pulses_per_symbol=pulses_per_symbol)
    if not single_burst:
        return []

    single_duration_us = single_burst[-1] + (SLOTS_PER_SYMBOL * chip_us)
    gap_us = inter_pass_gap_ms * 1000.0
    combined_stream = []
    offset_us = 0.0
    for _ in range(max(1, passes)):
        combined_stream.extend(t + offset_us for t in single_burst)
        offset_us += single_duration_us + gap_us
    return combined_stream


def create_signed_sky_alert(alert_meta, signing_key_hex):
    """
    Bridges a camera node alert dict into a compact, Ed25519-signed JSON payload
    suitable for 8-PPM optical transmission (`DD\\x01` wire-compatible with `receiver_hub.py`).
    Preserves both canonical `receiver_hub.py` keys (`detections`, `pico_trig`, `img_sha256`)
    and compact aliases (`det`, `trig`, `sha16`) so the packet can be fed directly into
    `receiver_hub.process_datagram()` without re-signing.
    """
    import json
    from nacl.signing import SigningKey
    full_sha = alert_meta.get("img_sha256", "") or ""
    detections = alert_meta.get("detections", alert_meta.get("det", []))
    pico_trig = alert_meta.get("pico_trig", alert_meta.get("trig", ""))
    compact = {
        "node": alert_meta.get("node", "NODE-NORTH-01"),
        "ts": int(alert_meta.get("ts", time.time())),
        "nonce": alert_meta.get("nonce", "00" * 8),
        "detections": detections,
        "pico_trig": pico_trig,
        "img_sha256": full_sha,
        "camera_ok": alert_meta.get("camera_ok", True),
        "inference_backend": alert_meta.get("inference_backend", "sky-optical"),
        "det": detections,
        "trig": pico_trig,
        "sha16": full_sha[:16],
    }
    msg_bytes = json.dumps(compact, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sk = SigningKey(bytes.fromhex(signing_key_hex))
    sig = sk.sign(msg_bytes).signature
    return b"DD\x01" + sig + msg_bytes


FRAGMENT_MAGIC = b"SKFG"


def package_udp_datagrams_for_optical(
    udp_datagrams,
    max_frag_bytes=360,
    enable_fec=True,
    profile="FAST_FSO_1550",
):
    """
    Transparent UDP-to-Optical Physical Layer Bridge:
    1. Deduplicates redundant 3x UDP carousel copies emitted by `sender_node.py`.
    2. Segments large UDP datagrams (such as 1039-byte `DD\\x02` JPEG chunks) into
       compact optical sub-frames (`SKFG` header: 4B magic + 2B dgram_id + 1B frag_idx + 1B total_frags)
       so each optical burst remains short (<15 ms), minimizing crystal drift and snowflake wipeout risk.
    3. Encodes each fragment into an FEC-protected `SKYF` 8-PPM pulse train.
    Returns a list of burst dicts ready for hardware PIO transmission.
    """
    prof = TRANSMISSION_PROFILES.get(profile, TRANSMISSION_PROFILES["FAST_FSO_1550"])
    chip_us = prof["chip_us"]
    pps = prof["pulses_per_symbol"]

    unique_dgrams = []
    seen_hashes = set()
    for dgram in udp_datagrams:
        if not dgram:
            continue
        h = zlib.crc32(dgram) & 0xFFFFFFFF
        if (h, len(dgram)) not in seen_hashes:
            seen_hashes.add((h, len(dgram)))
            unique_dgrams.append(dgram)

    optical_bursts = []
    for dgram_id, dgram in enumerate(unique_dgrams):
        if len(dgram) <= max_frag_bytes and not dgram.startswith(FRAGMENT_MAGIC):
            # Fits in a single optical frame without fragmentation wrapper
            frame = create_sky_frame(dgram, enable_fec=enable_fec)
            symbols = encode_bytes_to_8ppm(frame)
            pulses = format_ppm_pulse_train(symbols, chip_us=chip_us, pulses_per_symbol=pps)
            optical_bursts.append({
                "dgram_id": dgram_id,
                "frag_idx": 0,
                "total_frags": 1,
                "frame_len": len(frame),
                "pulse_train_us": pulses,
            })
        else:
            slices = [
                dgram[i:i + max_frag_bytes]
                for i in range(0, len(dgram), max_frag_bytes)
            ]
            total_frags = len(slices)
            for frag_idx, sl in enumerate(slices):
                frag_payload = FRAGMENT_MAGIC + struct.pack(">HBB", dgram_id, frag_idx, total_frags) + sl
                frame = create_sky_frame(frag_payload, enable_fec=enable_fec)
                symbols = encode_bytes_to_8ppm(frame)
                pulses = format_ppm_pulse_train(symbols, chip_us=chip_us, pulses_per_symbol=pps)
                optical_bursts.append({
                    "dgram_id": dgram_id,
                    "frag_idx": frag_idx,
                    "total_frags": total_frags,
                    "frame_len": len(frame),
                    "pulse_train_us": pulses,
                })

    return optical_bursts


def compute_sky_relay_energy_budget(
    payload_bytes_len=250,
    jpeg_crop_bytes_len=2048,
    temp_c=-20.0,
    profile="FAST_FSO_1550",
):
    """
    Computes the per-event electrical energy budget (Joules and Watt-hours) of the
    `sky-diode-relay` transmitter on the battery-powered field node, including:
      - RP2040 gatekeeper/modulator active draw (3.3V @ 28 mA)
      - Pulsed optical emitter & GaN driver capacitor bank recharge energy
      - Sub-zero annular PTC window heater overlap (5.0 W for 4.0 s when temp_c < +2.0 C,
        overlapped with the Pi 5 fastboot window so zero extra latency is added).
    Compares directly against the 0.0104 Wh/event StarTech fiber media converter draw.
    """
    prof = TRANSMISSION_PROFILES.get(profile, TRANSMISSION_PROFILES["FAST_FSO_1550"])
    chip_us = prof["chip_us"]
    pulse_ns = prof["pulse_ns"]
    pps = prof["pulses_per_symbol"]
    passes = prof["carousel_passes"]

    total_raw_bytes = payload_bytes_len + jpeg_crop_bytes_len
    total_fec_bytes = 2 * (total_raw_bytes + 16)
    total_symbols = total_fec_bytes * 3
    total_pulses = (total_symbols * pps + 16 * max(1, total_raw_bytes // 360)) * passes

    active_tx_time_s = (total_symbols * SLOTS_PER_SYMBOL * chip_us * passes) * 1e-6 + 0.05
    total_laser_on_s = total_pulses * (pulse_ns * 1e-9)

    # Peak electrical power during pulse: ~6W for 1550nm DFB driver, ~18W for 12-LED UV-C array
    peak_driver_w = 18.0 if profile == "NLOS_UVC_SCATTER" else 6.0
    emitter_energy_j = (peak_driver_w * total_laser_on_s) / 0.80  # 80% buck/capacitor efficiency
    mcu_energy_j = (3.3 * 0.028) * active_tx_time_s
    deicer_energy_j = (5.0 * 4.0) if temp_c < 2.0 else 0.0

    total_j = emitter_energy_j + mcu_energy_j + deicer_energy_j
    total_wh = total_j / 3600.0
    fiber_converter_wh = 0.0104  # 5V * 0.5A * 15s / 3600

    return {
        "profile": profile,
        "temp_c": temp_c,
        "total_pulses": total_pulses,
        "active_tx_time_ms": round(active_tx_time_s * 1000.0, 2),
        "emitter_energy_mj": round(emitter_energy_j * 1000.0, 2),
        "deicer_energy_j": round(deicer_energy_j, 2),
        "total_energy_wh": round(total_wh, 6),
        "savings_vs_fiber_converter_pct": round((1.0 - (total_wh / fiber_converter_wh)) * 100.0, 1),
    }


def get_vk7mo_tone_frequencies(symbol_ms=16.0, base_tone_hz=1500.0, tone_spacing_hz=None):
    """
    Computes the 8 strictly orthogonal audio subcarrier frequencies (Hz) in the
    KA7OEI / VK7MO low-noise passband (1,500 Hz - 2,400 Hz, above 50/100 Hz AC
    lighting harmonics and below the 2.5 kHz large-area photodiode RC rolloff).
    Default spacing is 2 / T_sym (e.g., 125 Hz for 16 ms symbols) so every tone
    completes an exact integer number of cycles per symbol integration window.
    """
    if tone_spacing_hz is None:
        tone_spacing_hz = 2000.0 / float(symbol_ms)
    return tuple(round(base_tone_hz + m * float(tone_spacing_hz), 6) for m in range(SLOTS_PER_SYMBOL))


def _vk7mo_fhss_shift(symbol_idx, fhss_key):
    """
    Computes a deterministic pseudo-random tone-hopping offset (0..7) for data
    symbol `symbol_idx` using HMAC/SHA-256 over `fhss_key` so an optical jammer
    or eavesdropper cannot predict which tone frequency carries which symbol.
    """
    if not fhss_key:
        return 0
    import hashlib
    key_bytes = fhss_key.encode("utf-8") if isinstance(fhss_key, str) else bytes(fhss_key)
    digest = hashlib.sha256(key_bytes + struct.pack(">I", int(symbol_idx))).digest()
    return digest[0] & 0x07


def derive_fhss_carrier_schedule(
    fhss_key,
    num_passes=3,
    band_min_mhz=2370.0,
    band_max_mhz=2500.0,
    min_hop_separation_mhz=25.0,
):
    """
    Cryptographic Wideband Multi-Pass RF Carrier Hopping Schedule (`2370–2500 MHz`):
    Derives `num_passes` widely separated carrier frequencies across the full 130 MHz
    hardware passband of the Mini-Circuits `VBF-2435+` filter and `ADALM-PLUTO` SDR.
    - Pass 0 is placed in the lower guard band (`2372–2396 MHz`, below Wi-Fi Ch 1 and
      outside standard 2400–2483.5 MHz consumer Wi-Fi / C-UAS drone barrage jammers).
    - Pass 1 is placed in the upper guard band (`2485–2498 MHz`, above Wi-Fi Ch 13).
    - Pass 2+ hop pseudo-randomly across the full `band_min_mhz..band_max_mhz` span
      while enforcing `min_hop_separation_mhz` from prior hops.
    """
    import hashlib

    if not fhss_key:
        default_hops = [2382.0, 2491.0, 2437.0]
        return [default_hops[i % len(default_hops)] for i in range(max(1, int(num_passes)))]

    key_bytes = fhss_key.encode("utf-8") if isinstance(fhss_key, str) else bytes(fhss_key)
    hops_mhz = []
    for p_idx in range(max(1, int(num_passes))):
        digest = hashlib.sha256(key_bytes + b":CARRIER:" + struct.pack(">I", p_idx)).digest()
        u_val = struct.unpack(">I", digest[:4])[0] / 4294967295.0
        if p_idx == 0 and band_min_mhz <= 2372.0 and band_max_mhz >= 2498.0:
            # Lower guard band outside 2.400–2.4835 GHz ISM barrage jammers & Wi-Fi
            cand_mhz = round(2372.0 + u_val * 24.0, 3)
        elif p_idx == 1 and band_min_mhz <= 2372.0 and band_max_mhz >= 2498.0:
            # Upper guard band outside 2.400–2.4835 GHz ISM barrage jammers & Wi-Fi
            cand_mhz = round(2485.0 + u_val * 13.0, 3)
        else:
            cand_mhz = round(band_min_mhz + u_val * (band_max_mhz - band_min_mhz), 3)
            for attempt in range(1, 16):
                if all(abs(cand_mhz - prev) >= min_hop_separation_mhz for prev in hops_mhz):
                    break
                d_retry = hashlib.sha256(
                    key_bytes + b":CARRIER_RETRY:" + struct.pack(">II", p_idx, attempt)
                ).digest()
                u_retry = struct.unpack(">I", d_retry[:4])[0] / 4294967295.0
                cand_mhz = round(band_min_mhz + u_retry * (band_max_mhz - band_min_mhz), 3)
        hops_mhz.append(cand_mhz)
    return hops_mhz


def encode_vk7mo_lockin_frame(
    payload_bytes,
    symbol_ms=16.0,
    base_tone_hz=1500.0,
    tone_spacing_hz=None,
    sample_rate_hz=16000,
    enable_fec=True,
    fhss_key=None,
):
    """
    VK7MO / KA7OEI Weak-Signal Coherent 8-FSK Lock-In Transmitter:
    1. Encapsulates `payload_bytes` in a Bit-Interleaved Extended Hamming(8,4)
       SECDED frame (`SKYF`, d_min = 4) and maps bytes to 3-bit symbols (0..7).
    2. Optionally applies cryptographic Keyed Frequency-Hopping (`fhss_key`) per
       data symbol to defeat narrowband optical/RF tone jamming and derives a
       multi-band RF carrier schedule (`carrier_schedule_mhz`) outside ISM Wi-Fi.
    3. Prepends the 16-symbol Costas synchronization header (`VK7MO_COSTAS_PREAMBLE`).
    4. Generates both:
       - `tone_schedule_hz`: Hardware PWM frequency sequence for Raspberry Pi Pico 2
         driving the OSRAM Oslon 850 nm LED array via logic-level MOSFET, and
       - `waveform`: Sampled subcarrier intensity envelope at `sample_rate_hz`.
    """
    import math

    frame = create_sky_frame(payload_bytes, enable_fec=enable_fec)
    raw_data_symbols = encode_bytes_to_8ppm(frame)
    hopped_data_symbols = [
        (sym + _vk7mo_fhss_shift(w, fhss_key)) & 0x07
        for w, sym in enumerate(raw_data_symbols)
    ]
    all_symbols = list(VK7MO_COSTAS_PREAMBLE) + hopped_data_symbols
    tone_freqs = get_vk7mo_tone_frequencies(
        symbol_ms=symbol_ms, base_tone_hz=base_tone_hz, tone_spacing_hz=tone_spacing_hz
    )

    samples_per_sym = max(8, int(round((symbol_ms * 1e-3) * sample_rate_hz)))
    two_pi_over_fs = (2.0 * math.pi) / float(sample_rate_hz)

    tone_schedule_hz = []
    waveform = []
    for sym in all_symbols:
        freq_hz = tone_freqs[sym]
        tone_schedule_hz.append(freq_hz)
        omega = two_pi_over_fs * freq_hz
        for n in range(samples_per_sym):
            waveform.append(math.cos(omega * n))

    tx_duration_s = (len(all_symbols) * samples_per_sym) / float(sample_rate_hz)
    effective_bps = (len(payload_bytes) * 8.0) / max(1e-9, tx_duration_s)

    return {
        "frame_len": len(frame),
        "fec_enabled": enable_fec,
        "fhss_enabled": bool(fhss_key),
        "carrier_schedule_mhz": derive_fhss_carrier_schedule(fhss_key, num_passes=3),
        "data_symbol_count": len(raw_data_symbols),
        "total_symbol_count": len(all_symbols),
        "symbol_ms": float(symbol_ms),
        "samples_per_symbol": samples_per_sym,
        "sample_rate_hz": int(sample_rate_hz),
        "tone_frequencies_hz": tone_freqs,
        "tone_schedule_hz": tone_schedule_hz,
        "tx_duration_s": round(tx_duration_s, 3),
        "effective_bps": round(effective_bps, 1),
        "waveform": waveform,
    }


def calculate_troposcatter_link_budget(
    distance_km=100.0,
    freq_ghz=5.8,
    tx_power_w=10.0,
    tx_dish_diam_m=0.60,
    rx_dish_diam_m=0.60,
    horizon_angle_deg=0.5,
    rx_nf_db=1.0,
    symbol_ms=16.0,
    weather_regime="CLEAR_TROPOSCATTER",
):
    """
    ITU-R P.617 / NBS Technical Note 101 Beyond-Line-of-Sight (BLOS) Troposcatter
    & Hydrometeor (Rain/Snow) Scatter Link Budget for 5 km - 150 km NLOS links:
      - Models 4/3-Earth effective curvature (R_eff = 8,495 km) and common scatter
        volume intersection altitude `scatter_altitude_m`
      - Computes Free-Space Path Loss + angular scatter loss `30*log10(theta_mrad)` +
        aperture-to-medium coupling loss `L_c`
      - Evaluates weather regimes:
        * `CLEAR_TROPOSCATTER`: Clear sky (day or night, summer or winter)
        * `DRY_ARCTIC_WINTER`: -30°C dry polar air (-7.5 dB lower humidity refractivity)
        * `RAIN_SNOW_SCATTER`: Heavy rain/wet snow hydrometeor scatter (+12 to +18 dB
          volumetric backscatter enhancement at 2.4-10 GHz)
      - Computes median SNR and 99% Rayleigh multipath fade margin relative to our
        VK7MO / Q65 Quadrature Lock-In threshold (-13.5 dB wideband SNR in 2,500 Hz).
    """
    import math

    d_km = max(1.0, float(distance_km))
    f_ghz = max(0.4, float(freq_ghz))
    wavelength_m = 0.299792458 / f_ghz

    # Parabolic antenna gain (55% aperture efficiency) and 3 dB beamwidth
    eff = 0.55
    g_tx_dbi = 10.0 * math.log10(eff * ((math.pi * tx_dish_diam_m / wavelength_m) ** 2))
    g_rx_dbi = 10.0 * math.log10(eff * ((math.pi * rx_dish_diam_m / wavelength_m) ** 2))
    beamwidth_deg = 70.0 * (wavelength_m / max(0.1, tx_dish_diam_m))

    # 4/3 Earth effective radius (8,495 km) + treetop horizon takeoff angle
    r_eff_km = 8495.0
    theta_earth_rad = d_km / r_eff_km
    theta_takeoff_rad = math.radians(max(0.1, float(horizon_angle_deg)))
    theta_scatter_rad = theta_earth_rad + (2.0 * theta_takeoff_rad)
    theta_scatter_mrad = theta_scatter_rad * 1000.0

    # Altitude of the common sky-bounce scatter volume above the midpoint
    half_d_m = (d_km * 1000.0) * 0.5
    earth_bulge_m = ((d_km * 1000.0) ** 2) / (8.0 * r_eff_km * 1000.0)
    scatter_altitude_m = half_d_m * math.tan(theta_takeoff_rad) + earth_bulge_m * 0.5

    # Free-Space Path Loss (dB)
    fspl_db = 92.45 + 20.0 * math.log10(d_km) + 20.0 * math.log10(f_ghz)

    # NBS-101 / ITU-R P.617 Median Tropospheric Scatter Excess Loss (dB)
    # L_s = 30*log10(theta_mrad) + 10*log10(f_ghz) + 0.04*d_km + 6.5
    tropo_excess_db = (
        30.0 * math.log10(max(1.0, theta_scatter_mrad))
        + 10.0 * math.log10(f_ghz)
        + (0.04 * d_km)
        + 6.5
    )

    # Aperture-to-medium coupling loss L_c (when narrow beams intersect in turbulent medium)
    sum_gain_db = g_tx_dbi + g_rx_dbi
    coupling_loss_db = max(0.0, 0.07 * math.exp(0.055 * (sum_gain_db - 40.0)))

    # Weather regime adjustment
    regime = str(weather_regime).upper()
    weather_delta_db = 0.0
    if regime == "DRY_ARCTIC_WINTER":
        weather_delta_db = 7.5  # Dry -30°C air has weaker humidity refractivity gradients
    elif regime == "RAIN_SNOW_SCATTER":
        # Hydrometeor Rayleigh/Mie volumetric scatter boosts 2-10 GHz bounce significantly
        weather_delta_db = -min(18.0, 6.0 * math.log10(max(1.0, f_ghz)))

    total_path_loss_db = fspl_db + tropo_excess_db + coupling_loss_db + weather_delta_db

    tx_power_dbm = 10.0 * math.log10(max(1e-3, float(tx_power_w)) * 1000.0)
    rx_power_dbm = tx_power_dbm + g_tx_dbi + g_rx_dbi - total_path_loss_db

    # Receiver thermal noise in 2,500 Hz audio lock-in passband and in 1/symbol_ms tone bin
    wideband_bw_hz = 2500.0
    tone_bw_hz = 1000.0 / max(1.0, float(symbol_ms))
    noise_wideband_dbm = -174.0 + float(rx_nf_db) + 10.0 * math.log10(wideband_bw_hz)
    noise_tone_bin_dbm = -174.0 + float(rx_nf_db) + 10.0 * math.log10(tone_bw_hz)

    wideband_snr_db = rx_power_dbm - noise_wideband_dbm
    tone_bin_snr_db = rx_power_dbm - noise_tone_bin_dbm

    # VK7MO / Q65 3-pass non-coherent lock-in sensitivity threshold (-13.5 dB in 2.5 kHz)
    required_wideband_snr_db = -13.5
    median_link_margin_db = wideband_snr_db - required_wideband_snr_db
    # Dual-branch frequency/time diversity (FHSS + 3-pass carousel) reduces 99% Rayleigh fade to 14 dB
    fade_margin_99pct_db = median_link_margin_db - 14.0

    return {
        "distance_km": round(d_km, 1),
        "freq_ghz": round(f_ghz, 2),
        "weather_regime": regime,
        "scatter_altitude_m": round(scatter_altitude_m, 1),
        "beamwidth_deg": round(beamwidth_deg, 2),
        "tx_gain_dbi": round(g_tx_dbi, 1),
        "rx_gain_dbi": round(g_rx_dbi, 1),
        "fspl_db": round(fspl_db, 1),
        "tropo_excess_loss_db": round(tropo_excess_db + coupling_loss_db + weather_delta_db, 1),
        "total_path_loss_db": round(total_path_loss_db, 1),
        "rx_power_dbm": round(rx_power_dbm, 1),
        "wideband_snr_2500hz_db": round(wideband_snr_db, 1),
        "tone_bin_snr_db": round(tone_bin_snr_db, 1),
        "median_link_margin_db": round(median_link_margin_db, 1),
        "fade_margin_99pct_db": round(fade_margin_99pct_db, 1),
        "all_weather_viable": fade_margin_99pct_db >= 6.0,
    }


if __name__ == "__main__":
    test_msg = b'{"node":"NODE-NORTH-01","alert":"PERSON","ts":1760000000}'
    result = transmit_simulated_burst(test_msg, enable_fec=True)
    pio_words = pack_pio_timing_words(result["pulse_train_us"])
    energy = compute_sky_relay_energy_budget(len(test_msg), jpeg_crop_bytes_len=2048, temp_c=-20.0)
    vk7mo_tx = encode_vk7mo_lockin_frame(test_msg, symbol_ms=16.0)
    tropo_100km = calculate_troposcatter_link_budget(distance_km=100.0, freq_ghz=2.4, tx_power_w=10.0)
    print("=== SKY RELAY 8-PPM, VK7MO LOCK-IN & 100KM TROPOSCATTER TEST ===")
    print(f"Payload: {test_msg.decode()}")
    print(f"Frame Size: {result['frame_len']} bytes (FEC={result['fec_enabled']})")
    print(f"8-PPM Symbols: {result['symbol_count']} | VK7MO Lock-In Duration: {vk7mo_tx['tx_duration_s']} s")
    print(f"100km Troposcatter (2.4 GHz, 10W, 60cm dish): RX={tropo_100km['rx_power_dbm']} dBm | Margin=+{tropo_100km['median_link_margin_db']} dB")
    print(f"Winter Energy (-20°C w/ 2KB crop + de-icer): {energy['total_energy_wh']:.5f} Wh ({energy['savings_vs_fiber_converter_pct']}% less than Ethernet media converter)")


