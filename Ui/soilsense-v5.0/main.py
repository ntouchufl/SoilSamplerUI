import flet as ft
import time
import threading
import json
import os

# --- CONFIGURATION ---
GANTRY_PORT = "/dev/ttyACM0"
STIRRER_PORT = "/dev/ttyACM1"
SCOOP_PORT = "/dev/ttyACM2"
JETSON_IP = "192.168.1.100"

# --- SYSTEM STATE ---
class SystemState:
    def __init__(self):
        self.gantry = {"x": 0, "y": 0, "status": "disconnected", "targetX": 0, "targetY": 0}
        self.stirrer = {"active": False, "status": "disconnected"}
        self.scoop = {"position": "up", "status": "disconnected"}
        self.jetson = {"status": "disconnected", "ip": JETSON_IP}
        self.process = {
            "isRunning": False,
            "currentRow": 0,
            "currentCol": 0,
            "soilTypes": [],
            "logs": ["SoilSense v4.0 Flet Engine Initialized."]
        }
        self.config = {
            "rows": 3,
            "cols": 3,
            "dist": 5.0
        }
        self.dummyMode = True

state = SystemState()

# --- MOCK SERIAL FOR MAC/DEV ---
class MockSerial:
    def __init__(self, name):
        self.name = name
        self.isOpen = True
    def write(self, data):
        print(f"[MOCK {self.name}] Writing: {data.decode().strip()}")
    def close(self):
        self.isOpen = False

# --- HARDWARE INITIALIZATION ---
ports = {"gantry": None, "stirrer": None, "scoop": None}

def init_hardware():
    global ports
    if state.dummyMode:
        ports = {k: MockSerial(k.upper()) for k in ports}
        return

    try:
        import serial
        # Real Serial Init (Commented out for safety in preview)
        # ports["gantry"] = serial.Serial(GANTRY_PORT, 115200, timeout=1)
        # ports["stirrer"] = serial.Serial(STIRRER_PORT, 9600, timeout=1)
        # ports["scoop"] = serial.Serial(SCOOP_PORT, 9600, timeout=1)
    except Exception as e:
        log(f"Hardware Init Error: {e}. Falling back to mocks.")
        ports = {k: MockSerial(k.upper()) for k in ports}

def log(msg, page=None):
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    state.process["logs"].append(full_msg)
    if len(state.process["logs"]) > 100:
        state.process["logs"].pop(0)
    if page:
        page.update()

# --- PROCESS LOGIC ---
def run_sequence(page):
    log("Starting automated soil analysis sequence...", page)
    state.process["isRunning"] = True
    rows = state.config["rows"]
    cols = state.config["cols"]
    dist = state.config["dist"]
    
    state.process["soilTypes"] = [None] * (rows * cols)
    page.update()

    try:
        for r in range(rows):
            if not state.process["isRunning"]: break
            state.process["currentRow"] = r
            for c in range(cols):
                if not state.process["isRunning"]: break
                state.process["currentCol"] = c
                
                # 1. Move Gantry
                target_x = c * dist
                target_y = r * dist
                log(f"Moving to Grid [{r},{c}] -> ({target_x}, {target_y})", page)
                state.gantry["targetX"] = target_x
                state.gantry["targetY"] = target_y
                
                ports["gantry"].write(f"{target_x},{target_y}\n".encode())
                time.sleep(2) # Simulate travel time
                state.gantry["x"] = target_x
                state.gantry["y"] = target_y
                page.update()

                # 2. Scoop Down
                log("Lowering scoop...", page)
                state.scoop["position"] = "down"
                ports["scoop"].write(b"1\n")
                page.update()
                time.sleep(1)

                # 3. Stir
                log("Stirring soil sample...", page)
                state.stirrer["active"] = True
                ports["stirrer"].write(b"1\n")
                page.update()
                time.sleep(3)
                state.stirrer["active"] = False
                ports["stirrer"].write(b"0\n")
                page.update()

                # 4. Scoop Up
                log("Raising scoop...", page)
                state.scoop["position"] = "up"
                ports["scoop"].write(b"0\n")
                page.update()
                time.sleep(1)

                # 5. Analyze
                log("Analyzing sample with Jetson AI...", page)
                time.sleep(1.5)
                soil_type = "Loam" if (r+c) % 2 == 0 else "Clay"
                state.process["soilTypes"][r * cols + c] = soil_type
                log(f"Result for [{r},{c}]: {soil_type}", page)
                page.update()

        log("Sequence complete.", page)
    except Exception as e:
        log(f"Sequence Error: {e}", page)
    finally:
        state.process["isRunning"] = False
        page.update()

# --- UI COMPONENTS ---

def main(page: ft.Page):
    page.title = "SoilSense v4.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#151619"
    page.padding = 20
    page.window_width = 1200
    page.window_height = 800
    
    init_hardware()

    # --- THEME COLORS ---
    ACCENT = "#00ff41"
    BG_CARD = "#1c1e22"
    BORDER = "#2c2e33"
    TEXT_DIM = "#8e9299"

    def update_status():
        for k in ["gantry", "stirrer", "scoop"]:
            state.__dict__[k]["status"] = "connected" if ports[k] and ports[k].isOpen else "disconnected"

    def handle_start(e):
        if not state.process["isRunning"]:
            threading.Thread(target=run_sequence, args=(page,), daemon=True).start()

    def handle_stop(e):
        state.process["isRunning"] = False
        log("Emergency Stop Triggered.", page)

    def handle_reset(e):
        state.process["isRunning"] = False
        state.process["currentRow"] = 0
        state.process["currentCol"] = 0
        state.process["soilTypes"] = [None] * (state.config["rows"] * state.config["cols"])
        state.gantry["x"] = 0
        state.gantry["y"] = 0
        state.scoop["position"] = "up"
        state.stirrer["active"] = False
        log("System Reset.", page)

    # --- UI LAYOUT ---
    
    # Header
    header = ft.Row(
        [
            ft.Icon(ft.icons.SETTINGS_INPUT_COMPONENT, color=ACCENT, size=30),
            ft.Column(
                [
                    ft.Text("SoilSense v4.0", size=24, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text("Flet Hardware Controller", size=10, color=TEXT_DIM, weight=ft.FontWeight.W_500),
                ],
                spacing=0,
            ),
            ft.VerticalDivider(width=20, color=BORDER),
            ft.Row(
                [
                    ft.Container(
                        content=ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor=ACCENT), ft.Text("GANTRY", size=10, color=TEXT_DIM)]),
                    ),
                    ft.Container(
                        content=ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor=ACCENT), ft.Text("STIRRER", size=10, color=TEXT_DIM)]),
                    ),
                    ft.Container(
                        content=ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor=ACCENT), ft.Text("SCOOP", size=10, color=TEXT_DIM)]),
                    ),
                ],
                spacing=20,
            ),
        ],
        alignment=ft.MainAxisAlignment.START,
    )

    # Main Content Area
    
    # Left Panel: Grid & Controls
    grid_view = ft.GridView(
        expand=1,
        runs_count=state.config["cols"],
        max_extent=150,
        child_aspect_ratio=1.0,
        spacing=10,
        run_spacing=10,
    )

    def build_grid():
        grid_view.controls.clear()
        grid_view.runs_count = state.config["cols"]
        for i in range(state.config["rows"] * state.config["cols"]):
            r = i // state.config["cols"]
            c = i % state.config["cols"]
            is_active = state.process["isRunning"] and state.process["currentRow"] == r and state.process["currentCol"] == c
            soil_type = state.process["soilTypes"][i] if i < len(state.process["soilTypes"]) else None
            
            grid_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"{r},{c}", size=10, color=TEXT_DIM),
                            ft.Text(soil_type if soil_type else "-", size=12, weight=ft.FontWeight.BOLD, color=ACCENT if soil_type else "white"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=BG_CARD if not is_active else ft.colors.with_opacity(0.1, ACCENT),
                    border=ft.border.all(1, ACCENT if is_active else BORDER),
                    border_radius=8,
                    padding=10,
                )
            )

    build_grid()

    # Controls
    controls_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("SYSTEM CONTROLS", size=12, weight=ft.FontWeight.BOLD, color=TEXT_DIM),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "START SEQUENCE",
                            icon=ft.icons.PLAY_ARROW,
                            bgcolor=ACCENT,
                            color="black",
                            on_click=handle_start,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        ),
                        ft.ElevatedButton(
                            "STOP",
                            icon=ft.icons.STOP,
                            bgcolor="#ff4444",
                            color="white",
                            on_click=handle_stop,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        ),
                        ft.OutlinedButton(
                            "RESET",
                            icon=ft.icons.REFRESH,
                            on_click=handle_reset,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        ),
                    ]
                ),
            ],
            spacing=15,
        ),
        padding=20,
        border=ft.border.all(1, BORDER),
        border_radius=12,
        bgcolor=BG_CARD,
    )

    # Right Panel: Logs
    log_list = ft.ListView(expand=1, spacing=5, padding=10)
    
    def update_logs():
        log_list.controls.clear()
        for l in state.process["logs"]:
            log_list.controls.append(ft.Text(l, size=11, font_family="monospace", color=TEXT_DIM))
        log_list.scroll_to(offset=-1, duration=100)

    logs_panel = ft.Container(
        content=ft.Column(
            [
                ft.Row([ft.Text("SYSTEM LOGS", size=12, weight=ft.FontWeight.BOLD, color=TEXT_DIM), ft.Text("LIVE", size=10, color=ACCENT)]),
                ft.Container(
                    content=log_list,
                    bgcolor="black",
                    border=ft.border.all(1, BORDER),
                    border_radius=8,
                    expand=1,
                ),
            ],
            expand=1,
        ),
        expand=1,
        padding=20,
        border=ft.border.all(1, BORDER),
        border_radius=12,
        bgcolor=BG_CARD,
    )

    # Assemble Layout
    page.add(
        header,
        ft.Divider(height=20, color=BORDER),
        ft.Row(
            [
                ft.Column(
                    [
                        ft.Container(
                            content=ft.Column([ft.Text("GANTRY GRID VIEW", size=12, weight=ft.FontWeight.BOLD, color=TEXT_DIM), grid_view], expand=1),
                            padding=20,
                            border=ft.border.all(1, BORDER),
                            border_radius=12,
                            bgcolor=BG_CARD,
                            expand=1,
                        ),
                        controls_panel,
                    ],
                    expand=2,
                    spacing=20,
                ),
                logs_panel,
            ],
            expand=1,
            spacing=20,
        ),
        ft.Container(
            content=ft.Row(
                [
                    ft.Text("LATENCY: 42ms", size=10, color=TEXT_DIM),
                    ft.Text("JETSON: CONNECTED", size=10, color=TEXT_DIM),
                    ft.Text("© 2026 SOILSENSE AUTOMATION SYSTEMS", size=10, color=TEXT_DIM),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.only(top=10),
        )
    )

    # Periodic UI Update
    def refresh_ui():
        while True:
            try:
                build_grid()
                update_logs()
                page.update()
                time.sleep(1)
            except:
                break

    threading.Thread(target=refresh_ui, daemon=True).start()

if __name__ == "__main__":
    # Run as a web app on port 3000
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=3000, host="0.0.0.0")
