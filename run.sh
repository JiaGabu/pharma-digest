#!/bin/bash
# Wrapper script for launchd to run the Pharma Digest
set -e

PROJECT_DIR="$HOME/pharma-digest"
cd "$PROJECT_DIR"

# Only run at or after 07:10 (prevents hourly fallback from firing before scheduled time)
CURRENT_HOUR=$(date +%H)
CURRENT_MIN=$(date +%M)
if [ "$CURRENT_HOUR" -lt 7 ] || { [ "$CURRENT_HOUR" -eq 7 ] && [ "$CURRENT_MIN" -lt 10 ]; }; then
    exit 0
fi

# Activate virtualenv if it exists
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

"$PROJECT_DIR/venv/bin/python3" main.py
