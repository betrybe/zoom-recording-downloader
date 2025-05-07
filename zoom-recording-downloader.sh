#!/bin/bash
SCRIPT_DIR="$(dirname "$0")"
# -- Check if we have python3 command
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3."
    exit 1
fi

# -- Check if venv is setup
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Virtual environment not found. Setting up..."
    python3 -m venv "$SCRIPT_DIR/.venv"
    source "$SCRIPT_DIR/.venv/bin/activate"
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
else
    echo "Virtual environment found."
fi

source "$(dirname "$0")/.venv/bin/activate"
python "$(dirname "$0")/zoom_recording_downloader.py" "$@"
