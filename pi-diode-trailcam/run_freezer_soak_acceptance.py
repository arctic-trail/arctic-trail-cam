#!/usr/bin/env python3
"""
Turnkey 4-Hour -18 °C Freezer Soak Acceptance Harness for `pi-diode-trailcam`.

Usage:
  1. Self-Test (verifies cryptographic + thermal + optical-diode acceptance logic offline):
       python3 -B pi-diode-trailcam/run_freezer_soak_acceptance.py --self-test

  2. Live 4-Hour Freezer Soak (once StarTech USB2TYPEN1M 5.5x2.5mm barrel cable B009JXJITS is connected):
       python3 -B pi-diode-trailcam/run_freezer_soak_acceptance.py --duration-min 240 --out-dir ./verified_alerts
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time

try:
    from nacl.signing import SigningKey, VerifyKey
except ModuleNotFoundError:
    for _cand in (
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "python3"),
        "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
    ):
        if os.path.exists(_cand) and os.path.realpath(sys.executable) != os.path.realpath(_cand):
            os.execv(_cand, [_cand, "-B"] + sys.argv)
    raise

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HUB_DIR = os.path.join(SCRIPT_DIR, "collector_hub")
SENDER_DIR = os.path.join(SCRIPT_DIR, "pi5_sender_node")
for p in (HUB_DIR, SENDER_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import receiver_hub  # noqa: E402


TEMP_RE = re.compile(r"(?<![A-Z0-9_])(?:AMB_TEMP_C|TEMP_C|TEMP)=([-+]?\d+(?:\.\d+)?)")
CPU_TEMP_RE = re.compile(r"(?<![A-Z0-9_])CPU_TEMP_C=([-+]?\d+(?:\.\d+)?)")
UPTIME_RE = re.compile(r"(?<![A-Z0-9_])UPTIME_S=(\d+)")
STALE_SD_SCRIPT_RE = re.compile(r"MAG=1480,SEIS=0,DIST=0,SPD=0")


def parse_trig_metrics(trig_str: str) -> dict:
    s = trig_str or ""
    temp_m = TEMP_RE.search(s)
    cpu_m = CPU_TEMP_RE.search(s)
    up_m = UPTIME_RE.search(s)
    stale_sd = bool(STALE_SD_SCRIPT_RE.search(s))
    return {
        "temp_c": float(temp_m.group(1)) if temp_m else None,
        "cpu_temp_c": float(cpu_m.group(1)) if cpu_m else None,
        "uptime_s": int(up_m.group(1)) if up_m else None,
        "stale_sd_card_loop_detected": stale_sd,
    }


def evaluate_journal_records(
    alerts_dir: str,
    target_temp_c: float = -10.0,
    min_frames: int = 4,
    since_ts: float = 0.0,
    dry_run: bool = False,
) -> dict:
    journal_path = os.path.join(alerts_dir, "alerts_journal.jsonl")
    records = []
    if os.path.isfile(journal_path):
        with open(journal_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    rec_ts = float(rec.get("received_at") or rec.get("timestamp") or 0.0)
                    if since_ts <= 0.0 or rec_ts >= since_ts:
                        records.append(rec)

    temps = []
    cpu_temps = []
    stale_sd_hits = 0
    sig_verified_count = 0
    sha_verified_count = 0
    for rec in records:
        trig = rec.get("pico_trig") or rec.get("pico_trigger", "")
        parsed = parse_trig_metrics(trig)
        if parsed["stale_sd_card_loop_detected"]:
            stale_sd_hits += 1
        if parsed["temp_c"] is not None:
            temps.append(parsed["temp_c"])
        if parsed["cpu_temp_c"] is not None:
            cpu_temps.append(parsed["cpu_temp_c"])

        img_file = rec.get("image_file")
        sig_file = rec.get("sig_file") or rec.get("signature_bundle")
        if img_file and sig_file:
            img_path = os.path.join(alerts_dir, os.path.basename(img_file))
            sig_path = os.path.join(alerts_dir, os.path.basename(sig_file))
            if os.path.isfile(img_path) and os.path.isfile(sig_path):
                with open(img_path, "rb") as ifh:
                    img_bytes = ifh.read()
                with open(sig_path, "r", encoding="utf-8") as sfh:
                    bundle = json.load(sfh)
                calc_sha = hashlib.sha256(img_bytes).hexdigest()
                if calc_sha == bundle.get("image_sha256"):
                    sha_verified_count += 1
                pub_hex = bundle.get("pubkey_hex") or bundle.get("public_key_hex")
                sig_hex = bundle.get("signature_hex") or bundle.get("signature_ed25519_hex")
                vk = VerifyKey(bytes.fromhex(pub_hex))
                if "signed_payload_b64" in bundle:
                    import base64
                    raw_meta = base64.b64decode(bundle["signed_payload_b64"])
                else:
                    raw_meta = bytes.fromhex(bundle["signed_metadata_utf8_hex"])
                sig_b = bytes.fromhex(sig_hex)
                vk.verify(raw_meta, sig_b)
                sig_verified_count += 1

    min_temp_c = min(temps) if temps else None
    max_temp_c = max(temps) if temps else None
    qualifying_cold_frames = sum(1 for t in temps if t <= target_temp_c)
    total = len(records)
    corrupted_pct = round(100.0 * (total - sha_verified_count) / total, 2) if total > 0 else 100.0
    req_frames = max(5, min_frames) if dry_run else min_frames
    req_cold_frames = max(2, min(3, req_frames // 2)) if not dry_run else 0

    # Compute inter-frame cadence intervals (seconds) across consecutive records
    rec_timestamps = sorted(
        float(r.get("received_at") or r.get("timestamp") or 0.0)
        for r in records
        if (r.get("received_at") or r.get("timestamp"))
    )
    intervals_s = [
        round(rec_timestamps[i] - rec_timestamps[i - 1], 2)
        for i in range(1, len(rec_timestamps))
    ]
    max_interval_s = max(intervals_s) if intervals_s else None

    temp_ok = (
        len(temps) == total
        and min_temp_c is not None
        and (
            (-45.0 <= min_temp_c <= 34.0 and max_temp_c <= 34.0)
            if dry_run
            else (min_temp_c <= target_temp_c and qualifying_cold_frames >= req_cold_frames)
        )
    )
    failure_reasons = []
    if total < req_frames:
        failure_reasons.append(f"INSUFFICIENT_FRAMES ({total}/{req_frames})")
    if stale_sd_hits > 0:
        failure_reasons.append(
            f"STALE_PI5_SD_SCRIPT_DETECTED ({stale_sd_hits} frames contain hardcoded MAG=1480,SEIS=0,DIST=0,SPD=0 "
            "from un-updated Pi 5 SD card script)"
        )
    if total > 0 and len(temps) < total:
        failure_reasons.append(
            f"AMBIENT_TEMP_SENSOR_MISSING ({total - len(temps)}/{total} frames lack Pico 2 ambient TEMP_C/TEMP; "
            "CPU_TEMP_C is never accepted as ambient temperature)"
        )
    if not dry_run and qualifying_cold_frames < req_cold_frames:
        failure_reasons.append(
            f"INSUFFICIENT_COLD_SOAK_FRAMES (qualifying_cold_frames={qualifying_cold_frames}/{req_cold_frames} "
            f"at <= {target_temp_c} C; min_temp_c={min_temp_c} C)"
        )
    if dry_run and max_temp_c is not None and max_temp_c > 34.0:
        failure_reasons.append(
            f"SUSPECT_CPU_DIE_TEMP_REPORTED_AS_AMBIENT (max_temp_c={max_temp_c} C > 34.0 C room-temp ceiling)"
        )

    passed = (
        total >= req_frames
        and stale_sd_hits == 0
        and sig_verified_count == total
        and sha_verified_count == total
        and temp_ok
    )
    if passed:
        verdict = "PREFLIGHT_PASS" if dry_run else "SOAK_PASS"
    elif stale_sd_hits > 0:
        verdict = "FAIL_PREFLIGHT"
    elif total < req_frames:
        verdict = "INCOMPLETE"
    else:
        verdict = "FAIL"

    return {
        "schema": "ARCTIC_TRAILCAM_FREEZER_SOAK_ACCEPTANCE_V1",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "DRY_RUN_PREFLIGHT" if dry_run else "FREEZER_SOAK",
        "power_rail_topology": "5V USB Power Bank -> StarTech USB2TYPEN1M (5.5x2.5mm Type-N) + Pi 5 27W/5A PD",
        "total_optical_diode_frames": total,
        "ed25519_signatures_verified": sig_verified_count,
        "sha256_image_digests_verified": sha_verified_count,
        "corrupted_received_frame_pct": corrupted_pct,
        "udp_optical_diode_loss_pct": corrupted_pct,
        "inter_frame_intervals_s": intervals_s,
        "max_inter_frame_interval_s": max_interval_s,
        "min_core_temp_c": min_temp_c,
        "max_core_temp_c": max_temp_c,
        "qualifying_cold_frames": qualifying_cold_frames,
        "required_cold_frames": req_cold_frames,
        "cpu_temp_samples_c": cpu_temps,
        "stale_sd_card_frames": stale_sd_hits,
        "target_subzero_threshold_c": target_temp_c,
        "failure_reasons": failure_reasons,
        "verdict": verdict,
    }


def run_self_test() -> int:
    print("[*] Running Freezer Soak Acceptance Harness Self-Test (Offline Unit Test Only)...")
    # Invariant 1: CPU_TEMP_C must NEVER be parsed as ambient TEMP_C
    m_cpu_only = parse_trig_metrics("TRIG,DIRECT_WAKE,CPU_TEMP_C=38.0")
    assert m_cpu_only["temp_c"] is None and m_cpu_only["cpu_temp_c"] == 38.0, f"CPU_TEMP_C leaked into temp_c: {m_cpu_only}"
    # Invariant 2: Stale Pi 5 SD card loop (MAG=1480,SEIS=0,DIST=0,SPD=0) must be flagged immediately
    m_stale = parse_trig_metrics("TRIG,MAG=1480,SEIS=0,DIST=0,SPD=0,TEMP_C=38.0,UPTIME_S=640")
    assert m_stale["stale_sd_card_loop_detected"] is True, f"Failed to flag stale SD loop: {m_stale}"

    with tempfile.TemporaryDirectory(prefix="freezer_soak_selftest_") as tmpdir:
        os.environ.pop("ALLOW_EXAMPLE_KEYS", None)
        sk = SigningKey.generate()
        pub_hex = sk.verify_key.encode().hex()
        node_id = "CAMERA-FREEZER-01"

        reg_path = os.path.join(tmpdir, "authorized_nodes.json")
        with open(reg_path, "w", encoding="utf-8") as fh:
            json.dump({node_id: pub_hex}, fh)

        os.environ["AUTHORIZED_NODES_FILE"] = reg_path
        receiver_hub.OUT_DIR = tmpdir
        receiver_hub.pending_chunks.clear()
        receiver_hub.pending_meta.clear()
        receiver_hub.completed_prefixes.clear()
        receiver_hub.node_security_state.clear()
        receiver_hub.load_authorized_nodes(tmpdir, allow_example_keys=False)

        # Simulate 5 hourly cold-soak epochs cooling from +18.0 C down to -18.4 C
        sample_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            + b"\x11" * 512
            + b"\xff\xd9"
        )
        sha_hex = hashlib.sha256(sample_jpeg).hexdigest()
        soak_temps = [18.0, 2.5, -8.2, -15.6, -18.4]

        for idx, t_c in enumerate(soak_temps):
            nonce_hex = f"f00d20260000000{idx}"
            meta = {
                "v": 2,
                "node": node_id,
                "ts": 1761540000 + idx * 3600,
                "nonce": nonce_hex,
                "pico_trig": f"TRIG,MAG={1620 + idx * 15},SEIS=12,RADAR_M=3.45,TEMP={t_c:.1f},UPTIME_S={idx * 3600 + 60}",
                "chunks": 1,
                "img_size": len(sample_jpeg),
                "img_sha256": sha_hex,
                "camera_ok": True,
                "detections": [{"class": "person", "conf": 0.94, "bbox": [0.15, 0.2, 0.55, 0.85]}],
            }
            meta_bytes = json.dumps(meta, separators=(",", ":")).encode("utf-8")
            sig = sk.sign(meta_bytes).signature
            pkt_meta = b"DD\x01" + sig + meta_bytes
            pkt_chunk = b"DD\x02" + bytes.fromhex(nonce_hex) + b"\x00\x00\x00\x01" + sample_jpeg
            assert receiver_hub.process_datagram(pkt_meta) is True
            assert receiver_hub.process_datagram(pkt_chunk) is True

        report = evaluate_journal_records(tmpdir, target_temp_c=-15.0)
        assert report["verdict"] == "SOAK_PASS", f"Expected SOAK_PASS in unit test evaluation, got {report}"
        # Invariant 3: A single cold sample (-18.4 C) must FAIL if fewer than req_cold_frames meet threshold
        report_strict = evaluate_journal_records(tmpdir, target_temp_c=-17.0)
        assert report_strict["verdict"] == "FAIL", f"Single cold sample should FAIL sustained cold check: {report_strict}"
        report["mode"] = "SIMULATED_SELF_TEST_ONLY"
        report["verdict"] = "SIMULATED_SELF_TEST_ONLY"
        assert report["total_optical_diode_frames"] == 5
        assert report["min_core_temp_c"] == -18.4
        assert report["corrupted_received_frame_pct"] == 0.0
        print(f"    [+] Offline Unit Self-Test Completed (NOT a hardware pass): {json.dumps(report)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Arctic Trail Cam 4-Hour -18 C Freezer Soak Acceptance Harness")
    parser.add_argument("--self-test", action="store_true", help="Run offline end-to-end verification self-test")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run a 5-minute room-temperature disconnect/reconnect miniature test (requires >= 5 fresh frames)",
    )
    parser.add_argument(
        "--out-dir",
        "--journal-dir",
        dest="out_dir",
        default=os.path.join(SCRIPT_DIR, "verified_alerts"),
        help="Alerts directory containing alerts_journal.jsonl",
    )
    parser.add_argument("--duration-min", type=float, default=0.0, help="Live monitoring duration in minutes")
    parser.add_argument(
        "--target-temp-c",
        "--max-temp-c",
        dest="target_temp_c",
        type=float,
        default=-10.0,
        help="Target sub-zero core temperature (C)",
    )
    parser.add_argument("--min-frames", type=int, default=5, help="Minimum verified frames required for soak PASS")
    parser.add_argument("--report-out", default="", help="Optional output JSON report path")
    parser.add_argument(
        "--fresh-only",
        action="store_true",
        default=True,
        help="Only count frames arriving after this script is launched (default: True)",
    )
    parser.add_argument(
        "--allow-historical",
        action="store_true",
        help="Inspect existing historical records in alerts_journal.jsonl (audit/diagnostic mode)",
    )
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    os.makedirs(args.out_dir, exist_ok=True)
    start_ts = 0.0 if args.allow_historical else (time.time() - 5.0)
    wait_min = args.duration_min if args.duration_min > 0 else (5.0 if args.dry_run else 0.0)

    if wait_min > 0:
        end_t = time.time() + wait_min * 60.0
        mode_lbl = "5-MINUTE PHYSICAL REHEARSAL (DRY RUN)" if args.dry_run else "FREEZER SOAK"
        print(f"[*] [{mode_lbl}] Monitoring {args.out_dir} for full {wait_min:.1f} minutes (no early exit)...")
        while time.time() < end_t:
            rep = evaluate_journal_records(
                args.out_dir,
                target_temp_c=args.target_temp_c,
                min_frames=args.min_frames,
                since_ts=start_ts,
                dry_run=args.dry_run,
            )
            print(
                f"    [t={time.strftime('%H:%M:%S')}] Frames={rep['total_optical_diode_frames']} | "
                f"MinTemp={rep['min_core_temp_c']} C | Verdict={rep['verdict']}"
            )
            time.sleep(10.0 if args.dry_run else 30.0)

    report = evaluate_journal_records(
        args.out_dir,
        target_temp_c=args.target_temp_c,
        min_frames=args.min_frames,
        since_ts=start_ts,
        dry_run=args.dry_run,
    )
    out_path = args.report_out or os.path.join(
        args.out_dir,
        "freezer_dry_run_report.json" if args.dry_run else "freezer_soak_acceptance_report.json",
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"[+] Wrote Report -> {out_path}")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] in ("PREFLIGHT_PASS", "SOAK_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
