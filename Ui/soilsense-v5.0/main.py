import flet as ft
import threading
from hardware_logic import SoilSenseLogic

def main(page: ft.Page):
    page.title = "SoilSense v5.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#151619"
    page.window_width = 1100
    page.window_height = 850

    # Initialize the Hardware Backend
    logic = SoilSenseLogic()

    # --- UI STYLING ---
    ACCENT = "#00ff41"
    BG_CARD = "#1c1e22"
    BORDER = "#2c2e33"

    # --- UI COMPONENTS ---
    log_column = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True)
    grid_display = ft.GridView(expand=True, runs_count=3, max_extent=150, spacing=10)

    btn_start = ft.ElevatedButton(
        "START GRID ANALYSIS", 
        icon=ft.Icons.PLAY_ARROW, 
        bgcolor=ACCENT, 
        color="black",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )

    # --- CALLBACK FUNCTIONS ---
    def refresh_logs_ui():
        """Triggered by logic.log()"""
        log_column.controls = [ft.Text(l, size=12, color="#8e9299", font_family="monospace") for l in logic.logs]
        page.update()

    def refresh_grid_ui():
        """Triggered by logic.run_sequence() during updates"""
        grid_display.controls.clear()
        for i in range(9):
            res = logic.soil_results[i]
            r, c = i // 3, i % 3
            is_active = logic.isRunning and logic.currentRow == r and logic.currentCol == c
            
            grid_display.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{r},{c}", size=10, color="#8e9299"),
                        ft.Text(res if res else "-", color=ACCENT if res else "white", weight="bold", size=16),
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment.CENTER,
                    bgcolor=BG_CARD if not is_active else "#1A00FF41",
                    border=ft.Border.all(1, ACCENT if is_active or res else BORDER),
                    border_radius=8,
                )
            )
        btn_start.disabled = logic.isRunning
        page.update()

    # Wire the UI functions to the Logic engine
    logic.on_log_update = refresh_logs_ui
    logic.on_grid_update = refresh_grid_ui

    def handle_start_click(e):
        # Run hardware sequence in a background thread so UI doesn't freeze
        threading.Thread(target=logic.run_sequence, daemon=True).start()

    btn_start.on_click = handle_start_click

    # Render initial states
    refresh_grid_ui()
    refresh_logs_ui()

    # --- DASHBOARD & DEBUG VIEWS ---
    dashboard_view = ft.Row([
        ft.Column([
            ft.Text("GANTRY VISUALIZER", size=12, weight="bold", color="#8e9299"),
            ft.Container(content=grid_display, expand=True),
            btn_start,
        ], expand=2),
        ft.VerticalDivider(width=1, color=BORDER),
        ft.Column([
            ft.Text("SYSTEM LOGS", size=12, weight="bold", color="#8e9299"),
            ft.Container(content=log_column, expand=True, bgcolor="black", padding=10, border_radius=8),
        ], expand=1)
    ], expand=True)

    debug_view = ft.Container(
        content=ft.Column([
            ft.Text("HARDWARE MANUAL OVERRIDE", size=20, weight="bold"),
            ft.Switch(
                label="Dummy Mode (Simulation)", 
                value=logic.dummyMode, 
                on_change=lambda e: logic.set_dummy_mode(e.control.value),
                active_color=ACCENT
            ),
            ft.Divider(color=BORDER),
            ft.Text("Manual Control:", weight="bold"),
            ft.Row([
                ft.ElevatedButton("Scoop UP", icon=ft.Icons.ARROW_UPWARD, on_click=lambda _: logic.write_hardware("scoop", b"0\n")),
                ft.ElevatedButton("Scoop DOWN", icon=ft.Icons.ARROW_DOWNWARD, on_click=lambda _: logic.write_hardware("scoop", b"1\n")),
            ]),
            ft.Row([
                ft.ElevatedButton("Stirrer ON", icon=ft.Icons.AUTORENEW, on_click=lambda _: logic.write_hardware("stirrer", b"1\n")),
                ft.ElevatedButton("Stirrer OFF", icon=ft.Icons.STOP, on_click=lambda _: logic.write_hardware("stirrer", b"0\n")),
            ]),
        ], spacing=15),
        padding=20
    )

    # --- MODERN TAB SYSTEM ---
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
                controls=[dashboard_view, debug_view]
            )
        ])
    )

    # --- FINAL PAGE ADD ---
    page.add(
        ft.Row([
            ft.Icon(ft.Icons.PRECISION_MANUFACTURING, color=ACCENT, size=30),
            ft.Text("SoilSense v5.0", size=24, weight="bold", color="white"),
        ], alignment=ft.MainAxisAlignment.START),
        ft.Divider(height=10, color=BORDER),
        tab_system
    )

if __name__ == "__main__":
    ft.app(target=main)