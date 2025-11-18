import time
import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from enum import Enum
from typing import Dict, Any, Optional, List
import os
import threading
from collections import deque


import shutil
import zipfile

LOG_DIR = "logs"
LOG_FILE = "npm_console.log"


def ensure_log_file():
    """
    Asegura que el log actual sea del día. Si existe y no es de hoy, lo mueve a logs/ y lo comprime.
    """
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    # Crear carpeta logs si no existe
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # Si existe el log, verificar si es de hoy
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                first_line = f.readline()
                second_line = f.readline()
                # Buscar fecha en el primer log del día
                # Si el archivo es muy grande, solo revisamos el nombre
            # Obtener fecha de modificación
            mtime = datetime.datetime.fromtimestamp(
                os.path.getmtime(LOG_FILE)
            ).strftime("%Y-%m-%d")
            if mtime != today_str:
                # Mover y comprimir log anterior
                zip_name = f"npm_console_{mtime}.zip"
                zip_path = os.path.join(LOG_DIR, zip_name)
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(LOG_FILE, arcname=f"npm_console_{mtime}.log")
                os.remove(LOG_FILE)
        except Exception as e:
            # Si hay error, continuar y crear nuevo log
            pass
    # Crear nuevo log si no existe
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("NPM Console Log\n")
            f.write("=" * 50 + "\n")


def append_to_log(entry: str):
    """
    Añade una entrada al log actual con timestamp. Llama a ensure_log_file para rotar si es necesario.
    """
    try:
        ensure_log_file()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {entry}\n")
    except PermissionError:
        # Si no hay permisos de escritura, intentar imprimir en consola en lugar de fallar
        pass
    except Exception:
        # Ignorar otros errores de log para no interrumpir el flujo principal
        pass


class MessageType(Enum):
    """WebSocket message types"""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"
    CONNECTION = "connection"
    SERVER = "server"
    CLIENT = "client"


class ConsoleHandler:
    """
    Centralized console handler for all WebSocket messages.
    Provides unified layout and consistent formatting with scroll.
    """

    def __init__(self):
        self.console = Console()
        self.message_history = []
        self.max_history = 1000
        self.live_messages = deque(maxlen=100)  # Buffer para mensajes en vivo
        self.current_component = None
        self.is_live_mode = False
        self.live_display = None
        self.message_lock = threading.Lock()

        # Style configuration for each message type
        self.styles = {
            MessageType.INFO: {"color": "cyan", "icon": "ℹ️", "prefix": "INFO"},
            MessageType.SUCCESS: {"color": "green", "icon": "✅", "prefix": "SUCCESS"},
            MessageType.WARNING: {"color": "yellow", "icon": "⚠️", "prefix": "WARNING"},
            MessageType.ERROR: {"color": "red", "icon": "❌", "prefix": "ERROR"},
            MessageType.DEBUG: {"color": "blue", "icon": "🔍", "prefix": "DEBUG"},
            MessageType.CONNECTION: {
                "color": "magenta",
                "icon": "🔗",
                "prefix": "CONNECTION",
            },
            MessageType.SERVER: {
                "color": "bright_blue",
                "icon": "🖥️",
                "prefix": "SERVER",
            },
            MessageType.CLIENT: {
                "color": "bright_green",
                "icon": "💻",
                "prefix": "CLIENT",
            },
        }

        # Component configuration
        self.components = {
            "WS": "WebSocket",
            "WS_CLIENT": "WebSocket Client",
            "WS_SERVER": "WebSocket Server",
            "REMOTE": "Remote Control",
            "CONFLICT": "Conflict Resolution",
            "STREAM": "Stream Manager",
            "NPM": "NPM Handler",
        }

    def clear_console(self):
        """Clears the console"""
        os.system("cls" if os.name == "nt" else "clear")

    def get_timestamp(self) -> str:
        """Gets formatted timestamp"""
        return datetime.datetime.now().strftime("%H:%M:%S")

    def format_message(
        self,
        component: str,
        message: str,
        msg_type: MessageType = MessageType.INFO,
        details: Optional[Dict[str, Any]] = None,
    ) -> Text:
        """
        Formats a message with unified style.

        Args:
            component: System component (WS, WS_CLIENT, etc.)
            message: Main message
            msg_type: Message type
            details: Optional additional details
        """
        style_config = self.styles[msg_type]
        timestamp = self.get_timestamp()

        # Crear texto formateado
        formatted_text = Text()

        # Timestamp
        formatted_text.append(f"[{timestamp}] ", style="dim white")

        # Icono y tipo
        formatted_text.append(f"{style_config['icon']} ", style=style_config["color"])

        # Componente
        component_name = self.components.get(component, component)
        formatted_text.append(
            f"[{component_name}] ", style=f"bold {style_config['color']}"
        )

        # Mensaje principal
        formatted_text.append(message, style=style_config["color"])

        # Detalles adicionales si existen
        if details:
            formatted_text.append("\n")
            for key, value in details.items():
                formatted_text.append(f"  {key}: {value}\n", style="dim white")

        return formatted_text

    def get_terminal_size(self):
        """Gets the current terminal size"""
        return self.console.size

    def create_header(
        self, title: str = "NPM Stream Manager", subtitle: str = "Console Output"
    ):
        """Creates the fixed header for the console"""
        header_content = Text()
        header_content.append(title, style="bold blue")
        if subtitle:
            header_content.append(f"\n{subtitle}", style="dim white")

        return Panel(
            Align.center(header_content),
            style="bold blue",
            padding=(0, 2),
            height=4 if subtitle else 3,
        )

    def create_footer(self, help_items: Optional[List[tuple]] = None):
        """Creates the fixed footer with help"""
        if not help_items:
            help_items = [
                ("Ctrl+C", "Exit"),
                ("↑↓", "Scroll"),
                ("Esc", "Return"),
                ("Space", "Pause"),
            ]

        help_text = Text()
        for i, (key, action) in enumerate(help_items):
            if i > 0:
                help_text.append(" | ", style="dim white")
            help_text.append(key, style="bold yellow")
            help_text.append(f" {action}", style="white")

        return Panel(
            Align.center(help_text),
            title="[bold cyan]Controls[/bold cyan]",
            style="cyan",
            padding=(0, 2),
            height=3,
        )

    def create_message_panel(self, max_lines: int = 20):
        """Creates the message panel with scroll"""
        terminal_width, terminal_height = self.get_terminal_size()

        # Calculate number of available lines
        available_lines = min(
            max_lines, terminal_height - 10
        )  # Reserve space for header/footer

        # Obtener mensajes recientes
        with self.message_lock:
            recent_messages = list(self.live_messages)[-available_lines:]

        if not recent_messages:
            content = Text("No messages yet...", style="dim white")
        else:
            content = Text()
            for i, msg_text in enumerate(recent_messages):
                if i > 0:
                    content.append("\n")
                content.append(msg_text)

        # Crear panel con scroll
        message_panel = Panel(
            content,
            title="[bold green]Console Messages[/bold green]",
            title_align="left",
            border_style="green",
            padding=(0, 1),
        )

        return message_panel

    def start_live_mode(
        self, title: str = "NPM Stream Manager", subtitle: str = "Live Console"
    ):
        """Starts live console mode with fixed layout"""
        if self.is_live_mode:
            return

        self.is_live_mode = True
        self.current_component = title

        def create_layout():
            """Crea el layout completo de la consola"""
            layout = Layout()

            # Estructura principal
            layout.split_column(
                Layout(self.create_header(title, subtitle), name="header", size=4),
                Layout(name="main"),
                Layout(self.create_footer(), name="footer", size=3),
            )

            # Panel de mensajes en el área principal
            layout["main"].update(self.create_message_panel())

            return layout

        # Iniciar display en vivo
        try:
            self.live_display = Live(
                create_layout(),
                console=self.console,
                refresh_per_second=2,  # Actualizar 2 veces por segundo
                screen=True,
            )
            self.live_display.start()
        except Exception as e:
            # Si falla el modo live, usar modo normal
            self.is_live_mode = False
            self.console.print(f"[red]Failed to start live mode: {e}[/red]")

    def stop_live_mode(self):
        """Stops live console mode"""
        if not self.is_live_mode:
            return

        self.is_live_mode = False

        if self.live_display:
            try:
                self.live_display.stop()
            except:
                pass
            self.live_display = None

    def update_live_display(self):
        """Updates the live display if active"""
        if not self.is_live_mode or not self.live_display:
            return

        try:
            # Crear layout actualizado
            layout = Layout()
            layout.split_column(
                Layout(
                    self.create_header(
                        self.current_component or "NPM Stream Manager", "Live Console"
                    ),
                    name="header",
                    size=4,
                ),
                Layout(name="main"),
                Layout(self.create_footer(), name="footer", size=3),
            )

            layout["main"].update(self.create_message_panel())

            # Actualizar display
            self.live_display.update(layout)
        except Exception:
            # Si falla la actualización, continuar sin errores
            pass

    def add_live_message(self, formatted_text: Text):
        """Adds a message to the live message buffer"""
        with self.message_lock:
            # Añadir timestamp si no está en modo live
            if not self.is_live_mode:
                timestamp = f"[{self.get_timestamp()}] "
                timestamped_text = Text()
                timestamped_text.append(timestamp, style="dim white")
                timestamped_text.append(formatted_text)
                self.live_messages.append(timestamped_text)
            else:
                self.live_messages.append(formatted_text)

        # Actualizar display si está en modo live
        if self.is_live_mode:
            self.update_live_display()

    def print_message(
        self,
        component: str,
        message: str,
        msg_type: MessageType = MessageType.INFO,
        details: Optional[Dict[str, Any]] = None,
        save_to_history: bool = True,
        interpret_markup: bool = True,
    ):
        """
        Prints a formatted message to the console with scroll.
        If interpret_markup is True, interprets Rich markup tags in the message.
        """
        # Si el mensaje contiene etiquetas Rich, usar markup
        if interpret_markup and ("[" in message and "]" in message):
            # Imprimir usando markup
            if self.is_live_mode:
                # En modo live, añadir como texto plano (sin markup)
                formatted_message = self.format_message(
                    component, self._strip_markup(message), msg_type, details
                )
                self.add_live_message(formatted_message)
            else:
                # Imprimir con markup
                self.console.print(message, markup=True)
                # También añadir al buffer para futuro modo live
                formatted_message = self.format_message(
                    component, self._strip_markup(message), msg_type, details
                )
                self.add_live_message(formatted_message)
        else:
            formatted_message = self.format_message(
                component, message, msg_type, details
            )
            if self.is_live_mode:
                self.add_live_message(formatted_message)
            else:
                self.console.print(formatted_message)
                self.add_live_message(formatted_message)
        # Guardar en historial
        if save_to_history:
            self.message_history.append(
                {
                    "timestamp": time.time(),
                    "component": component,
                    "message": self._strip_markup(message),
                    "type": msg_type.value,
                    "details": details,
                }
            )
            # Limitar historial
            if len(self.message_history) > self.max_history:
                self.message_history = self.message_history[-self.max_history :]

    def _strip_markup(self, text: str) -> str:
        """
        Elimina las etiquetas Rich markup del texto para guardar limpio en el log.
        """
        import re

        # Elimina [xxx] y [/xxx] y [xxx=yyy]
        return re.sub(r"\[/?[a-zA-Z0-9_\-=]+\]", "", text)

    def show_scrollable_console(
        self,
        title: str = "Console Output",
        auto_scroll: bool = True,
        show_help: bool = True,
    ):
        """
        Shows a simple scrollable console, similar to the client, with key navigation.
        """
        import os, sys
        import time

        # Manejo de teclas multiplataforma simple
        if os.name == "nt":
            import msvcrt

            def get_key():
                key = msvcrt.getch()
                if key == b"\xe0":
                    key2 = msvcrt.getch()
                    if key2 == b"H":
                        return "up"
                    elif key2 == b"P":
                        return "down"
                    elif key2 == b"G":
                        return "home"
                    elif key2 == b"O":
                        return "end"
                    elif key2 == b"I":
                        return "pgup"
                    elif key2 == b"Q":
                        return "pgdn"
                elif key == b"\r":
                    return "enter"
                elif key == b"\x1b":
                    return "esc"
                elif key == b" ":
                    return "space"

        else:
            import termios, tty, select

            def get_key():
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    while True:
                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            key = sys.stdin.read(1)
                            if key == "\x1b":
                                seq = sys.stdin.read(1)
                                if seq == "[":
                                    seq2 = sys.stdin.read(1)
                                    if seq2 == "A":
                                        return "up"
                                    elif seq2 == "B":
                                        return "down"
                                    elif seq2 == "H":
                                        return "home"
                                    elif seq2 == "F":
                                        return "end"
                                    elif seq2 == "5":
                                        if sys.stdin.read(1) == "~":
                                            return "pgup"
                                    elif seq2 == "6":
                                        if sys.stdin.read(1) == "~":
                                            return "pgdn"
                                else:
                                    return "esc"
                            elif key == "\r" or key == "\n":
                                return "enter"
                            elif key == " ":
                                return "space"
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        # Mensajes formateados
        messages_to_show = []
        for msg_data in self.message_history:
            formatted = self.format_message(
                msg_data["component"],
                msg_data["message"],
                MessageType(msg_data["type"]),
                msg_data.get("details"),
            )
            messages_to_show.append(formatted)

        if not messages_to_show:
            messages_to_show = [Text("No messages in history...", style="dim white")]

        # Determinar altura de terminal y ventana de scroll
        terminal_height = self.console.size.height
        window_size = max(5, terminal_height - 4)  # 4 líneas para controles y título
        scroll_pos = max(0, len(messages_to_show) - window_size)

        while True:
            self.clear_console()
            self.console.print(
                f"[bold blue]{title}[/bold blue]  ([yellow]↑↓ PgUp/PgDn Home/End Esc[/yellow])"
            )
            self.console.print("-" * self.console.size.width)
            window = messages_to_show[scroll_pos : scroll_pos + window_size]
            for msg in window:
                self.console.print(msg)
            self.console.print("-" * self.console.size.width)
            self.console.print(
                f"[dim]Scroll: {scroll_pos+1}-{min(scroll_pos+window_size, len(messages_to_show))} / {len(messages_to_show)}[/dim]"
            )
            key = get_key()
            if key == "up":
                if scroll_pos > 0:
                    scroll_pos -= 1
            elif key == "down":
                if scroll_pos < max(0, len(messages_to_show) - window_size):
                    scroll_pos += 1
            elif key == "pgup":
                scroll_pos = max(0, scroll_pos - window_size)
            elif key == "pgdn":
                scroll_pos = min(
                    max(0, len(messages_to_show) - window_size),
                    scroll_pos + window_size,
                )
            elif key == "home":
                scroll_pos = 0
            elif key == "end":
                scroll_pos = max(0, len(messages_to_show) - window_size)
            elif key == "esc" or key == "enter":
                break
            # else: ignorar otras teclas

    def create_status_dashboard(
        self,
        components_status: Dict[str, Dict[str, Any]],
        title: str = "System Status Dashboard",
    ):
        """
        Creates a system status dashboard with fixed layout.
        """
        layout = Layout()
        layout.split_column(
            Layout(
                self.create_header(title, "Real-time System Status"),
                name="header",
                size=4,
            ),
            Layout(name="main"),
            Layout(
                self.create_footer(
                    [
                        ("R", "Refresh"),
                        ("C", "Clear"),
                        ("H", "History"),
                        ("Esc", "Exit"),
                    ]
                ),
                name="footer",
                size=3,
            ),
        )

        # Crear tabla de estado
        status_table = Table(
            show_header=True, header_style="bold cyan", show_lines=True
        )
        status_table.add_column("Component", style="yellow", width=20)
        status_table.add_column("Status", style="green", width=15)
        status_table.add_column("Last Activity", style="blue", width=20)
        status_table.add_column("Details", style="white")

        for component, status_data in components_status.items():
            component_name = self.components.get(component, component)
            status = status_data.get("status", "Unknown")
            last_activity = status_data.get("last_activity", "N/A")
            details = status_data.get("details", "No details")

            # Formatear estado con colores
            if status.lower() in ["active", "connected", "running"]:
                status_display = f"[green]✅ {status}[/green]"
            elif status.lower() in ["inactive", "disconnected", "stopped"]:
                status_display = f"[red]❌ {status}[/red]"
            else:
                status_display = f"[yellow]⚠️ {status}[/yellow]"

            status_table.add_row(component_name, status_display, last_activity, details)

        # Panel principal con la tabla
        main_panel = Panel(
            status_table,
            title="[bold blue]Component Status[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )

        layout["main"].update(main_panel)
        return layout

    def print_connection_status(
        self,
        component: str,
        uri: str,
        status: str,
        additional_info: Optional[Dict[str, Any]] = None,
    ):
        """
        Prints connection status with special formatting.
        """
        status_styles = {
            "connecting": MessageType.INFO,
            "connected": MessageType.SUCCESS,
            "disconnected": MessageType.WARNING,
            "failed": MessageType.ERROR,
            "reconnecting": MessageType.WARNING,
        }

        msg_type = status_styles.get(status.lower(), MessageType.INFO)
        details = {"URI": uri}
        if additional_info:
            details.update(additional_info)

        self.print_message(
            component=component,
            message=f"Connection {status}",
            msg_type=msg_type,
            details=details,
        )

    def print_port_info(
        self,
        component: str,
        action: str,
        ports: List[Dict[str, Any]],
        additional_info: Optional[str] = None,
    ):
        """
        Prints information about ports with formatted table.
        """
        # Mensaje principal
        msg = f"{action} {len(ports)} port(s)"
        if additional_info:
            msg += f" - {additional_info}"

        self.print_message(component, msg, MessageType.INFO)

        # Crear tabla de puertos si hay pocos
        if len(ports) <= 10:
            table = Table(show_header=True, header_style="bold cyan", show_lines=True)
            table.add_column("Port", style="yellow", justify="center")
            table.add_column("Protocol", style="green", justify="center")
            table.add_column("Status", style="blue")

            for port_info in ports:
                port = str(port_info.get("port", "N/A"))
                protocol = port_info.get("protocol", "tcp")
                status = port_info.get("status", "active")
                table.add_row(port, protocol, status)

            if self.is_live_mode:
                # En modo live, añadir como texto formateado
                table_text = Text()
                table_text.append(str(table))
                self.add_live_message(table_text)
            else:
                self.console.print(table)
        else:
            # Para muchos puertos, solo mostrar resumen
            protocols = {}
            for port_info in ports:
                proto = port_info.get("protocol", "tcp")
                protocols[proto] = protocols.get(proto, 0) + 1

            summary = ", ".join(
                [f"{count} {proto}" for proto, count in protocols.items()]
            )
            self.print_message(component, f"Port summary: {summary}", MessageType.DEBUG)

    def print_server_capabilities(
        self, component: str, server_uri: str, capabilities: Dict[str, Any]
    ):
        """
        Prints server capabilities with special formatting.
        """
        self.print_message(
            component, f"Server capabilities for {server_uri}", MessageType.INFO
        )

        # Crear tabla de capacidades
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Capability", style="yellow")
        table.add_column("Value", style="green")

        capability_names = {
            "server_type": "Server Type",
            "has_wireguard": "WireGuard",
            "conflict_resolution_server": "Conflict Resolution",
            "port_forwarding_server": "Port Forwarding",
            "wireguard_ip": "WireGuard IP",
            "wireguard_peer_ip": "WireGuard Peer IP",
        }

        for key, value in capabilities.items():
            display_name = capability_names.get(key, key.replace("_", " ").title())
            if isinstance(value, bool):
                display_value = "✅ Yes" if value else "❌ No"
            else:
                display_value = str(value) if value else "N/A"
            table.add_row(display_name, display_value)

        if self.is_live_mode:
            # En modo live, añadir como texto formateado
            table_text = Text()
            table_text.append(str(table))
            self.add_live_message(table_text)
        else:
            self.console.print(table)

    def print_error_panel(
        self,
        component: str,
        error_title: str,
        error_message: str,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Prints error panel with suggestions.
        """
        content = Text()
        content.append(f"❌ {error_message}\n", style="bold red")

        if suggestions:
            content.append("\n💡 Suggestions:\n", style="bold yellow")
            for i, suggestion in enumerate(suggestions, 1):
                content.append(f"  {i}. {suggestion}\n", style="white")

        error_panel = Panel(
            content,
            title=f"[bold red]Error in {self.components.get(component, component)}[/bold red]",
            title_align="left",
            border_style="red",
            padding=(1, 2),
        )

        if self.is_live_mode:
            # En modo live, convertir panel a texto
            error_text = Text()
            error_text.append(
                f"ERROR in {self.components.get(component, component)}: {error_message}",
                style="bold red",
            )
            if suggestions:
                error_text.append("\nSuggestions: ", style="bold yellow")
                for suggestion in suggestions:
                    error_text.append(f"\n  • {suggestion}", style="white")
            self.add_live_message(error_text)
        else:
            self.console.print(error_panel)

    def print_status_summary(self, component: str, status_data: Dict[str, Any]):
        """
        Prints status summary with formatted panel.
        """
        content = Text()

        for key, value in status_data.items():
            display_key = key.replace("_", " ").title()
            content.append(f"{display_key}: ", style="bold cyan")

            if isinstance(value, bool):
                content.append(
                    "✅ Active" if value else "❌ Inactive",
                    style="green" if value else "red",
                )
            elif isinstance(value, (int, float)):
                content.append(str(value), style="yellow")
            else:
                content.append(str(value), style="white")
            content.append("\n")

        if self.is_live_mode:
            # En modo live, usar formato simplificado
            status_text = Text()
            status_text.append(
                f"Status - {self.components.get(component, component)}: ",
                style="bold blue",
            )
            status_items = []
            for key, value in status_data.items():
                status_items.append(f"{key.replace('_', ' ')}: {value}")
            status_text.append(", ".join(status_items), style="white")
            self.add_live_message(status_text)
        else:
            status_panel = Panel(
                content,
                title=f"[bold blue]Status - {self.components.get(component, component)}[/bold blue]",
                title_align="left",
                border_style="blue",
                padding=(1, 2),
            )
            self.console.print(status_panel)

    def get_message_history(
        self,
        component: Optional[str] = None,
        msg_type: Optional[MessageType] = None,
        last_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Gets filtered message history.
        """
        filtered_history = self.message_history

        if component:
            filtered_history = [
                msg for msg in filtered_history if msg["component"] == component
            ]

        if msg_type:
            filtered_history = [
                msg for msg in filtered_history if msg["type"] == msg_type.value
            ]

        if last_n:
            filtered_history = filtered_history[-last_n:]

        return filtered_history

    def clear_history(self):
        """Clears the message history."""
        self.message_history.clear()


# Global instance of the console handler
console_handler = ConsoleHandler()


# Updated convenience functions
def start_live_console(
    title: str = "NPM Stream Manager", subtitle: str = "Live Console"
):
    """Starts the live console with scroll"""
    console_handler.start_live_mode(title, subtitle)


def stop_live_console():
    """Stops the live console"""
    console_handler.stop_live_mode()


def show_message_history():
    """Shows the message history in scrollable format"""
    console_handler.show_scrollable_console()


def show_status_dashboard(components_status: Dict[str, Dict[str, Any]]):
    """Shows system status dashboard"""
    layout = console_handler.create_status_dashboard(components_status)
    console_handler.console.print(layout)


def ws_info(component: str, message: str, details: Optional[Dict[str, Any]] = None):
    """WebSocket informational message"""
    console_handler.print_message(
        component, message, MessageType.INFO, details, interpret_markup=True
    )
    ensure_log_file()
    append_to_log(
        f"[INFO] [{component}] {console_handler._strip_markup(message)} - {details if details else ''}"
    )


def ws_success(component: str, message: str, details: Optional[Dict[str, Any]] = None):
    """WebSocket success message"""
    console_handler.print_message(
        component, message, MessageType.SUCCESS, details, interpret_markup=True
    )
    ensure_log_file()
    append_to_log(
        f"[SUCCESS] [{component}] {console_handler._strip_markup(message)} - {details if details else ''}"
    )


def ws_warning(component: str, message: str, details: Optional[Dict[str, Any]] = None):
    """WebSocket warning message"""
    console_handler.print_message(
        component, message, MessageType.WARNING, details, interpret_markup=True
    )
    ensure_log_file()
    append_to_log(
        f"[WARNING] [{component}] {console_handler._strip_markup(message)} - {details if details else ''}"
    )


def ws_error(
    component: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    suggestions: Optional[List[str]] = None,
):
    """WebSocket error message"""
    if suggestions:
        console_handler.print_error_panel(component, "Error", message, suggestions)
        # Para paneles de error, también guardar el mensaje limpio
        clean_msg = console_handler._strip_markup(message)
    else:
        console_handler.print_message(
            component, message, MessageType.ERROR, details, interpret_markup=True
        )
        clean_msg = console_handler._strip_markup(message)
    ensure_log_file()
    append_to_log(f"[ERROR] [{component}] {clean_msg} - {details if details else ''}")


def ws_connection(
    component: str, uri: str, status: str, info: Optional[Dict[str, Any]] = None
):
    """WebSocket connection status"""
    console_handler.print_connection_status(component, uri, status, info)


def ws_ports(
    component: str, action: str, ports: List[Dict[str, Any]], info: Optional[str] = None
):
    """WebSocket port information"""
    console_handler.print_port_info(component, action, ports, info)


def ws_capabilities(component: str, uri: str, capabilities: Dict[str, Any]):
    """WebSocket server capabilities"""
    console_handler.print_server_capabilities(component, uri, capabilities)


def ws_status(component: str, status_data: Dict[str, Any]):
    """WebSocket status summary"""
    console_handler.print_status_summary(component, status_data)


def clear_console():
    """Clears the console"""
    console_handler.clear_console()
    """Clears the console"""
    console_handler.clear_console()
