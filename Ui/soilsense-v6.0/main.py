import flet as ft
import threading
import platform
from hardware_logic import SoilSenseLogic, DeviceStatus

def main(page: ft.Page):
    page.title = "SoilSense v6.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#151619"

    # Target Raspberry Pi Display Resolution (Update to match your exact screen)
    PI_WIDTH = 1920
    PI_HEIGHT = 1200

    # Kiosk Mode Lock on Pi, fixed window size on macOS
    if platform.system() == "Darwin":  # "Darwin" is macOS
        SCALE = 0.5  # Scale down to 50% for Mac to fit the screen
        page.window.width = int(PI_WIDTH * SCALE)
        page.window.height = int(PI_HEIGHT * SCALE)
        page.window.full_screen = False
        page.window.resizable = False  # Lock resizing to mimic a fixed physical screen
    else:
        SCALE = 1.0
        page.window.full_screen = True

    page.padding = int(40 * SCALE)  # Increased padding from edges

    logic = SoilSenseLogic()

    # --- UI STYLING & TOUCHSCREEN SCALING ---
    ACCENT = "#00ff41"
    BG_CARD = "#1c1e22"
    BORDER = "#2c2e33"
    TEXT_MUTED = "#8e9299"

    # Fat-Finger Sizing Variables (Tweak these if it's too big/small)
    TXT_TINY = int(18 * SCALE)
    TXT_MED = int(24 * SCALE)
    TXT_LARGE = int(36 * SCALE)
    ICON_LG = int(48 * SCALE)
    BTN_HEIGHT = int(80 * SCALE) 
    GRID_SIZE = int(180 * SCALE) # Size of the gantry grid cells

    # --- BUTTON CLICK HANDLERS ---
    def handle_start_click(e):
        threading.Thread(target=logic.run_sequence, daemon=True).start()

    def handle_stop_click(e):
        logic.stop_sequence()

    async def handle_exit_click(e):
        print("[DEBUG] Shutting down Flet frontend...")
        await page.window.close()

    # --- HELPER WIDGETS ---
    def create_stepper(label, current_val, on_change, step=1, min_val=1, is_float=False, vertical=False):
        val_text = ft.Text(str(current_val), size=TXT_MED, weight="bold")
        
        def handle_click(delta):
            def _click(e):
                current = float(val_text.value) if is_float else int(val_text.value)
                new_val = max(min_val, current + delta)
                if is_float: 
                    new_val = round(new_val, 1)
                else:
                    new_val = int(new_val)
                    
                val_text.value = str(new_val)
                val_text.update()
                on_change(new_val)
            return _click

        stepper_controls = ft.Row([
            ft.IconButton(ft.Icons.REMOVE, on_click=handle_click(-step), icon_size=int(24 * SCALE), icon_color="white", bgcolor=BORDER),
            # Changed back to all-lowercase 'center'
            ft.Container(val_text, width=int(60 * SCALE), alignment=ft.Alignment.CENTER),
            ft.IconButton(ft.Icons.ADD, on_click=handle_click(step), icon_size=int(24 * SCALE), icon_color="white", bgcolor=BORDER),
        ], spacing=int(5 * SCALE))

        if vertical:
            return ft.Column([ft.Text(label, size=TXT_TINY, color=TEXT_MUTED), stepper_controls], spacing=int(5 * SCALE), expand=1)
        else:
            return ft.Row([ft.Text(label, size=TXT_MED, color=TEXT_MUTED), stepper_controls], spacing=int(10 * SCALE))
    # --- UI COMPONENTS ---
    # Added auto_scroll=True so Flet handles this natively
    log_column = ft.Column([], scroll=ft.ScrollMode.ALWAYS, auto_scroll=True, expand=True)
    
    # Changed from GridView to Column to allow dynamic vertical shrinking
    grid_display = ft.Column(expand=True, spacing=int(15 * SCALE))
    
    jetson_image = ft.Image(
        src="https://picsum.photos/seed/soil/400/300",
        width=int(400 * SCALE), height=int(300 * SCALE), fit=ft.BoxFit.CONTAIN, border_radius=int(12 * SCALE), visible=False
    )
    
    image_placeholder = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=int(80 * SCALE), color=TEXT_MUTED),
            ft.Text("No Image Data", size=TXT_MED, color=TEXT_MUTED)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=int(400 * SCALE), height=int(300 * SCALE), bgcolor="black", border_radius=int(12 * SCALE), border=ft.Border.all(2, BORDER)
    )

    btn_style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=int(12 * SCALE)), 
        text_style=ft.TextStyle(size=TXT_MED, weight="bold")
    )

    btn_start = ft.Button("START GRID ANALYSIS", icon=ft.Icons.PLAY_ARROW, bgcolor=ACCENT, color="black", height=BTN_HEIGHT, on_click=handle_start_click, style=btn_style)
    btn_stop = ft.Button("STOP", icon=ft.Icons.STOP, bgcolor="#ff4444", color="white", height=BTN_HEIGHT, on_click=handle_stop_click, style=btn_style, visible=False)

    # Door Status Dots (Default: Open = Red)
    door_indicators = {
        "left": ft.Container(width=int(24 * SCALE), height=int(24 * SCALE), border_radius=int(12 * SCALE)),
        "right": ft.Container(width=int(24 * SCALE), height=int(24 * SCALE), border_radius=int(12 * SCALE))
    }

    # Fat Status Dots
    status_indicators = {
        "gantry": ft.Container(width=int(24 * SCALE), height=int(24 * SCALE), border_radius=int(12 * SCALE)),
        "stirrer": ft.Container(width=int(24 * SCALE), height=int(24 * SCALE), border_radius=int(12 * SCALE)),
        "scoop": ft.Container(width=int(24 * SCALE), height=int(24 * SCALE), border_radius=int(12 * SCALE)),
        "jetson": ft.Container(width=int(24 * SCALE), height=int(24 * SCALE), border_radius=int(12 * SCALE))
    }

    grid_cells = {}
    def build_grid_structure():
        grid_display.controls.clear()
        grid_cells.clear()
        
        for r in range(logic.grid_rows):
            row_controls = []
            for c in range(logic.grid_cols):
                txt_res = ft.Text("-", color="white", weight="bold", size=TXT_LARGE)
                container = ft.Container(
                    expand=True, # Forces cells to share horizontal space evenly
                    content=ft.Column([ft.Text(f"{r},{c}", size=TXT_TINY, color=TEXT_MUTED), txt_res], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment.CENTER, bgcolor=BG_CARD, border=ft.Border.all(2, BORDER), border_radius=int(12 * SCALE),
                )
                grid_cells[(r, c)] = {"box": container, "txt": txt_res}
                row_controls.append(container)
            
            # Add the row to the display, expand=True forces rows to share vertical space evenly
            grid_display.controls.append(ft.Row(row_controls, expand=True, spacing=int(15 * SCALE)))

    build_grid_structure()

    # --- THE PUBSUB MAGIC ---
    def handle_pubsub_message(message):
        if message == "refresh":
            # Check if the number of logs has changed to trigger a rebuild and scroll
            if len(log_column.controls) != len(logic.logs):
                log_column.controls = [
                    ft.Text(line, size=TXT_TINY, color=TEXT_MUTED, font_family="monospace", selectable=True) for line in logic.logs
                ]
                log_column.scroll_to(offset=-1, duration=300)

            # --- Status Indicators (Gantry, Stirrer, etc.) ---
            for device, indicator in status_indicators.items():
                status = logic.statuses[device]
                indicator.border = ft.Border.all(int(2 * SCALE), status.value)
                indicator.bgcolor = BG_CARD # Hollow appearance

            # --- Door Indicators ---
            door_overall_status = logic.statuses["doors"]
            if door_overall_status == DeviceStatus.OFFLINE:
                # Not detected: Red ring, hollow inside
                for indicator in door_indicators.values():
                    indicator.border = ft.Border.all(int(2 * SCALE), DeviceStatus.OFFLINE.value)
                    indicator.bgcolor = BG_CARD
            elif door_overall_status == DeviceStatus.DUMMY:
                # Dummy mode: Yellow ring, inner color for state
                for door, indicator in door_indicators.items():
                    indicator.border = ft.Border.all(int(2 * SCALE), DeviceStatus.DUMMY.value)
                    indicator.bgcolor = logic.door_statuses[door].value
            else: # ONLINE (Real mode, detected)
                for door, indicator in door_indicators.items():
                    door_state = logic.door_statuses[door]
                    
                    # Always show a green outline to indicate the connection is active
                    indicator.border = ft.Border.all(int(2 * SCALE), DeviceStatus.ONLINE.value)
                    
                    # Red fill for Open (OFFLINE), Green fill for Closed (ONLINE)
                    if door_state == DeviceStatus.OFFLINE:
                        indicator.bgcolor = DeviceStatus.OFFLINE.value
                    else:
                        indicator.bgcolor = DeviceStatus.ONLINE.value
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

            # Update visibility of door toggle buttons in debug view
            door_toggle_row.visible = logic.device_modes["doors"] == "dummy"

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
                    # Replaced TextFields with Steppers
                    create_stepper("Rows:", logic.grid_rows, lambda v: logic.update_grid_size(v, logic.grid_cols), step=1, min_val=1),
                    create_stepper("Cols:", logic.grid_cols, lambda v: logic.update_grid_size(logic.grid_rows, v), step=1, min_val=1),
                ], spacing=int(15 * SCALE))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(content=grid_display, expand=True),
            ft.Row([btn_start, btn_stop], spacing=int(20 * SCALE)),
        ], expand=2),
        ft.VerticalDivider(width=2, color=BORDER),
        ft.Column([
            ft.Text("JETSON FEED", size=TXT_MED, weight="bold", color=TEXT_MUTED),
            ft.Stack([image_placeholder, jetson_image]),
            ft.Divider(height=int(20 * SCALE), color="transparent"),
            ft.Text("SYSTEM LOGS", size=TXT_MED, weight="bold", color=TEXT_MUTED),
            ft.Container(content=log_column, expand=True, bgcolor="black", padding=int(20 * SCALE), border_radius=int(12 * SCALE)),
        ], expand=1)
    ], expand=True)

    # --- DEBUG VIEW ---
    # Create controls that need to be updated dynamically
    door_toggle_row = ft.Row(visible=False, spacing=int(20 * SCALE))

    def create_device_control(name):
        is_mac_and_doors = platform.system() == "Darwin" and name == "doors"

        dummy_switch = ft.Switch(
            label="Dummy Mode",
            value=logic.device_modes[name] == "dummy",
            scale=1.5 * SCALE,
            on_change=lambda e: logic.set_device_mode(name, "dummy" if e.control.value else "real"),
            active_color=ACCENT,
            disabled=is_mac_and_doors
        )

        content_rows = [
            ft.Row([
                # Changed from TXT_MED to TXT_TINY to make the names smaller
                ft.Text(name.upper(), size=TXT_TINY, weight="bold"),
                dummy_switch,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]

        if name == "doors":
            door_toggle_row.controls.clear() 
            door_toggle_row.controls.extend([
                ft.Button("Toggle Left", height=int(60 * SCALE), on_click=lambda _: logic.toggle_dummy_door("left"), style=ft.ButtonStyle(text_style=ft.TextStyle(size=TXT_TINY))),
                ft.Button("Toggle Right", height=int(60 * SCALE), on_click=lambda _: logic.toggle_dummy_door("right"), style=ft.ButtonStyle(text_style=ft.TextStyle(size=TXT_TINY))),
            ])
            content_rows.append(door_toggle_row)
        else:
            content_rows.append(
                ft.Row([
                    ft.Button("Trigger 1", height=int(60 * SCALE), on_click=lambda _: logic.write_hardware(name, b"CMD1\n"), style=ft.ButtonStyle(text_style=ft.TextStyle(size=TXT_TINY))),
                    ft.Button("Trigger 2", height=int(60 * SCALE), on_click=lambda _: logic.write_hardware(name, b"CMD2\n"), style=ft.ButtonStyle(text_style=ft.TextStyle(size=TXT_TINY))),
                ], spacing=int(10 * SCALE)) # Reduced spacing
            )

        return ft.Container(
            content=ft.Column(content_rows, spacing=int(10 * SCALE)), # Reduced spacing
            padding=int(15 * SCALE), bgcolor=BG_CARD, border_radius=int(12 * SCALE), border=ft.Border.all(2, BORDER),
            expand=True # Added expand=True so they share row width perfectly
        )
    debug_view = ft.ListView(
        # Reduced overall spacing and padding to fit more vertically
        expand=True, spacing=int(15 * SCALE), padding=int(20 * SCALE),
        controls=[
            ft.Text("HARDWARE MANUAL OVERRIDE", size=TXT_MED, weight="bold"), # Shrunk header slightly
            
            # Grouped 3 devices into the first row
            ft.Row([
                create_device_control("gantry"), 
                create_device_control("stirrer"),
                create_device_control("scoop")
            ], spacing=int(15 * SCALE)),            
            # Grouped the remaining 2 devices into the second row
            ft.Row([
                create_device_control("jetson"),
                create_device_control("doors")
            ], spacing=int(15 * SCALE)),
            
            ft.Divider(color=BORDER),
            ft.Text("DUMMY RESPONSE SETTINGS", size=TXT_MED, weight="bold"),
            
            # Replaced TextFields with vertical Steppers
            ft.Row([
                create_stepper("Move Time (s):", logic.dummy_responses["move_time"], lambda v: logic.dummy_responses.update({"move_time": v}), step=0.5, min_val=0.0, is_float=True, vertical=True),
                create_stepper("Analyze Time (s):", logic.dummy_responses["analyze_time"], lambda v: logic.dummy_responses.update({"analyze_time": v}), step=0.5, min_val=0.0, is_float=True, vertical=True),
            ], spacing=int(15 * SCALE)),
            
            ft.Text("Mock Soil Types (comma separated):", size=TXT_TINY, color=TEXT_MUTED),
            ft.TextField(value=", ".join(logic.dummy_responses["soil_types"]), height=int(60 * SCALE), text_size=TXT_MED, on_change=lambda e: logic.dummy_responses.update({"soil_types": [s.strip() for s in e.control.value.split(",")]})),
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
            ft.Row([door_indicators["left"], ft.Text("Left Door", size=TXT_TINY, color=TEXT_MUTED)], spacing=int(10 * SCALE)),
            ft.Row([door_indicators["right"], ft.Text("Right Door", size=TXT_TINY, color=TEXT_MUTED)], spacing=int(10 * SCALE)),
            ft.Row([status_indicators["gantry"], ft.Text("Gantry", size=TXT_TINY, color=TEXT_MUTED)], spacing=int(10 * SCALE)),
            ft.Row([status_indicators["stirrer"], ft.Text("Stirrer", size=TXT_TINY, color=TEXT_MUTED)], spacing=int(10 * SCALE)),
            ft.Row([status_indicators["scoop"], ft.Text("Scoop", size=TXT_TINY, color=TEXT_MUTED)], spacing=int(10 * SCALE)),
            ft.Row([status_indicators["jetson"], ft.Text("Jetson", size=TXT_TINY, color=TEXT_MUTED)], spacing=int(10 * SCALE)),
        ], spacing=int(30 * SCALE))
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # --- FINAL PAGE ADD ---
    page.add(header, ft.Divider(height=int(10 * SCALE), color=BORDER), tab_system)
    
    handle_pubsub_message("refresh")

if __name__ == "__main__":
    ft.run(main, assets_dir="images")