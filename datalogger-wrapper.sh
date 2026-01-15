#!/bin/bash

LOG_FILE="/home/logger/datalogger/datalogger.log"
APP_SCRIPT="/home/logger/datalogger/datalogger_app.py"
FIND_SCRIPT="/home/logger/datalogger/findcdcport.py"
VENV_DIR="/home/logger/datalogger/.venv"
PYTHON_CMD="$VENV_DIR/bin/python"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_eth0_ip() {
    ip -4 addr show eth0 | grep -q "inet "
    return $?
}

# check_eth1_internet() {
#     if ping -c 1 -W 3 8.8.8.8 -I usb0 &>/dev/null; then
#         return 0
#     else
#         return 1
#     fi
# }

wait_for_network() {
    local max_attempts=120
    local attempt=0
    
    log "Waiting for network interfaces to be ready..."
    
    while [ $attempt -lt $max_attempts ]; do
        if check_eth0_ip; then
            ETH0_IP=$(ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
            log "eth0 has IP: $ETH0_IP"
            return 0
            # if check_eth1_internet; then
            #     log "usb0 has internet connectivity"
            #     return 0
            # else
            #     log "eth0 ready but eth1 no internet (attempt $((attempt+1))/$max_attempts)"
            # fi
        else
            log "Waiting for eth0 IP (attempt $((attempt+1))/$max_attempts)"
        fi
        
        sleep 5
        attempt=$((attempt+1))
    done
    
    log "ERROR: Network interfaces not ready after $((max_attempts * 5)) seconds"
    log "Starting anyway (will retry with app's retry logic)"
    return 1
}

cd /home/logger/datalogger

if [ ! -d "$VENV_DIR" ]; then
    log "ERROR: Virtual environment not found at $VENV_DIR"
    exit 1
fi

log "Activating virtual environment at $VENV_DIR"
source "$VENV_DIR/bin/activate"

exec $PYTHON_CMD $FIND_SCRIPT &
sleep 10

wait_for_network

log "Waiting 30 seconds before starting DataLogger..."
sleep 30

log "Starting DataLogger application..."
exec $PYTHON_CMD $APP_SCRIPT