# Saimaa Archipelago Site Planning & Link Topologies

This guide defines site-specific deployment topologies for forest approaches, island/peninsula properties, and remote perimeters in Lake Saimaa and Boreal environments. Complete the [Assembly Sequence](ASSEMBLY_GUIDE.md) and [Validation Plan](FIELD_TESTING_AND_VALIDATION_GUIDE.md) on the bench before field installation.

![Deployment Scenarios: Cabin Nearby vs. Remote / Obstacle Crossing](images/deployment_scenarios_cabin_vs_remote.jpg)

*(Editable vector schematic: [`images/deployment_scenarios_cabin_vs_remote.svg`](images/deployment_scenarios_cabin_vs_remote.svg))*

---

## 1. Selecting the Right Link Topology for Each Site

| Site Condition | Recommended Architecture | Hardware & Engineering Notes |
| :--- | :--- | :--- |
| **Scenario A: Cabin or Outbuilding Nearby ($30\text{ m}$ to $10\text{ km}$)** | **Direct Moss-Buried Single-Mode OS2 Fiber** | **Simply use a longer pre-terminated `SC/UPC` armored single-mode OS2 fiber spool** ($3\text{ mm}$ black jacket tucked $2\text{ cm}$ under forest moss/duff). At $1310\text{ nm}$, OS2 attenuation is only $0.35\text{ dB/km}$; the $+13.2\text{ dB}$ link margin after the $1\times 2$ splitter supports $>10\text{ km}$ with zero repeaters and 100% weather/snow immunity. |
| **Scenario B1: Remote Perimeter / No Cabin Nearby** | **Buried "Dead-Drop" Collector Vault ($100\text{–}500\text{ m}$ Back in Deep Woods)** | Run $100\text{–}300\text{ m}$ of $3\text{ mm}$ armored fiber from the Tree Camera Node away from the trail to a hidden, buried waterproof Collector Vault (`QILIPSU` #2 + battery + headless Pi Collector SSD running `receiver_hub.py --max-alerts 1000`). **Defeats camera destruction/theft:** even if intruders spot and smash the camera at the trail, all signed JPEGs are safely stored $200\text{ m}$ away in the forest vault. |
| **Scenario B2: Narrow Water Strait, Creek, or Public Road Crossing ($5\text{–}100\text{ m}$ LOS)** | **COTS Free-Space Optical (FSO) Collimator Beam** | Where laying cable across a channel or public road is impossible, screw a pair of **Thorlabs (`F220FC-1310` / `F280FC-C`)** or **Edmund Optics** `SC`/`FC` fiber collimators onto Media Converter #1 `TX` and Media Converter #2 `RX` (or use industrial **Leuze DDLS 200** / **Sick ISD400** IP67 optical Ethernet transceivers). Mount on **low rigid granite bedrock or ground stakes**—never high on a swaying tree trunk. |
| **Scenario B3: `200 m – 20 km` Over-the-Hill All-Weather NLOS Relay (`sky-diode-relay` `Build D`)** | **200 m Fiber Standoff + Ordered `2.4 GHz` Troposcatter, Hydrometeor & Canopy-Bounce System** | **Ordered production COTS hardware (`$1,341.94` parts subtotal, `~35–45 min` zero-solder assembly, `23/23` tests passing):** The camera at the lake cottage emits **0.00 W RF** and shoots full-resolution JPEGs over $200\text{ m}$ of moss-buried fiber to the woods Dead-Drop Vault (completely outside any intruder's $15\text{–}30\text{ m}$ RF jammer radius). Uses `ADALM-PLUTO` SDRs, a `Skyworks SE2576L-EK1` (`1 W` / `+30 dBm`) PA, a `Skyworks SKY65405-21EK1` (`1.2 dB NF`) LNA, `Mini-Circuits VBF-2435+` (`2370–2500 MHz`) coaxial bandpass filters, and `2× L-com HG2414P` (`14 dBi`) square outdoor flat-panel antennas to bounce `VK7MO` coherent lock-in frames over granite hills and dense forest (`+14.1 dB` to `+62.3 dB` SNR across clear night, `24h` sun, rain, fog, and snow) with 6-layer out-of-ISM guard-band anti-jamming ([`sky-diode-relay/README.md`](../../sky-diode-relay/README.md)). |

---

## 2. Field Camouflage & Anti-Tamper Installation Checklist

1. **Zone 1 (Tree-Mounted Micro Sensor Pod at $1.8\text{–}2.2\text{ m}$ Height):**
   * Mount the camouflaged `Hammond 1591BSBK` ($112 \times 62 \times 31\text{ mm}$) pod **above natural eye level** ($1.8\text{–}2.2\text{ m}$) inside a vertical bark crevice on the shaded side of a mature pine or spruce trunk.
   * Aim the lens **$20^\circ\text{–}30^\circ$ obliquely down the approach path** so approaching vehicles ($30\text{ km/h} = 8.33\text{ m/s}$) remain in the $40\text{–}50\text{ m}$ field of view after the $6.5\text{–}7.1\text{ s}$ cold boot.
   * Use only **non-metallic** `Rust-Oleum` or `Krylon` Specialty Camouflage Ultra-Flat Earth Brown and Deep Forest Green spray paint so $24\text{ GHz}$ radar waves pass through the front ABS wall unattenuated.
2. **Zone 2 (Trunk Umbilical):**
   * Wrap the $2\text{ m}$ umbilical cable in `Gear Aid Camo Form` matte fabric tape and tuck it flush into a vertical bark furrow down to the roots.
3. **Zone 3 (Moss-Buried Base Vault):**
   * Place the `QILIPSU IP67` base vault ($285 \times 195 \times 130\text{ mm}$) in the root hollow at the base of the tree and cover the top and sides with $3\text{–}5\text{ cm}$ of natural moss, pine needles, and deadwood.
   * Ground burial conceals the heavy box from visual discovery and buffers the `12V` battery against deep night frosts.
4. **Offline Verification Before Leaving the Site:**
   * Record the node ID, `Ed25519` public key fingerprint, GPS coordinates, aiming azimuth, and measured standby/burst current.
   * Walk and drive the approach path to trigger at least 3 live events and inspect the reconstructed JPEGs at the Cabin Collector Hub (or Dead-Drop Vault) before concluding installation.
