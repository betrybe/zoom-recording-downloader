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

# --- Log file setup ---
# Create a 'logs' directory for console outputs if it doesn't exist
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
# Create a unique, timestamped filename for this specific run's console log
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
CONSOLE_LOG_FILE="$LOG_DIR/console_output_${TIMESTAMP}.log"


# --- Script Execution Logic ---
# A helper function to wrap the python execution and apply 'tee' for logging.
run_script() {
    # The first argument is the python script to run
    # The rest of the arguments are passed directly to that script
    local script_to_run=$1
    shift
    echo "Saving console output to: ${CONSOLE_LOG_FILE}"
    # Execute the python script.
    # 2>&1 redirects stderr to stdout.
    # The pipe '|' sends this combined output to 'tee', which splits it:
    # one stream goes to the console, the other to the specified log file.
    python -u "$script_to_run" "$@" 2>&1 | tee "$CONSOLE_LOG_FILE"
}

if [[ "$1" == "verify" ]]; then
    echo "--- Running Migration Verification Script ---"
    shift
    run_script "$(dirname "$0")/verify_migration.py" "$@"

elif [[ "$1" == "delete" ]]; then
    echo "--- Running Zoom Deletion Script ---"
    shift
    run_script "$(dirname "$0")/delete_from_zoom.py" "$@"

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
    run_script "$(dirname "$0")/zoom_recording_downloader.py" "$@"
fi
