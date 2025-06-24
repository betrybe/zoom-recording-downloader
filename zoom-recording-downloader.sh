#!/bin/bash
SCRIPT_DIR="$(dirname "$0")"

# --- Environment Setup ---
# -- Check if we have python3 command
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3."
    exit 1
fi

# -- Check if venv is setup and install dependencies
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Virtual environment not found. Setting up..."
    python3 -m venv "$SCRIPT_DIR/.venv"
    source "$SCRIPT_DIR/.venv/bin/activate"
    pip install --upgrade pip
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        pip install -r "$SCRIPT_DIR/requirements.txt"
    fi
else
    echo "Virtual environment found."
fi

# Activate the virtual environment for the current shell
source "$(dirname "$0")/.venv/bin/activate"


# --- Script Execution Logic ---

# Check the first argument to decide which script to run.
if [[ "$1" == "verify" ]]; then
    echo "--- Running Migration Verification Script ---"
    shift # Remove 'verify' from arguments
    python "$(dirname "$0")/verify_migration.py" "$@"

elif [[ "$1" == "delete" ]]; then
    echo "--- Running Zoom Deletion Script ---"
    shift # Remove 'delete' from arguments
    python "$(dirname "$0")/delete_from_zoom.py" "$@"

elif [[ "$1" == "--help" || "$1" == "help" ]]; then
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "A tool to download, verify, and delete Zoom recordings."
    echo ""
    echo "Commands:"
    echo "  <no command>    Run the main download/upload migration script."
    echo "                  e.g., $0 path/to/recordings.csv"
    echo ""
    echo "  verify          Run the migration verification script."
    echo "                  e.g., $0 verify path/to/recordings.csv"
    echo ""
    echo "  delete          Run the Zoom cloud recording deletion script."
    echo "                  e.g., $0 delete path/to/verification_report.csv"
    echo ""
    echo "  help            Show this help message."
    exit 0
else
    echo "--- Running Zoom Recording Downloader Script ---"
    python "$(dirname "$0")/zoom_recording_downloader.py" "$@"
fi
