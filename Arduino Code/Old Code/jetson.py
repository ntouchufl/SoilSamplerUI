#!/usr/bin/env python3
# Developed in EML 4502 Mechanical Design 3 with the use of UF NaviGator AI, Rights Reserved by Sonic Sampler.
"""
Soil Grader — Jetson Nano
Multi-mode operation:
  1. calibrate       — Greyscale calibration using a test card
  2. colorcalibrate  — RGB colour calibration using the same test card
  3. spin            — Run the stir motor for a set duration
  4. grade           — Turn on light, capture photo, analyse soil, output results

Usage:
  python3 soil_grader.py calibrate
  python3 soil_grader.py colorcalibrate
  python3 soil_grader.py spin
  python3 soil_grader.py grade
"""

import cv2
import numpy as np
import time
import json
import os
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Jetson GPIO — falls back to simulation on a regular PC
# ---------------------------------------------------------------------------
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


# ========================  CONFIGURATION  ==================================

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


# ========================  CAMERA  ==========================================

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
    """Load calibration LUT from disk if it exists."""
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, "r") as f:
            data = json.load(f)
        if "lut" in data:
            data["lut"] = np.array(data["lut"], dtype=np.uint8)
        return data
    return None


def apply_calibration(gray, calibration):
    """Apply the saved lookup table to remap grayscale values."""
    if calibration and "lut" in calibration:
        lut = calibration["lut"]
        if isinstance(lut, list):
            lut = np.array(lut, dtype=np.uint8)
        return cv2.LUT(gray, lut)
    return gray


# ========================  1. CALIBRATE  ====================================

# What each patch on the test card SHOULD read as (ideal grayscale values).
# 7 patches captured one at a time.
#
#   ┌──────────────────────────┐
#   │                          │
#   │     BIG MIDDLE GREY      │   -> ideal 128
#   │                          │
#   ├────┬────┬────┬────┬────┬────┤
#   │ wht│    │    │    │    │ blk│
#   └────┴────┴────┴────┴────┴────┘

IDEAL_PATCH_VALUES = [128, 255, 204, 153, 102, 51, 0]
PATCH_LABELS = ["mid-grey", "white", "light", "med-light", "med-dark", "dark", "black"]

# Size of the sampling box as a fraction of frame dimensions
SAMPLE_BOX_W_FRAC = 0.08
SAMPLE_BOX_H_FRAC = 0.08


def _build_lut(measured, ideal):
    """
    Build a 256-entry lookup table that maps measured camera values
    to corrected values using piecewise linear interpolation.
    """
    pairs = sorted(zip(measured, ideal))
    m_sorted = [p[0] for p in pairs]
    i_sorted = [p[1] for p in pairs]

    # Clamp endpoints so the full 0-255 range is covered
    if m_sorted[0] > 0:
        m_sorted.insert(0, 0)
        i_sorted.insert(0, 0)
    if m_sorted[-1] < 255:
        m_sorted.append(255)
        i_sorted.append(255)

    lut = np.interp(
        np.arange(256, dtype=np.float32),
        np.array(m_sorted, dtype=np.float32),
        np.array(i_sorted, dtype=np.float32),
    )
    return np.clip(lut, 0, 255).astype(np.uint8)


def calibrate():
    """
    Step-by-step greyscale calibration — one patch at a time.

    For each of the 7 patches, a live preview is shown with a green
    sampling box in the centre. Position that patch inside the box,
    then press SPACE to capture it. After all 7 are captured, the
    correction LUT is built and saved.

    Keys (each step):
      SPACE  — capture this patch
      Q      — quit without saving (aborts entire calibration)
    """
    print("=" * 56)
    print("  CALIBRATE — one patch at a time")
    print("=" * 56)
    print()
    print("  For each patch, position it inside the green box")
    print("  on screen and press SPACE to capture.")
    print("  Press Q at any point to quit without saving.")
    print()

    cap = open_camera()
    h_frame = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w_frame = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    # Sampling box coordinates (centred)
    box_w = int(w_frame * SAMPLE_BOX_W_FRAC)
    box_h = int(h_frame * SAMPLE_BOX_H_FRAC)
    bx1 = (w_frame - box_w) // 2
    by1 = (h_frame - box_h) // 2
    bx2 = bx1 + box_w
    by2 = by1 + box_h

    measured = []
    aborted = False

    for step, (label, ideal) in enumerate(zip(PATCH_LABELS, IDEAL_PATCH_VALUES)):
        print(f"\n[Step {step + 1}/7]  Place the  {label.upper()}  patch "
              f"(ideal {ideal}) inside the box...")

        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Sample the box region
            roi = gray[by1:by2, bx1:bx2]
            roi_mean = float(np.mean(roi))

            # Draw the sampling box and info
            display = frame.copy()
            cv2.rectangle(display, (bx1, by1), (bx2, by2), (0, 255, 0), 2)

            # Patch label and step counter
            cv2.putText(display,
                        f"Step {step + 1}/7:  {label}  (ideal: {ideal})",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Live reading inside the box
            cv2.putText(display,
                        f"Reading: {roi_mean:.1f}",
                        (bx1 + 5, by1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # Show patches captured so far
            y_info = 65
            for prev_i, (prev_label, prev_val) in enumerate(
                    zip(PATCH_LABELS[:len(measured)], measured)):
                diff = prev_val - IDEAL_PATCH_VALUES[prev_i]
                color = (0, 200, 0) if abs(diff) < 20 else (0, 100, 255)
                cv2.putText(display,
                            f"  {prev_label}: {prev_val:.0f} (diff {diff:+.0f})",
                            (10, y_info),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
                y_info += 20

            cv2.imshow("Calibration — SPACE to capture patch, Q to quit",
                       display)
            key = cv2.waitKey(30) & 0xFF

            if key == ord("q") or key == ord("Q"):
                print("[INFO] Calibration aborted.")
                aborted = True
                break

            elif key == ord(" "):
                measured.append(roi_mean)
                print(f"  Captured {label}: {roi_mean:.1f}  "
                      f"(ideal {ideal}, diff {roi_mean - ideal:+.1f})")
                break

        if aborted:
            break

    cap.release()
    cv2.destroyAllWindows()

    if aborted or len(measured) != 7:
        print("[INFO] Calibration not saved.")
        return

    # Build LUT and save
    lut = _build_lut(measured, IDEAL_PATCH_VALUES)

    cal_data = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "measured": measured,
        "ideal": IDEAL_PATCH_VALUES,
        "lut": lut.tolist(),
    }
    os.makedirs(os.path.dirname(CALIBRATION_FILE), exist_ok=True)
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(cal_data, f, indent=2)
    print(f"\n[SAVED] Calibration -> {CALIBRATION_FILE}")

    print()
    print("  All 7 patches captured:")
    for label, meas, ideal in zip(PATCH_LABELS, measured, IDEAL_PATCH_VALUES):
        print(f"    {label:10s}  camera={meas:5.1f}  ideal={ideal:3d}  "
              f"diff={meas - ideal:+5.1f}")
    print()
    print("  Correction LUT saved. The 'grade' command will")
    print("  automatically apply it to future captures.")


def load_color_calibration():
    """Load color adjustment settings from disk if they exist."""
    if os.path.exists(COLOR_CALIBRATION_FILE):
        with open(COLOR_CALIBRATION_FILE, "r") as f:
            return json.load(f)
    return None


def apply_color_calibration(frame, color_cal):
    """Apply saved color adjustments (R/G/B offsets + saturation) to a frame."""
    if color_cal is None:
        return frame
    corrected = frame.copy()

    # Apply per-channel offsets (BGR order in OpenCV)
    r_off = color_cal.get("r_offset", 0)
    g_off = color_cal.get("g_offset", 0)
    b_off = color_cal.get("b_offset", 0)

    if r_off != 0 or g_off != 0 or b_off != 0:
        corrected = corrected.astype(np.int16)
        corrected[:, :, 2] += r_off   # R
        corrected[:, :, 1] += g_off   # G
        corrected[:, :, 0] += b_off   # B
        corrected = np.clip(corrected, 0, 255).astype(np.uint8)

    # Apply saturation adjustment
    sat_scale = color_cal.get("saturation", 1.0)
    if sat_scale != 1.0:
        hsv = cv2.cvtColor(corrected, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] *= sat_scale
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        corrected = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    return corrected


# ========================  1b. COLOR CALIBRATE  ==============================

def _apply_adjustments(frame, r_off, g_off, b_off, sat_scale):
    """Apply R/G/B offsets and saturation scale to a frame for live preview."""
    adjusted = frame.copy()

    if r_off != 0 or g_off != 0 or b_off != 0:
        adjusted = adjusted.astype(np.int16)
        adjusted[:, :, 2] += r_off
        adjusted[:, :, 1] += g_off
        adjusted[:, :, 0] += b_off
        adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)

    if sat_scale != 1.0:
        hsv = cv2.cvtColor(adjusted, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] *= sat_scale
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        adjusted = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    return adjusted


def colorcalibrate():
    """
    Two-phase colour calibration:

    Phase 1 — Live preview. Press SPACE to capture a photo.
    Phase 2 — Adjust the captured photo. Use keyboard to tweak
              R, G, B offsets and saturation until it looks right.
              Press SPACE to save, Q to quit.

    Keys (Phase 2):
      R / r  — Red channel   +5 / -5
      G / g  — Green channel +5 / -5
      B / b  — Blue channel  +5 / -5
      S / s  — Saturation    +0.05 / -0.05
      0      — Reset all adjustments
      SPACE  — Save and exit
      Q      — Quit without saving
    """
    print("=" * 56)
    print("  COLOR CALIBRATE")
    print("=" * 56)
    print()
    print("  Phase 1: Live preview — press SPACE to take a photo.")
    print("  Phase 2: Adjust colours until it looks right.")
    print()

    # ---- Phase 1: Live preview and capture ----
    cap = open_camera()
    print("[INFO] Live preview — press SPACE to capture, Q to quit...")

    captured = None
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        cv2.imshow("Color Calibration — SPACE to capture", frame)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q") or key == ord("Q"):
            print("[INFO] Quit.")
            cap.release()
            cv2.destroyAllWindows()
            return

        elif key == ord(" "):
            captured = frame.copy()
            print("[INFO] Photo captured. Entering adjustment mode...")
            break

    cap.release()
    cv2.destroyAllWindows()

    # ---- Phase 2: Adjust the captured photo ----
    r_off = 0
    g_off = 0
    b_off = 0
    sat_scale = 1.0

    R_STEP = 5
    G_STEP = 5
    B_STEP = 5
    SAT_STEP = 0.05

    print()
    print("  Adjustment keys:")
    print("    R / r  Red   +/- 5")
    print("    G / g  Green +/- 5")
    print("    B / b  Blue  +/- 5")
    print("    S / s  Saturation +/- 0.05")
    print("    0      Reset all")
    print("    SPACE  Save & exit")
    print("    Q      Quit without saving")
    print()

    while True:
        adjusted = _apply_adjustments(captured, r_off, g_off, b_off, sat_scale)

        # Draw current settings as small text in the corner
        display = adjusted.copy()
        info_lines = [
            f"R: {r_off:+d}",
            f"G: {g_off:+d}",
            f"B: {b_off:+d}",
            f"Sat: {sat_scale:.2f}",
        ]
        y = 25
        for line in info_lines:
            cv2.putText(display, line, (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(display, line, (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            y += 25

        cv2.imshow("Adjust — SPACE to save, Q to quit", display)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q") or key == ord("Q"):
            print("[INFO] Quit without saving.")
            break

        elif key == ord("0"):
            r_off, g_off, b_off, sat_scale = 0, 0, 0, 1.0
            print("[INFO] Reset to defaults.")

        elif key == ord(" "):
            cal_data = {
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "r_offset": r_off,
                "g_offset": g_off,
                "b_offset": b_off,
                "saturation": round(sat_scale, 4),
            }
            os.makedirs(os.path.dirname(COLOR_CALIBRATION_FILE), exist_ok=True)
            with open(COLOR_CALIBRATION_FILE, "w") as f:
                json.dump(cal_data, f, indent=2)
            print(f"[SAVED] Color calibration -> {COLOR_CALIBRATION_FILE}")

            # Save the adjusted reference image
            snap_path = os.path.join(
                os.path.dirname(COLOR_CALIBRATION_FILE),
                "color_calibration_reference.jpg"
            )
            cv2.imwrite(snap_path, adjusted)
            print(f"[SAVED] Reference image -> {snap_path}")

            print()
            print(f"  R offset:    {r_off:+d}")
            print(f"  G offset:    {g_off:+d}")
            print(f"  B offset:    {b_off:+d}")
            print(f"  Saturation:  {sat_scale:.2f}")
            print()
            print("  The 'grade' command will automatically apply")
            print("  these adjustments to future captures.")
            break

        else:
            keymap = {
                ord("R"): ("r", +1),
                ord("r"): ("r", -1),
                ord("G"): ("g", +1),
                ord("g"): ("g", -1),
                ord("B"): ("b", +1),
                ord("b"): ("b", -1),
                ord("S"): ("s", +1),
                ord("s"): ("s", -1),
            }
            if key in keymap:
                channel, direction = keymap[key]
                if channel == "r":
                    r_off += direction * R_STEP
                elif channel == "g":
                    g_off += direction * G_STEP
                elif channel == "b":
                    b_off += direction * B_STEP
                elif channel == "s":
                    sat_scale = max(0.0, sat_scale + direction * SAT_STEP)

    cv2.destroyAllWindows()


# ========================  2. SPIN  =========================================

def spin():
    """Run the stir motor for MOTOR_STIR_SECONDS, then stop."""
    print("=" * 56)
    print("  SPIN — stirring motor")
    print("=" * 56)

    gpio_init()

    print(f"[MOTOR] ON for {MOTOR_STIR_SECONDS} seconds...")
    relay_on(MOTOR_RELAY_PIN)
    time.sleep(MOTOR_STIR_SECONDS)

    relay_off(MOTOR_RELAY_PIN)
    print("[MOTOR] OFF.")

    GPIO.cleanup()
    print("Done.")


# ========================  3. GRADE  ========================================

def grade():
    """Turn on light, capture photo, analyse soil, save and print results."""
    print("=" * 56)
    print("  GRADE — analysing soil")
    print("=" * 56)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    gpio_init()

    # Light on
    print(f"[LIGHT] ON — warming up {LIGHT_WARMUP_SECONDS}s...")
    relay_on(LIGHT_RELAY_PIN)
    time.sleep(LIGHT_WARMUP_SECONDS)

    # Capture
    print("[CAMERA] Capturing...")
    cap = open_camera()
    frame = capture_frame(cap)
    cap.release()

    # Light off
    relay_off(LIGHT_RELAY_PIN)
    print("[LIGHT] OFF.")

    GPIO.cleanup()

    # ---- Crop to inner 900x650 to avoid edge distortion ----
    h, w = frame.shape[:2]
    crop_w, crop_h = 750, 500
    cx, cy = w // 2, h // 2
    x1 = max(cx - crop_w // 2, 0)
    y1 = max(cy - crop_h // 2, 0)
    x2 = x1 + crop_w
    y2 = y1 + crop_h
    frame = frame[y1:y2, x1:x2]
    print(f"[INFO] Cropped to {frame.shape[1]}x{frame.shape[0]} centre region.")

    # ---- Analyse ----
    print("[ANALYSIS] Grading soil...")

    # Apply color calibration to the colour image first
    color_cal = load_color_calibration()
    if color_cal:
        frame = apply_color_calibration(frame, color_cal)
        print("[INFO] Color calibration applied.")

    # Compute RGB averages from the (corrected) colour image
    # OpenCV stores as BGR
    avg_b = round(float(np.mean(frame[:, :, 0])), 2)
    avg_g = round(float(np.mean(frame[:, :, 1])), 2)
    avg_r = round(float(np.mean(frame[:, :, 2])), 2)

    # Greyscale analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Apply greyscale calibration correction if available
    calibration = load_calibration()
    gray = apply_calibration(gray, calibration)
    if calibration:
        print("[INFO] Greyscale calibration LUT applied.")

    total = gray.size
    dark_count = int(np.sum(gray <= DARK_THRESH))
    light_count = int(np.sum(gray >= LIGHT_THRESH))
    medium_count = total - dark_count - light_count

    dark_pct  = round(100.0 * dark_count / total, 2)
    medium_pct = round(100.0 * medium_count / total, 2)
    light_pct = round(100.0 * light_count / total, 2)
    avg_value = round(float(np.mean(gray)), 2)

    # ---- Soil classification ----
    classification = "Organic" if dark_pct > 14 else "Mineral"

    # ---- Heatmap ----
    heatmap = np.zeros((*gray.shape, 3), dtype=np.uint8)
    heatmap[gray <= DARK_THRESH] = (255, 80, 40)
    heatmap[(gray > DARK_THRESH) & (gray < LIGHT_THRESH)] = (40, 200, 80)
    heatmap[gray >= LIGHT_THRESH] = (50, 80, 255)

    # ---- Save files (classification in filename) ----
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

    # ---- Print results ----
    print()
    print("=" * 56)
    print("  RESULTS")
    print("=" * 56)
    print(f"  Dark   (0-{DARK_THRESH}):       {dark_pct:6.2f} %")
    print(f"  Medium ({DARK_THRESH+1}-{LIGHT_THRESH-1}):   {medium_pct:6.2f} %")
    print(f"  Light  ({LIGHT_THRESH}-255):   {light_pct:6.2f} %")
    print(f"  Average value:        {avg_value:6.2f} / 255")
    print(f"  Average RGB:          R={avg_r:.1f}  G={avg_g:.1f}  B={avg_b:.1f}")
    print()
    print(f"  Soil Classification:  {classification}")
    print("-" * 56)
    print(f"  Colour image : {color_path}")
    print(f"  Grayscale    : {gray_path}")
    print(f"  Heatmap      : {heatmap_path}")
    print(f"  JSON         : {json_path}")
    print("=" * 56)

    return results


# ========================  CLI ENTRY POINT  =================================

COMMANDS = {
    "calibrate": calibrate,
    "colorcalibrate": colorcalibrate,
    "spin": spin,
    "grade": grade,
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Soil Grader — usage:")
        print()
        print("  python3 soil_grader.py calibrate        Greyscale calibration with test card")
        print("  python3 soil_grader.py colorcalibrate   RGB colour calibration with test card")
        print("  python3 soil_grader.py spin             Run the stir motor")
        print("  python3 soil_grader.py grade            Light -> photo -> analyse -> results")
        print()
        sys.exit(1)

    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        GPIO.cleanup()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        GPIO.cleanup()
        sys.exit(1)