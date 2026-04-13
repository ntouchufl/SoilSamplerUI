# SoilSense v6.0: Automated Soil Analysis System

SoilSense v6.0 is an integrated hardware and software platform designed for automated soil sampling and analysis. The system utilizes a multi-axis gantry to navigate a grid of soil samples, performing stirring and scooping operations before capturing images for automated soil type classification.

## 🚀 Overview

The system is powered by a Flet-based user interface designed for deployment on Raspberry Pi or macOS. It features high-level state management, safety interlocks, and flexible hardware integration through serial communication or dummy simulation modes.

### Key Features
- **Precision Gantry Control:** X-Y movement to navigate a grid of soil sample containers.
- **Automated Sampling:** Integrated stirrer and scoop actuator for soil preparation and sampling.
- **Safety Interlock System:** Monitors door states (physical via GPIO or simulated) to halt operations if safety is compromised.
- **Dual Operating Modes:** Supports both "Real" (hardware-connected) and "Dummy" (simulation) modes for all subsystems.
- **Live Feed Integration:** Connects to an NVIDIA Jetson or simulated source for soil classification and image display.

---

## 🛠 Hardware Architecture

The system is powered by three primary Arduino-based controllers and an NVIDIA Jetson:
1. **Gantry Controller:** Manages X-Y stepper motors for precise positioning.
2. **Stirrer Controller:** Operates the soil stirring mechanism.
3. **Scoop Controller:** Controls the sampling actuator. Supports variable weight presets (Small/Medium/Large).
4. **Jetson Interface:** Handles image processing and soil type classification.
5. **Safety Sensors:** GPIO-connected limit switches for door monitoring.

---

## 🚦 Getting Started

### Prerequisites
- Python 3.10+
- `flet`, `pyserial`, and `gpiozero` (for Linux/Pi deployment)

### Running the Desktop UI
1. Navigate to the `Ui/soilsense-v6.0` directory.
2. Install dependencies:
   ```bash
   pip install -r ../../requirements.txt
   ```
3. Update serial numbers in `hardware_logic.py` if necessary.
4. Run the application:
   ```bash
   python main.py
   ```

---

## 📁 File Structure

- **`Ui/soilsense-v6.0/`**:
  - **`main.py`**: The Flet UI entry point.
  - **`hardware_logic.py`**: The core logic engine, managing hardware communication and the analysis sequence.
  - **`limit_switch.py`**: A standalone test script for GPIO-connected sensors.
  - **`images/`**: Directory for locally stored soil images.
- **`requirements.txt`**: Top-level dependencies.

## 📊 Data Output Format (Jetson)

The system communicates with an NVIDIA Jetson for soil analysis. The Jetson returns a JSON object with the following structure:

```json
{
  "timestamp": "20260406_161322",
  "classification": "Organic",
  "dark_pct": 36.96,
  "medium_pct": 37.99,
  "light_pct": 25.05,
  "avg_value": 120.68,
  "avg_r": 147.82,
  "avg_g": 163.25,
  "avg_b": 162.99,
  "dark_thresh": 85,
  "light_thresh": 170,
  "total_pixels": 375000,
  "calibration_applied": true,
  "color_calibration_applied": true,
  "files": {
    "color": "path/to/color.jpg",
    "gray": "path/to/gray.jpg",
    "heatmap": "path/to/heatmap.jpg"
  }
}
```

The UI extracts the `classification` and `avg_value` for real-time display.

## 💾 Data Export (SD Card)
The system includes an **EXPORT DATA** button that:
1.  **Auto-detects USB SD Cards:** Searches `/media/pi` on Linux (Raspberry Pi) or `/Volumes` on macOS.
2.  **Generates Timestamped Reports:** Saves a CSV (e.g., `soil_analysis_20260406_161322.csv`) with full details.
3.  **Comprehensive Trial Data:** Includes grid coordinates, full Jetson classification, color percentages (Dark/Medium/Light), RGB averages, and pixel counts for every sample in the trial.

If no SD card is detected, the file is saved to the application's local directory as a fallback.

## 🥄 Scoop Size Control
The system supports three weight presets for the scoop mechanism. When the sequence runs, the UI sends the selected weight to the scoop controller:
- **Small:** 10g (Command: `DOWN Small\n`)
- **Medium:** 20g (Command: `DOWN Medium\n`)
- **Large:** 30g (Command: `DOWN Large\n`)

## 📊 Testing & Simulation
To test the interface without hardware, enable "Dummy Mode" in the **Manual Debug** tab of the application. This will simulate all hardware responses, including gantry movement, stirring, and soil analysis.

## ⚖️ License
This project is for educational/research purposes.
