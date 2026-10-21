# Arctic Trail Cam System

> **Open-source, RF-silent Arctic trail & cabin camera with a 1-way optical fiber diode and `<4mW` cold-boot gatekeeper. A private, pro-bono free-market COTS build. 🇫🇮 Finnish engineering.**
>
> * **GitHub Topics:** `raspberry-pi-5` · `rp2350` · `pico-2` · `trail-camera` · `data-diode` · `fiber-optics` · `edge-ai` · `hailo-8l` · `ed25519` · `open-hardware` · `arctic-engineering` · `cots`
> * **Visual Architecture & Engineering Overview (27-Slide PDF Deck):** [`ARCTIC_TRAIL_CAM_EXECUTIVE_OVERVIEW.pdf`](ARCTIC_TRAIL_CAM_EXECUTIVE_OVERVIEW.pdf)
> * **Complete Illustrated IKEA-Style Build Manual (PDF Booklet):** [`ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf`](ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf)
> * **Sister Project (Autonomous Wilderness Search-and-Rescue Drone & Digital Hut Guide):** [`arctic-trail/karhunkierros-sar-drone`](https://github.com/arctic-trail/karhunkierros-sar-drone)
> * **License:** [`MIT License`](LICENSE)

> [!WARNING]
> **PROTOTYPE DISCLAIMER — ACTIVE DEVELOPMENT & BENCHTOP TESTING IN PROGRESS (`v0.9-beta`)**
> * **Under Active Development:** This repository is an **experimental proof-of-concept hardware & software engineering prototype** currently undergoing physical benchtop integration and staged validation.
> * **Validated vs. Target Metrics:** All software/firmware state machines (`Pico 2` Gatekeeper, `Pi 5` sender node, `Ed25519` + `1×2` optical diode UDP pipeline, and `5/5` automated simulation & DRC test suites) are implemented and verified in simulation and Stage 1–3 benchtop bring-up. System performance figures—including the **`6.4–6.8 s` cold-boot latency** (`<150 ms` with SPI Instant-Snap buffer) and **`1.0 to 2.5+ year` (`365–900+ day`) battery life** (at a realistic `10 captures/month` with a drop-in `LiFePO4` / AGM battery, or `4–10+ months` on busy `10 captures/day` trails)—are **engineering design targets and theoretical power/link-budget projections** currently undergoing physical measurement.
> * **Ongoing Defect Tracking & Field Reports:** Hardware, firmware, and mechanical defects discovered during benchtop and outdoor trials are actively being fixed. Measured real-world latency logs, false-alarm soak results, and battery discharge telemetry will be published here as testing progresses.

An off-grid, event-triggered movement-detection and trail camera system (**Arctic Trail Cam System** / `pi-diode-trailcam` & `sky-diode-relay`) designed for remote cabins, hunting grounds, and private forest lands far from internet or cellular coverage. Engineered for year-round operation in harsh Finnish Arctic conditions (`-40°C` to `+50°C`), the system combines milliwatt standby sensing (`Raspberry Pi Pico 2` Gatekeeper), 6-second cold-boot AI vision (`Raspberry Pi 5` + `Sony IMX708 NoIR`), and **physics-enforced one-way optical transmission** (`Ed25519`-signed `1080p` JPEGs sent over `3 mm` moss-buried armored glass fiber or an invisible infrared light beam) with **zero radio emissions (`0.00 W RF`)** at the camera tree.

> [!IMPORTANT]
> **Project Ethos — Private, Pro-Bono Free-Market Engineering ([`MIT License`](LICENSE)):**
> Rather than relying on `$15,000+` proprietary defense sensors or cloud-tethered cellular cameras that broadcast detectable radio beacons and die in freezing `-30°C` winters, this project explores how **standard commercial off-the-shelf (COTS) components (`$233.37` benchtop / `$598.20` complete turnkey field system including all power supplies, USB/SD adapters, and Cat6/fiber cables)** can be assembled by any cabin owner, hunter, landowner, or researcher:
> 1. **100% Retail COTS Supply Chain:** Built from standard parts on Amazon, Adafruit, DigiKey, Mouser, or Motonet/Verkkokauppa.com in Finland.
> 2. **Zero Cloud Subscriptions & Zero Radio Signature:** No monthly fees, no cellular SIM cards, and zero Wi-Fi/Bluetooth beacons.
> 3. **"IKEA-Simple" Reproducibility:** Every breadboard hole, jumper wire, and enclosure hole-saw cut is illustrated step by step.
> 4. **Single-Source-of-Truth (`SSOT`) Documentation:** Each guide in this repository owns one distinct topic without duplicating tables or instructions across files (see [Documentation Map](#single-source-of-truth-ssot-documentation-map) below).

---

## 1. System Performance & Battery Life Expectations (At a Glance)

Detailed seasonal power models and component-level current draws are maintained in **[`HARDWARE_SPECS_AND_BOM.md`](pi-diode-trailcam/docs/HARDWARE_SPECS_AND_BOM.md#1-system-performance-expectations--cold-boot-latency-spec)**.

| Performance Parameter | Verified / Target Specification | Operating Context |
| :--- | :--- | :--- |
| **Multi-Year Battery Life (Drop-In `12V 15Ah–24Ah` `LiFePO4` / `60Ah` External)** | **At `10 Photos/Month` *(Realistic Cabin / Border Trail)*:**<br>• **`1.5 – 2.5+ Years` (`565 – 900+ Days`)** *(Drop-In `15Ah–24Ah LiFePO4` inside vault)*<br>• **`3.0 – 4.0+ Years`** *(External `60Ah` Battery — self-discharge limited)*<br>**At `10 Photos/Day` (`300/Month` *High-Traffic Trail*):**<br>• **`10 – 16+ Months`** *(`15Ah–24Ah LiFePO4`)* / **`1.8 – 2.5+ Years`** *(`60Ah`)* | At `10 photos/month` (`0.33/day`), active capture energy is negligible (`~0.01 Wh/day`), so total draw with `4–12 mW` Eco Gatekeeper standby is just `~0.15–0.30 Wh/day`. |
| **Battery Life (Standard `12V 12Ah` AGM `[P17]`, `$29` / `€27`)** | **At `10 Photos/Month`:** **`1.0 – 1.3+ Years` (`365 – 480 Days`)** *(3-Season)* / **`9 – 12 Months` (`270 – 365 Days`)** *(Finnish Winter under moss)*<br>**At `10 Photos/Day`:** **`120 – 220+ Days`** | Included baseline `12V 12Ah` sealed AGM battery (`[P17]`) mounted inside the moss-buried `QILIPSU` Base Vault (`[P21]`). |
| **Standby Power (`Domain A` Always-On)** | **`3.8 mW – 12.0 mW`** *(Eco Gatekeeper)* / **`~38 mW`** *(Radar Micro-Sweep)* | `Raspberry Pi 5 [P01]` and `StarTech Fiber Converter [P13]` are **100% physically powered off (`0.00 W`)** by the high-side relay `99.9%` of the time. |
| **Cold-Boot Trigger-to-Photo Latency** | **`6.4 – 6.8 seconds` total** (`0.025 Wh` per capture) | `Pico 2` switches on `Domain B` $\rightarrow$ `Pi 5` boots stripped Linux kernel in `3.8s` $\rightarrow$ captures `1080p` JPEG $\rightarrow$ runs AI detection $\rightarrow$ signs (`Ed25519`) & blasts `3×` over optical fiber $\rightarrow$ cuts power back to `0.00 W`. |
| **Operating Temperature & Weatherproofing** | **`-40°C` to `+50°C` Year-Round (`IP67` / `IP68`)** | Moss-buried `QILIPSU` vault buffers battery at `-2°C to -8°C` in deep winter; `3.6W` PTC window heater clears lens frost in `4.0s`. |
| **Detection & Night-Vision Range** | **`15 m – 60 m` approach** (`25°` oblique trail aim)<br>**`8 m – 18 m` night IR** (`940 nm` invisible LEDs, zero red glow) | 3-stage wake cascade (`QMC5883L` magnetometer + `HLK-LD2450` `24 GHz` radar behind solid ABS + optional `SM-24` geophone). |
| **Link Reach (`Fiber`, `Collimator`, or `Sky-Relay`)** | **`30 m – 10 km`** *(Moss-Buried Armored OS2 Glass Fiber)*<br>**`10 m – 100 m`** *(Water-Strait `1310 nm` Collimator Laser Bridge)*<br>**`200 m – 20 km`** *(All-Weather `2.4 GHz` Troposcatter & Canopy-Bounce Relay — [`sky-diode-relay`](sky-diode-relay/README.md) `Build D`)* | Physical one-way optical data diode (`1×2` optical splitter loopback trick at camera; cabin receiver `TX` port physically unpatched and capped) or one-way `VK7MO` Keyed-FHSS Troposcatter (`+14.1 dB` to `+62.3 dB` all-weather SNR). |

---

## 2. Device in Context: 3-Zone Pine Tree Unit & `200 m – 20 km` Troposcatter / Beam Relay

Detailed exterior/interior cutaway plates for **Device 1 (`Zone 1` Camera/Radar Pod)**, **Device 2 (`Zone 3` Base Vault)**, **Device 3 (Cabin & Woods Collectors)**, and the **Scenario A / B1 / B2 / B3** deployment comparison are included in **[`ASSEMBLY_GUIDE.md`](pi-diode-trailcam/docs/ASSEMBLY_GUIDE.md)**.

### 2.1 The 3-Zone Covert Split-Pod Camera Unit on a Forest Pine Tree
![Complete Landscape Architecture: Sense at the Tree, Decide at the Roots, Deliver One Way](pi-diode-trailcam/docs/images/product_units_in_context.jpg)

![Three-Zone Tree Cutaway: A Small Eye Up High, the Heavy Parts Buried Below](pi-diode-trailcam/docs/images/slide_three_zone_tree_cutaway.jpg)

![Sensor Roles: Three Clues, One Decision to Wake the Camera](pi-diode-trailcam/docs/images/slide_sensor_wake_cascade.jpg)

![Capture and Local AI: Only Confirmed Detections Leave the Tree](pi-diode-trailcam/docs/images/slide_local_ai_pipeline.jpg)

* **Zone 1 (Top — `2.0 m` High in Pine Bark Crevice):** Fist-sized `Hammond 1591BSBK` (`112 × 62 × 31 mm`, factory `IP54` sealed with a perimeter `Permatex 81158` lid-channel gasket, or drop-in `Hammond 1554EGY` factory `IP68`) pod with **only one circular `20 mm` (`[T06]` cone step bit) or `28 mm` (`[T05]` hole saw) glass window** (`IMX708` camera locked to `AfMode=0, LensPosition=0.5` hyperfocal focus + black neoprene foam anti-glare baffle + `2× 940 nm` stealth IR LEDs + `39-Ohm 5W` [`3.69 W` @ `12V`] de-icer) and an internal `HLK-LD2450` `24 GHz` radar shooting cleanly through the solid, uncut lower ABS wall.
* **Zone 2 (Middle — `2.0 m` Trunk Cord):** Shielded `Arducam CSI-to-HDMI` (`2.0 m`) + 4-wire radar/heater umbilical wrapped in `Gear Aid Camo Form` matte bark tape tucked into a natural vertical bark groove.
* **Zone 3 (Bottom — Buried `20–30 cm` Underground & Foam-Insulated at Tree Roots):** Waterproof `QILIPSU IP67` (`285 × 195 × 130 mm`) vault housing the wall-to-wall `12V 12Ah` battery (`[P17]`), `Pico 2` Gatekeeper (`[P07]`), `5V` buck/relay power switches (`[P12]`), `Raspberry Pi 5` (`[P01]`), and `1310 nm` `StarTech` Media Converter + `1×2` Optical Splitter Diode (`[P13]`–`[P15]`).
  * **Cold-Weather Survival WITH vs. WITHOUT Underground Burial & Foam Insulation:** The tree-mounted **Zone 1 Micro-Pod** contains only solid-state silicon + the `3.69 W` ceramic window de-icer (`[P12-HEAT]`) and operates in open air down to **`-35°C to -40°C`**. For the **Zone 3 Base Vault**: **WITHOUT underground burial or foam insulation** (sitting above ground in open air with standard `12Ah` AGM `[P17]`), reliable operation is limited to **`-15°C to -20°C`** (`45%–55%` battery capacity; risk of `Pi 5` boot brownout or electrolyte freeze below `-22°C`, or **`-25°C to -28°C`** if fitted with the `10–20 mm` foam liner + `[P21-FROST]` supercap buffer on bare rock). **WITH `20–30 cm` underground burial + `10–20 mm` closed-cell XPS/neoprene foam insulation + moss/snow cover**, geothermal subsoil warmth keeps the internal battery bay at **`-2°C to -8°C`** even when outside air plunges to **`-35°C to -40°C`** (**`-45°C`** under `30+ cm` snowpack), preserving **`85%–92%` battery capacity** (`1.2–2.5+ years` with `LiFePO4`).

### 2.2 The `200 m – 20 km` Non-Line-of-Sight Troposcatter & Water-Crossing Beam System ([`sky-diode-relay`](sky-diode-relay/README.md))
![Build D Transmitter: 200 m Setback + 2.4 GHz Directional Launch](sky-diode-relay/docs/images/sky_diode_beam_system_in_context.jpg)

![Build D Receiver: Filtering, Low-Noise Amplification, Coherent Integration](sky-diode-relay/docs/images/sky_relay_20km_troposcatter_blueprint.png)

* **Ordered Production Baseline (`Build D` — `200 m to 20 km` All-Weather `2.4 GHz` Troposcatter, Hydrometeor & Canopy-Bounce Relay, `$1,341.94` parts subtotal, `~35–45 min` zero-solder assembly):** Uses **Analog Devices `ADALM-PLUTO` SDRs**, a **Skyworks `SE2576L-EK1` `1.0 W` (`+30 dBm`) PA (`PA_EN` driven strictly at `3.3 V` from `Pico 2 GP3`)**, a **Skyworks `SKY65405-21EK1` (`1.2 dB NF`) LNA (`VEN` driven strictly at `3.3 V` from `Pico 2 3V3_OUT`)**, **Mini-Circuits `VBF-2435+` (`2370–2500 MHz`) coaxial bandpass filters**, and **L-com `HG2414P` (`14 dBi`) outdoor flat-panel antennas** to bounce `VK7MO` coherent lock-in frames (`+55.8 dB` processing gain) off lower-troposphere refractivity gradients, rain/snow clouds, and forest canopies over granite hills (`+14.1 dB` to `+62.3 dB` SNR across all 5 Finnish weather regimes). Protected by a **6-layer electronic anti-jamming stack** that hops into out-of-ISM guard bands (`2380.373 MHz` & `2487.818 MHz`) outside consumer Wi-Fi/drone jammers.
  * **⚠️ Regulatory Disclaimer & `--civilian-eu-compliant` Software Flag (Zero Hardware Changes):** Operating `Build D` at full `1.0 W` (`+42.5 dBm` / `17.8 W` EIRP) or hopping into out-of-ISM guard bands (`2370–2400 MHz` / `2483.5–2500 MHz`) **requires a Traficom experimental/test radio license, defence/border authority authorization, or Amateur Radio permit (`13 cm` band, `2300–2450 MHz`)**. For **license-exempt peacetime civilian operation** under Traficom Regulation 15 / EU ETSI EN 300 328, pass **`--civilian-eu-compliant`** (`civilian_eu_compliant=True`) to `sky_transmitter.py` and `sky_receiver.py`: this restricts all FHSS carrier hops strictly inside **`2400.0–2483.5 MHz`** (`2402–2480 MHz`) and disables/attenuates the PA (`pa_gate_gp3=0`, `+7.5 dBm` SDR output) so total radiated power is capped at **`<= +20.0 dBm` (`100 mW` EIRP)** while still bridging multi-kilometer NLOS forest paths via `VK7MO`'s `+55.8 dB` coherent processing gain.
* **Short-Range Optical Beam (`Scenario B2` — `10 m to 100 m` Across a Lake Strait or Road):** Two shore-mounted `1310 nm` fiber lens collimators (**Thorlabs `F220FC-1310`**) convert the fiber signal into a pencil-thin, invisible infrared laser beam across water channels where boats or winter ice prevent laying cable (with optical reference builds `A/B/C` also supported in [`sky-diode-relay`](sky-diode-relay/README.md)).

### 2.3 The Cabin Collector Hub & 3D Evidence Console ([`dashboard_server.py`](pi-diode-trailcam/collector_hub/dashboard_server.py) / [`ui/index.html`](pi-diode-trailcam/collector_hub/ui/index.html))
![Arctic Trail Cam Collector Hub & 3D Evidence Console UI](pi-diode-trailcam/docs/images/collector_hub_command_center_ui.png)

* **100% Offline Local Browser Console (`http://localhost:8080` / `8123`):** Streams `Ed25519`-verified JPEGs (`DD\x02` chunks), AI bounding boxes (`Hailo-8L` / `YOLOv8n ONNX`), `<150 ms` `Pico 2` SPI First-Frame Instant-Snap PIP insets, and 6-cell `Pico 2` sensor telemetry (`MAG ΔB`, `SEISMIC RMS`, `RADAR DIST/SPD`, `NODE TEMP`, `UPTIME`, `PROFILE`) alongside an interactive 3D topographical terrain map (`Nuuksio`, `Saimaa Archipelago`, `Koli`, `Inari Lapland`, or custom `GeoJSON`/`DEM`) and real-time 4-channel sensor waveforms.

---

## 3. Build Cost Tiers (`$233` to `$598`) & Step-by-Step IKEA Manuals

The complete itemized parts schedule (`[P01]`–`[P24]`), workshop tool list (`[T01]`–`[T12]`), and 5-hole enclosure drilling table live exclusively in **[`HARDWARE_SPECS_AND_BOM.md`](pi-diode-trailcam/docs/HARDWARE_SPECS_AND_BOM.md)**.

| Build Tier | Parts Included | Total (USD) | Approx. (EUR) | Where to Start |
| :--- | :--- | :---: | :---: | :--- |
| **Tier 1A — Indoor Core Benchtop Kit (`Stages 1–2`)** | `[P01]`, `[P02]`, `[P04]`–`[P10]`, `[P23]`, `[P24]` | **`$233.37`** | **`~€215`** | **[IKEA Manual Part 1 (`Stages 1–2`)](pi-diode-trailcam/docs/BENCHTOP_QUICKSTART_GUIDE.md)** |
| **Tier 1B — Indoor Benchtop + Optical Fiber Diode (`Stages 1–3`)** | Tier 1A + `[P13]`–`[P16]`, `[P19]` | **`$402.67`** | **`~€370`** | **[IKEA Manual Part 1 (`Stage 3`)](pi-diode-trailcam/docs/BENCHTOP_QUICKSTART_GUIDE.md#stage-3-snap-together-the-1-way-optical-fiber-data-diode-p13p16-p19)** |
| **Tier 2A — 3-Zone Weatherproof Field Camera Node Only (`Stages 1–6`)** | Field Node `[P01]`–`[P24]` (excl. Cabin RX, `30m` spool & laptop adapter) | **`$497.25`** | **`~€457`** | **[IKEA Manual Part 2 (`Stages 4–5`)](pi-diode-trailcam/docs/ASSEMBLY_GUIDE.md)** |
| **Tier 2B — Complete Turnkey System (`Field Node + 30m Fiber + Cabin RX + All Cables/Adapters`)** | **All `[P01]`–`[P24]` Parts** | **`$598.20`** | **`~€550`** | **[IKEA Manual Part 2 (`Stage 6`)](pi-diode-trailcam/docs/ASSEMBLY_GUIDE.md#stage-6-tree-installation-collector-setup--operating-the-system-in-the-field)** |

![Real-World Stage 2 Benchtop Build — Completed Breadboard Close-Up & Complete Powered System (Photos 57 & 58)](pi-diode-trailcam/docs/images/real_build/stage2_4b_verified_and_step2_5_usb_power_guide_v1.jpg)

---

## 4. Single-Source-of-Truth (`SSOT`) Documentation Map

Every document in this repository owns **one distinct responsibility** with zero duplicated tables:

| Document | Single-Source-of-Truth (`SSOT`) Responsibility |
| :--- | :--- |
| **[`ARCTIC_TRAIL_CAM_EXECUTIVE_OVERVIEW.pdf`](ARCTIC_TRAIL_CAM_EXECUTIVE_OVERVIEW.pdf)** | **27-Slide Visual Architecture & Engineering Overview Deck (PDF):** End-to-end visual walk-through of the 3-zone camera pod, wake cascade, optical diode, `Build D` relay, BOM tiers, and validation roadmap. |
| **[`ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf`](ARCTIC_TRAIL_CAM_BUILD_AND_FIELD_GUIDE.pdf)** | **Illustrated Master Build Booklet** (compiled printable PDF of Stages 1–6 + 1:1 vector drilling templates). |
| **[`HARDWARE_SPECS_AND_BOM.md`](pi-diode-trailcam/docs/HARDWARE_SPECS_AND_BOM.md)** | **Parts (`[P01]`–`[P24]`), Tools (`[T01]`–`[T12]`), Retail Prices, Seasonal Battery Life Models & 5-Hole Drilling Schedule.** |
| **[`BENCHTOP_QUICKSTART_GUIDE.md`](pi-diode-trailcam/docs/BENCHTOP_QUICKSTART_GUIDE.md)** | **IKEA Manual Part 1 (`Stages 1–3`):** Real-photo benchtop assembly (`Photos 1–72`), SD/Pico flashing, breadboard wiring (`W1`–`W7`), and optical diode test. |
| **[`ASSEMBLY_GUIDE.md`](pi-diode-trailcam/docs/ASSEMBLY_GUIDE.md)** | **IKEA Manual Part 2 (`Stages 4–6`):** Enclosure hole-saw drilling, glass sealing, solid matte forest-green painting, `12V` battery wiring, `Device 1–3` cutaways, `Scenario A / B1 / B2 / B3` field topologies & air-shipping guide. |
| **[`WIRING_PINOUT.md`](pi-diode-trailcam/docs/WIRING_PINOUT.md)** | **Electrical Pinout & Voltage Schedule:** Exact GPIO, I2C, UART, ADC, and power-domain pin assignments. |
| **[`pi-diode-trailcam/README.md`](pi-diode-trailcam/README.md)** | **Software CLI & Collector Hub Reference:** `sender_node.py`, `receiver_hub.py`, `dashboard_server.py`, and `generate_keys.py`. |
| **[`FIELD_TESTING_AND_VALIDATION_GUIDE.md`](pi-diode-trailcam/docs/FIELD_TESTING_AND_VALIDATION_GUIDE.md)** | **Field Acceptance Protocol:** 20-walk detection matrix, night `940 nm` zero-glare test, and 48-hour (`192-event`) unattended soak checklist. |
| **[`PROJECT_DECISIONS_AND_ROADMAP.md`](PROJECT_DECISIONS_AND_ROADMAP.md)** | **Architecture Trade-Off Decisions (`Decisions 1–9`) & Codebase Audit Log:** Engineering rationale, field vibration-locking rules, and historical defect remediation record. |
| **[`technical_architecture_engineering_specification.md`](technical_architecture_engineering_specification.md)** | **Wire Protocol & Cryptographic Spec:** Byte-level layout of `DD\x01` telemetry packets, `DD\x02` FEC JPEG chunks, `Ed25519` signatures, and `ChaCha20-Poly1305`. |
| **[`sky-diode-relay/README.md`](sky-diode-relay/README.md)** | **All-Weather `200 m – 20 km` Troposcatter & Optical Relay (`sky-diode-relay`):** Ordered `Build D` (`2.4 GHz` Troposcatter/Canopy-Bounce), 6-layer anti-jamming FHSS lock-in, `Hamming(8,4)` erasure FEC, and [`DESIGN_EVOLUTION_AND_STABILITY_RECORD.md`](sky-diode-relay/docs/DESIGN_EVOLUTION_AND_STABILITY_RECORD.md). |
| **[`arctic-trail/karhunkierros-sar-drone`](https://github.com/arctic-trail/karhunkierros-sar-drone)** | **Sister Project — Autonomous Wilderness SAR Drone & "Digital Wilderness Hut" Guidance System:** Reuses 100% of this camera & collector stack as a passive 48h `0.00 W` RF trail post paired with a GNSS-independent `Holybro X500 V2` aerial lantern rescue drone (`~€1,189–€1,329` COTS). |

---

## 5. Automated Software, Protocol & Channel Simulation Suites

![Software Map: Four Modules From Wake Interrupt to Browser Alert](pi-diode-trailcam/docs/images/slide_software_architecture_map.jpg)

*(Note: These automated suites validate software state machines, `Ed25519` cryptography, durable disk persistence, pagination, and Monte-Carlo channel models in deterministic software simulation; physical hardware acceptance tests are defined in [`FIELD_TESTING_AND_VALIDATION_GUIDE.md`](pi-diode-trailcam/docs/FIELD_TESTING_AND_VALIDATION_GUIDE.md).)*

```bash
# 1. Run the interactive no-hardware benchtop simulation (generates a signed alert + opens live dashboard):
python3 pi-diode-trailcam/run_mock_demo.py

# 2. Run all trailcam unit, firmware, resilience, and quality-assessment regression suites:
python3 pi-diode-trailcam/tests/test_dual_node_simulation.py
python3 pi-diode-trailcam/tests/test_pico_firmware_simulation.py
python3 pi-diode-trailcam/tests/test_enhanced_resilience.py
python3 pi-diode-trailcam/tests/test_quality_assessment_remediations.py

# 3. Run all 24 sky-diode-relay 20km all-weather troposcatter, anti-jamming, civilian-EU mode, and FEC tests:
python3 -B sky-diode-relay/tests/test_sky_relay_simulation.py
```
