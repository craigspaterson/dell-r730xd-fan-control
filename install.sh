#!/bin/bash
# =============================================================================
# install.sh
# Installs Dell R730xd Fan Control on a Proxmox host
# Run as root on the Proxmox host
# =============================================================================

set -euo pipefail

INSTALL_DIR="/opt/dell-fan-control"
CONFIG_DIR="/etc/dell-fan-control"
SERVICE_DIR="/etc/systemd/system"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

echo "============================================="
echo " Dell R730xd Fan Control — Installer"
echo "============================================="
echo ""

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Must run as root"
    exit 1
fi

# Check dependencies
for cmd in ipmitool nvidia-smi python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' not found. Please install it first."
        exit 1
    fi
done

# Check PyYAML
if ! python3 -c "import yaml" &>/dev/null; then
    echo "Installing PyYAML..."
    apt-get install -y python3-yaml
fi

echo "Dependencies OK"
echo ""

# ---------------------------------------------------------------------------
# Install files
# ---------------------------------------------------------------------------

echo "[1/4] Installing scripts to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp fan_control.py "$INSTALL_DIR/"
cp watchdog.sh "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/fan_control.py"
chmod +x "$INSTALL_DIR/watchdog.sh"
echo "    Done."

echo "[2/4] Installing config to $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"
if [[ -f "$CONFIG_DIR/config.yaml" ]]; then
    echo "    Existing config found — backing up to config.yaml.bak"
    cp "$CONFIG_DIR/config.yaml" "$CONFIG_DIR/config.yaml.bak"
fi
cp config.yaml "$CONFIG_DIR/"
echo "    Done."

echo "[3/4] Installing systemd services"
cp dell-fan-control.service "$SERVICE_DIR/"
cp dell-fan-control-watchdog.service "$SERVICE_DIR/"
systemctl daemon-reload
echo "    Done."

echo "[4/4] Enabling and starting services"
systemctl enable dell-fan-control.service
systemctl enable dell-fan-control-watchdog.service
systemctl restart dell-fan-control.service
systemctl restart dell-fan-control-watchdog.service
echo "    Done."

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

echo ""
echo "============================================="
echo " Installation Complete"
echo "============================================="
echo ""
echo "Service status:"
systemctl is-active dell-fan-control.service && echo "  fan-control:  RUNNING" || echo "  fan-control:  FAILED"
systemctl is-active dell-fan-control-watchdog.service && echo "  watchdog:     RUNNING" || echo "  watchdog:     FAILED"
echo ""
echo "Useful commands:"
echo "  systemctl status dell-fan-control"
echo "  journalctl -u dell-fan-control -f"
echo "  tail -f /var/log/dell-fan-control.log"
echo "  cat /var/run/fan_control.heartbeat"
echo ""
echo "Config: $CONFIG_DIR/config.yaml"
echo "Logs:   /var/log/dell-fan-control.log"
echo ""
