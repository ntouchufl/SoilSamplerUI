import time
import socket
import threading
import random
import serial
import serial.tools.list_ports
from enum import Enum

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
    def write(self, data): 
        print(f"[MOCK {self.name}] Sending: {data.decode().strip()}")
    def close(self): 
        pass

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
            "jetson": "dummy" # Keeping Jetson dummy until you have the script running
        }
        
        # Device Statuses
        self.statuses = {
            "gantry": DeviceStatus.OFFLINE,
            "stirrer": DeviceStatus.OFFLINE,
            "scoop": DeviceStatus.OFFLINE,
            "jetson": DeviceStatus.OFFLINE
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

    def write_hardware(self, device, command):
        if self.ports.get(device):
            try:
                self.ports[device].write(command)
            except Exception as e:
                self.log(f"Write error on {device}: {e}")

    def communicate_with_jetson(self, command):
        if self.device_modes["jetson"] == "dummy":
            time.sleep(self.dummy_responses["analyze_time"])
            res = random.choice(self.dummy_responses["soil_types"])
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
        self.isRunning = True
        self.soil_results = {}
        if self.on_grid_update: self.on_grid_update()
        
        self.log(f"Starting {self.grid_rows}x{self.grid_cols} Grid Analysis...")
        dist = 5.0 
        
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                if not self.isRunning: break
                self.currentRow, self.currentCol = r, c
                if self.on_grid_update: self.on_grid_update()
                
                # 1. Gantry Move
                target_x, target_y = c * dist, r * dist
                self.log(f"Moving Gantry to [{r},{c}]")
                self.write_hardware("gantry", f"MOVE {target_x},{target_y}\n".encode())
                time.sleep(self.dummy_responses["move_time"]) 
                
                # 2. Scoop Down
                self.log("Lowering scoop...")
                self.write_hardware("scoop", b"DOWN\n")
                time.sleep(1)
                
                # 3. Stir Sample
                self.log("Stirring soil...")
                self.write_hardware("stirrer", b"START\n")
                time.sleep(2)
                self.write_hardware("stirrer", b"STOP\n")
                
                # 4. Scoop Up
                self.log("Raising scoop...")
                self.write_hardware("scoop", b"UP\n")
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

    def stop_sequence(self):
        self.isRunning = False
        self.log("Sequence Aborted by User.")