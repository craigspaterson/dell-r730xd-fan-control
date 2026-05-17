#!/bin/bash
# Dell R730xd Fan Control Watchdog
# If the fan control daemon stalls (heartbeat not updated in 5 minutes),
# set fans to a safe speed and restart the service.

HEARTBEAT_FILE="/var/run/fan_control.heartbeat"
MAX_AGE_SECONDS=300   # 5 minutes
SAFE_FAN_SPEED="0x50" # 80% — safe fallback
CHECK_INTERVAL=60     # Check every 60 seconds

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] $*" | tee -a /var/log/dell-fan-control-watchdog.log
}

set_safe_fans() {
    log "Setting fans to safe speed (80%)"
    ipmitool raw 0x30 0x30 0x01 0x00
    ipmitool raw 0x30 0x30 0x02 0xff $SAFE_FAN_SPEED
}

log "Watchdog starting"

while true; do
    if [[ ! -f "$HEARTBEAT_FILE" ]]; then
        log "WARNING: Heartbeat file missing — daemon may not have started"
        set_safe_fans
    else
        LAST_MODIFIED=$(stat -c %Y "$HEARTBEAT_FILE" 2>/dev/null || echo 0)
        NOW=$(date +%s)
        AGE=$(( NOW - LAST_MODIFIED ))

        if [[ $AGE -gt $MAX_AGE_SECONDS ]]; then
            log "WARNING: Heartbeat stale (${AGE}s old, max ${MAX_AGE_SECONDS}s)"
            set_safe_fans
            log "Restarting fan control service"
            systemctl restart dell-fan-control.service
        else
            : # Heartbeat fresh, all good
        fi
    fi

    sleep $CHECK_INTERVAL
done
