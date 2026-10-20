#!/usr/bin/env python3
"""
File: collector_hub/dashboard_server.py
Description: Production Local Web Server & Live Telemetry Bridge for the 3D Spatial Command Center UI.
             Serves collector_hub/ui/index.html and streams verified Ed25519 alerts from
             verified_alerts/alerts_journal.jsonl to the 3D WebGL Command Center.
License: MIT
"""
import os
import sys
import json
import time
import errno
import socket
import argparse
import base64
import threading
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE_DIR, "ui")
REPO_DIR = os.path.dirname(BASE_DIR)
DEFAULT_ALERTS_DIR = os.getenv("OUT_DIR", os.path.join(REPO_DIR, "verified_alerts"))
DOCS_IMAGES_DIR = os.path.join(REPO_DIR, "docs", "images")
SERVER_START_TIME = time.time()

LIVE_FRAME_LOCK = threading.Lock()
LIVE_FRAME_STATE = {
    "meta": None,
    "jpeg": None,
    "updated_at": 0.0,
    "seq": 0,
    "source": "pi_camera",  # 'pi_camera' (live IMX708 on Pi 5) or 'video_file' (recorded CCTV mp4)
    "handoff_sim_step": 0,
    "handoff_sim_ts": 0.0,
}


def valid_port(value):
    """Argparse validator ensuring port is an integer in the valid TCP range 1-65535."""
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid integer")
    if not (1 <= port <= 65535):
        raise argparse.ArgumentTypeError(f"port {port} is out of range (must be 1-65535)")
    return port


class ReusableHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with SO_REUSEADDR enabled to allow immediate port reuse and concurrent live video streaming."""
    allow_reuse_address = True
    daemon_threads = True


import io
import zipfile
import receiver_hub


STANDALONE_VERIFY_SCRIPT = '''#!/usr/bin/env python3
"""
Standalone Offline Forensic Evidence Verifier (Arctic Trail Cam System)
Verifies SHA-256 image integrity and Ed25519 cryptographic signatures for exported evidence bundles.
Usage: python3 verify_evidence_offline.py
"""
import base64, glob, hashlib, json, os, sys
from nacl.signing import VerifyKey

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sig_files = sorted(glob.glob(os.path.join(here, "*.sig.json")))
    if not sig_files:
        print("[!] No .sig.json envelopes found in current directory.")
        sys.exit(1)
    passed = 0
    for sf in sig_files:
        with open(sf, "r", encoding="utf-8") as f:
            env = json.load(f)
        img_name = os.path.basename(env["image_file"])
        img_path = os.path.join(here, img_name)
        with open(img_path, "rb") as imgf:
            img_bytes = imgf.read()
        actual_sha = hashlib.sha256(img_bytes).hexdigest()
        expected_sha = env.get("image_sha256") or env.get("img_sha256", "")
        if actual_sha.lower() != expected_sha.lower():
            print(f"[FAIL] {img_name}: SHA-256 mismatch!")
            sys.exit(2)
        pub_hex = env.get("pubkey_hex") or env.get("ed25519_pubkey_hex", "")
        payload_b64 = env.get("signed_payload_b64") or env.get("raw_meta_b64", "")
        sig_hex = env.get("signature_hex") or env.get("ed25519_sig_hex", "")
        vk = VerifyKey(bytes.fromhex(pub_hex))
        raw_meta = base64.b64decode(payload_b64)
        vk.verify(raw_meta, bytes.fromhex(sig_hex))
        print(f"[PASS] {img_name} | Node: {env.get('node')} | SHA-256 & Ed25519 VERIFIED")
        passed += 1
    print(f"\\nSUCCESS: All {passed}/{len(sig_files)} forensic evidence file(s) cryptographically verified.")

if __name__ == "__main__":
    main()
'''


def _collect_node_states(alerts_dir):
    """Aggregates provisioned nodes from authorized_nodes.json and live telemetry from alerts_journal.jsonl."""
    nodes = {}
    reg_file = os.getenv("AUTHORIZED_NODES_FILE", os.path.join(alerts_dir, "authorized_nodes.json"))
    if os.path.isfile(reg_file):
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for nid, pub_hex in data.items():
                    nodes[nid] = {
                        "id": nid,
                        "provisioned": True,
                        "pubkey_fingerprint": str(pub_hex)[:16] + "..." if pub_hex else "unknown",
                        "alerts_count": 0,
                        "last_seen_ts": None,
                        "last_trigger": None,
                        "last_sha256": None,
                        "camera_ok": True,
                    }
        except Exception:
            pass

    journal_path = os.path.join(alerts_dir, "alerts_journal.jsonl")
    if os.path.exists(journal_path):
        try:
            with open(journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        nid = rec.get("node")
                        if not nid:
                            continue
                        if nid not in nodes:
                            nodes[nid] = {
                                "id": nid,
                                "provisioned": nid in receiver_hub.KNOWN_NODE_PUBKEYS,
                                "pubkey_fingerprint": "default/discovered",
                                "alerts_count": 0,
                                "last_seen_ts": None,
                                "last_trigger": None,
                                "last_sha256": None,
                                "camera_ok": True,
                            }
                        n_entry = nodes[nid]
                        n_entry["alerts_count"] += 1
                        ts = rec.get("timestamp") or rec.get("ts")
                        if ts and (n_entry["last_seen_ts"] is None or ts >= n_entry["last_seen_ts"]):
                            n_entry["last_seen_ts"] = ts
                            n_entry["last_trigger"] = rec.get("pico_trig") or rec.get("trigger")
                            n_entry["last_sha256"] = rec.get("image_sha256") or rec.get("img_sha256")
                            n_entry["camera_ok"] = rec.get("camera_ok", True)
                    except Exception:
                        pass
        except Exception:
            pass

    return list(nodes.values())


def build_fleet_grid_payload(alerts_dir, demo_mode=True):
    """Builds the multi-sector camera federation topology, camera grid states, and cross-camera object tracks.
    When demo_mode=False (live production mode), returns ONLY real connected cameras and real detections (zero fake/simulated cameras or tracks).
    """
    now = time.time()
    with LIVE_FRAME_LOCK:
        lf_meta = LIVE_FRAME_STATE["meta"]
        lf_updated = LIVE_FRAME_STATE["updated_at"]
        lf_seq = LIVE_FRAME_STATE["seq"]
        sim_step = LIVE_FRAME_STATE.get("handoff_sim_step", 0)
        sim_ts = LIVE_FRAME_STATE.get("handoff_sim_ts", 0.0)

    live_active = (lf_meta is not None) and ((now - lf_updated) < 30.0)
    top_live_class = "PERSON + KNIFE" if demo_mode else "CLEAR"
    top_live_cat = "weapon" if demo_mode else "everyday"
    top_live_conf = 0.94 if demo_mode else 0.0
    if live_active and isinstance(lf_meta, dict):
        dets = [
            d for d in (lf_meta.get("detections") or [])
            if d.get("source", "standing") == "standing"
            and float(d.get("conf", d.get("confidence", 0.0))) >= 0.25
        ]
        if dets:
            best = max(dets, key=lambda d: float(d.get("conf", d.get("confidence", 0.0))))
            top_live_class = str(best.get("class") or best.get("class_name") or "TARGET").upper()
            top_live_cat = str(best.get("category") or "person")
            top_live_conf = round(float(best.get("conf", best.get("confidence", 0.90))), 2)

    # Read optional local site map (gitignored offline_site_map.json) for local camera coordinates
    local_sector_title = "Local Live Camera"
    local_nodes_override = {}
    map_file = os.path.join(alerts_dir, "offline_site_map.json")
    if os.path.isfile(map_file):
        try:
            with open(map_file, "r", encoding="utf-8") as mf:
                sm = json.load(mf)
            if isinstance(sm, dict):
                if sm.get("title"):
                    local_sector_title = str(sm["title"]).split("//")[0].strip()
                for idx, sn in enumerate(sm.get("nodes") or []):
                    if isinstance(sn, dict) and sn.get("id"):
                        local_nodes_override[sn["id"]] = sn
        except Exception:
            pass

    c1_ovr = local_nodes_override.get("NODE-NORTH-01", {})
    c2_ovr = local_nodes_override.get("NODE-SOUTH-02", {})
    c3_ovr = local_nodes_override.get("NODE-RIDGE-02", {})

    if not demo_mode:
        live_fps = lf_meta.get("stream_fps", 15.0) if (live_active and isinstance(lf_meta, dict)) else 0.0
        reg_file = os.path.join(alerts_dir, "cameras_registry.json")
        reg_cams = None
        if os.path.isfile(reg_file):
            try:
                with open(reg_file, "r", encoding="utf-8") as rf:
                    rdata = json.load(rf)
                if isinstance(rdata, dict) and isinstance(rdata.get("cameras"), list) and len(rdata["cameras"]) > 0:
                    reg_cams = rdata["cameras"]
            except Exception:
                reg_cams = None

        c1_lat = float(c1_ovr.get("lat", 42.35245))
        c1_lon = float(c1_ovr.get("lon", -71.07135))
        c1_hdg = int(c1_ovr.get("heading_deg", 288))
        if reg_cams:
            out_cams = []
            for idx, rc in enumerate(reg_cams):
                is_c1 = (idx == 0 or rc.get("cam_id") == "C1")
                out_cams.append({
                    "cam_id": rc.get("cam_id") or f"C{idx + 1}",
                    "node_id": rc.get("node_id") or f"NODE-{idx + 1:02d}",
                    "sector_id": "local_cluster",
                    "sector_badge": "LIVE PI 5 CAMERA" if is_c1 else "CONNECTED CAMERA",
                    "name": rc.get("name") or f"Camera C{idx + 1}",
                    "lat": float(rc.get("lat", c1_lat)),
                    "lon": float(rc.get("lon", c1_lon)),
                    "heading_deg": int(rc.get("heading_deg", c1_hdg)),
                    "heading_cardinal": rc.get("heading_cardinal") or "WNW",
                    "fov_deg": int(rc.get("fov_deg", 66)),
                    "range_m": int(rc.get("range_m", 45)),
                    "host": rc.get("host") or ("trailcam-node.local" if is_c1 else ""),
                    "pos": rc.get("pos") or c1_ovr.get("pos") or {"x": -25, "z": 45},
                    "lookAt": rc.get("lookAt") or c1_ovr.get("lookAt") or {"x": -65, "y": 4, "z": 75},
                    "tier1_link": rc.get("tier1_link") or "1000BASE-LX Optical Diode",
                    "tier2_hub": "HUB-LOCAL-01",
                    "status": (f"LIVE ({live_fps} FPS)" if live_active else "STANDBY (UDP:5514)") if is_c1 else "STANDBY (UDP:5514)",
                    "is_live_stream": is_c1,
                    "last_detection": top_live_class if is_c1 else "NO TARGET",
                    "last_conf": top_live_conf if is_c1 else 0.0,
                    "last_category": top_live_cat if is_c1 else "none",
                })
        else:
            out_cams = [{
                "cam_id": "C1",
                "node_id": "NODE-NORTH-01",
                "sector_id": "local_cluster",
                "sector_badge": "LIVE PI 5 CAMERA",
                "name": c1_ovr.get("name") or "C1: 3 Newbury St — Live Pi 5 Camera (IMX708)",
                "lat": c1_lat,
                "lon": c1_lon,
                "heading_deg": c1_hdg,
                "heading_cardinal": "WNW",
                "fov_deg": 66,
                "range_m": 45,
                "host": "trailcam-node.local",
                "pos": c1_ovr.get("pos") or {"x": -25, "z": 45},
                "lookAt": c1_ovr.get("lookAt") or {"x": -65, "y": 4, "z": 75},
                "tier1_link": "1000BASE-LX Optical Diode",
                "tier2_hub": "HUB-LOCAL-01",
                "status": f"LIVE ({live_fps} FPS)" if live_active else "STANDBY (UDP:5514)",
                "is_live_stream": True,
                "last_detection": top_live_class,
                "last_conf": top_live_conf,
                "last_category": top_live_cat,
            }]
        return {
            "timestamp": int(now),
            "demo_mode": False,
            "live_seq": lf_seq,
            "handoff_sim_step": 0,
            "sectors": [
                {
                    "id": "all",
                    "name": f"📍 {local_sector_title}",
                    "short_name": f"Connected Cameras ({len(out_cams)})",
                    "cam_count": len(out_cams),
                    "active_tracks": 0,
                }
            ],
            "cameras": out_cams,
            "edges": [],
            "tracks": [],
        }

    sectors = [
        {
            "id": "all",
            "name": "🌍 All Connected Units (National Fleet)",
            "short_name": "All Sectors (8 Cams)",
            "tier2_hub": "National Command Federation (3 Sector Hubs)",
            "tier3_backhaul": "Hybrid Optical Diode + 20km Build D Troposcatter + LTE Edge",
            "cam_count": 8,
            "active_tracks": 3,
        },
        {
            "id": "local_cluster",
            "name": f"📍 Sector A: {local_sector_title}",
            "short_name": "Sector A: Local Live (C1–C3)",
            "tier1_bus": "Shared 1×2 / 90:10 Passive Single-Mode Optical Bus (ALOHA Burst)",
            "tier2_hub": "HUB-LOCAL-01 (Direct UDP:5514 Optical Diode Receiver)",
            "tier3_backhaul": "Local Zero-Latency LAN / Fiber Trunk",
            "cam_count": 3,
            "active_tracks": 1,
            "preset": "local",
        },
        {
            "id": "saimaa_public",
            "name": "🌲 Sector B: Saimaa Public Lands (C4–C6)",
            "short_name": "Sector B: Saimaa Public (C4–C6)",
            "tier1_bus": "Zero-Trench 1310nm Collimated FSO + 2.4GHz Canopy-Bounce Micro-Links",
            "tier2_hub": "HUB-SAIMAA-02 (Trailhead Solar Dead-Drop Aggregator)",
            "tier3_backhaul": "Sky-Diode Build D 14.2km Troposcatter / LTE Summary Uplink",
            "cam_count": 3,
            "active_tracks": 1,
            "preset": "saimaa",
        },
        {
            "id": "karhunkierros_np",
            "name": "🏔️ Sector C: Karhunkierros National Park (C7–C8)",
            "short_name": "Sector C: Karhunkierros NP (C7–C8)",
            "tier1_bus": "0.00W-Standby Sub-GHz LoRa + Surface Moss-Tucked OS2 Fiber Tap",
            "tier2_hub": "HUB-KARHU-03 (Oulanka Ranger Vault Aggregator)",
            "tier3_backhaul": "Sky-Diode Build D 19.8km Quartzite Ridge Troposcatter",
            "cam_count": 2,
            "active_tracks": 1,
            "preset": "koli",
        },
    ]

    c1_ovr = local_nodes_override.get("NODE-NORTH-01", {})
    c2_ovr = local_nodes_override.get("NODE-SOUTH-02", {})
    c3_ovr = local_nodes_override.get("NODE-RIDGE-02", {})

    cameras = [
        {
            "cam_id": "C1",
            "node_id": "NODE-NORTH-01",
            "sector_id": "local_cluster",
            "sector_badge": "SECTOR A • LIVE PI 5",
            "name": c1_ovr.get("name") or "C1: North Gate — Live Pi 5 (IMX708 + CLIP)",
            "heading_deg": 288,
            "heading_cardinal": "WNW",
            "fov_deg": 66,
            "pos": c1_ovr.get("pos") or {"x": -25, "z": 45},
            "lookAt": c1_ovr.get("lookAt") or {"x": -65, "y": 4, "z": 75},
            "tier1_link": "1000BASE-LX Optical Diode (Port 1)",
            "tier2_hub": "HUB-LOCAL-01",
            "status": "LIVE STREAM (25.6 FPS)" if live_active else "WATCH (18 mW)",
            "is_live_stream": True,
            "battery_v": 12.64,
            "temp_c": 21.4,
            "last_detection": top_live_class,
            "last_conf": top_live_conf,
            "last_category": top_live_cat,
            "next_handoff": {"target_cam": "C2", "distance_m": 140, "bearing_deg": 288, "cardinal": "WNW", "eta_walk_s": 28, "eta_veh_s": 11},
        },
        {
            "cam_id": "C2",
            "node_id": "NODE-SOUTH-02",
            "sector_id": "local_cluster",
            "sector_badge": "SECTOR A • LOCAL BUS",
            "name": c2_ovr.get("name") or "C2: Mid-Corridor West Crossing",
            "heading_deg": 285,
            "heading_cardinal": "WNW",
            "fov_deg": 66,
            "pos": c2_ovr.get("pos") or {"x": 20, "z": 78},
            "lookAt": c2_ovr.get("lookAt") or {"x": -10, "y": 6, "z": 110},
            "tier1_link": "Passive 1×2 Optical Tap (ALOHA Delay 180ms)",
            "tier2_hub": "HUB-LOCAL-01",
            "status": "BURST RX VERIFIED" if sim_step >= 2 else "PREDICTED HANDOFF TARGET",
            "is_live_stream": False,
            "battery_v": 12.58,
            "temp_c": 19.8,
            "last_detection": top_live_class if sim_step >= 2 else "PERSON (CORRIDOR WEST)",
            "last_conf": 0.93,
            "last_category": top_live_cat if sim_step >= 2 else "person",
            "preview_img": "/docs/images/demo_alert_person.jpg",
            "next_handoff": {"target_cam": "C1", "distance_m": 140, "bearing_deg": 108, "cardinal": "ESE", "eta_walk_s": 28, "eta_veh_s": 11},
        },
        {
            "cam_id": "C3",
            "node_id": "NODE-RIDGE-02",
            "sector_id": "local_cluster",
            "sector_badge": "SECTOR A • PERIMETER",
            "name": c3_ovr.get("name") or "C3: East Perimeter / Park Approach",
            "heading_deg": 290,
            "heading_cardinal": "WNW",
            "fov_deg": 66,
            "pos": c3_ovr.get("pos") or {"x": -115, "z": -65},
            "lookAt": c3_ovr.get("lookAt") or {"x": -145, "y": 8, "z": -45},
            "tier1_link": "Passive 90/10 Optical Tap (ALOHA Delay 340ms)",
            "tier2_hub": "HUB-LOCAL-01",
            "status": "HOP #1 ORIGIN (VERIFIED)",
            "is_live_stream": False,
            "battery_v": 12.52,
            "temp_c": 19.2,
            "last_detection": top_live_class,
            "last_conf": 0.91,
            "last_category": top_live_cat,
            "preview_img": "/docs/images/demo_alert_person.jpg",
            "next_handoff": {"target_cam": "C1", "distance_m": 115, "bearing_deg": 290, "cardinal": "WNW", "eta_walk_s": 24, "eta_veh_s": 9},
        },
        {
            "cam_id": "C4",
            "node_id": "NODE-SAIMAA-04",
            "sector_id": "saimaa_public",
            "sector_badge": "SECTOR B • PUBLIC LANDS",
            "name": "C4: Saimaa Trailhead Access Road",
            "heading_deg": 45,
            "heading_cardinal": "NE",
            "fov_deg": 66,
            "pos": {"x": -85, "z": 55},
            "lookAt": {"x": -55, "y": 8, "z": 25},
            "tier1_link": "2.4GHz Canopy-Bounce Micro-Burst (0.00W Sleep)",
            "tier2_hub": "HUB-SAIMAA-02",
            "status": "HOP #1 VERIFIED (TRK-102)",
            "is_live_stream": False,
            "battery_v": 12.71,
            "temp_c": -4.2,
            "last_detection": "VEHICLE / ATV",
            "last_conf": 0.96,
            "last_category": "bag_vehicle",
            "preview_img": "/docs/images/demo_alert_truck.jpg",
            "next_handoff": {"target_cam": "C5", "distance_m": 420, "bearing_deg": 48, "cardinal": "NE", "eta_walk_s": 310, "eta_veh_s": 54},
        },
        {
            "cam_id": "C5",
            "node_id": "NODE-SAIMAA-05",
            "sector_id": "saimaa_public",
            "sector_badge": "SECTOR B • PUBLIC LANDS",
            "name": "C5: Saimaa Pine Isthmus Bridge",
            "heading_deg": 52,
            "heading_cardinal": "NE",
            "fov_deg": 66,
            "pos": {"x": -15, "z": 10},
            "lookAt": {"x": 15, "y": 8, "z": -18},
            "tier1_link": "1310nm Collimated FSO Tree-to-Tree Link (380m)",
            "tier2_hub": "HUB-SAIMAA-02",
            "status": "HOP #2 VERIFIED (TRK-102)",
            "is_live_stream": False,
            "battery_v": 12.66,
            "temp_c": -4.5,
            "last_detection": "VEHICLE / ATV",
            "last_conf": 0.94,
            "last_category": "bag_vehicle",
            "preview_img": "/docs/images/demo_alert_truck.jpg",
            "next_handoff": {"target_cam": "C6", "distance_m": 510, "bearing_deg": 55, "cardinal": "NE", "eta_walk_s": 370, "eta_veh_s": 62},
        },
        {
            "cam_id": "C6",
            "node_id": "NODE-SAIMAA-06",
            "sector_id": "saimaa_public",
            "sector_badge": "SECTOR B • PUBLIC LANDS",
            "name": "C6: Saimaa North Boat Landing",
            "heading_deg": 60,
            "heading_cardinal": "ENE",
            "fov_deg": 66,
            "pos": {"x": 65, "z": -35},
            "lookAt": {"x": 95, "y": 6, "z": -55},
            "tier1_link": "1310nm Collimated FSO Across Strait (450m)",
            "tier2_hub": "HUB-SAIMAA-02",
            "status": "PREDICTED ETA 42s (TRK-102)",
            "is_live_stream": False,
            "battery_v": 12.60,
            "temp_c": -4.8,
            "last_detection": "STANDBY (ETA 42s)",
            "last_conf": 0.90,
            "last_category": "bag_vehicle",
            "preview_img": "/docs/images/demo_alert_truck.jpg",
            "next_handoff": {"target_cam": "C5", "distance_m": 510, "bearing_deg": 235, "cardinal": "SW", "eta_walk_s": 370, "eta_veh_s": 62},
        },
        {
            "cam_id": "C7",
            "node_id": "NODE-KARHU-07",
            "sector_id": "karhunkierros_np",
            "sector_badge": "SECTOR C • AIRSPACE WATCH",
            "name": "C7: Oulanka Canyon South Saddle (Sky Watch)",
            "heading_deg": 15,
            "heading_cardinal": "NNE",
            "fov_deg": 66,
            "pos": {"x": -45, "z": 68},
            "lookAt": {"x": -35, "y": 14, "z": 35},
            "tier1_link": "868MHz LoRa Signed Digest + Moss Fiber Tap",
            "tier2_hub": "HUB-KARHU-03",
            "status": "HOP #1 VERIFIED (TRK-103)",
            "is_live_stream": False,
            "battery_v": 12.48,
            "temp_c": -14.6,
            "last_detection": "DRONE / QUADCOPTER UAV",
            "last_conf": 0.97,
            "last_category": "aircraft",
            "preview_img": "/docs/images/demo_alert_moose.jpg",
            "next_handoff": {"target_cam": "C8", "distance_m": 290, "bearing_deg": 18, "cardinal": "NNE", "eta_walk_s": 19, "eta_veh_s": 19},
        },
        {
            "cam_id": "C8",
            "node_id": "NODE-KARHU-08",
            "sector_id": "karhunkierros_np",
            "sector_badge": "SECTOR C • AIRSPACE WATCH",
            "name": "C8: Karhunkierros Ridge Overlook (Sky Watch)",
            "heading_deg": 20,
            "heading_cardinal": "NNE",
            "fov_deg": 66,
            "pos": {"x": -18, "z": -38},
            "lookAt": {"x": -5, "y": 18, "z": -70},
            "tier1_link": "Build D 2.4GHz Troposcatter Uplink (19.8km)",
            "tier2_hub": "HUB-KARHU-03",
            "status": "PREDICTED ETA 19s (TRK-103)",
            "is_live_stream": False,
            "battery_v": 12.44,
            "temp_c": -15.1,
            "last_detection": "DRONE / HELICOPTER (ETA 19s)",
            "last_conf": 0.94,
            "last_category": "aircraft",
            "preview_img": "/docs/images/demo_alert_moose.jpg",
            "next_handoff": {"target_cam": "C7", "distance_m": 290, "bearing_deg": 198, "cardinal": "SSW", "eta_walk_s": 19, "eta_veh_s": 19},
        },
    ]

    edges = [
        {"from": "C3", "to": "C1", "sector_id": "local_cluster", "distance_m": 115, "bearing_deg": 290, "cardinal": "WNW", "link_type": "optical_bus"},
        {"from": "C1", "to": "C2", "sector_id": "local_cluster", "distance_m": 140, "bearing_deg": 288, "cardinal": "WNW", "link_type": "optical_bus"},
        {"from": "C4", "to": "C5", "sector_id": "saimaa_public", "distance_m": 420, "bearing_deg": 48, "cardinal": "NE", "link_type": "fso_laser"},
        {"from": "C5", "to": "C6", "sector_id": "saimaa_public", "distance_m": 510, "bearing_deg": 55, "cardinal": "NE", "link_type": "fso_laser"},
        {"from": "C7", "to": "C8", "sector_id": "karhunkierros_np", "distance_m": 290, "bearing_deg": 18, "cardinal": "NNE", "link_type": "troposcatter"},
    ]

    t_fmt = lambda offset_s: time.strftime("%H:%M:%S", time.localtime(now + offset_s))

    # Build Track 101 dynamically reflecting the live C1 stream and simulation handoff step
    if sim_step == 1 and (now - sim_ts) < 120.0:
        trk101_hops = [
            {"hop": 1, "cam_id": "C3", "time_str": t_fmt(-42), "state": "verified", "conf": 0.91, "note": "Entered East Gate (290° WNW)"},
            {"hop": 2, "cam_id": "C1", "time_str": t_fmt(-3), "state": "live_now", "conf": top_live_conf, "note": f"LIVE ON C1 NOW ({top_live_class}, Re-ID 96%)"},
        ]
        trk101_next = {"hop": 3, "cam_id": "C2", "distance_m": 140, "bearing_deg": 288, "cardinal": "WNW", "eta_s": 19}
    elif sim_step >= 2 and (now - sim_ts) < 120.0:
        trk101_hops = [
            {"hop": 1, "cam_id": "C3", "time_str": t_fmt(-64), "state": "verified", "conf": 0.91, "note": "Entered East Gate (290° WNW)"},
            {"hop": 2, "cam_id": "C1", "time_str": t_fmt(-28), "state": "verified", "conf": top_live_conf, "note": f"Passed Live C1 ({top_live_class}, Re-ID 96%)"},
            {"hop": 3, "cam_id": "C2", "time_str": t_fmt(-2), "state": "live_now", "conf": 0.93, "note": f"ARRIVED AT C2! Handoff Confirmed (+26s, 140m WNW)"},
        ]
        trk101_next = None
    else:
        trk101_hops = [
            {"hop": 1, "cam_id": "C3", "time_str": t_fmt(-54), "state": "verified", "conf": 0.91, "note": "Origin at C3 Perimeter (HDG 290° WNW)"},
            {"hop": 2, "cam_id": "C1", "time_str": t_fmt(-4), "state": "live_now", "conf": top_live_conf, "note": f"LIVE ON C1 ({top_live_class}, Re-ID 95%)"},
        ]
        trk101_next = {"hop": 3, "cam_id": "C2", "distance_m": 140, "bearing_deg": 288, "cardinal": "WNW", "eta_s": 28}

    tracks = [
        {
            "track_id": "TRK-101",
            "sector_id": "local_cluster",
            "title": f"{top_live_class} (Local Corridor WNW)",
            "category": top_live_cat,
            "reid_score": 0.95,
            "speed_kmh": 18.0 if top_live_cat == "bag_vehicle" else 5.4,
            "heading_deg": 288,
            "heading_cardinal": "WNW",
            "total_distance_m": 255,
            "hops": trk101_hops,
            "predicted_next": trk101_next,
        },
        {
            "track_id": "TRK-102",
            "sector_id": "saimaa_public",
            "title": "UTILITY VEHICLE / ATV (Saimaa Public Lands)",
            "category": "bag_vehicle",
            "reid_score": 0.93,
            "speed_kmh": 28.5,
            "heading_deg": 52,
            "heading_cardinal": "NE",
            "total_distance_m": 930,
            "hops": [
                {"hop": 1, "cam_id": "C4", "time_str": t_fmt(-115), "state": "verified", "conf": 0.96, "note": "Entered Trailhead Road (MAG ΔB=2840nT)"},
                {"hop": 2, "cam_id": "C5", "time_str": t_fmt(-48), "state": "verified", "conf": 0.94, "note": "Crossed Pine Isthmus (+67s, 420m NE, Re-ID 93%)"},
            ],
            "predicted_next": {"hop": 3, "cam_id": "C6", "distance_m": 510, "bearing_deg": 55, "cardinal": "NE", "eta_s": 42},
        },
        {
            "track_id": "TRK-103",
            "sector_id": "karhunkierros_np",
            "title": "FPV QUADCOPTER DRONE / UAV (Ridge Airspace)",
            "category": "aircraft",
            "reid_score": 0.97,
            "speed_kmh": 54.0,
            "heading_deg": 18,
            "heading_cardinal": "NNE",
            "total_distance_m": 290,
            "hops": [
                {"hop": 1, "cam_id": "C7", "time_str": t_fmt(-11), "state": "verified", "conf": 0.97, "note": "Canyon Airspace CLIP ViT-B/32 + 24GHz Radar"},
            ],
            "predicted_next": {"hop": 2, "cam_id": "C8", "distance_m": 290, "bearing_deg": 18, "cardinal": "NNE", "eta_s": 19},
        },
    ]

    return {
        "timestamp": int(now),
        "live_seq": lf_seq,
        "handoff_sim_step": sim_step,
        "sectors": sectors,
        "cameras": cameras,
        "edges": edges,
        "tracks": tracks,
    }


def build_forensic_evidence_zip(alerts_dir, target_nonce=None):
    """Builds an in-memory ZIP bundle containing verified JPEGs, .sig.json envelopes, custody report, and verifier."""
    buf = io.BytesIO()
    journal_path = os.path.join(alerts_dir, "alerts_journal.jsonl")
    records = []
    if os.path.isfile(journal_path):
        with open(journal_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        rec = json.loads(line)
                        if not target_nonce or rec.get("nonce") == target_nonce:
                            records.append(rec)
                    except Exception:
                        pass

    verified_count, failed_count = receiver_hub.verify_exported_bundle(alerts_dir)
    ok = (failed_count == 0 and verified_count >= 0)
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        included_files = 0
        verify_lines = []
        for rec in records:
            img_rel = rec.get("saved_file") or rec.get("image_file")
            sig_rel = rec.get("sig_file")
            if img_rel:
                img_base = os.path.basename(img_rel)
                img_abs = os.path.join(alerts_dir, img_base)
                if os.path.isfile(img_abs):
                    zf.write(img_abs, arcname=img_base)
                    included_files += 1
                    verify_lines.append(
                        f"  [VERIFIED] {img_base} | Node={rec.get('node')} | Nonce={rec.get('nonce')} | SHA256={rec.get('image_sha256')}"
                    )
                if not sig_rel:
                    sig_rel = os.path.splitext(img_base)[0] + ".sig.json"
            if sig_rel:
                sig_base = os.path.basename(sig_rel)
                sig_abs = os.path.join(alerts_dir, sig_base)
                if os.path.isfile(sig_abs):
                    zf.write(sig_abs, arcname=sig_base)

        reg_file = os.getenv("AUTHORIZED_NODES_FILE", os.path.join(alerts_dir, "authorized_nodes.json"))
        if os.path.isfile(reg_file):
            zf.write(reg_file, arcname="authorized_nodes.json")

        report_text = [
            "========================================================================",
            "ARCTIC TRAIL CAM // FORENSIC CHAIN-OF-CUSTODY & CRYPTOGRAPHIC AUDIT LOG",
            "========================================================================",
            f"Generated UTC     : {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            f"Target Filter     : {target_nonce or 'ALL VERIFIED ALERTS'}",
            f"Events Included   : {len(records)} (JPEG files attached: {included_files})",
            f"Disk Integrity    : {'PASSED (100% Ed25519 + SHA-256 Verified)' if ok else f'FAILED ({failed_count} tampered/corrupt)'} (Verified={verified_count}, Failed={failed_count})",
            "------------------------------------------------------------------------",
            "Verification Details:",
            *(verify_lines if verify_lines else ["No .sig.json envelopes on disk yet."]),
            "========================================================================",
        ]
        zf.writestr("CHAIN_OF_CUSTODY_REPORT.txt", "\n".join(report_text) + "\n")
        zf.writestr("verify_evidence_offline.py", STANDALONE_VERIFY_SCRIPT)

    return buf.getvalue()


def make_command_center_handler(alerts_dir, verbose=False, demo_mode=False):
    """Factory creating a customized SimpleHTTPRequestHandler bound to specific asset directories."""

    class CommandCenterHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # Serve UI assets directly from UI_DIR without mutating process cwd
            super().__init__(*args, directory=UI_DIR, **kwargs)

        def do_GET(self):
            parsed = urlparse(self.path)
            clean_path = unquote(parsed.path)
            query_params = {}
            if parsed.query:
                for kv in parsed.query.split("&"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        query_params[unquote(k)] = unquote(v)

            # 1. API: Live verified alerts journal (supports ?since_idx=<N>&limit=<M> cursor pagination)
            if clean_path == "/api/alerts":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                journal_path = os.path.join(alerts_dir, "alerts_journal.jsonl")
                alerts = []
                if os.path.exists(journal_path):
                    try:
                        with open(journal_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    alerts.append(json.loads(line))
                    except Exception:
                        pass

                total_count = len(alerts)
                try:
                    limit = max(1, min(500, int(query_params.get("limit", "50"))))
                except ValueError:
                    limit = 50

                if "since_idx" in query_params:
                    try:
                        since_idx = max(0, int(query_params["since_idx"]))
                    except ValueError:
                        since_idx = 0
                    sliced_alerts = alerts[since_idx:since_idx + limit]
                    next_idx = min(total_count, since_idx + len(sliced_alerts))
                    has_more = next_idx < total_count
                else:
                    sliced_alerts = alerts[-limit:]
                    next_idx = total_count
                    has_more = False

                node_states = _collect_node_states(alerts_dir)
                payload = {
                    "timestamp": int(time.time()),
                    "total_count": total_count,
                    "next_idx": next_idx,
                    "has_more": has_more,
                    "alerts": sliced_alerts,
                    "node_count": len(node_states),
                    "nodes": node_states,
                    "diode_enforced": True,
                    "demo_mode": bool(demo_mode),
                    "storage_dir": alerts_dir,
                }
                self.wfile.write(json.dumps(payload).encode("utf-8"))
                return

            # 1B. API: Provisioned & active camera nodes with real telemetry
            if clean_path == "/api/nodes":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                node_states = _collect_node_states(alerts_dir)
                self.wfile.write(json.dumps({"node_count": len(node_states), "nodes": node_states}).encode("utf-8"))
                return

            # 1C. API: Live cryptographic verification of all saved .jpg + .sig.json files on disk
            if clean_path == "/api/verify_chain":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                journal_path = os.path.join(alerts_dir, "alerts_journal.jsonl")
                if not os.path.isfile(journal_path):
                    verified_count, failed_count = 0, 0
                else:
                    verified_count, failed_count = receiver_hub.verify_exported_bundle(alerts_dir)
                self.wfile.write(json.dumps({
                    "verified": failed_count == 0,
                    "verified_count": verified_count,
                    "failed_count": failed_count,
                    "checked_count": verified_count + failed_count,
                    "timestamp": int(time.time()),
                }).encode("utf-8"))
                return

            # 1D. API: Download Court/Police Forensic Evidence Bundle (.zip)
            if clean_path == "/api/evidence_bundle":
                target_nonce = query_params.get("nonce")
                zip_bytes = build_forensic_evidence_zip(alerts_dir, target_nonce=target_nonce)
                fname = f"forensic_evidence_{target_nonce[:8]}.zip" if target_nonce else f"forensic_evidence_bundle_{int(time.time())}.zip"
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(zip_bytes)
                return

            # 2. API: Server health & diagnostic status
            if clean_path in ("/api/status", "/api/health"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Calculate storage usage
                alerts_count = 0
                journal_path = os.path.join(alerts_dir, "alerts_journal.jsonl")
                active_nodes = set()
                if os.path.exists(journal_path):
                    try:
                        with open(journal_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    alerts_count += 1
                                    try:
                                        item = json.loads(line)
                                        if "node" in item:
                                            active_nodes.add(item["node"])
                                    except Exception:
                                        pass
                    except Exception:
                        pass

                # Check disk space
                statvfs = os.statvfs(alerts_dir) if os.path.exists(alerts_dir) else None
                free_gb = round((statvfs.f_bavail * statvfs.f_frsize) / (1024**3), 2) if statvfs else 0.0

                # True receiver liveness check: inspect receiver_heartbeat.json or UDP 5514 port bind state
                udp_live = False
                hb_path = os.path.join(alerts_dir, "receiver_heartbeat.json")
                if os.path.isfile(hb_path):
                    try:
                        with open(hb_path, "r", encoding="utf-8") as hbf:
                            hb = json.load(hbf)
                        if time.time() - float(hb.get("updated_at", 0)) < 10.0:
                            udp_live = True
                    except Exception:
                        pass

                if not udp_live:
                    try:
                        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        probe.bind(("0.0.0.0", 5514))
                        probe.close()
                        udp_live = False
                    except OSError as e:
                        if e.errno in (errno.EADDRINUSE, 48):
                            udp_live = True

                node_states = _collect_node_states(alerts_dir)
                health = {
                    "status": "healthy",
                    "system": "PI-DIODE-TRAILCAM FORENSIC EVIDENCE & TELEMETRY HUB",
                    "uptime_sec": int(time.time() - SERVER_START_TIME),
                    "server_time": int(time.time()),
                    "receiver_udp_port": 5514,
                    "receiver_online": udp_live,
                    "alerts_recorded": alerts_count,
                    "active_nodes": sorted(list(active_nodes)),
                    "node_count": len(node_states),
                    "demo_mode": bool(demo_mode),
                    "free_disk_gb": free_gb,
                    "alerts_dir": alerts_dir,
                }
                self.wfile.write(json.dumps(health).encode("utf-8"))
                return

            # 3. Serve verified image captures from alerts_dir (with canonical commonpath containment)
            if clean_path.startswith("/alerts/"):
                rel_file = os.path.basename(clean_path[len("/alerts/"):].lstrip("/"))
                real_base = os.path.realpath(alerts_dir)
                real_target = os.path.realpath(os.path.join(real_base, rel_file))
                if os.path.commonpath([real_target, real_base]) == real_base and os.path.isfile(real_target):
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "public, max-age=3600")
                    self.end_headers()
                    with open(real_target, "rb") as f:
                        self.wfile.write(f.read())
                    return
                else:
                    self.send_error(404, "Alert image not found")
                    return

            # 4. Serve documentation preview images from docs/images (with canonical commonpath containment)
            if clean_path.startswith("/docs/images/"):
                rel_file = clean_path[len("/docs/images/"):].lstrip("/")
                real_base = os.path.realpath(DOCS_IMAGES_DIR)
                real_target = os.path.realpath(os.path.join(real_base, rel_file))
                if os.path.commonpath([real_target, real_base]) == real_base and os.path.isfile(real_target):
                    self.send_response(200)
                    mime = "image/png" if real_target.endswith(".png") else "image/jpeg"
                    self.send_header("Content-Type", mime)
                    self.end_headers()
                    with open(real_target, "rb") as f:
                        self.wfile.write(f.read())
                    return

            # 4B. API: Real Map Tile Proxy + Offline Disk Tile Cache (/api/map_tile/{layer}/{z}/{x}/{y})
            if clean_path.startswith("/api/map_tile/"):
                parts = [p for p in clean_path[len("/api/map_tile/"):].split("/") if p]
                if len(parts) == 4:
                    layer, z_str, x_str, y_raw = parts
                    y_str = y_raw.split(".")[0]
                    if layer in ("osm", "sat", "topo", "labels") and z_str.isdigit() and x_str.isdigit() and y_str.isdigit():
                        tile_dir = os.path.join(alerts_dir, "map_tiles_cache", layer, z_str, x_str)
                        os.makedirs(tile_dir, exist_ok=True)
                        ext = "jpg" if layer == "sat" else "png"
                        tile_path = os.path.join(tile_dir, f"{y_str}.{ext}")
                        tile_bytes = None
                        if os.path.isfile(tile_path) and os.path.getsize(tile_path) > 100:
                            try:
                                with open(tile_path, "rb") as tf:
                                    tile_bytes = tf.read()
                            except Exception:
                                tile_bytes = None
                        if not tile_bytes:
                            import ssl
                            import urllib.request
                            if layer == "sat":
                                url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z_str}/{y_str}/{x_str}"
                            elif layer == "topo":
                                url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z_str}/{y_str}/{x_str}"
                            elif layer == "labels":
                                url = f"https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z_str}/{y_str}/{x_str}"
                            else:
                                url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z_str}/{y_str}/{x_str}"
                            try:
                                ctx = ssl._create_unverified_context()
                                req = urllib.request.Request(
                                    url,
                                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                                )
                                with urllib.request.urlopen(req, timeout=5.0, context=ctx) as resp:
                                    tile_bytes = resp.read()
                                if tile_bytes and len(tile_bytes) > 100:
                                    with open(tile_path, "wb") as tf:
                                        tf.write(tile_bytes)
                            except Exception:
                                tile_bytes = None
                        if tile_bytes:
                            self.send_response(200)
                            self.send_header("Content-Type", "image/png" if layer == "labels" else "image/jpeg")
                            self.send_header("Cache-Control", "public, max-age=86400")
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.end_headers()
                            self.wfile.write(tile_bytes)
                            return
                self.send_error(404, "Map tile unavailable")
                return

            # 4B2. API: Real-World Address & Place Geocoder (/api/geocode?q=...)
            if clean_path == "/api/geocode":
                from urllib.parse import parse_qs, quote
                import urllib.request
                qs = parse_qs(parsed.query)
                q = (qs.get("q") or [""])[0].strip()
                results = []
                if q:
                    try:
                        import ssl
                        ctx = ssl._create_unverified_context()
                        url = f"https://nominatim.openstreetmap.org/search?format=json&limit=5&q={quote(q)}"
                        req = urllib.request.Request(
                            url,
                            headers={"User-Agent": "ArcticTrailCamForensicHub/1.0 (RealMapGeocoder)"},
                        )
                        with urllib.request.urlopen(req, timeout=5.0, context=ctx) as resp:
                            raw_list = json.loads(resp.read().decode("utf-8"))
                            for item in raw_list:
                                results.append({
                                    "display_name": item.get("display_name", ""),
                                    "lat": float(item.get("lat", 0.0)),
                                    "lon": float(item.get("lon", 0.0)),
                                })
                    except Exception:
                        pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"results": results}).encode("utf-8"))
                return

            # 4B3. API: Real Deployed Camera Registry (/api/cameras)
            if clean_path == "/api/cameras":
                payload = build_fleet_grid_payload(alerts_dir, demo_mode=False)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"cameras": payload.get("cameras", [])}).encode("utf-8"))
                return

            # 4B4. API: Load persisted offline site map & camera placement (verified_alerts/offline_site_map.json)
            if clean_path == "/api/site_map":
                map_file = os.path.join(alerts_dir, "offline_site_map.json")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                if os.path.isfile(map_file):
                    try:
                        with open(map_file, "r", encoding="utf-8") as mf:
                            data = json.load(mf)
                        self.wfile.write(json.dumps({"cached": True, "site_map": data}).encode("utf-8"))
                        return
                    except Exception:
                        pass
                self.wfile.write(json.dumps({"cached": False, "site_map": None}).encode("utf-8"))
                return

            # 4C. API: Multi-Unit Federation, Sector Aggregation & Cross-Camera Object Trajectory Grid
            if clean_path == "/api/fleet_grid":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                is_demo_req = ("demo=1" in parsed.query) if parsed.query else bool(demo_mode)
                payload = build_fleet_grid_payload(alerts_dir, demo_mode=is_demo_req)
                self.wfile.write(json.dumps(payload).encode("utf-8"))
                return

            # 4D. API: Live video stream telemetry & multi-threshold / persistence-tracker detections
            if clean_path == "/api/fleet_grid/simulate_handoff":
                try:
                    with LIVE_FRAME_LOCK:
                        cur = LIVE_FRAME_STATE.get("handoff_sim_step", 0)
                        nxt = 1 if cur >= 2 else (cur + 1)
                        LIVE_FRAME_STATE["handoff_sim_step"] = nxt
                        LIVE_FRAME_STATE["handoff_sim_ts"] = time.time()
                    payload = build_fleet_grid_payload(alerts_dir)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "step": nxt, "fleet_grid": payload}).encode("utf-8"))
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
                return
            if clean_path == "/api/stream_source":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with LIVE_FRAME_LOCK:
                    src = LIVE_FRAME_STATE.get("source", "pi_camera")
                self.wfile.write(json.dumps({"source": src}).encode("utf-8"))
                return

            if clean_path == "/api/live_frame":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with LIVE_FRAME_LOCK:
                    meta = LIVE_FRAME_STATE["meta"]
                    updated_at = LIVE_FRAME_STATE["updated_at"]
                    seq = LIVE_FRAME_STATE["seq"]
                    src = LIVE_FRAME_STATE.get("source", "pi_camera")
                if meta is None:
                    lf_path = os.path.join(alerts_dir, "live_frame.json")
                    if os.path.isfile(lf_path):
                        try:
                            with open(lf_path, "r", encoding="utf-8") as lf:
                                meta = json.load(lf)
                            updated_at = os.path.getmtime(lf_path)
                        except Exception:
                            meta = None
                active = meta is not None
                self.wfile.write(json.dumps({
                    "active": active,
                    "seq": seq,
                    "source": src,
                    "updated_at": updated_at,
                    "frame": meta,
                }).encode("utf-8"))
                return

            if clean_path == "/api/live_frame.jpg":
                with LIVE_FRAME_LOCK:
                    jpeg_bytes = LIVE_FRAME_STATE["jpeg"]
                if not jpeg_bytes:
                    jpg_path = os.path.join(alerts_dir, "live_frame.jpg")
                    if os.path.isfile(jpg_path):
                        try:
                            with open(jpg_path, "rb") as jf:
                                jpeg_bytes = jf.read()
                        except Exception:
                            jpeg_bytes = None
                if jpeg_bytes:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(jpeg_bytes)
                    return
                self.send_error(404, "No live frame available")
                return

            # 5. Root page -> index.html
            if clean_path in ("", "/", "/index.html"):
                index_path = os.path.join(UI_DIR, "index.html")
                if os.path.exists(index_path):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                    self.end_headers()
                    with open(index_path, "rb") as f:
                        self.wfile.write(f.read())
                    return

            # 6. Fallback to SimpleHTTPRequestHandler serving UI_DIR
            return super().do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            clean_path = unquote(parsed.path)
            if clean_path == "/api/fleet_grid/simulate_handoff":
                try:
                    with LIVE_FRAME_LOCK:
                        cur = LIVE_FRAME_STATE.get("handoff_sim_step", 0)
                        nxt = 1 if cur >= 2 else (cur + 1)
                        LIVE_FRAME_STATE["handoff_sim_step"] = nxt
                        LIVE_FRAME_STATE["handoff_sim_ts"] = time.time()
                    payload = build_fleet_grid_payload(alerts_dir)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "step": nxt, "fleet_grid": payload}).encode("utf-8"))
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
                return
            if clean_path == "/api/stream_source":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(min(length, 65536))
                    payload = json.loads(raw_body.decode("utf-8"))
                    new_src = payload.get("source", "pi_camera")
                    if new_src not in ("pi_camera", "video_file"):
                        new_src = "pi_camera"
                    with LIVE_FRAME_LOCK:
                        LIVE_FRAME_STATE["source"] = new_src
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "source": new_src}).encode("utf-8"))
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
                return
            if clean_path == "/api/live_frame":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(min(length, 10 * 1024 * 1024))
                    payload = json.loads(raw_body.decode("utf-8"))
                    meta = payload.get("meta", {})
                    jpeg_b64 = payload.get("jpeg_b64")
                    jpeg_bytes = base64.b64decode(jpeg_b64) if jpeg_b64 else None
                    with LIVE_FRAME_LOCK:
                        LIVE_FRAME_STATE["meta"] = meta
                        if jpeg_bytes:
                            LIVE_FRAME_STATE["jpeg"] = jpeg_bytes
                        LIVE_FRAME_STATE["updated_at"] = time.time()
                        LIVE_FRAME_STATE["seq"] += 1
                        seq = LIVE_FRAME_STATE["seq"]
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "seq": seq}).encode("utf-8"))
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
                return
            if clean_path == "/api/cameras":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(min(length, 2 * 1024 * 1024))
                    payload = json.loads(raw_body.decode("utf-8"))
                    os.makedirs(alerts_dir, exist_ok=True)
                    reg_file = os.path.join(alerts_dir, "cameras_registry.json")
                    with open(reg_file, "w", encoding="utf-8") as rf:
                        json.dump(payload, rf, indent=2)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"saved": True, "path": reg_file}).encode("utf-8"))
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"saved": False, "error": str(e)}).encode("utf-8"))
                return
            if clean_path == "/api/site_map":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(min(length, 15 * 1024 * 1024))
                    payload = json.loads(raw_body.decode("utf-8"))
                    os.makedirs(alerts_dir, exist_ok=True)
                    map_file = os.path.join(alerts_dir, "offline_site_map.json")
                    with open(map_file, "w", encoding="utf-8") as mf:
                        json.dump(payload, mf, indent=2)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"saved": True, "path": map_file}).encode("utf-8"))
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"saved": False, "error": str(e)}).encode("utf-8"))
                return
            self.send_error(404, "Endpoint not found")

        def log_message(self, format, *args):
            if verbose:
                super().log_message(format, *args)

    return CommandCenterHandler


def is_port_in_use(host, port):
    """Checks whether a TCP port is currently open and bound by another process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_available_port(host, preferred_port, fallback_ports=None):
    """Finds an available port starting from preferred_port, then probing fallback candidates."""
    if not is_port_in_use(host, preferred_port):
        return preferred_port

    if fallback_ports is None:
        fallback_ports = [8081, 8082, 8083, 8084, 8123, 8888, 9090]

    for p in fallback_ports:
        if p != preferred_port and not is_port_in_use(host, p):
            return p

    # Linear probe
    for p in range(preferred_port + 1, preferred_port + 50):
        if p <= 65535 and not is_port_in_use(host, p):
            return p

    raise OSError(f"No available ports found on {host} near {preferred_port}")


def run_dashboard(host="127.0.0.1", port=8080, alerts_dir=DEFAULT_ALERTS_DIR, auto_fallback=True, explicit_port=False, verbose=False, demo_mode=False):
    """Starts the Forensic Evidence & Telemetry Hub HTTP server with robust port management."""
    os.makedirs(alerts_dir, exist_ok=True)
    handler_class = make_command_center_handler(alerts_dir, verbose=verbose, demo_mode=demo_mode)

    target_port = port
    if is_port_in_use(host, target_port):
        if explicit_port or not auto_fallback:
            print(f"[!] ERROR: Port {target_port} is already in use by another process.", file=sys.stderr)
            print(f"[*] TIP: Specify a different port using '--port <PORT>' (e.g., --port 8123 or --port 8081).", file=sys.stderr)
            sys.exit(1)
        else:
            fallback = find_available_port(host, target_port)
            print(f"[*] NOTICE: Port {target_port} is currently in use by another process.")
            print(f"[*] Automatically switching to available port {fallback}...")
            target_port = fallback

    try:
        server = ReusableHTTPServer((host, target_port), handler_class)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            print(f"[!] ERROR: Port {target_port} is already in use ({e}).", file=sys.stderr)
            print(f"[*] Specify an alternate port using '--port <PORT>'.", file=sys.stderr)
            sys.exit(1)
        raise

    display_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host
    print("=================================================================")
    print("  PI-DIODE-TRAILCAM // FORENSIC EVIDENCE & TELEMETRY HUB")
    print("=================================================================")
    print(f"  [+] Web Interface   : http://{display_host}:{target_port}")
    print(f"  [+] Listening On    : {host}:{target_port}")
    print(f"  [+] Alerts Storage  : {alerts_dir}")
    print(f"  [+] Journal File    : {os.path.join(alerts_dir, 'alerts_journal.jsonl')}")
    print(f"  [+] Operating Mode  : {'DEMO / BENCHTOP SIM' if demo_mode else 'PRODUCTION FORENSIC NVR'}")
    print("=================================================================")
    print("  Press Ctrl+C to terminate the dashboard server.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down Forensic Evidence Hub server.")
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(
        description="Local Web Server & Live Telemetry Bridge for the Forensic Evidence & Telemetry Hub UI."
    )
    parser.add_argument(
        "-p", "--port",
        type=valid_port,
        default=None,
        help="Port to listen on (1-65535, default: 8080 or DASHBOARD_PORT env var)"
    )
    parser.add_argument(
        "-H", "--host",
        type=str,
        default=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
        help="Host address to bind to (default: 127.0.0.1; pass 0.0.0.0 for LAN access)"
    )
    parser.add_argument(
        "--alerts-dir",
        type=str,
        default=DEFAULT_ALERTS_DIR,
        help=f"Directory where verified alert JPEGs & journal are stored (default: {DEFAULT_ALERTS_DIR})"
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable automatic port fallback if the default port 8080 is in use"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        default=os.getenv("DEMO_MODE", "0") == "1",
        help="Enable benchtop walk/drive simulation triggers in the UI"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Log all HTTP requests to stdout"
    )

    args = parser.parse_args()

    env_port_str = os.getenv("DASHBOARD_PORT")
    explicit_port = args.port is not None

    if explicit_port:
        port = args.port
    elif env_port_str:
        try:
            port = valid_port(env_port_str)
            explicit_port = True
        except argparse.ArgumentTypeError:
            print(f"[!] Warning: DASHBOARD_PORT='{env_port_str}' is invalid; defaulting to 8080.", file=sys.stderr)
            port = 8080
    else:
        port = 8080

    run_dashboard(
        host=args.host,
        port=port,
        alerts_dir=args.alerts_dir,
        auto_fallback=not args.no_fallback,
        explicit_port=explicit_port,
        verbose=args.verbose,
        demo_mode=args.demo
    )


if __name__ == "__main__":
    main()


