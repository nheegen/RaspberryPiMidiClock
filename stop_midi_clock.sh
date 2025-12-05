#!/bin/bash
# Script to stop the MIDI clock application

echo "Stopping MIDI clock..."

# Try to stop systemd service first
if systemctl is-active --quiet midi-clock.service 2>/dev/null; then
    echo "Stopping systemd service..."
    sudo systemctl stop midi-clock.service
    echo "MIDI clock service stopped."
else
    echo "Service not running, checking for manual process..."
    # Stop any running process
    if pgrep -f "midi_clock.py" > /dev/null; then
        pkill -f midi_clock.py
        echo "MIDI clock process stopped."
    else
        echo "MIDI clock is not running."
    fi
fi




