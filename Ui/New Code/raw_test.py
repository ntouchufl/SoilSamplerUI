import serial
import time
import serial.tools.list_ports

# 1. FIND THE PORT MANUALLY
print("Scanning ports...")
ports = list(serial.tools.list_ports.comports())
target_port = None

for p in ports:
    print(f"Found: {p.device} - {p.serial_number}")
    # Auto-select the first USB device
    if "usbmodem" in p.device or "usbserial" in p.device:
        target_port = p.device

if not target_port:
    print("\nCRITICAL ERROR: No Arduino found!")
    print("Check your USB cable. Is it power-only?")
    exit()

print(f"\nTargeting: {target_port}")

# 2. OPEN CONNECTION (The "Reset" Moment)
try:
    print("Opening Serial Port...")
    # DTR=True causes the Arduino to reboot. This is normal.
    ser = serial.Serial(target_port, 9600, timeout=1, dsrdtr=True)
    
    print("WAITING 3 SECONDS FOR ARDUINO TO BOOT...")
    # If we don't wait here, the bootloader eats our command.
    time.sleep(3) 
    
    # Clear any garbage startup noise
    ser.reset_input_buffer()
    
    # 3. SEND COMMAND
    print("Sending '1'...")
    ser.write(b"1\n") # Note the \n
    
    # 4. LISTEN FOR REPLY
    print("Listening for 5 seconds...")
    start = time.time()
    while time.time() - start < 5:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            print(f"RECEIVED: '{line}'")
            if "Finished" in line:
                print("SUCCESS! The Arduino is talking.")
                break
        time.sleep(0.1)
        
    ser.close()
    
except Exception as e:
    print(f"CRITICAL PYTHON ERROR: {e}")

print("Test Done.")