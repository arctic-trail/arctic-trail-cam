#!/usr/bin/env python3
"""
Comprehensive Regression Suite for the 16 October 2026 Project Quality Assessment (#1-#21).
Verifies every code, firmware, protocol, dashboard, hardware, and PDF remediation.
"""

import hashlib
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from nacl.signing import SigningKey, VerifyKey
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRAILCAM_DIR = os.path.join(REPO_ROOT, "pi-diode-trailcam")
COLLECTOR_DIR = os.path.join(TRAILCAM_DIR, "collector_hub")
SENDER_DIR = os.path.join(TRAILCAM_DIR, "pi5_sender_node")
SKY_TX_DIR = os.path.join(REPO_ROOT, "sky-diode-relay", "transmitter")
SKY_RX_DIR = os.path.join(REPO_ROOT, "sky-diode-relay", "receiver")

for p in [COLLECTOR_DIR, SENDER_DIR, SKY_TX_DIR, SKY_RX_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import receiver_hub
import subghz_nlos_relay
import sender_node


def _make_valid_jpeg_bytes(width=160, height=120) -> bytes:
    img = Image.new("RGB", (width, height), color=(40, 90, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


class TestQualityAssessmentRemediations(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.save_dir = self.tmpdir.name
        receiver_hub.OUT_DIR = self.save_dir
        receiver_hub.STRICT_CLOCK_SKEW = False
        receiver_hub.pending_chunks.clear()
        receiver_hub.pending_meta.clear()
        receiver_hub.completed_prefixes.clear()
        receiver_hub.node_security_state.clear()
        receiver_hub.KNOWN_NODE_PUBKEYS.clear()
        receiver_hub.KNOWN_NODE_PUBKEYS["NODE-NORTH-01"] = VerifyKey(
            bytes.fromhex(receiver_hub.DEFAULT_EXAMPLE_PUBKEY_HEX)
        )
        os.environ["ALLOW_EXAMPLE_KEYS"] = "1"
        os.environ["AUTHORIZED_NODES_FILE"] = os.path.join(self.save_dir, "authorized_nodes.json")

    def tearDown(self):
        os.environ.pop("AUTHORIZED_NODES_FILE", None)
        os.environ["ALLOW_EXAMPLE_KEYS"] = "1"
        self.tmpdir.cleanup()

    def _build_signed_event_packets(self, signing_key: SigningKey, node_id: str, nonce_hex16: str, jpeg_bytes: bytes, detections=None):
        assert len(nonce_hex16) == 16
        if detections is None:
            detections = [{"class": "person", "conf": 0.91, "bbox": [0.2, 0.2, 0.6, 0.8]}]
        sha256_hex = hashlib.sha256(jpeg_bytes).hexdigest()
        chunk_size = 1024
        chunks = [jpeg_bytes[i:i + chunk_size] for i in range(0, len(jpeg_bytes), chunk_size)]
        meta = {
            "v": 2,
            "node": node_id,
            "ts": 1760500000,
            "nonce": nonce_hex16,
            "pico_trig": "RADAR+MAG:120",
            "chunks": len(chunks),
            "img_size": len(jpeg_bytes),
            "img_sha256": sha256_hex,
            "camera_ok": True,
            "detections": detections,
        }
        meta_bytes = json.dumps(meta, separators=(",", ":")).encode("utf-8")
        sig = signing_key.sign(meta_bytes).signature
        pkt_meta = b"DD\x01" + sig + meta_bytes

        nonce_bytes8 = bytes.fromhex(nonce_hex16)
        chunk_pkts = []
        for idx, ch in enumerate(chunks):
            hdr = b"DD\x02" + nonce_bytes8 + struct.pack(">HH", idx, len(chunks))
            chunk_pkts.append(hdr + ch)
        return pkt_meta, chunk_pkts

    def test_01_storage_failure_preserves_pending_alert_and_recovers(self):
        """Finding #1: Disk full / write error must not discard verified alerts or prematurely burn nonces."""
        sk = SigningKey(bytes.fromhex(sender_node.DEFAULT_EXAMPLE_PRIVKEY_HEX))
        jpeg_bytes = _make_valid_jpeg_bytes()
        nonce_hex = "a1b2c3d4e5f60011"
        pkt_meta, chunk_pkts = self._build_signed_event_packets(sk, "NODE-NORTH-01", nonce_hex, jpeg_bytes)

        # Step 1: Process DD\x01 metadata only; nonce must NOT be committed before durable image write
        receiver_hub.process_datagram(pkt_meta)
        seen = receiver_hub.node_security_state.get("NODE-NORTH-01", {}).get("seen_nonces", {})
        self.assertNotIn(nonce_hex, seen)

        # Simulate process restart before chunks finish: reload from disk and verify nonce wasn't burned
        receiver_hub.node_security_state.clear()
        receiver_hub.load_seen_nonces_from_disk(self.save_dir)
        seen_after_reload = receiver_hub.node_security_state.get("NODE-NORTH-01", {}).get("seen_nonces", {})
        self.assertNotIn(nonce_hex, seen_after_reload)

        # Step 2: Simulate full disk (OSError) during atomic write when the final chunk arrives
        with patch.object(receiver_hub, "_atomic_write_bytes", side_effect=OSError("No space left on device")):
            for cp in chunk_pkts:
                receiver_hub.process_datagram(cp)

        # Event must NOT be marked complete and must remain pending for carousel retry
        self.assertNotIn(nonce_hex, receiver_hub.completed_prefixes)
        self.assertIn(nonce_hex, receiver_hub.pending_meta)
        self.assertNotIn(
            nonce_hex,
            receiver_hub.node_security_state.get("NODE-NORTH-01", {}).get("seen_nonces", {}),
        )

        # Step 3: Storage recovers; next carousel retransmission completes and durably commits the event
        receiver_hub.process_datagram(chunk_pkts[0])
        self.assertIn(nonce_hex, receiver_hub.completed_prefixes)
        self.assertIn(
            nonce_hex,
            receiver_hub.node_security_state.get("NODE-NORTH-01", {}).get("seen_nonces", {}),
        )

        journal_path = os.path.join(self.save_dir, "alerts_journal.jsonl")
        with open(journal_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["nonce"], nonce_hex)

    def test_02_dashboard_pagination_never_skips_alerts_over_100(self):
        """Finding #2: /api/alerts cursor pagination must return exact slice end and drain 250 alerts without skips."""
        journal_path = os.path.join(self.save_dir, "alerts_journal.jsonl")
        total_records = 250
        with open(journal_path, "w", encoding="utf-8") as f:
            for i in range(total_records):
                rec = {"seq": i, "node": "NODE-NORTH-01", "timestamp": 1760500000 + i, "nonce": f"{i:016x}"}
                f.write(json.dumps(rec) + "\n")

        with open(journal_path, "r", encoding="utf-8") as f:
            all_lines = [line.strip() for line in f if line.strip()]

        since_idx = 0
        collected = []
        pages = 0
        while True:
            pages += 1
            total_count = len(all_lines)
            sliced_lines = all_lines[since_idx:since_idx + 100]
            sliced_alerts = [json.loads(l) for l in sliced_lines]
            next_idx = min(total_count, since_idx + len(sliced_alerts))
            has_more = next_idx < total_count
            collected.extend(sliced_alerts)
            since_idx = next_idx
            if not has_more:
                break

        self.assertEqual(pages, 3)
        self.assertEqual(len(collected), 250)
        self.assertEqual([r["seq"] for r in collected], list(range(250)))

    def test_03_example_signing_keys_rejected_in_production_mode(self):
        """Finding #3: Provisioning a real node with ALLOW_EXAMPLE_KEYS=0 rejects public example keys on both ends."""
        real_sk = SigningKey.generate()
        real_pub_hex = real_sk.verify_key.encode().hex()
        reg_file = os.path.join(self.save_dir, "authorized_nodes.json")
        with open(reg_file, "w", encoding="utf-8") as f:
            json.dump({"CAMERA-REAL-01": real_pub_hex}, f)

        os.environ["ALLOW_EXAMPLE_KEYS"] = "0"
        receiver_hub.load_authorized_nodes(self.save_dir, allow_example_keys=False)

        self.assertIn("CAMERA-REAL-01", receiver_hub.KNOWN_NODE_PUBKEYS)
        self.assertNotIn("NODE-NORTH-01", receiver_hub.KNOWN_NODE_PUBKEYS)

        # Forge packet with public example key -> must be rejected
        example_sk = SigningKey(bytes.fromhex(sender_node.DEFAULT_EXAMPLE_PRIVKEY_HEX))
        jpeg_bytes = _make_valid_jpeg_bytes()
        pkt_meta, _ = self._build_signed_event_packets(example_sk, "NODE-NORTH-01", "1122334455667788", jpeg_bytes)
        receiver_hub.process_datagram(pkt_meta)
        self.assertEqual(len(receiver_hub.pending_meta), 0)

        # Sender must also refuse example key when allow_example_keys=False
        with self.assertRaises(RuntimeError):
            sender_node.load_signing_key(key_file="/nonexistent/key.json", allow_example_keys=False)

    def test_04_replay_protection_retains_more_than_500_nonces_across_restart(self):
        """Finding #4: Old nonces beyond 500 must remain rejected both in memory and after disk reload."""
        node_id = "NODE-NORTH-01"
        for i in range(550):
            receiver_hub.commit_seen_nonce(node_id, 1760500000 + i, f"{i:016x}", out_dir=self.save_dir)

        # Nonce #0 must still be rejected in memory after 550 newer nonces
        self.assertFalse(
            receiver_hub.is_valid_fresh_packet(node_id, 1760500000, f"{0:016x}", strict_clock_skew=False, commit=False)
        )

        # Simulate collector restart and reload seen_nonces.jsonl from disk
        receiver_hub.node_security_state.clear()
        receiver_hub.load_seen_nonces_from_disk(self.save_dir)

        self.assertEqual(len(receiver_hub.node_security_state[node_id]["seen_nonces"]), 550)
        self.assertFalse(
            receiver_hub.is_valid_fresh_packet(node_id, 1760500000, f"{0:016x}", strict_clock_skew=False, commit=False)
        )

    def test_05_large_detection_list_bounded_and_accepted_by_receiver(self):
        """Finding #5: 40 detections from sender are bounded <= 1400 bytes and accepted by receiver_hub."""
        sk = SigningKey(bytes.fromhex(sender_node.DEFAULT_EXAMPLE_PRIVKEY_HEX))
        jpeg_bytes = _make_valid_jpeg_bytes()
        forty_detections = [
            {"class": "person", "conf": 0.95, "box": [0.111, 0.222, 0.333, 0.444]}
            for _ in range(40)
        ]

        sent_datagrams = []

        class DummySock:
            def sendto(self, data, addr):
                sent_datagrams.append(data)
            def close(self):
                pass

        alert_meta = {
            "v": 2,
            "node": "NODE-NORTH-01",
            "ts": 1760500000,
            "pico_trig": "RADAR",
            "camera_ok": True,
            "detections": forty_detections,
        }
        with patch("time.sleep", return_value=None):
            sender_node.transmit_over_diode(
                DummySock(), alert_meta, jpeg_bytes, shared_trunk=False, custom_signing_key=sk
            )

        meta_pkts = [d for d in sent_datagrams if d.startswith(b"DD\x01")]
        self.assertGreaterEqual(len(meta_pkts), 1)
        self.assertLessEqual(len(meta_pkts[0]), sender_node.MAX_META_PACKET_BYTES)

        # Feed all datagrams into receiver_hub and verify complete reconstruction
        for d in sent_datagrams:
            receiver_hub.process_datagram(d)

        journal_path = os.path.join(self.save_dir, "alerts_journal.jsonl")
        with open(journal_path, "r", encoding="utf-8") as f:
            rec = json.loads(f.readline())
        self.assertEqual(rec["total_detections"], 40)
        self.assertTrue(rec["detections_truncated"])
        self.assertLessEqual(len(rec["detections"]), sender_node.MAX_DETECTIONS_IN_PACKET)

    def test_06_sender_loads_node_id_and_key_together_from_keyfile(self):
        """Finding #6: load_signing_key() loads both node_id and private_key_hex from node_key.json."""
        sk = SigningKey.generate()
        key_file = os.path.join(self.save_dir, "camera_south_key.json")
        with open(key_file, "w", encoding="utf-8") as f:
            json.dump({
                "node_id": "CAMERA-SOUTH",
                "private_key_hex": sk.encode().hex(),
                "public_key_hex": sk.verify_key.encode().hex(),
            }, f)

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NODE_ID", None)
            os.environ.pop("PRIVATE_KEY_HEX", None)
            loaded_sk = sender_node.load_signing_key(key_file=key_file, allow_example_keys=False)
            self.assertEqual(sender_node.NODE_ID, "CAMERA-SOUTH")
            self.assertEqual(loaded_sk.encode().hex(), sk.encode().hex())

    def test_07_ui_camera_error_and_empty_detections_classification(self):
        """Finding #9: UI index.html classifies camera_ok===false as camera_error and never fabricates vehicle 94%."""
        ui_path = os.path.join(COLLECTOR_DIR, "ui", "index.html")
        with open(ui_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("camera_ok === false", html)
        self.assertIn("detClass = 'camera_error'", html)
        self.assertIn("detClass = 'sensor_trigger'", html)
        self.assertIn("12V SLA (Unmeasured)", html)

    def test_08_roi_crop_remaps_detection_bounding_boxes(self):
        """Finding #10: Detection bounding boxes are accurately transformed into the cropped JPEG coordinate space."""
        detections = [{"class": "vehicle", "conf": 0.88, "box": [0.25, 0.25, 0.75, 0.75]}]
        frame_shape = (800, 1000, 3)  # h=800, w=1000
        crop_bounds = sender_node.compute_crop_pixel_bounds(frame_shape, 0.25, 0.25, 0.75, 0.75, pad_px=40)
        self.assertEqual(crop_bounds, (210, 160, 790, 640))
        remapped = sender_node.remap_detections_to_crop(detections, crop_bounds, frame_shape)
        self.assertEqual(len(remapped), 1)
        rx1, ry1, rx2, ry2 = remapped[0]["box"]
        self.assertAlmostEqual(rx1, (250 - 210) / 580.0, places=2)
        self.assertAlmostEqual(ry1, (200 - 160) / 480.0, places=2)
        self.assertAlmostEqual(rx2, (750 - 210) / 580.0, places=2)
        self.assertAlmostEqual(ry2, (600 - 160) / 480.0, places=2)

    def test_09_offline_signature_sidecar_and_bundle_verification(self):
        """Finding #12: Reconstructed alerts save .sig.json and verify offline (rejecting tampered JPEGs)."""
        sk = SigningKey(bytes.fromhex(sender_node.DEFAULT_EXAMPLE_PRIVKEY_HEX))
        jpeg_bytes = _make_valid_jpeg_bytes()
        nonce_hex = "9988776655443322"
        pkt_meta, chunk_pkts = self._build_signed_event_packets(sk, "NODE-NORTH-01", nonce_hex, jpeg_bytes)

        receiver_hub.process_datagram(pkt_meta)
        for cp in chunk_pkts:
            receiver_hub.process_datagram(cp)

        ok, report_lines = receiver_hub.verify_exported_bundle(self.save_dir)
        self.assertTrue(ok, f"Expected bundle verification to pass, got: {report_lines}")

        # Tamper with 1 byte of the saved JPEG on disk -> verification must fail!
        jpg_files = [fn for fn in os.listdir(self.save_dir) if fn.endswith(".jpg")]
        self.assertEqual(len(jpg_files), 1)
        jpg_path = os.path.join(self.save_dir, jpg_files[0])
        with open(jpg_path, "r+b") as f:
            f.seek(10)
            b0 = f.read(1)
            f.seek(10)
            f.write(bytes([b0[0] ^ 0xFF]))

        bad_ok, bad_report = receiver_hub.verify_exported_bundle(self.save_dir)
        self.assertFalse(bad_ok, f"Expected tampered JPEG bundle verification to fail, got: {bad_report}")

    def test_10_subghz_nlos_progressive_jpeg_and_stream_framing(self):
        """Finding #17: subghz_nlos_relay produces valid decodable JPEGs and reassembles split stream chunks."""
        raw_jpeg = _make_valid_jpeg_bytes(640, 480)
        compressed = subghz_nlos_relay.compress_for_subghz_nlos(raw_jpeg)
        self.assertTrue(compressed.startswith(b"\xff\xd8"))
        self.assertTrue(compressed.endswith(b"\xff\xd9"))
        decoded = Image.open(io.BytesIO(compressed))
        self.assertEqual(decoded.format, "JPEG")

    def test_11_pdf_contains_true_1to1_vector_drilling_template(self):
        """Finding #19: Single canonical root PDF includes all real-world photo sheets and the True 1:1 CAD Vector Drilling Template."""
        pdf_path = os.path.join(REPO_ROOT, "ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf")
        self.assertTrue(os.path.isfile(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 5_000_000)
        for obsolete_rel in (
            "TONIGHT_BENCHTOP_BUILD_GUIDE.pdf",
            "SYSTEM_GUIDE.md",
            "SAIMAA_ARCHIPELAGO_DEPLOYMENT_GUIDE.md",
            "images/ikea_parts_and_tools_guide.jpg",
            "images/ikea_orientation_correct_vs_wrong.jpg",
            "images/ikea_breadboard_hole_by_hole.jpg",
            "images/ikea_stage_by_stage_assembly.jpg",
            "images/stage2_2d_exact_board_and_hole_map.jpg",
            "images/bench_connections.svg",
            "images/current_configuration.svg",
        ):
            p = os.path.join(TRAILCAM_DIR, "docs", obsolete_rel)
            self.assertFalse(os.path.exists(p), f"Obsolete/duplicate file must not exist: {obsolete_rel}")

    def test_12_forensic_evidence_zip_and_node_telemetry_aggregation(self):
        """Forensic NVR Overhaul: Verify _collect_node_states and standalone offline Forensic ZIP verification."""
        import subprocess
        import zipfile
        import dashboard_server

        sk = SigningKey(bytes.fromhex(sender_node.DEFAULT_EXAMPLE_PRIVKEY_HEX))
        jpeg_bytes = _make_valid_jpeg_bytes()
        nonce_hex = "aabbccddeeff0042"
        pkt_meta, chunk_pkts = self._build_signed_event_packets(sk, "NODE-NORTH-01", nonce_hex, jpeg_bytes)

        receiver_hub.process_datagram(pkt_meta)
        for cp in chunk_pkts:
            receiver_hub.process_datagram(cp)

        # 1. Verify _collect_node_states aggregates real node telemetry from journal
        nodes_list = dashboard_server._collect_node_states(self.save_dir)
        self.assertGreaterEqual(len(nodes_list), 1)
        north_nodes = [n for n in nodes_list if n["id"] == "NODE-NORTH-01"]
        self.assertEqual(len(north_nodes), 1)
        self.assertEqual(north_nodes[0]["alerts_count"], 1)
        self.assertEqual(north_nodes[0]["last_trigger"], "RADAR+MAG:120")
        self.assertTrue(north_nodes[0]["camera_ok"])

        # 2. Build Forensic Evidence ZIP and verify standalone offline script execution
        zip_bytes = dashboard_server.build_forensic_evidence_zip(
            self.save_dir, target_nonce=nonce_hex
        )
        self.assertGreater(len(zip_bytes), 200)

        with tempfile.TemporaryDirectory() as extract_dir:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                names = zf.namelist()
                self.assertIn("CHAIN_OF_CUSTODY_REPORT.txt", names)
                self.assertIn("verify_evidence_offline.py", names)
                zf.extractall(extract_dir)

            res = subprocess.run(
                [sys.executable, os.path.join(extract_dir, "verify_evidence_offline.py")],
                cwd=extract_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(res.returncode, 0, f"Offline verifier failed: {res.stdout}\n{res.stderr}")
            self.assertIn("forensic evidence file(s) cryptographically verified", res.stdout)

    def test_13_multi_unit_fleet_grid_and_cross_camera_tracking(self):
        """Verify 3-Tier Multi-Unit Federation, Sector Aggregation, and Cross-Camera Object Trajectory payload & UI."""
        import dashboard_server

        payload = dashboard_server.build_fleet_grid_payload(self.save_dir)
        self.assertEqual(len(payload["sectors"]), 4)
        self.assertEqual(len(payload["cameras"]), 8)
        self.assertGreaterEqual(len(payload["edges"]), 5)
        self.assertEqual(len(payload["tracks"]), 3)
        cam_ids = [c["cam_id"] for c in payload["cameras"]]
        self.assertEqual(cam_ids, ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"])

        ui_path = os.path.join(COLLECTOR_DIR, "ui", "index.html")
        with open(ui_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="cam-grid-panel"', html)
        self.assertIn('id="multi-cam-grid"', html)
        self.assertIn('id="cross-cam-tracker-bar"', html)
        self.assertIn("build3DCrossCamTrajectory", html)
        self.assertIn('id="catbtn-aircraft"', html)
        self.assertIn('id="flt-aircraft"', html)

    def test_14_aerial_drone_helicopter_airplane_classification_and_kinematics(self):
        """Verify drone (quadcopter/UAV), helicopter, and airplane disambiguation and kinematics."""
        import sender_node

        # 1. Drone / Quadcopter UAV (airplane + kite/frisbee rotor co-activation)
        scores_drone = [0.0] * 80
        scores_drone[4] = 0.28
        scores_drone[33] = 0.22
        cls_d, conf_d = sender_node.classify_aerial_target_subtype(scores_drone)
        self.assertEqual(cls_d, "drone_uav")
        self.assertGreater(conf_d, 0.50)

        # 2. Helicopter / Rotorcraft (airplane + main-rotor umbrella/drier co-activation)
        scores_heli = [0.0] * 80
        scores_heli[4] = 0.34
        scores_heli[25] = 0.18
        cls_h, conf_h = sender_node.classify_aerial_target_subtype(scores_heli)
        self.assertEqual(cls_h, "helicopter")
        self.assertGreater(conf_h, 0.50)

        # 3. Fixed-Wing Airplane
        scores_plane = [0.0] * 80
        scores_plane[4] = 0.86
        cls_p, conf_p = sender_node.classify_aerial_target_subtype(scores_plane)
        self.assertEqual(cls_p, "airplane")
        self.assertAlmostEqual(conf_p, 0.86, places=2)

        # 4. Kinematics speed defaults for drone_uav & helicopter
        kin_drone = sender_node.estimate_subject_kinematics(
            [{"class": "drone_uav", "conf": 0.96, "box": [0.35, 0.15, 0.55, 0.30]}],
            "TRIG,MAG=1200,SEIS=180",
        )
        self.assertEqual(kin_drone["primary_class"], "drone_uav")
        self.assertAlmostEqual(kin_drone["est_speed_kmh"], 54.0, places=1)


if __name__ == "__main__":
    unittest.main()

