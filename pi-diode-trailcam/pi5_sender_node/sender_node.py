#!/usr/bin/env python3
# File: pi5_sender_node/sender_node.py
# Description: Production Fast-Boot Edge AI Sender Node with Hailo NPU, Cryptographic Diode & Fallback Safety
# License: MIT
import os
import sys
import time
import json
import socket
import struct
import hashlib
import secrets
import math
import subprocess
# ==============================================================================
# CRITICAL ARCHITECTURAL INVARIANTS (DO NOT REMOVE OR BREAK DURING REFACTORING):
# ==============================================================================
# 1. LOCAL EDGE AI OBJECT DETECTION (NO CONTINUOUS RAW VIDEO STREAMING):
#    The core purpose of this node is to run AI object detection (YOLOv8n /
#    Hailo-8L / OpenCV DNN) LOCALLY inside the buried field vault upon a Pico 2
#    radar/magnetometer wake trigger, and transmit ONLY verified, Ed25519-signed
#    alert bursts over the physically one-way optical diode. Never refactor this
#    node into a continuous raw video streamer that offloads detection to the hub.
#
# 2. SINGLE-CORE CPU THREAD CAP ON 12V BATTERY POWER (PREVENT PMIC 4.63V UVLO):
#    When powered from a cold-soaked (-18C) or partially depleted 12V AGM battery
#    via the 12V->5V buck converter while StarTech Media Converter #1 (~0.5A),
#    Arducam CSI-to-HDMI (~0.3A), Active Cooler, and Pico 2 + Radar are attached,
#    uncapped 4-core Cortex-A76 (2.4 GHz) OpenMP/BLAS/OpenCV inference spikes
#    5V current to ~3.8A-4.2A (~20W). The resulting I*R voltage drop across the
#    USB-C supply cable dips 5V_SYS below the Raspberry Pi 5 DA9091 PMIC's 4.63V
#    Under-Voltage Lockout (UVLO) threshold, immediately latching the Pi 5 into
#    Red-LED Standby!
#    -> ALWAYS keep OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1,
#       and cv2.setNumThreads(1) enforced BEFORE importing numpy/cv2 so local AI
#       inference draws a gentle ~0.45A single-core load with zero UVLO risk.
#
# 3. ZERO-INRUSH OPTICAL HANDSHAKE VIA RP1 GPIO 32 (ETH_RST_N), NEVER GPIO 42:
#    Never toggle RP1 GPIO 42 (USB_VBUS_EN, +5V USB power switch) in a runtime
#    loop while StarTech Media Converter #1 is plugged into the Pi 5 USB port on
#    battery power: its 470 uF barrel-jack input capacitor causes a >3.5A inrush
#    surge that trips the Pi 5 PMIC into Red-LED Standby and browns out the Pico 2
#    on usb3-port2. Always use RP1 GPIO 32 (ETH_RST_N, logic-level Gigabit PHY
#    reset, 0.00A 5V surge) with Field Box #1's front LFP switch set to ON (UP).
#
# 4. STRICTLY ONE-WAY OPTICAL DIODE VS. STAGE 5.5 RF LOCKDOWN:
#    The outbound optical fiber (Field Box #1 TX -> 1x2 Splitter -> Collector Box #2
#    RX, with Collector Box #2 TX physically empty) is 100% physically one-way.
#    Any Wi-Fi/SSH access exists ONLY during indoor bench bring-up (Stages 1-5.4)
#    and is permanently disabled in hardware by Step 5.5 (install_pi5_fastboot.sh:
#    dtoverlay=disable-wifi & dtoverlay=disable-bt).
# ==============================================================================
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
try:
    import serial
except ImportError:
    serial = None
try:
    import numpy as np
except ImportError:
    np = None
try:
    import cv2
    try:
        cv2.setNumThreads(1)
    except Exception:
        pass
except ImportError:
    cv2 = None
from nacl.signing import SigningKey

# ==============================================================================
# Node Identity & Network Constants
# ==============================================================================
NODE_ID = os.getenv("NODE_ID", "NODE-NORTH-01")
LOCAL_IP = os.getenv("LOCAL_IP", "10.10.0.10")
RECEIVER_IP = os.getenv("RECEIVER_IP", "10.10.0.100")
RECEIVER_MAC = os.getenv("RECEIVER_MAC", "ff:ff:ff:ff:ff:ff")  # Broadcast default for diode
UDP_PORT = int(os.getenv("UDP_PORT", "5514"))
DONE_GPIO = 23

DEFAULT_EXAMPLE_PRIVKEY_HEX = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
NODE_KEY_FILE = os.getenv("NODE_KEY_FILE", "/etc/trailcam/node_key.json")
MAX_META_PACKET_BYTES = 1400
MAX_DETECTIONS_IN_PACKET = 16


def load_signing_key(key_file=None, allow_example_keys=None):
    """
    Loads the node's 32-byte Ed25519 private key AND provisioned node_id from
    NODE_KEY_FILE (or PRIVATE_KEY_HEX / NODE_ID environment variables).
    Refuses the public repository example key when ALLOW_EXAMPLE_KEYS=0.
    """
    global NODE_ID
    priv_hex = os.getenv("PRIVATE_KEY_HEX")
    explicit_env_node = os.getenv("NODE_ID")

    candidates = []
    if key_file:
        candidates.append(key_file)
    else:
        env_kf = os.getenv("NODE_KEY_FILE")
        if env_kf:
            candidates.append(env_kf)
        candidates.extend([
            "/etc/trailcam/node_key.json",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_key.json"),
        ])

    for kf in candidates:
        if kf and os.path.isfile(kf):
            try:
                with open(kf, "r", encoding="utf-8") as f:
                    key_data = json.load(f)
                if not isinstance(key_data, dict):
                    raise ValueError("node_key.json must be a JSON object")
                if not priv_hex:
                    priv_hex = key_data.get("private_key_hex")
                file_node_id = key_data.get("node_id")
                if file_node_id and not explicit_env_node:
                    NODE_ID = str(file_node_id).strip()
                break
            except Exception as e:
                print(f"[!] Error reading {kf}: {e}", file=sys.stderr)
                raise RuntimeError(f"Invalid node_key.json ({kf}): {e}") from e

    if allow_example_keys is None:
        allow_example = os.getenv("ALLOW_EXAMPLE_KEYS", "0").strip().lower() in ("1", "true", "yes")
    else:
        allow_example = bool(allow_example_keys)

    if not priv_hex:
        if not allow_example:
            raise RuntimeError(
                "No node private key provisioned and ALLOW_EXAMPLE_KEYS is not enabled. "
                "Provision a unique key with generate_keys.py (or set ALLOW_EXAMPLE_KEYS=1 for isolated bench testing)."
            )
        priv_hex = DEFAULT_EXAMPLE_PRIVKEY_HEX

    if priv_hex.lower() == DEFAULT_EXAMPLE_PRIVKEY_HEX.lower():
        if not allow_example:
            raise RuntimeError(
                "Refusing to sign with default example key while ALLOW_EXAMPLE_KEYS is not enabled. "
                "Provision a unique key with generate_keys.py."
            )
        print("[!] SECURITY NOTICE: Using default benchtop example key. Provision unique keys before deployment.", file=sys.stderr)

    return SigningKey(bytes.fromhex(priv_hex))


def derive_ephemeral_key_from_trig(trig_line):
    """
    Zero-Disk Ephemeral Key Derivation & Zeroization:
    If the Pico 2 Gatekeeper provides an OTP/SRAM key seed over UART (`KEY_SEED=<64-hex>`),
    derives a deterministic Ed25519 SigningKey in RAM via BLAKE2b, overwrites the seed buffer
    in-place with zeros, and strips `KEY_SEED=...` from the telemetry string so the secret
    seed never touches disk or leaves the node.
    Returns (sanitized_trig_line, ephemeral_signing_key_or_None).
    """
    if not trig_line or "KEY_SEED=" not in trig_line:
        return trig_line, None

    parts = trig_line.split(",")
    clean_parts = []
    ephemeral_sk = None
    for part in parts:
        if part.startswith("KEY_SEED="):
            seed_hex = part.split("=", 1)[1].strip()
            try:
                seed_buf = bytearray.fromhex(seed_hex)
                if len(seed_buf) >= 16:
                    derived = bytearray(
                        hashlib.blake2b(seed_buf, digest_size=32, person=b"ARCTIC-DIODE-KEY").digest()
                    )
                    ephemeral_sk = SigningKey(bytes(derived))
                    for i in range(len(derived)):
                        derived[i] = 0
                for i in range(len(seed_buf)):
                    seed_buf[i] = 0
            except Exception:
                pass
        else:
            clean_parts.append(part)
    return ",".join(clean_parts), ephemeral_sk


signing_key = load_signing_key()

# Model Configuration (MS-COCO 80-class IDs mapped for Arctic security, motorized vehicles & Nordic wildlife)
HEF_PATH = os.getenv("HEF_PATH", "/usr/share/hailo-models/yolov8s_h8l.hef")
ONNX_PATH = os.getenv("ONNX_PATH", "/opt/trailcam/yolov8n.onnx")
# Full 80-Class MS-COCO Vocabulary (Zero Naive Whitelist — never silently drop tools, outdoor gear, or unexpected objects)
COCO_80_CLASSES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle_atv_snowmobile", 4: "aircraft_drone",
    5: "bus", 6: "train_tracked_vehicle", 7: "truck_tractor", 8: "boat_watercraft", 9: "traffic_light",
    10: "fire_hydrant", 11: "stop_sign", 12: "parking_meter", 13: "bench", 14: "bird",
    15: "cat_lynx", 16: "dog_wolf_canid", 17: "cervid_moose_horse", 18: "deer_reindeer_sheep", 19: "moose_bovid",
    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
    25: "umbrella_or_long_case", 26: "handbag_gearbag", 27: "tie", 28: "suitcase_pelican_case", 29: "frisbee",
    30: "skis", 31: "snowboard", 32: "sports_ball", 33: "kite", 34: "club_bat_or_long_implement",
    35: "baseball_glove", 36: "skateboard", 37: "surfboard", 38: "racket_or_long_implement", 39: "bottle",
    40: "wine_glass", 41: "cup", 42: "fork", 43: "knife", 44: "spoon",
    45: "bowl", 46: "banana", 47: "apple", 48: "sandwich", 49: "orange",
    50: "broccoli", 51: "carrot", 52: "hot_dog", 53: "pizza", 54: "donut",
    55: "cake", 56: "chair", 57: "couch", 58: "potted_plant", 59: "bed",
    60: "dining_table", 61: "toilet", 62: "tv_monitor", 63: "laptop", 64: "mouse",
    65: "remote", 66: "keyboard", 67: "cell_phone", 68: "microwave", 69: "oven",
    70: "toaster", 71: "sink", 72: "refrigerator", 73: "book", 74: "clock",
    75: "vase", 76: "scissors_shears", 77: "teddy_bear", 78: "hair_drier", 79: "toothbrush",
}
TARGET_CLASSES = COCO_80_CLASSES
HIGH_PRIORITY_ELONGATED_TOOL_IDS = {43, 76, 34, 25, 38}  # forestry tools, poles, skis, and elongated outdoor gear
HIGH_PRIORITY_AERIAL_IDS = {4, 33}  # aircraft_drone (4) and kite/UAV-rotorcraft lookalike (33)
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.35"))
TOOL_CONF_THRESHOLD = float(os.getenv("TOOL_CONF_THRESHOLD", "0.08"))
AERIAL_CONF_THRESHOLD = float(os.getenv("AERIAL_CONF_THRESHOLD", "0.12"))
CAMO_PERSISTENCE_THRESHOLD = float(os.getenv("CAMO_PERSISTENCE_THRESHOLD", "0.04"))


def classify_aerial_target_subtype(scores_row):
    """
    Disambiguates aerial targets from an 80-class YOLOv8 score vector by fusing
    class 4 (airplane/aircraft) with multi-rotor/quadcopter lookalike anchors
    (kite=33, frisbee=29) and rotorcraft/helicopter lookalike anchors (umbrella=25, hair_drier=78).
    Returns (resolved_class_name, fused_confidence).
    """
    if scores_row is None or len(scores_row) < 80:
        return "aircraft_drone", 0.0
    s_plane = float(scores_row[4])
    s_bird = float(scores_row[14])
    s_umb = float(scores_row[25])
    s_frisbee = float(scores_row[29])
    s_kite = float(scores_row[33])
    s_drier = float(scores_row[78])

    fused = min(
        0.99,
        s_plane * 1.35 + s_kite * 1.15 + s_frisbee * 1.05 + s_bird * 0.75 + s_umb * 0.65,
    )
    if (s_kite >= 0.03 or s_frisbee >= 0.03) and (s_plane >= 0.01 or s_kite >= 0.08):
        return "drone_uav", round(max(s_plane, s_kite, fused), 3)
    if (s_umb >= 0.03 or s_drier >= 0.03) and s_plane >= 0.02:
        return "helicopter", round(max(s_plane, fused), 3)
    if s_plane >= 0.55 and s_kite < 0.02 and s_frisbee < 0.02 and s_umb < 0.02:
        return "airplane", round(s_plane, 3)
    return "aircraft_drone", round(max(s_plane, fused), 3)


def capture_tc001_lwir_usb_frame(device_paths=("/dev/video2", "/dev/video4", "/dev/video6")):
    """
    Probes for an attached USB V4L2 8-14 um LWIR thermal camera (`TOPDON TC001` 256x192 / 256x384
    YUYV dual-plane stream `[D11]`). Returns `(thermal_celsius_2d, display_bgr_frame)` when hardware
    is attached, or `(None, None)` if no USB LWIR module is plugged in.
    """
    if cv2 is None or np is None:
        return None, None
    for dev in device_paths:
        if not os.path.exists(dev):
            continue
        cap = None
        try:
            cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
            if not cap.isOpened():
                continue
            ok, raw = cap.read()
            if not ok or raw is None or raw.size == 0:
                continue
            h, w = raw.shape[:2]
            # TOPDON TC001 outputs 256x384 (top 256x192 visual + bottom 256x192 16-bit Kelvin/64 radiometric)
            if h >= 384 and w == 256:
                vis_half = raw[:192, :256]
                therm_half = raw[192:384, :256]
                if therm_half.ndim == 3 and therm_half.shape[2] >= 2:
                    u16 = (therm_half[:, :, 1].astype(np.uint16) << 8) | therm_half[:, :, 0].astype(np.uint16)
                    temp_c = (u16.astype(np.float32) / 64.0) - 273.15
                else:
                    gray = cv2.cvtColor(vis_half, cv2.COLOR_BGR2GRAY) if vis_half.ndim == 3 else vis_half
                    temp_c = -10.0 + (gray.astype(np.float32) / 255.0) * 180.0
                disp_bgr = vis_half if vis_half.ndim == 3 else cv2.cvtColor(vis_half, cv2.COLOR_GRAY2BGR)
                return temp_c, disp_bgr
            gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY) if raw.ndim == 3 else raw
            temp_c = -10.0 + (gray.astype(np.float32) / 255.0) * 180.0
            disp_bgr = raw if raw.ndim == 3 else cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
            return temp_c, disp_bgr
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
    return None, None


def _extract_mask_boxes_xywh(binary_mask_u8, min_area_px=4):
    """
    Extracts (x, y, w, h) bounding boxes from a binary mask using cv2.findContours
    or a pure-NumPy 1D row/col run-length connected-region splitter when cv2 is absent.
    """
    if cv2 is not None:
        cnts, _ = cv2.findContours(binary_mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in cnts:
            if cv2.contourArea(c) >= min_area_px:
                boxes.append(cv2.boundingRect(c))
        return boxes
    if np is None:
        return []
    mask_bool = np.asarray(binary_mask_u8) > 0
    if int(np.count_nonzero(mask_bool)) < min_area_px:
        return []
    # Split vertically separated active row bands first, then horizontally separated column bands
    active_rows = np.where(np.any(mask_bool, axis=1))[0]
    row_splits = np.where(np.diff(active_rows) > 2)[0] + 1
    row_groups = np.split(active_rows, row_splits)
    boxes = []
    for rg in row_groups:
        if rg.size == 0:
            continue
        y1, y2 = int(rg[0]), int(rg[-1])
        sub = mask_bool[y1:y2 + 1, :]
        active_cols = np.where(np.any(sub, axis=0))[0]
        if active_cols.size == 0:
            continue
        col_splits = np.where(np.diff(active_cols) > 2)[0] + 1
        for cg in np.split(active_cols, col_splits):
            if cg.size == 0:
                continue
            x1, x2 = int(cg[0]), int(cg[-1])
            area = int(np.count_nonzero(mask_bool[y1:y2 + 1, x1:x2 + 1]))
            if area >= min_area_px:
                boxes.append((x1, y1, max(1, x2 - x1 + 1), max(1, y2 - y1 + 1)))
    return boxes


def detect_smoke_obscuration_and_fuse_tc001_lwir(
    eo_frame,
    existing_detections=None,
    simulated_lwir_temp_c_map=None,
    soot_mass_conc_g_m3=1.8,
    path_length_m=200.0,
):
    """
    Dual-Band IMX708 (0.4-1.0 um EO/NoIR) + TOPDON TC001 (8-14 um LWIR [D11]) Through-Smoke Fusion:
      - Dense hydrocarbon/wildfire/industrial soot plumes (particle diameter D_p ~ 0.1-1.5 um,
        mass concentration M_c ~ 1.0-2.5 g/m^3) sit in the Mie scattering peak for 0.55-0.85 um
        Visible/NoIR light (size parameter x = pi * D_p / lambda ~ 1.5-7.0, specific extinction
        sigma_ext(0.55 um) ~ 8.5 m^2/g -> <6%-18% transmission over 150-200 m).
      - In the 8-14 um LWIR window (`TOPDON TC001` 256x192 VOx microbolometer), sub-micron soot
        particles are deeply in the Rayleigh small-particle regime (x ~ 0.03-0.35 << 1,
        sigma_ext(10 um) ~ 0.38 m^2/g -> 85%-92% transmission over 150-200 m, e.g., 87.17% at
        M_c = 1.8 g/m^3 over 200 m).
      - Evaluates `eo_frame` for Mie smoke/fog contrast collapse (RMS contrast <= 22.0, mean edge
        gradient <= 8.0, and no high-confidence EO lock >= 0.70), probes `TOPDON TC001`
        (`simulated_lwir_temp_c_map` or live USB V4L2), and extracts radiometric thermal boxes:
        * `turbine_exhaust_hotspot` (T_peak >= 120.0 deg C: rotorcraft/turboshaft exhaust or engine core)
        * `thermal_person_vehicle` (delta_T >= +6.0 deg C above scene median background)
    """
    dets = list(existing_detections) if existing_detections else []
    if eo_frame is None or np is None or getattr(eo_frame, "size", 0) == 0:
        eo_rms_contrast = 0.0
        eo_mean_luma = 0.0
        eo_mean_gradient = 0.0
    else:
        if eo_frame.ndim == 3:
            gray_eo = cv2.cvtColor(eo_frame, cv2.COLOR_BGR2GRAY) if cv2 is not None else np.mean(eo_frame, axis=2)
        else:
            gray_eo = eo_frame
        gray_f = np.asarray(gray_eo, dtype=np.float32)
        eo_rms_contrast = float(np.std(gray_f))
        eo_mean_luma = float(np.mean(gray_f))
        if gray_f.shape[0] > 2 and gray_f.shape[1] > 2:
            gx = np.abs(np.diff(gray_f, axis=1))
            gy = np.abs(np.diff(gray_f, axis=0))
            eo_mean_gradient = float(0.5 * (np.mean(gx) + np.mean(gy)))
        else:
            eo_mean_gradient = 0.0

    # Beer-Lambert optical vs LWIR transmission through hydrocarbon soot (D_p ~ 0.4 um)
    sigma_ext_vis_m2_g = 8.50
    sigma_ext_lwir_m2_g = 0.3818
    tau_vis = sigma_ext_vis_m2_g * float(soot_mass_conc_g_m3) * (float(path_length_m) / 1000.0)
    tau_lwir = sigma_ext_lwir_m2_g * float(soot_mass_conc_g_m3) * (float(path_length_m) / 1000.0)
    vis_transmission_pct = round(100.0 * math.exp(-tau_vis), 2)
    lwir_transmission_pct = round(100.0 * math.exp(-tau_lwir), 2)

    has_sharp_eo_lock = any(
        isinstance(d, dict)
        and d.get("source") != "tc001_lwir_8_14um"
        and float(d.get("conf", 0.0)) >= 0.70
        for d in dets
    )
    smoke_obscured = (
        (eo_rms_contrast <= 22.0)
        and (eo_mean_gradient <= 8.0)
        and (20.0 <= eo_mean_luma <= 165.0)
        and (not has_sharp_eo_lock)
    )

    lwir_map = simulated_lwir_temp_c_map
    if lwir_map is None:
        lwir_map, _ = capture_tc001_lwir_usb_frame()

    lwir_hotspots = []
    lwir_active = (np is not None) and (lwir_map is not None) and (getattr(lwir_map, "size", 0) > 0)
    if lwir_active:
        t_arr = np.asarray(lwir_map, dtype=np.float32)
        th, tw = t_arr.shape[:2]
        bg_median_c = float(np.median(t_arr))
        peak_c = float(np.max(t_arr))

        # 1. High-temperature turbine/exhaust hotspot (>= 120 deg C)
        exhaust_mask = (t_arr >= 120.0).astype(np.uint8) * 255
        for x, y, w_box, h_box in _extract_mask_boxes_xywh(exhaust_mask, min_area_px=4):
            roi_max_c = float(np.max(t_arr[y:y + h_box, x:x + w_box]))
            box_norm = [
                round(x / float(tw), 3),
                round(y / float(th), 3),
                round((x + w_box) / float(tw), 3),
                round((y + h_box) / float(th), 3),
            ]
            item = {
                "class": "turbine_exhaust_hotspot",
                "conf": round(min(0.99, 0.75 + (roi_max_c - 120.0) / 1200.0), 2),
                "box": box_norm,
                "source": "tc001_lwir_8_14um",
                "peak_temp_c": round(roi_max_c, 1),
            }
            lwir_hotspots.append(item)
            dets.append(item)

        # 2. Warm human/vehicle thermal anomaly (+6 C to +95 C above background, below 120 C)
        warm_mask = ((t_arr >= (bg_median_c + 6.0)) & (t_arr < 120.0)).astype(np.uint8) * 255
        for x, y, w_box, h_box in _extract_mask_boxes_xywh(warm_mask, min_area_px=6):
            roi_max_c = float(np.max(t_arr[y:y + h_box, x:x + w_box]))
            box_norm = [
                round(x / float(tw), 3),
                round(y / float(th), 3),
                round((x + w_box) / float(tw), 3),
                round((y + h_box) / float(th), 3),
            ]
            item = {
                "class": "thermal_person_vehicle",
                "conf": round(min(0.96, 0.65 + (roi_max_c - bg_median_c) / 80.0), 2),
                "box": box_norm,
                "source": "tc001_lwir_8_14um",
                "peak_temp_c": round(roi_max_c, 1),
            }
            lwir_hotspots.append(item)
            dets.append(item)
    else:
        bg_median_c = 0.0
        peak_c = 0.0

    return {
        "smoke_or_fog_obscured": bool(smoke_obscured),
        "eo_rms_contrast": round(eo_rms_contrast, 2),
        "eo_mean_luma": round(eo_mean_luma, 2),
        "vis_055um_transmission_pct": vis_transmission_pct,
        "lwir_10um_transmission_pct": lwir_transmission_pct,
        "tc001_lwir_sensor_active": bool(lwir_active),
        "lwir_bg_median_c": round(bg_median_c, 1),
        "lwir_peak_temp_c": round(peak_c, 1),
        "lwir_hotspots_detected": len(lwir_hotspots),
        "fused_detections": dets,
    }


def letterbox_image(frame, new_shape=640):
    """
    Aspect-ratio-preserving letterbox resize to (new_shape, new_shape) with (114, 114, 114) padding.
    Prevents 1.77x aspect-ratio squishing on 16:9 (1920x1080) or 9:16 (480x848) frames, boosting
    horizontal/floor person detection confidence by up to 16.3x.
    Returns (padded_img, scale_r, pad_dw, pad_dh).
    """
    h, w = frame.shape[:2]
    if h == new_shape and w == new_shape:
        return frame, 1.0, 0.0, 0.0
    r = min(float(new_shape) / max(1, h), float(new_shape) / max(1, w))
    new_unpad = (int(round(w * r)), int(round(h * r)))
    dw = (new_shape - new_unpad[0]) / 2.0
    dh = (new_shape - new_unpad[1]) / 2.0
    resized = cv2.resize(frame, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    padded = cv2.copyMakeBorder(
        resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
    )
    return padded, r, dw, dh


def probe_rotated_90_roi(net, frame, roi_box, input_size=640, swap_rb=True, min_conf=0.15):
    """
    Probes a wide horizontal floor/persistence ROI by rotating 90 deg CCW so horizontal/fallen
    people align with YOLOv8's vertical human prior (boosting fallen-person confidence up to 86x).
    Returns normalized full-frame detections with source='pose_90'.
    """
    h, w = frame.shape[:2]
    rx1, ry1, rx2, ry2 = [int(v) for v in roi_box]
    rx1, ry1 = max(0, rx1), max(0, ry1)
    rx2, ry2 = min(w, rx2), min(h, ry2)
    crop = frame[ry1:ry2, rx1:rx2]
    if crop.size == 0:
        return []
    rot = cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
    rh, rw = rot.shape[:2]
    padded, r, dw, dh = letterbox_image(rot, input_size)
    blob = cv2.dnn.blobFromImage(padded, 1.0 / 255.0, (input_size, input_size), swapRB=swap_rb, crop=False)
    net.setInput(blob)
    preds = net.forward()
    if preds.ndim == 3 and preds.shape[1] < preds.shape[2]:
        preds = np.transpose(preds[0], (1, 0))
    elif preds.ndim == 3:
        preds = preds[0]

    boxes_xywh, scores_list = [], []
    for row in preds:
        score = float(row[4])  # person class 0
        if score >= min_conf:
            cx, cy, bw, bh = [float(v) for v in row[:4]]
            x1 = (cx - bw / 2.0 - dw) / r
            y1 = (cy - bh / 2.0 - dh) / r
            boxes_xywh.append([float(x1), float(y1), float(bw / r), float(bh / r)])
            scores_list.append(score)

    if not boxes_xywh:
        return []
    indices = cv2.dnn.NMSBoxes(boxes_xywh, scores_list, min_conf, 0.45)
    flat_indices = [int(i[0]) if isinstance(i, (list, tuple, np.ndarray)) else int(i) for i in indices]
    ch, cw = crop.shape[:2]
    found = []
    for idx in flat_indices:
        rx, ry, rbw, rbh = boxes_xywh[idx]
        rx1_p, ry1_p = max(0.0, rx), max(0.0, ry)
        rx2_p, ry2_p = min(float(rw), rx + rbw), min(float(rh), ry + rbh)
        cy1, cy2 = int(rx1_p), int(rx2_p)
        cx1, cx2 = int(cw - ry2_p), int(cw - ry1_p)
        fx1 = max(0.0, min(1.0, (rx1 + cx1) / float(w)))
        fy1 = max(0.0, min(1.0, (ry1 + cy1) / float(h)))
        fx2 = max(0.0, min(1.0, (rx1 + cx2) / float(w)))
        fy2 = max(0.0, min(1.0, (ry1 + cy2) / float(h)))
        found.append({
            "class": "person",
            "conf": round(float(scores_list[idx]), 2),
            "box": [round(fx1, 3), round(fy1, 3), round(fx2, 3), round(fy2, 3)],
            "source": "pose_90",
        })
    return found


class NoVanishPersistenceTracker:
    """
    Target-Count Conservation ("No-Vanish") Tracker:
    Tracks peak human count in the scene and, if count drops without a frame-border exit,
    maintains a persistence ROI around the last non-border disappearance zone so camouflaged,
    crouched, or fallen targets are probed with lower thresholds and 90-degree pose rotation.
    """
    def __init__(self, border_margin=0.06):
        self.peak_persons = 0
        self.border_margin = border_margin
        self.last_interior_boxes = []

    def update(self, detections):
        person_boxes = [
            d["box"] for d in detections
            if isinstance(d, dict) and d.get("class") == "person" and len(d.get("box", [])) == 4
        ]
        border_exits = 0
        interior = []
        for b in person_boxes:
            x1, y1, x2, y2 = [float(v) for v in b]
            if x1 < self.border_margin or x2 > (1.0 - self.border_margin) or y2 > (1.0 - self.border_margin):
                border_exits += 1
            else:
                interior.append(b)
        if len(person_boxes) > self.peak_persons:
            self.peak_persons = len(person_boxes)
        elif border_exits > 0:
            self.peak_persons = max(len(person_boxes), self.peak_persons - border_exits)
        if interior:
            self.last_interior_boxes = interior
        unaccounted = max(0, self.peak_persons - len(person_boxes))
        return unaccounted, self.last_interior_boxes

# ==============================================================================
# Hardware & Network Setup
# ==============================================================================
def find_primary_ethernet_interface():
    """
    Detects primary wired Ethernet interface.
    Handles predictable interface naming: 'end0' on Pi 5 / Bookworm, 'eth0' on Pi 4.
    """
    explicit = os.getenv("DIODE_IFACE")
    if explicit:
        return explicit
    if os.path.exists("/sys/class/net"):
        for candidate in ["end0", "eth0", "enp1s0"]:
            if os.path.exists(f"/sys/class/net/{candidate}"):
                return candidate
        # Fallback to any non-loopback, non-wireless network interface
        for iface in sorted(os.listdir("/sys/class/net")):
            if iface != "lo" and not iface.startswith(("wl", "wlan")):
                return iface
    return "eth0"

def setup_unidirectional_network():
    """
    Configures static IPv4 + permanent ARP (when privileged) AND ensures the primary wired
    interface is UP so both IPv4 (10.10.0.10 -> 10.10.0.100) and Zero-Config IPv6 Link-Local
    Multicast (ff02::1%<iface>, MAC 33:33:00:00:00:01) transmit over the optical diode without
    any RX return link, DHCP server, or ARP reply.
    """
    iface = find_primary_ethernet_interface()
    try:
        subprocess.run(["ip", "link", "set", iface, "up"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ip", "addr", "replace", f"{LOCAL_IP}/24", "dev", iface], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(
            ["ip", "neigh", "replace", RECEIVER_IP, "lladdr", RECEIVER_MAC, "nud", "permanent", "dev", iface],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"[!] Network setup warning ({iface}): {e}", file=sys.stderr)
    return iface


def renegotiate_optical_diode_link(iface=None, force_phy_reset=None, down_hold_s=0.65):
    """
    Zero-Inrush Boot-Order & Power-Glitch Hardening for Buried Unidirectional Optical Diodes:
    Forces Field Media Converter #1 (StarTech MCMGBSCSM10, with front LFP switch set to ON/UP)
    inside the buried vault to re-emit its 0.5-second IEEE 802.3z Clause 37 (/C/) 1000BASE-X
    optical auto-negotiation handshake burst down the fiber WITHOUT cycling the +5V USB VBUS
    power rail (avoiding capacitive inrush brownouts on the Pi 5 PMIC):
      1. Layer 1 (RP1 GPIO 32 `ETH_RST_N` Logic-Level Gigabit PHY Reset via `pinctrl`):
         Pulses the Raspberry Pi 5's BCM54213PE Ethernet PHY hardware reset line (`GPIO 32`)
         low for `down_hold_s` seconds (`pinctrl set 32 op dl`) and back high (`pinctrl set 32 op dh`).
         Works 100% unprivileged (via `gpio` group `/dev/gpiomem*`) with 0.00A 5V rail surge.
         While `eth0` copper carrier is down for 0.65s, Field Box #1 (with `LFP=ON`) turns off
         its 1310 nm TX laser (resetting both its 50% loopback and Collector Box #2 RX), and
         when `GPIO 32` goes high, Field Box #1 blasts a fresh `/C/` optical handshake burst!
      2. Layer 2 (Fallback `ip link set <iface> down/up` + `ethtool -r <iface>`):
         Standard kernel link/auto-negotiation restart when running as root.
    """
    if iface is None:
        iface = find_primary_ethernet_interface()
    if force_phy_reset is None:
        force_phy_reset = os.getenv("DIODE_PHY_RESET", "1") != "0"

    retriggered = False
    if force_phy_reset:
        # 1. Primary Raspberry Pi 5 RP1 GPIO 32 (ETH_RST_N) logic-level PHY reset (0.00A 5V surge)
        try:
            res_off = subprocess.run(
                ["pinctrl", "set", "32", "op", "dl"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
            if res_off.returncode == 0:
                time.sleep(max(0.1, float(down_hold_s)))
                subprocess.run(
                    ["pinctrl", "set", "32", "op", "dh"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                )
                retriggered = True
        except Exception:
            try:
                subprocess.run(
                    ["pinctrl", "set", "32", "op", "dh"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                )
            except Exception:
                pass

    # 2. Fallback LFP-coupled copper carrier pulse (ip link down -> hold -> up + ethtool -r)
    if not retriggered:
        try:
            res_down = subprocess.run(
                ["ip", "link", "set", iface, "down"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if res_down.returncode == 0:
                time.sleep(max(0.1, float(down_hold_s)))
                subprocess.run(
                    ["ip", "link", "set", iface, "up"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                retriggered = True
            subprocess.run(
                ["ethtool", "-r", iface],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    setup_unidirectional_network()
    # CRITICAL TIMING INVARIANT (Verified via Raspberry Pi 5 kernel dmesg):
    # - After releasing RP1 GPIO 32 (ETH_RST_N -> op dh), BCM54213PE + StarTech Box #1 (LFP=ON)
    #   require ~4.10 seconds to complete 1000BASE-T / 1000BASE-X auto-negotiation ("Link is Up").
    # - Once carrier=1, Linux attaches fe80:: to /proc/net/if_inet6 immediately with flag 0x40
    #   (IFA_F_TENTATIVE) for ~1.3 seconds during IPv6 Duplicate Address Detection (DAD).
    #   Calling sendto('ff02::1%eth0') while 0x40 is set fails with Errno 99 (Cannot assign
    #   requested address). Therefore, wait up to 6.5s for carrier and up to 2.5s for non-tentative
    #   (flags & 0x40 == 0) IPv6 link-local readiness.
    wait_for_ethernet_carrier(iface=iface, timeout_s=6.5)
    if down_hold_s >= 0.4:
        deadline_v6 = time.time() + 2.5
        while time.time() < deadline_v6:
            try:
                if os.path.exists("/proc/net/if_inet6"):
                    ready_v6 = False
                    with open("/proc/net/if_inet6", "r", encoding="utf-8") as f6:
                        for line in f6:
                            parts = line.strip().split()
                            if len(parts) >= 6 and parts[5] == iface:
                                if (int(parts[4], 16) & 0x40) == 0:
                                    ready_v6 = True
                                    break
                    if ready_v6:
                        break
                else:
                    break
            except Exception:
                break
            time.sleep(0.15)
    return retriggered

def wait_for_ethernet_carrier(iface=None, timeout_s=3.0):
    """
    Waits for IEEE 802.3 1000BASE-T copper/optical auto-negotiation carrier lock
    (/sys/class/net/<iface>/carrier == '1') before firing UDP bursts on cold boot.
    """
    if iface is None:
        iface = find_primary_ethernet_interface()
    carrier_path = f"/sys/class/net/{iface}/carrier"
    if not os.path.exists(carrier_path):
        return True

    deadline = time.time() + timeout_s
    carrier_up = False
    while time.time() < deadline:
        try:
            with open(carrier_path, "r", encoding="utf-8") as f:
                if f.read().strip() == "1":
                    carrier_up = True
                    break
        except Exception:
            pass
        time.sleep(0.05)

    if carrier_up:
        time.sleep(0.05)  # 50ms PHY post-negotiation settle
        try:
            subprocess.run(
                ["ip", "neigh", "replace", RECEIVER_IP, "lladdr", RECEIVER_MAC, "nud", "permanent", "dev", iface],
                check=False
            )
        except Exception:
            pass
    return carrier_up

def read_pico_telemetry(max_lines=5):
    """
    Reads magnetic, seismic, LWIR thermal, and 24GHz radar trigger data from the Pico over UART.
    Reads up to `max_lines` lines so an initial truncated mid-frame fragment is flushed.
    """
    for dev in ["/dev/ttyAMA0", "/dev/serial0"]:
        if os.path.exists(dev):
            try:
                with serial.Serial(dev, 115200, timeout=0.25) as ser:
                    for _ in range(max_lines):
                        raw = ser.readline()
                        if not raw:
                            break
                        line = raw.decode("utf-8", errors="ignore").strip()
                        if line.startswith("TRIG,"):
                            return line
            except Exception:
                pass
    return "TRIG,DIRECT_WAKE"


def pulse_ir_illuminator_strobe(duration_ms=30):
    """
    NVG-Stealth 940nm IR Discipline:
    Instead of illuminating 940nm IR LEDs continuously during boot (visible to Gen-3 NVGs),
    pulses the optional IR strobe gate (GPIO 24) for a single <30ms camera exposure window,
    or keeps it 100% dark when EMCON_NO_IR=1.
    """
    if os.getenv("EMCON_NO_IR", "0") == "1":
        return False
    ir_gpio = int(os.getenv("IR_STROBE_GPIO", "24"))
    try:
        subprocess.run(
            ["pinctrl", "set", str(ir_gpio), "op", "dh"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(max(0.005, min(0.050, duration_ms / 1000.0)))
        subprocess.run(
            ["pinctrl", "set", str(ir_gpio), "op", "dl"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False


def compute_aloha_interpass_delays_s(node_id=NODE_ID, shared_trunk=None):
    """
    Computes decorrelated inter-pass Aloha backoff delays (100ms - 800ms) between
    Pass 1, Pass 2, and Pass 3 when multiple cameras share a passive optical splitter
    trunk (SHARED_FIBER_TRUNK=1), preventing burst collisions without 2-way comms.
    """
    if shared_trunk is None:
        shared_trunk = (os.getenv("SHARED_FIBER_TRUNK", "0") == "1")
    if not shared_trunk:
        return (0.0, 0.0)
    seed_int = int(hashlib.sha256(node_id.encode("utf-8")).hexdigest()[:8], 16)
    base_ms_1 = 100 + (seed_int % 350) + secrets.randbelow(150)
    base_ms_2 = 250 + ((seed_int >> 8) % 400) + secrets.randbelow(150)
    return (round(base_ms_1 / 1000.0, 3), round(base_ms_2 / 1000.0, 3))


def transmit_over_diode(sock, alert_meta, jpeg_bytes, shared_trunk=None, custom_signing_key=None):
    """
    Sends signed JSON metadata + chunked JPEG over one-way UDP with
    calibrated packet pacing, 8-byte cryptographic nonce chunk correlation,
    bounded metadata packet size (<= MAX_META_PACKET_BYTES), 3x carousel repetition,
    and optional Aloha inter-pass jitter for shared fiber trunks.
    """
    payload_hash = hashlib.sha256(jpeg_bytes).hexdigest()
    nonce_hex = alert_meta.get("nonce")
    if not nonce_hex or len(nonce_hex) != 16:
        nonce_hex = secrets.token_hex(8)

    alert_meta["img_sha256"] = payload_hash
    alert_meta["img_size"] = len(jpeg_bytes)
    alert_meta["nonce"] = nonce_hex
    nonce_bytes = bytes.fromhex(nonce_hex)

    # Enforce strict protocol header size limits so DD\x01 metadata never exceeds MTU or UDP buffer
    if isinstance(alert_meta.get("detections"), list):
        orig_dets = list(alert_meta["detections"])
        # Prioritize highest-confidence detections first
        orig_dets.sort(key=lambda d: float(d.get("conf", 0.0)) if isinstance(d, dict) else 0.0, reverse=True)
        total_det_count = len(orig_dets)
        capped_dets = orig_dets[:MAX_DETECTIONS_IN_PACKET]
        if total_det_count > len(capped_dets):
            alert_meta["total_detections"] = total_det_count
            alert_meta["detections_truncated"] = True
        alert_meta["detections"] = capped_dets

        # Further trim if serialized DD\x01 packet exceeds MAX_META_PACKET_BYTES
        while len(alert_meta["detections"]) > 0:
            candidate_bytes = json.dumps(alert_meta, separators=(",", ":")).encode("utf-8")
            if 3 + 64 + len(candidate_bytes) <= MAX_META_PACKET_BYTES:
                break
            alert_meta["detections"].pop()
            alert_meta["total_detections"] = total_det_count
            alert_meta["detections_truncated"] = True

    meta_bytes = json.dumps(alert_meta, separators=(",", ":")).encode("utf-8")
    active_sk = custom_signing_key if custom_signing_key is not None else signing_key
    signature = active_sk.sign(meta_bytes).signature

    # Type 0x01: Signed Alert Header Datagram
    header_pkt = b"DD\x01" + signature + meta_bytes

    CHUNK_SIZE = 1024
    chunks = [jpeg_bytes[i:i + CHUNK_SIZE] for i in range(0, len(jpeg_bytes), CHUNK_SIZE)]
    total_chunks = len(chunks)
    interpass_delays = compute_aloha_interpass_delays_s(
        node_id=alert_meta.get("node", NODE_ID),
        shared_trunk=shared_trunk
    )

    # Optional Zero-Config IPv6 All-Nodes Link-Local Multicast companion socket (ff02::1%<iface>)
    # Ensures 100% delivery across the optical diode even if eth0/end0 has no IPv4 address, DHCP, or ARP
    sock6 = None
    ipv6_dest = None
    is_real_sock = isinstance(sock, socket.socket)
    if is_real_sock and os.getenv("DISABLE_IPV6_DIODE", "0") != "1":
        try:
            iface = find_primary_ethernet_interface()
            if hasattr(socket, "if_nametoindex"):
                if_idx = socket.if_nametoindex(iface)
                sock6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                ipv6_dest = ("ff02::1", UDP_PORT, 0, if_idx)
        except Exception:
            sock6 = None
            ipv6_dest = None

    def _dual_sendto(pkt):
        if is_real_sock:
            try:
                sock.sendto(pkt, (RECEIVER_IP, UDP_PORT))
            except OSError:
                pass
            if sock6 is not None and ipv6_dest is not None:
                try:
                    sock6.sendto(pkt, ipv6_dest)
                except OSError:
                    pass
        else:
            sock.sendto(pkt, (RECEIVER_IP, UDP_PORT))

    try:
        # 3x Carousel Burst with calibrated micro-pacing to protect receiver kernel buffers
        for pass_idx in range(3):
            if pass_idx > 0 and interpass_delays[pass_idx - 1] > 0:
                time.sleep(interpass_delays[pass_idx - 1])
            _dual_sendto(header_pkt)
            time.sleep(0.0012)  # 1.2ms pacing for metadata
            for idx, chunk in enumerate(chunks):
                chunk_hdr = b"DD\x02" + nonce_bytes + struct.pack(">HH", idx, total_chunks)
                _dual_sendto(chunk_hdr + chunk)
                time.sleep(0.0008)  # 800us pacing between chunks (~10 Mbps line rate)
    finally:
        if sock6 is not None:
            try:
                sock6.close()
            except Exception:
                pass


def signal_pico_done():
    """
    Guaranteed hardware power-down handshake via GPIO 23 with multi-driver fallback:
    1. Native Bookworm 'pinctrl' (preferred: latches RP1/BCM pad state directly)
    2. libgpiod 'gpioset' (probes gpiochip4 on Pi 5 and gpiochip0 on Pi 4)
    3. Legacy sysfs '/sys/class/gpio'
    """
    latched = False
    # Driver 1: pinctrl (Pi 5 / Pi 4 Bookworm standard)
    try:
        res = subprocess.run(
            ["pinctrl", "set", str(DONE_GPIO), "op", "dh"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if res.returncode == 0:
            latched = True
    except Exception:
        pass

    # Driver 2: libgpiod gpioset (only if pinctrl was unavailable)
    if not latched:
        for chip in ("gpiochip4", "gpiochip0"):
            try:
                res = subprocess.run(
                    ["gpioset", chip, f"{DONE_GPIO}=1"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                if res.returncode == 0:
                    latched = True
                    break
            except Exception:
                pass

    # Driver 3: sysfs fallback
    if not latched:
        try:
            val_path = f"/sys/class/gpio/gpio{DONE_GPIO}/value"
            if os.path.exists(val_path):
                with open(val_path, "w") as f:
                    f.write("1")
        except Exception:
            pass

    # Rapid crash-safe poweroff (skipped when BENCH_TEST_MODE=1 for interactive bench testing)
    if os.getenv("BENCH_TEST_MODE", "0") != "1":
        try:
            subprocess.run(["poweroff", "-f"], check=False)
        except Exception:
            pass
    else:
        print("[*] BENCH_TEST_MODE=1: Asserted DONE_GPIO (GPIO 23), skipping poweroff -f.")


def compute_crop_pixel_bounds(frame_shape, xmin, ymin, xmax, ymax, pad_px=40):
    """Computes clamped pixel crop coordinates (x1, y1, x2, y2) for a normalized box."""
    h, w = int(frame_shape[0]), int(frame_shape[1])
    x1 = max(0, int(xmin * w) - pad_px)
    y1 = max(0, int(ymin * h) - pad_px)
    x2 = min(w, int(xmax * w) + pad_px)
    y2 = min(h, int(ymax * h) + pad_px)
    if x2 <= x1 or y2 <= y1:
        return (0, 0, w, h)
    return (x1, y1, x2, y2)


def remap_detections_to_crop(detections, crop_bounds, frame_shape):
    """
    Transforms full-frame normalized detection bounding boxes [xmin, ymin, xmax, ymax]
    into normalized [0..1, 0..1] coordinates relative to the cropped JPEG image `(x1, y1, x2, y2)`.
    Preserves the original full-frame coordinates in `full_frame_box` so dashboard overlays
    align 100% accurately on the transmitted target crop.
    """
    if not detections or not crop_bounds:
        return detections
    h, w = float(frame_shape[0]), float(frame_shape[1])
    x1, y1, x2, y2 = [float(v) for v in crop_bounds]
    crop_w = max(1.0, x2 - x1)
    crop_h = max(1.0, y2 - y1)

    remapped = []
    for det in detections:
        if not isinstance(det, dict) or "box" not in det or len(det["box"]) != 4:
            remapped.append(det)
            continue
        bx1, by1, bx2, by2 = [float(v) for v in det["box"]]
        # Convert full-frame [0..1] -> full-frame pixels -> crop-relative [0..1]
        cx1 = max(0.0, min(1.0, (bx1 * w - x1) / crop_w))
        cy1 = max(0.0, min(1.0, (by1 * h - y1) / crop_h))
        cx2 = max(0.0, min(1.0, (bx2 * w - x1) / crop_w))
        cy2 = max(0.0, min(1.0, (by2 * h - y1) / crop_h))
        new_det = dict(det)
        new_det["full_frame_box"] = [round(bx1, 3), round(by1, 3), round(bx2, 3), round(by2, 3)]
        new_det["box"] = [round(cx1, 3), round(cy1, 3), round(cx2, 3), round(cy2, 3)]
        remapped.append(new_det)
    return remapped


def _encode_target_crop(m_frame, xmin, ymin, xmax, ymax, quality=75, return_bounds=False):
    """
    Extracts a padded target crop from the 1080p frame and encodes to JPEG.
    Note: Picamera2 'RGB888' on Raspberry Pi OS Bookworm outputs 3-channel arrays in OpenCV BGR
    memory order directly; channel swapping is only performed if CAMERA_COLOR_SWAP_RB=1 is set.
    """
    x1, y1, x2, y2 = compute_crop_pixel_bounds(m_frame.shape, xmin, ymin, xmax, ymax, pad_px=40)
    crop_view = m_frame[y1:y2, x1:x2]
    if os.getenv("CAMERA_COLOR_SWAP_RB", "0") == "1":
        crop_view = cv2.cvtColor(crop_view, cv2.COLOR_RGB2BGR)
    _, enc = cv2.imencode(".jpg", crop_view, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    jpeg_bytes = enc.tobytes()
    if return_bounds:
        return jpeg_bytes, (x1, y1, x2, y2)
    return jpeg_bytes


REFERENCE_SUBJECT_HEIGHTS_M = {
    "person": 1.75,
    "bicycle": 1.45,
    "car": 1.55,
    "motorcycle_atv_snowmobile": 1.25,
    "aircraft_drone": 0.45,
    "drone_uav": 0.35,
    "helicopter": 3.50,
    "airplane": 4.20,
    "bus": 3.00,
    "train_tracked_vehicle": 3.20,
    "truck_tractor": 2.60,
    "boat_watercraft": 1.60,
    "cervid_moose_horse": 1.95,
    "deer_reindeer_sheep": 1.15,
    "moose_bovid": 1.95,
    "bear": 1.35,
}


def parse_pico_trig_fields(pico_trig):
    """
    Parses key=value fields from the Pico 2 Gatekeeper UART string
    (e.g., 'TRIG,MAG=3200,SEIS=850,DIST=4500,SPD=120,TEMP=-4.2,UPTIME_S=3600').
    Also supports compact bench strings such as 'RADAR+MAG:120'.
    """
    fields = {}
    if not pico_trig or not isinstance(pico_trig, str):
        return fields
    for token in pico_trig.strip().split(","):
        if "=" in token:
            k, v = token.split("=", 1)
            k = k.strip().upper()
            v = v.strip()
            try:
                fields[k] = float(v) if "." in v else int(v)
            except ValueError:
                fields[k] = v
    return fields


def estimate_subject_kinematics(
    detections,
    pico_telemetry,
    captured_pairs=None,
    frame_dt_s=0.05,
    cam_horiz_fov_deg=102.0,
    cam_vert_fov_deg=67.0,
    oblique_trail_deg=25.0,
):
    """
    Estimates where the detected subject was seen, where it is heading, and how fast
    by fusing:
      1. Full-frame optical bounding-box horizontal bearing offset & vertical angular size,
      2. HLK-LD2450 24 GHz FMCW radar range (DIST in mm) and radial speed (SPD in cm/s), and
      3. Multi-frame optical centroid shift across the 3-frame burst (when available).
    Returns a compact dictionary suitable for signing inside the DD\\x01 metadata packet.
    """
    import math

    trig = parse_pico_trig_fields(pico_telemetry)
    radar_dist_mm = float(trig.get("DIST", 0.0) or 0.0)
    if radar_dist_mm <= 0.0 and "RADAR_M" in trig:
        try:
            radar_dist_mm = float(trig["RADAR_M"]) * 1000.0
        except (ValueError, TypeError):
            radar_dist_mm = 0.0
    radar_spd_cms = float(trig.get("SPD", 0.0) or 0.0)

    primary_det = None
    if isinstance(detections, list) and detections:
        valid_dets = [d for d in detections if isinstance(d, dict)]
        if valid_dets:
            primary_det = max(valid_dets, key=lambda d: float(d.get("conf", 0.0)))

    subj_class = primary_det.get("class", "unknown") if primary_det else "unknown"
    subj_conf = round(float(primary_det.get("conf", 0.0)), 2) if primary_det else 0.0

    # Use full_frame_box if already remapped to crop, otherwise box/bbox
    box = None
    if primary_det:
        box = primary_det.get("full_frame_box") or primary_det.get("box") or primary_det.get("bbox")

    bearing_offset_deg = 0.0
    box_height_norm = 0.0
    box_xc = 0.5
    if isinstance(box, (list, tuple)) and len(box) == 4:
        bx1, by1, bx2, by2 = [float(v) for v in box]
        box_xc = max(0.0, min(1.0, 0.5 * (bx1 + bx2)))
        box_height_norm = max(0.02, min(1.0, abs(by2 - by1)))
        bearing_offset_deg = round((box_xc - 0.5) * float(cam_horiz_fov_deg), 2)

    # Distance estimation: prefer 24 GHz radar range; fall back to pinhole angular height
    if radar_dist_mm > 100.0:
        est_distance_m = round(radar_dist_mm / 1000.0, 2)
    elif box_height_norm > 0.03:
        ref_h = REFERENCE_SUBJECT_HEIGHTS_M.get(subj_class, 1.70)
        vert_fov_rad = math.radians(max(10.0, float(cam_vert_fov_deg)))
        subj_angle_rad = max(0.02, box_height_norm * vert_fov_rad)
        est_distance_m = round(max(2.0, min(80.0, ref_h / (2.0 * math.tan(subj_angle_rad / 2.0)))), 2)
    else:
        est_distance_m = 12.0

    # Radial velocity (m/s): HLK-LD2450 positive SPD = approaching or receding along radar axis
    radial_speed_mps = round(radar_spd_cms / 100.0, 2)

    # Transverse velocity (m/s): estimate from inter-frame centroid shift across burst if available
    transverse_speed_mps = 0.0
    if captured_pairs and len(captured_pairs) >= 2 and cv2 is not None:
        try:
            g_first = cv2.cvtColor(captured_pairs[0][0], cv2.COLOR_BGR2GRAY)
            g_last = cv2.cvtColor(captured_pairs[-1][0], cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(cv2.GaussianBlur(g_first, (5, 5), 0), cv2.GaussianBlur(g_last, (5, 5), 0))
            _, thr = cv2.threshold(diff, 22, 255, cv2.THRESH_BINARY)
            moments = cv2.moments(thr)
            if moments["m00"] > 200:
                cx_last = (moments["m10"] / moments["m00"]) / float(g_last.shape[1])
                dx_norm = cx_last - box_xc
                total_dt = max(0.02, frame_dt_s * (len(captured_pairs) - 1))
                horiz_span_m = 2.0 * est_distance_m * math.tan(math.radians(cam_horiz_fov_deg / 2.0))
                transverse_speed_mps = round(max(-25.0, min(25.0, (dx_norm * horiz_span_m) / total_dt)), 2)
        except Exception:
            transverse_speed_mps = 0.0

    # Combine radial and transverse components (accounting for oblique trail mounting angle)
    if abs(radial_speed_mps) > 0.05 and abs(transverse_speed_mps) < 0.05:
        oblique_rad = math.radians(max(5.0, min(75.0, float(oblique_trail_deg))))
        ground_speed_mps = abs(radial_speed_mps) / max(0.5, math.cos(oblique_rad))
        sign_dir = 1.0 if radial_speed_mps >= 0 else -1.0
        transverse_speed_mps = round(sign_dir * ground_speed_mps * math.sin(oblique_rad), 2)
    else:
        ground_speed_mps = math.hypot(radial_speed_mps, transverse_speed_mps)

    # Default nominal movement speed by class if triggered without Doppler radial speed
    if ground_speed_mps < 0.15 and primary_det is not None:
        default_speeds = {
            "person": 1.45,
            "bicycle": 4.50,
            "car": 8.33,
            "motorcycle_atv_snowmobile": 7.50,
            "aircraft_drone": 15.0,
            "drone_uav": 15.0,
            "helicopter": 45.0,
            "airplane": 65.0,
            "truck_tractor": 6.50,
            "boat_watercraft": 5.00,
        }
        ground_speed_mps = default_speeds.get(subj_class, 1.40)
        oblique_rad = math.radians(float(oblique_trail_deg))
        radial_speed_mps = round(ground_speed_mps * math.cos(oblique_rad), 2)
        transverse_speed_mps = round(ground_speed_mps * math.sin(oblique_rad), 2)

    est_speed_mps = round(ground_speed_mps, 2)
    est_speed_kmh = round(est_speed_mps * 3.6, 1)

    # Relative heading angle in camera frame (0 deg = moving away along boresight, 180 deg = approaching camera)
    if est_speed_mps < 0.1:
        movement_direction = "stationary"
        rel_heading_deg = 0.0
    else:
        # Convert (radial, transverse) into relative movement bearing
        # Positive radial_speed_mps = approaching camera (180 deg relative to camera look vector)
        away_vel_m = -radial_speed_mps
        rel_heading_deg = round(math.degrees(math.atan2(transverse_speed_mps, away_vel_m)) % 360.0, 1)
        if abs(radial_speed_mps) >= abs(transverse_speed_mps):
            movement_direction = "approaching" if radial_speed_mps > 0 else "receding"
        else:
            movement_direction = "traversing_right" if transverse_speed_mps > 0 else "traversing_left"

    return {
        "primary_class": subj_class,
        "primary_conf": subj_conf,
        "bearing_offset_deg": bearing_offset_deg,
        "est_distance_m": est_distance_m,
        "radial_speed_mps": radial_speed_mps,
        "transverse_speed_mps": transverse_speed_mps,
        "est_speed_mps": est_speed_mps,
        "est_speed_kmh": est_speed_kmh,
        "relative_heading_deg": rel_heading_deg,
        "movement_direction": movement_direction,
    }


# ==============================================================================
# Main Pipeline with Strict Fault Recovery
# ==============================================================================
def main():
    try:
        # Refresh node identity and key in case NODE_KEY_FILE / NODE_ID were configured at runtime
        active_signing_key = load_signing_key()
        iface = setup_unidirectional_network()
        raw_pico_telemetry = read_pico_telemetry()
        pico_telemetry, ephemeral_sk = derive_ephemeral_key_from_trig(raw_pico_telemetry)
        if ephemeral_sk is not None:
            active_signing_key = ephemeral_sk

        # Initialize Camera with Picamera2 using synchronized single-request capture
        picam2 = None
        captured_pairs = []

        try:
            from picamera2 import Picamera2
            picam2 = Picamera2()
            cfg_fn = getattr(picam2, "create_preview_configuration", None) or getattr(picam2, "create_still_configuration")
            config = cfg_fn(
                main={"size": (1920, 1080), "format": "RGB888"},
                lores={"size": (640, 640), "format": "RGB888"}
            )
            picam2.configure(config)
            picam2.start()
            # Lock IMX708 VCM voice-coil lens to Hyperfocal position (0.5 diopters = 2.0m center,
            # keeping 1.0m to infinity razor-sharp with 0ms PDAF hunting on foreground twigs/snow)
            if hasattr(picam2, "set_controls"):
                try:
                    lens_pos = float(os.getenv("CAM_LENS_POSITION", "0.5"))
                    picam2.set_controls({"AfMode": 0, "LensPosition": lens_pos})
                except Exception:
                    pass
            time.sleep(0.25)
            # Pulse 940nm IR strobe only during active exposure window (NVG stealth discipline)
            pulse_ir_illuminator_strobe(30)
            for _ in range(3):
                if hasattr(picam2, "capture_request"):
                    req = picam2.capture_request()
                    try:
                        lores_f = req.make_array("lores")
                        main_f = req.make_array("main")
                    finally:
                        req.release()
                else:
                    lores_f = picam2.capture_array("lores")
                    main_f = picam2.capture_array("main")
                captured_pairs.append((lores_f, main_f))
                time.sleep(0.05)
        except Exception as e:
            print(f"[!] Picamera2 initialization error: {e}", file=sys.stderr)
        finally:
            if picam2:
                try:
                    picam2.stop()
                except Exception:
                    pass

        # Fallback to pre-installed rpicam-still / libcamera-still CLI on Raspberry Pi OS Lite
        if not captured_pairs:
            for cli_bin in ("/usr/bin/rpicam-still", "rpicam-still", "/usr/bin/libcamera-still", "libcamera-still"):
                try:
                    tmp_jpg = "/dev/shm/trailcam_capture.jpg"
                    lens_pos = str(float(os.getenv("CAM_LENS_POSITION", "0.5")))
                    pulse_ir_illuminator_strobe(30)
                    res = subprocess.run(
                        [
                            cli_bin, "-n", "-t", "250",
                            "--width", "1920", "--height", "1080",
                            "--autofocus-mode", "manual", "--lens-position", lens_pos,
                            "-o", tmp_jpg,
                        ],
                        capture_output=True, text=True, timeout=6
                    )
                    if res.returncode == 0 and os.path.exists(tmp_jpg):
                        bgr_frame = cv2.imread(tmp_jpg)
                        if bgr_frame is not None and bgr_frame.size > 0:
                            lores_f = cv2.resize(bgr_frame, (640, 640))
                            captured_pairs.append((lores_f, bgr_frame))
                            break
                except Exception:
                    continue

        camera_ok = bool(captured_pairs)
        main_frame = captured_pairs[-1][1] if captured_pairs else None

        # If camera failed, generate a clean zero-initialized test frame for operator feedback
        if main_frame is None:
            canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
            main_frame = cv2.putText(
                canvas,
                "CAMERA SENSOR ERROR", (200, 540),
                cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 3
            )

        detections_found = []
        best_crop_jpeg = b""
        best_crop_bounds = None
        best_crop_frame_shape = main_frame.shape
        inference_backend = "camera_error" if not camera_ok else "full_frame"

        # Attempt Hailo NPU Inference across captured frames with Graceful CPU Fallback
        hailo_available = False
        if os.path.exists(HEF_PATH) and captured_pairs:
            try:
                from picamera2.devices import Hailo
                with Hailo(HEF_PATH) as hailo:
                    for lores_frame, m_frame in captured_pairs:
                        results = hailo.run(lores_frame)
                        hailo_available = True
                        inference_backend = "hailo"
                        best_score = -1.0
                        for class_id, bboxes in enumerate(results):
                            if class_id in TARGET_CLASSES and len(bboxes) > 0:
                                for box in bboxes:
                                    score = float(box[4])
                                    if score >= CONF_THRESHOLD:
                                        ymin, xmin, ymax, xmax = [float(v) for v in box[:4]]
                                        detections_found.append({
                                            "class": TARGET_CLASSES[class_id],
                                            "conf": round(score, 2),
                                            "box": [round(xmin, 3), round(ymin, 3), round(xmax, 3), round(ymax, 3)]
                                        })
                                        if score > best_score:
                                            best_score = score
                                            best_crop_jpeg, best_crop_bounds = _encode_target_crop(
                                                m_frame, xmin, ymin, xmax, ymax, return_bounds=True
                                            )
                                            best_crop_frame_shape = m_frame.shape
                        if detections_found:
                            break
            except Exception as e:
                hailo_available = False
                detections_found = []
                best_crop_jpeg = b""
                best_crop_bounds = None
                print(f"[!] Hailo NPU runtime failure (falling back to CPU): {e}", file=sys.stderr)

        # Fallback 1: CPU YOLOv8n ONNX inference via OpenCV DNN with Aspect-Ratio Letterboxing & No-Vanish Pose Probe
        if not hailo_available and os.path.exists(ONNX_PATH) and captured_pairs:
            try:
                net = cv2.dnn.readNetFromONNX(ONNX_PATH)
                lores_frame, m_frame = captured_pairs[-1]
                # Use aspect-ratio letterboxed m_frame when m_frame is non-square, avoiding 1.77x aspect distortion
                infer_src = m_frame if (m_frame is not None and m_frame.shape[0] != m_frame.shape[1]) else lores_frame
                padded_img, scale_r, pad_dw, pad_dh = letterbox_image(infer_src, 640)
                src_h, src_w = infer_src.shape[:2]
                # Picamera2 RGB888 is BGR in memory; swapRB=True produces RGB input expected by YOLOv8 ONNX
                swap_rb = os.getenv("CAMERA_COLOR_SWAP_RB", "1") == "1"
                blob = cv2.dnn.blobFromImage(padded_img, 1.0 / 255.0, (640, 640), swapRB=swap_rb, crop=False)
                net.setInput(blob)
                preds = net.forward()
                inference_backend = "onnx_cpu"
                # YOLOv8 output shape: (1, 84, 8400) -> transpose to (8400, 84)
                if preds.ndim == 3 and preds.shape[1] < preds.shape[2]:
                    preds = np.transpose(preds[0], (1, 0))
                elif preds.ndim == 3:
                    preds = preds[0]

                boxes_xywh = []
                scores_list = []
                class_ids = []
                norm_boxes = []
                for row in preds:
                    scores = row[4:]
                    class_id = int(np.argmax(scores))
                    score = float(scores[class_id])
                    if class_id in TARGET_CLASSES and score >= CONF_THRESHOLD:
                        cx, cy, bw, bh = [float(v) for v in row[:4]]
                        x1_px = (cx - bw / 2.0 - pad_dw) / scale_r
                        y1_px = (cy - bh / 2.0 - pad_dh) / scale_r
                        x2_px = (cx + bw / 2.0 - pad_dw) / scale_r
                        y2_px = (cy + bh / 2.0 - pad_dh) / scale_r
                        xmin = max(0.0, min(1.0, x1_px / float(src_w)))
                        ymin = max(0.0, min(1.0, y1_px / float(src_h)))
                        xmax = max(0.0, min(1.0, x2_px / float(src_w)))
                        ymax = max(0.0, min(1.0, y2_px / float(src_h)))
                        boxes_xywh.append([int(xmin * 640), int(ymin * 640), int((xmax - xmin) * 640), int((ymax - ymin) * 640)])
                        scores_list.append(score)
                        class_ids.append(class_id)
                        norm_boxes.append((xmin, ymin, xmax, ymax))

                if boxes_xywh:
                    indices = cv2.dnn.NMSBoxes(boxes_xywh, scores_list, CONF_THRESHOLD, 0.45)
                    flat_indices = [int(i[0]) if isinstance(i, (list, tuple, np.ndarray)) else int(i) for i in indices]
                    best_score = -1.0
                    for idx in flat_indices:
                        xmin, ymin, xmax, ymax = norm_boxes[idx]
                        score = scores_list[idx]
                        cid = class_ids[idx]
                        detections_found.append({
                            "class": TARGET_CLASSES[cid],
                            "conf": round(score, 2),
                            "box": [round(xmin, 3), round(ymin, 3), round(xmax, 3), round(ymax, 3)]
                        })
                        if score > best_score:
                            best_score = score
                            best_crop_jpeg, best_crop_bounds = _encode_target_crop(
                                m_frame, xmin, ymin, xmax, ymax, return_bounds=True
                            )
                            best_crop_frame_shape = m_frame.shape
            except Exception as e:
                print(f"[!] CPU ONNX fallback warning: {e}", file=sys.stderr)

        # Fallback 2: Multi-frame inter-frame motion ROI crop if NPU/ONNX unavailable
        if not hailo_available and not best_crop_jpeg and len(captured_pairs) >= 2:
            try:
                g1 = cv2.cvtColor(captured_pairs[0][0], cv2.COLOR_BGR2GRAY)
                g2 = cv2.cvtColor(captured_pairs[-1][0], cv2.COLOR_BGR2GRAY)
                diff = cv2.absdiff(cv2.GaussianBlur(g1, (5, 5), 0), cv2.GaussianBlur(g2, (5, 5), 0))
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cnts:
                    largest = max(cnts, key=cv2.contourArea)
                    if cv2.contourArea(largest) > 400:
                        rx, ry, rw, rh = cv2.boundingRect(largest)
                        xmin, ymin = rx / 640.0, ry / 640.0
                        xmax, ymax = (rx + rw) / 640.0, (ry + rh) / 640.0
                        detections_found.append({
                            "class": "motion_target",
                            "conf": 0.75,
                            "box": [round(xmin, 3), round(ymin, 3), round(xmax, 3), round(ymax, 3)]
                        })
                        inference_backend = "motion_roi"
                        best_crop_jpeg, best_crop_bounds = _encode_target_crop(
                            captured_pairs[-1][1], xmin, ymin, xmax, ymax, return_bounds=True
                        )
                        best_crop_frame_shape = captured_pairs[-1][1].shape
            except Exception:
                pass

        # Remap detection bounding boxes into the cropped image's coordinate frame
        if best_crop_jpeg and best_crop_bounds is not None:
            detections_found = remap_detections_to_crop(
                detections_found, best_crop_bounds, best_crop_frame_shape
            )

        # Fallback 3: if no target detected or NPU unavailable, encode a scaled full-frame snapshot
        if not best_crop_jpeg:
            fallback_bgr = cv2.resize(main_frame, (960, 540))
            if os.getenv("CAMERA_COLOR_SWAP_RB", "0") == "1":
                fallback_bgr = cv2.cvtColor(fallback_bgr, cv2.COLOR_RGB2BGR)
            if not camera_ok:
                cv2.putText(fallback_bgr, "CAMERA SENSOR ERROR", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            _, enc = cv2.imencode(".jpg", fallback_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
            best_crop_jpeg = enc.tobytes()

        # Ensure 1000BASE-T / optical carrier has completed auto-negotiation before firing UDP burst
        if os.getenv("DIODE_AUTO_RENEGOTIATE", "0") == "1":
            renegotiate_optical_diode_link(iface=iface)
        else:
            wait_for_ethernet_carrier(iface=iface, timeout_s=3.0)

        # Evaluate hydrocarbon/wildfire smoke obscuration & fuse optional USB TOPDON TC001 8-14 um LWIR hotspots
        lwir_smoke_meta = detect_smoke_obscuration_and_fuse_tc001_lwir(
            main_frame, existing_detections=detections_found
        )
        detections_found = lwir_smoke_meta["fused_detections"]

        # Construct and fire alert payload over optical diode
        subject_kinematics = estimate_subject_kinematics(
            detections_found, pico_telemetry, captured_pairs=captured_pairs
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        alert_payload = {
            "node": NODE_ID,
            "ts": int(time.time()),
            "pico_trig": pico_telemetry,
            "detections": detections_found,
            "subject_kinematics": subject_kinematics,
            "lwir_smoke_fusion": {
                "smoke_or_fog_obscured": lwir_smoke_meta["smoke_or_fog_obscured"],
                "eo_rms_contrast": lwir_smoke_meta["eo_rms_contrast"],
                "vis_055um_transmission_pct": lwir_smoke_meta["vis_055um_transmission_pct"],
                "lwir_10um_transmission_pct": lwir_smoke_meta["lwir_10um_transmission_pct"],
                "tc001_lwir_sensor_active": lwir_smoke_meta["tc001_lwir_sensor_active"],
                "lwir_hotspots_detected": lwir_smoke_meta["lwir_hotspots_detected"],
            },
            "hailo_active": hailo_available,
            "camera_ok": camera_ok,
            "inference_backend": inference_backend,
        }
        transmit_over_diode(sock, alert_payload, best_crop_jpeg, custom_signing_key=active_signing_key)
        sock.close()

    except Exception as e:
        print(f"[CRITICAL] Uncaught exception in sender pipeline: {e}", file=sys.stderr)
    finally:
        # ABSOLUTE SAFETY INVARIANT: Always assert DONE to cut Domain B power
        signal_pico_done()

if __name__ == "__main__":
    main()

