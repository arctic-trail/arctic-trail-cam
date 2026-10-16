# Arctic Trail Cam System — Field Camera, Gatekeeper & Collector Hub Software (`pi-diode-trailcam`)

> **Open-source, RF-silent Arctic trail & cabin camera with a 1-way optical fiber diode and `<4mW` cold-boot gatekeeper. A private, pro-bono free-market COTS build.**

> [!WARNING]
> **PROTOTYPE STATUS (`v0.9-beta`):** This hardware and software package is under active development and physical benchtop testing. While all automated software/simulation suites pass (`4/4`), physical cold-boot latency (`target: 6.4–6.8 s`), battery discharge curves (`target: 120–220+ days`), and outdoor sensor thresholds are currently being tested on physical hardware. Defects are being fixed and measured performance reports will be posted as testing progresses.

This package contains the firmware and software for the **Arctic Trail Cam System**: the **Raspberry Pi Pico 2 Gatekeeper**, **Raspberry Pi 5 / Pi 4 Camera Sender Node**, and **Passive Optical Diode Collector Hub & Live Dashboard**.

See the [root documentation map](../README.md) for the complete guide index and the [Master Architecture Decisions & 10-Day Roadmap](../PROJECT_DECISIONS_AND_ROADMAP.md) for electrical, optical, and deployment specifications.

![3-Zone Covert Split-Pod Field Camera Unit in Context](docs/images/product_units_in_context.jpg)

---

## Core Software Entry Points

| File | Role & Hardened Capabilities |
| :--- | :--- |
| [`pico_gatekeeper/main.py`](pico_gatekeeper/main.py) | Always-on sensor polling (`QMC5883L` + `HLK-LD2450` + optional `SM-24`/`ADS1115`), automatic sensor profile detection (`PROFILE_FULL_TRIPLE`, `PROFILE_MAG_RADAR_DUTY`, `PROFILE_BENCH_MAG_ONLY`), parallel staggered PTC lens de-icing ($t = 0.25\text{..}4.25\text{ s}$), `UART1` telemetry (`TRIG,...,UPTIME_S=`), and $3 \times 25\text{ ms}$ EMI-debounced `DONE` power cutoff (`GP17`/`GP2`). |
| [`pi5_sender_node/sender_node.py`](pi5_sender_node/sender_node.py) | Cold-boot `Picamera2` capture, `1000BASE-T` carrier-lock polling, multi-line UART frame sync, `Hailo-8L` $\rightarrow$ CPU YOLOv8n ONNX (`NMSBoxes`) $\rightarrow$ Motion ROI fallback chain, `Ed25519` signing, 8-byte `nonce` chunk headers, and $3\times$ paced UDP carousel transmission (`10.10.0.100:5514`). |
| [`pi5_sender_node/install_pi5_fastboot.sh`](pi5_sender_node/install_pi5_fastboot.sh) | Idempotent Raspberry Pi OS Bookworm fastboot provisioning (`dtparam=uart0=on`, `enable_uart=1`, static ARP injection, `diode-node.service` registration). |
| [`pi5_sender_node/generate_keys.py`](pi5_sender_node/generate_keys.py) | Per-node `Ed25519` keypair generator (`--node`, `--write-node-key`, `--register-hub`) populating `node_key.json` and `authorized_nodes.json`. |
| [`collector_hub/receiver_hub.py`](collector_hub/receiver_hub.py) | Passive UDP `5514` listener, `Ed25519` verification, 8-byte `nonce` chunk reassembly, Pass 2/3 corrupt-chunk SHA-256 repair, persistent `seen_nonces.jsonl` anti-replay cache, off-grid clock-drift logging, circular disk retention (`--max-alerts`), and Dead-Drop courier export (`--export-bundle`). |
| [`collector_hub/dashboard_server.py`](collector_hub/dashboard_server.py) | Local Web UI server (`127.0.0.1:8123` default) with `?since_idx=` alert pagination, `os.path.commonpath` traversal protection, and true `receiver_heartbeat.json` + UDP port-bind health reporting. |
| [`collector_hub/ui/index.html`](collector_hub/ui/index.html) | Browser dashboard rendering actual verified JPEGs (`/alerts/<file>.jpg`) and AI bounding-box overlays in `#camera-viewport` alongside 3D terrain telemetry. |
| [`collector_hub/subghz_nlos_relay.py`](collector_hub/subghz_nlos_relay.py) | One-way Sub-GHz (`868 MHz` EU / `915 MHz` US) FHSS / LoRa woods-vault-to-farmhouse bridge (`--mode tx-vault` / `--mode rx-farmhouse`), preserving `Ed25519` payload signatures across $2\text{–}5\text{ km}$ of non-line-of-sight hills and trees. |
| [`run_guided_bench_doctor.py`](run_guided_bench_doctor.py) | Interactive & automated IKEA-style benchtop hardware doctor (`--self-test`, `--start-hub`, `--open-browser`): probes Pico 2 USB/`I2C0` (`0x0d`), checks Pi SSH & camera, prints pin-exact breadboard hole troubleshooting (`Hole j5`, `Hole j3`, `Hole a6`, `Hole a7`, `Hole a11`, `Hole a4`, `Hole a13`), and launches the Collector Hub + Live Dashboard in one command. |
| [`run_mock_demo.py`](run_mock_demo.py) | Self-contained synthetic end-to-end verification of `Ed25519` signing, 8-byte `nonce` chunking, and UDP reconstruction. |

---

## Starting the Collector Hub (Cabin Mode, Dead-Drop Vault Mode, or 2 km NLOS Farmhouse Bridge)

Install dependencies from [`collector_hub/requirements.txt`](collector_hub/requirements.txt) into your Python environment.

### 1. Cabin Collector Mode (Interactive Live Dashboard)
From this directory (`pi-diode-trailcam/`), open two terminals:

```bash
# Terminal 1: Start the passive UDP 5514 optical diode receiver
python3 collector_hub/receiver_hub.py

# Terminal 2: Start the local dashboard web server (defaults to 127.0.0.1:8123)
python3 collector_hub/dashboard_server.py --port 8123
```

Open `http://127.0.0.1:8123` in your browser. As alerts arrive over the one-way fiber link, the dashboard automatically paginates through all new events (`?since_idx=`) and renders the verified JPEG with detection bounding boxes in the top-right viewport.

### 2. Unattended "Dead-Drop" Collector Vault Mode (No Cabin Nearby)
When deployed inside a buried waterproof vault $100\text{–}300\text{ m}$ back in the woods with no cabin nearby:

```bash
# Run headless with a circular disk cap (e.g., keep the latest 1,000 verified JPEGs)
python3 collector_hub/receiver_hub.py --max-alerts 1000 --out-dir ./verified_alerts

# When visiting the buried vault to extract evidence into a single portable ZIP:
python3 collector_hub/receiver_hub.py --out-dir ./verified_alerts --export-bundle ./dead_drop_alerts_export.zip
```

### 3. `200 m – 20 km` Non-Line-of-Sight Lake Cottage $\rightarrow$ Farmhouse Bridge (`Scenario B3` / `sky-diode-relay` `Build D`)
When the camera protects a lake cottage $200\text{ m}$ to $20\text{ km}$ away from a main farmhouse with granite hills and boreal forest blocking line-of-sight:
* The Lake Cottage camera node sends full-resolution signed JPEGs over $200\text{ m}$ of moss-buried fiber to the woods Dead-Drop Vault (completely outside any burglar's $15\text{–}30\text{ m}$ RF jammer radius).
* The woods vault forwards a signed, cryptographically verified alert over the ordered **`2.4 GHz` Troposcatter, Hydrometeor & Canopy-Bounce System** ([`sky-diode-relay`](../sky-diode-relay/README.md) `Build D`: `ADALM-PLUTO` SDRs, `Skyworks SE2576L-EK1` `1 W` PA, `Skyworks SKY65405-21EK1` `1.2 dB NF` LNA, `Mini-Circuits VBF-2435+` bandpass filters, and `2× L-com HG2414P` `14 dBi` flat-panel antennas) with 6-layer out-of-ISM guard-band anti-jamming (`2380.373 MHz`, `2487.818 MHz`, `2459.496 MHz`) and persistent store-and-forward retry:

```bash
# Run the full 200m–20km Build D Troposcatter & 6-Layer Anti-Jamming link verification suite:
pytest -v ../sky-diode-relay/tests/test_sky_relay.py
```

### 4. Provisioning Unique Node Keys Before Field Deployment
Generate a unique `Ed25519` keypair for each camera node and register its public key with the collector hub:

```bash
python3 pi5_sender_node/generate_keys.py \
  --node NODE-NORTH-01 \
  --write-node-key ./node_key.json \
  --register-hub ./verified_alerts/authorized_nodes.json
```

Follow **[Part 1: IKEA-Style Indoor Benchtop Assembly & Bring-Up Manual (`Stages 1–3`)](docs/BENCHTOP_QUICKSTART_GUIDE.md)** and **[Part 2: IKEA-Style 3-Zone Enclosure Build, Camouflage & Tree Installation Manual (`Stages 4–6`)](docs/ASSEMBLY_GUIDE.md)** (plus the complete **[Tools & Hole-Saw Schedule (`[T01]`–`[T12]`)](docs/HARDWARE_SPECS_AND_BOM.md#complete-tools--workshop-equipment-schedule-t01t12)**) for step-by-step zero-experience assembly, installation, and daily operation.
