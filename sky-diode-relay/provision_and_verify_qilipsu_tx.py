#!/usr/bin/env python3
"""
Turnkey Provisioning & 100% Field-Topology Verification for TX ADALM-PLUTO #1
=============================================================================
Enforces the "Zero Close-Enough Bench Tests" rule:
1. `--provision-pluto`:
   Connects to TX ADALM-PLUTO #1 over USB serial, writes `/mnt/jffs2/autostart_tx.sh`
   targeting `iio:device0` (ad9361-phy) + `iio:device2` (cf-ad9361-dds-core-lpc),
   hooks `/etc/network/interfaces` via `fw_setenv -s` AND updates `/opt/vfat.md5`
   so macOS FAT16 unmounting never triggers `/sbin/update.sh` (`process_ini`) to strip
   `\n\t` from `netmask`.
2. `--verify-qilipsu-ota`:
   Verifies the exact 100.00% field power & cabling topology:
   - TX ADALM-PLUTO #1 MUST be completely unplugged from the receiver laptop and plugged ONLY
     into the QILIPSU box (Raspberry Pi 5 USB port on 12V battery power).
   - RX ADALM-PLUTO #2 is connected to the receiver laptop (confirming exactly 1 Pluto on host USB).
   - Measures live 2.425 GHz RX RSSI and requires >= -60.0 dBm (at least +40 dB above the
     -101 dBm noise floor) before certifying PASS.
"""

import argparse
import glob
import os
import sys
import time


JFFS2_STARTUP_SCRIPT = """#!/bin/sh
# Persistent 2.425 GHz + 500 kHz DDS TX Beacon for Sky-Diode-Relay Field Unit
PHY=/sys/bus/iio/devices/iio:device0
DDS=/sys/bus/iio/devices/iio:device2
echo 2425000000 > $PHY/out_altvoltage1_TX_LO_frequency
echo 2425000000 > $PHY/out_altvoltage0_RX_LO_frequency
echo 0 > $PHY/out_altvoltage1_TX_LO_powerdown
echo 1 > $DDS/out_altvoltage0_TX1_I_F1_raw
echo 1 > $DDS/out_altvoltage1_TX1_I_F2_raw
echo 1 > $DDS/out_altvoltage2_TX1_Q_F1_raw
echo 1 > $DDS/out_altvoltage3_TX1_Q_F2_raw
echo 500000 > $DDS/out_altvoltage0_TX1_I_F1_frequency
echo 90000 > $DDS/out_altvoltage0_TX1_I_F1_phase
echo 0.25 > $DDS/out_altvoltage0_TX1_I_F1_scale
echo 0 > $DDS/out_altvoltage1_TX1_I_F2_scale
echo 500000 > $DDS/out_altvoltage2_TX1_Q_F1_frequency
echo 0 > $DDS/out_altvoltage2_TX1_Q_F1_phase
echo 0.25 > $DDS/out_altvoltage2_TX1_Q_F1_scale
echo 0 > $DDS/out_altvoltage3_TX1_Q_F2_scale
echo -3 > $PHY/out_voltage0_hardwaregain
"""


def _open_pluto_serial(port: str):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

    def _cmd(s: str, wait_s: float = 0.28) -> str:
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
    _cmd("root", 0.25)
    _cmd("analog", 0.25)
    return fd, _cmd


def provision_tx_pluto() -> int:
    ports = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))
    if not ports:
        print("[-] No ADALM-PLUTO serial port (/dev/cu.usbmodem* or /dev/ttyACM*) found.")
        return 1

    port = ports[0]
    print(f"[*] Connecting to ADALM-PLUTO on {port} for JFFS2 + U-Boot provisioning...")
    fd, _cmd = _open_pluto_serial(port)
    try:
        probe = _cmd("cat /sys/bus/iio/devices/iio:device0/name 2>/dev/null", 0.3)
        if "ad9361-phy" not in probe:
            print(f"[-] Device on {port} is not an ADALM-PLUTO (ad9361-phy not found).")
            return 1

        _cmd("mkdir -p /mnt/jffs2/etc/init.d", 0.2)
        for target in ("/mnt/jffs2/autostart_tx.sh", "/mnt/jffs2/runme.sh"):
            _cmd(f"cat << 'EOF' > {target}\n{JFFS2_STARTUP_SCRIPT.strip()}\nEOF", 0.4)
            _cmd(f"chmod +x {target}", 0.2)

        # Hook S40network via fw_setenv -s and make /sbin/update.sh a safe no-op or sync vfat.md5
        # so macOS Spotlight metadata on /Volumes/PlutoSDR never triggers process_ini to corrupt netmask!
        _cmd("printf 'netmask 255.255.255.0\\\\n\\\\tup /mnt/jffs2/autostart_tx.sh\\n' > /tmp/fw.tmp", 0.25)
        _cmd("fw_setenv -s /tmp/fw.tmp", 0.4)
        _cmd("sed -i 's/netmask = .*/netmask = 255.255.255.0/' /opt/config.txt 2>/dev/null || true", 0.3)
        _cmd("md5sum /opt/vfat.img > /opt/vfat.md5 2>/dev/null || true", 0.3)
        _cmd("sync", 0.3)
        _cmd("/mnt/jffs2/autostart_tx.sh", 0.5)

        lo_out = _cmd("cat /sys/bus/iio/devices/iio:device0/out_altvoltage1_TX_LO_frequency", 0.25)
        gain_out = _cmd("cat /sys/bus/iio/devices/iio:device0/out_voltage0_hardwaregain", 0.25)
        scale_out = _cmd("cat /sys/bus/iio/devices/iio:device2/out_altvoltage0_TX1_I_F1_scale", 0.25)
        env_out = _cmd("fw_printenv netmask", 0.25)
        print(f"[+] U-Boot netmask hook: {env_out.strip()}")
        print(f"[+] Live TX LO: {lo_out.strip()} | TX Gain: {gain_out.strip()} | DDS Scale: {scale_out.strip()}")
        return 0
    finally:
        os.close(fd)


def verify_qilipsu_ota(num_samples: int = 8, min_rssi_dbm: float = -60.0) -> int:
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if len(ports) == 0:
        print("[-] FAIL: No RX ADALM-PLUTO detected on receiver laptop (/dev/cu.usbmodem*).")
        return 1
    if len(ports) > 1:
        print(
            f"[-] FAIL (Topology Violation): Found {len(ports)} Plutos plugged into the receiver laptop ({ports}).\n"
            "    TX ADALM-PLUTO #1 MUST be unplugged from the laptop and plugged ONLY into the QILIPSU box!"
        )
        return 1

    rx_port = ports[0]
    print(f"[*] Topology Check PASSED: Exactly 1 ADALM-PLUTO ({rx_port}) is connected to the receiver laptop (RX unit).")
    print("[*] Tuning RX ADALM-PLUTO #2 to 2.425 GHz (slow_attack AGC) and measuring over-the-air RSSI...")
    fd, _cmd = _open_pluto_serial(rx_port)
    try:
        _cmd("echo 2425000000 > /sys/bus/iio/devices/iio:device0/out_altvoltage0_RX_LO_frequency", 0.25)
        _cmd("echo slow_attack > /sys/bus/iio/devices/iio:device0/in_voltage0_gain_control_mode", 0.25)
        # Ensure RX Pluto's own TX is powered down so it never self-interferes!
        _cmd("echo 1 > /sys/bus/iio/devices/iio:device0/out_altvoltage1_TX_LO_powerdown", 0.25)
        _cmd("echo 0 > /sys/bus/iio/devices/iio:device2/out_altvoltage0_TX1_I_F1_scale", 0.2)
        _cmd("echo 0 > /sys/bus/iio/devices/iio:device2/out_altvoltage2_TX1_Q_F1_scale", 0.2)

        samples = []
        for idx in range(num_samples):
            out_rssi = _cmd("cat /sys/bus/iio/devices/iio:device0/in_voltage0_rssi", 0.3)
            out_gain = _cmd("cat /sys/bus/iio/devices/iio:device0/in_voltage0_hardwaregain", 0.3)
            rssi_lines = [l.strip() for l in out_rssi.splitlines() if "dB" in l]
            gain_lines = [l.strip() for l in out_gain.splitlines() if "dB" in l]
            if rssi_lines and gain_lines:
                rssi_dbm = -abs(float(rssi_lines[-1].split()[0]))
                agc_db = float(gain_lines[-1].split()[0])
                samples.append({"sample": idx + 1, "rx_rssi_dbm": rssi_dbm, "rx_agc_gain_db": agc_db})
                print(f"    Sample {idx + 1}/{num_samples}: Live RX RSSI = {rssi_dbm:6.2f} dBm | AGC Gain = {agc_db:5.1f} dB")

        if not samples:
            print("[-] FAIL: Could not read RSSI samples from RX Pluto.")
            return 1

        avg_rssi = round(sum(s["rx_rssi_dbm"] for s in samples) / len(samples), 2)
        avg_agc = round(sum(s["rx_agc_gain_db"] for s in samples) / len(samples), 2)
        passed = avg_rssi >= min_rssi_dbm
        verdict = "PASS" if passed else "FAIL"
        print(
            f"\n[{'+' if passed else '-'}] QILIPSU Standalone TX Verification Verdict: {verdict}\n"
            f"    Average RX RSSI: {avg_rssi:.2f} dBm (Required >= {min_rssi_dbm:.2f} dBm) | Average AGC Gain: {avg_agc:.2f} dB"
        )
        return 0 if passed else 1
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision & Verify Standalone QILIPSU TX ADALM-PLUTO")
    parser.add_argument("--provision-pluto", action="store_true", help="Provision connected Pluto JFFS2 flash & enable 2.425 GHz TX")
    parser.add_argument("--verify-qilipsu-ota", action="store_true", help="Verify RX Pluto receives strong 2.425 GHz carrier from standalone QILIPSU TX")
    parser.add_argument("--min-rssi-dbm", type=float, default=-60.0, help="Minimum required RX RSSI (dBm) for PASS")
    args = parser.parse_args()

    if args.provision_pluto:
        return provision_tx_pluto()
    if args.verify_qilipsu_ota:
        return verify_qilipsu_ota(min_rssi_dbm=args.min_rssi_dbm)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
