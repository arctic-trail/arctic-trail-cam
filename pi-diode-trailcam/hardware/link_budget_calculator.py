#!/usr/bin/env python3
# File: hardware/link_budget_calculator.py
# Description: Optical Link Budget & Attenuation Calculator for Single-Mode Simplex Diode Links
# License: MIT
import argparse

TRANSCEIVER_PRESETS = {
    "1310-LX": {
        "desc": "Standard 1310nm LX/LH (e.g., TP-Link MC210CS / StarTech)",
        "wavelength_nm": 1310,
        "tx_power_dbm": -3.0,
        "rx_sensitivity_dbm": -20.0,
        "rx_saturation_dbm": -3.0,
        "fiber_loss_db_km": 0.35,
        "max_rated_km": 20.0
    },
    "1550-ZX": {
        "desc": "Long-Haul 1550nm ZX SFP Module",
        "wavelength_nm": 1550,
        "tx_power_dbm": 0.0,
        "rx_sensitivity_dbm": -23.0,
        "rx_saturation_dbm": -3.0,
        "fiber_loss_db_km": 0.19,
        "max_rated_km": 80.0
    },
    "1550-EZX": {
        "desc": "Ultra-Long-Haul 1550nm EZX DFB/APD SFP Module",
        "wavelength_nm": 1550,
        "tx_power_dbm": 3.0,
        "rx_sensitivity_dbm": -30.0,
        "rx_saturation_dbm": -8.0,
        "fiber_loss_db_km": 0.19,
        "max_rated_km": 120.0
    }
}

SPLITTER_LOSS_DB = 3.2    # 1x2 PLC Splitter 50/50 split loss
CONNECTOR_LOSS_DB = 0.6   # 2x SC/UPC connector mated pairs (0.3 dB each)

def calculate_budget(preset_name, distance_km, extra_loss_db=0.0):
    spec = TRANSCEIVER_PRESETS[preset_name]
    fiber_loss = distance_km * spec["fiber_loss_db_km"]
    total_passive_loss = SPLITTER_LOSS_DB + CONNECTOR_LOSS_DB + fiber_loss + extra_loss_db

    received_power = spec["tx_power_dbm"] - total_passive_loss
    safety_margin = received_power - spec["rx_sensitivity_dbm"]

    # Saturation check: is received power higher than maximum allowed RX input?
    is_saturated = received_power > spec["rx_saturation_dbm"]
    recommended_attenuator = 0
    if is_saturated:
        recommended_attenuator = round(received_power - spec["rx_saturation_dbm"] + 3.0, 1)

    return {
        "preset": spec["desc"],
        "wavelength": f"{spec['wavelength_nm']} nm",
        "distance": f"{distance_km:.2f} km",
        "tx_power": f"{spec['tx_power_dbm']:.1f} dBm",
        "splitter_loss": f"{SPLITTER_LOSS_DB:.1f} dB",
        "fiber_loss": f"{fiber_loss:.2f} dB ({spec['fiber_loss_db_km']} dB/km)",
        "total_passive_loss": f"{total_passive_loss:.2f} dB",
        "rx_power": f"{received_power:.2f} dBm",
        "rx_sensitivity": f"{spec['rx_sensitivity_dbm']:.1f} dBm",
        "safety_margin": f"{safety_margin:+.2f} dB",
        "is_saturated": is_saturated,
        "recommended_attenuator": f"{recommended_attenuator} dB" if is_saturated else "None required (Safe)",
        "link_viable": safety_margin >= 3.0 and not is_saturated
    }

def main():
    parser = argparse.ArgumentParser(description="Optical Link Budget Calculator for Pi-Diode System")
    parser.add_argument("--distance", type=float, default=5.0, help="Fiber distance in kilometers (default: 5.0)")
    parser.add_argument("--preset", choices=list(TRANSCEIVER_PRESETS.keys()), default="1310-LX", help="Transceiver type")
    parser.add_argument("--bench", action="store_true", help="Calculate for benchtop test (0.01 km patch cord)")
    args = parser.parse_args()

    dist = 0.01 if args.bench else args.distance
    res = calculate_budget(args.preset, dist)

    print("=" * 65)
    print("PI-DIODE OPTICAL FIBER LINK BUDGET ASSESSMENT")
    print("=" * 65)
    for k, v in res.items():
        print(f"  {k.replace('_', ' ').title():<26}: {v}")
    print("=" * 65)
    if res["is_saturated"]:
        print("[WARNING] RECEIVER PHOTODIODE SATURATION RISK!")
        print(f"  For short-distance tests, install a {res['recommended_attenuator']} optical attenuator")
        print("  to prevent overdriving the receiver photodiode.")
    elif res["link_viable"]:
        print("[+] OPTICAL LINK STATUS: EXCELLENT (Robust link margin)")
    else:
        print("[!] OPTICAL LINK MARGIN TOO LOW (<3.0 dB safety margin)")

if __name__ == "__main__":
    main()
