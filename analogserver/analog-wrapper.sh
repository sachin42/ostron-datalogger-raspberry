#!/bin/bash

LOG_FILE="/home/logger/datalogger/datalogger.log"
APP_SCRIPT="/home/logger/datalogger/datalogger_app.py"
VENV_DIR="/home/logger/datalogger/.venv"
PYTHON_CMD="$VENV_DIR/bin/python"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

cd /home/logger/datalogger

if [ ! -d "$VENV_DIR" ]; then
    log "ERROR: Virtual environment not found at $VENV_DIR"
    exit 1
fi

log "Activating virtual environment at $VENV_DIR"
source "$VENV_DIR/bin/activate"

log "Waiting 30 seconds before starting DataLogger..."
sleep 30

log "Starting DataLogger application..."
exec $PYTHON_CMD $APP_SCRIPT