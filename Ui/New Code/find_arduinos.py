import serial.tools.list_ports
import sys

def list_serial_devices():
    """
    Lists all connected serial devices with detailed information.
    Works on Windows (COMx), macOS (/dev/cu.*), and Linux (/dev/tty*).
    """
    # Get a list of all available ports
    ports = serial.tools.list_ports.comports()
    
    print(f"\n{'='*60}")
    print(f"SCANNING FOR CONNECTED DEVICES ({sys.platform})")
    print(f"{'='*60}")

    if not ports:
        print("\nNo serial devices found!")
        print(" -> Check your USB cable (some are power-only).")
        print(" -> Check if drivers (CH340/CP210x) are installed.")
        return

    found_count = 0
    
    for p in ports:
        # Filter: Skip Bluetooth ports on Mac/Windows to reduce noise
        if "Bluetooth" in p.description or "n/a" in p.description:
            continue
            
        found_count += 1
        print(f"\n[Device #{found_count}]")
        print(f"  • Port Name:     {p.device}")
        print(f"  • Serial Number: {p.serial_number if p.serial_number else 'N/A'}")
        print(f"  • Description:   {p.description}")
        print(f"  • Hardware ID:   {p.hwid}")
        
        # Heuristic to guess if it's an Arduino
        if "Arduino" in p.description or "VID:2341" in p.hwid:
            print("  -> STATUS: Likely an Official Arduino")
        elif "USB" in p.description and ("1A86" in p.hwid or "10C4" in p.hwid):
            print("  -> STATUS: Likely a Clone Arduino (CH340/CP210x)")

    print(f"\n{'='*60}")
    print(f"Found {found_count} device(s).")
    print("Copy the 'Serial Number' string into your Python code.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    list_serial_devices()