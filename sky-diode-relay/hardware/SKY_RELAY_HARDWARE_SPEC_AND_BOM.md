# Sky-Diode-Relay Hardware Specification, Ordered DigiKey BOM & Zero-Solder Assembly Guide

> [!IMPORTANT]
> **ORDERED PRODUCTION HARDWARE BASELINE (`Build D`):**
> Following 5 engineering iterations and the [Design Evolution & Stability Audit](../docs/DESIGN_EVOLUTION_AND_STABILITY_RECORD.md), **`Build D` (`200 m – 20 km` All-Weather `2.4 GHz` Troposcatter, Hydrometeor & Canopy-Bounce Relay)** is the primary ordered hardware configuration (**`1 Complete TX + RX Link Pair`** — `10 BOM SKUs / 20 individual part pieces total`, **`$1,341.94` parts subtotal**).
> * **Zero Soldering Required:** Every module is a pre-assembled, factory-tested evaluation board (`Analog Devices`, `Skyworks`, `Mini-Circuits`, `L-com`, `TDK-Lambda`, `Raspberry Pi`, `Hammond`) that connects via standard `SMA` coaxial jumpers and screw terminals in **`~35–45 minutes total`**.
> * **100% Non-Chinese Manufacturer Origin:** Every single component is manufactured by vetted US, UK, Japanese, or Canadian manufacturers.
> * **⚠️ RF Regulatory Disclaimer (Traficom / EU ETSI EN 300 328) & `--civilian-eu-compliant` Mode:**
>   * **Licensed / Test-Permit / Amateur Radio / Emergency Mode (Default):** Operating `Build D` with the `1.0 W` (`+30 dBm`) `SE2576L-EK1` PA into the `14 dBi` `HG2414P` panel antenna (`+42.5 dBm` / `17.8 W` EIRP) or hopping into out-of-ISM guard bands (`2370–2400 MHz` & `2483.5–2500 MHz`) **requires a Traficom experimental/test radio license, authority authorization, or Amateur Radio permit (`13 cm` band, `2300–2450 MHz`)**.
>   * **Peacetime License-Exempt Civilian Mode (`--civilian-eu-compliant`, Zero Hardware Changes):** Passing `--civilian-eu-compliant` (`civilian_eu_compliant=True`) in software restricts all FHSS carrier hops strictly inside **`2400.0–2483.5 MHz`** (`2402–2480 MHz`), keeps `Pico 2 GP3 = LOW` (disabling/bypassing the `1.0 W` PA), and sets `ADALM-PLUTO` TX output to `+7.5 dBm` so total radiated power is capped at **`<= +20.0 dBm` (`100 mW` EIRP)** under **Traficom Regulation 15 / EU ETSI EN 300 328**, while `VK7MO`'s `+55.8 dB` coherent processing gain still bridges multi-kilometer NLOS forest paths.
> * **Optical Reference Architectures (`Builds A, B, and C`):** Retained in Section 4 below for strictly zero-RF (`0.00 W`) optical line-of-sight or clear-weather cloud-bounce research.

![Build D Transmitter: 200 m Setback + 2.4 GHz Directional Launch](../docs/images/sky_diode_beam_system_in_context.jpg)

![Build D Receiver: Filtering, Low-Noise Amplification, Coherent Integration](../docs/images/sky_relay_20km_troposcatter_blueprint.png)

---

## 1. Ordered `Build D` Complete 2-Node Bill of Materials (`1 TX Node + 1 RX Node`)

| Line | DigiKey Part # | Manufacturer Part # | Manufacturer & Origin | Component Role & Technical Specification | Qty | Unit Price | Line Total |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **1** | `2648-SC1632-ND` | **`SC1632`** | **Raspberry Pi** *(UK)* | **Pico 2 H (`RP2350` Dual Cortex-M33 @ `150 MHz`)** with pre-soldered headers (1× TX node, 1× RX node) | **2** | `$6.00` | **`$12.00`** |
| **2** | `HM600-ND` | **`1590Z120`** | **Hammond Mfg.** *(Canada)* | **Heavy-Duty `IP66` Cast Aluminum RF Shield Enclosure** (`125 × 80 × 57 mm`, EMI gasketed lid) | **2** | `$36.43` | **`$72.86`** |
| **3** | `285-1824-ND` | **`LS50-5`** | **TDK-Lambda** *(Japan)* | **`5.0V DC`, `10A` (`50W`) Enclosed Industrial Power Supply** (low-ripple regulated `5V` rail for PA, LNA & SDR) | **2** | `$41.85` | **`$83.70`** |
| **4** | `505-ADALM-PLUTO-ND` | **`ADALM-PLUTO`** | **Analog Devices** *(USA)* | **`AD9363` `70 MHz – 6.0 GHz` SDR Transceiver** (`12-bit` IQ, agile `2370–2500 MHz` synthesized LO, `SMA` TX/RX) | **2** | `$253.32` | **`$506.64`** |
| **5** | `863-1328-ND` | **`SKY65405-21EK1`** | **Skyworks Solutions** *(USA)* | **Receiver `2.4 GHz` Ultra-Low-Noise Amplifier (LNA) Eval Board** (`1.2 dB` Noise Figure, `+15 dB` gain, `+29 dBm` OIP3, `SMA`) | **1** | `$108.93` | **`$108.93`** |
| **6** | `863-1436-ND` | **`SE2576L-EK1`** | **Skyworks Solutions** *(USA)* | **Transmitter `2.4 GHz` `1.0 W` (`+30 dBm`) Power Amplifier Eval Board** (`33 dB` gain, `5.0V` supply, `SMA` I/O) | **1** | `$108.93` | **`$108.93`** |
| **7** | `3157-VBF-2435+-ND` | **`VBF-2435+`** | **Mini-Circuits** *(USA)* | **Coaxial `2370–2500 MHz` Bandpass Filter** (`SMA-Male` to `SMA-Female`, `>40 dB` out-of-band jammer rejection, `10W` power handling) | **2** | `$57.50` | **`$115.00`** |
| **8** | `5073-HG2414P-ND` | **`HG2414P`** | **L-com** *(USA)* | **`14.0 dBi` `2.4 GHz` Outdoor Weatherproof Flat-Panel Antenna** (`30° × 30°` beam, UV-stable radome, pole bracket, `N-Female`) | **2** | `$111.25` | **`$222.50`** |
| **9** | `J3712-ND` | **`415-0029-012`** | **Cinch / Johnson** *(USA)* | **Precision `12"` (`305 mm`) Double-Shielded `RG-142` PTFE Coax Jumpers** (`SMA-Male` to `SMA-Male`, gold-plated brass) | **4** | `$20.76` | **`$83.04`** |
| **10** | `ACX1345-ND` | **`242125`** | **Amphenol RF** *(USA)* | **Precision `N-Male` to `SMA-Female` Straight RF Adapters** (`50 Ω`, mates `HG2414P` `N-Female` port to `SMA` coax) | **2** | `$14.17` | **`$28.34`** |
| — | **ORDER TOTAL** | **`10 BOM SKUs`** | **100% In Stock (`20 Individual Part Pieces`)** | **1 Complete TX + RX Link Pair (`$1,341.94` Subtotal)** | **20 pcs** | — | **`$1,341.94`** |

---

## 2. How Long Does It Take to Assemble? (`~35–45 Minutes Total`, Zero Soldering)

Because every RF component uses threaded `SMA` / `Type-N` coaxial connectors and pre-built evaluation boards, assembling both nodes takes **`35 to 45 minutes total`**:

| Assembly Phase | Time Required | What You Do |
| :--- | :---: | :--- |
| **Phase 1: Transmitter (`TX`) Node RF & Power Assembly** | **`~15 minutes`** | 1. Screw 1× `Amphenol 242125` (`N-Male` to `SMA-Female`) adapter into the back of the TX `L-com HG2414P` panel antenna (`1 min`).<br>2. Thread 1× `Mini-Circuits VBF-2435+` bandpass filter directly onto the output of the `Skyworks SE2576L-EK1` `1W` PA board (`1 min`).<br>3. Connect `ADALM-PLUTO #1 TX` $\rightarrow$ `SE2576L-EK1 RFIN` using `RG-142 SMA Jumper #1`, and `VBF-2435+ OUT` $\rightarrow$ `HG2414P Antenna` using `RG-142 SMA Jumper #2` (`3 min`).<br>4. Connect `+5.0V` and `GND` from `TDK-Lambda LS50-5 #1` screw terminals to `SE2576L-EK1 VCC` (`+5.0V` collector rail only) and `Pico 2 H #1 VSYS` (`Pin 39`). Wire `SE2576L-EK1 PA_EN` (`C0`/`C1` logic enable, **`3.6 V` absolute max — NEVER `+5.0V`!**) strictly to **`Pico 2 H #1 GP3` (`Pin 5`, `3.3 V` logic)**, and place the PA + filter inside the `Hammond 1590Z120 #1` cast-aluminum shield box (`10 min`). |
| **Phase 2: Receiver (`RX`) Node RF & Power Assembly** | **`~15 minutes`** | 1. Screw 1× `Amphenol 242125` (`N-Male` to `SMA-Female`) adapter into the back of the RX `L-com HG2414P` panel antenna (`1 min`).<br>2. Thread 1× `Mini-Circuits VBF-2435+` bandpass filter **directly onto the input** (`RFIN`) of the `Skyworks SKY65405-21EK1` LNA board so out-of-band signals are blocked before the LNA (`1 min`).<br>3. Connect `HG2414P Antenna` $\rightarrow$ `VBF-2435+ IN` using `RG-142 SMA Jumper #3`, and `SKY65405-21EK1 RFOUT` $\rightarrow$ `ADALM-PLUTO #2 RX` using `RG-142 SMA Jumper #4` (`3 min`).<br>4. Connect `+5.0V` and `GND` from `TDK-Lambda LS50-5 #2` screw terminals to `SKY65405-21EK1 VDD` (`+5.0V` supply rail only) and `Pico 2 H #2 VSYS` (`Pin 39`). Wire `SKY65405-21EK1 VEN` (LNA active-bias enable, **`2.8 V` nominal / `3.5 V` max — NEVER `+5.0V`!**) strictly to **`Pico 2 H #2 3V3_OUT` (`Pin 36`, `3.3 V` regulated rail)**, and place the filter + LNA inside `Hammond 1590Z120 #2` (`10 min`). |
| **Phase 3: USB Connection & Software Self-Test** | **`~10 minutes`** | Plug the USB cables of `ADALM-PLUTO #1/#2` and `Pico 2 H #1/#2` into the sender and collector hosts, run `python3 -B sky-diode-relay/tests/test_sky_relay_simulation.py`, and verify the first `SKFG` frame lock. |
| **Total Build Time (Both Nodes)** | **`35 – 45 minutes`** | **100% plug-and-play coaxial & screw-terminal assembly.** |

> [!CAUTION]
> **Two Golden Rules Before Applying `+5.0V` Power (`SE2576L-EK1` & `SKY65405-21EK1`):**
> 1. **Always Connect the `50 Ω` Antenna Load First:** Screw the `HG2414P` antenna (or a `50 Ω` load) onto the `SE2576L-EK1` output **before** turning on the `LS50-5` `+5.0V` supply or asserting `PA_EN`. Never fire a `+30 dBm` (`1 W`) RF power amplifier into an open, disconnected `SMA` jack.
> 2. **`PA_EN` (`C0`/`C1`) and `VEN` Are `3.3 V` Logic Pins (`3.6 V` Max — NEVER Connect to `+5.0 V`!):** On the `Skyworks SE2576L-EK1` PA, only the main `VCC` rail takes `+5.0 V`; its logic enable pins (`PA_EN` / `C0` & `C1`, datasheet `1.8–3.3 V` operating, `3.6 V` abs max) MUST be driven from **`Pico 2 H #1 GP3` (`3.3 V` GPIO)**. Likewise, on the `Skyworks SKY65405-21EK1` LNA, `VDD` takes `+5.0 V`, while `VEN` (`2.8 V` typ / `3.5 V` max) MUST be wired to **`Pico 2 H #2 Pin 36` (`3V3_OUT`, `3.3 V`)**. Tying `PA_EN` or `VEN` directly to `+5.0 V` will permanently damage the CMOS bias controller.

---

## 3. Exact Coaxial & DC Pinout Schedule (`Build D`)

### 3.1 Transmitter (`TX`) Chain (`+42.5 dBm` EIRP across `2380 / 2488 / 2459 MHz`)
```
[Raspberry Pi 5 / Pico 2 H #1 (SC1632)]
       │ • USB / UART (SKFG FEC + Keyed-FHSS Schedule: 2380.373 / 2487.818 / 2459.116 MHz)
       │ • Pico 2 H #1 GP3 (Pin 5, 3.3V CMOS Logic) ──► SE2576L-EK1 PA_EN (C0/C1, 3.6V Max — NEVER +5.0V!)
       ▼
[Analog Devices ADALM-PLUTO #1] ──(TX Out: +2.0 dBm Licensed / +7.5 dBm Civilian, SMA-F)
       │
       │ Cinch Johnson 415-0029-012 (12" RG-142 SMA-M to SMA-M Jumper #1)
       ▼
[Skyworks SE2576L-EK1 1W PA] ──(VCC: +5.0V from LS50-5 #1 | PA_EN: 3.3V from Pico 2 GP3 | GND: Common GND)
       │ RFOUT (+30.0 dBm / 1.0 W, SMA-F)
       ▼ (Direct SMA-M to SMA-F Thread)
[Mini-Circuits VBF-2435+ Bandpass Filter (2370–2500 MHz)]
       │ Filter Out (+29.5 dBm, SMA-F)
       │
       │ Cinch Johnson 415-0029-012 (12" RG-142 SMA-M to SMA-M Jumper #2)
       ▼
[Amphenol RF 242125 (SMA-F to N-Male Adapter #1)]
       │
       ▼
[L-com HG2414P 14.0 dBi Outdoor Flat Patch Panel Antenna #1] ──► +42.5 dBm EIRP (30° × 30° Beam, +2° Tilt)
```

### 3.2 Receiver (`RX`) Chain (`1.2 dB` Noise Figure, `+55.8 dB` Coherent Lock-In Gain)
```
[L-com HG2414P 14.0 dBi Outdoor Flat Patch Panel Antenna #2] ◄── 200 m – 20 km Troposcatter / Canopy Bounce
       │
       ▼
[Amphenol RF 242125 (N-Male to SMA-F Adapter #2)]
       │
       │ Cinch Johnson 415-0029-012 (12" RG-142 SMA-M to SMA-M Jumper #3)
       ▼
[Mini-Circuits VBF-2435+ Bandpass Filter (2370–2500 MHz)] ──(Blocks Out-of-Band Jammers BEFORE LNA!)
       │ Filter Out (SMA-M)
       ▼ (Direct SMA-M to SMA-F Thread)
[Skyworks SKY65405-21EK1 Ultra-Low-Noise Amplifier] ──(VDD: +5.0V from LS50-5 #2 | VEN: 3.3V from Pico 2 Pin 36 3V3_OUT — NEVER +5.0V!)
       │ RFOUT (+15.0 dB Gain, 1.2 dB NF, +29 dBm OIP3)
       │
       │ Cinch Johnson 415-0029-012 (12" RG-142 SMA-M to SMA-M Jumper #4)
       ▼
[Analog Devices ADALM-PLUTO #2 (RX SMA-F)]
       │ USB IQ Stream
       ▼
[Receiver Host + Pico 2 H #2] ──► Barrage-Rejecting VK7MO Lock-In + 2D Costas + Hamming(8,4) ──► receiver_hub.py
```

---

## 4. Alternative Zero-RF Optical Reference Architectures (`Builds A, B, and C`)

For specialized sites requiring strictly **`0.00 W` RF emissions** along the entire backhaul path, the `sky-diode-relay` software stack (`transmitter/sky_transmitter.py` and `receiver/sky_receiver.py`) also supports three optical reference builds:
* **Build A (`100 m – 2.5 km` Line-of-Sight / Treetop-Mirror FSO):** Thorlabs `L1550P5DFB` (`1550 nm` eye-safe Class 1 DFB laser) + Texas Instruments `LMG1020EVM-006` driver + Thorlabs `LA1951-C` (`25.4 mm`) TX lens $\rightarrow$ Thorlabs `LA1433-C` (`50.8 mm`) RX lens + `FBH1550-12` (`12 nm` bandpass filter) + `APD430C` InGaAs APD.
* **Build B (`50 m – 300 m` Over-the-Trees Solar-Blind UV-C NLOS):** `265 nm` AlGaN UV-C LED array (`60 mW`) + Hamamatsu `R7154` / `H11901-110` solar-blind Cs-Te PMT (`0.00 Hz` daytime solar background below the stratospheric ozone cutoff).
* **Build C (`20 km` Clear-to-Overcast Optical Cloud-Bounce with `VK7MO` Lock-In):** `1550 nm` `2.0 W` fiber-coupled laser diode + `50 mm` collimator + `100 mm` Fresnel receiver aperture + `Thorlabs PDA20CS2` InGaAs detector running the `VK7MO` coherent lock-in integration engine (operates in clear and overcast weather; limited by heavy fog/snow optical extinction as documented in [`DESIGN_EVOLUTION_AND_STABILITY_RECORD.md`](../docs/DESIGN_EVOLUTION_AND_STABILITY_RECORD.md)).
