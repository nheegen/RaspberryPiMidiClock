# How the MIDI Clock Master Works

## Overview

This application sends MIDI clock signals from the Raspberry Pi to any class-compliant USB MIDI interface. It acts as a **master clock** that other MIDI devices can sync to. If an ESI MIDIMATE eX is connected it will be preferred and both of its ports will be opened automatically, but any other USB-MIDI interface works as well.

## MIDI Clock Protocol

### Standard MIDI Clock Messages

The application sends three types of MIDI messages:

1. **MIDI Clock (0xF8)**: 
   - Sent 24 times per quarter note (24 PPQN - standard MIDI resolution)
   - At 120 BPM, this means 24 pulses per beat = 2,880 pulses per minute
   - These pulses tell your device when to advance its sequencer/clock

2. **MIDI Start (0xFA)**:
   - Sent when you press the joystick to start the clock
   - Tells your device to begin playback from the beginning

3. **MIDI Stop (0xFC)**:
   - Sent when you press the joystick to stop the clock
   - Tells your device to stop playback

### Timing Calculation

The application calculates the exact timing between clock pulses:

```
Interval (seconds) = 60 / (BPM × 24)
```

**Examples:**
- At 120 BPM: 60 / (120 × 24) = 0.0208 seconds = 20.8 milliseconds between pulses
- At 60 BPM: 60 / (60 × 24) = 0.0417 seconds = 41.7 milliseconds between pulses
- At 180 BPM: 60 / (180 × 24) = 0.0139 seconds = 13.9 milliseconds between pulses

## Hardware Connection

```
Raspberry Pi → ESI MIDIMATE eX (USB) → MIDI OUT → Your MIDI Device
```

If an ESI MIDIMATE eX is present it exposes two MIDI outputs:
- **MIDI 1** (Port 1)
- **MIDI 2** (Port 2)

When detected, the app opens both ports and sends clock to each. With other USB interfaces, the app opens the first non-"Midi Through" port by default (or the first available port as a fallback).

## How to Use

### Starting the Application

```bash
cd ~/RaspberryPiMidiClock
source venv/bin/activate
python3 midi_clock.py
```

### Controls (Sense HAT Joystick)

- **Up**: Increase BPM by 1
- **Down**: Decrease BPM by 1
- **Left**: Fine decrease BPM by 0.1
- **Right**: Fine increase BPM by 0.1
- **Press (Middle)**: Start/Stop the MIDI clock

### Display

The Sense HAT LED matrix shows:
- **Current BPM** as a static number (no scrolling)
- **Green color**: Clock is running
- **Red color**: Clock is stopped

## Sending MIDI Clock to Your Device

### Automatic Port Detection

- If an ESI MIDIMATE eX is connected: open all of its ports (MIDI 1 and MIDI 2) and send clock to both.
- If no ESI MIDIMATE eX is present: open the first non-"Midi Through" USB-MIDI port (fallback to the first port if only "Midi Through" exists).

When you run the application you'll see the detected ports and which ones were opened. All opened ports receive the same clock/start/stop messages.

### Manual Port Selection

You can pass `midi_port` to `MIDIClock` to override auto-detection:
```python
clock = MIDIClock(midi_port=None)      # Auto: prefer MIDIMATE, else first non-"Midi Through"
clock = MIDIClock(midi_port=1)         # Use only port index 1
clock = MIDIClock(midi_port=[1, 2])    # Use specific port indices
```

### Connecting to Your MIDI Device

1. **Physical Connection**:
   - Connect MIDI cables from **both** ESI MIDIMATE eX MIDI OUT ports to your devices' MIDI IN
   - MIDI 1 and MIDI 2 will both send the same clock signal simultaneously
   - Ensure your devices are set to receive MIDI clock (usually a sync setting)

2. **Start the Clock**:
   - Run the application
   - Press the joystick (middle) to start sending MIDI clock
   - The display will turn green and show the BPM
   - Your device should start syncing to the clock

3. **Adjust BPM**:
   - Use joystick up/down to change BPM
   - Your device will follow the new tempo

4. **Stop the Clock**:
   - Press the joystick again to stop
   - The display will turn red
   - MIDI Stop message is sent to your device

## Technical Details

### Threading

The application uses multiple threads:
- **Clock thread**: Sends MIDI clock pulses at precise intervals
- **Display thread**: Updates the LED matrix display
- **Main thread**: Handles joystick input and coordinates everything

### Accuracy

The clock thread schedules ticks using `time.perf_counter()` and short sleeps to reduce jitter, resyncing if the loop ever runs late. It calculates the interval from the current BPM and maintains a scheduled next-tick target rather than relying on long sleeps.

### MIDI Port Selection Logic

1. If `midi_port=None`: Auto-detect and open **all** ESI MIDIMATE eX ports
2. If ESI MIDIMATE not found: Use first non-"Midi Through" port
3. If only "Midi Through" available: Use it (with warning)
4. If `midi_port` is a number: Use only that specific port
5. If `midi_port` is a list: Use all specified ports

**Note**: When multiple ports are open, all MIDI messages (clock, start, stop) are sent to all open ports simultaneously.

## Troubleshooting

### Device Not Receiving Clock

1. **Check MIDI cable**: Ensure it's connected from MIDI OUT to your device's MIDI IN
2. **Check device settings**: Your device must be set to receive MIDI clock/sync
3. **Check port**: Verify the application is using the correct MIDI port (check startup messages)
4. **Test with MIDI monitor**: Use a MIDI monitor tool to verify messages are being sent

### Clock Running Too Fast/Slow

- The BPM display shows the exact tempo
- If your device seems off, check if it's set to the correct PPQN (should be 24)
- Some devices have their own tempo multipliers - check your device's manual

### Port Not Found

- Ensure ESI MIDIMATE eX is connected via USB
- Check with: `aconnect -l` (should show ESI MIDIMATE eX ports)
- Try unplugging and reconnecting the USB cable

## Example Workflow

1. **Start the application**: `python3 midi_clock.py`
2. **Set desired BPM**: Use joystick up/down (default is 120 BPM)
3. **Connect your device**: MIDI cable from ESI MIDIMATE eX to your device
4. **Start clock**: Press joystick - display turns green
5. **Your device syncs**: It should start playing/syncing to the clock
6. **Adjust tempo**: Change BPM on the fly - device follows
7. **Stop**: Press joystick again - display turns red, device stops

The MIDI clock is now being sent continuously to your device!

