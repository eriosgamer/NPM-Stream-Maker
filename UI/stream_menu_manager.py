import sys
import os
import time
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.layout import Layout
from UI.console_handler import ws_info, ws_error, ws_warning
from Core.remote_message_handler import create_stream_from_remote
from Streams.stream_cleaning import delete_specific_stream

# Key handling cross-platform
if os.name == "nt":
    import msvcrt
else:
    import termios
    import tty

console = Console()


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


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


def create_header():
    header_text = Text("Administración de Streams", style="bold blue", justify="center")
    return Panel(Align.center(header_text), style="bold blue", padding=(0, 2), height=3)


def create_footer():
    help_text = Text.assemble(
        ("Navegación: ", "bold cyan"),
        ("↑↓ ", "bold yellow"),
        ("Mover  ", "white"),
        ("Enter ", "bold yellow"),
        ("Seleccionar  ", "white"),
        ("Esc ", "bold yellow"),
        ("Salir", "white"),
    )
    return Panel(
        Align.center(help_text),
        title="[bold cyan]Controles[/bold cyan]",
        style="cyan",
        padding=(0, 2),
        height=3,
    )


def create_menu_content(menu_options, selected_index, window_start, window_size):
    content = []
    content.append("[bold cyan]Opciones de Streams:[/bold cyan]\n")
    visible_options = menu_options[window_start : window_start + window_size]
    for i, (option_text, available, requirement) in enumerate(visible_options):
        real_index = window_start + i
        prefix = "► " if real_index == selected_index else "  "
        if available:
            if real_index == selected_index:
                content.append(
                    f"[bold yellow]{prefix}[/bold yellow][bold green]{option_text}[/bold green]"
                )
            else:
                content.append(f"[green]{prefix}{option_text}[/green]")
        else:
            if real_index == selected_index:
                content.append(
                    f"[bold yellow]{prefix}[/bold yellow][bold red]{option_text}[/bold red] [dim red]({requirement})[/dim red]"
                )
            else:
                content.append(
                    f"[red]{prefix}{option_text}[/red] [dim red]({requirement})[/dim red]"
                )
    return "\n".join(content)


def add_stream_form():
    clear_console()
    console.print(
        Panel("[bold cyan]Agregar Stream Manualmente[/bold cyan]", style="blue")
    )
    try:
        port = int(
            console.input("[bold green]Puerto (entrada/destino): [/bold green]").strip()
        )
        host = console.input("[bold green]Host de destino: [/bold green]").strip()
        tcp = (
            console.input("[bold green]¿Activar TCP? (s/n): [/bold green]")
            .strip()
            .lower()
            == "s"
        )
        udp = (
            console.input("[bold green]¿Activar UDP? (s/n): [/bold green]")
            .strip()
            .lower()
            == "s"
        )
        stream_data = {
            "incoming_port": port,
            "forwarding_host": host,
            "forwarding_port": port,
            "tcp_forwarding": int(tcp),
            "udp_forwarding": int(udp),
        }
        ws_info("[ADD_STREAM]", f"Creando stream: {stream_data}")
        result = asyncio.run(create_stream_from_remote(stream_data))
        if result:
            ws_info("[ADD_STREAM]", "Stream creado y sincronizado correctamente.")
            return True
        else:
            ws_error("[ADD_STREAM]", "Error al crear el stream.")
            return False
    except Exception as e:
        ws_error("[ADD_STREAM]", f"Error al crear el stream: {e}")
        return False


def create_stream_from_remote_message(stream_data):
    ws_info("[ADD_STREAM]", "Creando stream con datos remotos...")
    try:
        stream_data = {
            "incoming_port": stream_data["incoming_port"],
            "forwarding_host": stream_data["forwarding_host"],
            "forwarding_port": stream_data["forwarding_port"],
            "tcp_forwarding": stream_data["tcp_forwarding"],
            "udp_forwarding": stream_data["udp_forwarding"],
        }
        ws_info("[ADD_STREAM]", f"Creando stream: {stream_data}")
        result = asyncio.run(create_stream_from_remote(stream_data))
        if result:
            ws_info("[ADD_STREAM]", "Stream creado y sincronizado correctamente.")
            return True
        else:
            ws_error("[ADD_STREAM]", "Error al crear el stream.")
            return False
    except Exception as e:
        ws_error("[ADD_STREAM]", f"Error al crear el stream: {e}")
        return False

def remove_stream_from_remote(stream_id):
    ws_info("[REMOVE_STREAM]", f"Eliminando stream con ID {stream_id}...")
    try:
        delete_specific_stream(stream_id)
        ws_info("[REMOVE_STREAM]", f"Stream con ID {stream_id} eliminado correctamente.")
    except Exception as e:
        ws_error("[REMOVE_STREAM]", f"Error al eliminar el stream: {e}")
    

def remove_stream_form():
    clear_console()
    console.print(Panel("[bold cyan]Eliminar Stream[/bold cyan]", style="red"))
    try:
        stream_id = int(
            console.input("[bold green]ID del Stream a eliminar: [/bold green]").strip()
        )
        delete_specific_stream(stream_id)
        ws_info(
            "[REMOVE_STREAM]", f"Stream con ID {stream_id} eliminado correctamente."
        )
    except Exception as e:
        ws_error("[REMOVE_STREAM]", f"Error al eliminar el stream: {e}")


def show_streams():
    clear_console()
    from Streams import stream_handler as sh

    sh.show_streams()


def clear_all_streams():
    clear_console()
    from Streams import stream_cleaning as sc

    sc.clear_all_streams()


def stream_menu_manager():
    menu_options = [
        ("Agregar Stream Manualmente", True, ""),
        ("Eliminar Stream", True, ""),
        ("Mostrar Streams Existentes", True, ""),
        ("Limpiar Todos los Streams", True, ""),
        ("Volver al Menú Principal", True, ""),
    ]
    selected_index = 0
    window_start = 0
    while True:
        clear_console()
        terminal_width, terminal_height = console.size
        window_size = max(1, terminal_height - 15)
        if selected_index < window_start:
            window_start = selected_index
        elif selected_index >= window_start + window_size:
            window_start = selected_index - window_size + 1
        if window_start + window_size > len(menu_options):
            window_start = max(0, len(menu_options) - window_size)
        layout = Layout()
        layout.split_column(
            Layout(create_header(), name="header", size=3),
            Layout(name="main"),
            Layout(create_footer(), name="footer", size=3),
        )
        menu_content = create_menu_content(
            menu_options, selected_index, window_start, window_size
        )
        layout["main"].update(Panel(menu_content, style="white", padding=(1, 2)))
        console.print(layout)
        try:
            key = get_key()
            if key == "up":
                selected_index = (selected_index - 1) % len(menu_options)
            elif key == "down":
                selected_index = (selected_index + 1) % len(menu_options)
            elif key == "enter":
                if selected_index == 0:
                    add_stream_form()
                elif selected_index == 1:
                    remove_stream_form()
                elif selected_index == 2:
                    show_streams()
                elif selected_index == 3:
                    clear_all_streams()
                elif selected_index == 4:
                    break
            elif key == "esc":
                break
        except KeyboardInterrupt:
            ws_warning("[STREAM_MENU]", "Saliendo...")
            break
