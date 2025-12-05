# Raspberry Pi MIDI Clock Master

A MIDI clock master application for Raspberry Pi 3 Model B with Sense HAT and ESI MidiMate eX USB MIDI interface.

## Features

- Sends MIDI clock signals (24 pulses per quarter note) through USB MIDI interface
- Displays current BPM on Sense HAT LED matrix
- Joystick control:
  - **Up**: Increase BPM by 1
  - **Down**: Decrease BPM by 1
  - **Left**: Fine decrease BPM by 0.1
  - **Right**: Fine increase BPM by 0.1
  - **Press (Middle)**: Start/Stop MIDI clock
- Accurate timing for MIDI clock messages
- Visual feedback: Green display when running, red when stopped

## Hardware Requirements

- Raspberry Pi 3 Model B (or compatible)
- Sense HAT
- ESI MidiMate eX USB MIDI interface (or compatible USB MIDI device)

## Software Requirements

- Raspberry Pi OS
- Python 3.6 or higher

## Installation

1. Install system dependencies:
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev python3-venv
```

2. Install Sense HAT system packages (required for hardware access):
```bash
sudo apt-get install -y sense-hat python3-sense-hat
```

3. Create a virtual environment with system site-packages access:
```bash
python3 -m venv --system-site-packages venv
```

4. Activate the virtual environment and install Python packages:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

4. Ensure your MIDI interface is connected and recognized:
```bash
# Check if MIDI device is detected
aconnect -l
```

5. **Disable OS joystick handling (recommended):**
   
   By default, the Sense HAT joystick also controls the Raspberry Pi OS (cursor movement, etc.), which can interfere with the MIDI clock application. To disable OS joystick handling so only your application can use it:
   
   ```bash
   ./disable_os_joystick.sh
   ```
   
   This will:
   - Unload the joystick kernel module
   - Blacklist it to prevent loading on boot
   - Allow your MIDI clock application exclusive access to the joystick
   
   **Note:** You may need to reboot for changes to take full effect:
   ```bash
   sudo reboot
   ```
   
   To re-enable OS joystick handling later:
   ```bash
   sudo rm /etc/modprobe.d/blacklist-rpisense-js.conf
   sudo reboot
   ```

## Usage

Activate the virtual environment (if you used one) and run the application:
```bash
source venv/bin/activate
python3 midi_clock.py
```

Or if you installed packages system-wide:
```bash
python3 midi_clock.py
```

The application will:
- Detect available MIDI output ports
- Display the current BPM on the Sense HAT LED matrix
- Respond to joystick input for BPM control and start/stop

### Controls

- **Joystick Up**: Increase BPM (+1)
- **Joystick Down**: Decrease BPM (-1)
- **Joystick Left**: Fine decrease BPM (-0.1)
- **Joystick Right**: Fine increase BPM (+0.1)
- **Joystick Press**: Toggle start/stop MIDI clock

### BPM Range

The BPM is clamped between 20 and 300 BPM for safety.

## MIDI Clock Specification

The application sends standard MIDI clock messages:
- **MIDI Clock (0xF8)**: Sent 24 times per quarter note at the specified BPM
- **MIDI Start (0xFA)**: Sent when clock is started
- **MIDI Stop (0xFC)**: Sent when clock is stopped

## Troubleshooting

### No MIDI ports available

If you see "No MIDI output ports available":
1. Check that your USB MIDI interface is connected
2. Verify the device is recognized: `lsusb`
3. Check ALSA MIDI ports: `aconnect -l`
4. You may need to install ALSA MIDI support: `sudo apt-get install alsa-utils`

### Sense HAT not detected

If the Sense HAT is not working:
1. Ensure it's properly connected to the GPIO header
2. Check I2C is enabled: `sudo raspi-config` → Interface Options → I2C → Enable
3. Verify I2C connection: `sudo i2cdetect -y 1`

### Joystick interfering with OS

If the joystick is controlling the Raspberry Pi OS (cursor movement, etc.) instead of just the MIDI clock application:

1. Run the disable script: `./disable_os_joystick.sh`
2. Reboot if needed: `sudo reboot`
3. The joystick will now only work with your MIDI clock application

The Sense HAT Python library can still access the joystick directly through I2C even when the OS kernel module is disabled.

### Permission issues

If you encounter permission errors:
1. Add your user to the `i2c` group: `sudo usermod -a -G i2c $USER`
2. Log out and log back in for changes to take effect

## License

This project is provided as-is for educational and personal use.

