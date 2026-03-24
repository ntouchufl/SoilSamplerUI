import flet as ft
import threading
from hardware_logic import SoilSenseLogic, DeviceStatus

def main(page: ft.Page):
    page.title = "SoilSense v6.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#151619"
    page.padding = 40  # Increased padding from edges

    # Kiosk Mode Lock
    page.window.full_screen = True 

    logic = SoilSenseLogic()

    # --- UI STYLING & TOUCHSCREEN SCALING ---
    ACCENT = "#00ff41"
    BG_CARD = "#1c1e22"
    BORDER = "#2c2e33"
    TEXT_MUTED = "#8e9299"

    # Fat-Finger Sizing Variables (Tweak these if it's too big/small)
    TXT_TINY = 18
    TXT_MED = 24
    TXT_LARGE = 36
    ICON_LG = 48
    BTN_HEIGHT = 80
    GRID_SIZE = 300 # Makes the gantry boxes massive

    # --- BUTTON CLICK HANDLERS ---
    def handle_start_click(e):
        threading.Thread(target=logic.run_sequence, daemon=True).start()

    def handle_stop_click(e):
        logic.stop_sequence()

    async def handle_exit_click(e):
        print("[DEBUG] Shutting down Flet frontend...")
        await page.window.close()

    # --- UI COMPONENTS ---
    log_text = ft.Text(value="", size=TXT_MED, color=TEXT_MUTED, font_family="monospace")
    log_column = ft.Column([log_text], scroll=ft.ScrollMode.ALWAYS, expand=True)
    
    grid_display = ft.GridView(expand=True, runs_count=3, max_extent=GRID_SIZE, spacing=15, run_spacing=15)
    
    jetson_image = ft.Image(
        src="https://picsum.photos/seed/soil/600/450",
        width=600, height=450, fit=ft.BoxFit.CONTAIN, border_radius=12, visible=False
    )
    
    image_placeholder = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=100, color=TEXT_MUTED),
            ft.Text("No Image Data", size=TXT_MED, color=TEXT_MUTED)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=600, height=450, bgcolor="black", border_radius=12, border=ft.Border.all(2, BORDER)
    )

    btn_style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=12), 
        text_style=ft.TextStyle(size=TXT_MED, weight="bold")
    )

    btn_start = ft.Button("START GRID ANALYSIS", icon=ft.Icons.PLAY_ARROW, bgcolor=ACCENT, color="black", height=BTN_HEIGHT, on_click=handle_start_click, style=btn_style)
    btn_stop = ft.Button("STOP", icon=ft.Icons.STOP, bgcolor="#ff4444", color="white", height=BTN_HEIGHT, on_click=handle_stop_click, style=btn_style, visible=False)

    # Fat Status Dots
    status_indicators = {
        "gantry": ft.Container(width=24, height=24, border_radius=12, bgcolor=DeviceStatus.OFFLINE.value),
        "stirrer": ft.Container(width=24, height=24, border_radius=12, bgcolor=DeviceStatus.OFFLINE.value),
        "scoop": ft.Container(width=24, height=24, border_radius=12, bgcolor=DeviceStatus.OFFLINE.value),
        "jetson": ft.Container(width=24, height=24, border_radius=12, bgcolor=DeviceStatus.OFFLINE.value)
    }

    grid_cells = {}
    def build_grid_structure():
        grid_display.controls.clear()
        grid_cells.clear()
        grid_display.runs_count = logic.grid_cols
        for r in range(logic.grid_rows):
            for c in range(logic.grid_cols):
                txt_res = ft.Text("-", color="white", weight="bold", size=TXT_LARGE)
                container = ft.Container(
                    content=ft.Column([ft.Text(f"{r},{c}", size=TXT_TINY, color=TEXT_MUTED), txt_res], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment.CENTER, bgcolor=BG_CARD, border=ft.Border.all(2, BORDER), border_radius=12,
                )
                grid_cells[(r, c)] = {"box": container, "txt": txt_res}
                grid_display.controls.append(container)

    build_grid_structure()

    # --- THE PUBSUB MAGIC ---
    def handle_pubsub_message(message):
        if message == "refresh":
            log_text.value = "\n".join(logic.logs)

            for device, indicator in status_indicators.items():
                indicator.bgcolor = logic.statuses[device].value

            if len(grid_cells) != (logic.grid_rows * logic.grid_cols):
                build_grid_structure()

            for r in range(logic.grid_rows):
                for c in range(logic.grid_cols):
                    cell = grid_cells.get((r, c))
                    if not cell: continue
                    res = logic.soil_results.get((r, c))
                    is_active = logic.isRunning and logic.currentRow == r and logic.currentCol == c
                    
                    cell["txt"].value = res if res else "-"
                    cell["txt"].color = "black" if is_active else (ACCENT if res else "white")
                    cell["box"].bgcolor = ACCENT if is_active else BG_CARD
                    cell["box"].border = ft.Border.all(2, ACCENT if is_active or res else BORDER)

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

    page.pubsub.subscribe(handle_pubsub_message)
    logic.on_log_update = lambda: page.pubsub.send_all("refresh")
    logic.on_grid_update = lambda: page.pubsub.send_all("refresh")
    logic.on_status_update = lambda: page.pubsub.send_all("refresh")

    # --- DASHBOARD VIEW ---
    dashboard_view = ft.Row([
        ft.Column([
            ft.Row([
                ft.Text("GANTRY VISUALIZER", size=TXT_MED, weight="bold", color=TEXT_MUTED),
                ft.Row([
                    ft.Text("Rows:", size=TXT_MED, color=TEXT_MUTED),
                    ft.TextField(value=str(logic.grid_rows), width=80, height=60, text_size=TXT_MED, content_padding=10, on_change=lambda e: logic.update_grid_size(int(e.control.value or 1), logic.grid_cols)),
                    ft.Text("Cols:", size=TXT_MED, color=TEXT_MUTED),
                    ft.TextField(value=str(logic.grid_cols), width=80, height=60, text_size=TXT_MED, content_padding=10, on_change=lambda e: logic.update_grid_size(logic.grid_rows, int(e.control.value or 1))),
                ], spacing=15)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(content=grid_display, expand=True),
            ft.Row([btn_start, btn_stop], spacing=20),
        ], expand=2),
        ft.VerticalDivider(width=2, color=BORDER),
        ft.Column([
            ft.Text("JETSON FEED", size=TXT_MED, weight="bold", color=TEXT_MUTED),
            ft.Stack([image_placeholder, jetson_image]),
            ft.Divider(height=20, color="transparent"),
            ft.Text("SYSTEM LOGS", size=TXT_MED, weight="bold", color=TEXT_MUTED),
            ft.Container(content=log_column, expand=True, bgcolor="black", padding=20, border_radius=12),
        ], expand=1)
    ], expand=True)

    # --- DEBUG VIEW ---
    def create_device_control(name):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(name.upper(), size=TXT_MED, weight="bold"),
                    ft.Switch(label="Dummy Mode", value=logic.device_modes[name] == "dummy", scale=1.5, on_change=lambda e: logic.set_device_mode(name, "dummy" if e.control.value else "real"), active_color=ACCENT),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Button("Trigger 1", height=60, on_click=lambda _: logic.write_hardware(name, b"CMD1\n"), style=ft.ButtonStyle(text_style=ft.TextStyle(size=TXT_TINY))),
                    ft.Button("Trigger 2", height=60, on_click=lambda _: logic.write_hardware(name, b"CMD2\n"), style=ft.ButtonStyle(text_style=ft.TextStyle(size=TXT_TINY))),
                ], spacing=20)
            ], spacing=20),
            padding=25, bgcolor=BG_CARD, border_radius=12, border=ft.Border.all(2, BORDER)
        )

    debug_view = ft.ListView(
        expand=True, spacing=30, padding=30,
        controls=[
            ft.Text("HARDWARE MANUAL OVERRIDE", size=TXT_LARGE, weight="bold"),
            ft.Row([create_device_control("gantry"), create_device_control("stirrer")], spacing=30),
            ft.Row([create_device_control("scoop"), create_device_control("jetson")], spacing=30),
            ft.Divider(color=BORDER),
            ft.Text("DUMMY RESPONSE SETTINGS", size=TXT_MED, weight="bold"),
            ft.Row([
                ft.Column([
                    ft.Text("Move Time (s):", size=TXT_MED, color=TEXT_MUTED),
                    ft.TextField(value=str(logic.dummy_responses["move_time"]), height=60, text_size=TXT_MED, input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9.]*$"), on_change=lambda e: logic.dummy_responses.update({"move_time": float(e.control.value) if e.control.value else 0.0})),
                ], expand=1),
                ft.Column([
                    ft.Text("Analyze Time (s):", size=TXT_MED, color=TEXT_MUTED),
                    ft.TextField(value=str(logic.dummy_responses["analyze_time"]), height=60, text_size=TXT_MED, input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9.]*$"), on_change=lambda e: logic.dummy_responses.update({"analyze_time": float(e.control.value) if e.control.value else 0.0})),
                ], expand=1),
            ], spacing=30),
            ft.Text("Mock Soil Types (comma separated):", size=TXT_MED, color=TEXT_MUTED),
            ft.TextField(value=", ".join(logic.dummy_responses["soil_types"]), height=60, text_size=TXT_MED, on_change=lambda e: logic.dummy_responses.update({"soil_types": [s.strip() for s in e.control.value.split(",")]})),
            ft.Divider(color=BORDER),
            ft.Button("EXIT TO DESKTOP", icon=ft.Icons.POWER_SETTINGS_NEW, bgcolor="#ff4444", color="white", height=BTN_HEIGHT, on_click=handle_exit_click, style=btn_style)
        ]
    )

    # --- TAB SYSTEM ---
    tab_system = ft.Tabs(
        selected_index=0, length=2, expand=True,
        content=ft.Column([
            ft.TabBar(
                # The styling moved here!
                tab_alignment=ft.TabAlignment.START,
                label_text_style=ft.TextStyle(size=TXT_MED, weight="bold"),
                tabs=[
                    ft.Tab(label="Dashboard", icon=ft.Icons.DASHBOARD), 
                    ft.Tab(label="Manual Debug", icon=ft.Icons.HANDYMAN)
                ]
            ),
            ft.TabBarView(expand=True, controls=[dashboard_view, debug_view])
        ])
    )

    # --- HEADER ---
    header = ft.Row([
        ft.Row([ft.Icon(ft.Icons.PRECISION_MANUFACTURING, color=ACCENT, size=ICON_LG), ft.Text("SoilSense v6.0", size=TXT_LARGE, weight="bold", color="white")]),
        ft.Row([
            ft.Row([status_indicators["gantry"], ft.Text("Gantry", size=TXT_TINY, color=TEXT_MUTED)], spacing=10),
            ft.Row([status_indicators["stirrer"], ft.Text("Stirrer", size=TXT_TINY, color=TEXT_MUTED)], spacing=10),
            ft.Row([status_indicators["scoop"], ft.Text("Scoop", size=TXT_TINY, color=TEXT_MUTED)], spacing=10),
            ft.Row([status_indicators["jetson"], ft.Text("Jetson", size=TXT_TINY, color=TEXT_MUTED)], spacing=10),
        ], spacing=30)
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # --- FINAL PAGE ADD ---
    page.add(header, ft.Divider(height=10, color=BORDER), tab_system)
    
    handle_pubsub_message("refresh")

if __name__ == "__main__":
    ft.run(main)