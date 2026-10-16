#!/usr/bin/env bash
# File: pi5_sender_node/install_pi5_fastboot.sh
# Description: Configures Raspberry Pi 5 for <5s fast boot and installs the sender service
# License: MIT
set -e

echo "[*] Stripping any macOS metadata files (._*, .DS_Store, .Spotlight-V100, .fseventsd)..."
find . /boot/firmware /opt/diode-node -name '._*' -o -name '.DS_Store' -delete 2>/dev/null || true
rm -rf /boot/firmware/.Spotlight-V100 /boot/firmware/.fseventsd /boot/firmware/.Trashes 2>/dev/null || true

echo "[*] Installing core Python & camera dependencies..."
apt-get update
apt-get install -y python3-picamera2 python3-opencv python3-nacl python3-serial
apt-get install -y hailo-all || echo "[i] hailo-all not available on this board (e.g. Pi 4 or non-Hailo OS); using CPU ONNX / Motion fallback."

echo "[*] Installing sender_node.py to /opt/diode-node..."
mkdir -p /opt/diode-node
cp sender_node.py /opt/diode-node/sender_node.py
chmod +x /opt/diode-node/sender_node.py

echo "[*] Installing systemd early-boot unit..."
cp diode-node.service /etc/systemd/system/diode-node.service
systemctl daemon-reload
systemctl enable diode-node.service

echo "[*] Disabling unnecessary services & serial login console for <5s fast boot..."
systemctl disable systemd-networkd-wait-online.service NetworkManager-wait-online.service || true
systemctl disable bluetooth.service hciuart.service ModemManager.service avahi-daemon.service || true
systemctl disable triggerhappy.service cron.service rsyslog.service || true
systemctl stop serial-getty@ttyAMA0.service serial-getty@serial0.service || true
systemctl disable serial-getty@ttyAMA0.service serial-getty@serial0.service || true

BOOT_CFG="/boot/firmware/config.txt"
if [ ! -f "$BOOT_CFG" ] && [ -f "/boot/config.txt" ]; then
    BOOT_CFG="/boot/config.txt"
fi
if [ -f "$BOOT_CFG" ]; then
    echo "[*] Ensuring PL011 UART0 (GPIO14/15, Pins 8/10) is enabled in $BOOT_CFG..."
    grep -q "^dtparam=uart0=on" "$BOOT_CFG" || echo "dtparam=uart0=on" >> "$BOOT_CFG"
    grep -q "^enable_uart=1" "$BOOT_CFG" || echo "enable_uart=1" >> "$BOOT_CFG"
fi

CMDLINE_CFG="/boot/firmware/cmdline.txt"
if [ ! -f "$CMDLINE_CFG" ] && [ -f "/boot/cmdline.txt" ]; then
    CMDLINE_CFG="/boot/cmdline.txt"
fi
if [ -f "$CMDLINE_CFG" ]; then
    sed -i 's/console=serial0,[0-9]* //g; s/console=ttyAMA0,[0-9]* //g' "$CMDLINE_CFG" || true
fi

echo "[*] Done! Enable OverlayFS (read-only root) in raspi-config after provisioning node keys."
