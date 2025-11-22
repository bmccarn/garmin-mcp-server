#!/bin/bash
# Run the Garmin Connect app with the correct conda environment

# Initialize conda for the current shell
source /opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh

# Activate the connect environment
conda activate connect

# Run the app
python "$(dirname "$0")/garmin_app.py"
