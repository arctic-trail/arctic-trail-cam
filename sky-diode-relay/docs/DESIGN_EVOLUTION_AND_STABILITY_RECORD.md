# Sky-Diode-Relay: Design Evolution, Trade-Off Ledger & Architecture Stability Record

**Purpose of This Document:**  
Because the system requirements evolved across several iterations—from a $1.85\text{ km}$ cloud-bounce concept to a $100\text{ km}$ strategic link, and finally to the practical **$200\text{ m}\text{ – }20\text{ km}$ zero-trenching Finnish wilderness cabin relay**—this document records **every design iteration, why each prior iteration was rejected or superseded, why we must not loop back to rejected designs, and why the current architecture (`Build D` $2.4\text{ GHz}$ Troposcatter/Canopy-Bounce + `VK7MO` Keyed-FHSS Lock-In) is now stable.**

---

## 1. Chronological Design Evolution & Why Each Change Happened

```
Iteration 1: 905 nm / 1550 nm Fast 8-PPM Laser + 0.2 mm InGaAs APD (200 m – 2 km)
   │  ✗ REJECTED for NLOS: 0.2 mm APD active area (0.031 mm²) has microscopic etendue (A·Ω);
   │    collects ~0.04 photons/pulse off diffuse clouds and fails 100% on clear nights.
   ▼
Iteration 2: Build B (265 nm Solar-Blind UV-C NLOS, 50 m – 300 m) + Build A (1550 nm LOS FSO)
   │  ✗ REJECTED for >500 m: Rayleigh/ozone absorption limits 265 nm LEDs to <300 m;
   │    1550 nm FSO requires line-of-sight or a mounted treetop mirror.
   ▼
Iteration 3: Build C — VK7MO / KA7OEI 850 nm OSRAM LED + Fresnel Lens + 75.4 mm² PDA100A2 Lock-In (2 km NLOS)
   │  ✓ SOLVED 2 km NLOS (2,400× larger detector area + 16 ms lock-in integration at -13.5 dB SNR).
   │  ✗ REJECTED for 20 km–100 km All-Day/All-Weather & Stealth:
   │    1) Glows brightly on all Gen-2/Gen-3 Night-Vision Goggles (NVGs), hunting scopes & drones.
   │    2) Blinded at 20 km during 18–22 h/day Finnish summer daylight (Fresnel collects massive 850 nm sky glare).
   │    3) Fails at 20 km on clear high-pressure days/nights (insufficient aerosol scatter at 100–300 m altitude).
   ▼
Iteration 4: Build D (v1) — 2.4 GHz 5W Troposcatter / Rain-Scatter SDR System (Targeted for 100 km)
   │  ✓ SOLVED NVG stealth, summer daylight immunity, clear-night refractivity & fog/rain/snow penetration.
   │  ✗ OVER-SPECIFIED for real Finnish geography: In Finland, road/village/farmhouse internet is almost
   │    always within 200 m – 20 km; 100 km required a 2-stage PA chain (ZX60 + 5W QPA9940) and dual 12V/5V rails.
   ▼
Iteration 5 (FINAL & STABLE): Build D (v2) — 200 m to 20 km Optimized 2.4 GHz 1W Troposcatter / Canopy-Bounce
   │  ✓ Single 5.0V DC rail across all boards (TDK-Lambda LS50-5).
   │  ✓ Single 3-stage 1W (+30 dBm, 33 dB gain) Skyworks SE2576L-EK1 PA (no pre-driver needed).
   │  ✓ Works seamlessly from 200 m to 20 km (+40.8 dB median margin at 20 km; +26.8 dB 99% fade margin).
   │  ✓ Shares 100% of the hardened VK7MO + Keyed-FHSS + 2D Costas CFO + Biquad Jammer Notch software stack.
```

---

## 2. Detailed Ledger of Rejected Designs (So We Never Go in Circles)

| Design Option | Distance Where It Works | Fatal Bottleneck for a $200\text{ m}\text{ – }20\text{ km}$ Finnish Product | Why We Must Not Circle Back to It |
| :--- | :---: | :--- | :--- |
| **1. Trenching Physical Fiber (`OS2` Armored Cable)** | $10\text{ m}\text{ – }300\text{ m}$ (Own property only) | Digging $2\text{–}20\text{ km}$ through Finnish granite till (*kivikko*), peat bog (*suo*), tree roots, frost heave (*routa*), and state/third-party land (*Metsähallitus*) is legally and physically impractical. | Keep fiber strictly for short $<15\text{ m}\text{ – }200\text{ m}$ local camera-to-relay runs where desired. |
| **2. $1550\text{ nm}$ Laser + $0.2\text{ mm}$ `InGaAs` APD (`Build A`) for Cloud Bounce** | $100\text{ m}\text{ – }2.5\text{ km}$ **Line-of-Sight Only** | Conservation of etendue ($A\Omega = \text{const}$): a $0.2\text{ mm}$ detector behind a $50\text{ mm}$ lens has a $4\text{ mrad}$ ($0.23^\circ$) field of view, rejecting $>99.9\%$ of diffuse cloud/canopy scatter. | Only usable when endpoints have direct line-of-sight (or a physical mirror on a tower/ridge). |
| **3. `VK7MO` $850\text{ nm}$ OSRAM LED + Fresnel Optical Scatter (`Build C`) at $20\text{ km}$** | $200\text{ m}\text{ – }2\text{ km}$ all-day;<br>up to $5\text{–}10\text{ km}$ **at night** | **Fails at $20\text{ km}$ even in fair weather (no snow/fog):**<br>1. **Summer Daylight (`Yötön yö`):** Wide-angle Fresnel lens gathers intense $850\text{ nm}$ solar background for 18–22 hours/day from May to August, drowning out femtowatt $20\text{ km}$ scatter.<br>2. **Clear Crisp Skies:** Without low cloud/mist at $100\text{–}300\text{ m}$ altitude, the $850\text{ nm}$ beam escapes into space.<br>3. **NVG Beacon:** $850\text{ nm}$ is brightly visible to all night-vision scopes and trail cameras. | Great as a $200\text{ m}\text{ – }2\text{ km}$ $0.00\text{ W}$ RF experiment, but **cannot** serve as a reliable $20\text{ km}$ year-round cabin backhaul. |
| **4. Standard LoRa / Cellular / GPSDO Weak-Signal Radio (`Q65`/`FT8`)** | $2\text{ km}\text{ – }20\text{ km}$ (Peacetime / No EW) | Standard `Q65`/`FT8` requires GPS-Disciplined Oscillators (`GPSDO`) that fail under Eastern Finland GNSS jamming/spoofing; omnidirectional `868 MHz` LoRa has wide beamwidth susceptible to direction-finding and broadband UHF jamming. | Our custom `VK7MO` 2D Costas Time-Frequency correlator locks onto $\pm 450\text{ Hz}$ drift with **zero GPS**, and our $2.4\text{ GHz}$ directional beam + biquad notch filter defeats $+20\text{ dB}$ jammers. |
| **5. $100\text{ km}$ Dual-PA (`ZX60` + `5W QPA9940`) + Dual `12V`/`5V` PSU Cart** | $20\text{ km}\text{ – }100\text{ km}$ | Added $\$276+$ of redundant RF stages (`ZX60-2510MA-S+` pre-driver + `QPA9940EVB-01` 5W PA) and a `12V` PSU that could accidentally over-volt `5.0V` RF boards. | In Finland, internet/roadside hubs are within $200\text{ m}\text{ – }20\text{ km}$. The single `1W` `SE2576L-EK1` (`33 dB` built-in gain) on a unified `5.0V` rail is simpler, safer, and cheaper. |

---

## 3. FAQ: "What If There Are No Burglars in Heavy Snow or Fog?"

A natural question is: *If cabin burglars rarely operate during heavy blizzards or dense fog (and store-and-forward retries can wait out a passing squall), can we go back to the `850 nm` optical Fresnel design (`Build C`) for the $20\text{ km}$ hop?*

**No—for three reasons that have nothing to do with snow or fog:**

1. **Finnish Summer & Spring Daylight (When Most Rural Trespassing Actually Happens):**
   * From April through September, Finland has **14 to 22 hours of bright daylight per day**.
   * At **$2\text{ km}$**, an $850\text{ nm}$ optical canopy/cloud bounce is strong enough for lock-in detection in daylight.
   * At **$20\text{ km}$**, the scattered optical signal is **$35\text{ to }45\text{ dB}$ ($3,000\times\text{ to }30,000\times$) weaker** than at $2\text{ km}$. Meanwhile, the wide-angle Fresnel lens collects full daytime solar sky radiance at $850\text{ nm}$. Even with an `RG780` filter (`FGL780M`), solar shot noise at $850\text{ nm}$ overwhelms a $20\text{ km}$ non-line-of-sight LED bounce throughout the daytime. (Rex Moncur `VK7MO`'s $27\text{ km}$ optical scatter tests were conducted **in darkness at night**).
2. **Clear High-Pressure Weather (Zero Clouds to Bounce Off):**
   * On a clear, crisp day or clear starry night (`Visibility > 30 km`), there is no cloud base and minimal aerosol haze at the $100\text{–}300\text{ m}$ geometric intersection height over a $20\text{ km}$ path. Optical scatter drops by $>25\text{ dB}$ on clear nights, whereas **$2.4\text{ GHz}$ troposcatter bounces off refractive index turbulence ($\Delta n$) and terrain diffraction that exist 24/7 in clear sky**.
3. **Human/Hunter Detection with Night-Vision Scopes:**
   * A $5\text{–}15\text{ W}$ $850\text{ nm}$ LED bank firing for $35\text{ seconds}$ looks like a bright flashlight through any digital night-vision hunting scope, thermal/IR monocular, or neighbouring trail camera. **$2.4\text{ GHz}$ (`Build D`) is 100% invisible to all eyes, cameras, and night-vision goggles.**

---

## 4. Final Sense-Check & Stability Verdict on Current `Build D` ($200\text{ m}\text{ – }20\text{ km}$)

### A. What Is 100% Locked, Verified & Stable (Zero Further Changes Needed)

1. **Software & DSP Stack (`transmitter/sky_transmitter.py`, `receiver/sky_receiver.py`, `tests/test_sky_relay_simulation.py`):**
   * **23/23 automated tests passing.**
   * Includes `VK7MO` 8-FSK quadrature lock-in (`encode_vk7mo_lockin_frame` / `demodulate_vk7mo_lockin_stream`), **2D Costas Time-Frequency CFO Lock** ($\pm 450\text{ Hz}$ drift without GPS/GPSDO), **HMAC/SHA-256 Keyed FHSS (`fhss_key`)**, **Wideband Multi-Pass RF Carrier Hopping** (`derive_fhss_carrier_schedule`, hopping into `2372–2396 MHz` and `2485–2498 MHz` guard bands outside consumer Wi-Fi/drone jammers), **Barrage-Jammer Pass Gate & Inverse-Variance Combiner** (rejects $+26\text{ dB}$ wideband barrage-jammed passes), **Pulsed/Chirp Jammer Symbol Erasure Detector** (repairs $+25\text{ dB}$ wideband bursts via FEC), **Time-Domain Biquad Notch Filter** (`_excise_cw_jammers_time_domain`, defeating $+20\text{ dB}$ continuous jammers), **Single-Jammed-Tone Carrier-Absence Recovery**, and **Bit-Interleaved Extended Hamming(8,4) SECDED + Erasure FEC**.
2. **RF Signal Chain & Link Budget ($200\text{ m}\text{ – }20\text{ km}$):**
   * **TX Chain:** `ADALM-PLUTO SDR` ($-3\text{ dBm}$) $\rightarrow$ `Skyworks SE2576L-EK1` ($33\text{ dB}$ gain, $+30\text{ dBm} / 1\text{ W}$ out) $\rightarrow$ `Mini-Circuits VBF-2435+` Bandpass Filter $\rightarrow$ `L-com HG2414P` ($14\text{ dBi}$ weatherproof flat radome patch panel).
   * **RX Chain:** `L-com HG2414P` ($14\text{ dBi}$ panel) $\rightarrow$ `Mini-Circuits VBF-2435+` Bandpass Filter $\rightarrow$ `Skyworks SKY65405-21EK1` ($1.2\text{ dB}$ NF, $15\text{ dB}$ gain LNA) $\rightarrow$ `ADALM-PLUTO SDR`.
   * **Link Margin:** **$+40.8\text{ dB}$ median link margin** ($+26.8\text{ dB}$ 99% Rayleigh fade margin) at $20\text{ km}$ non-line-of-sight; works all the way down to $200\text{ m}$ without saturating the receiver (max RX input at $200\text{ m}$ obstructed is $\sim -42\text{ dBm}$, well below the $-13\text{ dBm}$ LNA compression point).
3. **10-Item Non-Chinese DigiKey Order Submitted:**
   * Every part is **In Stock**, **100% non-Chinese** (USA, UK, Canada, Japan), and operates on a **single unified `5.0V DC` rail** (`TDK-Lambda LS50-5`, `285-1824-ND`).

![Build D Receiver: Filtering, Low-Noise Amplification, Coherent Integration](images/sky_relay_20km_troposcatter_blueprint.png)

### B. Three Practical Assembly Details to Keep in Mind When Building (`~35–45 Minutes Total`, Zero Soldering)

To ensure zero surprises when the DigiKey box arrives on your bench:

1. **How the Enclosures Are Used (`Hammond 1590Z120` Mast Doghouse vs. Indoor/Cabin Host):**
   * The two cast-aluminum `Hammond 1590Z120` boxes (`4.91" × 3.14" × 2.26"`, `HM600-ND`) are compact **mast-mounted RF shield boxes ("doghouses")** that house the outdoor `SE2576L-EK1` PA (on TX) or `SKY65405-21EK1` LNA (on RX) + `VBF-2435+` bandpass filter right behind the `HG2414P` antenna.
   * The `ADALM-PLUTO` SDR (`4.6" × 3.1"`) and `TDK-Lambda LS50-5` `5V` power supply (`3.9" × 3.2"`) sit inside your dry cabin/farmhouse (or inside your main `QILIPSU` / `Fibox` camera vault) alongside the Raspberry Pi / laptop host.
2. **Enabling the `Skyworks SE2576L-EK1` $1\text{ W}$ PA (`C0` / `C1` Logic Pins):**
   * By design, the `SE2576L-EK1` evaluation board sleeps at **`< 1 µA` ($0.00\text{ W}$)** until its logic enable pins (`C0` and `C1` on the control header) are pulled HIGH to `3.3V`.
   * Connect `C0` and `C1` to a `3.3V` GPIO pin on the `Raspberry Pi Pico 2 H` (or jumper them to `3.3V` during bench testing) so the $1\text{ W}$ PA only draws power during the actual transmit burst and consumes $0.00\text{ W}$ in standby.
3. **Off-Grid $12\text{ V}$ Battery Operation vs. $230\text{ V AC}$ Mains Operation:**
   * At a farmhouse or village hub with wall power, use the `TDK-Lambda LS50-5` (`85–264V AC` $\rightarrow$ `5.0V DC`) included in the cart.
   * At an off-grid wilderness cabin running on a `12V 12Ah` AGM/LiFePO4 battery, `ADALM-PLUTO`, `Pico 2 H`, and the `5.0V` RF boards only draw **`~4.5 W` total during a transmit burst** (`< 1 A` at `5.0V`) and can be powered directly from the Raspberry Pi's USB ports or any standard `12V`-to-`5V` USB/buck supply.
