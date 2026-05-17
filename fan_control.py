#!/usr/bin/env python3
"""
Dell R730xd Fan Control Daemon
Monitors GPU temperature via nvidia-smi and adjusts fan speed
via ipmitool based on configurable thresholds.

Designed for Dell PowerEdge R730xd with third-party GPUs
(e.g. NVIDIA Tesla P40) that iDRAC doesn't natively support.
"""

import subprocess
import time
import logging
import sys
import signal
import os
from pathlib import Path
from datetime import datetime

import yaml


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_level: str, log_file: str | None) -> logging.Logger:
    logger = logging.getLogger("fan_control")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "polling_interval_seconds": 30,
    "heartbeat_file": "/var/run/fan_control.heartbeat",
    "log_level": "INFO",
    "log_file": "/var/log/dell-fan-control.log",
    "fan": {
        "manual_control_command": "ipmitool raw 0x30 0x30 0x01 0x00",
        "set_speed_command": "ipmitool raw 0x30 0x30 0x02 0xff {hex_speed}",
        "restore_auto_command": "ipmitool raw 0x30 0x30 0x01 0x01",
        "third_party_pcie_command": "ipmitool raw 0x30 0xce 0x00 0x16 0x05 0x00 0x00 0x00 0x05 0x00 0x01 0x00 0x00",
    },
    "thresholds": [
        {"max_temp": 50,  "fan_percent": 30,  "label": "idle"},
        {"max_temp": 65,  "fan_percent": 50,  "label": "light"},
        {"max_temp": 75,  "fan_percent": 70,  "label": "moderate"},
        {"max_temp": 85,  "fan_percent": 85,  "label": "heavy"},
        {"max_temp": 999, "fan_percent": 100, "label": "emergency"},
    ],
}


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        return DEFAULT_CONFIG

    with open(path) as f:
        user_config = yaml.safe_load(f)

    # Deep merge user config over defaults
    config = DEFAULT_CONFIG.copy()
    config.update(user_config)
    return config


# ---------------------------------------------------------------------------
# IPMI / GPU helpers
# ---------------------------------------------------------------------------

def run_command(cmd: str, logger: logging.Logger) -> tuple[int, str]:
    """Run a shell command, return (returncode, output)."""
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {cmd}")
        return -1, ""
    except Exception as e:
        logger.error(f"Command failed: {cmd} — {e}")
        return -1, ""


def get_gpu_temperature(logger: logging.Logger) -> int | None:
    """Query GPU temperature via nvidia-smi. Returns degrees C or None."""
    rc, output = run_command(
        "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits",
        logger,
    )
    if rc != 0 or not output:
        return None
    try:
        return int(output.strip())
    except ValueError:
        logger.error(f"Could not parse GPU temp from: {output!r}")
        return None


def percent_to_hex(percent: int) -> str:
    """Convert fan percentage (0-100) to hex string for ipmitool."""
    value = max(0, min(100, percent))
    return hex(round(value * 255 / 100))


def set_fan_speed(percent: int, config: dict, logger: logging.Logger) -> bool:
    """Set fan speed to given percentage via ipmitool."""
    hex_speed = percent_to_hex(percent)
    cmd = config["fan"]["set_speed_command"].format(hex_speed=hex_speed)
    rc, _ = run_command(cmd, logger)
    return rc == 0


def enable_manual_fan_control(config: dict, logger: logging.Logger) -> bool:
    """Disable iDRAC automatic fan control."""
    rc, _ = run_command(config["fan"]["manual_control_command"], logger)
    return rc == 0


def enable_third_party_pcie(config: dict, logger: logging.Logger) -> bool:
    """Tell iDRAC a third-party PCIe card is installed."""
    rc, _ = run_command(config["fan"]["third_party_pcie_command"], logger)
    return rc == 0


def restore_auto_fan_control(config: dict, logger: logging.Logger) -> bool:
    """Re-enable iDRAC automatic fan control (used on clean exit)."""
    rc, _ = run_command(config["fan"]["restore_auto_command"], logger)
    return rc == 0


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def get_target_fan_speed(temp: int, thresholds: list[dict]) -> tuple[int, str]:
    """
    Given a GPU temperature, return (fan_percent, label)
    based on the configured threshold table.
    Thresholds must be sorted ascending by max_temp.
    """
    for threshold in sorted(thresholds, key=lambda t: t["max_temp"]):
        if temp <= threshold["max_temp"]:
            return threshold["fan_percent"], threshold["label"]
    # Fallback — should not normally reach here
    return 100, "emergency"


def write_heartbeat(heartbeat_file: str) -> None:
    """Write current timestamp to heartbeat file."""
    Path(heartbeat_file).write_text(str(datetime.now().isoformat()))


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

_running = True


def handle_signal(signum, frame):
    global _running
    _running = False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    config_path = os.environ.get("FAN_CONTROL_CONFIG", "/etc/dell-fan-control/config.yaml")
    config = load_config(config_path)

    logger = setup_logging(config.get("log_level", "INFO"), config.get("log_file"))
    logger.info("Dell R730xd Fan Control starting")
    logger.info(f"Config: {config_path}")

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Initialise
    logger.info("Enabling manual fan control")
    enable_manual_fan_control(config, logger)

    logger.info("Enabling third-party PCIe fan response")
    enable_third_party_pcie(config, logger)

    # Set baseline fan speed on startup
    baseline = config["thresholds"][0]["fan_percent"]
    logger.info(f"Setting baseline fan speed: {baseline}%")
    set_fan_speed(baseline, config, logger)

    current_percent = baseline
    interval = config.get("polling_interval_seconds", 30)
    heartbeat_file = config.get("heartbeat_file", "/var/run/fan_control.heartbeat")

    logger.info(f"Polling every {interval}s")

    while _running:
        temp = get_gpu_temperature(logger)

        if temp is None:
            logger.warning("Could not read GPU temperature — holding current fan speed")
        else:
            target_percent, label = get_target_fan_speed(temp, config["thresholds"])

            if target_percent != current_percent:
                logger.info(
                    f"GPU {temp}°C → {label} → fan {current_percent}% → {target_percent}%"
                )
                if set_fan_speed(target_percent, config, logger):
                    current_percent = target_percent
                else:
                    logger.error("Failed to set fan speed")
            else:
                logger.debug(f"GPU {temp}°C → {label} → fan {current_percent}% (no change)")

        write_heartbeat(heartbeat_file)
        time.sleep(interval)

    # Clean exit
    logger.info("Shutting down — restoring automatic fan control")
    restore_auto_fan_control(config, logger)


if __name__ == "__main__":
    main()
