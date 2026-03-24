import sys
import signal
from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit, QLabel
from arduino_worker import ArduinoWorker

DIST = 5.0 # inches between soil bags
ROWS = 3
COLS = 3

class GantryController(QObject):
    ui_update = Signal(str)  # Signal to send updates to the UI
    def __init__(self, gan_worker, scoop_worker, stir_worker, rows, cols):
        super().__init__()
        self.gan_worker = gan_worker
        self.scoop_worker = scoop_worker
        self.stir_worker = stir_worker
        self.rows = rows
        self.cols = cols
        self.current_row = 0
        self.current_col = 0
        self.soil_types = []

        self.reset_flag = False
        
        # State tracker for the scoop to know if we are scooping or unscooping
        self.currently_scooped = False 

        # --- SIGNAL CHAINING ---
        self.gan_worker.ack.connect(self.start_stir) 
        self.stir_worker.ack.connect(self.start_scoop) 
        self.scoop_worker.ack.connect(self.handle_scoop_ack) 

    def connect_arduinos(self):
        print("Connecting to Arduinos...")
        self.gan_worker.start()
        self.stir_worker.start()
        self.scoop_worker.start()

    def start_process(self):
        print("\n--- STARTING SOIL ANALYSIS SEQUENCE ---")
        
        # Give Arduinos 2 seconds to boot, then move gantry
        QTimer.singleShot(2000, self.send_gantry_move) 

    def send_gantry_move(self):
        if self.current_row < self.rows:
            x = self.current_col * DIST
            y = self.current_row * DIST
            print(f"[GANTRY] Moving to bag: Row {self.current_row}, Col {self.current_col} (x={x}, y={y})")
            self.gan_worker.send_raw(f"{x},{y}")
        else:
            print("\n[SYSTEM] All bags processed!")
            self.display_results()

    def start_stir(self, msg=None):
        print("[STIR] Starting stir process...")
        self.stir_worker.send_raw("1") 

    def start_scoop(self, msg=None):
        print("[SCOOP] Scooping sample...")
        self.currently_scooped = True
        self.scoop_worker.send_raw("1") 

    def start_unscoop(self):
        print("[SCOOP] Releasing sample...")
        self.currently_scooped = False
        self.scoop_worker.send_raw("0")
    
    def handle_scoop_ack(self, msg=None):
        # Use our internal state to know what just finished
        if self.currently_scooped:
            print("[CAMERA] Scoop finished. Taking picture...")
            self.capture_image()
        else:
            print("[SYSTEM] Unscoop finished. Moving to next bag...")
            self.finish_bag_cycle()
    
    def capture_image(self):
        # simulate camera delay
        print("[CAMERA] Analyzing soil...")
        soil_type = 1 # placeholder for actual image processing result
        self.soil_types.append(soil_type)

        bag_number = len(self.soil_types)
        msg = f"Bag {bag_number} (Row {self.current_row}, Col {self.current_col}): Soil Type {soil_type}"
        self.ui_update.emit(msg)  # Send update to UI
        
        # Wait 1 second after taking picture before unscooping
        QTimer.singleShot(1000, self.start_unscoop)

    def finish_bag_cycle(self):
        print("--- Bag Cycle Complete ---\n")
        
        if self.reset_flag:
            self.reset_flag = False
            print("[SYSTEM] Reset flag detected. Stopping process.")
            return

        self.current_col += 1
        if self.current_col >= self.cols:
            self.current_col = 0
            self.current_row += 1
            
        self.send_gantry_move()

    def display_results(self):
        print("Final Soil Types:", self.soil_types)
        self.ui_update.emit("\n--- ALL BAGS PROCESSED ---")
        self.ui_update.emit("Final Soil Types: " + ", ".join(str(s) for s in self.soil_types))

    def emergency_stop(self):
        print("\n!!! EMERGENCY STOP ACTIVATED !!!")
        self.gan_worker.e_stop()
        self.stir_worker.e_stop()
        self.scoop_worker.e_stop()
        print("All processes halted immediately.")
    
    
    def reset_system(self):
            print("\n--- SYSTEM RESETTING ---")
            # Reset all logic variables
            self.current_row = 0
            self.current_col = 0
            self.soil_types = []
            self.currently_scooped = False
            self.reset_flag = True  
            
            # Tell the UI what happened
            self.ui_update.emit("\n⚠️ System Reset. Ready to start over.")



class SystemDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Soil Analysis Dashboard")
        self.resize(500, 400)

        # Build UI Layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # add e-stop and reset buttons
        button_layout = QVBoxLayout()
        self.btn_estop = QPushButton("EMERGENCY STOP")
        self.btn_estop.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.btn_reset = QPushButton("Reset System")
        self.btn_reset.setStyleSheet("background-color: orange; color: black; font-weight: bold;")
        button_layout.addWidget(self.btn_estop)
        button_layout.addWidget(self.btn_reset)
        main_layout.addLayout(button_layout)

        # add results display
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)
        main_layout.addWidget(self.results_display)

        self.results_display.setPlainText("Results will be displayed here.")


        status_layout = QVBoxLayout()

        self.lbl_gan = QLabel("Gantry: 🔴 Missing")
        self.lbl_stir = QLabel("Stir: 🔴 Missing")
        self.lbl_scoop = QLabel("Scoop: 🔴 Missing")

        font = self.lbl_gan.font()
        font.setPointSize(14)
        self.lbl_gan.setFont(font)
        self.lbl_stir.setFont(font)
        self.lbl_scoop.setFont(font)

        status_layout.addWidget(self.lbl_gan)
        status_layout.addWidget(self.lbl_stir)
        status_layout.addWidget(self.lbl_scoop)

        main_layout.addLayout(status_layout)

        self.start_button = QPushButton("Start Process")
        self.start_button.setMinimumHeight(50)
        main_layout.addWidget(self.start_button)

        # Setup Arduinos
        # (Make sure these match your actual serial numbers and baud rates)
        #self.ard_gan = ArduinoWorker(target_serial_number="48CA435A3A20", baud=115200)
        #self.ard_stir = ArduinoWorker(target_serial_number="95138323838351401091", baud=9600)
        #self.ard_scoop = ArduinoWorker(target_serial_number="44231313430351116261", baud=9600)


        self.ard_gan = ArduinoWorker(target_serial_number="1344A474030351C07938", baud=9600)
        self.ard_stir = ArduinoWorker(target_serial_number="33436323438351818303", baud=9600)
        self.ard_scoop = ArduinoWorker(target_serial_number="1344A474030351B0F919", baud=9600)

        # Optional: Route logs to terminal (you can route these to a UI text box later)
        self.ard_gan.log.connect(lambda s: print(f"  [Gan Log]: {s}"))
        self.ard_stir.log.connect(lambda s: print(f"  [Stir Log]: {s}"))
        self.ard_scoop.log.connect(lambda s: print(f"  [Scoop Log]: {s}"))


        self.ard_gan.connected.connect(lambda sn: self.lbl_gan.setText(f"Gantry: 🟢 Connected ({sn})"))
        self.ard_stir.connected.connect(lambda sn: self.lbl_stir.setText(f"Stir: 🟢 Connected ({sn})"))
        self.ard_scoop.connected.connect(lambda sn: self.lbl_scoop.setText(f"Scoop: 🟢 Connected ({sn})"))

        self.ard_gan.disconnected.connect(lambda sn: self.lbl_gan.setText(f"Gantry: 🔴 Missing ({sn})"))
        self.ard_stir.disconnected.connect(lambda sn: self.lbl_stir.setText(f"Stir: 🔴 Missing ({sn})"))
        self.ard_scoop.disconnected.connect(lambda sn: self.lbl_scoop.setText(f"Scoop: 🔴 Missing ({sn})"))

        # Setup Controller
        self.controller = GantryController(self.ard_gan, self.ard_scoop, self.ard_stir, ROWS, COLS)
        self.controller.connect_arduinos()

        self.controller.ui_update.connect(lambda msg: self.results_display.append(msg))
        
        # Connect Button to Controller
        self.start_button.clicked.connect(self.controller.start_process)
        self.btn_estop.clicked.connect(self.controller.emergency_stop)
        self.btn_reset.clicked.connect(self.controller.reset_system)



def signal_handler(sig, frame):
    print("Exiting...")
    QApplication.quit()

if __name__ == "__main__":
    # CRITICAL FIX: Use QApplication for GUI
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal_handler)

    # Show the dashboard
    window = SystemDashboard()
    window.show()

    sys.exit(app.exec())