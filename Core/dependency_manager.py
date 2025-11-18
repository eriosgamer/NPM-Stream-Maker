import shutil
import sys
from rich.prompt import Prompt
import os

# Add the parent directory to sys.path to allow importing config from Config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from rich.console import Console
from UI.console_handler import ws_info, ws_error

console = Console()


def get_missing_dependencies():
    """
    Returns a set with the names of the required commands that are missing in the system.
    Iterates over the REQUIRED_COMMANDS defined in the config and checks if each command is available.
    """
    missing = []
    for name, cmd in cfg.REQUIRED_COMMANDS:
        if not shutil.which(cmd):
            missing.append(name)
    return set(missing)


def show_missing_deps_message(missing):
    """
    Displays a detailed message about the missing dependencies and how to install them.
    Shows installation tips based on the operating system.
    """
    console.rule("[bold red]Missing dependencies")
    ws_error(
        "[WS_DEPENDENCY]",
        f"The following required commands are missing: [bold]{', '.join(missing)}[/bold]",
    )
    ws_info(
        "[WS_DEPENDENCY]",
        "[yellow]Please install the missing commands before continuing.[/yellow]",
    )
    # Installation tips for each dependency and OS
    tips = {
        "git": {
            "Linux": "sudo apt install git  # or sudo yum install git",
            "macOS": "brew install git",
            "Windows": "Download from https://git-scm.com/download/win",
        },
        "docker": {
            "Linux": "sudo apt install docker.io  # or follow the official guide at https://docs.docker.com/engine/install/",
            "macOS": "brew install --cask docker",
            "Windows": "Download Docker Desktop from https://www.docker.com/products/docker-desktop/",
        },
        "docker-compose": {
            "Linux": "sudo apt install docker-compose  # or pip install docker-compose",
            "macOS": "brew install docker-compose",
            "Windows": "Included in Docker Desktop",
        },
        "python3": {
            "Linux": "sudo apt install python3",
            "macOS": "brew install python",
            "Windows": "Download from https://www.python.org/downloads/windows/",
        },
    }
    # Detect the current OS for installation tips
    os_tip = "Linux"
    if sys.platform.startswith("darwin"):
        os_tip = "macOS"
    elif sys.platform.startswith("win"):
        os_tip = "Windows"
    ws_info("[WS_DEPENDENCY]", "[bold cyan]Quick install tips:[/bold cyan]")
    for dep in missing:
        if dep in tips and os_tip in tips[dep]:
            ws_info(
                "[WS_DEPENDENCY]",
                f"[bold]{dep}[/bold] on {os_tip}: [green]{tips[dep][os_tip]}[/green]",
            )
    Prompt.ask("\n[bold cyan]Press ENTER to return to the menu...")
