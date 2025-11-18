import argparse
import logging
import os
import sys
import asyncio

# Add the parent directory to sys.path to allow importing modules from parent folders
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from UI import menu  # Import menu UI module
from Server.ws_server import start_ws_server
from Config import config as cfg
from Client import ws_client
from UI.console_handler import ws_info, ws_error

from rich.console import Console

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

console = Console()

# Configure logging to display info level logs with timestamp, level, and message
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    """
    Main entry point for the application.
    Handles command-line arguments and launches the appropriate scripts or menu.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ws-client-only",
        action="store_true",
        help="Run only ws_client without dependency checks",
    )
    parser.add_argument(
        "--ws-server-only",
        action="store_true",
        help="Run only ws_server without dependency checks",
    )
    parser.add_argument(
        "--ws-server-port",
        type=int,
        default=8765,
        help="Port for WebSocket server (default: 8765)",
    )

    args = parser.parse_args()

    # Set WebSocket server port in config
    cfg.WS_SERVER_PORT = args.ws_server_port

    try:
        if args.ws_client_only:
            # Run only the WebSocket client script
            ws_info("WS_CLIENT", "Starting WebSocket client...")
            ws_client.start_ws_client()
            return
        elif args.ws_server_only:
            # Run only the WebSocket server script
            ws_info("WS_SERVER", f"Starting WebSocket server on port {args.ws_server_port}...")
            os.environ["RUN_FROM_PANEL"] = "1"  # Set required environment variable
            start_ws_server()
            return

        # Show the main menu in a loop and handle user choices
        while True:
            choice = menu.show_main_menu()
            menu.handle_choice(choice)

    except KeyboardInterrupt:
        console.print("")
        # Print message when process is interrupted by the user
        ws_info("[WS_CLIENT]", "[bold red]Process interrupted by user.[/bold red]")
        sys.exit(0)
    except Exception as e:
        # Print any unexpected error
        ws_error("[MAIN]", f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
