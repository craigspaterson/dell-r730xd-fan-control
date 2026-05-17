# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.0.0] - 2026-05-17

### Added
- Python daemon (`fan_control.py`) that polls GPU temperature every 30 seconds via `nvidia-smi`
- Fan speed control via `ipmitool` IPMI raw commands based on configurable thresholds
- Third-party PCIe fan response enabled on startup to prevent iDRAC from overriding manual control
- Heartbeat file written each poll cycle for watchdog monitoring
- Systemd service unit (`dell-fan-control.service`) with automatic restart
- Watchdog service (`dell-fan-control-watchdog.service`) that sets fans to 80% and restarts the daemon if the heartbeat stalls
- Installer script (`install.sh`) for Proxmox hosts
- Configurable thresholds and fan speeds via `config.yaml`
- Clean shutdown restores iDRAC automatic fan control

### Fixed
- Removed `WatchdogSec=120` from service unit — daemon does not call `sd_notify`, causing systemd to kill it every 2 minutes ([#1](https://github.com/craigspaterson/dell-r730xd-fan-control/issues/1))
- `percent_to_hex` was scaling fan speed to 0–255 instead of 0–100, causing all fan speed commands above 39% to fail ([#2](https://github.com/craigspaterson/dell-r730xd-fan-control/issues/2))
