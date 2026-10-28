# `pi-diode-trailcam` — Software Stack & CLI Reference

> **Single-Source Documentation Notice:** System architecture, hardware BOMs, and step-by-step assembly instructions are maintained in a single location to avoid duplication:
> * **Project Overview & SSOT Documentation Map:** [`../README.md`](../README.md)
> * **Complete Illustrated Build & Field Manual (PDF):** [`../ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf`](../ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf)
> * **Part 1 — Indoor Benchtop Assembly (`Stages 1–3`, `Photos 1–58`):** [`docs/BENCHTOP_QUICKSTART_GUIDE.md`](docs/BENCHTOP_QUICKSTART_GUIDE.md)
> * **Part 2 — Enclosure Build, Camouflage & Tree Deployment (`Stages 4–6`):** [`docs/ASSEMBLY_GUIDE.md`](docs/ASSEMBLY_GUIDE.md)
> * **Parts, Tools & Cold-Weather Power Schedule (`[P01]`–`[P24]`, `[T01]`–`[T12]`):** [`docs/HARDWARE_SPECS_AND_BOM.md`](docs/HARDWARE_SPECS_AND_BOM.md)
> * **Electrical Pinout & Breadboard Coordinate Schedule:** [`docs/WIRING_PINOUT.md`](docs/WIRING_PINOUT.md)

---

## Core Software Entry Points

| File | Role & Capabilities |
| :--- | :--- |
| [`pico_gatekeeper/main.py`](pico_gatekeeper/main.py) | Always-on sensor polling (`QMC5883L` + `HLK-LD2450` + optional `SM-24`/`ADS1115`), automatic sensor profile detection (`PROFILE_FULL_TRIPLE`, `PROFILE_MAG_RADAR_DUTY`, `PROFILE_BENCH_MAG_ONLY`), parallel staggered PTC lens de-icing ($t = 0.25\text{..}4.25\text{ s}$), `UART1` telemetry (`TRIG,...,UPTIME_S=`), and $3 \times 25\text{ ms}$ EMI-debounced `DONE` power cutoff (`GP17`/`GP2`). |
| [`pi5_sender_node/sender_node.py`](pi5_sender_node/sender_node.py) | Cold-boot `Picamera2` capture (locked hyperfocal `AfMode=0, LensPosition=0.5`), `1000BASE-T` carrier-lock polling, multi-line UART frame sync, `Hailo-8L` $\rightarrow$ CPU YOLOv8n ONNX (`NMSBoxes`) $\rightarrow$ Motion ROI fallback chain, `Ed25519` signing, 8-byte `nonce` chunk headers, and $3\times$ paced UDP carousel transmission (`10.10.0.100:5514`). |
| [`pi5_sender_node/install_pi5_fastboot.sh`](pi5_sender_node/install_pi5_fastboot.sh) | Idempotent Raspberry Pi OS Bookworm fastboot provisioning (`dtparam=uart0=on`, `enable_uart=1`, static ARP injection, `diode-node.service` registration, read-only `OverlayFS`). |
| [`pi5_sender_node/generate_keys.py`](pi5_sender_node/generate_keys.py) | Per-node `Ed25519` keypair generator (`--node`, `--write-node-key`, `--register-hub`) populating `node_key.json` and `authorized_nodes.json`. |
| [`collector_hub/receiver_hub.py`](collector_hub/receiver_hub.py) | Passive UDP `5514` listener, `Ed25519` verification, 8-byte `nonce` chunk reassembly, Pass 2/3 corrupt-chunk SHA-256 repair, persistent `seen_nonces.jsonl` anti-replay cache, circular disk retention (`--max-alerts`), and Dead-Drop bundle export/verification (`--export-bundle`, `--verify-bundle`). |
| [`collector_hub/dashboard_server.py`](collector_hub/dashboard_server.py) | Local Web UI server (`127.0.0.1:8123` default) with `?since_idx=` alert pagination, `os.path.commonpath` traversal protection, and forensic evidence ZIP export. |
| [`collector_hub/ui/index.html`](collector_hub/ui/index.html) | Browser dashboard rendering verified JPEGs (`/alerts/<file>.jpg`) and AI bounding-box overlays alongside 3D terrain telemetry. |
| [`collector_hub/subghz_nlos_relay.py`](collector_hub/subghz_nlos_relay.py) | One-way Sub-GHz (`868 MHz` EU / `915 MHz` US) FHSS / LoRa woods-vault-to-farmhouse bridge (`--mode tx-vault` / `--mode rx-farmhouse`). |
| [`run_guided_bench_doctor.py`](run_guided_bench_doctor.py) | Automated benchtop hardware doctor (`--self-test`, `--start-hub`, `--open-browser`): probes Pico 2 USB/`I2C0` (`0x0d`), checks Pi SSH & camera, prints pin-exact breadboard hole troubleshooting (`Hole j5`, `Hole j3`, `Hole a6`, `Hole a7`, `Hole a11`, `Hole a4`, `Hole a13`, `Hole f24`–`Hole f27`), and launches the Collector Hub + Live Dashboard. |
| [`run_freezer_soak_acceptance.py`](run_freezer_soak_acceptance.py) | Stage 5 `-18 °C` freezer soak & cold-start acceptance runner (`--self-test`, `--journal-dir`, `--max-temp-c -10.0`, `--min-frames 5`): audits `Ed25519` `.sig.json` receipts, `SHA-256` JPEG integrity, `TEMP=` telemetry, and fail-closed production key enforcement. |
| [`run_mock_demo.py`](run_mock_demo.py) | Self-contained synthetic end-to-end verification of `Ed25519` signing, 8-byte `nonce` chunking, and UDP reconstruction. |

---

## Quick CLI Commands

```bash
# 1. Start the Cabin Collector Receiver & Live Web Dashboard (http://127.0.0.1:8123):
python3 collector_hub/receiver_hub.py
python3 collector_hub/dashboard_server.py --port 8123

# 2. Run Headless Dead-Drop Vault Mode (circular disk retention + portable ZIP export/verify):
python3 collector_hub/receiver_hub.py --max-alerts 1000 --out-dir ./verified_alerts
python3 collector_hub/receiver_hub.py --out-dir ./verified_alerts --export-bundle ./dead_drop_alerts_export.zip
python3 collector_hub/receiver_hub.py --verify-bundle ./dead_drop_alerts_export.zip

# 3. Provision Unique Production Ed25519 Node Keys & Fast-Boot Service on Raspberry Pi 5:
python3 pi5_sender_node/generate_keys.py CAMERA-NORTH-01
sudo bash pi5_sender_node/install_pi5_fastboot.sh CAMERA-NORTH-01

# 4. Run Stage 5 -18 °C Freezer Soak Acceptance Audit:
python3 run_freezer_soak_acceptance.py --self-test
python3 run_freezer_soak_acceptance.py --journal-dir ./verified_alerts --max-temp-c -10.0 --min-frames 5
```

