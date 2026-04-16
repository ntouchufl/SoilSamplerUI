#!/usr/bin/env python3
"""
SoilSense Jetson Nano Dual-Server
Port 5000: Live MJPEG Video Stream
Port 5005: TCP Command Server (Analysis/Spin)
"""

import cv2
import numpy as np
import time
import json
import os
import threading
import socket
from datetime import datetime
from flask import Flask, Response

# ========================  CONFIG  ==================================
HOST = '0.0.0.0'
TCP_PORT = 5005
HTTP_PORT = 5000

# GPIO pins
MOTOR_RELAY_PIN = 11
LIGHT_RELAY_PIN = 13

# Timing
MOTOR_STIR_SECONDS = 5
LIGHT_WARMUP_SECONDS = 1

# Camera
CAMERA_INDEX = 0
CAPTURE_WIDTH = 1280
CAPTURE_HEIGHT = 720
DARK_THRESH = 40
LIGHT_THRESH = 170
OUTPUT_DIR = os.path.expanduser("~/soil_grader/results")

# Global Video Feed Variables
latest_frame = None
camera_lock = threading.Lock()

app = Flask(__name__)

# ========================  JETSON GPIO  ====================================
try:
    import Jetson.GPIO as GPIO
    ON_JETSON = True
except ImportError:
    print("[WARN] Jetson.GPIO not found — running in SIMULATION mode.")
    ON_JETSON = False

    class _MockGPIO:
        BOARD = "BOARD"
        OUT = "OUT"
        HIGH = True
        LOW = False
        def setmode(self, m): pass
        def setup(self, pin, mode, initial=None): pass
        def output(self, pin, val): print(f"  [SIM] GPIO {pin} -> {'HIGH' if val else 'LOW'}")
        def cleanup(self): pass
        def setwarnings(self, v): pass
    GPIO = _MockGPIO()

def gpio_init():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(MOTOR_RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LIGHT_RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)

def relay_on(pin):
    GPIO.output(pin, GPIO.HIGH)

def relay_off(pin):
    GPIO.output(pin, GPIO.LOW)

# ========================  CAMERA THREAD  ===================================
def camera_reader_thread():
    """Continuously reads from the camera to provide a live feed."""
    global latest_frame
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(CAMERA_INDEX)
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)

    print("[INFO] Camera warmed up and streaming...")
    while True:
        ret, frame = cap.read()
        if ret:
            with camera_lock:
                latest_frame = frame.copy()
        else:
            time.sleep(0.1)

# ========================  FLASK HTTP STREAMING  ============================
def generate_mjpeg():
    """Yields JPEG frames for the Flask web stream."""
    global latest_frame
    while True:
        with camera_lock:
            frame = latest_frame
            
        if frame is None:
            time.sleep(0.1)
            continue
            
        # Compress to JPEG for the stream
        ret, jpeg = cv2.imencode('.jpg', frame)
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
        time.sleep(0.05) # Cap stream at ~20fps to save CPU

@app.route('/video_feed')
def video_feed():
    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ========================  ACTION FUNCTIONS  ================================
def spin():
    print("[ACTION] Spinning stir motor...")
    gpio_init()
    relay_on(MOTOR_RELAY_PIN)
    time.sleep(MOTOR_STIR_SECONDS)
    relay_off(MOTOR_RELAY_PIN)
    print("[ACTION] Spin complete.")

def grade():
    global latest_frame
    print("[ACTION] Grading soil...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    gpio_init()

    # Turn on Light for analysis
    relay_on(LIGHT_RELAY_PIN)
    time.sleep(LIGHT_WARMUP_SECONDS)

    # Grab the current frame from the live stream
    with camera_lock:
        if latest_frame is None:
            relay_off(LIGHT_RELAY_PIN)
            raise RuntimeError("Camera frame not available.")
        frame = latest_frame.copy()

    # Light off
    relay_off(LIGHT_RELAY_PIN)

    # Crop to inner 900x650
    h, w = frame.shape[:2]
    crop_w, crop_h = 750, 500
    cx, cy = w // 2, h // 2
    x1, y1 = max(cx - crop_w // 2, 0), max(cy - crop_h // 2, 0)
    frame = frame[y1:y1 + crop_h, x1:x1 + crop_w]

    avg_b = round(float(np.mean(frame[:, :, 0])), 2)
    avg_g = round(float(np.mean(frame[:, :, 1])), 2)
    avg_r = round(float(np.mean(frame[:, :, 2])), 2)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    total = gray.size
    dark_count = int(np.sum(gray <= DARK_THRESH))
    light_count = int(np.sum(gray >= LIGHT_THRESH))
    medium_count = total - dark_count - light_count

    dark_pct  = round(100.0 * dark_count / total, 2)
    medium_pct = round(100.0 * medium_count / total, 2)
    light_pct = round(100.0 * light_count / total, 2)
    avg_value = round(float(np.mean(gray)), 2)

    classification = "Organic" if dark_pct > 14 else "Mineral"

    tag = classification.lower()
    color_path   = os.path.join(OUTPUT_DIR, f"{timestamp}_{tag}_color.jpg")
    cv2.imwrite(color_path, frame)

    results = {
        "timestamp": timestamp,
        "classification": classification,
        "avg_value": avg_value,
        "dark_pct": dark_pct,
        "light_pct": light_pct
    }

    print(f"[ACTION] Grading complete: {classification}")
    return results

# ========================  TCP SERVER  ======================================
def tcp_server_thread():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, TCP_PORT))
        s.listen()
        print(f"[TCP] Command Server Online on port {TCP_PORT}")

        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024).decode().strip()
                if not data: continue
                    
                if data.startswith("A"):
                    print(f"\n[TCP] ANALYSIS request from {addr[0]}")
                    try:
                        results = grade()
                        conn.sendall(json.dumps(results).encode())
                        print("[TCP] -> Results sent.")
                    except Exception as e:
                        print(f"[TCP] -> [ERROR] {e}")
                        conn.sendall(json.dumps({"classification": "Error"}).encode())
                        
                elif data.startswith("SPIN"):
                    print(f"\n[TCP] SPIN request from {addr[0]}")
                    try:
                        spin()
                        conn.sendall(b"DONE")
                    except Exception as e:
                        conn.sendall(b"ERROR")

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Start the camera hardware reader
    threading.Thread(target=camera_reader_thread, daemon=True).start()
    
    # 2. Start the TCP Command server on 5005
    threading.Thread(target=tcp_server_thread, daemon=True).start()
    
    # 3. Start the Flask Live Stream server on 5000
    print(f"[HTTP] Live Video Stream Online at http://{HOST}:{HTTP_PORT}/video_feed")
    app.run(host=HOST, port=HTTP_PORT, debug=False, use_reloader=False)