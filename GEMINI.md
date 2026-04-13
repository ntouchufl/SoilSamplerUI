# SoilSense v6.0 Project Context (GEMINI.md)

This document provides essential context for AI agents working on **SoilSense v6.0**.

## 🎯 Project Goals
Automate soil analysis using a mechanical gantry and integrated sampling tools. The v6.0 system focuses on a unified Flet interface, robust safety interlocks, and flexible hardware simulation for cross-platform development.

## 🏗 System Architecture
- **Hardware Interface:** Controlled via `pyserial` using serial numbers for dynamic port discovery.
- **Safety Interlocks:** GPIO-connected limit switches monitor door status. Operations are halted if doors are open for >1 second.
- **Backend:** `SoilSenseLogic` handles state, hardware communication, and the analysis sequence.
- **Frontend:** A responsive Flet application with "Dashboard" and "Manual Debug" views.

## 📂 Key File Locations
- **`Ui/soilsense-v6.0/main.py`**: Entry point for the Flet UI. Handles layout, user input, and UI updates via PubSub.
- **`Ui/soilsense-v6.0/hardware_logic.py`**: Core engine managing state, hardware communication, and simulation logic.
- **`requirements.txt`**: Minimal dependency list (Flet, PySerial).
- **`Ui/soilsense-v6.0/images/`**: Source folder for soil images used in the Jetson analysis simulation.

## 🧪 Hardware Protocols
- **Serial Ports:** Baud rates are 115200 (Gantry) and 9600 (Stirrer/Scoop).
- **Control Commands:**
  - **Gantry:** `MOVE x,y\n`, `STOP\n`
  - **Stirrer:** `START\n`, `STOP\n`
  - **Scoop:** `DOWN\n`, `UP\n`, `STOP\n`
- **Acknowledgment:** Hardware is expected to respond with `Finished\n` upon completion of most tasks.

## 🛠 Working Guidelines
1. **Safety Interlocks:** Never disable or bypass the door safety logic in `_door_monitor`.
2. **Serial IDs:** Hardware must be identified via `serial_number`. Avoid hardcoding port paths like `COM3` or `/dev/ttyUSB0`.
3. **Cross-Platform Compatibility:** The code handles macOS (Darwin) by forcing "Dummy Mode" for GPIO and scaling the UI.
4. **Threading:** Hardware I/O and sequence execution MUST occur in background threads to maintain UI responsiveness.
5. **Simulation:** Use `MockSerial` and `MockDoor` for development and testing without physical hardware.

## 🚀 How to Help
- **Sequence Refinement:** Optimize the `run_sequence` method for better performance or error handling.
- **Jetson Integration:** Replace the dummy Jetson communication with real computer vision API calls.
- **UI Enhancements:** Improve the "Dashboard" visualization or add data export features.
