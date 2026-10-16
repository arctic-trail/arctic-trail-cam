#!/usr/bin/env python3
"""
File: sky-diode-relay/receiver/sky_receiver.py
Description: Production-Hardened Pulse Position Modulation (8-PPM) Photon Counting Receiver
             with O(N log N) Full-Stream Comb Correlator, Decision-Directed Delay-Locked Loop
             (DLL) Clock Recovery, Erasure-Aware Bit-Interleaved Extended Hamming(8,4) FEC,
             Multi-Pass Snowflake Carousel Combining, and Collector Hub Bridge.
License: MIT
"""
import bisect
import struct
import zlib

FRAME_SYNC_WORD = b"SKY!"
FRAME_SYNC_FEC  = b"SKYF"
CHIP_DURATION_US = 2
SLOTS_PER_SYMBOL = 8
SYMBOL_PERIOD_US = SLOTS_PER_SYMBOL * CHIP_DURATION_US  # 16 us


def _hamming_parity_nibble(nibble):
    """Computes 4-bit Extended Hamming(8,4) SECDED parity nibble (p3, p2, p1, p0)."""
    d0 = (nibble >> 0) & 1
    d1 = (nibble >> 1) & 1
    d2 = (nibble >> 2) & 1
    d3 = (nibble >> 3) & 1
    p0 = d0 ^ d1 ^ d3
    p1 = d0 ^ d2 ^ d3
    p2 = d1 ^ d2 ^ d3
    p3 = d0 ^ d1 ^ d2 ^ d3 ^ p0 ^ p1 ^ p2
    return (p3 << 3) | (p2 << 2) | (p1 << 1) | p0


HAMMING84_CODEWORDS = tuple(
    ((_hamming_parity_nibble(n) & 0x0F) << 4) | (n & 0x0F)
    for n in range(16)
)

_POPCOUNT8 = tuple(bin(i).count("1") for i in range(256))


def _decode_hamming84_codeword(rx_cw, erase_mask=0):
    """
    Maximum-Likelihood Minimum-Distance decoder for an 8-bit Extended Hamming(8,4) codeword.
    - `erase_mask` (8-bit int): bit positions set to 1 are known erasures (ignored in distance).
    - Corrects any single bit error (0 erasures), 1 bit error + 1 erasure, or up to 3 erasures.
    """
    active_bits = (~erase_mask) & 0xFF
    best_nibble = rx_cw & 0x0F
    best_dist = 99
    for nib, valid_cw in enumerate(HAMMING84_CODEWORDS):
        diff = (rx_cw ^ valid_cw) & active_bits
        dist = _POPCOUNT8[diff]
        if dist < best_dist:
            best_dist = dist
            best_nibble = nib
            if dist == 0:
                break
    return best_nibble


def fec_decode_bytes(encoded_bytes, erased_mask_bytes=None):
    """
    Decodes Bit-Interleaved Extended Hamming(8,4) SECDED FEC buffer.
    Input format: `encoded_bytes` of length 2M bytes (representing K = 2M interleaved codewords).
    Optional `erased_mask_bytes` (length 2M bytes): bitmask where 1 indicates a bit belonging
    to an erased 8-PPM symbol window (zero detected photons).
    Automatically repairs:
      - Any single 8-PPM symbol error or erasure (including 3-bit `0b111 -> 0b000` flips)
      - Any burst of up to floor(2M / 3) consecutive corrupted 8-PPM symbols
      - Any burst of up to 2M consecutive erased 8-PPM symbols when `erased_mask_bytes` is supplied.
    """
    if not encoded_bytes:
        return b""

    k_count = len(encoded_bytes)
    if k_count % 2 != 0:
        k_count -= 1
    if k_count <= 0:
        return b""

    rx_codewords = [0] * k_count
    erase_codewords = [0] * k_count
    has_erasures = (
        erased_mask_bytes is not None and len(erased_mask_bytes) >= k_count
    )

    in_bit_idx = 0
    for bit_plane in range(8):
        for u in range(k_count):
            byte_pos = in_bit_idx >> 3
            bit_offset = 7 - (in_bit_idx & 7)
            if (encoded_bytes[byte_pos] >> bit_offset) & 1:
                rx_codewords[u] |= (1 << bit_plane)
            if has_erasures and ((erased_mask_bytes[byte_pos] >> bit_offset) & 1):
                erase_codewords[u] |= (1 << bit_plane)
            in_bit_idx += 1

    m_bytes = k_count // 2
    corrected = bytearray(m_bytes)
    for i in range(m_bytes):
        c_hi = _decode_hamming84_codeword(rx_codewords[2 * i], erase_codewords[2 * i])
        c_lo = _decode_hamming84_codeword(rx_codewords[2 * i + 1], erase_codewords[2 * i + 1])
        corrected[i] = ((c_hi & 0x0F) << 4) | (c_lo & 0x0F)

    return bytes(corrected)


def decode_8ppm_symbols_to_bytes(symbols):
    """
    Decodes a stream of 8-PPM symbols (0..7) back into raw bytes.
    Every group of 3 symbols reconstructs one byte:
      Byte = (s0 << 5) | (s1 << 2) | s2
    """
    decoded_bytes = bytearray()
    i = 0
    while i + 2 < len(symbols):
        s0 = symbols[i] & 0x07
        s1 = symbols[i + 1] & 0x07
        s2 = symbols[i + 2] & 0x03
        b = (s0 << 5) | (s1 << 2) | s2
        decoded_bytes.append(b)
        i += 3
    return bytes(decoded_bytes)


def decode_8ppm_symbols_with_erasures(symbols, erased_symbol_indices):
    """
    Decodes 8-PPM symbols into `(raw_bytes, erased_mask_bytes)` where `erased_mask_bytes`
    marks the exact bit positions (7..5 for s0, 4..2 for s1, 1..0 for s2) of any symbol
    window that suffered a pulse erasure (zero detected photons).
    """
    decoded_bytes = bytearray()
    erased_mask = bytearray()
    erased_set = set(erased_symbol_indices or ())
    i = 0
    while i + 2 < len(symbols):
        s0 = symbols[i] & 0x07
        s1 = symbols[i + 1] & 0x07
        s2 = symbols[i + 2] & 0x03
        decoded_bytes.append((s0 << 5) | (s1 << 2) | s2)

        m = 0
        if i in erased_set:
            m |= 0b11100000
        if (i + 1) in erased_set:
            m |= 0b00011100
        if (i + 2) in erased_set:
            m |= 0b00000011
        erased_mask.append(m)
        i += 3
    return bytes(decoded_bytes), bytes(erased_mask)


def _sync_hamming_distance(a_bytes, b_bytes):
    if len(a_bytes) != len(b_bytes):
        return 32
    return sum(_POPCOUNT8[x ^ y] for x, y in zip(a_bytes, b_bytes))


def _acquire_preamble_all_candidates(sorted_pulses, chip_us=CHIP_DURATION_US, min_matches=10):
    """
    O(N log N) binary-search sliding-window comb correlator across the ENTIRE pulse stream.
    Finds all candidate preamble locks `(t0_est, data_start_us, period_est_us, sync_dist)`
    even after thousands of continuous background/solar noise pulses and under +/-500 ppm
    independent crystal clock skew.
    """
    n_pulses = len(sorted_pulses)
    if n_pulses < min_matches:
        return []

    nom_period = float(SLOTS_PER_SYMBOL * chip_us)
    tolerance_us = min(0.85, chip_us * 0.42)
    quick_tol = tolerance_us + 0.015 * nom_period

    raw_candidates = []
    seen_t0_buckets = set()

    for idx in range(n_pulses):
        p_anchor = sorted_pulses[idx]

        # Fast O(log N) pre-check: must have at least one pulse ~1, 2, or 3 periods ahead
        has_comb_neighbor = False
        for step in (1, 2, 3):
            target = p_anchor + step * nom_period
            pos = bisect.bisect_left(sorted_pulses, target - quick_tol, idx + 1)
            if pos < n_pulses and sorted_pulses[pos] <= target + quick_tol:
                has_comb_neighbor = True
                break
        if not has_comb_neighbor:
            continue

        for k_anchor in range(7):
            cand_t0 = p_anchor - (k_anchor * nom_period)
            bucket = int(round(cand_t0 / (tolerance_us * 0.5)))
            if bucket in seen_t0_buckets:
                continue

            matched_m = []
            matched_p = []
            residuals = 0.0

            for m in range(16):
                expected_t = cand_t0 + (m * nom_period)
                lo_idx = bisect.bisect_left(sorted_pulses, expected_t - tolerance_us)
                best_p = None
                best_diff = None
                j = lo_idx
                while j < n_pulses and sorted_pulses[j] <= expected_t + tolerance_us:
                    diff = abs(sorted_pulses[j] - expected_t)
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        best_p = sorted_pulses[j]
                    j += 1
                if best_p is not None:
                    matched_m.append(m)
                    matched_p.append(best_p)
                    residuals += best_diff

            match_count = len(matched_m)
            if match_count >= min_matches:
                seen_t0_buckets.add(bucket)
                # Least-squares linear fit: p_i = t0_fit + m_i * period_fit
                mean_m = sum(matched_m) / match_count
                mean_p = sum(matched_p) / match_count
                var_m = sum((m - mean_m) ** 2 for m in matched_m)
                if var_m > 10.0:
                    cov_mp = sum((m - mean_m) * (p - mean_p) for m, p in zip(matched_m, matched_p))
                    period_fit = cov_mp / var_m
                    # Clamp to +/- 500 ppm around nominal crystal period
                    period_est = max(nom_period * 0.9995, min(nom_period * 1.0005, period_fit))
                else:
                    period_est = nom_period

                t0_est = mean_p - mean_m * period_est
                fit_residuals = sum(
                    abs(p - (t0_est + m * period_est))
                    for m, p in zip(matched_m, matched_p)
                )

                guard_lo = t0_est + 15.125 * period_est
                guard_hi = t0_est + 17.875 * period_est
                g_start = bisect.bisect_left(sorted_pulses, guard_lo)
                g_end = bisect.bisect_right(sorted_pulses, guard_hi)
                guard_pulses = max(0, g_end - g_start)

                raw_candidates.append((match_count, -guard_pulses, -fit_residuals, t0_est, period_est))

    if not raw_candidates:
        return []

    raw_candidates.sort(key=lambda c: (-c[0], -c[1], -c[2]))

    verified_locks = []
    for match_count, neg_guard, neg_res, t0_cand, period_cand in raw_candidates:
        chip_cand = period_cand / SLOTS_PER_SYMBOL
        half_chip = chip_cand * 0.5
        data_start = t0_cand + 18.0 * period_cand

        sync_syms = []
        for w in range(12):
            win_start = data_start + (w * period_cand)
            win_lo = win_start - half_chip
            win_hi = win_start + period_cand - half_chip
            i_lo = bisect.bisect_left(sorted_pulses, win_lo)
            i_hi = bisect.bisect_right(sorted_pulses, win_hi)
            in_win = sorted_pulses[i_lo:i_hi]
            if not in_win:
                sync_syms.append(0)
            else:
                best_slot = 0
                best_err = float("inf")
                for p_time in in_win:
                    raw_slot = (p_time - win_start) / chip_cand
                    slot_cand = max(0, min(SLOTS_PER_SYMBOL - 1, int(round(raw_slot))))
                    err = abs(raw_slot - slot_cand)
                    if err < best_err:
                        best_err = err
                        best_slot = slot_cand
                sync_syms.append(best_slot)

        sync_bytes = decode_8ppm_symbols_to_bytes(sync_syms)
        dist_std = _sync_hamming_distance(sync_bytes, FRAME_SYNC_WORD)
        dist_fec = _sync_hamming_distance(sync_bytes, FRAME_SYNC_FEC)
        min_sync_dist = min(dist_std, dist_fec)
        verified_locks.append((min_sync_dist, -match_count, -neg_guard, -neg_res, t0_cand, data_start, period_cand))

    verified_locks.sort(key=lambda v: (v[0], v[1], v[2], v[3]))

    # Deduplicate overlapping locks within 8 symbol periods
    distinct_locks = []
    for v in verified_locks:
        _, _, _, _, t0_c, ds_c, per_c = v
        if not any(abs(t0_c - prev[0]) < 8.0 * per_c for prev in distinct_locks):
            distinct_locks.append((t0_c, ds_c, per_c, v[0]))

    return distinct_locks


def acquire_preamble_t0(pulse_timestamps_us, chip_us=CHIP_DURATION_US, min_matches=10):
    """
    Sliding-window asynchronous comb correlator for 16-pulse periodic preamble
    followed by guard silence and 'SKY!' / 'SKYF' sync word.
    Tolerates:
      - Unlimited pre-burst solar/dark background noise pulses across continuous streams
      - Missing/dropped preamble pulses (including dropped initial pulses)
      - Interleaved noise pulses and +/-500 ppm clock skew
    Returns (t0_avg, data_start_time_us) or (None, None) if no preamble lock is found.
    """
    if len(pulse_timestamps_us) < min_matches:
        return None, None
    sorted_pulses = sorted(pulse_timestamps_us)
    locks = _acquire_preamble_all_candidates(sorted_pulses, chip_us=chip_us, min_matches=min_matches)
    if not locks:
        return None, None
    best_t0, best_data_start, _, _ = locks[0]
    return best_t0, best_data_start


def _demodulate_from_lock(sorted_pulses, data_start_time_us, init_period_us, nom_chip_us=CHIP_DURATION_US):
    """
    Demodulates 8-PPM symbols starting at `data_start_time_us` using a second-order
    Decision-Directed Delay-Locked Loop (DLL / PLL) to track independent TX/RX crystal
    clock drift (+/-250 ppm) across long packets.
    Returns `(symbols, erased_symbol_indices)`.
    """
    n_pulses = len(sorted_pulses)
    if n_pulses == 0 or sorted_pulses[-1] < data_start_time_us:
        return [], set()

    nom_period_us = float(SLOTS_PER_SYMBOL * nom_chip_us)
    min_period_us = nom_period_us * 0.9994
    max_period_us = nom_period_us * 1.0006

    cur_win_start = float(data_start_time_us)
    cur_period_us = float(init_period_us)
    last_pulse_time = sorted_pulses[-1]

    symbols = []
    erased_indices = set()
    w = 0
    max_windows = int((last_pulse_time - data_start_time_us) // min_period_us) + 2

    # Proportional-Integral (PI) tracking loop coefficients
    alpha_phase = 0.12
    beta_freq = 0.003

    while w < max_windows and cur_win_start <= last_pulse_time + (cur_period_us * 0.5):
        cur_chip_us = cur_period_us / SLOTS_PER_SYMBOL
        half_chip = cur_chip_us * 0.5
        win_lo = cur_win_start - half_chip
        win_hi = cur_win_start + cur_period_us - half_chip

        i_lo = bisect.bisect_left(sorted_pulses, win_lo)
        i_hi = bisect.bisect_right(sorted_pulses, win_hi)
        in_win = sorted_pulses[i_lo:i_hi]

        if not in_win:
            symbols.append(0)
            erased_indices.add(w)
            cur_win_start += cur_period_us
        else:
            # Vote across slots (handles both single-pulse and multi-pulse per slot profiles)
            slot_counts = [0] * SLOTS_PER_SYMBOL
            slot_err_sum = [0.0] * SLOTS_PER_SYMBOL
            slot_signed_err = [0.0] * SLOTS_PER_SYMBOL

            for p_time in in_win:
                raw_slot = (p_time - cur_win_start) / cur_chip_us
                s_cand = max(0, min(SLOTS_PER_SYMBOL - 1, int(round(raw_slot))))
                signed_err_us = p_time - (cur_win_start + s_cand * cur_chip_us)
                slot_counts[s_cand] += 1
                slot_err_sum[s_cand] += abs(signed_err_us)
                slot_signed_err[s_cand] += signed_err_us

            # Select slot with highest pulse count, breaking ties by lowest timing residual
            best_slot = 0
            best_score = (-1, float("inf"))
            for s_idx in range(SLOTS_PER_SYMBOL):
                if slot_counts[s_idx] > 0:
                    avg_abs_err = slot_err_sum[s_idx] / slot_counts[s_idx]
                    score = (slot_counts[s_idx], -avg_abs_err)
                    if score > best_score:
                        best_score = score
                        best_slot = s_idx

            symbols.append(best_slot)

            # Update Decision-Directed DLL only when a single dominant slot is cleanly locked
            active_slots = sum(1 for c in slot_counts if c > 0)
            mean_signed_err = slot_signed_err[best_slot] / slot_counts[best_slot]
            if active_slots == 1 and abs(mean_signed_err) <= (0.45 * cur_chip_us):
                cur_period_us = max(
                    min_period_us,
                    min(max_period_us, cur_period_us + beta_freq * mean_signed_err),
                )
                cur_win_start += cur_period_us + (alpha_phase * mean_signed_err)
            else:
                cur_win_start += cur_period_us

        w += 1

    return symbols, erased_indices


def demodulate_pulse_train(pulse_timestamps_us, chip_us=CHIP_DURATION_US, return_erasures=False):
    """
    Demodulates raw microsecond pulse timestamps into 8-PPM symbol indices.
    1. Uses O(N log N) sliding-window comb correlation to lock onto the 16-pulse preamble
       across arbitrary pre-burst background noise pulses and dropped preamble pulses.
    2. Tracks symbol windows using a Decision-Directed Delay-Locked Loop (DLL) to compensate
       for independent hardware crystal frequency offsets (+/-250 ppm) and flags empty windows
       as symbol erasures without losing frame alignment.
    """
    if len(pulse_timestamps_us) < 10:
        return ([], set()) if return_erasures else []

    sorted_pulses = sorted(pulse_timestamps_us)
    locks = _acquire_preamble_all_candidates(sorted_pulses, chip_us=chip_us)
    if not locks:
        return ([], set()) if return_erasures else []

    _, data_start_time_us, period_est_us, _ = locks[0]
    symbols, erased_indices = _demodulate_from_lock(
        sorted_pulses, data_start_time_us, period_est_us, nom_chip_us=chip_us
    )
    if return_erasures:
        return symbols, erased_indices
    return symbols


def parse_sky_frame(raw_bytes, erased_mask_bytes=None):
    """
    Parses framed packet:
    - Standard frame: [Sync: 4B 'SKY!'] [Length: 2B] [Payload: N B] [CRC32: 4B]
    - FEC frame:      [Sync: 4B 'SKYF'] [FEC(Length): 4B] [FEC(Payload + CRC32): 2*(N+4) B]
    Validates sync word, runs Bit-Interleaved Extended Hamming(8,4) SECDED + Erasure repair
    if enabled, and checks CRC32 integrity.
    """
    if len(raw_bytes) < 10:
        return None, "Packet too short"

    sync = raw_bytes[:4]

    # Check if this is an FEC-protected frame ('SKYF' exact or <=4 bit error in 'SKYF' sync word)
    dist_fec = _sync_hamming_distance(sync, FRAME_SYNC_FEC)
    if sync == FRAME_SYNC_FEC or (sync != FRAME_SYNC_WORD and dist_fec <= 4 and len(raw_bytes) >= 16):
        if len(raw_bytes) < 16:
            return None, "FEC packet header too short"
        len_mask = erased_mask_bytes[4:8] if erased_mask_bytes and len(erased_mask_bytes) >= 8 else None
        len_bytes = fec_decode_bytes(raw_bytes[4:8], erased_mask_bytes=len_mask)
        payload_len = struct.unpack(">H", len_bytes)[0]
        if payload_len > 4096:
            return None, f"Implausible FEC payload length: {payload_len}"
        fec_body_len = 2 * (payload_len + 4)
        total_expected = 8 + fec_body_len
        if len(raw_bytes) < total_expected:
            missing_bytes = total_expected - len(raw_bytes)
            # If up to 35% of trailing bytes were lost due to tail-pulse erasure, pad as erased bytes
            if missing_bytes <= (fec_body_len * 3) // 8:
                raw_bytes = raw_bytes + (b"\x00" * missing_bytes)
                if erased_mask_bytes is not None:
                    erased_mask_bytes = erased_mask_bytes + (b"\xff" * missing_bytes)
            else:
                return None, f"Incomplete FEC frame: expected {total_expected}, got {len(raw_bytes)}"

        body_mask = (
            erased_mask_bytes[8:total_expected]
            if erased_mask_bytes and len(erased_mask_bytes) >= total_expected
            else None
        )
        repaired_body = fec_decode_bytes(raw_bytes[8:total_expected], erased_mask_bytes=body_mask)
        payload = repaired_body[:payload_len]
        expected_crc = struct.unpack(">I", repaired_body[payload_len:payload_len + 4])[0]
    elif sync == FRAME_SYNC_WORD:
        payload_len = struct.unpack(">H", raw_bytes[4:6])[0]
        total_expected = 6 + payload_len + 4
        if len(raw_bytes) < total_expected:
            return None, f"Incomplete frame: expected {total_expected}, got {len(raw_bytes)}"
        payload = raw_bytes[6:6 + payload_len]
        expected_crc = struct.unpack(">I", raw_bytes[6 + payload_len:total_expected])[0]
    else:
        return None, f"Invalid sync word: {sync}"

    actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        return None, f"CRC mismatch: expected {hex(expected_crc)}, got {hex(actual_crc)}"

    return payload, "OK"


def verify_signed_sky_alert(raw_payload_bytes, verify_key_hex):
    """
    Verifies an Ed25519-signed camera alert received over the 8-PPM optical channel.
    Returns (alert_dict, True) on valid signature or (None, False) on forgery/corruption.
    """
    import json
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError

    if not raw_payload_bytes or len(raw_payload_bytes) <= 67 or raw_payload_bytes[:3] != b"DD\x01":
        return None, False
    sig = raw_payload_bytes[3:67]
    msg_bytes = raw_payload_bytes[67:]
    try:
        vk = VerifyKey(bytes.fromhex(verify_key_hex))
        vk.verify(msg_bytes, sig)
        return json.loads(msg_bytes.decode("utf-8")), True
    except (BadSignatureError, Exception):
        return None, False


def process_incoming_pulse_stream(pulse_timestamps_us, chip_us=CHIP_DURATION_US):
    """
    Full pipeline: pulse train -> 8-PPM symbols & erasures -> bytes -> frame & FEC verification.
    Supports both single bursts and multi-pass time-diversity carousel streams (automatically
    attempting each detected preamble lock and performing erasure-aware symbol combining across
    passes if individual passes suffered heavy snowflake occultation).
    """
    if len(pulse_timestamps_us) < 10:
        return {"status": "Too few pulses", "payload": None, "symbol_count": 0, "raw_bytes_len": 0}

    sorted_pulses = sorted(pulse_timestamps_us)
    locks = _acquire_preamble_all_candidates(sorted_pulses, chip_us=chip_us)
    if not locks:
        return {"status": "No preamble lock", "payload": None, "symbol_count": 0, "raw_bytes_len": 0}

    # Filter to valid frame preamble locks (sync word distance <= 6 bits)
    valid_pass_locks = sorted([lk for lk in locks if lk[3] <= 6], key=lambda x: x[0])
    search_locks = valid_pass_locks if valid_pass_locks else locks[:1]

    pass_demods = []
    last_status = "Parse failed"
    first_sym_count = 0
    first_raw_len = 0

    for idx, (t0_us, data_start_us, period_est_us, sync_dist) in enumerate(search_locks):
        # Bound this pass's pulses to before the next valid pass's preamble t0
        if idx + 1 < len(search_locks):
            next_t0 = search_locks[idx + 1][0] - period_est_us
            end_i = bisect.bisect_right(sorted_pulses, next_t0)
            pass_pulses = sorted_pulses[:end_i]
        else:
            pass_pulses = sorted_pulses

        symbols, erased_indices = _demodulate_from_lock(
            pass_pulses, data_start_us, period_est_us, nom_chip_us=chip_us
        )
        raw_data, erased_mask = decode_8ppm_symbols_with_erasures(symbols, erased_indices)
        if idx == 0:
            first_sym_count = len(symbols)
            first_raw_len = len(raw_data)

        payload, status = parse_sky_frame(raw_data, erased_mask_bytes=erased_mask)
        if status == "OK" and payload is not None:
            return {
                "status": "OK",
                "payload": payload,
                "symbol_count": len(symbols),
                "raw_bytes_len": len(raw_data),
                "pass_used": idx + 1,
            }
        last_status = status
        if sync_dist <= 6 and len(symbols) >= 24:
            pass_demods.append((symbols, erased_indices))

    # Multi-pass carousel erasure combining: fill erased symbols in Pass 1 using non-erased symbols from Pass 2..K
    if len(pass_demods) >= 2:
        max_len = max(len(s) for s, _ in pass_demods)
        combined_syms = []
        combined_erased = set()
        for w in range(max_len):
            non_erased_vals = [
                s[w] for s, er in pass_demods if w < len(s) and w not in er
            ]
            if not non_erased_vals:
                combined_syms.append(0)
                combined_erased.add(w)
            else:
                combined_syms.append(max(set(non_erased_vals), key=non_erased_vals.count))

        raw_comb, mask_comb = decode_8ppm_symbols_with_erasures(combined_syms, combined_erased)
        payload, status = parse_sky_frame(raw_comb, erased_mask_bytes=mask_comb)
        if status == "OK" and payload is not None:
            return {
                "status": "OK",
                "payload": payload,
                "symbol_count": len(combined_syms),
                "raw_bytes_len": len(raw_comb),
                "pass_used": "CAROUSEL_COMBINED",
            }

    return {
        "status": last_status,
        "payload": None,
        "symbol_count": first_sym_count,
        "raw_bytes_len": first_raw_len,
    }


def unpack_pio_rx_timestamps(rx_fifo_words, tick_ns=20.0):
    """
    Converts 32-bit monotonic tick counts from `pio_pulse_receiver.pio` RX FIFO
    into microsecond timestamps suitable for `process_incoming_pulse_stream`.
    """
    if not rx_fifo_words:
        return []
    t0_tick = rx_fifo_words[0]
    return [((w - t0_tick) & 0xFFFFFFFF) * (tick_ns / 1000.0) for w in rx_fifo_words]


def forward_verified_sky_alert(raw_payload_bytes, verify_key_hex, udp_host="127.0.0.1", udp_port=5514, send_udp=False):
    """
    Verifies a received `DD\\x01` signed sky alert and formats it into the canonical
    `pi-diode-trailcam` collector hub record (and optionally forwards the raw `DD\\x01`
    datagram over localhost UDP to `receiver_hub.py`).
    """
    alert_dict, ok = verify_signed_sky_alert(raw_payload_bytes, verify_key_hex)
    if not ok or alert_dict is None:
        return None, False

    hub_record = {
        "node": alert_dict.get("node", "UNKNOWN"),
        "ts": alert_dict.get("ts", 0),
        "nonce": alert_dict.get("nonce", ""),
        "detections": alert_dict.get("det", []),
        "pico_trig": alert_dict.get("trig", ""),
        "img_sha256_prefix": alert_dict.get("sha16", ""),
        "transport": "SKY_OPTICAL_8PPM",
        "verified": True,
    }
    if send_udp:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(raw_payload_bytes, (udp_host, udp_port))
        finally:
            sock.close()

    return hub_record, True


FRAGMENT_MAGIC = b"SKFG"


def reassemble_udp_datagrams_from_optical(optical_burst_streams, chip_us=CHIP_DURATION_US):
    """
    Transparent Optical-to-UDP Reassembler:
    Demodulates and FEC-decodes a sequence of received 8-PPM optical pulse bursts,
    reassembles `SKFG` fragmented sub-frames back into full `DD\\x01` and `DD\\x02`
    UDP datagrams, and returns `(reconstructed_datagrams, stats_dict)`.
    """
    single_datagrams = {}
    frag_buckets = {}  # dgram_id -> {"total": int, "parts": {frag_idx: bytes}}
    frames_ok = 0
    frames_failed = 0

    for stream in optical_burst_streams:
        pulses = stream["pulse_train_us"] if isinstance(stream, dict) else stream
        res = process_incoming_pulse_stream(pulses, chip_us=chip_us)
        if res["status"] != "OK" or res["payload"] is None:
            frames_failed += 1
            continue

        frames_ok += 1
        payload = res["payload"]
        if len(payload) >= 8 and payload[:4] == FRAGMENT_MAGIC:
            dgram_id, frag_idx, total_frags = struct.unpack(">HBB", payload[4:8])
            frag_data = payload[8:]
            if dgram_id not in frag_buckets:
                frag_buckets[dgram_id] = {"total": total_frags, "parts": {}}
            frag_buckets[dgram_id]["parts"][frag_idx] = frag_data
        else:
            # Unfragmented datagram: assign next available synthetic order or hash key
            next_id = len(single_datagrams) + 10000
            single_datagrams[next_id] = payload

    reconstructed = []
    # Reassemble fragmented datagrams in dgram_id order, interleaved with single datagrams
    for dgram_id, bkt in sorted(frag_buckets.items()):
        total = bkt["total"]
        parts = bkt["parts"]
        if total > 0 and len(parts) == total and all(i in parts for i in range(total)):
            full_dgram = b"".join(parts[i] for i in range(total))
            single_datagrams[dgram_id] = full_dgram

    # Preserve DD\x01 metadata datagrams first, followed by DD\x02 image chunk datagrams
    all_dgrams = [d for _, d in sorted(single_datagrams.items())]
    dd01 = [d for d in all_dgrams if d.startswith(b"DD\x01")]
    dd02 = [d for d in all_dgrams if not d.startswith(b"DD\x01")]
    reconstructed = dd01 + dd02

    return reconstructed, {
        "frames_ok": frames_ok,
        "frames_failed": frames_failed,
        "datagrams_reconstructed": len(reconstructed),
    }


def simulate_physical_detector_channel(
    tx_pulse_timestamps_us,
    mean_signal_pe=18.0,
    threshold_pe=3,
    bg_dark_rate_hz=2500.0,
    dead_time_ns=400.0,
    clock_drift_ppm=-120.0,
    jitter_rms_ns=35.0,
    pre_window_us=50000.0,
    post_window_us=5000.0,
    seed=2026,
):
    """
    Physically rigorous Monte-Carlo detector & atmospheric channel simulator:
      1. Applies independent TX/RX crystal clock frequency offset (`clock_drift_ppm`)
         and Gaussian TIA/comparator edge timing jitter (`jitter_rms_ns`).
      2. Draws Poisson photoelectron arrivals `k ~ Poisson(mean_signal_pe)` for each
         transmitted optical pulse; pulses with `k < threshold_pe` suffer shot-noise erasure.
      3. Generates Poisson solar background + detector dark count events (`bg_dark_rate_hz`)
         with exponential inter-arrival times across `[0, pre_window_us + burst + post_window_us]`.
      4. Enforces non-paralyzable detector/TDC dead time (`dead_time_ns`, matching
         `pio_pulse_receiver.pio`), where any background count arriving within `dead_time_ns`
         prior to a true signal pulse blinds the comparator and erases the signal pulse.
    """
    import math
    import random

    rng = random.Random(seed)
    if not tx_pulse_timestamps_us:
        return [], {}

    def _sample_poisson(lam):
        if lam <= 0.0:
            return 0
        if lam < 30.0:
            l_lim = math.exp(-lam)
            k = 0
            p = 1.0
            while p > l_lim:
                k += 1
                p *= rng.random()
            return k - 1
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))

    clock_scale = 1.0 + (clock_drift_ppm * 1e-6)
    jitter_us = jitter_rms_ns * 1e-3
    dead_time_us = dead_time_ns * 1e-3

    # 1. Signal pulses after clock drift, TIA jitter, and Poisson quantum threshold
    raw_events = []
    signal_kept = 0
    signal_shot_erased = 0
    for t_tx in tx_pulse_timestamps_us:
        pe_count = _sample_poisson(mean_signal_pe)
        if pe_count >= threshold_pe:
            t_rx = pre_window_us + (t_tx * clock_scale) + rng.gauss(0.0, jitter_us)
            raw_events.append((t_rx, "SIG"))
            signal_kept += 1
        else:
            signal_shot_erased += 1

    # 2. Poisson background/dark counts across the observation window
    total_span_us = pre_window_us + (tx_pulse_timestamps_us[-1] * clock_scale) + post_window_us
    bg_count = 0
    if bg_dark_rate_hz > 0.0:
        mean_interval_us = 1e6 / bg_dark_rate_hz
        t_bg = rng.expovariate(1.0 / mean_interval_us)
        while t_bg < total_span_us:
            raw_events.append((t_bg, "BG"))
            bg_count += 1
            t_bg += rng.expovariate(1.0 / mean_interval_us)

    # 3. Sort chronologically and enforce non-paralyzable detector dead time
    raw_events.sort(key=lambda e: e[0])
    accepted_timestamps_us = []
    last_trigger_us = -1e12
    deadtime_blinding_losses = 0

    for t_ev, kind in raw_events:
        if (t_ev - last_trigger_us) >= dead_time_us:
            accepted_timestamps_us.append(t_ev)
            last_trigger_us = t_ev
        elif kind == "SIG":
            deadtime_blinding_losses += 1

    return accepted_timestamps_us, {
        "tx_pulses": len(tx_pulse_timestamps_us),
        "signal_survived_shot_noise": signal_kept,
        "signal_shot_erased": signal_shot_erased,
        "deadtime_blinding_losses": deadtime_blinding_losses,
        "background_pulses_injected": bg_count,
        "total_output_pulses": len(accepted_timestamps_us),
    }


def evaluate_link_health_diagnostics(pulse_timestamps_us, chip_us=CHIP_DURATION_US):
    """
    Field Alignment & Link Qualification Telemetry Analyzer:
    Computes real-time physical link quality metrics from a received pulse stream
    for outdoor telescope alignment and client acceptance testing:
      - `preamble_matches`: Matched comb teeth out of 16
      - `clock_skew_ppm`: Estimated TX-to-RX crystal frequency offset in ppm
      - `timing_jitter_rms_ns`: RMS pulse arrival jitter relative to DLL slot centers (ns)
      - `symbol_erasure_pct`: Percentage of 8-PPM symbol windows with zero detected photons
      - `estimated_bg_rate_hz`: Background/solar noise count rate estimated from pre-burst/guard windows
      - `status` & `go_no_go`: Overall packet decode status and field readiness verdict.
    """
    import math

    if len(pulse_timestamps_us) < 10:
        return {"status": "NO_SIGNAL", "go_no_go": "NO-GO", "preamble_matches": 0}

    sorted_pulses = sorted(pulse_timestamps_us)
    nom_period = float(SLOTS_PER_SYMBOL * chip_us)
    locks = _acquire_preamble_all_candidates(sorted_pulses, chip_us=chip_us)
    if not locks:
        return {"status": "NO_PREAMBLE_LOCK", "go_no_go": "NO-GO", "preamble_matches": 0}

    t0_us, data_start_us, period_est_us, sync_dist = locks[0]
    clock_skew_ppm = ((period_est_us - nom_period) / nom_period) * 1e6

    # Count matched preamble teeth and pre-burst background rate
    tol_us = min(0.85, chip_us * 0.42)
    preamble_matches = 0
    for m in range(16):
        exp_t = t0_us + m * period_est_us
        idx = bisect.bisect_left(sorted_pulses, exp_t - tol_us)
        if idx < len(sorted_pulses) and sorted_pulses[idx] <= exp_t + tol_us:
            preamble_matches += 1

    pre_idx = bisect.bisect_left(sorted_pulses, t0_us - tol_us)
    pre_span_s = max(0.0, (t0_us - sorted_pulses[0]) * 1e-6) if pre_idx > 1 else 0.0
    est_bg_hz = (pre_idx / pre_span_s) if pre_span_s > 1e-4 else 0.0

    symbols, erased_indices = _demodulate_from_lock(
        sorted_pulses, data_start_us, period_est_us, nom_chip_us=chip_us
    )
    rx_res = process_incoming_pulse_stream(sorted_pulses, chip_us=chip_us)

    # Bound diagnostics to actual frame symbols (excluding post-burst trailing background window)
    if rx_res["status"] == "OK" and rx_res["payload"] is not None:
        frame_sym_len = min(len(symbols), 3 * (8 + 2 * (len(rx_res["payload"]) + 4)))
    else:
        frame_sym_len = len(symbols)

    frame_erased = sum(1 for w in erased_indices if w < frame_sym_len)

    # Compute RMS timing jitter across non-erased frame symbol windows
    sq_errs_ns2 = []
    cur_chip = period_est_us / SLOTS_PER_SYMBOL
    for w in range(frame_sym_len):
        if w in erased_indices:
            continue
        sym = symbols[w]
        expected_p = data_start_us + (w * period_est_us) + (sym * cur_chip)
        idx = bisect.bisect_left(sorted_pulses, expected_p - cur_chip * 0.5)
        if idx < len(sorted_pulses) and abs(sorted_pulses[idx] - expected_p) <= cur_chip * 0.5:
            err_ns = (sorted_pulses[idx] - expected_p) * 1000.0
            sq_errs_ns2.append(err_ns * err_ns)

    jitter_rms_ns = math.sqrt(sum(sq_errs_ns2) / len(sq_errs_ns2)) if sq_errs_ns2 else 0.0
    erasure_pct = (frame_erased / max(1, frame_sym_len)) * 100.0
    go_verdict = (
        "GO"
        if (rx_res["status"] == "OK" and preamble_matches >= 12 and erasure_pct < 15.0)
        else "NO-GO"
    )

    return {
        "status": rx_res["status"],
        "go_no_go": go_verdict,
        "preamble_matches": preamble_matches,
        "sync_word_hamming_dist": sync_dist,
        "clock_skew_ppm": round(clock_skew_ppm, 1),
        "timing_jitter_rms_ns": round(jitter_rms_ns, 1),
        "symbol_erasure_pct": round(erasure_pct, 2),
        "estimated_bg_rate_hz": round(est_bg_hz, 0),
        "symbol_count": frame_sym_len,
    }


VK7MO_COSTAS_PREAMBLE = (0, 7, 1, 6, 2, 5, 3, 4, 0, 7, 4, 3, 5, 2, 6, 1)


def _ka7oei_highpass_filter(samples, cutoff_hz=850.0, sample_rate_hz=16000):
    """
    Digital model of the KA7OEI active DC-current-sink + 800 Hz 2-pole high-pass
    filter (DUBUS 3/2009 Part 4, pp. 2-4):
      - Strips steady solar/twilight DC photocurrent offset
      - Attenuates 50 Hz, 100 Hz, 150 Hz, and 300 Hz AC lighting hum scattered off
        clouds before the 1,500-2,400 Hz quadrature lock-in detector.
    """
    import math

    if not samples:
        return []
    rc = 1.0 / (2.0 * math.pi * float(cutoff_hz))
    dt = 1.0 / float(sample_rate_hz)
    alpha = rc / (rc + dt)

    # Pass 1: remove bulk DC mean + 1st-order high-pass
    mean_dc = sum(samples) / len(samples)
    stage1 = [0.0] * len(samples)
    prev_x = samples[0] - mean_dc
    prev_y = 0.0
    for i, s in enumerate(samples):
        x = s - mean_dc
        y = alpha * (prev_y + x - prev_x)
        stage1[i] = y
        prev_x = x
        prev_y = y

    # Pass 2: 2nd cascaded high-pass pole for >35 dB rejection at 50/100 Hz
    stage2 = [0.0] * len(samples)
    prev_x = stage1[0]
    prev_y = 0.0
    for i, x in enumerate(stage1):
        y = alpha * (prev_y + x - prev_x)
        stage2[i] = y
        prev_x = x
        prev_y = y

    return stage2


def simulate_vk7mo_scatter_channel(
    tx_waveform,
    snr_db=-10.0,
    mains_hum_50hz_amp=2.5,
    dc_sunlight_offset=12.0,
    cloud_multipath_phase_rad=1.35,
    pre_noise_ms=32.0,
    post_noise_ms=16.0,
    sample_rate_hz=16000,
    seed=2026,
):
    """
    Simulates a 2 km - 27 km non-line-of-sight (NLOS) VK7MO / KA7OEI cloud-bounce
    or low-elevation aerosol forward-scatter channel:
      - Applies random carrier phase rotation (`cloud_multipath_phase_rad`) from
        diffuse cloud/mist path-length spread
      - Injects unmodulated DC sky/twilight offset (`dc_sunlight_offset`)
      - Injects 50 Hz, 100 Hz, and 150 Hz AC mains lighting hum (`mains_hum_50hz_amp`)
      - Adds broadband Gaussian quantum shot noise at `snr_db` (e.g., -10 dB to -14 dB,
        where broadband noise RMS is 3x to 5x larger than the optical signal!).
    """
    import math
    import random

    rng = random.Random(seed)
    pre_samples = int(round((pre_noise_ms * 1e-3) * sample_rate_hz))
    post_samples = int(round((post_noise_ms * 1e-3) * sample_rate_hz))
    total_len = pre_samples + len(tx_waveform) + post_samples

    # Signal RMS of unit cosine is 1 / sqrt(2) = 0.7071
    sig_power = 0.5
    noise_power = sig_power / (10.0 ** (float(snr_db) / 10.0))
    noise_std = math.sqrt(noise_power)

    # Apply unit-gain cloud multipath phase shift via normalized quadrature difference
    cos_p = math.cos(cloud_multipath_phase_rad)
    sin_p = math.sin(cloud_multipath_phase_rad)
    two_pi_over_fs = (2.0 * math.pi) / float(sample_rate_hz)
    quad_norm = max(0.2, 2.0 * math.sin(math.pi * 1900.0 / float(sample_rate_hz)))

    rx_stream = [0.0] * total_len
    for idx in range(total_len):
        t_idx = idx - pre_samples
        sig_val = 0.0
        if 0 <= t_idx < len(tx_waveform):
            x_cur = tx_waveform[t_idx]
            x_prev = tx_waveform[t_idx - 1] if t_idx > 0 else x_cur
            sig_val = cos_p * x_cur + sin_p * ((x_cur - x_prev) / quad_norm)

        # 50 Hz + 100 Hz + 150 Hz AC lighting hum scattered off clouds
        hum = mains_hum_50hz_amp * (
            math.sin(two_pi_over_fs * 50.0 * idx)
            + 0.5 * math.sin(two_pi_over_fs * 100.0 * idx + 0.4)
            + 0.25 * math.sin(two_pi_over_fs * 150.0 * idx + 1.1)
        )
        shot_noise = rng.gauss(0.0, noise_std)
        rx_stream[idx] = dc_sunlight_offset + hum + sig_val + shot_noise

    return rx_stream, {
        "snr_db": snr_db,
        "noise_rms": round(noise_std, 4),
        "pre_samples": pre_samples,
        "total_samples": total_len,
    }


def _vk7mo_fhss_shift(symbol_idx, fhss_key):
    if not fhss_key:
        return 0
    import hashlib
    key_bytes = fhss_key.encode("utf-8") if isinstance(fhss_key, str) else bytes(fhss_key)
    digest = hashlib.sha256(key_bytes + struct.pack(">I", int(symbol_idx))).digest()
    return digest[0] & 0x07


def _excise_cw_jammers_time_domain(samples, sample_rate_hz=16000, min_freq_hz=900.0, max_freq_hz=3200.0):
    """
    Detects and notches continuous-wave (CW) narrowband jammers or strong PWM harmonics
    in the time domain before 2D Costas CFO search and rectangular-window tone correlation,
    preventing sinc() sidelobe leakage across adjacent tone bins at arbitrary CFO offsets.
    Returns `(cleaned_samples, notched_frequencies_hz)`.
    """
    import math

    block_len = 256
    n_blocks = min(28, len(samples) // block_len)
    if n_blocks < 8:
        return samples, []

    two_pi_over_fs = (2.0 * math.pi) / float(sample_rate_hz)
    step_hz = float(sample_rate_hz) / float(block_len)  # 62.5 Hz
    freqs = []
    f_cur = float(min_freq_hz)
    while f_cur <= float(max_freq_hz):
        freqs.append(f_cur)
        f_cur += step_hz

    medians = []
    for f_hz in freqs:
        omega = two_pi_over_fs * f_hz
        c_vec = [math.cos(omega * n) for n in range(block_len)]
        s_vec = [math.sin(omega * n) for n in range(block_len)]
        blk_e = []
        for b in range(n_blocks):
            base = b * block_len
            i_a = 0.0
            q_a = 0.0
            for n in range(block_len):
                v = samples[base + n]
                i_a += v * c_vec[n]
                q_a += v * s_vec[n]
            blk_e.append((i_a * i_a) + (q_a * q_a))
        blk_e.sort()
        medians.append(blk_e[n_blocks // 2])

    clean_floor = max(1e-9, sorted(medians)[len(medians) // 2])
    peak_idx = max(range(len(medians)), key=lambda i: medians[i])
    if medians[peak_idx] <= 5.0 * clean_floor:
        return samples, []

    # Fine-search exact jammer frequency around freqs[peak_idx] in 1.5 Hz steps
    coarse_f = freqs[peak_idx]
    best_f = coarse_f
    best_med = -1.0
    for df in range(-45, 46, 2):
        cand_f = coarse_f + float(df)
        omega = two_pi_over_fs * cand_f
        c_vec = [math.cos(omega * n) for n in range(block_len)]
        s_vec = [math.sin(omega * n) for n in range(block_len)]
        blk_e = []
        for b in range(min(12, n_blocks)):
            base = b * block_len
            i_a = 0.0
            q_a = 0.0
            for n in range(block_len):
                v = samples[base + n]
                i_a += v * c_vec[n]
                q_a += v * s_vec[n]
            blk_e.append((i_a * i_a) + (q_a * q_a))
        blk_e.sort()
        med = blk_e[len(blk_e) // 2]
        if med > best_med:
            best_med = med
            best_f = cand_f

    # Apply narrowband 2-pole biquad notch filter at best_f (pole radius r = 0.985)
    omega_0 = two_pi_over_fs * best_f
    cos_w0 = math.cos(omega_0)
    r = 0.985
    gain = (1.0 + r * r) * 0.5
    b1 = -2.0 * cos_w0
    a1 = -2.0 * r * cos_w0
    a2 = r * r

    out = [0.0] * len(samples)
    x1 = 0.0
    x2 = 0.0
    y1 = 0.0
    y2 = 0.0
    for idx, x0 in enumerate(samples):
        y0 = gain * (x0 + b1 * x1 + x2) - a1 * y1 - a2 * y2
        out[idx] = y0
        x2 = x1
        x1 = x0
        y2 = y1
        y1 = y0

    return out, [round(best_f, 1)]


def demodulate_vk7mo_lockin_stream(
    rx_samples_or_passes,
    symbol_ms=16.0,
    base_tone_hz=1500.0,
    tone_spacing_hz=None,
    sample_rate_hz=16000,
    erasure_snr_ratio=1.35,
    fhss_key=None,
    anti_jam_whitening=True,
    cfo_search_range_hz=0.0,
):
    """
    VK7MO / KA7OEI Weak-Signal Non-Coherent Quadrature IQ Lock-In Receiver:
    1. Passes incoming ADC/SDR samples (either a single sample list or a list of multi-pass
       carousel sample lists) through the KA7OEI DC-sink + 450 Hz 2-pole high-pass filter
       and optional time-domain biquad CW jammer notch pre-excision.
    2. Acquires the 16-symbol `VK7MO_COSTAS_PREAMBLE` in 2D Time & Frequency (`t0` and
       Carrier Frequency Offset `cfo_search_range_hz`) using the Costas thumbtack property
       so 2.4/5.8 GHz Troposcatter SDR links lock without GPSDO under crystal thermal drift
       and rain/cloud Doppler shift.
    3. Precomputes the 8 orthogonal quadrature basis vectors (cos/sin) at the locked carrier
       offset with exact inverse high-pass gain equalization.
    4. Integrates quadrature tone energies `E_m = I_m^2 + Q_m^2` across each symbol window,
       applies median baseline subtraction / spectral whitening (`anti_jam_whitening`) to
       suppress continuous narrowband jammers or PWM harmonics, and de-hops cryptographic
       FHSS symbol permutations (`fhss_key`).
    5. Flags low-reliability symbols (`peak / second_best < erasure_snr_ratio`) as erasures
       and decodes the `SKYF` Bit-Interleaved Extended Hamming(8,4) SECDED frame.
    """
    import math

    if not rx_samples_or_passes:
        return {"status": "EMPTY_STREAM", "payload": None}

    # Normalize input into a list of sample passes
    if isinstance(rx_samples_or_passes[0], (int, float)):
        passes = [rx_samples_or_passes]
    else:
        passes = list(rx_samples_or_passes)

    if tone_spacing_hz is None:
        tone_spacing_hz = 2000.0 / float(symbol_ms)
    samples_per_sym = max(8, int(round((symbol_ms * 1e-3) * sample_rate_hz)))
    two_pi_over_fs = (2.0 * math.pi) / float(sample_rate_hz)
    hp_cutoff_hz = 450.0

    def _build_tables(eff_base_hz):
        t_freqs = tuple(eff_base_hz + m * float(tone_spacing_hz) for m in range(SLOTS_PER_SYMBOL))
        c_tab = []
        s_tab = []
        for freq_hz in t_freqs:
            omega = two_pi_over_fs * freq_hz
            ratio_sq = (freq_hz / hp_cutoff_hz) ** 2
            hp_mag = ratio_sq / (1.0 + ratio_sq)
            eq_scale = 1.0 / max(0.25, hp_mag)
            c_tab.append([eq_scale * math.cos(omega * n) for n in range(samples_per_sym)])
            s_tab.append([eq_scale * math.sin(omega * n) for n in range(samples_per_sym)])
        return c_tab, s_tab

    filtered_passes = []
    excised_jammer_freqs = []
    pass_vars = []
    for p in passes:
        hp = _ka7oei_highpass_filter(p, cutoff_hz=hp_cutoff_hz, sample_rate_hz=sample_rate_hz)
        if anti_jam_whitening:
            hp, j_freqs = _excise_cw_jammers_time_domain(hp, sample_rate_hz=sample_rate_hz)
            excised_jammer_freqs.extend(j_freqs)
        filtered_passes.append(hp)
        p_var = sum(v * v for v in hp) / max(1, len(hp))
        pass_vars.append(max(1e-12, p_var))

    # Inverse-Noise-Variance Pass Weighting & Broadband Barrage-Jammer Gate:
    # If one or more passes were hit by a wideband barrage jammer (>4.5x broadband variance
    # relative to the cleanest hopped pass), gate out the barrage-jammed pass(es) (weight=0)
    # so their wideband noise cannot corrupt the clean frequency-hopped pass(es).
    min_pass_var = min(pass_vars) if pass_vars else 1.0
    cleanest_pass_idx = pass_vars.index(min_pass_var) if pass_vars else 0
    pass_weights = []
    barrage_jammed_passes_rejected = []
    for p_idx, p_var in enumerate(pass_vars):
        if len(pass_vars) > 1 and p_var > 4.5 * min_pass_var:
            pass_weights.append(0.0)
            barrage_jammed_passes_rejected.append(p_idx)
        else:
            pass_weights.append(min_pass_var / p_var)

    preamble_len = len(VK7MO_COSTAS_PREAMBLE)

    # Optional 2D Costas Time-Frequency search for SDR Carrier Frequency Offset (CFO) & Doppler
    # Acquire CFO on the cleanest (lowest-variance) hopped pass so a barrage jammer on Pass 0
    # cannot blind frequency synchronization.
    estimated_cfo_hz = 0.0
    if cfo_search_range_hz and float(cfo_search_range_hz) > 0.0:
        filt0 = filtered_passes[cleanest_pass_idx]
        max_search0 = min(len(filt0) - (preamble_len + 24) * samples_per_sym, samples_per_sym * 12)
        if max_search0 >= 0:
            cfo_max = float(cfo_search_range_hz)
            cfo_step = max(8.0, float(tone_spacing_hz) / 8.0)
            time_step = max(1, samples_per_sym // 4)
            f_min = max(500.0, float(base_tone_hz) - cfo_max)
            f_max = float(base_tone_hz) + (SLOTS_PER_SYMBOL - 1) * float(tone_spacing_hz) + cfo_max
            n_grid = int(round((f_max - f_min) / cfo_step)) + 1
            tone_stride = int(round(float(tone_spacing_hz) / cfo_step))

            # Precompute basis vectors across the candidate frequency grid
            grid_cos = []
            grid_sin = []
            for g_idx in range(n_grid):
                f_hz = f_min + g_idx * cfo_step
                omega = two_pi_over_fs * f_hz
                ratio_sq = (f_hz / hp_cutoff_hz) ** 2
                eq_scale = 1.0 / max(0.25, ratio_sq / (1.0 + ratio_sq))
                grid_cos.append([eq_scale * math.cos(omega * n) for n in range(samples_per_sym)])
                grid_sin.append([eq_scale * math.sin(omega * n) for n in range(samples_per_sym)])

            def _grid_bin_energy(buf, start_idx, g_idx):
                c_v = grid_cos[g_idx]
                s_v = grid_sin[g_idx]
                i_a = 0.0
                q_a = 0.0
                for n in range(samples_per_sym):
                    val = buf[start_idx + n]
                    i_a += val * c_v[n]
                    q_a += val * s_v[n]
                return (i_a * i_a) + (q_a * q_a)

            best_2d_score = -1e30
            best_g0 = 0
            best_cand0 = 0
            n_cfo_steps = n_grid - (SLOTS_PER_SYMBOL - 1) * tone_stride
            for cand in range(0, max_search0 + 1, time_step):
                sym_grid_e = []
                for k in range(preamble_len):
                    w_start = cand + k * samples_per_sym
                    row_e = [_grid_bin_energy(filt0, w_start, g_idx) for g_idx in range(n_grid)]
                    sym_grid_e.append(row_e)

                for g0 in range(max(1, n_cfo_steps)):
                    score = 0.0
                    for k, sym_k in enumerate(VK7MO_COSTAS_PREAMBLE):
                        score += sym_grid_e[k][g0 + sym_k * tone_stride]
                    if score > best_2d_score:
                        best_2d_score = score
                        best_g0 = g0
                        best_cand0 = cand

            coarse_cfo = (f_min + best_g0 * cfo_step) - float(base_tone_hz)
            # Fine CFO refinement (+/- cfo_step in 2 Hz increments at best_cand0)
            best_fine_cfo = coarse_cfo
            best_fine_score = -1e30
            fine_step_hz = 2.0
            n_fine = int(round((2.0 * cfo_step) / fine_step_hz))
            for f_i in range(n_fine + 1):
                cand_cfo = (coarse_cfo - cfo_step) + f_i * fine_step_hz
                c_tab, s_tab = _build_tables(float(base_tone_hz) + cand_cfo)
                score = 0.0
                for k, sym_k in enumerate(VK7MO_COSTAS_PREAMBLE):
                    w_start = best_cand0 + k * samples_per_sym
                    c_v = c_tab[sym_k]
                    s_v = s_tab[sym_k]
                    i_a = 0.0
                    q_a = 0.0
                    for n in range(samples_per_sym):
                        val = filt0[w_start + n]
                        i_a += val * c_v[n]
                        q_a += val * s_v[n]
                    score += (i_a * i_a) + (q_a * q_a)
                if score > best_fine_score:
                    best_fine_score = score
                    best_fine_cfo = cand_cfo
            estimated_cfo_hz = best_fine_cfo

    eff_base_hz = float(base_tone_hz) + estimated_cfo_hz
    cos_table, sin_table = _build_tables(eff_base_hz)

    def _tone_energy(buf, start_idx, m):
        c_vec = cos_table[m]
        s_vec = sin_table[m]
        i_acc = 0.0
        q_acc = 0.0
        for n in range(samples_per_sym):
            val = buf[start_idx + n]
            i_acc += val * c_vec[n]
            q_acc += val * s_vec[n]
        return (i_acc * i_acc) + (q_acc * q_acc)

    # Identify any tone bin that was notched by the time-domain CW jammer exciser
    jammed_tones = set()
    for j_hz in excised_jammer_freqs:
        for m in range(SLOTS_PER_SYMBOL):
            tone_m_hz = eff_base_hz + m * float(tone_spacing_hz)
            if abs(tone_m_hz - j_hz) <= 0.45 * float(tone_spacing_hz):
                jammed_tones.add(m)

    # Acquire Costas preamble on each pass independently (skipping any notched tone bin)
    data_starts = []
    for filt in filtered_passes:
        max_search = min(len(filt) - (preamble_len + 24) * samples_per_sym, samples_per_sym * 12)
        if max_search < 0:
            return {"status": "STREAM_TOO_SHORT", "payload": None}

        coarse_step = max(1, samples_per_sym // 8)
        best_coarse_idx = 0
        best_coarse_score = -1e30
        for cand in range(0, max_search + 1, coarse_step):
            score = 0.0
            for k, sym_k in enumerate(VK7MO_COSTAS_PREAMBLE):
                if sym_k in jammed_tones:
                    continue
                score += _tone_energy(filt, cand + k * samples_per_sym, sym_k)
            if score > best_coarse_score:
                best_coarse_score = score
                best_coarse_idx = cand

        # Fine search around best_coarse_idx
        fine_lo = max(0, best_coarse_idx - coarse_step)
        fine_hi = min(max_search, best_coarse_idx + coarse_step)
        best_idx = best_coarse_idx
        best_score = best_coarse_score
        for cand in range(fine_lo, fine_hi + 1):
            score = 0.0
            for k, sym_k in enumerate(VK7MO_COSTAS_PREAMBLE):
                if sym_k in jammed_tones:
                    continue
                score += _tone_energy(filt, cand + k * samples_per_sym, sym_k)
            if score > best_score:
                best_score = score
                best_idx = cand

        data_starts.append(best_idx + preamble_len * samples_per_sym)

    # Determine number of available data symbol windows across passes
    max_data_syms = min(
        (len(filt) - d_start) // samples_per_sym
        for filt, d_start in zip(filtered_passes, data_starts)
    )
    if max_data_syms < 24:
        return {"status": "INSUFFICIENT_DATA_SYMBOLS", "payload": None}

    # Build weighted energy matrix [w][m] summed across unjammed passes
    energy_matrix = []
    for w in range(max_data_syms):
        energies = [0.0] * SLOTS_PER_SYMBOL
        for p_idx, (filt, d_start) in enumerate(zip(filtered_passes, data_starts)):
            wt = pass_weights[p_idx]
            if wt <= 0.0:
                continue
            win_start = d_start + w * samples_per_sym
            for m in range(SLOTS_PER_SYMBOL):
                energies[m] += wt * _tone_energy(filt, win_start, m)
        energy_matrix.append(energies)

    # Anti-jamming spectral whitening: also check for residual tone baseline elevation
    if anti_jam_whitening and max_data_syms >= 16:
        tone_baselines = []
        for m in range(SLOTS_PER_SYMBOL):
            col = sorted(energy_matrix[w][m] for w in range(max_data_syms))
            tone_baselines.append(col[int(len(col) * 0.40)])
        clean_floor = max(1e-9, sorted(tone_baselines)[SLOTS_PER_SYMBOL // 2])
        for m in range(SLOTS_PER_SYMBOL):
            if tone_baselines[m] > 4.0 * clean_floor:
                jammed_tones.add(m)
            for w in range(max_data_syms):
                if m in jammed_tones:
                    energy_matrix[w][m] = 0.0
                else:
                    energy_matrix[w][m] = max(0.0, energy_matrix[w][m] - tone_baselines[m])

    unjammed_tone_list = [m for m in range(SLOTS_PER_SYMBOL) if m not in jammed_tones] or list(range(SLOTS_PER_SYMBOL))
    unjammed_peaks = sorted(
        max(energy_matrix[w][m] for m in unjammed_tone_list)
        for w in range(max_data_syms)
    )
    sig_peak_ref = unjammed_peaks[int(len(unjammed_peaks) * 0.60)] if unjammed_peaks else 0.0
    noise_medians = [
        sorted(energy_matrix[w][m] for w in range(max_data_syms))[max_data_syms // 2]
        for m in unjammed_tone_list
    ]
    median_noise_bin = sorted(noise_medians)[len(noise_medians) // 2] if noise_medians else 0.0
    sym_medians = [
        sorted(energy_matrix[w][m] for m in unjammed_tone_list)[len(unjammed_tone_list) // 2]
        for w in range(max_data_syms)
    ]
    ref_sym_median = sorted(sym_medians)[len(sym_medians) // 2] if sym_medians else 0.0

    demod_symbols = []
    erased_indices = set()
    snr_ratios = []
    jammed_symbols_recovered = 0
    pulsed_jammer_erasures = 0
    single_jammed_tone = next(iter(jammed_tones)) if len(jammed_tones) == 1 else None

    for w in range(max_data_syms):
        energies = energy_matrix[w]
        best_m = 0
        best_e = energies[0]
        second_e = 0.0
        for m in range(1, SLOTS_PER_SYMBOL):
            e_val = energies[m]
            if e_val > best_e:
                second_e = best_e
                best_e = e_val
                best_m = m
            elif e_val > second_e:
                second_e = e_val

        ratio = best_e / max(1e-12, second_e)
        snr_ratios.append(ratio)

        if ref_sym_median > 0.0 and sym_medians[w] > 4.5 * ref_sym_median:
            # Broadband pulsed/chirp jammer or Wi-Fi packet collision spiked all tones in window w
            erased_indices.add(w)
            pulsed_jammer_erasures += 1
        elif jammed_tones and (best_e - median_noise_bin) < 0.35 * max(1e-9, sig_peak_ref - median_noise_bin):
            # No unjammed tone carried signal energy above noise -> symbol hopped onto the notched jammer tone
            jammed_symbols_recovered += 1
            if single_jammed_tone is not None:
                best_m = single_jammed_tone
                if (best_e - median_noise_bin) > 0.24 * max(1e-9, sig_peak_ref - median_noise_bin):
                    erased_indices.add(w)
            else:
                erased_indices.add(w)
        elif not jammed_tones and best_e < 0.18 * sig_peak_ref:
            # Deep Rayleigh multipath fade null across all tones -> flag as erasure for Hamming(8,4) FEC
            erased_indices.add(w)
        elif ratio < erasure_snr_ratio:
            erased_indices.add(w)

        dehopped_sym = (best_m - _vk7mo_fhss_shift(w, fhss_key)) & 0x07
        demod_symbols.append(dehopped_sym)

    raw_bytes, erased_mask = decode_8ppm_symbols_with_erasures(demod_symbols, erased_indices)
    payload, status_msg = parse_sky_frame(raw_bytes, erased_mask_bytes=erased_mask)
    if payload is None:
        # Fallback retry without erasure masking in case aggressive erasure threshold over-masked
        payload, status_msg = parse_sky_frame(raw_bytes, erased_mask_bytes=None)

    if payload is not None:
        fec_block_len = 2 * (len(payload) + 4)
        return {
            "status": "OK",
            "mode": "VK7MO_LOCKIN_8FSK",
            "passes_combined": len(passes) - len(barrage_jammed_passes_rejected),
            "barrage_jammed_passes_rejected": barrage_jammed_passes_rejected,
            "pulsed_jammer_erasures": pulsed_jammer_erasures,
            "estimated_cfo_hz": round(estimated_cfo_hz, 1),
            "jammed_tones_notched": sorted(jammed_tones),
            "payload": payload,
            "payload_len": len(payload),
            "crc_valid": True,
            "erased_symbols_repaired": sum(1 for w in erased_indices if w < 3 * (8 + fec_block_len)),
            "mean_tone_peak_ratio": round(sum(snr_ratios) / max(1, len(snr_ratios)), 2),
        }

    return {
        "status": status_msg,
        "payload": None,
        "barrage_jammed_passes_rejected": barrage_jammed_passes_rejected,
        "pulsed_jammer_erasures": pulsed_jammer_erasures,
        "estimated_cfo_hz": round(estimated_cfo_hz, 1),
        "jammed_tones_notched": sorted(jammed_tones),
    }


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../transmitter")))
    from sky_transmitter import transmit_simulated_burst, encode_vk7mo_lockin_frame
    test_msg = b'{"node":"NODE-NORTH-01","alert":"PERSON","ts":1760000000}'
    tx_meta = transmit_simulated_burst(test_msg, enable_fec=True)
    rx_result = process_incoming_pulse_stream(tx_meta["pulse_train_us"])
    print("=== SKY RELAY 8-PPM RECEIVER TEST ===")
    print(f"Demodulation Status: {rx_result['status']}")
    print(f"Reconstructed Payload: {rx_result['payload'].decode() if rx_result['payload'] else 'None'}")
    assert rx_result["payload"] == test_msg

    # Verify VK7MO Weak-Signal Lock-In Receiver at -10 dB wideband SNR + 50 Hz mains hum + DC sunlight
    vk7mo_tx = encode_vk7mo_lockin_frame(test_msg, symbol_ms=16.0)
    noisy_rx, ch_meta = simulate_vk7mo_scatter_channel(vk7mo_tx["waveform"], snr_db=-10.0)
    vk7mo_res = demodulate_vk7mo_lockin_stream(noisy_rx, symbol_ms=16.0)
    print(f"VK7MO Lock-In (-10 dB SNR + 50Hz hum): {vk7mo_res['status']} (Repaired erasures: {vk7mo_res.get('erased_symbols_repaired')})")
    assert vk7mo_res["payload"] == test_msg
    print("-> Self-test verification: 100% MATCH!")

