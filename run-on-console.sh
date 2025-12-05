#!/bin/bash
# Script to run MIDI clock on console (for systemd service)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source venv/bin/activate
exec python3 midi_clock.py

