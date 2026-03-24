import os
import time
import json
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- CONFIGURATION ---
GANTRY_PORT = "/dev/ttyACM0"
STIRRER_PORT = "/dev/ttyACM1"
SCOOP_PORT = "/dev/ttyACM2"
JETSON_IP = "192.168.1.100"

app = Flask(__name__)
CORS(app)

# --- SYSTEM STATE ---
state = {
    "gantry": {"x": 0, "y": 0, "status": "disconnected", "targetX": 0, "targetY": 0},
    "stirrer": {"active": False, "status": "disconnected"},
    "scoop": {"position": "up", "status": "disconnected"},
    "jetson": {"status": "disconnected", "ip": JETSON_IP},
    "process": {
        "isRunning": False,
        "currentRow": 0,
        "currentCol": 0,
        "soilTypes": [],
        "logs": ["Python Logic Engine Initialized."]
    },
    "config": {
        "rows": 3,
        "cols": 3,
        "dist": 5.0
    },
    "dummyMode": True
}

# --- MOCK SERIAL FOR MAC/DEV ---
class MockSerial:
    def __init__(self, name):
        self.name = name
        self.isOpen = True
    def write(self, data):
        print(f"[MOCK {self.name}] Writing: {data.decode().strip()}")
    def close(self):
        self.isOpen = False

# --- HARDWARE INITIALIZATION ---
ports = {"gantry": None, "stirrer": None, "scoop": None}

def init_hardware():
    global ports
    if state["dummyMode"]:
        ports = {k: MockSerial(k.upper()) for k in ports}
        return

    try:
        import serial
        # Real Serial Init
        # ports["gantry"] = serial.Serial(GANTRY_PORT, 115200, timeout=1)
        # ports["stirrer"] = serial.Serial(STIRRER_PORT, 9600, timeout=1)
        # ports["scoop"] = serial.Serial(SCOOP_PORT, 9600, timeout=1)
    except Exception as e:
        log(f"Hardware Init Error: {e}. Falling back to mocks.")
        ports = {k: MockSerial(k.upper()) for k in ports}

def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    state["process"]["logs"].append(full_msg)
    if len(state["process"]["logs"]) > 100:
        state["process"]["logs"].pop(0)

# --- PROCESS LOGIC (THE BRAIN) ---
def run_sequence():
    log("Starting automated soil analysis sequence...")
    state["process"]["isRunning"] = True
    rows = state["config"]["rows"]
    cols = state["config"]["cols"]
    dist = state["config"]["dist"]
    
    state["process"]["soilTypes"] = [None] * (rows * cols)

    try:
        for r in range(rows):
            if not state["process"]["isRunning"]: break
            state["process"]["currentRow"] = r
            for c in range(cols):
                if not state["process"]["isRunning"]: break
                state["process"]["currentCol"] = c
                
                # 1. Move Gantry
                target_x = c * dist
                target_y = r * dist
                log(f"Moving to Grid [{r},{c}] -> ({target_x}, {target_y})")
                state["gantry"]["targetX"] = target_x
                state["gantry"]["targetY"] = target_y
                
                ports["gantry"].write(f"{target_x},{target_y}\n".encode())
                time.sleep(2) # Simulate travel time
                state["gantry"]["x"] = target_x
                state["gantry"]["y"] = target_y

                # 2. Scoop Down
                log("Lowering scoop...")
                state["scoop"]["position"] = "down"
                ports["scoop"].write(b"1\n")
                time.sleep(1)

                # 3. Stir
                log("Stirring soil sample...")
                state["stirrer"]["active"] = True
                ports["stirrer"].write(b"1\n")
                time.sleep(3)
                state["stirrer"]["active"] = False
                ports["stirrer"].write(b"0\n")

                # 4. Scoop Up
                log("Raising scoop...")
                state["scoop"]["position"] = "up"
                ports["scoop"].write(b"0\n")
                time.sleep(1)

                # 5. Analyze (Simulated Jetson call)
                log("Analyzing sample with Jetson AI...")
                time.sleep(1.5)
                soil_type = "Loam" if (r+c) % 2 == 0 else "Clay"
                state["process"]["soilTypes"][r * cols + c] = soil_type
                log(f"Result for [{r},{c}]: {soil_type}")

        log("Sequence complete.")
    except Exception as e:
        log(f"Sequence Error: {e}")
    finally:
        state["process"]["isRunning"] = False

# --- API ROUTES ---
@app.route('/api/state', methods=['GET'])
def get_state():
    # Update status indicators
    for k in ["gantry", "stirrer", "scoop"]:
        state[k]["status"] = "connected" if ports[k] and ports[k].isOpen else "disconnected"
    return jsonify(state)

@app.route('/api/control/start', methods=['POST'])
def start():
    if not state["process"]["isRunning"]:
        thread = threading.Thread(target=run_sequence)
        thread.daemon = True
        thread.start()
    return jsonify({"status": "ok"})

@app.route('/api/control/stop', methods=['POST'])
def stop():
    state["process"]["isRunning"] = False
    log("Emergency Stop Triggered.")
    return jsonify({"status": "ok"})

@app.route('/api/control/reset', methods=['POST'])
def reset():
    state["process"]["isRunning"] = False
    state["process"]["currentRow"] = 0
    state["process"]["currentCol"] = 0
    state["process"]["soilTypes"] = [None] * (state["config"]["rows"] * state["config"]["cols"])
    state["gantry"]["x"] = 0
    state["gantry"]["y"] = 0
    state["scoop"]["position"] = "up"
    state["stirrer"]["active"] = False
    log("System Reset.")
    return jsonify({"status": "ok"})

@app.route('/api/control/dummy', methods=['POST'])
def toggle_dummy():
    data = request.json
    state["dummyMode"] = bool(data.get("enabled", True))
    init_hardware()
    log(f"Dummy Mode {'ENABLED' if state['dummyMode'] else 'DISABLED'}")
    return jsonify({"status": "ok", "dummyMode": state["dummyMode"]})

@app.route('/api/control/gantry', methods=['POST'])
def manual_gantry():
    data = request.json
    x, y = data.get("x", 0), data.get("y", 0)
    state["gantry"]["targetX"] = x
    state["gantry"]["targetY"] = y
    ports["gantry"].write(f"{x},{y}\n".encode())
    state["gantry"]["x"] = x
    state["gantry"]["y"] = y
    return jsonify({"status": "ok"})

@app.route('/api/control/stirrer', methods=['POST'])
def manual_stirrer():
    active = request.json.get("active", False)
    state["stirrer"]["active"] = active
    ports["stirrer"].write(b"1\n" if active else b"0\n")
    return jsonify({"status": "ok"})

@app.route('/api/control/scoop', methods=['POST'])
def manual_scoop():
    pos = request.json.get("position", "up")
    state["scoop"]["position"] = pos
    ports["scoop"].write(b"1\n" if pos == "down" else b"0\n")
    return jsonify({"status": "ok"})

@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    state["config"]["rows"] = data.get("rows", state["config"]["rows"])
    state["config"]["cols"] = data.get("cols", state["config"]["cols"])
    state["config"]["dist"] = data.get("dist", state["config"]["dist"])
    reset()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    init_hardware()
    print("SoilSense v4.0 Python Logic Engine starting on port 5001...")
    app.run(host='0.0.0.0', port=5001, debug=False)
