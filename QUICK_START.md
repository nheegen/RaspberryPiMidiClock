# Quick Start Guide

## Starting the MIDI Clock

### Simple Method (Recommended)
```bash
cd ~/RaspberryPiMidiClock
./start_midi_clock.sh
```

### Manual Method
```bash
cd ~/RaspberryPiMidiClock
source venv/bin/activate
python3 midi_clock.py
```

### Run in Background
```bash
cd ~/RaspberryPiMidiClock
source venv/bin/activate
nohup python3 midi_clock.py > /dev/null 2>&1 &
```

## Stopping the MIDI Clock

### Easy Method (Recommended)
```bash
cd ~/RaspberryPiMidiClock
./stop_midi_clock.sh
```

### If running as systemd service
```bash
sudo systemctl stop midi-clock.service
```

### If running manually in foreground
Press `Ctrl+C`

### If running manually in background
```bash
pkill -f midi_clock.py
```

### Check if it's running
```bash
# Check systemd service
sudo systemctl status midi-clock.service

# Check for any running process
ps aux | grep midi_clock
```

## What You'll See

When you start the application, you should see:
- Available MIDI ports listed
- Both ESI MIDIMATE eX ports opened
- Current BPM displayed on Sense HAT LED matrix
- Controls instructions printed

## Controls (Sense HAT Joystick)

- **Up**: Increase BPM by 1
- **Down**: Decrease BPM by 1  
- **Left**: Fine decrease BPM by 0.1
- **Right**: Fine increase BPM by 0.1
- **Press (Middle)**: Start/Stop MIDI clock

## Display

- **Green**: Clock is running
- **Red**: Clock is stopped
- **Number**: Current BPM

## Troubleshooting

### Application won't start
- Check that virtual environment is activated: `source venv/bin/activate`
- Check MIDI interface is connected: `aconnect -l`
- Check Sense HAT is connected: `sudo i2cdetect -y 1`

### Joystick still controls OS
- Blacklist the joystick kernel module:
  ```bash
  echo "blacklist rpisense-js" | sudo tee /etc/modprobe.d/blacklist-rpisense-js.conf
  sudo modprobe -r rpisense-js
  sudo reboot
  ```

### Check if application is running
```bash
ps aux | grep midi_clock
```


