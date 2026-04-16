import flet as ft
import threading
import platform
import base64
import urllib.request
import time
from hardware_logic import SoilSenseLogic, DeviceStatus
import requests

def main(page: ft.Page):
    page.title = "SoilSense v7.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#151619"

    # Screen Scaling
    PI_WIDTH, PI_HEIGHT = 1920, 1200
    if platform.system() == "Darwin":
        SCALE = 0.5
        page.window.width, page.window.height = int(PI_WIDTH * SCALE), int(PI_HEIGHT * SCALE)
        page.window.full_screen = False
        page.window.resizable = False  # Keep this locked for Mac testing
    else:
        SCALE = 1.0
        page.window.full_screen = True
        # Notice resizable is removed here so the Pi can expand!

    logic = SoilSenseLogic()
    
    # UI State Tracker for Hardware Safety Interlocks
    ui_state = {"gantry_zeroed": False}

    # Styling
    ACCENT = "#00ff41"
    BG_CARD = "#1c1e22"
    BORDER = "#2c2e33"
    TEXT_MUTED = "#8e9299"
    TXT_TINY, TXT_MED, TXT_LARGE = int(18*SCALE), int(24*SCALE), int(36*SCALE)
    ICON_LG = int(48*SCALE)
    BTN_HEIGHT = int(80*SCALE)

    # --- BUTTON CLICK HANDLERS ---
    def handle_start_click(e):
        threading.Thread(target=logic.run_sequence, daemon=True).start()

    def handle_stop_click(e):
        logic.stop_sequence()
        # Revoke the zeroed status on stop/e-stop
        ui_state["gantry_zeroed"] = False 
        page.pubsub.send_all("refresh")

    def handle_export_click(e):
        logic.export_results_csv()

    def handle_zero_gantry_click(e):
        logic.zero_gantry()
        # Grant the zeroed status and unlock system
        ui_state["gantry_zeroed"] = True
        page.pubsub.send_all("refresh")

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
            ft.Container(val_text, width=int(60 * SCALE), alignment=ft.Alignment.CENTER),
            ft.IconButton(ft.Icons.ADD, on_click=handle_click(step), icon_size=int(24 * SCALE), icon_color="white", bgcolor=BORDER),
        ], spacing=int(5 * SCALE))

        if vertical:
            return ft.Column([ft.Text(label, size=TXT_TINY, color=TEXT_MUTED), stepper_controls], spacing=int(5 * SCALE), expand=1)
        else:
            return ft.Row([ft.Text(label, size=TXT_MED, color=TEXT_MUTED), stepper_controls], spacing=int(10 * SCALE))

    # --- SAMPLES KEYPAD DIALOG ---
    sample_input = ft.Text("0", size=TXT_LARGE, weight="bold")
    
    def handle_keypad_click(val):
        def _click(e):
            if val == "C": 
                sample_input.value = "0"
            elif val == "OK":
                final_val = int(sample_input.value)
                if final_val > 40:
                    final_val = 40
                logic.update_samples(final_val)
                keypad_dialog.open = False
            else:
                if sample_input.value == "0": 
                    sample_input.value = str(val)
                else:
                    new_val_str = sample_input.value + str(val)
                    if int(new_val_str) > 40:
                        sample_input.value = "40"
                    else:
                        sample_input.value = new_val_str
            page.update()
        return _click

    def create_kp_btn(text_val, text_color="white", bgcolor=BORDER):
        return ft.Container(
            content=ft.Text(text_val, size=TXT_MED, weight="bold", color=text_color, text_align=ft.TextAlign.CENTER), 
            alignment=ft.Alignment.CENTER,
            on_click=handle_keypad_click(text_val), 
            width=int(100*SCALE), height=int(90*SCALE), 
            bgcolor=bgcolor, 
            border_radius=int(8*SCALE),
            ink=True
        )

    kp_spacing = int(15*SCALE)
    keypad_rows = [
        ft.Row([create_kp_btn("1"), create_kp_btn("2"), create_kp_btn("3")], alignment=ft.MainAxisAlignment.CENTER, spacing=kp_spacing),
        ft.Row([create_kp_btn("4"), create_kp_btn("5"), create_kp_btn("6")], alignment=ft.MainAxisAlignment.CENTER, spacing=kp_spacing),
        ft.Row([create_kp_btn("7"), create_kp_btn("8"), create_kp_btn("9")], alignment=ft.MainAxisAlignment.CENTER, spacing=kp_spacing),
        ft.Row([create_kp_btn("C", "white", "#ff4444"), create_kp_btn("0"), create_kp_btn("OK", "black", ACCENT)], alignment=ft.MainAxisAlignment.CENTER, spacing=kp_spacing),
    ]

    keypad_dialog = ft.AlertDialog(
        title=ft.Text("Enter Samples (Max 40)", size=TXT_MED, weight="bold"),
        content=ft.Container(
            width=int(450*SCALE), 
            content=ft.Column([
                ft.Container(sample_input, alignment=ft.Alignment.CENTER, padding=int(20*SCALE), bgcolor="black", border_radius=int(10*SCALE)),
                ft.Divider(height=int(15*SCALE), color="transparent"),
                *keypad_rows
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    )
    page.overlay.append(keypad_dialog)

    def open_samples_keypad(e):
        sample_input.value = str(logic.total_samples)
        keypad_dialog.open = True
        page.update()

    # --- WEIGHT MENU DIALOG ---
    custom_weight_input = ft.TextField(
        label="Custom (g)", 
        width=int(220*SCALE), 
        height=int(80*SCALE),
        text_size=TXT_MED,
        label_style=ft.TextStyle(size=TXT_TINY),
        text_align=ft.TextAlign.CENTER, 
        keyboard_type=ft.KeyboardType.NUMBER
    )

    def set_weight(w):
        logic.soil_weight = int(w)
        logic.log(f"Soil weight target set to {logic.soil_weight}g")
        weight_dialog.open = False
        page.pubsub.send_all("refresh")

    def handle_custom_weight(e):
        if custom_weight_input.value.isdigit():
            set_weight(custom_weight_input.value)

    def create_weight_btn(text_val, weight_val):
        return ft.Container(
            content=ft.Text(text_val, size=TXT_MED, weight="bold", color="white", text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment.CENTER,
            height=BTN_HEIGHT,
            bgcolor=BORDER,
            border_radius=int(8*SCALE),
            on_click=lambda e: set_weight(weight_val),
            ink=True
        )
    
    weight_dialog = ft.AlertDialog(
        title=ft.Text("Select Target Weight", size=TXT_LARGE, weight="bold"),
        content=ft.Container(
            width=int(500*SCALE),
            content=ft.Column([
                create_weight_btn("10g (Small)", 10),
                create_weight_btn("20g (Medium)", 20),
                create_weight_btn("30g (Large)", 30),
                ft.Divider(color=BORDER, height=int(20*SCALE)),
                ft.Row([
                    custom_weight_input,
                    ft.Container(
                        content=ft.Text("APPLY", size=TXT_MED, weight="bold", color="black", text_align=ft.TextAlign.CENTER),
                        alignment=ft.Alignment.CENTER,
                        height=int(80*SCALE),
                        bgcolor=ACCENT,
                        border_radius=int(8*SCALE),
                        on_click=handle_custom_weight,
                        ink=True,
                        expand=True
                    )
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=int(15*SCALE))
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH) 
        )
    )
    page.overlay.append(weight_dialog)

    def open_weight_menu(e):
        custom_weight_input.value = ""
        weight_dialog.open = True
        page.update()

    # --- UI COMPONENTS ---
    btn_style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=int(12 * SCALE)), 
        text_style=ft.TextStyle(size=TXT_MED, weight="bold")
    )
    
    btn_start = ft.Button("START", icon=ft.Icons.PLAY_ARROW, bgcolor=ACCENT, color="black", height=BTN_HEIGHT, on_click=handle_start_click, style=btn_style)
    btn_stop = ft.Button("STOP", icon=ft.Icons.STOP, bgcolor="#ff4444", color="white", height=BTN_HEIGHT, on_click=handle_stop_click, visible=False, style=btn_style)
    btn_export = ft.Button("EXPORT", icon=ft.Icons.SAVE_ALT, bgcolor="#3b82f6", color="white", height=BTN_HEIGHT, on_click=handle_export_click, style=btn_style)
    btn_samples = ft.Button("SAMPLES", icon=ft.Icons.KEYBOARD, bgcolor=BORDER, color="white", height=BTN_HEIGHT, on_click=open_samples_keypad, style=btn_style)
    btn_weight = ft.Button("WEIGHT", icon=ft.Icons.SCALE, bgcolor=BORDER, color="white", height=BTN_HEIGHT, on_click=open_weight_menu, style=btn_style)
    btn_zero_gantry = ft.Button("ZERO FIRST", icon=ft.Icons.HOME, bgcolor="#f59e0b", color="black", height=BTN_HEIGHT, on_click=handle_zero_gantry_click, style=btn_style)

    log_column = ft.ListView(expand=True, auto_scroll=True, spacing=int(5*SCALE))
    total_samples_text = ft.Text(f"Target: {logic.total_samples} samples | {logic.soil_weight}g", size=TXT_MED, color=TEXT_MUTED)

    # Status indicators
    door_indicators = {
        "left": ft.Container(width=int(24*SCALE), height=int(24*SCALE), border_radius=int(12*SCALE), bgcolor=DeviceStatus.OFFLINE.value),
        "right": ft.Container(width=int(24*SCALE), height=int(24*SCALE), border_radius=int(12*SCALE), bgcolor=DeviceStatus.OFFLINE.value)
    }
    status_indicators = {
        "gantry": ft.Container(width=int(24*SCALE), height=int(24*SCALE), border_radius=int(12*SCALE), bgcolor=DeviceStatus.OFFLINE.value),
        "stirrer": ft.Container(width=int(24*SCALE), height=int(24*SCALE), border_radius=int(12*SCALE), bgcolor=DeviceStatus.OFFLINE.value),
        "scoop": ft.Container(width=int(24*SCALE), height=int(24*SCALE), border_radius=int(12*SCALE), bgcolor=DeviceStatus.OFFLINE.value),
        "jetson": ft.Container(width=int(24*SCALE), height=int(24*SCALE), border_radius=int(12*SCALE), bgcolor=DeviceStatus.OFFLINE.value)
    }
    debug_view = ft.ListView(expand=True, spacing=int(15 * SCALE), padding=int(20 * SCALE))

    camera_view = ft.Image(
    src="R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
    width=int(400 * SCALE),
    height=int(300 * SCALE),
    fit=ft.ImageFit.CONTAIN,
)

    camera_view_container = ft.Container(
        content=camera_view,
        width=int(400 * SCALE),
        height=int(300 * SCALE),
        bgcolor=ft.colors.BLACK,
        border_radius=int(12 * SCALE),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,  # enforces the border radius on the image
    )
    start_camera_stream()
    
    # Swapped Column for ListView to fix the rendering bug
    soil_results_view = ft.ListView(expand=True, auto_scroll=True, spacing=int(5*SCALE))

    # --- ACTION HIGHLIGHTER LIST ---
    SCOOPER_STEPS = [
        "Idle", "Moving to Bag", "Stirring", "Analyzing", "Scooping",
        "Moving to Tube", "Dispensing", "Returning to Bag", "Emptying"
    ]

    step_indicators = {}
    for step in SCOOPER_STEPS:
        step_indicators[step] = ft.Container(
            content=ft.Text(step, size=TXT_TINY, weight="bold", color=TEXT_MUTED),
            padding=int(8*SCALE),
            border_radius=int(6*SCALE),
            bgcolor="transparent"
        )
        
    scooper_status_view = ft.Column(
        controls=list(step_indicators.values()),
        spacing=int(2*SCALE),
        scroll=ft.ScrollMode.ADAPTIVE
    )

    def handle_refresh(msg):
        if msg == "refresh":
            if len(log_column.controls) != len(logic.logs):
                log_column.controls = [ft.Text(l, size=TXT_TINY, color=TEXT_MUTED, font_family="monospace", selectable=True) for l in logic.logs]
                
            total_samples_text.value = f"Target: {logic.total_samples} samples | {logic.soil_weight}g"
            
            # Update indicators
            for device, indicator in status_indicators.items():
                indicator.bgcolor = logic.statuses[device].value
            
            door_indicators["left"].bgcolor = logic.door_statuses["left"].value
            door_indicators["right"].bgcolor = logic.door_statuses["right"].value

            # Safety Interlock & Visual Feedback Logic
            if logic.isRunning:
                btn_start.text = "RUNNING"
                btn_start.disabled = True
            elif not ui_state["gantry_zeroed"]:
                btn_start.text = "ZERO FIRST"
                btn_start.disabled = True
                btn_zero_gantry.bgcolor = "#f59e0b" # Bright amber warning
                btn_zero_gantry.color = "black"
            else:
                btn_start.text = "START"
                btn_start.disabled = False
                btn_zero_gantry.bgcolor = BORDER # Return to normal dark gray
                btn_zero_gantry.color = "white"

            btn_stop.visible = logic.isRunning
            btn_samples.disabled = logic.isRunning
            btn_weight.disabled = logic.isRunning
            debug_view.disabled = logic.isRunning

            door_toggle_row.visible = logic.device_modes["doors"] == "dummy"

            if logic.last_image:
                camera_view.src = logic.last_image
            
            if len(soil_results_view.controls) != len(logic.soil_results):soil_results_view.controls = [ft.Text(f"Sample {i+1}: {data.get('classification', 'N/A')}", size=TXT_TINY) for i, data in logic.soil_results.items()]

            
            # Update Step Highlighter
            for step, container in step_indicators.items():
                if logic.scooper_status == step:
                    container.bgcolor = ACCENT
                    container.content.color = "black"
                else:
                    container.bgcolor = "transparent"
                    container.content.color = TEXT_MUTED

            page.update()

    page.pubsub.subscribe(handle_refresh)
    logic.on_log_update = lambda: page.pubsub.send_all("refresh")
    logic.on_status_update = lambda: page.pubsub.send_all("refresh")
    logic.on_sequence_update = lambda: page.pubsub.send_all("refresh")

    dashboard = ft.Column([
        # TOP AREA: 3-Column Data Display
        ft.Row([
            # Left Column: Jetson Feed & Soil Results
            ft.Column([
                ft.Text("JETSON FEED", size=TXT_MED, weight="bold", color=TEXT_MUTED),
                camera_view,
                ft.Divider(height=int(20*SCALE), color="transparent"),
                ft.Text("SOIL RESULTS", size=TXT_MED, weight="bold", color=TEXT_MUTED),
                ft.Container(
                    content=soil_results_view, 
                    expand=True,
                    bgcolor=BG_CARD,
                    padding=int(15*SCALE),
                    border_radius=int(12*SCALE),
                    border=ft.border.all(2, BORDER)
                ),
            ], expand=1, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            
            # Middle Column: Scooper Status
            ft.Column([
                ft.Text("SCOOPER STATUS", size=TXT_MED, weight="bold", color=TEXT_MUTED),
                ft.Container(
                    content=scooper_status_view, 
                    expand=True, 
                    bgcolor=BG_CARD, 
                    padding=int(15*SCALE), 
                    border_radius=int(12*SCALE),
                    border=ft.border.all(2, BORDER)
                ),
            ], expand=1, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),

            # Right Column: System Logs 
            ft.Column([
                ft.Text("SYSTEM LOGS", size=TXT_MED, weight="bold", color=TEXT_MUTED),
                ft.Container(
                    content=log_column, 
                    expand=True, 
                    bgcolor="black", 
                    padding=int(20*SCALE), 
                    border_radius=int(12*SCALE),
                    border=ft.border.all(2, BORDER)
                ),
            ], expand=1, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        ], expand=True),

        # BOTTOM AREA: Full-Width Control Bar
        ft.Divider(height=int(20*SCALE), color=BORDER),
        ft.Row([
            total_samples_text,
            ft.Row([
                btn_zero_gantry, 
                btn_samples, 
                btn_weight, 
                btn_export, 
                btn_stop, 
                btn_start
            ], spacing=int(10*SCALE), run_spacing=int(10*SCALE), wrap=True) 
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    ], expand=True)

    # --- DEBUG VIEW ---
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
                    ft.Button("Trigger 1", height=int(60 * SCALE), on_click=lambda _: logic.write_hardware(name, b"CMD1"), style=ft.ButtonStyle(text_style=ft.TextStyle(size=TXT_TINY))),
                    ft.Button("Trigger 2", height=int(60 * SCALE), on_click=lambda _: logic.write_hardware(name, b"CMD2"), style=ft.ButtonStyle(text_style=ft.TextStyle(size=TXT_TINY))),
                ], spacing=int(10 * SCALE))
            )

        return ft.Container(
            content=ft.Column(content_rows, spacing=int(10 * SCALE)),
            padding=int(15 * SCALE), bgcolor=BG_CARD, border_radius=int(12 * SCALE), border=ft.Border.all(2, BORDER),
            expand=True
        )
        
    debug_view.controls=[
            ft.Text("HARDWARE MANUAL OVERRIDE", size=TXT_MED, weight="bold"),
            
            ft.Row([
                create_device_control("gantry"), 
                create_device_control("stirrer"),
                create_device_control("scoop")
            ], spacing=int(15 * SCALE)),            
            ft.Row([
                create_device_control("jetson"),
                create_device_control("doors")
            ], spacing=int(15 * SCALE)),
            
            ft.Divider(color=BORDER),
            ft.Text("DUMMY RESPONSE SETTINGS", size=TXT_MED, weight="bold"),
            
            ft.Row([
                create_stepper("Move Time (s):", logic.dummy_responses["move_time"], lambda v: logic.dummy_responses.update({"move_time": v}), step=0.5, min_val=0.0, is_float=True, vertical=True),
                create_stepper("Analyze Time (s):", logic.dummy_responses["analyze_time"], lambda v: logic.dummy_responses.update({"analyze_time": v}), step=0.5, min_val=0.0, is_float=True, vertical=True),
            ], spacing=int(15 * SCALE)),
            
            ft.Text("Mock Soil Types (comma separated):", size=TXT_TINY, color=TEXT_MUTED),
            ft.TextField(value=", ".join(logic.dummy_responses["soil_types"]), height=int(60 * SCALE), text_size=TXT_MED, on_change=lambda e: logic.dummy_responses.update({"soil_types": [s.strip() for s in e.control.value.split(",")]})),
            ft.Button("EXIT TO DESKTOP", icon=ft.Icons.POWER_SETTINGS_NEW, bgcolor="#ff4444", color="white", height=BTN_HEIGHT, on_click=handle_exit_click, style=btn_style)
        ]

    tabs = ft.Tabs(
        selected_index=0, length=2, expand=True,
        content=ft.Column([
            ft.TabBar(
                tab_alignment=ft.TabAlignment.START,
                label_text_style=ft.TextStyle(size=TXT_MED, weight="bold"),
                tabs=[
                    ft.Tab(label="Dashboard", icon=ft.Icons.DASHBOARD), 
                    ft.Tab(label="Manual Debug", icon=ft.Icons.HANDYMAN)
                ]
            ),
            ft.TabBarView(expand=True, controls=[dashboard, debug_view])
        ])
    )

    header = ft.Row([
        ft.Text("SoilSense v7.0", size=TXT_LARGE, weight="bold"),
        ft.Row([
            ft.Row([door_indicators["left"], ft.Text("L Door", size=TXT_TINY)]),
            ft.Row([door_indicators["right"], ft.Text("R Door", size=TXT_TINY)]),
            ft.Row([status_indicators["gantry"], ft.Text("Gantry", size=TXT_TINY)]),
            ft.Row([status_indicators["stirrer"], ft.Text("Stirrer", size=TXT_TINY)]),
            ft.Row([status_indicators["scoop"], ft.Text("Scoop", size=TXT_TINY)]),
            ft.Row([status_indicators["jetson"], ft.Text("Jetson", size=TXT_TINY)]),
        ], spacing=int(20*SCALE))
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    page.add(header, ft.Divider(color=BORDER), tabs)
    handle_refresh("refresh")

 # Make sure to: pip install requests

    def start_camera_stream():
        def stream_loop():
            url = "http://10.42.0.76:5000/video_feed"
            while True:
                try:
                    with requests.get(url, stream=True, timeout=5) as r:
                        bytes_data = b''
                        for chunk in r.iter_content(chunk_size=1024):
                            bytes_data += chunk
                            a = bytes_data.find(b'\xff\xd8')
                            b_end = bytes_data.find(b'\xff\xd9')
                            if a != -1 and b_end != -1:
                                jpg = bytes_data[a:b_end+2]
                                bytes_data = bytes_data[b_end+2:]
                                camera_view.src_base64 = base64.b64encode(jpg).decode('utf-8')
                                camera_view.src = None  # clear file-path src so base64 takes priority
                                camera_view.update()
                                time.sleep(0.1)
                except Exception as e:
                    print(f"[STREAM] Connection lost: {e}")
                    time.sleep(2)

        threading.Thread(target=stream_loop, daemon=True).start()

if __name__ == "__main__":
    ft.run(main)