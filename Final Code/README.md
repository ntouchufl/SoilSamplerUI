My summary:
This code features a UI that is made of 2 files: main.py and hardware_logic.py.

Main:
This file is what you run. It includes all of the UI elements and how they are laid out on the display. No logic is done in this file.

Hardware Logic:
This file is where all the function calls and logic are. This file has the code that connects the Raspberry Pi to the Arduinos and the Jetson as well as all the code that figures out what order things should happen in. The main UI file just calls these functions when certain buttons are pressed.

Commands.txt:
This text file lists all the commands that are being sent and what functions they call. Due to some last minute code changes, it might not all line up perfectly. Just make sure that you look through all the Arduino code for what commands it's expecting and match hardware_logic.py to send the right ones. In this zip file, I don't think I have the NEWEST Arduino code from all the other subsystems. I'm including the most recent code I have just so I include something.

How this code works is it sends messages to the hardware then waits to hear back from them. It then does the next logical step based on the response it gets. For the Arduinos, it communicates over serial. All it does is type commands the same way you would in the serial monitor in the Arduino application. Note you cannot use the serial monitor while Python is actively using it. It listens from the Arduino based on what it prints to the serial monitor. For the Jetson, it communicates over Ethernet using a static IP address. I had to do some research to figure out how this actually works; it's hard to explain.

The "dummy" mode allows you to run the soil sensor without actually being connected to some/all of the hardware. It emulates either the Jetson or the Arduinos and sends a "pretend" response back. In the real system, you may send "H" to an Arduino and expect a "Y" back when it's done. Dummy mode just sends that response back in the same way the physical hardware would to allow for easy testing. Just remember to turn it off once you want to test the real hardware.

This code was developed for macOS and Linux since that is what I use. I think it runs on Windows, but it may be missing some functionality. It shouldn't be hard to add. What I mean by this is that it checks if the user's OS is macOS, which Python refers to as "Darwin" for some reason, and if that's not true it assumes it's Linux. Windows is also not macOS, so you would have to change those flags.

If you have any questions on how this software works, feel free to reach out to me. Good luck with the project.

Noah Touchton - ntouchton@ufl.edu




More Detailed AI summary:
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