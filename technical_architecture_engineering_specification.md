# Technical Architecture & Engineering Specification

This document owns the active system architecture, event pipeline, and hardware/software interfaces. Master architecture decisions and the 10-day sprint roadmap belong in [PROJECT_DECISIONS_AND_ROADMAP.md](PROJECT_DECISIONS_AND_ROADMAP.md); component choices belong in the [BOM](pi-diode-trailcam/docs/HARDWARE_SPECS_AND_BOM.md), and physical connections in the [wiring schedule](pi-diode-trailcam/docs/WIRING_PINOUT.md).

## 1. System Packaging & Deployment Topologies

The field unit uses a **3-Zone Covert Split-Pod Architecture**:
1. **Zone 1 (Tree-Mounted Micro Sensor Pod, `Hammond 1591BSBK` $112 \times 62 \times 31\text{ mm}$ at $1.8\text{–}2.2\text{ m}$ height):** Houses one `Sony IMX708 NoIR` camera, a `940 nm` invisible IR illuminator isolated by an opaque closed-cell neoprene foam optical baffle, and an `HLK-LD2450` $24\text{ GHz}$ FMCW radar behind a non-metallic ultra-flat camouflaged ABS wall.
2. **Zone 2 (Concealed Trunk Umbilical, $1.8\text{–}2.2\text{ m}$):** Bundled low-voltage harness wrapped in `Gear Aid Camo Form` matte fabric tape routed down a natural bark crevice.
3. **Zone 3 (Moss-Buried Base Vault, `QILIPSU IP67` $285 \times 195 \times 130\text{ mm}$ at ground level):** Houses the `12V 12Ah` battery, `5A` inline fuse, `Adafruit MPM3610` $5\text{V}$ always-on Domain A buck, `Raspberry Pi Pico 2` Gatekeeper, `QMC5883L` magnetometer (+ `ADS1115` 16-bit ADC & `SM-24` geophone), `Adafruit STEMMA` high-side relay switch, `12V-to-5V 5A` Domain B buck, `Raspberry Pi 5` (`8GB` + Active Cooler + `Hailo-8L` + `J5` RTC battery), $5\text{V}$ `1310 nm` Media Converter #1, and `1×2 SC/UPC` 50/50 optical splitter.

### Supported Collector & Link Configurations
* **Scenario A — Cabin / Outbuilding Nearby ($30\text{ m}$ to $10\text{ km}$):** Direct `SC/UPC` armored single-mode OS2 fiber ($3\text{ mm}$ OD buried $2\text{ cm}$ under moss; $0.35\text{ dB/km}$ attenuation at $1310\text{ nm}$) connecting Splitter Output 2 to the indoor Cabin Collector Hub (`10.10.0.100/24`, `UDP 5514`).
* **Scenario B1 — No Cabin Nearby (Buried "Dead-Drop" Collector Vault):** A $100\text{–}300\text{ m}$ moss-buried armored fiber connects the tree node to a hidden, buried waterproof Collector Vault (`QILIPSU` #2 + battery + headless Pi Collector SSD running `receiver_hub.py --max-alerts 1000`). Even if the camera is discovered and destroyed at the trail, all captured JPEGs are already stored $200\text{ m}$ away in the hidden vault (and can optionally be forwarded via a decoupled radio/cellular/satellite relay at the remote vault without exposing the camera's location).
* **Scenario B2 — Obstacle / Water Strait Crossing ($5\text{ m}$ to $100\text{ m}$ Line-of-Sight):** A pair of COTS `1310 nm` fiber optic collimators (**Thorlabs** `F220FC-1310` / `F280FC-C` or **Edmund Optics**, mounted on low rigid bedrock/ground stakes) or industrial IP67 optical Ethernet transceivers (**Leuze DDLS 200** / **Sick ISD400**) bridges rivers, straits, or public roads where fiber cable cannot be laid.

---

## 2. Hardened End-to-End Event Pipeline

1. **Always-On Gatekeeper Polling (`pico_gatekeeper/main.py`):**
   * Automatically selects one of three operating profiles at boot based on hardware presence on `I2C0`:
     * `PROFILE_FULL_TRIPLE`: `QMC5883L` (`0x0D`) + `ADS1115` (`0x48`) + `HLK-LD2450` (`UART0`).
     * `PROFILE_MAG_RADAR_DUTY`: `QMC5883L` (`0x0D`) + periodic $350\text{ ms}$ radar sniff every $3.0\text{ s}$ (detects both ferromagnetic vehicles and non-ferromagnetic humans/wildlife when no geophone is attached).
     * `PROFILE_BENCH_MAG_ONLY`: Triggered by `BENCH_MAG_ONLY = True` or a `GP14 -> GND` jumper for single-sensor bench testing.
2. **Parallel Cold-Boot & Staggered Lens De-Icing ($6.5\text{–}7.1\text{ s}$ Total Latency):**
   * Upon target confirmation, the Pico asserts `MOSFET_GATE` (`GP15`) immediately at $t = 0.0\text{ s}$ to switch high-side Domain B `+12V` power.
   * In sub-zero conditions ($\le +1.0^\circ\text{C}$), the Pico waits $250\text{ ms}$ for buck inrush settling and pulses the PTC viewport heater (`GP16`/`GP22`) **in parallel** from $t = 0.25\text{ s}$ to $t = 4.25\text{ s}$ while the Pi 5 boots Linux, eliminating the former $4.5\text{ s}$ serial pre-heat delay.
   * The Pico transmits `TRIG,MAG=...,SEIS=...,RADAR_M=...,UPTIME_S=...,PROFILE=...\n` bursts at $115200\text{ baud}$ over `UART1` (`GP8 -> GPIO15`) and monitors `DONE` (`GPIO23 -> GP17/GP2`) with a **$3 \times 25\text{ ms}$ ($75\text{ ms}$) consecutive-high EMI debounce filter**.
3. **Cold-Boot Capture, Fallback Inference & Carrier-Lock (`pi5_sender_node/sender_node.py`):**
   * Brings `end0`/`eth0` (`10.10.0.10/24`) up immediately so `1000BASE-T` copper/optical negotiation runs concurrently with camera capture.
   * Reads up to 5 UART lines to flush any partial mid-character boot fragment and capture a complete `TRIG,...` frame.
   * Captures a 3-frame `Picamera2` burst (`main` $2304 \times 1296$ + `lores` $640 \times 640$) and executes a 3-tier exception-safe detection chain:
     1. **Primary:** `Hailo-8L` NPU (`yolov8s_h8l.hef`), setting `hailo_available = True` only after `hailo.run()` succeeds.
     2. **Fallback 1:** CPU OpenCV DNN (`yolov8n.onnx`) with `cv2.dnn.NMSBoxes` and highest-confidence crop selection.
     3. **Fallback 2:** Inter-frame motion ROI bounding-box extraction.
   * Polls `/sys/class/net/<iface>/carrier == "1"` (up to $3.0\text{ s}$) and injects static ARP (`10.10.0.100 -> ff:ff:ff:ff:ff:ff`) before transmitting.
4. **Signed One-Way UDP Carousel (`UDP 5514`):**
   * Signs JSON metadata (`node`, `ts`, `nonce`, `img_sha256`, `detections`, `pico_trig`, `camera_ok`, `inference_backend`) with the node's `Ed25519` private key (`Type 0x01`: `b"DD\x01" + 64B_sig + json_bytes`).
   * Slices the JPEG into $1300\text{-byte}$ binary chunks keyed by the **8-byte binary `nonce`** (`Type 0x02`: `b"DD\x02" + 8B_nonce + uint16_idx + uint16_total + chunk_bytes`) and transmits $3$ paced carousel passes.
5. **Cryptographic Verification, Multi-Pass Repair & Live UI (`collector_hub/`):**
   * `receiver_hub.py` verifies the `Ed25519` signature, validates the 16-char hex `nonce` against the persistent disk cache (`seen_nonces.jsonl`), logs off-grid clock drift warnings (`clock_drift_warning`), reassembles chunks by `nonce`, and retains `pending_meta` across Pass 2/3 if a Pass 1 bit error causes a `SHA-256` mismatch.
   * `dashboard_server.py` and `ui/index.html` paginate alerts via `/api/alerts?since_idx=<N>`, verify true receiver liveness via `receiver_heartbeat.json` + UDP port probe, and render the verified JPEG and bounding boxes directly inside `#camera-viewport`.

---

## 3. Hardware & Software Interface Summary

| Interface | Implementation Details |
| :--- | :--- |
| **Sensor Bus (`I2C0`)** | Pico `GP4` (`SDA`) / `GP5` (`SCL`) at $400\text{ kHz}$: `QMC5883L` (`0x0D`, $\le 1.5\text{ m}$ harness) and `ADS1115` (`0x48`, $V_{\text{DD}}/2$ biased differential input for `SM-24` geophone). |
| **Radar (`UART0`)** | Pico `GP0` (`TX`) / `GP1` (`RX`) at $256000\text{ baud}$, switched via high-side `GP6`; parses `HLK-LD2450` multi-target frames (`AA FF 03 00 ... 55 CC`). |
| **Telemetry (`UART1`)** | Pico `GP8` (`TX`) $\rightarrow$ Pi `GPIO15` (`RX`) at $115200\text{ baud}$ (`dtparam=uart0=on`); 5-line sync read. |
| **Power Cutoff (`DONE`)** | Pi `GPIO23` (`pinctrl set 23 op dh`) $\rightarrow$ Pico `GP17` (primary) / `GP2` (bench); $3 \times 25\text{ ms}$ consecutive-high debounce. |
| **Optical Diode Topology** | Field `5V` Media Converter `TX` ($1310\text{ nm}$) $\rightarrow$ `1×2 SC/UPC` 50/50 Splitter $\rightarrow$ Output 1 to Field `RX` (FEFI loopback) & Output 2 to Collector `RX` (Collector `TX` capped). |
| **Collector Storage** | `./verified_alerts` (`alerts_journal.jsonl`, `seen_nonces.jsonl`, `receiver_heartbeat.json`, `authorized_nodes.json`, and verified `.jpg` files; supports `--max-alerts` and `--export-bundle`). |
