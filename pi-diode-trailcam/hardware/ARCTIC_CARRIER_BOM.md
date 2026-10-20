# Carrier component inventory — unvalidated

This inventory supports the [unreleased carrier study](CARRIER_BOARD_DESIGN_SPEC.md). It is not a manufacturing release. Part limits, footprints, substitutions, reference designators and the complete circuit must be reconciled before procurement. System-level purchasing is maintained in the [system BOM](../docs/HARDWARE_SPECS_AND_BOM.md).

## 1. Active Semiconductors & Integrated Circuits

| Item | RefDes | Description | Manufacturer | Manufacturer Part Number (MPN) | Package | Mouser / Farnell Order No. |
|---|---|---|---|---|---|---|
| 1 | `U1` | Ultra-Low-Quiescent 3.3V LDO Regulator ($I_q = 4\,\mu\text{A}$, 250mA) | Holtek | **HT7333-A** (or TI `TPS7A0233PDBVR`) | SOT-89 / SOT-23-5 | Mouser: `595-TPS7A0233PDBVR` |
| 2 | `U2` | Dual-Core ARM Cortex-M0+ Microcontroller Module (RP2040) | Raspberry Pi | **Raspberry Pi Pico H** | 40-Pin Castellated / DIP | Farnell: `3874378` |
| 3 | `U3` | Automotive 60V 5A Step-Down Buck Converter (>92% Efficiency) | Texas Instruments | **TPS54560BDDAR** | SO-8 PowerPAD | Mouser: `595-TPS54560BDDAR` |
| 4 | `U4` | 16-Bit Low-Power Precision ADC with Internal Reference | Texas Instruments | **ADS1115IDGSR** | VSSOP-10 | Mouser: `595-ADS1115IDGSR` |
| 5 | `Q1, Q3` | P-Channel Enhancement MOSFET ($-20\text{V}$, $-4.2\text{A}$, $R_{\text{DS(on)}} < 52\,\text{m}\Omega$) | Diodes Inc. | **DMG2305UX-7** | SOT-23 | Mouser: `621-DMG2305UX-7` |
| 6 | `Q2A, Q2B`| Dual N-Channel Power MOSFET ($40\text{V}$, $50\text{A}$, $R_{\text{DS(on)}} < 8\,\text{m}\Omega$) | Alpha & Omega | **AOD4184A** (or Onsemi `NTD4906N`) | TO-252 (DPAK) | Mouser: `863-NTD4906NT4G` |
| 7 | `Q4, Q5` | NPN General Purpose Bipolar Transistor ($40\text{V}$, $600\text{mA}$) | Nexperia | **PMBT2222A,215** | SOT-23 | Mouser: `771-PMBT2222A-T/R` |
| 8 | `D1` | 600W Bidirectional Transient Voltage Suppressor (TVS) | Littelfuse | **SMBJ15CA** | SMB (DO-214AA) | Mouser: `576-SMBJ15CA` |
| 9 | `D2..D5` | Low-Capacitance ($3.5\,\text{pF}$) Rail-to-Rail ESD Protection Array | STMicroelectronics | **USBLC6-2SC6** | SOT-23-6 | Mouser: `511-USBLC6-2SC6` |
| 10 | `D6` | 40V 5A Schottky Barrier Rectifier (Freewheeling for Buck) | Vishay | **SS54-E3/57T** | SMC (DO-214AB) | Mouser: `625-SS54-E3` |

---

## 2. Passive Components (Inductors, Capacitors & Resistors)

| Item | RefDes | Value / Description | Manufacturer | Manufacturer Part Number (MPN) | Package | Supplier |
|---|---|---|---|---|---|---|
| 11 | `L1` | $10\,\mu\text{H}$, $6.5\text{A}$ Shielded Power Inductor (Buck Output) | Wurth Elektronik | **744314101** | $10.5 \times 10\,\text{mm}$ | Mouser: `710-744314101` |
| 12 | `C1, C2` | $10\,\mu\text{F}$, $50\text{V}$ X7R Ceramic Capacitor (12V Input) | Murata | **GRM31CR71H106KA12L** | 1206 | Mouser: `81-GRM31CR71H106KA2L` |
| 13 | `C3, C4` | $47\,\mu\text{F}$, $16\text{V}$ X7R Ceramic Capacitor (5V Buck Output) | TDK | **C3216X7R1C476M160AC** | 1206 | Mouser: `810-C3216X7R1C476M` |
| 14 | `C5..C8` | $0.1\,\mu\text{F}$, $50\text{V}$ X7R Decoupling Capacitor | Murata | **GRM188R71H104KA93D** | 0603 | Mouser: `81-GRM188R71H104KA9D` |
| 15 | `R1` | $10\,\text{k}\Omega$, $1\%$, $0.125\text{W}$ Thick Film Resistor (Pi 5 Handshake) | Vishay | **CRCW080510K0FKEA** | 0805 | Mouser: `71-CRCW080510K0FKEA` |
| 16 | `R2` | $1\,\text{k}\Omega$, $1\%$, $0.125\text{W}$ Thick Film Resistor (UART Isolation) | Vishay | **CRCW08051K00FKEA** | 0805 | Mouser: `71-CRCW08051K00FKEA` |
| 17 | `R3, R4` | $4.7\,\text{k}\Omega$, $1\%$ Pull-Up Resistors (I2C0 SDA/SCL) | Vishay | **CRCW08054K70FKEA** | 0805 | Mouser: `71-CRCW08054K70FKEA` |
| 18 | `FB1..FB3`| Ferrite Bead $220\,\Omega$ @ $100\text{MHz}$, $2\text{A}$ (Noise Suppression) | Murata | **BLM21PG221SN1D** | 0805 | Mouser: `81-BLM21PG221SN1D` |

---

## 3. Industrial Latching Connectors & Terminals

| Item | RefDes | Description | Manufacturer | Manufacturer Part Number (MPN) | Mouser / Farnell Order No. |
|---|---|---|---|---|---|
| 19 | `J1` | 12V Battery Input Header (Molex Micro-Fit 3.0, 2-Pin, Right Angle) | Molex | **43650-0200** | Mouser: `538-43650-0200` |
| 20 | `J2` | I2C0 Sensor Bus Header (Molex Micro-Fit 3.0, 4-Pin, Right Angle) | Molex | **43650-0400** | Mouser: `538-43650-0400` |
| 21 | `J3` | 24 GHz Radar UART Header (Molex Micro-Fit 3.0, 4-Pin, Right Angle)| Molex | **43650-0400** | Mouser: `538-43650-0400` |
| 22 | `J4` | Raspberry Pi 5 Telemetry / Done Header (Micro-Fit 3.0, 4-Pin) | Molex | **43650-0400** | Mouser: `538-43650-0400` |
| 23 | `J5` | 5V 5A High-Power USB-C Receptacle (Power Delivery to Pi 5) | Amphenol ICC | **12401610E4#2A** | Mouser: `523-12401610E42A` |
| 24 | `J6` | Proposed 12V barrel output (not compatible with the selected 5V media converter)| CUI Devices | **PJ-002AH-SMT-TR** | Mouser: `490-PJ-002AH-SMT-TR` |
| 25 | `J7` | 12V PTC De-Icing Heater Ring Terminal (Molex Micro-Fit 3.0, 2-Pin) | Molex | **43650-0200** | Mouser: `538-43650-0200` |
| 26 | `TB1` | Geophone Differential Input Terminal (2-Pin 5.08mm Screw Terminal) | Phoenix Contact / COTS | **MKDSN 1,5/ 2-5,08** | LCSC: `C474952` |

---

## 4. Mechanical & Climate Weatherproofing Subsystem

| Item | Description | Manufacturer | Manufacturer Part Number | Supplier / Distributor |
|---|---|---|---|---|
| 27 | Industrial Polycarbonate Enclosure (IP66, IK10, $-40^\circ\text{C}$ to $+80^\circ\text{C}$) | **Fibox Oy (Espoo, Finland)** | **Fibox ARCA 302015** | Onninen FI / SLO / Yleiselektroniikka |
| 28 | Galvanized Steel Internal Mounting Plate ($250 \times 150\,\text{mm}$) | Fibox Oy | **MP ARCA 3020** | Onninen FI / Elfa Distrelec |
| 29 | M12 ePTFE Waterproof Pressure Equalization Vent (IP68, $-40^\circ\text{C}$) | Wiska Hoppmann | **VentGLAND M12 (EVMS 12)** | Elfa Distrelec: `301-44-122` |
| 30 | M20 IP68 Cable Glands with Low-Temp Silicone Seals ($-50^\circ\text{C}$ to $+100^\circ\text{C}$)| Lapp Group | **SKINTOP MS-M-XL 20x1.5** | Partco / Farnell FI: `1339832` |
| 31 | 12V 1.5W Ceramic PTC Lens De-Icing Ring ($25\,\text{mm}$ ID) | DBK Group / COTS | **PTC-RING-12V-1.5W** | Farnell FI / Mouser Europe |
| 32 | Conformal Coating Spray (Acrylic, IPC-CC-830 Industrial Spec) | HumiSeal | **HumiSeal 1B31** | Farnell FI: `1665873` |
| 33 | Outdoor Armored Single-Mode Fiber Cable (PUR, CSTA, $-45^\circ\text{C}$) | Prysmian Draka (Finland) | **Draka Boreal Flextreme SM** | Onninen Finland / SLO Oy |
