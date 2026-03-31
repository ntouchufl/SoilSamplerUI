import time
import socket
import threading
import random
import platform
import serial
import serial.tools.list_ports
from enum import Enum
from time import sleep

# --- CONFIGURATION ---
# REPLACE THESE WITH YOUR ACTUAL ARDUINO SERIAL NUMBERS
GANTRY_SERIAL = "48CA435A3A20" 
STIRRER_SERIAL = "0987654321FEDCBA"
SCOOP_SERIAL = "5555555555123456"

JETSON_IP = "192.168.1.100"
JETSON_PORT = 5005

class DeviceStatus(Enum):
    OFFLINE = "#ff4444"
    DUMMY = "#ffeb3b"
    ONLINE = "#00ff41"

class MockSerial:
    def __init__(self, name):
        self.name = name
        self._mock_response_queue = [] # To simulate responses
        self.dummy_responses = {} # This will be set by init_hardware to pass the reference
    def write(self, data):
        command = data.decode().strip()
        print(f"[MOCK {self.name}] Sending: {command}")
        # Simulate an ACK/response for common commands
        time.sleep(self.dummy_responses["move_time"])
        self._mock_response_queue.append("Finished\n") # Default ACK

    def readline(self):
        if self._mock_response_queue:
            response = self._mock_response_queue.pop(0)
            print(f"[MOCK {self.name}] Receiving: {response.strip()}")
            return response.encode()
        return b"" # Simulate no data if queue is empty

    def close(self):
        pass

class MockDoor:
    """A mock door class that mimics gpiozero.Button for consistent behavior."""
    def __init__(self, name: str):
        self.name = name
        # Start in a "pressed" (closed) state by default
        self.pressed = True

    @property
    def is_pressed(self) -> bool:
        return self.pressed

    def toggle(self):
        self.pressed = not self.pressed

class SoilSenseLogic:
    def __init__(self):
        # Grid Configuration
        self.grid_rows = 3
        self.grid_cols = 3
        
        # Individual Device Modes: "real" or "dummy"
        self.device_modes = {
            "gantry": "real",
            "stirrer": "dummy",
            "scoop": "dummy",
            "jetson": "dummy", # Keeping Jetson dummy until you have the script running
            "doors": "dummy"
        }
        
        # Device Statuses
        self.statuses = {
            "gantry": DeviceStatus.OFFLINE,
            "stirrer": DeviceStatus.OFFLINE,
            "scoop": DeviceStatus.OFFLINE,
            "jetson": DeviceStatus.OFFLINE,
            "doors": DeviceStatus.OFFLINE
        }

        self.isRunning = False
        self.logs = ["SoilSense v6.0 Engine Online."]
        self.soil_results = {}
        self.currentRow = 0
        self.currentCol = 0
        self.last_image = None
        
        self.dummy_responses = {
            "soil_types": ["Loam", "Clay", "Silt", "Sand"],
            "move_time": 1.5,
            "analyze_time": 2.0
        }

        self.ports = {"gantry": None, "stirrer": None, "scoop": None}
        
        # Callbacks
        self.on_log_update = None
        self.on_grid_update = None
        self.on_status_update = None

        self.door_statuses = {
            "left": DeviceStatus.OFFLINE,  # OFFLINE (Red) will represent Open
            "right": DeviceStatus.OFFLINE
        }

        self.left_door = None
        self.right_door = None

        # Start the background door monitoring thread
        threading.Thread(target=self._door_monitor, daemon=True).start()

        self.init_hardware()

    def find_port_by_serial(self, target_serial):
        """Scans all USB ports and returns the OS path for the matching serial number."""
        available_ports = serial.tools.list_ports.comports()
        for port in available_ports:
            # Some devices return None for serial_number, so we must check if it exists
            if port.serial_number and target_serial in port.serial_number:
                return port.device
        return None

    def init_hardware(self):
        self.log("Scanning USB bus for hardware...")
        
        serial_map = {"gantry": GANTRY_SERIAL, "stirrer": STIRRER_SERIAL, "scoop": SCOOP_SERIAL}
        baud_map = {"gantry": 115200, "stirrer": 9600, "scoop": 9600}
        
        for device in ["gantry", "stirrer", "scoop"]:
            if self.device_modes[device] == "dummy":
                self.ports[device] = MockSerial(device.upper())
                self.statuses[device] = DeviceStatus.DUMMY
            else:
                try:
                    # Look up the dynamic OS port (e.g., COM3 or /dev/ttyACM0)
                    target_sn = serial_map[device]
                    actual_port = self.find_port_by_serial(target_sn)
                    
                    if actual_port is None:
                        raise Exception(f"Serial '{target_sn}' not found on USB bus.")
                        
                    self.ports[device] = serial.Serial(actual_port, baud_map[device], timeout=1)
                    self.statuses[device] = DeviceStatus.ONLINE
                    self.log(f"Connected {device.upper()} on {actual_port}")
                except Exception as e:
                    self.log(f"Error connecting {device}: {e}")
                    self.statuses[device] = DeviceStatus.OFFLINE
                    self.ports[device] = None

        # After all ports are initialized, set dummy_responses for MockSerial instances
        for device in ["gantry", "stirrer", "scoop"]:
            if self.device_modes[device] == "dummy":
                self.ports[device].dummy_responses = self.dummy_responses

        # --- Door Initialization ---
        # On macOS, doors can only be in dummy mode.
        if platform.system() == "Darwin" and self.device_modes["doors"] == "real":
            self.log("Cannot use real doors on macOS. Forcing DUMMY mode.")
            self.device_modes["doors"] = "dummy"

        if self.device_modes["doors"] == "dummy":
            self.statuses["doors"] = DeviceStatus.DUMMY
            if not isinstance(self.left_door, MockDoor):
                self.left_door = MockDoor("left")
            if not isinstance(self.right_door, MockDoor):
                self.right_door = MockDoor("right")
            self.log("Doors operating in DUMMY mode.")
        else:  # Real mode on a capable system (e.g., Pi)
            try:
                from gpiozero import Button
                if not isinstance(self.left_door, Button):
                    self.left_door = Button(17, pull_up=True)
                if not isinstance(self.right_door, Button):
                    self.right_door = Button(27, pull_up=True)
                self.statuses["doors"] = DeviceStatus.ONLINE
                self.log("Doors operating in REAL mode.")
            except Exception as e:
                self.log(f"Door GPIO init failed: {e}. Reverting to DUMMY mode.")
                self.device_modes["doors"] = "dummy"
                self.statuses["doors"] = DeviceStatus.DUMMY
                self.left_door = MockDoor("left")
                self.right_door = MockDoor("right")

        # Initialize Jetson
        if self.device_modes["jetson"] == "dummy":
            self.statuses["jetson"] = DeviceStatus.DUMMY
        else:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect((JETSON_IP, JETSON_PORT))
                s.close()
                self.statuses["jetson"] = DeviceStatus.ONLINE
            except:
                self.statuses["jetson"] = DeviceStatus.OFFLINE

        if self.on_status_update:
            self.on_status_update()

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")
        if len(self.logs) > 50: self.logs.pop(0)
        if self.on_log_update:
            self.on_log_update()

    def set_device_mode(self, device, mode):
        self.device_modes[device] = mode
        self.init_hardware()
        self.log(f"{device.capitalize()} set to {mode} mode.")

    def update_grid_size(self, rows, cols):
        self.grid_rows = rows
        self.grid_cols = cols
        self.soil_results = {}
        self.log(f"Grid resized to {rows}x{cols}")
        if self.on_grid_update:
            self.on_grid_update()

    def _door_monitor(self):
        last_left_state = None
        last_right_state = None
        
        # Trackers for how long doors have been open
        left_open_timestamp = None
        right_open_timestamp = None

        while True:
            # This loop now runs for both real and dummy doors, as long as the objects are created.
            if self.left_door and self.right_door:
                current_left_closed = self.left_door.is_pressed
                current_right_closed = self.right_door.is_pressed

                # --- 1-SECOND SAFETY INTERLOCK LOGIC ---
                
                # Check Left Door
                if not current_left_closed:  # Door is open
                    if left_open_timestamp is None:
                        left_open_timestamp = time.time()  # Start the clock
                    elif self.isRunning and (time.time() - left_open_timestamp > 1.0):
                        self.log("SAFETY INTERLOCK: Left door open > 1s!")
                        self.stop_sequence()
                else:
                    left_open_timestamp = None  # Reset clock when closed

                # Check Right Door
                if not current_right_closed:  # Door is open
                    if right_open_timestamp is None:
                        right_open_timestamp = time.time()  # Start the clock
                    elif self.isRunning and (time.time() - right_open_timestamp > 1.0):
                        self.log("SAFETY INTERLOCK: Right door open > 1s!")
                        self.stop_sequence()
                else:
                    right_open_timestamp = None  # Reset clock when closed

                # --- UI REFRESH LOGIC ---
                if current_left_closed != last_left_state or current_right_closed != last_right_state:
                    self.door_statuses["left"] = DeviceStatus.ONLINE if current_left_closed else DeviceStatus.OFFLINE
                    self.door_statuses["right"] = DeviceStatus.ONLINE if current_right_closed else DeviceStatus.OFFLINE
                    
                    left_str = "Closed" if current_left_closed else "Open"
                    right_str = "Closed" if current_right_closed else "Open"
                    # Only log if it's a real state change, not just the first run
                    if last_left_state is not None:
                        self.log(f"Door state changed - Left: {left_str}, Right: {right_str}")
                    if self.on_status_update:
                        self.on_status_update()
                    
                    last_left_state = current_left_closed
                    last_right_state = current_right_closed
            
            time.sleep(0.1)



    def write_hardware(self, device, command):
        if self.ports.get(device):
            if self.statuses[device] == DeviceStatus.OFFLINE:
                self.log(f"Attempted to write to OFFLINE device {device}")
                return
            try:
                self.ports[device].write(command)
                self.log(f"Sent to {device}: {command.decode().strip()}") # Log the sent command
                
                msg = self.read_hardware(device)
                
                if msg == "Error": # From read_hardware
                    self.log(f"Read error from {device}")
                elif msg == "Timeout": # From read_hardware
                    self.log(f"Read timeout from {device}")
                elif msg == "Finished": # Expected ACK from Arduino
                    self.log(f"ACK from {device}: {msg}")
                elif msg: # Any other non-empty message is considered data
                    self.log(f"Received data from {device}: {msg}")
                    return msg
                
            except Exception as e:
                self.log(f"Write error on {device}: {e}")
        else:
            self.log(f"Attempted to write to non-existent port for {device}")

    def read_hardware(self, device):
        current_time = time.time()
        if self.ports.get(device):
            if self.statuses[device] == DeviceStatus.OFFLINE:
                self.log(f"Attempted to read from OFFLINE device {device}")
                return "Error"

            while time.time() - current_time < 30: # Loop for 30 seconds max
                try:
                    data = self.ports[device].readline().decode().strip()
                    if data:
                        return data # Data received, return it immediately
                except Exception as e:
                    self.log(f"Read error on {device}: {e}")
                    return "Error"
                time.sleep(0.05) # Prevent busy-waiting if readline returns empty
            self.log(f"Read timeout on {device}")
            return "Timeout"
        return None # No port object for the device

    def communicate_with_jetson(self, command):
        if self.device_modes["jetson"] == "dummy":
            goofy = False
            
            time.sleep(self.dummy_responses["analyze_time"])
            res = random.choice(self.dummy_responses["soil_types"])
            if goofy:
                img_num = random.randomint(1,3)
                img = f"/IM{img_num}.jpg"
            else:
                img = f"https://picsum.photos/seed/{random.random()}/400/300"
            return res, img
        else:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    s.connect((JETSON_IP, JETSON_PORT))
                    s.sendall(command.encode())
                    data = s.recv(4096).decode()
                    parts = data.split("|")
                    soil_type = parts[0]
                    image_data = parts[1] if len(parts) > 1 else None
                    return soil_type, image_data
            except Exception as e:
                self.log(f"Jetson Comm Error: {e}")
                return "Error", None

    def run_sequence(self):
        if self.isRunning: return

        # Check if doors are open before starting
        if any(status == DeviceStatus.OFFLINE for status in self.door_statuses.values()):
            self.log("Cannot start sequence: One or more doors are open.")
            return

        if not all(status in [DeviceStatus.ONLINE, DeviceStatus.DUMMY] for status in self.statuses.values()):
            self.log("Cannot start sequence: One or more devices are OFFLINE.")
            return
        self.isRunning = True
        self.soil_results = {}
        if self.on_grid_update: self.on_grid_update()
        
        self.log(f"Starting {self.grid_rows}x{self.grid_cols} Grid Analysis...")
        dist = 1.0 # gantry can do math on where that actually is
        
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                if not self.isRunning: break
                self.currentRow, self.currentCol = r, c
                if self.on_grid_update: self.on_grid_update()
                
                # 1. Gantry Move
                target_x, target_y = c * dist, r * dist
                self.log(f"Moving Gantry to [{r},{c}]")
                self.write_hardware("gantry", f"MOVE {target_x},{target_y}\n".encode()) #THIS IS COMMAND TO GANTRY
                
                # 2. Scoop Down
                self.log("Lowering scoop...")
                self.write_hardware("scoop", b"DOWN\n") #THIS IS COMMAND TO SCOOP
                time.sleep(1)
                
                # 3. Stir Sample
                self.log("Stirring soil...")
                self.write_hardware("stirrer", b"START\n") #THIS IS COMMAND TO STIR
                time.sleep(2)
                self.write_hardware("stirrer", b"STOP\n") #THIS IS COMMAND TO STOP STIR
                
                # 4. Scoop Up
                self.log("Raising scoop...")
                self.write_hardware("scoop", b"UP\n") #THIS IS COMMAND TO UP SCOOP
                time.sleep(1)
                
                # 5. Analyze with Jetson
                self.log("Requesting Jetson Analysis...")
                soil_type, img = self.communicate_with_jetson(f"ANALYZE {r},{c}")
                self.soil_results[(r, c)] = soil_type
                self.last_image = img
                
                if self.on_grid_update: self.on_grid_update()

        self.log("Grid Analysis Complete.")
        self.isRunning = False
        if self.on_grid_update: self.on_grid_update()

    def toggle_dummy_door(self, door: str):
        """Toggles the state of a dummy door ('left' or 'right')."""
        if self.device_modes.get("doors") != "dummy":
            self.log("Cannot toggle door state in 'real' mode.")
            return

        door_obj = self.left_door if door == "left" else self.right_door

        if not isinstance(door_obj, MockDoor):
            self.log(f"Error: Cannot toggle non-mock door '{door}'.")
            return

        door_obj.toggle()
        state_str = "Open" if not door_obj.is_pressed else "Closed"

        # The _door_monitor thread will pick up the change and update the UI status,
        # but we can log the action immediately for responsiveness.
        self.log(f"Dummy {door} door set to: {state_str}")
        # We no longer need to manually trigger a UI update here, as the
        # _door_monitor is the single source of truth and will fire the
        # on_status_update callback when it detects the state change.


    def stop_sequence(self):
        self.isRunning = False
        self.log("EMERGENCY STOP TRIGGERED. Halting hardware.")
        
        # Blast a STOP command to all moving parts
        self.write_hardware("gantry", b"STOP\n")
        self.write_hardware("stirrer", b"STOP\n")
        self.write_hardware("scoop", b"STOP\n")
        
        # Update the UI to re-enable the Start button
        if self.on_grid_update: 
            self.on_grid_update()