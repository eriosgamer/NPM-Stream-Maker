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
from ports import conflict_handler
from WebSockets import diagnostics


# Initialize Rich console for colored terminal output
console = Console()


def show_main_menu():
    """
    Displays the main menu of the application with the available options.
    """
    # Print the menu header and options using Rich formatting
    console.print(
        "\n[bold blue]╔══════════════════════════════════════════════════════════════════╗")
    console.print(
        "[bold blue]║                    NPM Stream Manager                           ║")
    console.print(
        "[bold blue]╚══════════════════════════════════════════════════════════════════╝")
    console.print("\n[bold cyan]Select an option:[/bold cyan]")
    console.print("[bold green]1.[/bold green] Show existing streams")
    console.print("[bold green]2.[/bold green] Add streams manually")
    console.print("[bold green]3.[/bold green] Edit WebSocket URIs")
    console.print("[bold green]4.[/bold green] Clear all streams")
    console.print("[bold green]5.[/bold green] Start WebSocket Server")
    console.print("[bold green]6.[/bold green] Start WebSocket Client")
    console.print("[bold green]7.[/bold green] Run Port Scanner")
    console.print("[bold green]8.[/bold green] WebSocket Diagnostic")
    console.print(
        "[bold green]9.[/bold green] Show conflict resolution summary")
    console.print("[bold green]10.[/bold green] Remote Control Menu")  # NEW
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
    if choice == "1":
        console.print("[bold cyan]Showing existing streams...[/bold cyan]")
        sh.show_streams()
    elif choice == "2":
        remote_stream_add.add_streams_manually()
    elif choice == "3":
        uri_menu.edit_ws_uris_menu(console)
    elif choice == "4":
        sc.clear_all_streams()
    elif choice == "5":
        # Set environment variable to indicate running from panel
        os.environ["RUN_FROM_PANEL"] = "1"
        ws_server.start_ws_server()
    elif choice == "6":
        ws_client.start_ws_client()
    elif choice == "7":
        run_port_scanner()
    elif choice == "8":
        diagnostics.show_websocket_diagnostic()
        input("\nPress Enter to continue...")
    elif choice == "9":
        conflict_handler.show_conflict_summary()
    elif choice == "10":  # NEW
        remote_control.start_remote_control()
    elif choice == "0":
        console.print("[bold green]Goodbye![/bold green]")
        sys.exit(0)
    else:
        console.print("[bold red]Invalid choice. Please try again.[/bold red]")
        input("\nPress Enter to continue...")


def run_port_scanner():
    """
    Runs the port scanner and displays the results.
    """
    try:
        console.print("[bold cyan]Running Port Scanner...[/bold cyan]")
        result = ps.get_listening_ports_with_proto()
        if result:
            console.print("[bold green]Port Scanner completed successfully![/bold green]")
        else:
            console.print("[bold red]Port Scanner failed.[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Error running Port Scanner: {e}[/bold red]")
    input("\nPress Enter to continue...")


# End of menu.py
# This file provides the main menu interface and dispatches user choices to the appropriate modules.
