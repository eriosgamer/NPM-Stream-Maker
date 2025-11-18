import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.layout import Layout

from UI.console_handler import ws_info, ws_warning, ws_error, clear_console

# Import methods for key handling
if os.name == "nt":
    import msvcrt
else:
    import termios
    import tty

console = Console()


def get_key():
    if os.name == "nt":
        key = msvcrt.getch()
        if key == b"\xe0":
            key = msvcrt.getch()
            if key == b"H":
                return "up"
            elif key == b"P":
                return "down"
        elif key == b"\r":
            return "enter"
        elif key == b"\x1b":
            return "esc"
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            key = sys.stdin.read(1)
            if key == "\x1b":
                key += sys.stdin.read(2)
                if key == "\x1b[A":
                    return "up"
                elif key == "\x1b[B":
                    return "down"
                elif len(key) == 1:
                    return "esc"
            elif key == "\r" or key == "\n":
                return "enter"
            elif key == "\x1b":
                return "esc"
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return None


def get_terminal_size():
    return console.size


def create_service_header():
    header_text = Text("Configur for AutoStart", style="bold blue", justify="center")
    return Panel(Align.center(header_text), style="bold blue", padding=(0, 2), height=3)


def create_service_footer():
    help_text = Text.assemble(
        ("Nav: ", "bold cyan"),
        ("↑↓ ", "bold yellow"),
        ("Move  ", "white"),
        ("Enter ", "bold yellow"),
        ("Select  ", "white"),
        ("Esc ", "bold yellow"),
        ("Cancel", "white"),
    )
    return Panel(
        Align.center(help_text),
        title="[bold cyan]Controls[/bold cyan]",
        style="cyan",
        padding=(0, 2),
        height=3,
    )


def create_service_menu_content(menu_options, selected_index):
    content = []
    content.append("[bold cyan]AutoStart options:[/bold cyan]")
    content.append("")
    for i, (option_text, action) in enumerate(menu_options):
        prefix = "► " if i == selected_index else "  "
        if i == selected_index:
            content.append(
                f"[bold yellow]{prefix}[/bold yellow][bold green]{option_text}[/bold green]"
            )
        else:
            content.append(f"[green]{prefix}{option_text}[/green]")
    return "\n".join(content)


def manage_auto_start_service():
    # Detectar sistema operativo y definir opciones
    is_linux = sys.platform.startswith("linux")
    is_windows = os.name == "nt"
    menu_options = []
    if is_linux:
        menu_options.append(("Create Systemd service", "create_systemd"))
        menu_options.append(("Remove Systemd service", "remove_systemd"))
    if is_windows:
        menu_options.append(("Create Autostart entry (Windows)", "create_windows"))
        menu_options.append(("Remove Autostart entry (Windows)", "remove_windows"))
    menu_options.append(("Back to main menu", "back"))

    selected_index = 0

    while True:
        clear_console()
        terminal_width, terminal_height = get_terminal_size()
        layout = Layout()
        layout.split_column(
            Layout(create_service_header(), name="header", size=3),
            Layout(name="main"),
            Layout(create_service_footer(), name="footer", size=3),
        )
        menu_content = create_service_menu_content(menu_options, selected_index)
        layout["main"].update(Panel(menu_content, style="white", padding=(0, 1)))

        with console.capture() as capture:
            console.print(layout, end="")
        print(capture.get(), end="", flush=True)

        try:
            key = get_key()
            if key == "up":
                selected_index = (selected_index - 1) % len(menu_options)
            elif key == "down":
                selected_index = (selected_index + 1) % len(menu_options)
            elif key == "enter":
                action = menu_options[selected_index][1]
                clear_console()
                if action == "create_systemd":
                    ws_info(
                        "[SERVICE MENU]",
                        "[bold cyan]Creating Systemd service...[/bold cyan]",
                    )
                    create_systemd_service()
                    input("\nPress Enter to continue...")
                elif action == "remove_systemd":
                    ws_info(
                        "[SERVICE MENU]",
                        "[bold cyan]Removing Systemd service...[/bold cyan]",
                    )
                    remove_systemd_service()
                    input("\nPress Enter to continue...")
                elif action == "create_windows":
                    ws_info(
                        "[SERVICE MENU]",
                        "[bold cyan]Creating Autostart entry (Windows)...[/bold cyan]",
                    )
                    create_windows_autostart()
                    input("\nPress Enter to continue...")
                elif action == "remove_windows":
                    ws_info(
                        "[SERVICE MENU]",
                        "[bold cyan]Removing Autostart entry (Windows)...[/bold cyan]",
                    )
                    remove_windows_autostart()
                    input("\nPress Enter to continue...")
                elif action == "back":
                    return
            elif key == "esc":
                clear_console()
                ws_info("[SERVICE MENU]", "[yellow]No changes were made.[/yellow]")
                input("\nPress Enter to return to the main menu...")
                return
        except KeyboardInterrupt:
            ws_info("[SERVICE MENU]", "\n[bold yellow]Exiting...[/bold yellow]")
            return


def create_systemd_service():
    # Here goes the logic to create the systemd service file
    ws_info(
        "[SERVICE MENU]",
        "[green]Function to create systemd service pending implementation.[/green]",
    )
    # Submenu to choose service type
    tipos = [("WebSocket Server", "server"), ("WebSocket Client", "client")]
    selected = 0
    while True:
        clear_console()
        print("\nSelect the type of Systemd service to create:\n")
        for i, (nombre, _) in enumerate(tipos):
            prefix = "► " if i == selected else "  "
            print(f"{prefix}{nombre}")
        print("\nUse ↑↓ and Enter to select, Esc to cancel.")
        key = get_key()
        if key == "up":
            selected = (selected - 1) % len(tipos)
        elif key == "down":
            selected = (selected + 1) % len(tipos)
        elif key == "enter":
            tipo = tipos[selected][1]
            break
        elif key == "esc":
            ws_info("[SERVICE MENU]", "[yellow]Operation canceled.[/yellow]")
            return

    # Automatically detect paths
    python_exec = sys.executable
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    workdir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    user = os.getenv("USER") or os.getenv("USERNAME") or ""
    if tipo == "server":
        desc = "Python WebSocket Server"
        exec_args = f"{python_exec} {main_py} --ws-server-only"
        service_name = "npm-ws-server.service"
    else:
        desc = "Python WebSocket Client"
        exec_args = f"{python_exec} {main_py} --ws-client-only"
        service_name = "npm-ws-client.service"

    service_content = f"""[Unit]
Description={desc}
After=network.target

[Service]
Type=simple
ExecStart={exec_args}
WorkingDirectory={workdir}
#User={user}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    import shutil

    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    local_path = os.path.abspath(service_name)
    systemd_path = f"/etc/systemd/system/{service_name}"
    try:
        with open(local_path, "w") as f:
            f.write(service_content)
        ws_info("[SERVICE MENU]", f"[green]Service generated at {local_path}.[/green]")
        if is_root:
            shutil.move(local_path, systemd_path)
            ws_info("[SERVICE MENU]", f"[green]Moved to {systemd_path}.[/green]")
            os.system("systemctl daemon-reload")
            ws_info(
                "[SERVICE MENU]", "[green]systemctl daemon-reload executed.[/green]"
            )
            os.system(f"systemctl enable --now {service_name}")
            ws_info(
                "[SERVICE MENU]",
                f"[green]Service {service_name} enabled and started.[/green]",
            )
        else:
            ws_warning(
                "[SERVICE MENU]",
                f"[yellow]You do not have root permissions. Manually copy to /etc/systemd/system/ and run systemctl daemon-reload && systemctl enable --now {service_name}.[/yellow]",
            )
    except Exception as e:
        ws_error("[SERVICE MENU]", f"[red]Error creating/moving file: {e}[/red]")


def remove_systemd_service():
    import shutil

    tipos = [
        ("WebSocket Server", "npm-ws-server.service"),
        ("WebSocket Client", "npm-ws-client.service"),
    ]
    selected = 0
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    while True:
        clear_console()
        print("\nSelect the Systemd service to remove:\n")
        for i, (nombre, fname) in enumerate(tipos):
            prefix = "► " if i == selected else "  "
            print(f"{prefix}{nombre} ({fname})")
        print("\nUse ↑↓ and Enter to select, Esc to cancel.")
        key = get_key()
        if key == "up":
            selected = (selected - 1) % len(tipos)
        elif key == "down":
            selected = (selected + 1) % len(tipos)
        elif key == "enter":
            service_name = tipos[selected][1]
            break
        elif key == "esc":
            ws_info("[SERVICE MENU]", "[yellow]Operation canceled.[/yellow]")
            return

    systemd_path = f"/etc/systemd/system/{service_name}"
    try:
        if is_root:
            os.system(f"systemctl disable --now {service_name}")
            ws_info(
                "[SERVICE MENU]",
                f"[green]Service {service_name} disabled and stopped.[/green]",
            )
            if os.path.exists(systemd_path):
                os.remove(systemd_path)
                ws_info(
                    "[SERVICE MENU]", f"[green]File {systemd_path} removed.[/green]"
                )
            os.system("systemctl daemon-reload")
            ws_info(
                "[SERVICE MENU]", "[green]systemctl daemon-reload executed.[/green]"
            )
        else:
            ws_warning(
                "[SERVICE MENU]",
                f"[yellow]You do not have root permissions. Manually remove {systemd_path} and run systemctl disable --now {service_name} && systemctl daemon-reload.[/yellow]",
            )
    except Exception as e:
        ws_error("[SERVICE MENU]", f"[red]Error removing/disabling service: {e}[/red]")


def create_windows_autostart():
    # Here goes the logic to create the .bat and add it to Windows startup
    ws_info(
        "[SERVICE MENU]",
        "[green]Function to create Autostart in Windows pending implementation.[/green]",
    )
    # Submenu to choose autostart type
    tipos = [("WebSocket Server", "server"), ("WebSocket Client", "client")]
    selected = 0
    while True:
        clear_console()
        print("\nSelect the type of Autostart to create (Windows):\n")
        for i, (nombre, _) in enumerate(tipos):
            prefix = "► " if i == selected else "  "
            print(f"{prefix}{nombre}")
        print("\nUse ↑↓ and Enter to select, Esc to cancel.")
        key = get_key()
        if key == "up":
            selected = (selected - 1) % len(tipos)
        elif key == "down":
            selected = (selected + 1) % len(tipos)
        elif key == "enter":
            tipo = tipos[selected][1]
            break
        elif key == "esc":
            ws_info("[SERVICE MENU]", "[yellow]Operation canceled.[/yellow]")
            return

    python_exec = sys.executable
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    workdir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if tipo == "server":
        exec_args = f'"{python_exec}" "{main_py}" --ws-server-only'
        bat_name = "npm-ws-server-autostart.bat"
    else:
        exec_args = f'"{python_exec}" "{main_py}" --ws-client-only'
        bat_name = "npm-ws-client-autostart.bat"

    bat_content = f"@echo off\ncd /d {workdir}\n{exec_args}\n"
    try:
        with open(bat_name, "w") as f:
            f.write(bat_content)
        ws_info(
            "[SERVICE MENU]",
            f"[green]File .bat generated in ./{bat_name}\nManually add to the Windows startup folder if necessary.[/green]",
        )
    except Exception as e:
        ws_error("[SERVICE MENU]", f"[red]Error creating file: {e}[/red]")


def remove_windows_autostart():
    # Here goes the logic to remove the .bat from Windows startup
    ws_info(
        "[SERVICE MENU]",
        "[green]Function to remove Autostart in Windows pending implementation.[/green]",
    )
