# Dell R730xd Fan Control

[![CI](https://github.com/craigspaterson/dell-r730xd-fan-control/actions/workflows/ci.yml/badge.svg)](https://github.com/craigspaterson/dell-r730xd-fan-control/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/craigspaterson/dell-r730xd-fan-control)](https://github.com/craigspaterson/dell-r730xd-fan-control/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Automatic GPU-aware fan control for the Dell PowerEdge R730xd running third-party GPUs (e.g. NVIDIA Tesla P40) on Proxmox.

> **Warning**
> This software takes manual control of your server's fan speeds via IPMI, bypassing iDRAC's automatic fan management. Misconfigured thresholds or a daemon failure can result in insufficient cooling and thermal damage to your hardware. Review and test your configuration before running under sustained load. Manual IPMI fan control may also affect your Dell support agreement. This software is provided as-is with no warranty — see [LICENSE](LICENSE).

## Problem

Dell's iDRAC does not recognise non-certified PCIe cards. When a third-party GPU is installed, iDRAC's default fan curve does not respond adequately to GPU heat output, causing the GPU to reach unsafe temperatures (85°C+) under inference load.

## Solution

A Python daemon running on the Proxmox host that:

- Reads GPU temperature every 30 seconds via `nvidia-smi`
- Adjusts chassis fan speed via `ipmitool` based on configurable thresholds
- Runs as a systemd service with automatic restart
- Includes a watchdog that sets fans to a safe speed if the daemon stalls
- Restores iDRAC automatic fan control on clean shutdown

## Hardware

| Component | Details |
|-----------|---------|
| Server | Dell PowerEdge R730xd |
| GPU | NVIDIA Tesla P40 24GB |
| Host OS | Proxmox VE (Debian Trixie base) |
| iDRAC | iDRAC8 Express |

## Temperature / Fan Profile

| GPU Temp | Fan Speed | Label |
|----------|-----------|-------|
| < 50°C | 30% | Idle |
| 50–65°C | 50% | Light load |
| 65–75°C | 70% | Moderate load |
| 75–85°C | 85% | Heavy load |
| > 85°C | 100% | Emergency |

All thresholds and fan speeds are configurable in `config.yaml`.

## Project Structure

```
dell-r730xd-fan-control/
├── README.md                          # This file
├── config.yaml                        # Tunable thresholds and settings
├── fan_control.py                     # Main daemon
├── watchdog.sh                        # Heartbeat watchdog script
├── install.sh                         # Installer for Proxmox host
├── dell-fan-control.service           # Systemd unit for main daemon
└── dell-fan-control-watchdog.service  # Systemd unit for watchdog
```

## Prerequisites

On the Proxmox host:

```bash
apt install -y ipmitool python3-yaml
```

NVIDIA drivers must already be installed and `nvidia-smi` must be functional.

## Installation

### 1. Clone the repo on the Proxmox host

```bash
git clone https://github.com/craigspaterson/dell-r730xd-fan-control.git
cd dell-r730xd-fan-control
```

### 2. Run the installer

```bash
chmod +x install.sh
./install.sh
```

The installer will:
- Copy scripts to `/opt/dell-fan-control/`
- Copy config to `/etc/dell-fan-control/config.yaml`
- Install and enable systemd services
- Start the daemon immediately

### 3. Verify

```bash
systemctl status dell-fan-control
journalctl -u dell-fan-control -f
```

## Configuration

Edit `/etc/dell-fan-control/config.yaml` to tune thresholds and fan speeds.

After editing, restart the service:

```bash
systemctl restart dell-fan-control
```

Key settings:

```yaml
polling_interval_seconds: 30   # How often to check GPU temp

thresholds:
  - max_temp: 50
    fan_percent: 30
    label: idle
  # ... add or adjust as needed
```

## Updating

```bash
cd /path/to/dell-r730xd-fan-control
git pull
./install.sh
```

The installer backs up your existing config before overwriting.

## Useful Commands

```bash
# Service status
systemctl status dell-fan-control
systemctl status dell-fan-control-watchdog

# Live logs
journalctl -u dell-fan-control -f
tail -f /var/log/dell-fan-control.log

# Check heartbeat (updated every poll cycle)
cat /var/run/fan_control.heartbeat

# Manually set fan speed (percent)
ipmitool raw 0x30 0x30 0x01 0x00                  # enable manual control
ipmitool raw 0x30 0x30 0x02 0xff 0x1e             # 30%
ipmitool raw 0x30 0x30 0x02 0xff 0x50             # 80%
ipmitool raw 0x30 0x30 0x02 0xff 0x64             # 100%

# Restore iDRAC automatic fan control
ipmitool raw 0x30 0x30 0x01 0x01

# Check GPU temperature
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits
```

## Fan Speed Reference

| Percent | Hex value |
|---------|-----------|
| 20% | 0x14 |
| 30% | 0x1e |
| 50% | 0x32 |
| 60% | 0x3c |
| 70% | 0x46 |
| 75% | 0x4b |
| 80% | 0x50 |
| 85% | 0x56 |
| 100% | 0x64 |

## Watchdog

The watchdog monitors the heartbeat file written by the daemon every poll cycle. If the file is not updated within 5 minutes, the watchdog:

1. Sets fans to 80% (safe fallback)
2. Restarts the `dell-fan-control` service

## License

MIT
