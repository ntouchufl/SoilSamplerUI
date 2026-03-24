import time
import serial

# --- CONFIGURATION ---
GANTRY_PORT = "/dev/ttyACM0"
STIRRER_PORT = "/dev/ttyACM1"
SCOOP_PORT = "/dev/ttyACM2"

class MockSerial:
    def __init__(self, name): self.name = name
    def write(self, data): print(f"[MOCK {self.name}] Sending: {data.decode().strip()}")
    def close(self): pass

class SoilSenseLogic:
    def __init__(self):
        self.dummyMode = True  
        self.isRunning = False
        self.logs = ["SoilSense v5.0 Engine Online."]
        self.soil_results = [None] * 9 # 3x3 Grid
        self.currentRow = 0
        self.currentCol = 0
        self.ports = {"gantry": None, "stirrer": None, "scoop": None}
        
        # Callbacks (These will be linked to the UI later)
        self.on_log_update = None
        self.on_grid_update = None

        self.init_hardware()

    def init_hardware(self):
        if self.dummyMode:
            self.ports = {k: MockSerial(k.upper()) for k in ["gantry", "stirrer", "scoop"]}
        else:
            try:
                self.ports["gantry"] = serial.Serial(GANTRY_PORT, 115200, timeout=1)
                self.ports["stirrer"] = serial.Serial(STIRRER_PORT, 9600, timeout=1)
                self.ports["scoop"] = serial.Serial(SCOOP_PORT, 9600, timeout=1)
            except Exception as e:
                print(f"Serial Error: {e}. Falling back to Dummy Mode.")
                self.dummyMode = True
                self.ports = {k: MockSerial(k.upper()) for k in ["gantry", "stirrer", "scoop"]}

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")
        if len(self.logs) > 40: self.logs.pop(0)
        
        # Tell the UI to update the log list
        if self.on_log_update:
            self.on_log_update()

    def set_dummy_mode(self, is_dummy):
        self.dummyMode = is_dummy
        self.init_hardware()
        self.log(f"Mode: {'Dummy' if self.dummyMode else 'Hardware'}")

    def write_hardware(self, device, command):
        """Helper function to manually trigger hardware from UI"""
        if self.ports[device]:
            self.ports[device].write(command)

    def run_sequence(self):
        self.isRunning = True
        if self.on_grid_update: self.on_grid_update()
        self.log("Starting automated soil analysis...")
        
        dist = 5.0 
        
        for i in range(9):
            if not self.isRunning: break
            row, col = i // 3, i % 3
            self.currentRow, self.currentCol = row, col
            
            # 1. Gantry Move
            target_x, target_y = col * dist, row * dist
            self.log(f"Moving Gantry to Grid [{row},{col}] -> ({target_x}, {target_y})")
            self.write_hardware("gantry", f"{target_x},{target_y}\n".encode())
            time.sleep(2) 
            
            # 2. Scoop Down
            self.log("Lowering scoop...")
            self.write_hardware("scoop", b"1\n")
            time.sleep(1)
            
            # 3. Stir Sample
            self.log("Stirring soil sample...")
            self.write_hardware("stirrer", b"1\n")
            time.sleep(3)
            self.write_hardware("stirrer", b"0\n")
            
            # 4. Scoop Up
            self.log("Raising scoop...")
            self.write_hardware("scoop", b"0\n")
            time.sleep(1)
            
            # 5. Analyze 
            self.log("Analyzing with Jetson Nano...")
            self.soil_results[i] = "Loam" if (row + col) % 2 == 0 else "Clay"
            
            # Tell the UI to redraw the grid
            if self.on_grid_update: self.on_grid_update()

        self.log("Full Grid Analysis Complete.")
        self.isRunning = False
        if self.on_grid_update: self.on_grid_update()