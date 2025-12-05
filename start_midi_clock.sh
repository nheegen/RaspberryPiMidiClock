#!/bin/bash
# Simple script to start the MIDI clock application

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source venv/bin/activate
python3 midi_clock.py





