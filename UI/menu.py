import sys
import os
from rich.console import Console

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


def show_main_menu():
    """
    Displays the main menu of the application with the available options.
    """
    # Check component availability
    npm_available = check_npm_availability()
    ws_uris_available = check_websocket_uris()

    # Print the menu header and options using Rich formatting
    console.print(
        "\n[bold blue]╔══════════════════════════════════════════════════════════════════╗")
    console.print(
        "[bold blue]║                    NPM Stream Manager                           ║")
    console.print(
        "[bold blue]╚══════════════════════════════════════════════════════════════════╝")
    console.print("\n[bold cyan]Select an option:[/bold cyan]")

    # Option 1 - Show existing streams (requires NPM)
    if npm_available:
        console.print("[bold green]1.[/bold green] Show existing streams")
    else:
        console.print("[bold red]1.[/bold red] Show existing streams [dim red](NPM required)[/dim red]")

    # Option 2 - Add streams manually (requires NPM)
    if npm_available:
        console.print("[bold green]2.[/bold green] Add streams manually")
    else:
        console.print("[bold red]2.[/bold red] Add streams manually [dim red](NPM required)[/dim red]")

    # Option 3 - Edit WebSocket URIs (always available)
    console.print("[bold green]3.[/bold green] Edit WebSocket URIs")

    # Option 4 - Clear all streams (requires NPM)
    if npm_available:
        console.print("[bold green]4.[/bold green] Clear all streams")
    else:
        console.print("[bold red]4.[/bold red] Clear all streams [dim red](NPM required)[/dim red]")

    # Option 5 - Start WebSocket Server (requires NPM capability)
    if npm_available:
        console.print("[bold green]5.[/bold green] Start WebSocket Server")
    else:
        console.print("[bold red]5.[/bold red] Start WebSocket Server [dim red](NPM required)[/dim red]")

    # Option 6 - Start WebSocket Client (requires WebSocket URIs)
    if ws_uris_available:
        console.print("[bold green]6.[/bold green] Start WebSocket Client")
    else:
        console.print("[bold red]6.[/bold red] Start WebSocket Client [dim red](WebSocket URIs required)[/dim red]")

    # Option 7 - Remote Control Menu (requires WebSocket URIs)
    if ws_uris_available:
        console.print("[bold green]7.[/bold green] Remote Control Menu")
    else:
        console.print("[bold red]7.[/bold red] Remote Control Menu [dim red](WebSocket URIs required)[/dim red]")

    console.print("[bold green]0.[/bold green] Exit")

    try:
        choice = input("\n[?] Enter your choice: ")
        return choice.strip()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Exiting...[/bold yellow]")
        sys.exit(0)
        return


def handle_choice(choice):
    """
    Executes the corresponding action according to the selected option in the main menu.
    """
    # Check component availability
    npm_available = check_npm_availability()
    ws_uris_available = check_websocket_uris()

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
        console.print("[bold green]Goodbye![/bold green]")
        sys.exit(0)
    else:
        console.print("[bold red]Invalid choice. Please try again.[/bold red]")
        input("\nPress Enter to continue...")


# End of menu.py
# This file provides the main menu interface and dispatches user choices to the appropriate modules.
