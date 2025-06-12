import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.layout import Layout
from rich.live import Live
import time

# Add platform-specific imports for key handling
if os.name == 'nt':  # Windows
    import msvcrt
else:  # Unix/Linux/macOS
    import termios
    import tty

# Add the parent directory to sys.path to allow module imports from other folders
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Streams import stream_handler as sh
from Streams import stream_cleaning as sc
from Remote import remote_stream_add, remote_control
from ports import port_scanner as ps
from UI import uri_menu
from Server import ws_server
from Client import ws_client
from WebSockets import diagnostics
from npm import npm_status as npms
from Remote import extra_utils as ex_util


# Initialize Rich console for colored terminal output
console = Console()

def clear_console():
    """
    Clear the console screen.
    """
    os.system('cls' if os.name == 'nt' else 'clear')

def get_key():
    """
    Get a single key press from the user in a cross-platform way.
    """
    if os.name == 'nt':  # Windows
        key = msvcrt.getch()
        if key == b'\xe0':  # Special key prefix on Windows
            key = msvcrt.getch()
            if key == b'H':  # Up arrow
                return 'up'
            elif key == b'P':  # Down arrow
                return 'down'
        elif key == b'\r':  # Enter key
            return 'enter'
        elif key == b'\x1b':  # Escape key
            return 'esc'
    else:  # Unix/Linux/macOS
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            key = sys.stdin.read(1)
            if key == '\x1b':  # Escape sequence
                key += sys.stdin.read(2)
                if key == '\x1b[A':  # Up arrow
                    return 'up'
                elif key == '\x1b[B':  # Down arrow
                    return 'down'
                elif len(key) == 1:  # Just escape
                    return 'esc'
            elif key == '\r' or key == '\n':  # Enter key
                return 'enter'
            elif key == '\x1b':  # Escape key
                return 'esc'
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    return None

def check_npm_availability():
    """
    Check if NPM is running and accessible.
    """
    try:
        return npms.check_npm()
    except:
        return False


def check_websocket_uris():
    """
    Check if WebSocket URIs are defined.
    """
    try:
        uris = diagnostics.get_ws_uris_and_tokens()
        return len(uris) > 0
    except:
        return False


def get_terminal_size():
    """
    Get the current terminal size.
    """
    return console.size

def create_header():
    """
    Create the header panel.
    """
    header_text = Text("NPM Stream Manager", style="bold blue", justify="center")
    return Panel(
        Align.center(header_text),
        style="bold blue",
        padding=(0, 2),
        height=3
    )

def create_footer():
    """
    Create the footer panel with controls.
    """
    help_text = Text.assemble(
        ("Navigation: ", "bold cyan"),
        ("↑↓ ", "bold yellow"), ("Move  ", "white"),
        ("Enter ", "bold yellow"), ("Select  ", "white"),
        ("Esc ", "bold yellow"), ("Exit", "white")
    )
    return Panel(
        Align.center(help_text),
        title="[bold cyan]Controls[/bold cyan]",
        style="cyan",
        padding=(0, 2),
        height=3
    )

def create_menu_content(menu_options, selected_index, terminal_height):
    """
    Create the menu content that fits in the available space.
    """
    # Calculate available height for menu content
    # Header (3) + Footer (3) + some padding = 8 lines reserved
    available_height = terminal_height - 8
    
    content = []
    content.append("[bold cyan]Menu Options:[/bold cyan]\n")
    
    for i, (option_text, available, requirement) in enumerate(menu_options):
        prefix = "► " if i == selected_index else "  "
        
        if available:
            if i == selected_index:
                content.append(f"[bold yellow]{prefix}[/bold yellow][bold green]{option_text}[/bold green]")
            else:
                content.append(f"[green]{prefix}{option_text}[/green]")
        else:
            if i == selected_index:
                content.append(f"[bold yellow]{prefix}[/bold yellow][bold red]{option_text}[/bold red] [dim red]({requirement})[/dim red]")
            else:
                content.append(f"[red]{prefix}{option_text}[/red] [dim red]({requirement})[/dim red]")
    
    # Add padding lines if needed to center content vertically
    content_lines = len(content)
    if content_lines < available_height:
        padding_lines = (available_height - content_lines) // 2
        content = [""] * padding_lines + content + [""] * padding_lines
    
    return "\n".join(content)

def show_main_menu():
    """
    Displays the main menu of the application with navigation by arrow keys and adaptive layout.
    """
    # Check component availability
    npm_available = check_npm_availability()
    ws_uris_available = check_websocket_uris()
    
    # Define menu options with their availability status
    menu_options = [
        ("Show existing streams", npm_available, "NPM required"),
        ("Add streams manually", npm_available, "NPM required"),
        ("Edit WebSocket URIs", True, ""),
        ("Clear all streams", npm_available, "NPM required"),
        ("Start WebSocket Server", npm_available, "NPM required"),
        ("Start WebSocket Client", ws_uris_available, "WebSocket URIs required"),
        ("Remote Control Menu", ws_uris_available, "WebSocket URIs required"),
        ("Exit", True, "")
    ]
    
    selected_index = 0
    
    while True:
        clear_console()
        
        # Get current terminal size
        terminal_width, terminal_height = get_terminal_size()
        
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(create_header(), name="header", size=3),
            Layout(name="main"),
            Layout(create_footer(), name="footer", size=3)
        )
        
        # Create menu content
        menu_content = create_menu_content(menu_options, selected_index, terminal_height)
        layout["main"].update(Panel(menu_content, style="white", padding=(1, 2)))
        
        # Print the layout
        console.print(layout)
        
        # Handle keyboard input
        try:
            key = get_key()
            if key == 'up':
                selected_index = (selected_index - 1) % len(menu_options)
            elif key == 'down':
                selected_index = (selected_index + 1) % len(menu_options)
            elif key == 'enter':
                return str(selected_index + 1) if selected_index < len(menu_options) - 1 else "0"
            elif key == 'esc':
                return "0"
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Exiting...[/bold yellow]")
            sys.exit(0)

def handle_choice(choice):
    """
    Executes the corresponding action according to the selected option in the main menu.
    """
    # Check component availability
    npm_available = check_npm_availability()
    ws_uris_available = check_websocket_uris()
    
    clear_console()

    if choice == "1":
        if npm_available:
            console.print("[bold cyan]Showing existing streams...[/bold cyan]")
            sh.show_streams()
        else:
            console.print("[bold red]NPM is not available. Please start NPM first.[/bold red]")
        input("\nPress Enter to continue...")
    elif choice == "2":
        if npm_available:
            remote_stream_add.add_streams_manually()
        else:
            console.print("[bold red]NPM is not available. Please start NPM first.[/bold red]")
            input("\nPress Enter to continue...")
    elif choice == "3":
        uri_menu.edit_ws_uris_menu(console)
    elif choice == "4":
        if npm_available:
            sc.clear_all_streams()
        else:
            console.print("[bold red]NPM is not available. Please start NPM first.[/bold red]")
            input("\nPress Enter to continue...")
    elif choice == "5":
        if npm_available:
            # Set environment variable to indicate running from panel
            os.environ["RUN_FROM_PANEL"] = "1"
            ws_server.start_ws_server()
        else:
            console.print("[bold red]NPM is not available. Please start NPM first.[/bold red]")
            input("\nPress Enter to continue...")
    elif choice == "6":
        if ws_uris_available:
            ws_client.start_ws_client()
        else:
            console.print("[bold red]No WebSocket URIs defined. Please configure WebSocket URIs first.[/bold red]")
            input("\nPress Enter to continue...")
    elif choice == "7":
        if ws_uris_available:
            remote_control.start_remote_control()
        else:
            console.print("[bold red]No WebSocket URIs defined. Please configure WebSocket URIs first.[/bold red]")
            input("\nPress Enter to continue...")
    elif choice == "0":
        clear_console()
        console.print("[bold green]Goodbye![/bold green]")
        sys.exit(0)
    else:
        console.print("[bold red]Invalid choice. Please try again.[/bold red]")
        input("\nPress Enter to continue...")

# End of menu.py
# This file provides the main menu interface and dispatches user choices to the appropriate modules.
