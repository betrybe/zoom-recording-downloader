#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Check if pipx is installed
if ! command -v pipx >/dev/null 2>&1; then
  echo "pipx is not installed. Please install pipx first via apt, brew, or pip."
fi

# Install the current project as a pipx package
echo "Installing the current project as a pipx package..."
pipx install .

echo "Installation complete. The package is now available as a pipx package."