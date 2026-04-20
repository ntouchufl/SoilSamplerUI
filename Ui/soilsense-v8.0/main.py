"""
SoilSense v8.0 — PyQt6 Rewrite
Replaces Flet with PyQt6. Camera feed reads MJPEG stream from a URL.
"""

import sys
import platform
import threading
import urllib.request

from PyQt6.QtCore import (Qt, QTimer, QThread, pyqtSignal, QObject, QSize)
from PyQt6.QtGui import (QFont, QColor, QPalette, QPixmap, QImage)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QDialog, QLineEdit,
    QGridLayout, QFrame, QSizePolicy, QTabWidget, QCheckBox
)

from hardware_logic import SoilSenseLogic, DeviceStatus


# ─────────────────────────── THEME ────────────────────────────
ACCENT      = "#00ff41"
BG_MAIN     = "#151619"
BG_CARD     = "#1c1e22"
BORDER      = "#2c2e33"
TEXT_MUTED  = "#8e9299"
RED         = "#ff4444"
BLUE        = "#3b82f6"
AMBER       = "#f59e0b"
WHITE       = "#ffffff"
BLACK       = "#000000"


# soilsense-v8.0/main.py

def _qss_btn(bg, fg="#ffffff", radius=12):
    # Determine a specific hover color. 
    # If the background is the ACCENT green (#00ff41), we'll use a darker forest green.
    hover_color = "#00cc33" if bg == ACCENT else f"{bg}cc"
    
    return f"""
        QPushButton {{
            background-color: {bg};
            color: {fg};
            border-radius: {radius}px;
            font-weight: bold;
            padding: 0 18px;
        }}
        QPushButton:hover {{ 
            background-color: {hover_color}; 
        }}
        QPushButton:disabled {{ background-color: #333; color: #666; }}
    """


def _card_frame(parent=None):
    f = QFrame(parent)
    f.setStyleSheet(f"""
        QFrame {{
            background-color: {BG_CARD};
            border: 2px solid {BORDER};
            border-radius: 12px;
        }}
    """)
    return f


# ─────────────────────── MJPEG STREAM THREAD ───────────────────
class MjpegThread(QThread):
    """Reads an MJPEG stream from a URL and emits QPixmap frames."""
    frame_ready = pyqtSignal(QPixmap)
    error       = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._running = True

    def run(self):
        try:
            req = urllib.request.urlopen(self.url, timeout=5)
        except Exception as e:
            self.error.emit(str(e))
            return

        buf = b""
        while self._running:
            try:
                buf += req.read(4096)
            except Exception as e:
                self.error.emit(str(e))
                break

            # Find JPEG boundaries
            start = buf.find(b"\xff\xd8")
            end   = buf.find(b"\xff\xd9")
            if start != -1 and end != -1 and end > start:
                jpg = buf[start:end + 2]
                buf = buf[end + 2:]
                img = QImage.fromData(jpg)
                if not img.isNull():
                    self.frame_ready.emit(QPixmap.fromImage(img))

    def stop(self):
        self._running = False
        self.quit()


# ──────────────────────── CAMERA WIDGET ────────────────────────
class CameraWidget(QLabel):
    """
    Shows a live MJPEG stream in real mode.
    In dummy mode the stream is killed and a static placeholder is shown.
    Call set_dummy_mode(True/False) to switch at runtime.
    """
    def __init__(self, url: str, dummy: bool = False, parent=None):
        super().__init__(parent)
        self._url    = url
        self._thread = None

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"background:{BLACK}; border:2px solid {BORDER}; border-radius:12px;")
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(200)

        # Initialise in whatever mode is requested
        self.set_dummy_mode(dummy)

    # ── public API ──────────────────────────────────────────────
    def set_dummy_mode(self, is_dummy: bool):
        if is_dummy:
            self._stop_stream()
            self._show_dummy_placeholder()
        else:
            self._show_connecting()
            self._start_stream()

    def stop(self):
        self._stop_stream()

    # ── stream lifecycle ────────────────────────────────────────
    def _start_stream(self):
        self._stop_stream()                        # kill any previous thread
        self._thread = MjpegThread(self._url)
        self._thread.frame_ready.connect(self._on_frame)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _stop_stream(self):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            self._thread.wait(2000)
        self._thread = None

    # ── display helpers ─────────────────────────────────────────
    def _show_connecting(self):
        self.clear()
        self.setText("Connecting to stream...")
        self.setStyleSheet(
            f"background:{BLACK}; border:2px solid {BORDER}; border-radius:12px;"
            f" color:#8e9299; font-size:14px;"
        )

    def _show_dummy_placeholder(self):
        self.clear()
        self.setText("[ DUMMY MODE ]\nJetson stream disabled")
        self.setStyleSheet(
            f"background:#1a1a1a; border:2px dashed {BORDER}; border-radius:12px;"
            f" color:{TEXT_MUTED}; font-size:14px; font-weight:bold;"
        )

    def _on_frame(self, pixmap: QPixmap):
        # Clear placeholder text on first real frame
        if self.text():
            self.clear()
            self.setStyleSheet(
                f"background:{BLACK}; border:2px solid {BORDER}; border-radius:12px;"
            )
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)

    def _on_error(self, msg: str):
        self.clear()
        self.setText(f"Stream error:\n{msg}")
        self.setStyleSheet(
            f"background:{BLACK}; border:2px solid {RED}; border-radius:12px;"
            f" color:{RED}; font-size:13px;"
        )


# ────────────────────────── DIALOGS ────────────────────────────
class KeypadDialog(QDialog):
    def __init__(self, logic, current_val, scale, parent=None):
        super().__init__(parent)
        self.logic  = logic
        self.setModal(True)
        self.setWindowTitle("Enter Samples (Max 40)")
        self.setStyleSheet(f"background:{BG_CARD}; color:{WHITE};")

        root = QVBoxLayout(self)
        root.setSpacing(12)

        self.display = QLabel(str(current_val))
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(f"background:black; border-radius:8px; font-size:{int(36*scale)}px; font-weight:bold; padding:14px;")
        root.addWidget(self.display)

        keys = [["1","2","3"],["4","5","6"],["7","8","9"],["C","0","OK"]]
        grid = QGridLayout()
        grid.setSpacing(10)
        for r, row in enumerate(keys):
            for c, k in enumerate(row):
                btn = QPushButton(k)
                h = int(90*scale)
                btn.setFixedHeight(h)
                if k == "C":
                    btn.setStyleSheet(_qss_btn(RED))
                elif k == "OK":
                    btn.setStyleSheet(_qss_btn(ACCENT, BLACK))
                else:
                    btn.setStyleSheet(_qss_btn(BORDER))
                btn.setFont(QFont("", int(20*scale), QFont.Weight.Bold))
                btn.clicked.connect(lambda _, v=k: self._press(v))
                grid.addWidget(btn, r, c)
        root.addLayout(grid)

    def _press(self, val):
        cur = self.display.text()
        if val == "C":
            self.display.setText("0")
        elif val == "OK":
            v = min(int(cur or "0"), 40)
            self.logic.update_samples(v)
            self.accept()
        else:
            new = ("0" if cur == "0" else cur) + val if cur != "0" else val
            self.display.setText(str(min(int(new), 40)))


class WeightDialog(QDialog):
    def __init__(self, logic, scale, parent=None):
        super().__init__(parent)
        self.logic = logic
        self.setModal(True)
        self.setWindowTitle("Select Target Weight")
        self.setStyleSheet(f"background:{BG_CARD}; color:{WHITE};")

        root = QVBoxLayout(self)
        root.setSpacing(10)

        for label, w in [("10g (Small)", 10), ("20g (Medium)", 20), ("30g (Large)", 30)]:
            btn = QPushButton(label)
            btn.setFixedHeight(int(80*scale))
            btn.setFont(QFont("", int(20*scale), QFont.Weight.Bold))
            btn.setStyleSheet(_qss_btn(BORDER))
            btn.clicked.connect(lambda _, ww=w: self._set(ww))
            root.addWidget(btn)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{BORDER};"); root.addWidget(sep)

        row = QHBoxLayout()
        self.custom_in = QLineEdit()
        self.custom_in.setPlaceholderText("Custom (g)")
        self.custom_in.setFixedHeight(int(70*scale))
        self.custom_in.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_in.setStyleSheet(f"background:black; color:white; border:1px solid {BORDER}; border-radius:8px; font-size:{int(18*scale)}px;")
        row.addWidget(self.custom_in)

        apply_btn = QPushButton("APPLY")
        apply_btn.setFixedHeight(int(70*scale))
        apply_btn.setFont(QFont("", int(18*scale), QFont.Weight.Bold))
        apply_btn.setStyleSheet(_qss_btn(ACCENT, BLACK))
        apply_btn.clicked.connect(self._apply_custom)
        row.addWidget(apply_btn)
        root.addLayout(row)

    def _set(self, w):
        self.logic.soil_weight = int(w)
        self.logic.log(f"Soil weight target set to {w}g")
        self.accept()

    def _apply_custom(self):
        v = self.custom_in.text()
        if v.isdigit():
            self._set(int(v))


# ──────────────────────── MAIN WINDOW ──────────────────────────
class SoilSenseWindow(QMainWindow):
    _refresh_sig = pyqtSignal()   # thread-safe bridge

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoilSense v8.0")

        # ── Scaling ──
        if platform.system() == "Darwin":
            self.SCALE = 0.5
            self.resize(960, 600)
        else:
            self.SCALE = 1.0
            self.showFullScreen()

        S = self.SCALE
        self.TXT_TINY  = int(18 * S)
        self.TXT_MED   = int(24 * S)
        self.TXT_LARGE = int(36 * S)
        self.BTN_H     = int(80 * S)

        # ── Logic ──
        self.logic    = SoilSenseLogic()
        self.ui_state = {"gantry_zeroed": False}

        # Wire logic callbacks → thread-safe signal
        self._refresh_sig.connect(self._refresh_ui)
        self.logic.on_log_update      = lambda: self._refresh_sig.emit()
        self.logic.on_status_update   = lambda: self._refresh_sig.emit()
        self.logic.on_sequence_update = lambda: self._refresh_sig.emit()

        # ── Video ──
        self.VIDEO_URL = "http://127.0.0.1:5005/video_feed"

        # ── Global stylesheet ──
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background-color:{BG_MAIN}; color:{WHITE}; }}
            QTabWidget::pane {{ border:none; }}
            QTabBar::tab {{
                background:{BG_CARD}; color:{TEXT_MUTED}; padding:10px 24px;
                border-radius:8px 8px 0 0; font-size:{self.TXT_MED}px; font-weight:bold;
            }}
            QTabBar::tab:selected {{ color:{ACCENT}; border-bottom:3px solid {ACCENT}; }}
            QScrollBar:vertical {{ background:{BG_CARD}; width:8px; border-radius:4px; }}
            QScrollBar::handle:vertical {{ background:{BORDER}; border-radius:4px; }}
        """)

        self._build_ui()
        self._refresh_ui()

    # ──────────────────────── BUILD UI ──────────────────────────
    def _build_ui(self):
        S = self.SCALE
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(int(20*S), int(10*S), int(20*S), int(10*S))
        root_layout.setSpacing(int(8*S))

        # Header
        root_layout.addWidget(self._build_header())

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{BORDER};")
        root_layout.addWidget(sep)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_dashboard(), "Dashboard")
        self.tabs.addTab(self._build_debug(),     "Manual Debug")
        root_layout.addWidget(self.tabs)

    # ── Header ──
    def _build_header(self):
        S = self.SCALE
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0,0,0,0)

        title = QLabel("SoilSense v8.0")
        title.setFont(QFont("", self.TXT_LARGE, QFont.Weight.Bold))
        lay.addWidget(title)
        lay.addStretch()

        self.door_indicators   = {}
        self.status_indicators = {}

        for key, label in [("left","L Door"),("right","R Door")]:
            dot = self._make_dot(DeviceStatus.OFFLINE.value)
            self.door_indicators[key] = dot
            row = QHBoxLayout(); row.setSpacing(4)
            row.addWidget(dot); row.addWidget(self._muted_lbl(label))
            c = QWidget(); c.setLayout(row); lay.addWidget(c)
            lay.addSpacing(int(12*S))

        for key, label in [("gantry","Gantry"),("stirrer","Stirrer"),("scoop","Scoop"),("jetson","Jetson")]:
            dot = self._make_dot(DeviceStatus.OFFLINE.value)
            self.status_indicators[key] = dot
            row = QHBoxLayout(); row.setSpacing(4)
            row.addWidget(dot); row.addWidget(self._muted_lbl(label))
            c = QWidget(); c.setLayout(row); lay.addWidget(c)
            lay.addSpacing(int(12*S))

        return w

    # ── Dashboard ──
    def _build_dashboard(self):
        S = self.SCALE
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, int(10*S), 0, 0)
        outer.setSpacing(int(10*S))

        # 3-column area
        cols = QHBoxLayout()
        cols.setSpacing(int(15*S))

        # Left — camera + soil results
        left = QVBoxLayout()
        left.setSpacing(int(10*S))
        left.addWidget(self._section_label("JETSON FEED"))
        self.camera_widget = CameraWidget(
            self.VIDEO_URL,
            dummy=(self.logic.device_modes.get("jetson") == "dummy")
        )
        self.camera_widget.setMinimumHeight(int(240*S))
        left.addWidget(self.camera_widget)
        left.addWidget(self._section_label("SOIL RESULTS"))
        self.soil_results_scroll, self.soil_results_layout = self._scroll_card()
        left.addWidget(self.soil_results_scroll, 1)
        lw = QWidget(); lw.setLayout(left)
        cols.addWidget(lw, 1)

        # Middle — scooper status
        mid = QVBoxLayout()
        mid.setSpacing(int(10*S))
        mid.addWidget(self._section_label("SCOOPER STATUS"))
        SCOOPER_STEPS = [
            "Idle","Moving to Bag","Stirring","Analyzing","Scooping",
            "Moving to Tube","Dispensing","Returning to Bag","Emptying"
        ]
        self.step_indicators = {}
        scroll, step_layout = self._scroll_card()
        for step in SCOOPER_STEPS:
            lbl = QLabel(step)
            lbl.setFont(QFont("", self.TXT_TINY, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color:{TEXT_MUTED}; padding:8px; border-radius:6px;")
            step_layout.addWidget(lbl)
            self.step_indicators[step] = lbl
        step_layout.addStretch()
        mid.addWidget(scroll, 1)
        mw = QWidget(); mw.setLayout(mid)
        cols.addWidget(mw, 1)

        # Right — logs
        right = QVBoxLayout()
        right.setSpacing(int(10*S))
        right.addWidget(self._section_label("SYSTEM LOGS"))
        log_card = _card_frame()
        log_card.setStyleSheet(f"QFrame {{ background:black; border:2px solid {BORDER}; border-radius:12px; }}")
        log_inner = QVBoxLayout(log_card)
        self.log_scroll = QScrollArea()
        self.log_scroll.setWidgetResizable(True)
        self.log_scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        log_container = QWidget()
        self.log_layout = QVBoxLayout(log_container)
        self.log_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.log_layout.setSpacing(int(3*S))
        self.log_scroll.setWidget(log_container)
        log_inner.addWidget(self.log_scroll)
        right.addWidget(log_card, 1)
        rw = QWidget(); rw.setLayout(right)
        cols.addWidget(rw, 1)

        outer.addLayout(cols, 1)

        # Bottom control bar
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color:{BORDER};")
        outer.addWidget(sep2)
        outer.addLayout(self._build_control_bar())

        return w

    def _build_control_bar(self):
        S = self.SCALE
        bar = QHBoxLayout()
        bar.setSpacing(int(10*S))

        self.total_samples_label = QLabel()
        self.total_samples_label.setFont(QFont("", self.TXT_MED))
        self.total_samples_label.setStyleSheet(f"color:{TEXT_MUTED};")
        bar.addWidget(self.total_samples_label)
        bar.addStretch()

        btn_data = [
            ("btn_zero_gantry", "ZERO FIRST",  AMBER,  BLACK,  self._handle_zero_gantry),
            ("btn_samples",     "SAMPLES",      BORDER, WHITE,  self._handle_samples),
            ("btn_weight",      "WEIGHT",       BORDER, WHITE,  self._handle_weight),
            ("btn_export",      "EXPORT",       BLUE,   WHITE,  self._handle_export),
            ("btn_stop",        "STOP",         RED,    WHITE,  self._handle_stop),
            ("btn_start",       "START",        ACCENT, BLACK,  self._handle_start),
        ]
        for attr, text, bg, fg, cb in btn_data:
            btn = QPushButton(text)
            btn.setFixedHeight(self.BTN_H)
            btn.setMinimumWidth(int(120*S))
            btn.setFont(QFont("", self.TXT_MED, QFont.Weight.Bold))
            btn.setStyleSheet(_qss_btn(bg, fg))
            btn.clicked.connect(cb)
            setattr(self, attr, btn)
            bar.addWidget(btn)

        self.btn_stop.hide()
        return bar

    # ── Debug Tab ──
    def _build_debug(self):
        S = self.SCALE
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(int(20*S), int(20*S), int(20*S), int(20*S))
        layout.setSpacing(int(15*S))

        title = QLabel("HARDWARE MANUAL OVERRIDE")
        title.setFont(QFont("", self.TXT_MED, QFont.Weight.Bold))
        layout.addWidget(title)

        # Device rows
        row1 = QHBoxLayout()
        for name in ["gantry", "stirrer", "scoop"]:
            row1.addWidget(self._device_control(name))
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        for name in ["jetson", "doors"]:
            row2.addWidget(self._device_control(name))
        layout.addLayout(row2)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{BORDER};"); layout.addWidget(sep)

        title2 = QLabel("DUMMY RESPONSE SETTINGS")
        title2.setFont(QFont("", self.TXT_MED, QFont.Weight.Bold))
        layout.addWidget(title2)

        # Steppers
        stepper_row = QHBoxLayout()
        stepper_row.addWidget(self._stepper_widget("Move Time (s):", "move_time", step=0.5, is_float=True))
        stepper_row.addWidget(self._stepper_widget("Analyze Time (s):", "analyze_time", step=0.5, is_float=True))
        layout.addLayout(stepper_row)

        soil_lbl = QLabel("Mock Soil Types (comma separated):")
        soil_lbl.setStyleSheet(f"color:{TEXT_MUTED};")
        soil_lbl.setFont(QFont("", self.TXT_TINY))
        layout.addWidget(soil_lbl)

        soil_input = QLineEdit(", ".join(self.logic.dummy_responses["soil_types"]))
        soil_input.setFixedHeight(int(60*S))
        soil_input.setStyleSheet(f"background:black; color:white; border:1px solid {BORDER}; border-radius:8px; font-size:{self.TXT_MED}px; padding:0 10px;")
        soil_input.textChanged.connect(lambda t: self.logic.dummy_responses.update({"soil_types": [s.strip() for s in t.split(",")]}))
        layout.addWidget(soil_input)

        exit_btn = QPushButton("EXIT TO DESKTOP")
        exit_btn.setFixedHeight(self.BTN_H)
        exit_btn.setFont(QFont("", self.TXT_MED, QFont.Weight.Bold))
        exit_btn.setStyleSheet(_qss_btn(RED))
        exit_btn.clicked.connect(QApplication.quit)
        layout.addWidget(exit_btn)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _device_control(self, name):
        S = self.SCALE
        card = _card_frame()
        lay = QVBoxLayout(card)
        lay.setSpacing(int(10*S))

        top = QHBoxLayout()
        label = QLabel(name.upper())
        label.setFont(QFont("", self.TXT_TINY, QFont.Weight.Bold))
        top.addWidget(label)
        top.addStretch()

        dummy_cb = QCheckBox("Dummy Mode")
        dummy_cb.setChecked(self.logic.device_modes[name] == "dummy")
        dummy_cb.setStyleSheet(f"color:{WHITE}; font-size:{self.TXT_TINY}px;")
        def _on_dummy_toggle(state, n=name):
            mode = "dummy" if state else "real"
            self.logic.set_device_mode(n, mode)
            if n == "jetson":
                self.camera_widget.set_dummy_mode(mode == "dummy")
        dummy_cb.stateChanged.connect(_on_dummy_toggle)
        top.addWidget(dummy_cb)
        lay.addLayout(top)

        btns = QHBoxLayout()
        if name == "doors":
            for side in ["left", "right"]:
                b = QPushButton(f"Toggle {side.capitalize()}")
                b.setFixedHeight(int(60*S))
                b.setFont(QFont("", self.TXT_TINY))
                b.setStyleSheet(_qss_btn(BORDER))
                b.clicked.connect(lambda _, s=side: self.logic.toggle_dummy_door(s))
                btns.addWidget(b)
        else:
            for cmd, label in [(b"CMD1", "Trigger 1"), (b"CMD2", "Trigger 2")]:
                b = QPushButton(label)
                b.setFixedHeight(int(60*S))
                b.setFont(QFont("", self.TXT_TINY))
                b.setStyleSheet(_qss_btn(BORDER))
                b.clicked.connect(lambda _, n=name, c=cmd: self.logic.write_hardware(n, c))
                btns.addWidget(b)
        lay.addLayout(btns)
        return card

    def _stepper_widget(self, label_text, key, step=1, is_float=False):
        S = self.SCALE
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(int(5*S))

        lbl = QLabel(label_text)
        lbl.setFont(QFont("", self.TXT_TINY))
        lbl.setStyleSheet(f"color:{TEXT_MUTED};")
        lay.addWidget(lbl)

        row = QHBoxLayout()
        row.setSpacing(int(5*S))

        minus = QPushButton("−")
        val_lbl = QLabel(str(self.logic.dummy_responses[key]))
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setFont(QFont("", self.TXT_MED, QFont.Weight.Bold))
        val_lbl.setMinimumWidth(int(60*S))
        plus = QPushButton("+")

        for btn in [minus, plus]:
            btn.setFixedSize(int(44*S), int(44*S))
            btn.setFont(QFont("", self.TXT_MED))
            btn.setStyleSheet(_qss_btn(BORDER))

        def _change(delta):
            current = float(val_lbl.text()) if is_float else int(val_lbl.text())
            new_val = max(0.0 if is_float else 0, current + delta)
            new_val = round(new_val, 1) if is_float else int(new_val)
            val_lbl.setText(str(new_val))
            self.logic.dummy_responses.update({key: new_val})

        minus.clicked.connect(lambda: _change(-step))
        plus.clicked.connect(lambda: _change(step))

        row.addWidget(minus)
        row.addWidget(val_lbl)
        row.addWidget(plus)
        lay.addLayout(row)
        return w

    # ─────────────────── HANDLERS ───────────────────────────────
    def _handle_start(self):
        threading.Thread(target=self.logic.run_sequence, daemon=True).start()

    def _handle_stop(self):
        self.logic.stop_sequence()
        self.ui_state["gantry_zeroed"] = False
        self._refresh_ui()

    def _handle_export(self):
        self.logic.export_results_csv()

    def _handle_zero_gantry(self):
        self.logic.zero_gantry()
        self.ui_state["gantry_zeroed"] = True
        self._refresh_ui()

    def _handle_samples(self):
        dlg = KeypadDialog(self.logic, self.logic.total_samples, self.SCALE, self)
        if dlg.exec():
            self._refresh_ui()

    def _handle_weight(self):
        dlg = WeightDialog(self.logic, self.SCALE, self)
        if dlg.exec():
            self._refresh_ui()

    # ─────────────────── REFRESH UI ─────────────────────────────
    def _refresh_ui(self):
        logic = self.logic

        # Logs
        while self.log_layout.count():
            item = self.log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for line in logic.logs:
            lbl = QLabel(line)
            lbl.setFont(QFont("Courier", self.TXT_TINY))
            lbl.setStyleSheet(f"color:{TEXT_MUTED};")
            lbl.setWordWrap(True)
            self.log_layout.addWidget(lbl)
        # Auto-scroll
        QTimer.singleShot(50, lambda: self.log_scroll.verticalScrollBar().setValue(
            self.log_scroll.verticalScrollBar().maximum()
        ))

        # Soil results
        while self.soil_results_layout.count() > 1:  # keep stretch
            item = self.soil_results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, data in logic.soil_results.items():
            lbl = QLabel(f"Sample {i+1}: {data.get('classification','N/A')}")
            lbl.setFont(QFont("", self.TXT_TINY))
            lbl.setStyleSheet(f"color:{WHITE};")
            self.soil_results_layout.insertWidget(i, lbl)

        # Samples / weight label
        self.total_samples_label.setText(
            f"Target: {logic.total_samples} samples | {logic.soil_weight}g"
        )

        # Status dots
        for device, indicator in self.status_indicators.items():
            indicator.setStyleSheet(
                f"background:{logic.statuses[device].value}; border-radius:{indicator.width()//2}px;"
            )
        self.door_indicators["left"].setStyleSheet(
            f"background:{logic.door_statuses['left'].value}; border-radius:{self.door_indicators['left'].width()//2}px;"
        )
        self.door_indicators["right"].setStyleSheet(
            f"background:{logic.door_statuses['right'].value}; border-radius:{self.door_indicators['right'].width()//2}px;"
        )

        # Start/stop button states
        if logic.isRunning:
            self.btn_start.setText("RUNNING")
            self.btn_start.setDisabled(True)
        elif not self.ui_state["gantry_zeroed"]:
            self.btn_start.setText("ZERO FIRST")
            self.btn_start.setDisabled(True)
            self.btn_zero_gantry.setStyleSheet(_qss_btn(AMBER, BLACK))
        else:
            self.btn_start.setText("START")
            self.btn_start.setDisabled(False)
            self.btn_zero_gantry.setStyleSheet(_qss_btn(BORDER))

        self.btn_stop.setVisible(logic.isRunning)
        self.btn_samples.setDisabled(logic.isRunning)
        self.btn_weight.setDisabled(logic.isRunning)

        # Step highlighter
        for step, lbl in self.step_indicators.items():
            if logic.scooper_status == step:
                lbl.setStyleSheet(f"background:{ACCENT}; color:black; padding:8px; border-radius:6px; font-weight:bold;")
            else:
                lbl.setStyleSheet(f"color:{TEXT_MUTED}; padding:8px; border-radius:6px;")

    # ─────────────── HELPERS ────────────────────────────────────
    def _make_dot(self, color: str) -> QLabel:
        S = self.SCALE
        size = int(24 * S)
        dot = QLabel()
        dot.setFixedSize(size, size)
        dot.setStyleSheet(f"background:{color}; border-radius:{size//2}px;")
        return dot

    def _muted_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("", self.TXT_TINY))
        lbl.setStyleSheet(f"color:{TEXT_MUTED};")
        return lbl

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("", self.TXT_MED, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color:{TEXT_MUTED};")
        return lbl

    def _scroll_card(self):
        """Returns (QScrollArea_inside_card_frame, inner QVBoxLayout)."""
        card = _card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4,4,4,4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(inner)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(int(5 * self.SCALE))
        layout.addStretch()
        scroll.setWidget(inner)
        card_layout.addWidget(scroll)

        # return the card (to add to parent) + inner layout (to populate)
        return card, layout

    def closeEvent(self, event):
        self.camera_widget.stop()
        super().closeEvent(event)


# ──────────────────────── ENTRY POINT ──────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette fallback
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(BG_MAIN))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(WHITE))
    palette.setColor(QPalette.ColorRole.Base,            QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(BORDER))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(WHITE))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(WHITE))
    palette.setColor(QPalette.ColorRole.Text,            QColor(WHITE))
    palette.setColor(QPalette.ColorRole.Button,          QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(WHITE))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BLACK))
    app.setPalette(palette)

    win = SoilSenseWindow()
    win.show()
    sys.exit(app.exec())