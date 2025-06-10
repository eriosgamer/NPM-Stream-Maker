"""
stream_cleaning.py

This module provides utilities for cleaning up all stream-related data, including:
- Deleting all stream configuration files (NGINX .conf files)
- Clearing the streams database
- Removing conflict resolution files
- Handling NPM (NGINX Proxy Manager) operations (stop/reload) depending on Docker availability and execution context

Intended for use in both manual (Control Panel) and automated (server-side) scenarios.
"""

import os
import subprocess
import sys

from rich.console import Console
from rich.prompt import Prompt

# Add parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Core import dependency_manager as dep_manager
from ports import ports_utils as pu
from Config import config as cfg
from Streams import stream_db_handler as db_handler
from npm import npm_handler as npmh
from ports import conflict_cleaner as cf_clean
from npm import npm_handler as npm

console = Console()

def clear_all_streams():
    """
    Deletes all streams and related data.
    Includes cleaning up conflict resolution files and stopping NPM if applicable.
    Intended for use from the Control Panel.
    """
    console.rule("[bold red]Clear All Streams")

    # Ask for confirmation before proceeding with destructive operation
    confirm = Prompt.ask(
        "[bold red]⚠️  This will delete ALL streams and conflict resolution data. Are you sure?[/bold red]",
        choices=["yes", "no"],
        default="yes"
    )

    if confirm != "yes":
        console.print("[bold yellow]Operation cancelled[/bold yellow]")
        input("\nPress Enter to continue...")
        return

    try:
        # Clear conflict resolution files first
        pu.clear_conflict_resolution_files()

        # Prepare environment variables for subprocesses
        env = os.environ.copy()
        env["RUN_FROM_PANEL"] = "1"

        # Check if Docker is available for optional NPM operations
        missing_deps = dep_manager.get_missing_dependencies()
        docker_available = "docker" not in missing_deps and "docker-compose" not in missing_deps
        env["DOCKER_AVAILABLE"] = "1" if docker_available else "0"

        console.print(
            "[bold cyan]🧹 Cleaning all streams and stopping NPM...[/bold cyan]")
        # Stop NPM if Docker is available, otherwise skip
        npm.stop_npm() if docker_available else console.print(
            "[bold yellow]📋 Docker not available - NPM operations were skipped[/bold yellow]")
        console.print(
            "[bold cyan]🗑️  Clearing streams database...[/bold cyan]")
        db_handler.clean_streams_database()
        console.print(
            "[bold cyan]🗂️  Cleaning stream configuration files...[/bold cyan]")
        clean_stream_configurations()

    except Exception as e:
        console.print(f"[bold red]❌ Error clearing streams: {e}[/bold red]")

    input("\nPress Enter to continue...")


def clean_stream_configurations():
    """
    Deletes all stream configuration files (NGINX .conf files).
    Creates the directory if it does not exist.
    """
    try:
        # Check if the NGINX stream directory exists
        if not os.path.exists(cfg.NGINX_STREAM_DIR):
            console.print("[bold cyan][INFO][/bold cyan] NGINX stream directory does not exist - creating it for future use")
            try:
                os.makedirs(cfg.NGINX_STREAM_DIR, exist_ok=True)
                console.print(f"[bold green][OK][/bold green] Created directory: {cfg.NGINX_STREAM_DIR}")
            except Exception as e:
                console.print(f"[bold yellow][WARNING][/bold yellow] Could not create directory {cfg.NGINX_STREAM_DIR}: {e}")
            return

        # List all files in the directory
        all_files = os.listdir(cfg.NGINX_STREAM_DIR)
        conf_files = [f for f in all_files if f.endswith('.conf')]

        if not conf_files:
            console.print(f"[bold cyan][INFO][/bold cyan] No .conf files found in {cfg.NGINX_STREAM_DIR} (directory has {len(all_files)} total files)")
            return

        console.print(f"[bold cyan][INFO][/bold cyan] Found {len(conf_files)} stream configuration files to remove")

        cleaned_count = 0
        failed_count = 0

        # Attempt to remove each .conf file
        for filename in conf_files:
            file_path = os.path.join(cfg.NGINX_STREAM_DIR, filename)
            try:
                os.remove(file_path)
                cleaned_count += 1
                console.print(f"[bold green][OK][/bold green] Removed: {filename}")
            except Exception as e:
                failed_count += 1
                console.print(f"[bold red][ERROR][/bold red] Could not remove {filename}: {e}")

        console.print(f"[bold green][OK][/bold green] Successfully cleaned {cleaned_count} stream configuration files")
        if failed_count > 0:
            console.print(f"[bold yellow][WARNING][/bold yellow] Failed to remove {failed_count} configuration files")

    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Error cleaning stream configurations: {e}")


def clean_all_streams():
    """
    Cleans all streams from the database and configuration files.
    Also cleans additional state files and handles NPM operations depending on context.
    Intended for use in automated scenarios (e.g., from ws_server).
    """
    docker_available = os.environ.get("DOCKER_AVAILABLE", "0") == "1"
    run_from_panel = os.environ.get("RUN_FROM_PANEL") == "1"

    print("[INFO] Starting comprehensive stream cleanup...")
    print(f"[INFO] Docker available: {docker_available}")
    print(f"[INFO] Run from panel: {run_from_panel}")

    try:
        # Step 1: Clean conflict resolution data first
        print("\n[STEP 1] Cleaning conflict resolution data...")
        try:
            cleared_count = cf_clean.clear_all_conflict_resolution_data()
            if cleared_count > 0:
                print(f"[OK] Cleared {cleared_count} conflict resolution files")
            else:
                print("[INFO] No conflict resolution files found to clear")
        except ImportError as e:
            print(f"[WARNING] Could not import Stream_Manager: {e}")
            # Fallback: manually clear files

            cleared_count = 0
            for file_path in cfg.CONFLICT_FILES:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        cleared_count += 1
                        print(f"[OK] Removed: {file_path}")
                except Exception as e:
                    print(f"[ERROR] Could not remove {file_path}: {e}")
            print(f"[OK] Manually cleared {cleared_count} conflict resolution files")
        except Exception as e:
            print(f"[ERROR] Could not clear conflict resolution data: {e}")

        # Step 2: Clean database (only if it exists)
        print("\n[STEP 2] Cleaning streams database...")
        db_handler.clean_streams_database()

        # Step 3: Clean configuration files (only if directory exists)
        print("\n[STEP 3] Cleaning stream configuration files...")
        clean_stream_configurations()

        # Step 4: Additional cleanup of state files that might not be covered
        print("\n[STEP 4] Cleaning additional state files...")

        cleaned_additional = 0
        found_additional = 0

        # Attempt to remove any additional conflict files listed in config
        for file_path in cfg.CONFLICT_FILES:
            try:
                if os.path.exists(file_path):
                    found_additional += 1
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    cleaned_additional += 1
                    print(f"[OK] Removed: {file_path} ({file_size} bytes)")
                else:
                    print(f"[INFO] File not found (already clean): {file_path}")
            except Exception as e:
                print(f"[ERROR] Could not remove {file_path}: {e}")

        if found_additional > 0:
            print(f"[OK] Successfully cleaned {cleaned_additional}/{found_additional} additional state files")
        else:
            print("[INFO] No additional state files found to clean")

        # Step 5: Handle NPM operations based on context
        print("\n[STEP 5] Handling NPM operations...")
        if docker_available:
            try:
                if run_from_panel:
                    # When run from Control Panel: only stop NPM, don't restart
                    print("[INFO] Running from Control Panel - stopping NPM without restart")
                    npmh.stop_npm()
                    print("[OK] NPM stopped successfully")
                    print("[INFO] NPM will need to be manually restarted when ready to use streams again")
                else:
                    # When run automatically (e.g., from ws_server): reload NPM
                    print("[INFO] Running automatically - reloading NPM")
                    npmh.reload_npm()
                    print("[OK] NPM reloaded successfully")
            except Exception as e:
                print(f"[WARNING] Could not handle NPM operations: {e}")
        else:
            print("[INFO] Docker not available - NPM operations skipped")

        print("\n" + "="*60)
        if run_from_panel:
            print("[SUCCESS] All streams and conflict resolutions cleaned successfully!")
            print("[INFO] NPM has been stopped. Restart manually when ready to use streams again.")
        else:
            print("[SUCCESS] All streams and conflict resolutions cleaned and NPM reloaded!")
        print("="*60)

    except Exception as e:
        print(f"\n[FATAL ERROR] Error during complete cleanup: {e}")
        raise
