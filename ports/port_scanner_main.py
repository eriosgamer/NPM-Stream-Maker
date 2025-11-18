from rich.progress import Progress
from rich.console import Console
import re
import shutil
import json
import time
import sys
import os
from collections import defaultdict
from dotenv import load_dotenv

# Add the parent directory to sys.path to allow importing local modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from npm import git_utils
from Client import port_file_reader as pfr
from Client import steam_ports as sp
from UI.console_handler import ws_info, ws_error, ws_warning

load_dotenv()


def gen_ports_file():
    """
    Main function for the port scanner.
    Clones AMP templates, extracts ports, expands them, and generates output files.
    Shows a summary and deletes the cloned repository at the end.
    """
    console = Console()
    console.rule("[bold blue]Port Scanner started")

    # URL of the AMPTemplates repository to clone
    repo_url = "https://github.com/CubeCoders/AMPTemplates.git"
    # Directory where the repository will be cloned
    repo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AMPTemplates")

    # Clone and process AMPTemplates repository
    git_utils.repo_clone(repo_url, repo_dir)

    all_ports = defaultdict(set)  # Dictionary to store all found ports

    # Collect all files to process from the cloned repository
    files = []
    for root, _, filelist in os.walk(repo_dir):
        for fname in filelist:
            fpath = os.path.join(root, fname)
            files.append(fpath)

    total_files = len(files)
    ws_info("[PORT_SCANNER]", f"Total files to read: {total_files}")

    # Process each file and extract ports using a progress bar
    with Progress() as progress:
        task = progress.add_task("[cyan]Processing files...", total=total_files)
        read_count = 0
        for fpath in files:
            # Search for ports in the current file
            ports = pfr.search_ports_in_file(fpath)
            for key, portset in ports.items():
                all_ports[key].update(portset)
            read_count += 1
            progress.update(
                task,
                advance=1,
                description=f"[cyan]Processing: {os.path.basename(fpath)} ({read_count}/{total_files})",
            )

    # Expand ports for game instances (for each key)
    expanded_ports = set()
    all_alternative_ports = set()
    for ports in all_ports.values():
        ports = list(ports)
        if not ports:
            continue
        if len(ports) == 1:
            # Single port, expand as individual
            expanded_ports.update(pfr.expand_instances_per_port(ports, max_instances=5))
        else:
            # Range, expand as blocks and alternative incoming ports
            ranges = pfr.group_ranges(ports)
            # Collect both main and alternative ports
            ports_this_range = pfr.expand_instances_per_range(
                ranges, max_instances=5, use_alternative_ranges=True
            )
            expanded_ports.update(ports_this_range)
            all_alternative_ports.update(ports_this_range)

    # --- Add common Steam ports if not already present ---
    steam_ports = sp.get_common_steam_ports()
    expanded_ports.update(steam_ports)
    all_alternative_ports.update(steam_ports)

    unique_ports = sorted(expanded_ports)
    unique_alternative_ports = sorted(all_alternative_ports)

    # Show all ports in a single line using OPNsense-compatible range format
    ranges = pfr.group_ranges(unique_ports)
    alt_ranges = pfr.group_ranges(unique_alternative_ports)
    console.rule("[bold green]Ports detected in all files (OPNsense range format)")
    opnsense_list = ",".join(
        (
            f"{str(start).replace(' ', '')}:{str(end).replace(' ', '')}"
            if start != end
            else f"{str(start).replace(' ', '')}"
        )
        for start, end in ranges
    )
    opnsense_alt_list = ",".join(
        (
            f"{str(start).replace(' ', '')}:{str(end).replace(' ', '')}"
            if start != end
            else f"{str(start).replace(' ', '')}"
        )
        for start, end in alt_ranges
    )
    ws_info("[PORT_SCANNER]", "[yellow]OPNsense: [/yellow]")
    ws_info("[PORT_SCANNER]", opnsense_alt_list)

    # Save ports in plain text in ports.txt (range format, single line, no spaces)
    with open("ports.txt", "w") as f:
        f.write(opnsense_alt_list)

    # Create a metadata file with generation info
    metadata = {
        "generated_on": time.time(),
        "generated_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_ports": len(unique_alternative_ports),
        "port_ranges": len(alt_ranges),
        "amp_templates_processed": total_files,
        "steam_game_ports_included": len(steam_ports),
        "version": "2.0",
    }

    with open("ports_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Verify the file was written correctly
    file_size = os.path.getsize("ports.txt")
    ws_info("[PORT_SCANNER]", f"ports.txt file generated successfully!")
    ws_info("[PORT_SCANNER]", f"Generated on: {metadata['generated_date']}")
    ws_info("[PORT_SCANNER]", f"File size: {file_size} bytes")
    ws_info("[PORT_SCANNER]", f"Total unique ports: {len(unique_alternative_ports)}")
    ws_info("[PORT_SCANNER]", f"Port ranges: {len(alt_ranges)}")
    ws_info("[PORT_SCANNER]", f"AMP templates processed: {total_files}")
    ws_info("[PORT_SCANNER]", f"Steam/game ports included: {len(steam_ports)}")

    # Show a preview of the content
    with open("ports.txt", "r") as f:
        content_preview = f.read(200)  # First 200 chars
    ws_info("[PORT_SCANNER]", f"[bold yellow]Content preview: {content_preview}...")

    # Delete the cloned repository to clean up
    try:
        shutil.rmtree(repo_dir)
        ws_info("[PORT_SCANNER]", f"[bold red]AMPTemplates repository deleted.")
    except Exception as e:
        ws_error(
            "[PORT_SCANNER]", f"[red]Could not delete AMPTemplates repository: {e}"
        )

    console.rule("[bold blue]Port Scanner finished")
    return True
