SOILSENSE AUTOMATED SOIL ANALYZER

SoilSense is a PyQt6-based automated hardware interface for soil sample processing and classification. It controls a multi-axis gantry, stirrer, and scooping mechanism via serial communication while interfacing with a Jetson device for visual AI classification.

FEATURES

PyQt6 Dashboard: Modern, dark-themed UI with real-time hardware status indicators, progress tracking, and log output.

Automated Sequencing: Runs fully automated routines from moving the gantry to the bag, stirring, triggering the Jetson analysis, scooping the target weight, and dispensing to tubes.

Live Camera Feed: Integrates an MJPEG video stream from the Jetson (or a local webcam mock) directly into the UI.

Manual Override & Debug: Dedicated tab to toggle hardware between "Real" and "Dummy" modes, test individual serial commands, and manually jog equipment.

Safety Interlocks: Background thread monitors hardware doors (via GPIO or Dummy mode). Halts all sequences automatically if a door is open for more than 1 second.

Data Export: Automatically saves classification results and sample timestamps to a CSV file.

SYSTEM ARCHITECTURE
The software communicates with several distinct hardware modules:

Gantry (Serial): Controls X/Y movement.

Stirrer (Serial): Agitates the soil sample.

Scoop (Serial): Collects and dispenses specific weights of soil using a load cell.

Jetson (TCP Socket): Receives the "A" (Analyze) command and returns JSON data containing the soil classification and average value.

Doors (GPIO): Hardware safety switches (defaults to Dummy mode on macOS).

PREREQUISITES
Ensure you have Python 3 installed. Install the required dependencies:
pip install PyQt6 pyserial opencv-python flask gpiozero
(Note: gpiozero is only required if running on a Raspberry Pi with real hardware doors).

RUNNING THE APPLICATION

Start the Camera Stream (Optional/Testing)
If you are testing without the physical Jetson, you can use your computer's webcam to mock the Jetson MJPEG stream. Run this command:
python mac_video_url.py
This will host a video feed on http://0.0.0.0:5005/video_feed.

Launch the Main GUI
Run this command:
python main.py
The application will automatically scan the USB bus for the Gantry, Stirrer, and Scoop Arduinos based on their hardcoded serial numbers. If they are disconnected, you can safely run the sequence using the built-in "Dummy Mode".

HARDWARE COMMUNICATION PROTOCOL
The system utilizes asynchronous serial commands. The sequencer waits for a "Y" (Yes/Success) confirmation from the hardware before advancing to the next step. All serial TX/RX traffic is logged to the console for debugging.

Gantry Commands:

BXY: Move to Bag X,Y

TXY: Move to Tube X,Y

Z: Zero Gantry

S: Stop

Scoop Commands:

S: Scoop

D<weight>: Dispense specific weight (e.g., D10)

E: Empty

Q: Quit

Standard Responses:

Yxxxx: Success (with elapsed time in milliseconds)

F<code: Failure (e.g., F0 for Unknown Command, F2 for Limit Hit)