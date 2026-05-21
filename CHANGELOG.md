# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.1.0] - 2026-05-21

### Added
- CPU temperature monitoring via `ipmitool sdr type Temperature` as an independent fan control input ([#17](https://github.com/craigspaterson/dell-r730xd-fan-control/issues/17))
- Per-source threshold tables for GPU and CPU — fan speed is set to the maximum required by either source
- Per-source configurable `failure_fallback_percent` (default 80%) applied when a temperature source cannot be read
- `deep_merge()` for correct nested config merging (previously shallow merge could drop nested user overrides)

### Changed
- Config structure: `thresholds:` replaced by `sources.gpu.thresholds` and `sources.cpu.thresholds`
- GPU read failure now jumps to `failure_fallback_percent` instead of holding current fan speed — consistent with CPU failure behaviour
- Startup baseline fan speed now uses `max()` across sources rather than `min()`, preventing an unsafe low start while iDRAC auto control is disabled
- Log output now shows both GPU and CPU temps and resolved label on every poll cycle

### Fixed
- `yaml.safe_load()` result normalised to `{}` on empty config files; non-mapping types raise a clear error on startup
- `ipmitool sdr` output parsed correctly: 3-field format (`name | reading | status`) — previous code required 5 fields and read the wrong field, causing CPU temps to always be missed and the daemon to run permanently in fallback mode

### Deprecated
- Flat `thresholds:` config key — automatically migrated to `sources.gpu.thresholds` on startup with a logged warning

## [1.0.1] - 2026-05-18

### Fixed
- Release workflow rewritten to use `gh` CLI to avoid backtick interpolation error in release notes ([#4](https://github.com/craigspaterson/dell-r730xd-fan-control/issues/4))
- Release workflow now skips tag creation if tag already exists ([#4](https://github.com/craigspaterson/dell-r730xd-fan-control/issues/4))

### Added
- Bug report and feature request issue templates
- `requirements.txt` to allow Dependabot to track PyYAML dependency

### Changed
- Upgraded `actions/checkout` from v4 to v6 for Node.js 24 compatibility ([#6](https://github.com/craigspaterson/dell-r730xd-fan-control/issues/6))
- Upgraded `actions/setup-python` from v5 to v6 for Node.js 24 compatibility ([#7](https://github.com/craigspaterson/dell-r730xd-fan-control/issues/7))

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
