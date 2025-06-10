import shutil
import subprocess
from rich.console import Console
import os
import sys

# Add the parent directory to the system path to allow imports from sibling modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import npm_handler as npmh
from Config import config as cfg

console = Console()


def check_npm():
    """
    Checks if Nginx Proxy Manager is installed and running.
    If not installed, attempts to create the docker-compose.yml file.
    Displays the current status of the service.
    """
    # Check if docker-compose is installed
    if not shutil.which("docker-compose"):
        console.print(
            "[red]docker-compose is not installed. Nginx Proxy Manager cannot be verified.[/red]")
        return False

    npm_dir = cfg.NGINX_BASE_DIR
    compose_file = os.path.join(npm_dir, "docker-compose.yml")

    # Check if docker-compose.yml exists in the NPM directory
    if not os.path.exists(compose_file):
        console.print(
            "[yellow]docker-compose.yml not found in ./npm. Nginx Proxy Manager is not installed.[/yellow]")
        npmh.ensure_npm_compose_file()
        console.print(
            "[green]docker-compose.yml created. Please start Nginx Proxy Manager with 'docker-compose up -d' in the ./npm directory.[/green]")

    try:
        console.print(
            "[cyan]Checking the status of Nginx Proxy Manager...[/cyan]")
        result = subprocess.run(
            ["docker-compose", "ps", "--services", "--filter", "status=running"],
            cwd=npm_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        console.print(
            f"[cyan]Result of docker-compose ps:\n{result.stdout.strip()}[/cyan]")
        running_services = result.stdout.strip().splitlines()

        if running_services:
            console.print(
                "[green]Nginx Proxy Manager is running.[/green]")
            return True
        else:
            console.print(
                "[yellow]docker-compose.yml found, but Nginx Proxy Manager is not running.[/yellow]")
            return False

    except Exception as e:
        console.print(
            f"[red]Error checking the status of Nginx Proxy Manager: {e}[/red]")
        return False

# ---------------------------------------------------------------------------------
# Module: npm_status.py
# Purpose: This module provides a function to check the installation and running
# status of Nginx Proxy Manager using docker-compose. It also attempts to create
# the docker-compose.yml file if it does not exist, and informs the user about
# the current state of the service.
# Usage: Import and call check_npm() to verify and manage Nginx Proxy Manager status.
# ---------------------------------------------------------------------------------
