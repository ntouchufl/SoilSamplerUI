import flet as ft
import threading
import time
from hardware_logic import SoilSenseLogic, DeviceStatus

def main(page: ft.Page):
    page.title = "SoilSense v6.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#151619"
    page.window_width = 1200
    page.window_height = 900
    page.padding = 20

    # Initialize the Hardware Backend
    logic = SoilSenseLogic()

    # --- UI STYLING ---
    ACCENT = "#00ff41"
    BG_CARD = "#1c1e22"
    BORDER = "#2c2e33"
    TEXT_MUTED = "#8e9299"

    # --- UI COMPONENTS ---
    log_column = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True)
    grid_display = ft.GridView(
        expand=True, 
        runs_count=3, 
        max_extent=150, 
        spacing=10, 
        run_spacing=10
    )
    
    jetson_image = ft.Image(
        src="https://picsum.photos/seed/soil/400/300",
        width=400,
        height=300,
        fit=ft.BoxFit.CONTAIN,
        border_radius=8,
        visible=False
    )
    
    image_placeholder = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=50, color=TEXT_MUTED),
            ft.Text("No Image Data", color=TEXT_MUTED)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=400,
        height=300,
        bgcolor="black",
        border_radius=8,
        border=ft.Border.all(1, BORDER)
    )

    btn_start = ft.Button(
        "START GRID ANALYSIS", 
        icon=ft.Icons.PLAY_ARROW, 
        bgcolor=ACCENT, 
        color="black",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )
    
    btn_stop = ft.Button(
        "STOP", 
        icon=ft.Icons.STOP, 
        bgcolor="#ff4444", 
        color="white",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        visible=False
    )

    # Status Indicators
    status_indicators = {
        "gantry": ft.Container(width=12, height=12, border_radius=6, bgcolor=DeviceStatus.OFFLINE.value, tooltip="Gantry Status"),
        "stirrer": ft.Container(width=12, height=12, border_radius=6, bgcolor=DeviceStatus.OFFLINE.value, tooltip="Stirrer Status"),
        "scoop": ft.Container(width=12, height=12, border_radius=6, bgcolor=DeviceStatus.OFFLINE.value, tooltip="Scoop Status"),
        "jetson": ft.Container(width=12, height=12, border_radius=6, bgcolor=DeviceStatus.OFFLINE.value, tooltip="Jetson Status")
    }

    # --- CALLBACK FUNCTIONS ---
    def refresh_logs_ui():
        log_column.controls = [ft.Text(l, size=12, color=TEXT_MUTED, font_family="monospace") for l in logic.logs]
        page.update()

    def refresh_status_ui():
        for device, indicator in status_indicators.items():
            indicator.bgcolor = logic.statuses[device].value
        page.update()

    def refresh_grid_ui():
        grid_display.controls.clear()
        grid_display.runs_count = logic.grid_cols
        
        for r in range(logic.grid_rows):
            for c in range(logic.grid_cols):
                res = logic.soil_results.get((r, c))
                is_active = logic.isRunning and logic.currentRow == r and logic.currentCol == c
                
                grid_display.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{r},{c}", size=10, color=TEXT_MUTED),
                            ft.Text(res if res else "-", color=ACCENT if res else "white", weight="bold", size=16),
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        alignment=ft.Alignment.CENTER,
                        bgcolor=BG_CARD if not is_active else "#1A00FF41",
                        border=ft.Border.all(1, ACCENT if is_active or res else BORDER),
                        border_radius=8,
                        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT)
                    )
                )
        
        btn_start.disabled = logic.isRunning
        btn_stop.visible = logic.isRunning
        
        if logic.last_image:
            jetson_image.src = logic.last_image
            jetson_image.visible = True
            image_placeholder.visible = False
        else:
            jetson_image.visible = False
            image_placeholder.visible = True
            
        page.update()

    # Wire the UI functions to the Logic engine
    logic.on_log_update = refresh_logs_ui
    logic.on_grid_update = refresh_grid_ui
    logic.on_status_update = refresh_status_ui

    def handle_start_click(e):
        threading.Thread(target=logic.run_sequence, daemon=True).start()

    def handle_stop_click(e):
        logic.stop_sequence()

    btn_start.on_click = handle_start_click
    btn_stop.on_click = handle_stop_click

    # --- DASHBOARD VIEW ---
    dashboard_view = ft.Row([
        ft.Column([
            ft.Row([
                ft.Text("GANTRY VISUALIZER", size=12, weight="bold", color=TEXT_MUTED),
                ft.Row([
                    ft.Text("Rows:", size=12, color=TEXT_MUTED),
                    ft.TextField(value=str(logic.grid_rows), width=50, height=30, text_size=12, on_change=lambda e: logic.update_grid_size(int(e.control.value or 1), logic.grid_cols)),
                    ft.Text("Cols:", size=12, color=TEXT_MUTED),
                    ft.TextField(value=str(logic.grid_cols), width=50, height=30, text_size=12, on_change=lambda e: logic.update_grid_size(logic.grid_rows, int(e.control.value or 1))),
                ], spacing=10)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(content=grid_display, expand=True),
            ft.Row([btn_start, btn_stop], spacing=10),
        ], expand=2),
        ft.VerticalDivider(width=1, color=BORDER),
        ft.Column([
            ft.Text("JETSON FEED", size=12, weight="bold", color=TEXT_MUTED),
            ft.Stack([image_placeholder, jetson_image]),
            ft.Divider(height=20, color="transparent"),
            ft.Text("SYSTEM LOGS", size=12, weight="bold", color=TEXT_MUTED),
            ft.Container(content=log_column, expand=True, bgcolor="black", padding=10, border_radius=8),
        ], expand=1)
    ], expand=True)

    # --- DEBUG VIEW ---
    def create_device_control(name):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(name.upper(), weight="bold"),
                    ft.Switch(
                        label="Dummy Mode", 
                        value=logic.device_modes[name] == "dummy",
                        on_change=lambda e: logic.set_device_mode(name, "dummy" if e.control.value else "real"),
                        active_color=ACCENT
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Button("Manual Trigger 1", on_click=lambda _: logic.write_hardware(name, b"CMD1\n")),
                    ft.Button("Manual Trigger 2", on_click=lambda _: logic.write_hardware(name, b"CMD2\n")),
                ], spacing=10)
            ]),
            padding=15,
            bgcolor=BG_CARD,
            border_radius=10,
            border=ft.Border.all(1, BORDER)
        )

    debug_view = ft.ListView(
        expand=True,
        spacing=20,
        padding=20,
        controls=[
            ft.Text("HARDWARE MANUAL OVERRIDE", size=20, weight="bold"),
            ft.Row([
                create_device_control("gantry"),
                create_device_control("stirrer"),
            ], spacing=20),
            ft.Row([
                create_device_control("scoop"),
                create_device_control("jetson"),
            ], spacing=20),
            ft.Divider(color=BORDER),
            ft.Text("DUMMY RESPONSE SETTINGS", size=16, weight="bold"),
            ft.Row([
                ft.Column([
                    ft.Text("Move Time (s):", size=12, color=TEXT_MUTED),
                    ft.Slider(min=0.1, max=5.0, value=logic.dummy_responses["move_time"], on_change=lambda e: logic.dummy_responses.update({"move_time": e.control.value})),
                ], expand=1),
                ft.Column([
                    ft.Text("Analyze Time (s):", size=12, color=TEXT_MUTED),
                    ft.Slider(min=0.1, max=10.0, value=logic.dummy_responses["analyze_time"], on_change=lambda e: logic.dummy_responses.update({"analyze_time": e.control.value})),
                ], expand=1),
            ]),
            ft.Text("Mock Soil Types (comma separated):", size=12, color=TEXT_MUTED),
            ft.TextField(
                value=", ".join(logic.dummy_responses["soil_types"]),
                on_change=lambda e: logic.dummy_responses.update({"soil_types": [s.strip() for s in e.control.value.split(",")]})
            )
        ]
    )

    # --- TAB SYSTEM ---
    tab_system = ft.Tabs(
        selected_index=0,
        length=2,
        expand=True,
        content=ft.Column([
            ft.TabBar(
                tabs=[
                    ft.Tab(label="Dashboard", icon=ft.Icons.DASHBOARD),
                    ft.Tab(label="Manual Debug", icon=ft.Icons.HANDYMAN),
                ]
            ),
            ft.TabBarView(
                expand=True,
                controls=[
                    dashboard_view, 
                    debug_view
                ]
            )
        ])
    )

    # --- HEADER ---
    header = ft.Row([
        ft.Row([
            ft.Icon(ft.Icons.PRECISION_MANUFACTURING, color=ACCENT, size=30),
            ft.Text("SoilSense v6.0", size=24, weight="bold", color="white"),
        ]),
        ft.Row([
            ft.Row([status_indicators["gantry"], ft.Text("Gantry", size=10, color=TEXT_MUTED)], spacing=5),
            ft.Row([status_indicators["stirrer"], ft.Text("Stirrer", size=10, color=TEXT_MUTED)], spacing=5),
            ft.Row([status_indicators["scoop"], ft.Text("Scoop", size=10, color=TEXT_MUTED)], spacing=5),
            ft.Row([status_indicators["jetson"], ft.Text("Jetson", size=10, color=TEXT_MUTED)], spacing=5),
        ], spacing=20)
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # --- FINAL PAGE ADD ---
    page.add(
        header,
        ft.Divider(height=10, color=BORDER),
        tab_system
    )

    # Initial Render
    refresh_grid_ui()
    refresh_logs_ui()
    refresh_status_ui()

if __name__ == "__main__":
    ft.run(main)
