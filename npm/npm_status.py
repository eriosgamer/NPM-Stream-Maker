import shutil
import subprocess
from rich.console import Console
import os
import sys

# Add the parent directory to the system path to allow imports from sibling modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import npm_handler as npmh
from Config import config as cfg
from UI.console_handler import ws_info, ws_error, ws_warning

console = Console()


def check_npm_install():
    """
    Checks if Nginx Proxy Manager is installed and running.
    If not installed, attempts to create the docker-compose.yml file.
    Displays the current status of the service.
    """
    # Check if docker-compose is installed
    if not shutil.which("docker-compose"):
        ws_error(
            "[NPM_INSTALL]",
            "docker-compose is not installed. Nginx Proxy Manager cannot be verified.",
        )
        return False
    return True


def check_npm():
    """
    Checks if Nginx Proxy Manager is installed and running.
    If not installed, attempts to create the docker-compose.yml file.
    Displays the current status of the service.
    """
    # Check if docker-compose is installed
    if not shutil.which("docker-compose"):
        ws_error(
            "[NPM_INSTALL]",
            "docker-compose is not installed. Nginx Proxy Manager cannot be verified.",
        )
        return False

    npm_dir = cfg.NGINX_BASE_DIR
    compose_file = os.path.join(npm_dir, "docker-compose.yml")

    # Check if docker-compose.yml exists in the NPM directory
    if not os.path.exists(compose_file):
        ws_warning(
            "[NPM_INSTALL]",
            "docker-compose.yml not found in ./npm. Nginx Proxy Manager is not installed.",
        )
        npmh.ensure_npm_compose_file()
        ws_info(
            "[NPM_INSTALL]",
            "docker-compose.yml created. Please start Nginx Proxy Manager with 'docker-compose up -d' in the ./npm directory.",
        )

    try:
        ws_info("[NPM_INSTALL]", "Checking the status of Nginx Proxy Manager...")
        result = subprocess.run(
            ["docker-compose", "ps", "--services", "--filter", "status=running"],
            cwd=npm_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        ws_info(
            "[NPM_INSTALL]", f"Result of docker-compose ps:\n{result.stdout.strip()}"
        )
        running_services = result.stdout.strip().splitlines()

        if running_services:
            ws_info("[NPM_INSTALL]", "Nginx Proxy Manager is running.")
            return True
        else:
            ws_warning(
                "[NPM_INSTALL]",
                "docker-compose.yml found, but Nginx Proxy Manager is not running.",
            )
            return False

    except Exception as e:
        ws_error(
            "[NPM_INSTALL]", f"Error checking the status of Nginx Proxy Manager: {e}"
        )
        return False


# ---------------------------------------------------------------------------------
# Module: npm_status.py
# Purpose: This module provides a function to check the installation and running
# status of Nginx Proxy Manager using docker-compose. It also attempts to create
# the docker-compose.yml file if it does not exist, and informs the user about
# the current state of the service.
# Usage: Import and call check_npm() to verify and manage Nginx Proxy Manager status.
# ---------------------------------------------------------------------------------
