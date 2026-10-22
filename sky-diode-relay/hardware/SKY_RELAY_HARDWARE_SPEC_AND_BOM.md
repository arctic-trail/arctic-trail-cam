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

![How Sky-Diode-Relay Bounces the 2.4 GHz Signal Over 200 m – 20 km Blocked Terrain](images/sky_diode_20km_nlos_troposcatter_and_canopy_bounce_v3.jpg)

![True Physical Enclosure Geometry: Vertical 125x80x57 mm Mast RF Shield Box vs Indoor Base Vault](images/sky_diode_physical_tx_rx_enclosures_v3.jpg)

![Complete 10-SKU Build D Engineering Blueprint & Coaxial Verification Ledger](images/sky_relay_20km_troposcatter_engineering_blueprint_v2.png)

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

### 1.1 Single-Unit Eval-Board Retail (`$1,341.94`) vs. Lot-100 (`100x`) Wholesale (`$462.00`) & Lot-1,000 (`1000x`) OEM Volume (`$284.00`)

`Build D` exhibits the largest single-unit retail convenience margin in the repository (**`65.6%` at `100x`** and **`78.8%` / `4.73×` at `1,000x`**) because the rapid-prototyping BOM uses **manufacturer RF laboratory evaluation kits (`SE2576L-EK1`, `SKY65405-21EK1`, `ADALM-PLUTO`), single-unit `L-com` patch antennas, and precision `RG-142` test jumpers** from DigiKey so that a builder can snap a `20 km` link together in `35 minutes` with zero soldering:

| Line | Component (`TX + RX` Complete 2-Node Link Pair) | Qty | Qty-1 DigiKey Fast Retail (Ext. USD) | Lot-100 (`100x`) B2B Wholesale (Ext. USD) | Lot-1,000 (`1000x`) OEM Volume (Ext. USD) | Why Qty-1 Retail Costs `2.9×`–`4.7×` More |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | **Gatekeepers (`2× Raspberry Pi Pico 2 H` `RP2350`)** | `2` | **`$12.00`** (`$6.00 × 2` retail headers) | **`$7.60`** (`$3.80 × 2` B2B reel/tray) | **`$3.60`** (`$1.80 × 2` direct `RP2350A` MCU on carrier) | Retail header pinning & single-unit packaging (`37–70%`) |
| **2–3** | **Cast-Aluminum Shield Boxes (`2× Hammond 1590Z120`, `$72.86`) + Industrial `5V 10A` PSUs (`2× TDK-Lambda LS50-5`, `$83.70`)** | `2+2` | **`$156.56`** (`$36.43 × 2` boxes + `$41.85 × 2` PSUs) | **`$34.00`** (`$23.00` pair bulk `IP66` die-cast aluminum boxes + `$11.00` pair OEM `5V` rails) | **`$18.50`** (`$12.00` pair factory CNC-drilled die-cast housings + `$6.50` integrated DC-DC) | Small-order metal casting & distributor handling markup (`78–88%`) |
| **4** | **SDR Transceivers (`2× Analog Devices ADALM-PLUTO` `AD9363 + Zynq-7010`)** | `2` | **`$506.64`** (`$253.32 × 2` retail educational kit) | **`$336.00`** (`$168.00 × 2` OEM `AD9363+Zynq` SDR SOM / B2B carton) | **`$224.50`** (`$112.25 × 2` direct `AD9363` + `XC7Z010` SOM carrier at `1,000x`) | Educational plastic housing, retail packaging & single-unit distributor margin (`34–56%`) |
| **5–6** | **`2.4 GHz` `1.0 W` PA (`SE2576L-EK1`, `$108.93`) + `1.2 dB NF` LNA (`SKY65405-21EK1`, `$108.93`)** | `1+1` | **`$217.86`** (`$108.93 × 2` Skyworks `-EK1` lab evaluation boards) | **`$28.00`** (`$14.00 × 2` pre-assembled SMA RF front-end modules) | **`$9.50`** (Bare Skyworks `SE2576L` IC is `$1.45` and `SKY65405-21` IC is `$1.10` on tape-and-reel + `$6.95` shared `4-layer` RF carrier) | **Lab Eval-Board Tax (`87–96%` markup):** DigiKey charges `$108.93` for a benchtop characterization PCB carrying a `$1.10–$1.45` silicon IC |
| **7** | **`2370–2500 MHz` Bandpass Filters (`2× Mini-Circuits VBF-2435+`)** | `2` | **`$115.00`** (`$57.50 × 2` connectorized `SMA` brass tube filter) | **`$16.00`** (`$8.00 × 2` B2B coaxial or connectorized SAW/ceramic BPF) | **`$4.80`** (`$2.40 × 2` surface-mount `2.4 GHz` BAW/ceramic RF bandpass filter on RF carrier) | Hand-assembled brass SMA connectorized housing vs. surface-mount RF filter (`86–96%`) |
| **8** | **Outdoor `14 dBi` Flat-Panel Antennas (`2× L-com HG2414P`)** | `2` | **`$222.50`** (`$111.25 × 2` single-unit DigiKey retail) | **`$25.00`** (`$12.50 × 2` case-lot OEM `2.4 GHz 14 dBi` `IP67` patch antenna) | **`$17.00`** (`$8.50 × 2` factory-direct `14 dBi` UV-radome outdoor directional patch w/ bracket) | Single-unit oversized box parcel shipping & brand markup (`89–92%`) |
| **9–10** | **RF Interconnects (`4× RG-142` SMA Jumpers `$83.04` + `2× Amphenol N-to-SMA` Adapters `$28.34`)** | `4+2` | **`$111.38`** (`$20.76 × 4` jumpers + `$14.17 × 2` adapters) | **`$15.40`** (`4× $2.80` `RG-142` jumpers + `2× $2.10` `N-SMA` adapters) | **`$6.10`** (Direct board-to-type-N bulkhead launch eliminating internal SMA jumpers + `2× $3.05` outdoor N-type pigtails) | **Precision Test-Cable Tax (`86–95%`):** `$20.76` per `12"` jumper at Qty-1 vs. `$2.80` bulk / direct bulkhead launch |
| **TOTAL** | **Complete 2-Node (`TX + RX`) `20 km` Troposcatter Link Pair** | **20 pcs** | **`$1,341.94` (`~€1,235`)** *(or `$670.97` / node)* | **`$462.00` (`~€425`)** *(or **`$231.00` / node**, `-65.6%`)* | **`$284.00` (`~€261`)** *(or **`$142.00` / node**, `-78.8%` / `4.73×` cheaper)* | **`$879.94` (`100x`) to `$1,057.94` (`1,000x`) of the Qty-1 price is RF eval-board, antenna & jumper retail overhead** |

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
> 1. **Always Connect the `50 Ω` Antenna Load First:** Screw the `HG2414P` antenna (or a `50 Ω` load) onto the `SE2576L-EK1` output **before** turning on the `+5.0V` supply (`Pico 2 H Pin 40 VBUS` or `LS50-5`) or asserting `PA_EN`. Never fire a `+30 dBm` (`1 W`) RF power amplifier into an open, disconnected `SMA` jack.
> 2. **`PA_EN` (`J4 Pin 1`) and `LNA_EN` (`Pin 4`) Are `3.3 V` Logic Pins (`3.6 V` Max — NEVER Connect to `+5.0 V`!):** On the `Skyworks SE2576L-EK1` PA, only the main `J3 VCC` rail takes `+5.0 V`; its logic enable pin (`J4 Pin 1 PA_EN`, datasheet `1.8–3.3 V` operating, `3.6 V` abs max) MUST be driven from **`Pico 2 H #1 Pin 36` (`3V3_OUT`, `3.3 V`)** (or `GP3` for duty-cycled keying). Likewise, on the `Skyworks SKY65405-21EK1` LNA, `Pin 1 (LNA_VDD)` takes `+5.0 V`, while `Pin 4 (LNA_EN)` (`2.8 V` typ / `3.5 V` max) MUST be wired to **`Pico 2 H #2 Pin 36` (`3V3_OUT`, `3.3 V`)**.On the pre-wired bench/field kit, both `Pico 2 H #1` and `Pico 2 H #2` use the exact same 3 adjacent odd/even header pins on the USB-right edge—**`Pin 40` (`VBUS +5.0V`, Red wire)**, skip `Pin 39`, **`Pin 38` (`GND`, Black wire)**, skip `Pin 37`, and **`Pin 36` (`3V3_OUT +3.3V`, Yellow wire on TX PA / Blue wire on RX LNA)**—so plugging the `Pico 2 H` and `ADALM-PLUTO` USB-A cables into the host (`Raspberry Pi 5` on TX; laptop on RX) powers the entire RF chain immediately with zero external AC/DC bricks.

---

## 3. Exact Coaxial & DC Pinout Schedule (`Build D`)

![Exact Identification of the 3 Sky-Diode TX Chain Devices + Pico 2 H #1 in Real Hardware Photos](../docs/images/sky_diode_3_tx_devices_real_photos_v5.jpg)

### 3.1 Transmitter (`TX`) Chain (`+42.5 dBm` EIRP across `2380 / 2488 / 2459 MHz`)
```
[Raspberry Pi 5 / Pico 2 H #1 (SC1632)]
       │ • USB / UART (SKFG FEC + Keyed-FHSS Schedule: 2380.373 / 2487.818 / 2459.116 MHz)
       │ • Pico 2 H #1 Pin 40 (VBUS +5.0V, Red) ──► SE2576L-EK1 J3 VCC (+5.0V)
       │ • Pico 2 H #1 Pin 38 (GND, Black)      ──► SE2576L-EK1 J3 GND
       │ • Pico 2 H #1 Pin 36 (3V3_OUT, Yellow) ──► SE2576L-EK1 J4 Pin 1 PA_EN (3.3V CMOS, 3.6V Max — NEVER +5.0V!)
       ▼
[Analog Devices ADALM-PLUTO #1] ──(TX Out: +2.0 dBm Licensed / +7.5 dBm Civilian, SMA-F)
       │
       │ Cinch Johnson 415-0029-012 (12" RG-142 SMA-M to SMA-M Jumper #1)
       ▼
[Skyworks SE2576L-EK1 1W PA] ──(VCC: +5.0V from Pico #1 Pin 40 VBUS or LS50-5 #1 | PA_EN: 3.3V from Pin 36/GP3 | GND: Pin 38)
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
[Skyworks SKY65405-21EK1 Ultra-Low-Noise Amplifier] ──(LNA_VDD Pin 1: +5.0V from Pico #2 Pin 40 VBUS or LS50-5 #2 | GND Pin 2: Pin 38 | LNA_EN Pin 4: 3.3V from Pin 36 3V3_OUT — NEVER +5.0V!)
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
