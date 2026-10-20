# File: pico_gatekeeper/test_qmc5883l.py
# Description: Quick 5-second I2C & Magnetometer Benchtop Verification Script
# Target: Raspberry Pi Pico / Pico 2 (MicroPython)
from machine import Pin, I2C
import time
import math
import struct

# Initialize I2C0 on GP4 (SDA) and GP5 (SCL)
i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=100000)

print("\n" + "=" * 50)
print("  QMC5883L MAGNETOMETER HARDWARE VERIFICATION")
print("=" * 50)

# 1. Scan I2C bus
devices = i2c.scan()
hex_devs = [hex(d) for d in devices]
print(f"[*] I2C Bus Scan: Detected devices: {hex_devs}")

def check_pullup(gp_num):
    p = Pin(gp_num, Pin.OUT, value=0)
    time.sleep_ms(2)
    p.init(Pin.IN, Pin.PULL_DOWN)
    time.sleep_ms(2)
    v = p.value()
    p.init(Pin.IN, Pin.PULL_UP)
    return v

QMC_ADDR = 0x0D
QMC_P_ADDR = 0x2C
MAG_THRESHOLD_DELTA = 1200

if (QMC_ADDR not in devices) and (QMC_P_ADDR not in devices):
    sda_ok = check_pullup(4)
    scl_ok = check_pullup(5)
    i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=100000)
    print(f"[!] GY-271 (0x0d/0x2c) not ready yet -> Pin Continuity: SDA(Blue GP4)={'OK(1)' if sda_ok else 'OPEN(0)'} | SCL(Yellow GP5)={'OK(1)' if scl_ok else 'OPEN(0)'}")
    print("[*] LIVE PIN MONITOR ACTIVE (Press Ctrl+C to stop):")
    print("    -> Wiggle/press Yellow wire (Row 7 & Hole f26) or touch the 3rd middle gold pin (SCL) on the blue compass board...")
    while (QMC_ADDR not in devices) and (QMC_P_ADDR not in devices):
        sda_ok = check_pullup(4)
        scl_ok = check_pullup(5)
        i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=100000)
        devices = i2c.scan()
        if (QMC_ADDR in devices) or (QMC_P_ADDR in devices):
            print("\n[+] CONNECTED! SCL=OK(1) & GY-271 Magnetometer detected on I2C0!")
            break
        print(f"    [Waiting...] SDA(Blue)={'OK(1)' if sda_ok else 'OPEN(0)'} | SCL(Yellow)={'OK(1)' if scl_ok else 'OPEN(0)'} | I2C={[hex(d) for d in devices]}   ", end="\r")
        time.sleep_ms(250)

if (QMC_ADDR in devices) or (QMC_P_ADDR in devices):
    is_p_variant = (QMC_P_ADDR in devices) and (QMC_ADDR not in devices)
    active_addr = QMC_P_ADDR if is_p_variant else QMC_ADDR
    chip_name = "QMC5883P (0x2c)" if is_p_variant else "QMC5883L (0x0d)"
    print(f"[+] SUCCESS: Found {chip_name} on I2C0 bus!")
    
    # 2. Configure QMC5883L (0x0D) or QMC5883P (0x2C) in continuous 200Hz mode
    try:
        if is_p_variant:
            i2c.writeto_mem(active_addr, 0x29, b'\x06') # Sign definition
            i2c.writeto_mem(active_addr, 0x0B, b'\x0C') # Set/Reset on, 2G high-sensitivity range
            i2c.writeto_mem(active_addr, 0x0A, b'\xCD') # Continuous mode, 200Hz ODR
        else:
            i2c.writeto_mem(active_addr, 0x0A, b'\x80') # Soft reset
            time.sleep_ms(10)
            i2c.writeto_mem(active_addr, 0x0B, b'\x01') # Set SET/RESET period
            i2c.writeto_mem(active_addr, 0x09, b'\x1D') # Mode: 512 OSR, 8G, 200Hz, Continuous
        print(f"[+] {chip_name} initialized in continuous measurement mode.")
        print("[*] Streaming live magnetic field... (Wave a steel screwdriver [T03] near the sensor!)\n")
        
        baseline_mag = None
        status_reg = 0x09 if is_p_variant else 0x06
        data_reg = 0x01 if is_p_variant else 0x00
        while True:
            # Check data ready (DRDY) flag
            status = i2c.readfrom_mem(active_addr, status_reg, 1)[0]
            if status & 0x01: # Data ready
                raw = i2c.readfrom_mem(active_addr, data_reg, 6)
                x, y, z = struct.unpack('<hhh', raw)
                mag = math.sqrt(x*x + y*y + z*z)
                if baseline_mag is None:
                    baseline_mag = mag
                delta = abs(mag - baseline_mag)
                if delta < (MAG_THRESHOLD_DELTA * 0.5):
                    baseline_mag = (0.98 * baseline_mag) + (0.02 * mag)
                bar = "#" * min(30, int(mag / 150))
                trig = " <-- [MAG TRIGGER]" if delta >= MAG_THRESHOLD_DELTA else ""
                print(f"  X:{x:6d}  Y:{y:6d}  Z:{z:6d}  |  |B|:{mag:6.0f} (d:{delta:5.0f}) [{bar:<30}]{trig}")
            time.sleep_ms(150)
    except KeyboardInterrupt:
        print("\n[*] Test stopped by user.")
    except Exception as e:
        print(f"[!] Read error: {e}")

