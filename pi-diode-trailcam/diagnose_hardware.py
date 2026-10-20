#!/usr/bin/env python3
"""
Arctic Trail Cam — Offline Zero-LLM Hardware & Wiring Diagnostic Doctor
=======================================================================
Troubleshoots the entire prototype (Pico 2 breadboard wiring, GY-271 QMC5883L
compass, ADS1015 ADC, HLK-LD2450 radar, Raspberry Pi 5 camera ribbon, UART/DONE
handshake wires, Optical Data Diode, and Collector Hub) using pure electrical
and protocol physics — NO LLM or internet connection required.

Usage:
  python3 pi-diode-trailcam/diagnose_hardware.py           # Full system diagnostic + live pin fixer if needed
  python3 pi-diode-trailcam/diagnose_hardware.py --watch   # Continuous live breadboard pin & sensor monitor
  python3 pi-diode-trailcam/diagnose_hardware.py --once    # Single-shot report (no interactive loop)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = Path(__file__).resolve().parent

# ANSI formatting
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"


def banner(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 76}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 76}{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}[✓ OK]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[! WARN]{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}[✗ PROBLEM]{RESET} {msg}")


def fix(msg: str) -> None:
    print(f"      {BOLD}{YELLOW}-> FIX:{RESET} {msg}")


def find_mpremote() -> str:
    venv_mp = REPO_ROOT / ".venv" / "bin" / "mpremote"
    if venv_mp.exists():
        return str(venv_mp)
    which_mp = shutil.which("mpremote")
    if which_mp:
        return which_mp
    return sys.executable + " -m mpremote"


# MicroPython snippet executed directly on Pico 2 to perform deterministic
# electrical continuity, pull-up/pull-down, swapped-pin, and bus scans.
PICO_PROBE_CODE = r"""
from machine import Pin, I2C, SoftI2C, UART
import time, json, struct, math

def check_ext_pullup(gp):
    # Drive low briefly to clear RP2350 pad capacitance, then enable 50k pull-down.
    # If an external 4.7k pull-up to 3.3V (on GY-271 or ADS1015) is connected,
    # the 4.7k pull-up holds the pin at ~3.0V (logic 1). Otherwise it stays 0.
    p = Pin(gp, Pin.OUT, value=0)
    time.sleep_ms(2)
    p.init(Pin.IN, Pin.PULL_DOWN)
    time.sleep_ms(2)
    val = p.value()
    p.init(Pin.IN, Pin.PULL_UP)
    return val

def check_short_to_gnd(gp):
    # Drive high briefly, then enable 50k pull-up. If shorted to GND, reads 0.
    p = Pin(gp, Pin.OUT, value=1)
    time.sleep_ms(1)
    p.init(Pin.IN, Pin.PULL_UP)
    time.sleep_ms(2)
    return 1 if p.value() == 0 else 0

# Map Pico left-side rows (Rows 1..20) to GP numbers
# Row 1=GP0, Row 2=GP1, Row 3=GND, Row 4=GP2, Row 5=GP3, Row 6=GP4, Row 7=GP5,
# Row 8=GND, Row 9=GP6, Row 10=GP7, Row 11=GP8, Row 12=GP9, Row 13=GND, Row 14=GP10, Row 15=GP11
SCAN_GPS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 22]
pulled_up_gps = []
gnd_short_gps = []

for gp in SCAN_GPS:
    if check_ext_pullup(gp) == 1:
        pulled_up_gps.append(gp)
    if check_short_to_gnd(gp) == 1:
        gnd_short_gps.append(gp)

sda_ok = 1 if 4 in pulled_up_gps else 0
scl_ok = 1 if 5 in pulled_up_gps else 0

# Test normal I2C0 (SDA=GP4, SCL=GP5)
i2c_norm = SoftI2C(sda=Pin(4), scl=Pin(5), freq=100000)
norm_devs = i2c_norm.scan()

# Test swapped SDA/SCL (SDA=GP5, SCL=GP4)
i2c_swap = SoftI2C(sda=Pin(5), scl=Pin(4), freq=100000)
swap_devs = i2c_swap.scan()

# Test if QMC5883L (0x0d) or QMC5883P (0x2c) can read a sample XYZ vector
qmc_xyz = None
qmc_chip = None
if 0x0D in norm_devs:
    qmc_chip = "QMC5883L (0x0d)"
    try:
        hw_i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
        hw_i2c.writeto_mem(0x0D, 0x0A, b'\x80')
        time.sleep_ms(10)
        hw_i2c.writeto_mem(0x0D, 0x0B, b'\x01')
        hw_i2c.writeto_mem(0x0D, 0x09, b'\x1D')
        time.sleep_ms(20)
        raw = hw_i2c.readfrom_mem(0x0D, 0x00, 6)
        x, y, z = struct.unpack('<hhh', raw)
        qmc_xyz = [x, y, z, int(math.sqrt(x*x + y*y + z*z))]
    except Exception as e:
        qmc_xyz = str(e)
elif 0x2C in norm_devs:
    qmc_chip = "QMC5883P (0x2c)"
    try:
        hw_i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
        hw_i2c.writeto_mem(0x2C, 0x29, b'\x06')
        hw_i2c.writeto_mem(0x2C, 0x0B, b'\x08')
        hw_i2c.writeto_mem(0x2C, 0x0A, b'\xCD')
        time.sleep_ms(25)
        raw = hw_i2c.readfrom_mem(0x2C, 0x01, 6)
        x, y, z = struct.unpack('<hhh', raw)
        qmc_xyz = [x, y, z, int(math.sqrt(x*x + y*y + z*z))]
    except Exception as e:
        qmc_xyz = str(e)

# Check Radar UART0 (GP0/GP1 at 256000 baud) for HLK-LD2450 frames (AA FF 03 00)
radar_bytes = 0
radar_valid = False
try:
    u0 = UART(0, baudrate=256000, tx=Pin(0), rx=Pin(1))
    t0 = time.ticks_ms()
    buf = b""
    while time.ticks_diff(time.ticks_ms(), t0) < 120:
        if u0.any():
            chunk = u0.read()
            if chunk:
                buf += chunk
        time.sleep_ms(5)
    radar_bytes = len(buf)
    if b"\xaa\xff\x03\x00" in buf:
        radar_valid = True
except Exception:
    pass

result = {
    "sda_gp4_pullup": sda_ok,
    "scl_gp5_pullup": scl_ok,
    "pulled_up_gps": pulled_up_gps,
    "gnd_short_gps": gnd_short_gps,
    "i2c_normal": [hex(x) for x in norm_devs],
    "i2c_swapped": [hex(x) for x in swap_devs],
    "qmc_xyz": qmc_xyz,
    "radar_bytes": radar_bytes,
    "radar_valid": radar_valid,
}
print("DIAG_JSON:" + json.dumps(result))
"""

GP_TO_LEFT_ROW = {
    0: "Row 1 (Pin 1, GP0)",
    1: "Row 2 (Pin 2, GP1)",
    2: "Row 4 (Pin 4, GP2 - Orange W6)",
    3: "Row 5 (Pin 5, GP3 - SHOULD BE EMPTY!)",
    4: "Row 6 (Pin 6, GP4 - Blue W3 SDA)",
    5: "Row 7 (Pin 7, GP5 - Yellow W4 SCL)",
    6: "Row 9 (Pin 9, GP6)",
    7: "Row 10 (Pin 10, GP7)",
    8: "Row 11 (Pin 11, GP8 - Purple W5 TX)",
    9: "Row 12 (Pin 12, GP9)",
    10: "Row 14 (Pin 14, GP10)",
    11: "Row 15 (Pin 15, GP11)",
}


def run_pico_probe(mpremote_bin: str) -> dict | None:
    cmd = mpremote_bin.split() + ["exec", PICO_PROBE_CODE]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        for line in res.stdout.splitlines():
            if line.startswith("DIAG_JSON:"):
                return json.loads(line.split("DIAG_JSON:", 1)[1].strip())
    except Exception:
        return None
    return None


def diagnose_pico_and_breadboard(mpremote_bin: str) -> tuple[bool, dict | None]:
    banner("STAGE 1 & 2A: PICO 2 USB & BREADBOARD WIRING (W1–W7 + GY-271 COMPASS)")

    # 1. Check BOOTSEL mode vs USB Serial
    if Path("/Volumes/RP2350").exists() or Path("/Volumes/RPI-RP2").exists():
        fail("Pico 2 is currently in UF2 BOOTSEL mass-storage mode (/Volumes/RP2350).")
        fix("Unplug the Micro-USB cable and plug it back in WITHOUT holding the white BOOTSEL button.")
        return False, None

    serial_ports = glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*")
    if not serial_ports:
        fail("Pico 2 is NOT detected on any USB port (/dev/cu.usbmodem* or /dev/ttyACM*).")
        fix("1. Push the black Micro-USB plug (CORD 1) firmly all the way into the Pico 2 past the 2 metal barbs.")
        fix("2. Make sure you are using a data-capable USB cable (not a charge-only cable).")
        return False, None

    ok(f"Pico 2 USB Serial detected at: {', '.join(serial_ports)}")

    # 2. Run electrical pin probe on Pico 2
    probe = run_pico_probe(mpremote_bin)
    if not probe:
        fail("Could not execute MicroPython probe on Pico 2 (another terminal may have mpremote open).")
        fix("Close any other running `mpremote` session (press Ctrl+C in other terminals) and re-run this script.")
        return False, None

    sda_ok = probe["sda_gp4_pullup"]
    scl_ok = probe["scl_gp5_pullup"]
    pulled_up = probe["pulled_up_gps"]
    gnd_shorts = probe["gnd_short_gps"]
    i2c_norm = probe["i2c_normal"]
    i2c_swap = probe["i2c_swapped"]

    # Check for misplaced wires on wrong Pico rows
    unexpected_pullups = [gp for gp in pulled_up if gp not in (4, 5)]
    if unexpected_pullups:
        for gp in unexpected_pullups:
            row_desc = GP_TO_LEFT_ROW.get(gp, f"GP{gp}")
            fail(f"MISPLACED WIRE DETECTED: External 3.3V pull-up seen on {row_desc}!")
            if gp == 3:
                fix("Your Blue (SDA) or Yellow (SCL) wire is plugged into Row 5 (GP3) instead of Row 6 (GP4) or Row 7 (GP5)! Move it down 1 hole.")
            elif gp in (6, 7):
                fix(f"Your Yellow (SCL) wire is plugged too low into {row_desc}! Move it up to Row 7 (Hole a7/b7 = GP5).")

    # Check if SDA or SCL is shorted to GND (e.g. plugged into Row 3, Row 8, or Row 25 GND)
    if 4 in gnd_shorts:
        fail("Blue SDA wire (GP4, Row 6) is SHORTED TO GROUND (0V)!")
        fix("Check that the bottom end of the Blue wire is in Hole f27 (Row 27), NOT Hole f25 (Row 25 GND)!")
    if 5 in gnd_shorts:
        fail("Yellow SCL wire (GP5, Row 7) is SHORTED TO GROUND (0V)!")
        fix("1. Check the top end of the Yellow wire: make sure it is in Row 7 (GP5), NOT Row 8 (Pin 8 is GND!).")
        fix("2. Check the bottom end of the Yellow wire: make sure it is in Hole f26 (Row 26), NOT Hole f25 (Row 25 is Black GND!).")

    # Evaluate I2C0 and the 4 compass pins (VCC, GND, SCL, SDA)
    if "0xd" in i2c_norm or "0x2c" in i2c_norm:
        det_addr = "0x2c (QMC5883P)" if "0x2c" in i2c_norm else "0x0d (QMC5883L)"
        ok(f"GY-271 Magnetometer detected at {det_addr} on I2C0! All 4 wires (Red, Black, Yellow, Blue) & solder joints are 100% solid.")
        if isinstance(probe["qmc_xyz"], list):
            x, y, z, mag = probe["qmc_xyz"]
            ok(f"Live Magnetometer Vector Readout: X={x}, Y={y}, Z={z}, |B|={mag} (Healthy!)")
        return True, probe

    if "0xd" in i2c_swap or "0x2c" in i2c_swap:
        fail("SWAPPED WIRES DETECTED: GY-271 Magnetometer responded when SDA and SCL were swapped in software!")
        fix("Your Blue (SDA) and Yellow (SCL) wires are swapped! Ensure:")
        fix("  - Yellow (W4 SCL): Row 7 (Hole a7/b7) -> Hole f26 (Row 26, 3rd compass pin)")
        fix("  - Blue   (W3 SDA): Row 6 (Hole a6/b6) -> Hole f27 (Row 27, 4th compass pin)")
        return False, probe

    # Pin-by-pin fault isolation when 0x0d / 0x2c is NOT found:
    print(f"\n  {BOLD}--- Pin-by-Pin Electrical Continuity Breakdown (GY-271 Compass) ---{RESET}")
    if sda_ok == 1 and scl_ok == 0:
        ok("Wire W1 (Red VCC, Row 5 j5 -> Row 24 f24 -> Compass Pin 1 VCC):   CONNECTED (3.3V verified via SDA pull-up)")
        ok("Wire W3 (Blue SDA, Row 6 a6 -> Row 27 f27 -> Compass Pin 4 SDA):  CONNECTED (3.3V pull-up verified on GP4)")
        fail("Wire W4 (Yellow SCL, Row 7 a7 -> Row 26 f26 -> Compass Pin 3 SCL): OPEN CIRCUIT (0V on GP5 — NOT TOUCHING!)")
        fix("The ONLY broken connection is on the YELLOW (SCL) path (`Row 7` -> `Hole f26` -> `3rd/Middle Compass Pin`).")
        fix("Why: If the blue GY-271 board is sitting on the 5-pin header without solder, the 0.64mm pin can float inside the 1.0mm hole.")
        fix("WARNING: NEVER bend or twist the short brass header pins with pliers — they are brittle and will snap!")
        fix("Option A (Best Practice): Solder the 4 active pins (VCC, GND, SCL, SDA) on the blue GY-271 board.")
        fix("Option B (Zero-Solder Workaround 1 — Foil/Toothpick Wedge): Wedge a tiny sliver of aluminum foil or a wooden toothpick tip")
        fix("         into the 3rd silver hole (SCL) on the blue GY-271 board so the pin presses tightly against the silver ring.")
        fix("Option C (Zero-Solder Workaround 2 — Direct Jumper Pinning): Skip the 5-pin header strip and push the 4 jumper wire pins")
        fix("         (Red, Black, Yellow, Blue) directly through the 4 holes of the blue GY-271 board into Column j (j24..j27)!")
    elif sda_ok == 0 and scl_ok == 1:
        ok("Wire W1 (Red VCC, Row 5 j5 -> Row 24 f24 -> Compass Pin 1 VCC):    CONNECTED (3.3V verified via SCL pull-up)")
        ok("Wire W4 (Yellow SCL, Row 7 a7 -> Row 26 f26 -> Compass Pin 3 SCL): CONNECTED (3.3V pull-up verified on GP5)")
        fail("Wire W3 (Blue SDA, Row 6 a6 -> Row 27 f27 -> Compass Pin 4 SDA):  OPEN CIRCUIT (0V on GP4 — NOT TOUCHING!)")
        fix("The ONLY broken connection is on the BLUE (SDA) path (`Row 6` -> `Hole f27` -> `4th Compass Pin`).")
        fix("Step 1: Pull the bottom end of the Blue wire out of Hole f27 and inspect if the metal pin tip is bent into a hook.")
        fix("Step 2: Touch/wedge the Blue wire tip directly into the 4th silver hole (SDA) on top of the blue GY-271 board.")
    elif sda_ok == 0 and scl_ok == 0:
        fail("NEITHER SDA (Blue) NOR SCL (Yellow) sees 3.3V from the GY-271 compass board!")
        fix("1. Check Wire W1 (Red 3.3V Power): Top end MUST be in Hole j5 (Row 5 right side of Pico 2), bottom end in Hole f24 (Row 24).")
        fix("2. Check the 1st (top) gold pin (VCC) on the blue GY-271 compass board at Hole j24: press the blue board down/sideways so Pin 1 (VCC) makes contact.")
        fix("3. Confirm Hole-Counting at the bottom of the breadboard:")
        fix("   - Column f (under the 4 wires): MUST have 3 empty bottom holes (f28, f29, f30).")
        fix("   - Column j (under the 5-pin compass): MUST have 2 empty bottom holes (j29, j30).")
    elif sda_ok == 1 and scl_ok == 1:
        ok("Wire W1 (Red VCC, Row 24):    CONNECTED (3.3V verified)")
        ok("Wire W4 (Yellow SCL, Row 26): CONNECTED (3.3V pull-up verified on GP5)")
        ok("Wire W3 (Blue SDA, Row 27):   CONNECTED (3.3V pull-up verified on GP4)")
        fail("Wire W2 (Black GND, Row 3 j3 -> Row 25 f25 -> Compass 2nd Pin GND): OPEN CIRCUIT!")
        fix("Because VCC, SDA, and SCL are all live at 3.3V yet the chip cannot pull SDA low to answer,")
        fix("the ONLY disconnected pin is GROUND (Black wire W2 at Row 3 Hole j3 -> Row 25 Hole f25 -> 2nd Compass Pin GND)!")
        fix("Press both ends of the Black wire (j3 and f25) and touch/wedge the 2nd hole down (GND) on the blue GY-271 board.")

    return False, probe


def live_pin_watch_loop(mpremote_bin: str) -> bool:
    banner("LIVE INTERACTIVE WIRING MONITOR (Wiggle/Touch Wires — Auto-Detects Fix!)")
    print("  Watching Pico 2 pins in real time (updates 4x/sec). Press Ctrl+C to stop.\n")

    watch_code = r"""
from machine import Pin, I2C, SoftI2C
import time, struct, math

def check_ext_pullup(gp):
    p = Pin(gp, Pin.OUT, value=0)
    time.sleep_ms(2)
    p.init(Pin.IN, Pin.PULL_DOWN)
    time.sleep_ms(2)
    val = p.value()
    p.init(Pin.IN, Pin.PULL_UP)
    return val

while True:
    sda = check_ext_pullup(4)
    scl = check_ext_pullup(5)
    i2c = SoftI2C(sda=Pin(4), scl=Pin(5), freq=100000)
    devs = i2c.scan()
    swap = SoftI2C(sda=Pin(5), scl=Pin(4), freq=100000).scan()
    if 0x0D in devs or 0x2C in devs:
        print("\nBINGO_CONNECTED_0x0D")
        hw = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
        if 0x0D in devs:
            hw.writeto_mem(0x0D, 0x0A, b'\x80')
            time.sleep_ms(10)
            hw.writeto_mem(0x0D, 0x0B, b'\x01')
            hw.writeto_mem(0x0D, 0x09, b'\x1D')
            for _ in range(15):
                time.sleep_ms(150)
                if hw.readfrom_mem(0x0D, 0x06, 1)[0] & 1:
                    x, y, z = struct.unpack('<hhh', hw.readfrom_mem(0x0D, 0x00, 6))
                    mag = int(math.sqrt(x*x + y*y + z*z))
                    print(f"SAMPLE: X={x} Y={y} Z={z} |B|={mag}")
        else:
            hw.writeto_mem(0x2C, 0x29, b'\x06')
            hw.writeto_mem(0x2C, 0x0B, b'\x08')
            hw.writeto_mem(0x2C, 0x0A, b'\xCD')
            for _ in range(15):
                time.sleep_ms(150)
                if hw.readfrom_mem(0x2C, 0x09, 1)[0] & 1:
                    x, y, z = struct.unpack('<hhh', hw.readfrom_mem(0x2C, 0x01, 6))
                    mag = int(math.sqrt(x*x + y*y + z*z))
                    print(f"SAMPLE: X={x} Y={y} Z={z} |B|={mag}")
        break
    hint = ""
    if 0x0D in swap or 0x2C in swap:
        hint = "-> SWAPPED! Swap Blue(SDA) & Yellow(SCL)!"
    elif sda == 1 and scl == 0:
        hint = "-> ONLY Yellow(SCL Row 7 / f26 / 3rd compass hole) is OPEN!"
    elif sda == 0 and scl == 1:
        hint = "-> ONLY Blue(SDA Row 6 / f27 / 4th compass hole) is OPEN!"
    elif sda == 0 and scl == 0:
        hint = "-> Red(VCC j5->f24) or 1st compass hole is OPEN!"
    elif sda == 1 and scl == 1:
        hint = "-> Black(GND j3->f25) or 2nd compass hole is OPEN!"
    print(f"STATUS|SDA={sda}|SCL={scl}|DEVS={[hex(d) for d in devs]}|{hint}")
    time.sleep_ms(220)
"""
    cmd = mpremote_bin.split() + ["exec", watch_code]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("STATUS|"):
                parts = line.split("|")
                sda_s = f"{GREEN}OK(1){RESET}" if "SDA=1" in parts[1] else f"{RED}OPEN(0){RESET}"
                scl_s = f"{GREEN}OK(1){RESET}" if "SCL=1" in parts[2] else f"{RED}OPEN(0){RESET}"
                hint = parts[4] if len(parts) > 4 else ""
                sys.stdout.write(f"\r  [LIVE] Blue SDA: {sda_s} | Yellow SCL: {scl_s} | {YELLOW}{hint}{RESET}          ")
                sys.stdout.flush()
            elif "BINGO_CONNECTED_0x0D" in line:
                print(f"\n\a\n  {GREEN}{BOLD}🎉 [✓ CONNECTED!] QMC5883L (0x0d) IS LIVE ON I2C0!{RESET}")
            elif line.startswith("SAMPLE:"):
                print(f"  {GREEN}{line}{RESET}")
        proc.wait(timeout=2)
    except KeyboardInterrupt:
        proc.terminate()
        print(f"\n  {YELLOW}[*] Live monitor stopped by user.{RESET}")
        return False
    return True


def diagnose_other_pico_sensors(probe: dict | None) -> None:
    if not probe:
        return
    banner("STAGE 2/4 OPTIONAL SENSORS: ADS1015 ADC (0x48) & HLK-LD2450 24GHz RADAR (GP0/GP1)")
    i2c_norm = probe.get("i2c_normal", [])
    if "0x48" in i2c_norm:
        ok("ADS1015/ADS1115 Geophone ADC detected at `0x48` on I2C0.")
    else:
        warn("ADS1015/ADS1115 (`0x48`) not connected on I2C0 (normal for Stage 2 magnetometer-only bench test).")

    if probe.get("radar_valid"):
        ok(f"HLK-LD2450 24GHz Radar streaming valid target frames on UART0 (`GP0/GP1`, {probe.get('radar_bytes')} bytes read).")
    elif probe.get("radar_bytes", 0) > 0:
        warn(f"UART0 (`GP0/GP1`) received {probe.get('radar_bytes')} bytes, but no `AA FF 03 00` radar header yet.")
        fix("Check if Radar TX/RX wires on Row 1 (`GP0`) and Row 2 (`GP1`) are swapped.")
    else:
        warn("HLK-LD2450 24GHz Radar not connected on `GP0/GP1` (normal for Stage 2 bench test; Pico uses `MAG_RADAR_DUTY` / `BENCH_MAG_ONLY` profile).")


def diagnose_pi5_and_camera() -> None:
    banner("STAGE 2B, STAGE 3 & STAGE 5: RASPBERRY PI 5, CAMERA RIBBON (J4), W5–W7 & FIBER DIODE")

    # 1. Check local Ethernet subnet (10.10.0.100) & Optical Carrier
    try:
        ifcfg = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=4).stdout
        if "10.10.0.100" in ifcfg:
            ok("MacBook Ethernet interface is configured with Collector IP `10.10.0.100`.")
            # Check if interface is active or no carrier
            for block in ifcfg.split("\n\n"):
                if "10.10.0.100" in block:
                    if "status: active" in block:
                        ok("Ethernet / Optical Media Converter #2 RJ45 link carrier is `ACTIVE`.")
                    elif "status: inactive" in block:
                        fail("MacBook Ethernet interface (`10.10.0.100`) shows `status: inactive` (NO LINK CARRIER)!")
                        fix("If testing Stage 2 (Copper Cat6): Plug the Cat6 cable into both the Pi 5 and MacBook Ethernet adapter, and power on the Pi 5.")
                        fix("If testing Stage 3 (Optical Fiber Diode): Check that Media Converter #2 has DIP Switch #1 `LFP = OFF` (DOWN), is powered via its +5.0V DC adapter,")
                        fix("  and that the outbound single-strand yellow OS2 fiber [P16] is clicked into Media Converter #2 `RX` (with the Silver 1x2 Splitter [P14] WHITE in #1 `TX`, BLUE in #1 `RX`, and ORANGE in Blue Coupler [P15]).")
        else:
            warn("MacBook Ethernet interface does not have `10.10.0.100` assigned yet (needed for Stage 2.6 / Stage 3 UDP alerts).")
            fix("Run `python3 pi-diode-trailcam/run_guided_bench_doctor.py` or `sudo ifconfig <enX> 10.10.0.100 netmask 255.255.255.0 up`.")
    except Exception:
        pass

    # 2. Check Collector Hub UDP 5514 & Web Dashboard TCP 8123
    try:
        with socket.create_connection(("127.0.0.1", 8123), timeout=0.8):
            ok("Collector Web Dashboard is LIVE at `http://127.0.0.1:8123`.")
    except Exception:
        warn("Collector Web Dashboard (`http://127.0.0.1:8123`) is not running yet.")
        fix("Start both Receiver & Dashboard with: `python3 pi-diode-trailcam/run_guided_bench_doctor.py --start-hub --open-browser`")

    journal_path = PROJECT_DIR / "verified_alerts" / "alerts_journal.jsonl"
    if journal_path.exists() and journal_path.stat().st_size > 0:
        lines = [ln for ln in journal_path.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
        if lines:
            try:
                last_alert = json.loads(lines[-1])
                ok(f"Verified Alerts Journal has {len(lines)} alert(s). Latest: node=`{last_alert.get('node_id')}`, camera_ok=`{last_alert.get('camera_ok')}`.")
            except Exception:
                pass

    # 3. Check if Pi 5 is reachable via mDNS (trailcam-node.local) or 10.10.0.10
    pi_host = None
    for candidate in ("trailcam-node.local", "10.10.0.10"):
        try:
            with socket.create_connection((candidate, 22), timeout=1.5):
                pi_host = candidate
                break
        except Exception:
            continue

    if not pi_host:
        warn("Raspberry Pi 5 (`trailcam-node.local` / `10.10.0.10`) is not reachable over SSH right now.")
        fix("If you are still on Step 2.5 (Pico 2 magnetometer test), this is normal—plug the 27W USB-C power supply into the Pi 5 in Step 2.6.")
        fix("If the Pi 5 IS plugged into power: confirm the SanDisk 64GB MicroSD card is pushed flush into the underside slot (gold teeth facing UP toward the green board) and wait 45s.")
        return

    ok(f"Raspberry Pi 5 is online and reachable at `{pi_host}:22`.")

    # 4. Probe Camera Module 3 NoIR Wide (IMX708) & UART (/dev/ttyAMA0) over non-interactive SSH if key/mux available
    ssh_cmd = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", f"pi@{pi_host}",
        "rpicam-hello --list-cameras 2>&1 || libcamera-hello --list-cameras 2>&1; ls -l /dev/ttyAMA0 /dev/serial0 2>&1"
    ]
    try:
        ssh_res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=6)
        if ssh_res.returncode == 0:
            out = ssh_res.stdout
            if "imx708" in out.lower():
                ok("Camera Module 3 NoIR Wide (`imx708`) is detected on Raspberry Pi 5 `J4 (CAM/DISP 0)`!")
            elif "no cameras available" in out.lower():
                fail("Raspberry Pi 5 does NOT detect the Camera Module 3 NoIR Wide (`No cameras available`)!")
                fix("Check both ends of the 200mm Orange Camera Ribbon [P06] (with Pi 5 UNPLUGGED from power):")
                fix("  1. Pi 5 End (Narrow 22-pin `Mini | 200mm` in upper slot `J4 CAM/DISP 0`):")
                fix("     - SHINY GOLD TEETH must face RIGHT (toward the silver Ethernet port).")
                fix("     - BLACK STIFFENER must face LEFT (toward the Micro-HDMI ports).")
                fix("  2. Camera End (Wide 15-pin `CE FC` on the back of Camera Module 3):")
                fix("     - SHINY GOLD TEETH must face DOWN against the black camera circuit board.")
                fix("     - BLACK STIFFENER + white `CE FC` text must face UP (on the brown latch side).")
                fix("  3. Push both ribbon ends 2mm deep so zero gold teeth show outside, and press both brown latches flush.")
            if "/dev/ttyAMA0" in out:
                ok("Raspberry Pi 5 Hardware UART (`/dev/ttyAMA0` — Pin 10 GPIO15 RX for Purple wire W5) is enabled.")
            else:
                warn("Raspberry Pi 5 Hardware UART (`/dev/ttyAMA0`) is not enabled yet.")
                fix(f"Run: `ssh pi@{pi_host} \"sudo raspi-config nonint do_serial_hw 0 && sudo raspi-config nonint do_serial_cons 1 && sudo reboot\"`")
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline Zero-LLM Hardware & Wiring Diagnostic Doctor")
    parser.add_argument("--watch", action="store_true", help="Stay in continuous live pin monitor mode")
    parser.add_argument("--once", action="store_true", help="Run a single diagnostic pass and exit without live monitor")
    args = parser.parse_args()

    mpremote_bin = find_mpremote()
    compass_ok, probe = diagnose_pico_and_breadboard(mpremote_bin)
    diagnose_other_pico_sensors(probe)
    diagnose_pi5_and_camera()

    if args.watch or (not compass_ok and not args.once):
        live_pin_watch_loop(mpremote_bin)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

