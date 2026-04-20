import time
import socket
import threading
import random
import platform
import serial
import serial.tools.list_ports
from enum import Enum
from time import sleep
import os
import json
from datetime import datetime

# --- CONFIGURATION ---
# REPLACE THESE WITH YOUR ACTUAL ARDUINO SERIAL NUMBERS
GANTRY_SERIAL = "48CA435A3A20" 
STIRRER_SERIAL = "0987654321FEDCBA"
SCOOP_SERIAL = "5555555555123456"

JETSON_IP = "10.42.0.76"
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
        # Safely handle both string and byte commands
        command = data.decode().strip() if isinstance(data, bytes) else str(data).strip()
        print(f"[MOCK {self.name}] Sending: {command}")
        
        # Simulate hardware sequence time
        time.sleep(self.dummy_responses.get("move_time", 1.5))
        
        # FIX: Send standard success code "Y" + elapsed ms instead of "Finished"
        self._mock_response_queue.append("Y1500") 

    def readline(self):
        if self._mock_response_queue:
            response = self._mock_response_queue.pop(0)
            print(f"[MOCK {self.name}] Receiving: {response.strip()}")
            return response.encode() if isinstance(response, str) else response
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
        self.total_samples = 40 # Default
        self.soil_weight = 10 # Default dispensing weight in grams
        
        # Individual Device Modes: "real" or "dummy"
        self.device_modes = {
            "gantry": "dummy",
            "stirrer": "dummy",
            "scoop": "dummy",
            "jetson": "real", # Keeping Jetson dummy until you have the script running
            "doors": "real"
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
        self.logs = ["SoilSense v7.0 Engine Online."]
        self.soil_results = {}
        self.currentSampleIndex = -1 # -1 means not started
        self.scooper_status = "Idle"
        self.last_image = None
        
        self.scoop_size = "Small" # Default preset
        
        self.dummy_responses = {
            "soil_types": ["Loam", "Clay", "Silt", "Sand"],
            "move_time": 1.5,
            "analyze_time": 2.0
        }

        self.ports = {"gantry": None, "stirrer": None, "scoop": None}
        
        # Callbacks
        self.on_log_update = None
        self.on_sequence_update = None
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

    def toggle_dummy_door(self, side):
        if side == "left" and isinstance(self.left_door, MockDoor):
            self.left_door.toggle()
        elif side == "right" and isinstance(self.right_door, MockDoor):
            self.right_door.toggle()
        
        if self.on_status_update:
            self.on_status_update()

    def update_samples(self, count):
        self.total_samples = count
        self.soil_results = {}
        self.log(f"Samples set to {count}")
        if self.on_sequence_update: self.on_sequence_update()

    def get_coords_from_index(self, index):
        """Converts sample index (0-39) to Gantry X,Y (0-9, 0-3)."""
        y = index // 10
        x = index % 10
        return x, y

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
        # Ensure command ends with a newline
        if isinstance(command, str):
            if not command.endswith('\n'):
                command += '\n'
            encoded_command = command.encode()
        elif isinstance(command, bytes):
            if not command.endswith(b'\n'):
                encoded_command = command + b'\n'
            else:
                encoded_command = command
        if self.ports.get(device):
            if self.statuses[device] == DeviceStatus.OFFLINE: return "F0"
            try:
                self.ports[device].write(encoded_command)
                raw_res = self.read_hardware(device)
                if raw_res and raw_res.startswith("Y"):
                    dur = raw_res[1:]
                    self.log(f"{device.upper()} success in {dur}ms")
                    return raw_res
                elif raw_res and raw_res.startswith("F"):
                    code = raw_res[1:]
                    error_map = {"0": "UNKNOWN COMMAND", "1": "INDEX OUT OF RANGE"}
                    err_msg = error_map.get(code, f"ERR_{code}")
                    self.log(f"{device.upper()} error: {err_msg}")
                    return raw_res
                return raw_res
            except Exception as e: 
                self.log(f"Write error on {device}: {e}")
                return "F9" # Generic communication error

    def read_hardware(self, device):
        current_time = time.time()
        if self.ports.get(device):
            while time.time() - current_time < 30:
                try:
                    data = self.ports[device].readline().decode().strip()
                    if data: return data
                except: return "F9"
                time.sleep(0.05)
            return "F8" # Timeout
        return "F0"

    def communicate_with_jetson(self, command):
        if self.device_modes["jetson"] == "dummy":
            time.sleep(self.dummy_responses["analyze_time"])
            classification = random.choice(self.dummy_responses["soil_types"])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mock_data = {"timestamp": timestamp, "classification": classification, "avg_value": round(random.uniform(100, 150), 2)}
            res_json = json.dumps(mock_data)
            img = f"https://picsum.photos/seed/{random.random()}/400/300"
            # Follow the protocol for Jetson too
            dur_ms = int(self.dummy_responses["analyze_time"] * 1000)
            return f"Y{dur_ms}", res_json, img
        else:
            try:
                startTime = time.time()
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(10)
                    s.connect((JETSON_IP, JETSON_PORT))
                    s.sendall(command.encode())
                    data = s.recv(4096).decode()
                    dur_ms = int((time.time() - startTime) * 1000)
                    return f"Y{dur_ms}", data, None
            except Exception as e:
                self.log(f"Jetson Comm Error: {e}")
                return "F9", None, None

    def stop_sequence(self):
        if not self.isRunning: return
        self.isRunning = False
        self.log("Stopping sequence and emergency stopping all hardware...")
        self.write_hardware("gantry", "S")
        self.write_hardware("stirrer", "STOP")
        self.write_hardware("scoop", "S")
        if self.on_sequence_update: self.on_sequence_update()

    def run_sequence(self):
        if self.isRunning: return
        if any(status == DeviceStatus.OFFLINE for status in self.door_statuses.values()):
            self.log("Cannot start: Doors open.")
            return
        if not all(status in [DeviceStatus.ONLINE, DeviceStatus.DUMMY] for status in self.statuses.values()):
            self.log("Cannot start: Hardware offline.")
            return
            
        self.isRunning = True
        self.soil_results = {}
        self.log(f"Starting analysis of {self.total_samples} samples (Target: {self.soil_weight}g)...")
        
        for i in range(self.total_samples):
            if not self.isRunning: break
            self.currentSampleIndex = i
            if self.on_sequence_update: self.on_sequence_update()
            
            x, y = self.get_coords_from_index(i)
            
            # 1. Gantry move stirrer to bag
            self.scooper_status = "Moving to Bag"
            self.log(f"Sample {i+1}: Moving Stirrer to Bag ({x},{y})...")
            self.write_hardware("gantry", f"B{x}{y}")
            if not self.isRunning: break
            
            # 2. Stir + take image
            self.scooper_status = "Stirring"
            self.log(f"Sample {i+1}: Stirring...")
            self.write_hardware("stirrer", "START")
            
            # Use a responsive sleep loop so it can be interrupted instantly
            for _ in range(20):
                if not self.isRunning: break
                time.sleep(0.1)
                
            if not self.isRunning: break
            self.write_hardware("stirrer", "STOP")
            if not self.isRunning: break
            
            self.scooper_status = "Analyzing"
            self.log(f"Sample {i+1}: Analyzing...")
            status, raw_res, img = self.communicate_with_jetson("A")
            if not self.isRunning: break
            
            if status.startswith("Y") and raw_res:
                try:
                    data = json.loads(raw_res)
                    self.soil_results[i] = data 
                    self.log(f"Result Sample {i+1}: {data.get('classification')}")
                except: self.soil_results[i] = {"classification": "Error"}
            else: 
                self.soil_results[i] = {"classification": "Offline"}
            self.last_image = img
            if self.on_sequence_update: self.on_sequence_update()

            # 3. Gantry move scooper to bag
            self.scooper_status = "Moving to Bag"
            self.log(f"Sample {i+1}: Moving Scooper to Bag ({x},{y})...")
            self.write_hardware("gantry", f"B{x}{y}")
            if not self.isRunning: break
            
            # 4. scoop() sequence
            self.scooper_status = "Scooping"
            self.log(f"Sample {i+1}: Performing Scoop Sequence...")
            self.write_hardware("scoop", "U")  # Open scoop
            if not self.isRunning: break
            
            self.write_hardware("scoop", "FD") # Flip down
            if not self.isRunning: break
            
            res = self.write_hardware("scoop", "L")  # Lower
            if not self.isRunning: break
            
            if res == "F1":
                self.log(f"WARNING: Bag {i+1} appears EMPTY. Skipping.")
                self.write_hardware("scoop", "R")
                self.write_hardware("scoop", "FU")
                continue

            self.write_hardware("scoop", "S")  # Close scoop
            if not self.isRunning: break
            self.write_hardware("scoop", "R")  # Raise
            if not self.isRunning: break
            self.write_hardware("scoop", "FU") # Flip up (Dispenser bottom)
            if not self.isRunning: break

            # 5. Gantry move to tube
            self.scooper_status = "Moving to Tube"
            self.log(f"Sample {i+1}: Moving to Tube ({x},{y})...")
            self.write_hardware("gantry", f"T{x}{y}")
            if not self.isRunning: break

            # 6. dispense(soilWeight)
            self.scooper_status = "Dispensing"
            self.log(f"Sample {i+1}: Dispensing {self.soil_weight}g...")
            self.write_hardware("scoop", f"D{self.soil_weight}")
            if not self.isRunning: break

            # 7. gantry move scoop back to bag
            self.scooper_status = "Returning to Bag"
            self.log(f"Sample {i+1}: Returning to Bag to clear scoop...")
            self.write_hardware("gantry", f"B{x}{y}")
            if not self.isRunning: break

            # 8. empty()
            self.scooper_status = "Emptying"
            self.log(f"Sample {i+1}: Vacating remaining soil...")
            self.write_hardware("scoop", "E")
            if not self.isRunning: break

        self.scooper_status = "Idle"
        if self.isRunning:
            self.log("Analysis Complete.")
        else:
            self.log("Sequence Stopped by User.")
        
        self.isRunning = False
        if self.on_sequence_update: self.on_sequence_update()

    def export_results_csv(self):
        import csv
        if not self.soil_results: return None
        filename = f"soil_analysis_v7_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            with open(filename, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Sample", "Timestamp", "Classification", "Avg_Value"])
                for i, data in self.soil_results.items():
                    writer.writerow([i+1, data.get("timestamp"), data.get("classification"), data.get("avg_value")])
            self.log(f"Exported to {filename}")
            return filename
        except Exception as e: self.log(f"Export error: {e}")
    
    def find_sd_card_path(self):
        """Attempts to find a mounted USB SD card/drive."""
        import platform
        import os

        system = platform.system()
        search_dirs = []

        if system == "Linux":
            # Common RPi mount points
            search_dirs = ["/media/pi", "/media"]
        elif system == "Darwin":
            # macOS mount points
            search_dirs = ["/Volumes"]

        for base in search_dirs:
            if not os.path.exists(base): continue
            for entry in os.listdir(base):
                full_path = os.path.join(base, entry)
                # Skip internal drives and hidden system volumes
                if os.path.isdir(full_path) and not entry.startswith(".") and "Macintosh" not in entry:
                    # Return the first external-looking directory
                    return full_path
        return None

    def zero_gantry(self):
        self.log("Zeroing gantry...")
        self.write_hardware("gantry", "Z")