#!/usr/bin/env python3
"""
SoilSense Jetson Nano TCP Server
Listens for commands from the Raspberry Pi and executes CV/Hardware logic.
"""

import cv2
import numpy as np
import time
import json
import os
import sys
import socket
from datetime import datetime

# ========================  SERVER CONFIG  ==================================
HOST = '0.0.0.0'  # Listens on all available IPs (including 10.42.0.75)
PORT = 5005

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

# ========================  HARDWARE CONFIG  ================================
# GPIO pins (BOARD numbering)
MOTOR_RELAY_PIN = 11
LIGHT_RELAY_PIN = 13

# Timing
MOTOR_STIR_SECONDS = 5
LIGHT_WARMUP_SECONDS = 1

# Camera
CAMERA_INDEX = 0
CAPTURE_WIDTH = 1280
CAPTURE_HEIGHT = 720

# Soil value thresholds (grayscale 0–255)
DARK_THRESH = 40
LIGHT_THRESH = 170

# Paths
OUTPUT_DIR = os.path.expanduser("~/soil_grader/results")
CALIBRATION_FILE = os.path.expanduser("~/soil_grader/calibration.json")
COLOR_CALIBRATION_FILE = os.path.expanduser("~/soil_grader/color_calibration.json")


# ========================  HARDWARE HELPERS  ================================
def gpio_init():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(MOTOR_RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LIGHT_RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)

def relay_on(pin):
    GPIO.output(pin, GPIO.HIGH)

def relay_off(pin):
    GPIO.output(pin, GPIO.LOW)

# ========================  CAMERA & CALIBRATION HELPERS  ====================
def open_camera():
    """Open USB camera and configure resolution."""
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open camera index {CAMERA_INDEX}. "
            "Check USB connection and run: ls /dev/video*"
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
    return cap

def capture_frame(cap, warmup_frames=10):
    for _ in range(warmup_frames):
        cap.read()
    ret, frame = cap.read()
    if not ret or frame is None:
        raise RuntimeError("Camera read failed.")
    return frame

def load_calibration():
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, "r") as f:
            data = json.load(f)
        if "lut" in data:
            data["lut"] = np.array(data["lut"], dtype=np.uint8)
        return data
    return None

def apply_calibration(gray, calibration):
    if calibration and "lut" in calibration:
        lut = calibration["lut"]
        if isinstance(lut, list):
            lut = np.array(lut, dtype=np.uint8)
        return cv2.LUT(gray, lut)
    return gray

def load_color_calibration():
    if os.path.exists(COLOR_CALIBRATION_FILE):
        with open(COLOR_CALIBRATION_FILE, "r") as f:
            return json.load(f)
    return None

def apply_color_calibration(frame, color_cal):
    if color_cal is None:
        return frame
    corrected = frame.copy()
    r_off = color_cal.get("r_offset", 0)
    g_off = color_cal.get("g_offset", 0)
    b_off = color_cal.get("b_offset", 0)

    if r_off != 0 or g_off != 0 or b_off != 0:
        corrected = corrected.astype(np.int16)
        corrected[:, :, 2] += r_off   # R
        corrected[:, :, 1] += g_off   # G
        corrected[:, :, 0] += b_off   # B
        corrected = np.clip(corrected, 0, 255).astype(np.uint8)

    sat_scale = color_cal.get("saturation", 1.0)
    if sat_scale != 1.0:
        hsv = cv2.cvtColor(corrected, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] *= sat_scale
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        corrected = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return corrected

# ========================  ACTION FUNCTIONS  ================================

def spin():
    """Run the stir motor for MOTOR_STIR_SECONDS, then stop."""
    print("[ACTION] Spinning stir motor...")
    gpio_init()
    relay_on(MOTOR_RELAY_PIN)
    time.sleep(MOTOR_STIR_SECONDS)
    relay_off(MOTOR_RELAY_PIN)
    GPIO.cleanup()
    print("[ACTION] Spin complete.")

def grade():
    """Turn on light, capture photo, analyse soil, save and return results dict."""
    print("[ACTION] Grading soil...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    gpio_init()

    # Light on
    relay_on(LIGHT_RELAY_PIN)
    time.sleep(LIGHT_WARMUP_SECONDS)

    # Capture
    cap = open_camera()
    frame = capture_frame(cap)
    cap.release()

    # Light off
    relay_off(LIGHT_RELAY_PIN)
    GPIO.cleanup()

    # Crop to inner 900x650 to avoid edge distortion
    h, w = frame.shape[:2]
    crop_w, crop_h = 750, 500
    cx, cy = w // 2, h // 2
    x1 = max(cx - crop_w // 2, 0)
    y1 = max(cy - crop_h // 2, 0)
    x2 = x1 + crop_w
    y2 = y1 + crop_h
    frame = frame[y1:y2, x1:x2]

    # Analyse
    color_cal = load_color_calibration()
    if color_cal:
        frame = apply_color_calibration(frame, color_cal)

    avg_b = round(float(np.mean(frame[:, :, 0])), 2)
    avg_g = round(float(np.mean(frame[:, :, 1])), 2)
    avg_r = round(float(np.mean(frame[:, :, 2])), 2)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    calibration = load_calibration()
    gray = apply_calibration(gray, calibration)

    total = gray.size
    dark_count = int(np.sum(gray <= DARK_THRESH))
    light_count = int(np.sum(gray >= LIGHT_THRESH))
    medium_count = total - dark_count - light_count

    dark_pct  = round(100.0 * dark_count / total, 2)
    medium_pct = round(100.0 * medium_count / total, 2)
    light_pct = round(100.0 * light_count / total, 2)
    avg_value = round(float(np.mean(gray)), 2)

    classification = "Organic" if dark_pct > 14 else "Mineral"

    # Heatmap
    heatmap = np.zeros((*gray.shape, 3), dtype=np.uint8)
    heatmap[gray <= DARK_THRESH] = (255, 80, 40)
    heatmap[(gray > DARK_THRESH) & (gray < LIGHT_THRESH)] = (40, 200, 80)
    heatmap[gray >= LIGHT_THRESH] = (50, 80, 255)

    # Save files
    tag = classification.lower()
    color_path   = os.path.join(OUTPUT_DIR, f"{timestamp}_{tag}_color.jpg")
    gray_path    = os.path.join(OUTPUT_DIR, f"{timestamp}_{tag}_gray.jpg")
    heatmap_path = os.path.join(OUTPUT_DIR, f"{timestamp}_{tag}_heatmap.jpg")
    json_path    = os.path.join(OUTPUT_DIR, f"{timestamp}_{tag}_results.json")

    cv2.imwrite(color_path, frame)
    cv2.imwrite(gray_path, gray)
    cv2.imwrite(heatmap_path, heatmap)

    results = {
        "timestamp": timestamp,
        "classification": classification,
        "dark_pct": dark_pct,
        "medium_pct": medium_pct,
        "light_pct": light_pct,
        "avg_value": avg_value,
        "avg_r": avg_r,
        "avg_g": avg_g,
        "avg_b": avg_b,
        "dark_thresh": DARK_THRESH,
        "light_thresh": LIGHT_THRESH,
        "total_pixels": total,
        "calibration_applied": calibration is not None,
        "color_calibration_applied": color_cal is not None,
        "files": {
            "color": color_path,
            "gray": gray_path,
            "heatmap": heatmap_path,
        },
    }
    
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"[ACTION] Grading complete: {classification}")
    return results

# ========================  TCP SERVER  ======================================

def start_server():
    # Ensure output directory exists before accepting connections
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Allow the port to be reused immediately after restart
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        
        print("=" * 56)
        print(f"  Jetson Soil Analysis Server Online")
        print(f"  Listening on {HOST}:{PORT}")
        print("=" * 56)
        print("Waiting for Raspberry Pi...")

        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024).decode().strip()
                if not data:
                    continue
                    
                # v7.0 Hardware Logic sends "A" for Analyze
                if data.startswith("A"):
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Received ANALYSIS request from {addr[0]}")
                    try:
                        results = grade()
                        # Send JSON back to the Pi
                        response = json.dumps(results)
                        conn.sendall(response.encode())
                        print("-> Results transmitted to Pi.")
                    except Exception as e:
                        print(f"-> [ERROR] Failed during grading: {e}")
                        error_res = json.dumps({"classification": "Error", "error": str(e)})
                        conn.sendall(error_res.encode())
                        
                elif data.startswith("SPIN"):
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Received SPIN request from {addr[0]}")
                    try:
                        spin()
                        conn.sendall(b"DONE")
                    except Exception as e:
                        print(f"-> [ERROR] Failed during spin: {e}")
                        conn.sendall(b"ERROR")

if __name__ == "__main__":
    try:
        start_server()
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
        GPIO.cleanup()