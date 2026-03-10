#!/bin/bash
# Wrapper script for launchd to run the Pharma Digest
set -e

PROJECT_DIR="$HOME/Desktop/pharma-digest"
cd "$PROJECT_DIR"

# Activate virtualenv if it exists
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

python3 main.py >> "$PROJECT_DIR/logs/app.log" 2>&1
