#!/bin/bash
#
# Simplified wrapper script for datalogger application.
# All startup diagnostics (modem detection, network checks, etc.) are now
# handled in Python by modules/diagnostics.py for better error handling.
#

APP_DIR="/home/logger/datalogger"
VENV_DIR="$APP_DIR/.venv"
PYTHON_CMD="$VENV_DIR/bin/python"
APP_SCRIPT="$APP_DIR/datalogger_app.py"

# Change to application directory
cd "$APP_DIR"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Virtual environment not found at $VENV_DIR"
    exit 1
fi

# Activate virtual environment and start application
source "$VENV_DIR/bin/activate"
exec $PYTHON_CMD $APP_SCRIPT