#!/usr/bin/env python3
"""
Raspberry Pi 5 USB Host Auto-TX Driver for ADALM-PLUTO (Sky-Diode-Relay)
========================================================================
Runs continuously on the Raspberry Pi 5 inside the QILIPSU field box.
Whenever TX ADALM-PLUTO #1 is plugged into any Raspberry Pi 5 USB port,
it enumerates as /dev/ttyACM0 (CDC ACM serial console).

Because ADALM-PLUTO stores its AD9363 RF transceiver registers (TX LO frequency,
cf-ad9361-dds-core-lpc tone scale, and TX hardwaregain) in volatile RAM that
resets to defaults (2450 MHz, scale 0.000000) on every power cycle, this daemon
checks /dev/ttyACM* every 3 seconds and ensures the connected ADALM-PLUTO is
actively transmitting its 2.425 GHz + 500 kHz DDS beacon at -3.0 dB TX hardwaregain.
"""

import glob
import os
import sys
import time


PLUTO_TX_COMMANDS = [
    "PHY=/sys/bus/iio/devices/iio:device0",
    "DDS=/sys/bus/iio/devices/iio:device2",
    "echo 2425000000 > $PHY/out_altvoltage1_TX_LO_frequency",
    "echo 2425000000 > $PHY/out_altvoltage0_RX_LO_frequency",
    "echo 0 > $PHY/out_altvoltage1_TX_LO_powerdown",
    "echo 1 > $DDS/out_altvoltage0_TX1_I_F1_raw",
    "echo 1 > $DDS/out_altvoltage1_TX1_I_F2_raw",
    "echo 1 > $DDS/out_altvoltage2_TX1_Q_F1_raw",
    "echo 1 > $DDS/out_altvoltage3_TX1_Q_F2_raw",
    "echo 500000 > $DDS/out_altvoltage0_TX1_I_F1_frequency",
    "echo 90000 > $DDS/out_altvoltage0_TX1_I_F1_phase",
    "echo 0.25 > $DDS/out_altvoltage0_TX1_I_F1_scale",
    "echo 0 > $DDS/out_altvoltage1_TX1_I_F2_scale",
    "echo 500000 > $DDS/out_altvoltage2_TX1_Q_F1_frequency",
    "echo 0 > $DDS/out_altvoltage2_TX1_Q_F1_phase",
    "echo 0.25 > $DDS/out_altvoltage2_TX1_Q_F1_scale",
    "echo 0 > $DDS/out_altvoltage3_TX1_Q_F2_scale",
    "echo -3 > $PHY/out_voltage0_hardwaregain",
]


def configure_pluto_on_port(port: str) -> dict:
    """Logs into ADALM-PLUTO serial console on `port` and enforces 2.425 GHz TX."""
    fd = None
    try:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

        def _cmd(s: str, wait_s: float = 0.22) -> str:
            os.write(fd, (s + "\r\n").encode())
            time.sleep(wait_s)
            out = b""
            while True:
                try:
                    chunk = os.read(fd, 8192)
                    if not chunk:
                        break
                    out += chunk
                except BlockingIOError:
                    break
            return out.decode(errors="ignore")

        _cmd("", 0.15)
        _cmd("root", 0.2)
        _cmd("analog", 0.2)
        name_out = _cmd("cat /sys/bus/iio/devices/iio:device0/name 2>/dev/null", 0.25)
        if "ad9361-phy" not in name_out:
            os.close(fd)
            return {"ok": False, "port": port, "reason": "not_ad9361_phy"}

        # Check current TX LO and DDS scale on iio:device2 (cf-ad9361-dds-core-lpc)
        lo_out = _cmd("cat /sys/bus/iio/devices/iio:device0/out_altvoltage1_TX_LO_frequency", 0.2)
        scale_out = _cmd("cat /sys/bus/iio/devices/iio:device2/out_altvoltage0_TX1_I_F1_scale", 0.2)
        already_configured = ("2425000000" in lo_out) and ("0.250" in scale_out or "0.249" in scale_out)

        if not already_configured:
            _cmd("; ".join(PLUTO_TX_COMMANDS), 0.6)

        lo_verify = _cmd("cat /sys/bus/iio/devices/iio:device0/out_altvoltage1_TX_LO_frequency", 0.2)
        gain_verify = _cmd("cat /sys/bus/iio/devices/iio:device0/out_voltage0_hardwaregain", 0.2)
        scale_verify = _cmd("cat /sys/bus/iio/devices/iio:device2/out_altvoltage0_TX1_I_F1_scale", 0.2)
        os.close(fd)
        return {
            "ok": ("2425000000" in lo_verify) and ("0.250" in scale_verify or "0.249" in scale_verify),
            "port": port,
            "reconfigured": not already_configured,
            "tx_lo_hz": "2425000000" if "2425000000" in lo_verify else lo_verify.strip(),
            "tx_gain_db": "-3.0 dB" if "-3.0" in gain_verify else gain_verify.strip(),
            "dds_scale": "0.250000" if "0.250" in scale_verify else scale_verify.strip(),
        }
    except Exception as exc:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        return {"ok": False, "port": port, "error": str(exc)}


def main() -> int:
    once = "--once" in sys.argv
    print("[*] Starting ADALM-PLUTO USB Host Auto-TX Driver (2.425 GHz DDS Beacon)...")
    while True:
        ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/cu.usbmodem*"))
        for p in ports:
            res = configure_pluto_on_port(p)
            if res.get("ok"):
                if res.get("reconfigured") or once:
                    print(f"[+] Configured ADALM-PLUTO TX on {p}: {res}", flush=True)
        if once:
            return 0
        time.sleep(3.0)


if __name__ == "__main__":
    raise SystemExit(main())
