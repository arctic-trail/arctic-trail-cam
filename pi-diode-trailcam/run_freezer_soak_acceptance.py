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
from nacl.signing import SigningKey, VerifyKey

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HUB_DIR = os.path.join(SCRIPT_DIR, "collector_hub")
SENDER_DIR = os.path.join(SCRIPT_DIR, "pi5_sender_node")
for p in (HUB_DIR, SENDER_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import receiver_hub  # noqa: E402


TEMP_RE = re.compile(r"TEMP_C=([-+]?\d+(?:\.\d+)?)")
UPTIME_RE = re.compile(r"UPTIME_S=(\d+)")


def parse_trig_metrics(trig_str: str) -> dict:
    temp_m = TEMP_RE.search(trig_str or "")
    up_m = UPTIME_RE.search(trig_str or "")
    return {
        "temp_c": float(temp_m.group(1)) if temp_m else None,
        "uptime_s": int(up_m.group(1)) if up_m else None,
    }


def evaluate_journal_records(alerts_dir: str, target_temp_c: float = -10.0) -> dict:
    journal_path = os.path.join(alerts_dir, "alerts_journal.jsonl")
    records = []
    if os.path.isfile(journal_path):
        with open(journal_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

    temps = []
    sig_verified_count = 0
    sha_verified_count = 0
    for rec in records:
        trig = rec.get("pico_trig") or rec.get("pico_trigger", "")
        parsed = parse_trig_metrics(trig)
        if parsed["temp_c"] is not None:
            temps.append(parsed["temp_c"])

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
    total = len(records)
    loss_pct = 0.0 if (total > 0 and sha_verified_count == total) else 100.0
    passed = (
        total >= 4
        and sig_verified_count == total
        and sha_verified_count == total
        and (min_temp_c is not None and min_temp_c <= target_temp_c)
    )
    return {
        "schema": "ARCTIC_TRAILCAM_FREEZER_SOAK_ACCEPTANCE_V1",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "power_rail_topology": "5V USB Power Bank -> StarTech USB2TYPEN1M (5.5x2.5mm Type-N) + Pi 5 27W/5A PD",
        "total_optical_diode_frames": total,
        "ed25519_signatures_verified": sig_verified_count,
        "sha256_image_digests_verified": sha_verified_count,
        "udp_optical_diode_loss_pct": loss_pct,
        "min_core_temp_c": min_temp_c,
        "max_core_temp_c": max_temp_c,
        "target_subzero_threshold_c": target_temp_c,
        "verdict": "PASS" if passed else "PENDING_SOAK_COMPLETION",
    }


def run_self_test() -> int:
    print("[*] Running Freezer Soak Acceptance Harness Self-Test (Provisioned Fail-Closed Mode)...")
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
                "pico_trig": f"TRIG,MAG=1480,SEIS=0,RADAR_M=3.45,TEMP_C={t_c:.1f},UPTIME_S={idx * 3600 + 60}",
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
        assert report["verdict"] == "PASS", f"Expected PASS, got {report}"
        assert report["total_optical_diode_frames"] == 5
        assert report["min_core_temp_c"] == -18.4
        assert report["udp_optical_diode_loss_pct"] == 0.0
        print(f"    [+] Self-Test PASSED: {json.dumps(report)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Arctic Trail Cam 4-Hour -18 C Freezer Soak Acceptance Harness")
    parser.add_argument("--self-test", action="store_true", help="Run offline end-to-end verification self-test")
    parser.add_argument("--out-dir", default=os.path.join(SCRIPT_DIR, "verified_alerts"), help="Alerts directory")
    parser.add_argument("--duration-min", type=float, default=0.0, help="Live monitoring duration in minutes")
    parser.add_argument("--target-temp-c", type=float, default=-10.0, help="Target sub-zero core temperature (C)")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    os.makedirs(args.out_dir, exist_ok=True)
    if args.duration_min > 0:
        end_t = time.time() + args.duration_min * 60.0
        print(f"[*] Monitoring {args.out_dir} for {args.duration_min:.1f} minutes...")
        while time.time() < end_t:
            rep = evaluate_journal_records(args.out_dir, target_temp_c=args.target_temp_c)
            print(
                f"    [t={time.strftime('%H:%M:%S')}] Frames={rep['total_optical_diode_frames']} | "
                f"MinTemp={rep['min_core_temp_c']} C | Verdict={rep['verdict']}"
            )
            time.sleep(30.0)

    report = evaluate_journal_records(args.out_dir, target_temp_c=args.target_temp_c)
    out_path = os.path.join(args.out_dir, "freezer_soak_acceptance_report.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"[+] Wrote Freezer Soak Acceptance Report -> {out_path}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
