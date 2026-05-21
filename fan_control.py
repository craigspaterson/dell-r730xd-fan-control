#!/usr/bin/env python3
"""
Dell R730xd Fan Control Daemon
Monitors GPU temperature via nvidia-smi and CPU temperatures via ipmitool,
then adjusts fan speed via ipmitool based on configurable per-source thresholds.
Fan speed is set to the maximum speed required by any source.

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
    "sources": {
        "gpu": {
            "failure_fallback_percent": 80,
            "thresholds": [
                {"max_temp": 50,  "fan_percent": 30,  "label": "idle"},
                {"max_temp": 65,  "fan_percent": 50,  "label": "light"},
                {"max_temp": 75,  "fan_percent": 70,  "label": "moderate"},
                {"max_temp": 85,  "fan_percent": 85,  "label": "heavy"},
                {"max_temp": 999, "fan_percent": 100, "label": "emergency"},
            ],
        },
        "cpu": {
            "sensors": ["CPU1 Temp", "CPU2 Temp"],
            "failure_fallback_percent": 80,
            "thresholds": [
                {"max_temp": 45,  "fan_percent": 30,  "label": "idle"},
                {"max_temp": 60,  "fan_percent": 50,  "label": "light"},
                {"max_temp": 70,  "fan_percent": 70,  "label": "moderate"},
                {"max_temp": 80,  "fan_percent": 85,  "label": "heavy"},
                {"max_temp": 999, "fan_percent": 100, "label": "emergency"},
            ],
        },
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str) -> tuple[dict, list[str]]:
    path = Path(config_path)
    if not path.exists():
        return DEFAULT_CONFIG, []

    with open(path) as f:
        user_config = yaml.safe_load(f) or {}

    if not isinstance(user_config, dict):
        raise ValueError(
            f"Config file {config_path} must be a YAML mapping, got {type(user_config).__name__}"
        )

    warnings = []

    # Auto-migrate old flat thresholds format to sources.gpu.thresholds
    if "thresholds" in user_config and "sources" not in user_config:
        warnings.append(
            "Config uses deprecated 'thresholds' key — migrated to sources.gpu.thresholds. "
            "Update /etc/dell-fan-control/config.yaml to use the 'sources' structure to silence this warning."
        )
        user_config.setdefault("sources", {})
        user_config["sources"].setdefault("gpu", {})
        user_config["sources"]["gpu"]["thresholds"] = user_config.pop("thresholds")

    return deep_merge(DEFAULT_CONFIG, user_config), warnings


# ---------------------------------------------------------------------------
# IPMI / GPU helpers
# ---------------------------------------------------------------------------

def run_command(cmd: str, logger: logging.Logger) -> tuple[int, str]:
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


def get_cpu_temperature(sensors: list[str], logger: logging.Logger) -> int | None:
    rc, output = run_command("ipmitool sdr type Temperature", logger)
    if rc != 0 or not output:
        return None

    temps = []
    for line in output.splitlines():
        # ipmitool sdr format: "CPU1 Temp | 52 degrees C | ok"
        parts = line.split("|")
        if len(parts) < 3:
            continue
        if parts[0].strip() not in sensors:
            continue
        try:
            temp_field = parts[1].strip()  # "52 degrees C"
            temp = int(temp_field.split()[0])
            temps.append(temp)
        except (ValueError, IndexError):
            logger.error(f"Could not parse CPU temp from: {line!r}")

    if not temps:
        logger.error(f"No CPU temperature sensors found matching: {sensors}")
        return None

    return max(temps)


def percent_to_hex(percent: int) -> str:
    value = max(0, min(100, percent))
    return hex(round(value))


def set_fan_speed(percent: int, config: dict, logger: logging.Logger) -> bool:
    hex_speed = percent_to_hex(percent)
    cmd = config["fan"]["set_speed_command"].format(hex_speed=hex_speed)
    rc, _ = run_command(cmd, logger)
    return rc == 0


def enable_manual_fan_control(config: dict, logger: logging.Logger) -> bool:
    rc, _ = run_command(config["fan"]["manual_control_command"], logger)
    return rc == 0


def enable_third_party_pcie(config: dict, logger: logging.Logger) -> bool:
    rc, _ = run_command(config["fan"]["third_party_pcie_command"], logger)
    return rc == 0


def restore_auto_fan_control(config: dict, logger: logging.Logger) -> bool:
    rc, _ = run_command(config["fan"]["restore_auto_command"], logger)
    return rc == 0


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def get_target_fan_speed(temp: int, thresholds: list[dict]) -> tuple[int, str]:
    for threshold in sorted(thresholds, key=lambda t: t["max_temp"]):
        if temp <= threshold["max_temp"]:
            return threshold["fan_percent"], threshold["label"]
    return 100, "emergency"


def write_heartbeat(heartbeat_file: str) -> None:
    Path(heartbeat_file).write_text(str(datetime.now().isoformat()))


def fmt_temp(t: int | None) -> str:
    return f"{t}°C" if t is not None else "N/A"


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
    config, config_warnings = load_config(config_path)

    logger = setup_logging(config.get("log_level", "INFO"), config.get("log_file"))
    logger.info("Dell R730xd Fan Control starting")
    logger.info(f"Config: {config_path}")

    for warning in config_warnings:
        logger.warning(warning)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    logger.info("Enabling manual fan control")
    enable_manual_fan_control(config, logger)

    logger.info("Enabling third-party PCIe fan response")
    enable_third_party_pcie(config, logger)

    gpu_cfg = config["sources"]["gpu"]
    cpu_cfg = config["sources"]["cpu"]

    baseline = max(
        gpu_cfg["thresholds"][0]["fan_percent"],
        cpu_cfg["thresholds"][0]["fan_percent"],
    )
    logger.info(f"Setting baseline fan speed: {baseline}%")
    set_fan_speed(baseline, config, logger)

    current_percent = baseline
    interval = config.get("polling_interval_seconds", 30)
    heartbeat_file = config.get("heartbeat_file", "/var/run/fan_control.heartbeat")

    logger.info(f"Polling every {interval}s — sources: GPU (nvidia-smi), CPU ({cpu_cfg['sensors']})")

    while _running:
        gpu_temp = get_gpu_temperature(logger)
        cpu_temp = get_cpu_temperature(cpu_cfg["sensors"], logger)

        if gpu_temp is None:
            gpu_target = gpu_cfg["failure_fallback_percent"]
            gpu_label = "fallback"
            logger.warning(f"Could not read GPU temperature — falling back to {gpu_target}%")
        else:
            gpu_target, gpu_label = get_target_fan_speed(gpu_temp, gpu_cfg["thresholds"])

        if cpu_temp is None:
            cpu_target = cpu_cfg["failure_fallback_percent"]
            cpu_label = "fallback"
            logger.warning(f"Could not read CPU temperature — falling back to {cpu_target}%")
        else:
            cpu_target, cpu_label = get_target_fan_speed(cpu_temp, cpu_cfg["thresholds"])

        target_percent = max(gpu_target, cpu_target)

        if target_percent != current_percent:
            logger.info(
                f"Fan {current_percent}% → {target_percent}% "
                f"[GPU: {fmt_temp(gpu_temp)} ({gpu_label}) → {gpu_target}%, "
                f"CPU: {fmt_temp(cpu_temp)} ({cpu_label}) → {cpu_target}%]"
            )
            if set_fan_speed(target_percent, config, logger):
                current_percent = target_percent
            else:
                logger.error("Failed to set fan speed")
        else:
            logger.debug(
                f"GPU {fmt_temp(gpu_temp)} ({gpu_label}) / CPU {fmt_temp(cpu_temp)} ({cpu_label}) "
                f"→ fan {current_percent}% (no change)"
            )

        write_heartbeat(heartbeat_file)
        time.sleep(interval)

    logger.info("Shutting down — restoring automatic fan control")
    restore_auto_fan_control(config, logger)


if __name__ == "__main__":
    main()
