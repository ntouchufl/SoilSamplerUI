# arduino_worker.py
from PySide6.QtCore import QObject, Signal, Slot
import serial
import serial.tools.list_ports
import time
import queue
import threading

class ArduinoWorker(QObject):
    # Custom signals to talk to the main thread
    connected = Signal(str)
    disconnected = Signal(str)
    ack = Signal(str)
    error = Signal(str)
    log = Signal(str)  # Useful for debugging

    def __init__(self, target_serial_number: str = None, specific_port: str = None, baud=115200, parent=None):
        super().__init__(parent)
        self._ser = None
        self._baud = baud
        self._target_sn = target_serial_number
        self._specific_port = specific_port
        
        # Threading safe queue
        self._cmd_q = queue.Queue()
        self._stop = threading.Event()
        self._max_wait_s = 5.0  # Reduced timeout for snappier feeling

    def start(self):
        """Starts the background loop."""
        self._stop.clear()
        t = threading.Thread(target=self._pump, daemon=True)
        t.start()

    def stop(self):
        """Stops the thread and closes serial."""
        self._stop.set()
        if self._ser:
            try: self._ser.close()
            except: pass
        self.disconnected.emit(self._target_sn or "Unknown")

    def e_stop(self):
        """Emergency stop: Clear queue and stops all processes but keeps serial open."""
        # Find a way to have the arduino stop immediately
        self._cmd_q.queue.clear()  # Clear pending commands
        self.stop()  # Then stop the thread and serial connection

    def _detect_port(self) -> str | None:
        """
        Smart detection:
        1. If specific_port is given (e.g., COM3), use it.
        2. If target_serial_number is given, scan all USB devices for a match.
        """
        if self._specific_port:
            return self._specific_port

        ports = serial.tools.list_ports.comports()
        
        # Method A: Search by Serial Number (Best for multiple Arduinos)
        if self._target_sn:
            for p in ports:
                if p.serial_number == self._target_sn:
                    return p.device
            return None
        
        return None

    def _open_serial(self):
            port = self._detect_port()
            if not port:
                # Emit disconnected to update the GUI to "Missing"
                self.disconnected.emit(self._target_sn or "Unknown")
                print(f"CRITICAL: Arduino with SN '{self._target_sn}' not found! Retrying...")
                time.sleep(2) 
                return

            try:
                self._ser = serial.Serial(port=port, baudrate=self._baud, timeout=0.2)
                self.connected.emit(port) # Tells GUI we connected
                self.log.emit(f"Connected to {port} (SN: {self._target_sn})")
                time.sleep(2.0)  # Critical: Wait for Arduino Auto-Reset
                self._ser.reset_input_buffer()
            except Exception as e:
                self.error.emit(f"Serial open failed: {e}")
                self.disconnected.emit(self._target_sn or "Unknown") # Also update GUI on crash
                self._ser = None
                time.sleep(2)

    def _pump(self):
        """The main loop running in a background thread."""
        while not self._stop.is_set():
            if not self._ser:
                self._open_serial()
                continue

            try:
                # 1. Get command from queue (non-blocking wait)
                try:
                    cmd = self._cmd_q.get(timeout=0.1)
                except queue.Empty:
                    # --- NEW: IDLE DISCONNECT CHECK ---
                    # Gently check the OS buffer. If the cable was pulled, this throws an error.
                    try:
                        _ = self._ser.in_waiting
                    except Exception:
                        self.log.emit(f"Device unplugged: {self._target_sn}")
                        self.disconnected.emit(self._target_sn or "Unknown")
                        
                        # Clean up the broken connection and reset
                        try: self._ser.close()
                        except: pass
                        self._ser = None
                    continue

                # 2. Write Command
                full_cmd = f"{cmd}\n".encode('utf-8')
                self._ser.write(full_cmd)
                self.log.emit(f"Sent: {cmd}")

                # 3. Wait for "Finished" response
                t0 = time.time()
                finished = False
                while time.time() - t0 < self._max_wait_s:
                    if self._ser.in_waiting:
                        line = self._ser.readline().decode(errors="ignore").strip()
                        if line:
                            if "Finished" in line:
                                self.ack.emit(cmd)
                                finished = True
                                break
                            else:
                                # Forward any other print() from Arduino to UI
                                self.log.emit(f"ARDUINO: {line}")
                    time.sleep(0.01)

                if not finished:
                    self.error.emit(f"Timeout on command: {cmd}")

            except Exception as e:
                self.error.emit(f"IO Error: {e}")
                # Also catch disconnects that happen exactly while writing
                self.disconnected.emit(self._target_sn or "Unknown")
                try: self._ser.close()
                except: pass
                self._ser = None

    @Slot(str)
    def send_raw(self, cmd: str):
        """Generic slot to send any string command."""
        self._cmd_q.put(cmd)