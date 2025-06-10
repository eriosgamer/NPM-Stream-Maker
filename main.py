import argparse
import logging
import os
import sys

# Add the parent directory to sys.path to allow importing modules from parent folders
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Config import script_loader as sl  # Import script loader utility
from UI import menu  # Import menu UI module

from rich.console import Console

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

console = Console()

# Configure logging to display info level logs with timestamp, level, and message
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")


def main():
    """
    Main entry point for the application.
    Handles command-line arguments and launches the appropriate scripts or menu.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--ws-client-only", action="store_true",
                        help="Run only ws_client.py without dependency checks")
    parser.add_argument("--ws-server-only", action="store_true",
                        help="Run only ws_server.py without dependency checks")
    args = parser.parse_args()

    if args.ws_client_only:
        # Run only the WebSocket client script
        sl.run_script("ws_client.py")
        return
    elif args.ws_server_only:
        # Run only the WebSocket server script
        sl.run_script("ws_server.py")
        return
    
    # Show the main menu in a loop and handle user choices
    while True:
        choice = menu.show_main_menu()
        menu.handle_choice(choice)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("")
        # Print message when process is interrupted by the user
        console.print(
            "[bold red]Process interrupted by user.[/bold red]")
        sys.exit(0)
    except Exception as e:
        # Print any unexpected error
        console.print(f"[red]Error: {e}[/red]")
