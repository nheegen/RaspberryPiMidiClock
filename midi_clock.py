#!/usr/bin/env python3
"""
Raspberry Pi MIDI Clock Master
Controls MIDI clock via Sense HAT joystick and displays BPM on LED matrix.
"""

import time
import threading
import sys
import termios
import tty
from sense_hat import SenseHat
import rtmidi

# ANSI color codes for console output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    # Bright colors
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'

# MIDI constants
MIDI_CLOCK = 0xF8
MIDI_START = 0xFA
MIDI_STOP = 0xFC
PPQN = 24  # Pulses Per Quarter Note (standard MIDI clock resolution)

class MIDIClock:
    def __init__(self, midi_port=None):
        # Disable terminal echo to prevent escape sequences from showing
        try:
            # Save terminal settings
            self.old_settings = termios.tcgetattr(sys.stdin)
            # Disable echo and set raw mode
            tty.setraw(sys.stdin.fileno())
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            # Disable echo specifically
            new_settings = termios.tcgetattr(sys.stdin)
            new_settings[3] = new_settings[3] & ~termios.ECHO
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
        except (AttributeError, OSError, termios.error):
            # If stdin is not a TTY, ignore
            self.old_settings = None
        
        self.sense = SenseHat()
        self.sense.clear()
        
        # Initialize MIDI output - support multiple ports
        temp_midiout = rtmidi.MidiOut()
        available_ports = temp_midiout.get_ports()
        temp_midiout.close_port()
        del temp_midiout
        
        if not available_ports:
            raise RuntimeError("No MIDI output ports available. Check your MIDI interface connection.")
        
        print(f"{Colors.CYAN}Available MIDI ports: {available_ports}{Colors.RESET}")
        
        # Find and open all ESI MIDIMATE eX ports
        self.midiout_ports = []
        esi_ports_found = []
        
        if midi_port is None or midi_port == -1:
            # Look for all ESI MIDIMATE eX ports
            for i, port_name in enumerate(available_ports):
                if "MIDIMATE" in port_name.upper() or "ESI" in port_name.upper():
                    esi_ports_found.append((i, port_name))
            
            if esi_ports_found:
                print(f"{Colors.BRIGHT_GREEN}✓ Found {len(esi_ports_found)} ESI MIDIMATE eX port(s):{Colors.RESET}")
                for port_idx, port_name in esi_ports_found:
                    midiout = rtmidi.MidiOut()
                    midiout.open_port(port_idx)
                    self.midiout_ports.append((midiout, port_name))
                    print(f"{Colors.BRIGHT_GREEN}  → Opened: {Colors.BOLD}{port_name}{Colors.RESET}")
            else:
                # Fall back to first non-"Midi Through" port
                for i, port_name in enumerate(available_ports):
                    if "Midi Through" not in port_name:
                        midiout = rtmidi.MidiOut()
                        midiout.open_port(i)
                        self.midiout_ports.append((midiout, port_name))
                        print(f"Using first available port: {port_name}")
                        break
                else:
                    # Last resort: use first port
                    midiout = rtmidi.MidiOut()
                    midiout.open_port(0)
                    self.midiout_ports.append((midiout, available_ports[0]))
                    print(f"Using first port: {available_ports[0]}")
        else:
            # Use specified port(s) - can be a single port or list
            if isinstance(midi_port, (list, tuple)):
                port_list = midi_port
            else:
                port_list = [midi_port]
            
            for port_idx in port_list:
                if port_idx < len(available_ports):
                    midiout = rtmidi.MidiOut()
                    midiout.open_port(port_idx)
                    self.midiout_ports.append((midiout, available_ports[port_idx]))
                    print(f"Opened MIDI port: {available_ports[port_idx]}")
                else:
                    raise RuntimeError(f"Invalid MIDI port {port_idx}. Available ports: {len(available_ports)}")
        
        if not self.midiout_ports:
            raise RuntimeError("No MIDI ports were opened.")
        
        # Keep single midiout for backward compatibility (use first port)
        self.midiout = self.midiout_ports[0][0] if self.midiout_ports else None
        
        # Clock state
        self.bpm = 120.0
        self.running = False
        self.clock_thread = None
        self.stop_event = threading.Event()
        
        # Display update
        self.display_thread = None
        self.display_stop_event = threading.Event()
        
        # Beat ramp state - synced to MIDI clock pulses
        self.beat_position = 0  # 0-3 (4 positions: x=0, 2, 4, 6)
        self.clock_pulse_count = 0  # Count MIDI clock pulses (24 per beat)
        
        # Joystick state
        self.last_joystick_time = 0
        self.joystick_debounce = 0.1  # 100ms debounce
        self.held_direction = None  # Track which direction is being held
        self.repeat_thread = None  # Thread for repeating BPM changes
        self.repeat_stop_event = threading.Event()
        self.last_joystick_event_time = {}  # Track last event time per direction
        
        # Start display thread
        self.start_display()
        
    def calculate_clock_interval(self, bpm):
        """Calculate the time interval between MIDI clock pulses in seconds."""
        # 24 pulses per quarter note
        # 1 minute = 60 seconds
        # Interval = 60 / (BPM * PPQN)
        return 60.0 / (bpm * PPQN)
    
    def send_midi_clock(self):
        """Send MIDI clock pulses at the correct interval to all open ports."""
        while not self.stop_event.is_set():
            if self.running:
                # Send clock to all open MIDI ports
                for midiout, port_name in self.midiout_ports:
                    try:
                        midiout.send_message([MIDI_CLOCK])
                    except Exception as e:
                        print(f"{Colors.BRIGHT_RED}⚠ Error sending to {port_name}: {e}{Colors.RESET}")
                
                # Increment clock pulse counter for beat ramp sync
                self.clock_pulse_count += 1
                # Every 24 pulses = 1 beat, advance beat ramp
                if self.clock_pulse_count >= PPQN:
                    self.clock_pulse_count = 0
                    # Advance beat position (0-3, cycles)
                    self.beat_position = (self.beat_position + 1) % 4
            
            # Calculate sleep time based on current BPM
            interval = self.calculate_clock_interval(self.bpm)
            time.sleep(interval)
    
    def start_clock(self):
        """Start the MIDI clock on all open ports."""
        if not self.running:
            self.running = True
            # Reset beat ramp position and clock pulse counter
            self.beat_position = 0
            self.clock_pulse_count = 0
            # Send start message to all open MIDI ports
            for midiout, port_name in self.midiout_ports:
                try:
                    midiout.send_message([MIDI_START])
                except Exception as e:
                    print(f"{Colors.BRIGHT_RED}Error sending START to {port_name}: {e}{Colors.RESET}")
            print(f"\r{Colors.BRIGHT_GREEN}{Colors.BOLD}▶ MIDI clock STARTED at {self.bpm:.1f} BPM{Colors.RESET} ({len(self.midiout_ports)} port(s))        ")
    
    def stop_clock(self):
        """Stop the MIDI clock on all open ports."""
        if self.running:
            self.running = False
            # Send stop message to all open MIDI ports
            for midiout, port_name in self.midiout_ports:
                try:
                    midiout.send_message([MIDI_STOP])
                except Exception as e:
                    print(f"{Colors.BRIGHT_RED}Error sending STOP to {port_name}: {e}{Colors.RESET}")
            print(f"\r{Colors.BRIGHT_RED}{Colors.BOLD}■ MIDI clock STOPPED{Colors.RESET} ({len(self.midiout_ports)} port(s))        ")
    
    def set_bpm(self, bpm):
        """Set the BPM (clamped to reasonable range)."""
        self.bpm = max(20.0, min(300.0, bpm))
        # Use carriage return to overwrite line and clear any escape sequences
        # Color based on running state
        color = Colors.BRIGHT_GREEN if self.running else Colors.BRIGHT_RED
        status = "▶ RUNNING" if self.running else "■ STOPPED"
        print(f"\r{color}{Colors.BOLD}BPM: {self.bpm:.1f} {status}{Colors.RESET}        ", end='', flush=True)
    
    def increase_bpm(self, step=1.0):
        """Increase BPM by step amount."""
        self.set_bpm(self.bpm + step)
    
    def decrease_bpm(self, step=1.0):
        """Decrease BPM by step amount."""
        self.set_bpm(self.bpm - step)
    
    def draw_digit(self, pixels, digit, x_offset, y_offset, color, small=False):
        """Draw a single digit on the LED matrix pixel array.
        
        Args:
            pixels: 64-element list of RGB tuples
            digit: digit character to draw
            x_offset: x position (0-7)
            y_offset: y position (0-7)
            color: RGB tuple
            small: if True, use 2x5 font, else use 3x5 font
        """
        if small:
            # Compact 2x5 font for 3-digit numbers (taller and more readable)
            digits = {
                '0': [[1,1], [1,1], [1,1], [1,1], [1,1]],
                '1': [[0,1], [1,1], [0,1], [0,1], [1,1]],
                '2': [[1,1], [0,1], [1,1], [1,0], [1,1]],
                '3': [[1,1], [0,1], [1,1], [0,1], [1,1]],
                '4': [[1,1], [1,1], [1,1], [0,1], [0,1]],
                '5': [[1,1], [1,0], [1,1], [0,1], [1,1]],
                '6': [[1,1], [1,0], [1,1], [1,1], [1,1]],
                '7': [[1,1], [0,1], [0,1], [0,1], [0,1]],
                '8': [[1,1], [1,1], [1,1], [1,1], [1,1]],
                '9': [[1,1], [1,1], [1,1], [0,1], [1,1]]
            }
            pattern = digits.get(str(digit), digits['0'])
            height, width = 5, 2
        else:
            # Standard 3x5 font for 1-2 digit numbers
            digits = {
                '0': [
                    [1,1,1],
                    [1,0,1],
                    [1,0,1],
                    [1,0,1],
                    [1,1,1]
                ],
                '1': [
                    [0,1,0],
                    [1,1,0],
                    [0,1,0],
                    [0,1,0],
                    [1,1,1]
                ],
                '2': [
                    [1,1,1],
                    [0,0,1],
                    [1,1,1],
                    [1,0,0],
                    [1,1,1]
                ],
                '3': [
                    [1,1,1],
                    [0,0,1],
                    [1,1,1],
                    [0,0,1],
                    [1,1,1]
                ],
                '4': [
                    [1,0,1],
                    [1,0,1],
                    [1,1,1],
                    [0,0,1],
                    [0,0,1]
                ],
                '5': [
                    [1,1,1],
                    [1,0,0],
                    [1,1,1],
                    [0,0,1],
                    [1,1,1]
                ],
                '6': [
                    [1,1,1],
                    [1,0,0],
                    [1,1,1],
                    [1,0,1],
                    [1,1,1]
                ],
                '7': [
                    [1,1,1],
                    [0,0,1],
                    [0,0,1],
                    [0,0,1],
                    [0,0,1]
                ],
                '8': [
                    [1,1,1],
                    [1,0,1],
                    [1,1,1],
                    [1,0,1],
                    [1,1,1]
                ],
                '9': [
                    [1,1,1],
                    [1,0,1],
                    [1,1,1],
                    [0,0,1],
                    [1,1,1]
                ]
            }
            pattern = digits.get(str(digit), digits['0'])
            height, width = 5, 3
        
        for y in range(height):
            for x in range(width):
                if pattern[y][x]:
                    # Calculate pixel index: row * 8 + column
                    idx = (y + y_offset) * 8 + (x + x_offset)
                    if 0 <= idx < 64:
                        pixels[idx] = color
    
    def draw_beat_ramp(self, pixels):
        """Draw a 2x2 white box in the beat ramp (rows 6-7) with dimmed trail.
        
        The beat position is updated by the MIDI clock thread, so it's
        perfectly synced to the actual MIDI clock pulses.
        
        Trail effect:
        - Current beat: white (100%)
        - Previous beats: 50% white (dimmed)
        
        Args:
            pixels: 64-element list of RGB tuples
        """
        if not self.running:
            # Don't show ramp when stopped
            return
        
        # Colors: white (100%) and dimmed white (50%)
        white = (255, 255, 255)
        dimmed_white = (127, 127, 127)  # 50% brightness
        
        # Draw all 4 boxes (positions 0, 2, 4, 6)
        for box_num in range(4):
            x_pos = box_num * 2  # x positions: 0, 2, 4, 6
            
            # Current beat is white, previous beats are dimmed
            if box_num == self.beat_position:
                color = white  # Current beat: full brightness
            elif box_num < self.beat_position:
                color = dimmed_white  # Previous beats: 50% brightness
            else:
                # Future beats (shouldn't happen in normal flow, but handle it)
                continue
            
            # Draw 2x2 box at this position (rows 6-7)
            for y in range(2):  # rows 6-7
                for x in range(2):  # 2 pixels wide
                    idx = (y + 6) * 8 + (x + x_pos)
                    if 0 <= idx < 64:
                        pixels[idx] = color
    
    def display_bpm(self):
        """Display BPM statically on the LED matrix with beat ramp."""
        last_bpm = -1
        last_running = None
        
        while not self.display_stop_event.is_set():
            current_bpm = int(self.bpm)
            
            # Update display if BPM or running state changed, or for beat ramp updates
            if current_bpm != last_bpm or self.running != last_running:
                # Initialize pixel array (64 pixels, all black)
                pixels = [(0, 0, 0)] * 64
                bpm_str = f"{current_bpm}"
                
                # Choose color: green if running, red if stopped
                color = (0, 255, 0) if self.running else (255, 0, 0)
                
                # Display BPM number statically (rows 0-4)
                if len(bpm_str) == 1:
                    # Center single digit with 3x5 font (starts at row 0)
                    self.draw_digit(pixels, bpm_str[0], 2, 0, color, small=False)
                elif len(bpm_str) == 2:
                    # Two digits side by side with 3x5 font (starts at row 0)
                    self.draw_digit(pixels, bpm_str[0], 0, 0, color, small=False)
                    self.draw_digit(pixels, bpm_str[1], 4, 0, color, small=False)
                else:  # 3 digits - use compact 2x5 font (more readable)
                    # 2x5 font: each digit is 2 wide, with 1 pixel spacing
                    # Positions: 0, 3, 6 (fits in 8 pixels width, starts at row 0)
                    self.draw_digit(pixels, bpm_str[0], 0, 0, color, small=True)
                    self.draw_digit(pixels, bpm_str[1], 3, 0, color, small=True)
                    self.draw_digit(pixels, bpm_str[2], 6, 0, color, small=True)
                
                # Draw beat ramp (rows 6-7)
                self.draw_beat_ramp(pixels)
                
                # Update the display
                self.sense.set_pixels(pixels)
                
                last_bpm = current_bpm
                last_running = self.running
            else:
                # Even if BPM/running state hasn't changed, update beat ramp
                pixels = [(0, 0, 0)] * 64
                bpm_str = f"{current_bpm}"
                color = (0, 255, 0) if self.running else (255, 0, 0)
                
                # Redraw BPM digits
                if len(bpm_str) == 1:
                    self.draw_digit(pixels, bpm_str[0], 2, 0, color, small=False)
                elif len(bpm_str) == 2:
                    self.draw_digit(pixels, bpm_str[0], 0, 0, color, small=False)
                    self.draw_digit(pixels, bpm_str[1], 4, 0, color, small=False)
                else:
                    self.draw_digit(pixels, bpm_str[0], 0, 0, color, small=True)
                    self.draw_digit(pixels, bpm_str[1], 3, 0, color, small=True)
                    self.draw_digit(pixels, bpm_str[2], 6, 0, color, small=True)
                
                # Update beat ramp
                self.draw_beat_ramp(pixels)
                self.sense.set_pixels(pixels)
            
            # Brief pause before checking for updates
            time.sleep(0.05)  # Faster update for smoother beat ramp
    
    def start_display(self):
        """Start the display update thread."""
        if self.display_thread is None or not self.display_thread.is_alive():
            self.display_stop_event.clear()
            self.display_thread = threading.Thread(target=self.display_bpm, daemon=True)
            self.display_thread.start()
    
    def _repeat_bpm_change(self, direction, step):
        """Repeatedly change BPM while joystick is held.
        
        Uses timeout to detect when joystick is released (no new events).
        
        Args:
            direction: 'up' or 'down'
            step: Amount to change BPM by
        """
        # Initial delay to avoid accidental rapid changes
        time.sleep(0.3)
        
        # Then repeat with shorter interval, checking for timeout
        timeout = 0.2  # If no new event in 200ms, assume released
        while not self.repeat_stop_event.is_set() and self.held_direction == direction:
            # Check if we've received a new event for this direction recently
            last_event_time = self.last_joystick_event_time.get(direction, 0)
            if time.time() - last_event_time > timeout:
                # No new event, assume joystick was released
                break
            
            if direction == 'up':
                self.increase_bpm(step)
            else:  # down
                self.decrease_bpm(step)
            time.sleep(0.15)  # Repeat every 150ms
    
    def handle_joystick(self, event):
        """Handle joystick events with repeat functionality."""
        if event.action == 'pressed':
            current_time = time.time()
            
            # Debounce joystick input
            if current_time - self.last_joystick_time < self.joystick_debounce:
                return
            
            self.last_joystick_time = current_time
            
            if event.direction == 'up':
                # Update last event time for this direction
                self.last_joystick_event_time['up'] = current_time
                
                # Stop any existing repeat
                self.held_direction = None
                self.repeat_stop_event.set()
                if self.repeat_thread and self.repeat_thread.is_alive():
                    self.repeat_thread.join(timeout=0.1)
                
                # Immediate change
                self.increase_bpm(1.0)
                
                # Start repeat thread
                self.held_direction = 'up'
                self.repeat_stop_event.clear()
                self.repeat_thread = threading.Thread(target=self._repeat_bpm_change, args=('up', 1.0), daemon=True)
                self.repeat_thread.start()
                
            elif event.direction == 'down':
                # Update last event time for this direction
                self.last_joystick_event_time['down'] = current_time
                
                # Stop any existing repeat
                self.held_direction = None
                self.repeat_stop_event.set()
                if self.repeat_thread and self.repeat_thread.is_alive():
                    self.repeat_thread.join(timeout=0.1)
                
                # Immediate change
                self.decrease_bpm(1.0)
                
                # Start repeat thread
                self.held_direction = 'down'
                self.repeat_stop_event.clear()
                self.repeat_thread = threading.Thread(target=self._repeat_bpm_change, args=('down', 1.0), daemon=True)
                self.repeat_thread.start()
                
            elif event.direction == 'middle':
                # Stop any repeat
                self.held_direction = None
                self.repeat_stop_event.set()
                
                # Toggle start/stop
                if self.running:
                    self.stop_clock()
                else:
                    self.start_clock()
                    
            elif event.direction == 'left':
                # Update last event time (use 'down' as the key since left decreases)
                self.last_joystick_event_time['down'] = current_time
                
                # Stop any existing repeat
                self.held_direction = None
                self.repeat_stop_event.set()
                if self.repeat_thread and self.repeat_thread.is_alive():
                    self.repeat_thread.join(timeout=0.1)
                
                # Immediate change
                self.decrease_bpm(0.1)
                
                # Start repeat thread for fine adjustment
                self.held_direction = 'down'  # Use 'down' for left (decrease)
                self.repeat_stop_event.clear()
                self.repeat_thread = threading.Thread(target=self._repeat_bpm_change, args=('down', 0.1), daemon=True)
                self.repeat_thread.start()
                
            elif event.direction == 'right':
                # Update last event time (use 'up' as the key since right increases)
                self.last_joystick_event_time['up'] = current_time
                
                # Stop any existing repeat
                self.held_direction = None
                self.repeat_stop_event.set()
                if self.repeat_thread and self.repeat_thread.is_alive():
                    self.repeat_thread.join(timeout=0.1)
                
                # Immediate change
                self.increase_bpm(0.1)
                
                # Start repeat thread for fine adjustment
                self.held_direction = 'up'  # Use 'up' for right (increase)
                self.repeat_stop_event.clear()
                self.repeat_thread = threading.Thread(target=self._repeat_bpm_change, args=('up', 0.1), daemon=True)
                self.repeat_thread.start()
    
    def run(self):
        """Main run loop."""
        print(f"\n{Colors.BRIGHT_CYAN}{Colors.BOLD}╔════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}{Colors.BOLD}║   MIDI Clock Master Started   ║{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}{Colors.BOLD}╚════════════════════════════════════╝{Colors.RESET}\n")
        print(f"{Colors.YELLOW}Controls:{Colors.RESET}")
        print(f"  {Colors.WHITE}Joystick Up:{Colors.RESET}    Increase BPM")
        print(f"  {Colors.WHITE}Joystick Down:{Colors.RESET}  Decrease BPM")
        print(f"  {Colors.WHITE}Joystick Left:{Colors.RESET}  Fine decrease BPM")
        print(f"  {Colors.WHITE}Joystick Right:{Colors.RESET} Fine increase BPM")
        print(f"  {Colors.WHITE}Joystick Press:{Colors.RESET} Start/Stop clock")
        print(f"\n{Colors.BRIGHT_RED}{Colors.BOLD}Current BPM: {self.bpm:.1f} (STOPPED){Colors.RESET}\n")
        
        # Start clock thread
        self.stop_event.clear()
        self.clock_thread = threading.Thread(target=self.send_midi_clock, daemon=True)
        self.clock_thread.start()
        
        # Register joystick callback
        self.sense.stick.direction_any = self.handle_joystick
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Shutting down...{Colors.RESET}")
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_clock()
        self.stop_event.set()
        self.display_stop_event.set()
        
        # Stop joystick repeat thread
        self.held_direction = None
        self.repeat_stop_event.set()
        if self.repeat_thread and self.repeat_thread.is_alive():
            self.repeat_thread.join(timeout=0.5)
        
        if self.clock_thread and self.clock_thread.is_alive():
            self.clock_thread.join(timeout=1.0)
        
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=1.0)
        
        # Close all MIDI ports
        for midiout, port_name in self.midiout_ports:
            try:
                midiout.close_port()
            except Exception as e:
                print(f"Error closing {port_name}: {e}")
        
        # Restore terminal settings
        if self.old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            except (AttributeError, OSError, termios.error):
                pass
        
        self.sense.clear()
        print(f"{Colors.BRIGHT_GREEN}✓ Cleanup complete{Colors.RESET}")

def main():
    """Main entry point."""
    try:
        # Try to create MIDI clock instance
        # midi_port=None will auto-detect ESI MIDIMATE eX, or specify port number manually
        # Example: MIDIClock(midi_port=1) to use port 1
        clock = MIDIClock(midi_port=None)
        clock.run()
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

