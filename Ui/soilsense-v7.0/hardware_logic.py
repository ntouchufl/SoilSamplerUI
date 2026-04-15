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
        self._mock_response_queue = []
        self.dummy_responses = {}
    def write(self, data):
        command = data.decode().strip()
        print(f"[MOCK {self.name}] Sending: {command}")
        time.sleep(self.dummy_responses.get("move_time", 1.5))
        self._mock_response_queue.append("Finished\n")

    def readline(self):
        if self._mock_response_queue:
            response = self._mock_response_queue.pop(0)
            print(f"[MOCK {self.name}] Receiving: {response.strip()}")
            return response.encode()
        return b""

    def close(self):
        pass

class MockDoor:
    def __init__(self, name: str):
        self.name = name
        self.pressed = True
    @property
    def is_pressed(self) -> bool:
        return self.pressed
    def toggle(self):
        self.pressed = not self.pressed

class SoilSenseLogic:
    def __init__(self):
        self.total_samples = 5 # Default
        
        self.device_modes = {
            "gantry": "dummy",
            "stirrer": "dummy",
            "scoop": "dummy",
            "jetson": "dummy",
            "doors": "real"
        }
        
        self.statuses = {
            "gantry": DeviceStatus.OFFLINE,
            "stirrer": DeviceStatus.OFFLINE,
            "scoop": DeviceStatus.OFFLINE,
            "jetson": DeviceStatus.OFFLINE,
            "doors": DeviceStatus.OFFLINE
        }

        self.isRunning = False
        self.logs = ["SoilSense v7.0 Engine Online."]
        self.soil_results = {} # Indexed by sample index (0 to total_samples-1)
        self.currentSampleIndex = -1 # -1 means not started
        self.last_image = None
        
        self.scoop_size = "Small"
        
        self.dummy_responses = {
            "soil_types": ["Loam", "Clay", "Silt", "Sand"],
            "move_time": 1.5,
            "analyze_time": 2.0
        }

        self.ports = {"gantry": None, "stirrer": None, "scoop": None}
        
        # Callbacks
        self.on_log_update = None
        self.on_status_update = None
        self.on_sequence_update = None # Replaces grid update

        self.door_statuses = {
            "left": DeviceStatus.OFFLINE,
            "right": DeviceStatus.OFFLINE
        }

        self.left_door = None
        self.right_door = None

        threading.Thread(target=self._door_monitor, daemon=True).start()
        self.init_hardware()

    def find_port_by_serial(self, target_serial):
        available_ports = serial.tools.list_ports.comports()
        for port in available_ports:
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
                    target_sn = serial_map[device]
                    actual_port = self.find_port_by_serial(target_sn)
                    if actual_port is None:
                        raise Exception(f"Serial '{target_sn}' not found.")
                    self.ports[device] = serial.Serial(actual_port, baud_map[device], timeout=1)
                    self.statuses[device] = DeviceStatus.ONLINE
                    self.log(f"Connected {device.upper()} on {actual_port}")
                except Exception as e:
                    self.log(f"Error connecting {device}: {e}")
                    self.statuses[device] = DeviceStatus.OFFLINE
                    self.ports[device] = None

        for device in ["gantry", "stirrer", "scoop"]:
            if self.device_modes[device] == "dummy":
                self.ports[device].dummy_responses = self.dummy_responses

        if platform.system() == "Darwin" and self.device_modes["doors"] == "real":
            self.log("Cannot use real doors on macOS. Forcing DUMMY mode.")
            self.device_modes["doors"] = "dummy"

        if self.device_modes["doors"] == "dummy":
            self.statuses["doors"] = DeviceStatus.DUMMY
            if not isinstance(self.left_door, MockDoor): self.left_door = MockDoor("left")
            if not isinstance(self.right_door, MockDoor): self.right_door = MockDoor("right")
        else:
            try:
                from gpiozero import Button
                if not isinstance(self.left_door, Button): self.left_door = Button(17, pull_up=True)
                if not isinstance(self.right_door, Button): self.right_door = Button(27, pull_up=True)
                self.statuses["doors"] = DeviceStatus.ONLINE
            except Exception as e:
                self.log(f"Door GPIO init failed: {e}. Reverting to DUMMY.")
                self.device_modes["doors"] = "dummy"
                self.statuses["doors"] = DeviceStatus.DUMMY
                self.left_door = MockDoor("left")
                self.right_door = MockDoor("right")

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

        if self.on_status_update: self.on_status_update()

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")
        if len(self.logs) > 50: self.logs.pop(0)
        if self.on_log_update: self.on_log_update()

    def set_device_mode(self, device, mode):
        self.device_modes[device] = mode
        self.init_hardware()
        self.log(f"{device.capitalize()} set to {mode} mode.")

    def toggle_dummy_door(self, side):
        if side == "left" and isinstance(self.left_door, MockDoor): self.left_door.toggle()
        elif side == "right" and isinstance(self.right_door, MockDoor): self.right_door.toggle()
        if self.on_status_update: self.on_status_update()

    def update_samples(self, count):
        self.total_samples = count
        self.soil_results = {}
        self.log(f"Samples set to {count}")
        if self.on_sequence_update: self.on_sequence_update()

    def _door_monitor(self):
        last_left_state = None
        last_right_state = None
        left_open_timestamp = None
        right_open_timestamp = None
        while True:
            if self.left_door and self.right_door:
                current_left_closed = self.left_door.is_pressed
                current_right_closed = self.right_door.is_pressed
                if not current_left_closed:
                    if left_open_timestamp is None: left_open_timestamp = time.time()
                    elif self.isRunning and (time.time() - left_open_timestamp > 1.0):
                        self.log("SAFETY INTERLOCK: Left door open > 1s!")
                        self.stop_sequence()
                else: left_open_timestamp = None
                if not current_right_closed:
                    if right_open_timestamp is None: right_open_timestamp = time.time()
                    elif self.isRunning and (time.time() - right_open_timestamp > 1.0):
                        self.log("SAFETY INTERLOCK: Right door open > 1s!")
                        self.stop_sequence()
                else: right_open_timestamp = None
                if current_left_closed != last_left_state or current_right_closed != last_right_state:
                    self.door_statuses["left"] = DeviceStatus.ONLINE if current_left_closed else DeviceStatus.OFFLINE
                    self.door_statuses["right"] = DeviceStatus.ONLINE if current_right_closed else DeviceStatus.OFFLINE
                    if self.on_status_update: self.on_status_update()
                    last_left_state = current_left_closed
                    last_right_state = current_right_closed
            time.sleep(0.1)

    def write_hardware(self, device, command):
        if self.ports.get(device):
            if self.statuses[device] == DeviceStatus.OFFLINE: return
            try:
                self.ports[device].write(command)
                return self.read_hardware(device)
            except Exception as e: self.log(f"Write error on {device}: {e}")

    def read_hardware(self, device):
        current_time = time.time()
        if self.ports.get(device):
            while time.time() - current_time < 30:
                try:
                    data = self.ports[device].readline().decode().strip()
                    if data: return data
                except: return "Error"
                time.sleep(0.05)
            return "Timeout"

    def communicate_with_jetson(self, command):
        if self.device_modes["jetson"] == "dummy":
            time.sleep(self.dummy_responses["analyze_time"])
            classification = random.choice(self.dummy_responses["soil_types"])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mock_data = {"timestamp": timestamp, "classification": classification, "avg_value": round(random.uniform(100, 150), 2)}
            res_json = json.dumps(mock_data)
            img = f"https://picsum.photos/seed/{random.random()}/400/300"
            return res_json, img
        else:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    s.connect((JETSON_IP, JETSON_PORT))
                    s.sendall(command.encode())
                    data = s.recv(4096).decode()
                    return data, None
            except Exception as e:
                self.log(f"Jetson Comm Error: {e}")
                return None, None

    def stop_sequence(self):
        if not self.isRunning: return
        self.isRunning = False
        self.log("Stopping sequence and emergency stopping all hardware...")
        self.write_hardware("gantry", b"STOP\n")
        self.write_hardware("stirrer", b"STOP\n")
        self.write_hardware("scoop", b"STOP\n")
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
        self.log(f"Starting analysis of {self.total_samples} samples...")
        dist = 1.0 
        for i in range(self.total_samples):
            if not self.isRunning: break
            self.currentSampleIndex = i
            if self.on_sequence_update: self.on_sequence_update()
            
            self.log(f"Sample {i+1}/{self.total_samples}: Moving Gantry...")
            self.write_hardware("gantry", f"MOVE {i * dist},0\n".encode())
            
            self.log(f"Sample {i+1}/{self.total_samples}: Lowering scoop...")
            self.write_hardware("scoop", f"DOWN {self.scoop_size}\n".encode())
            time.sleep(1)
            
            self.log(f"Sample {i+1}/{self.total_samples}: Stirring...")
            self.write_hardware("stirrer", b"START\n")
            time.sleep(2)
            self.write_hardware("stirrer", b"STOP\n")
            
            self.log(f"Sample {i+1}/{self.total_samples}: Raising scoop...")
            self.write_hardware("scoop", b"UP\n")
            time.sleep(1)
            
            self.log(f"Sample {i+1}/{self.total_samples}: Analyzing...")
            raw_res, img = self.communicate_with_jetson(f"ANALYZE {i}")
            if raw_res:
                try:
                    data = json.loads(raw_res)
                    self.soil_results[i] = data 
                    self.log(f"Result Sample {i+1}: {data.get('classification')} (Value: {data.get('avg_value')})")
                except: self.soil_results[i] = {"classification": "Error"}
            else: self.soil_results[i] = {"classification": "Offline"}
            self.last_image = img
            if self.on_sequence_update: self.on_sequence_update()

        self.log("Analysis Complete.")
        self.isRunning = False
        if self.on_sequence_update: self.on_sequence_update()

    def export_results_csv(self):
        import csv
        if not self.soil_results: return None
        sd_path = None # Simplified for brevity, same logic as v6
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
