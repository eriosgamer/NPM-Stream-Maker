import os
import re
import shutil
import subprocess
from collections import defaultdict
import sys
from rich.progress import Progress
from rich.console import Console

# Common keywords for ports
PORT_KEYWORDS = [
    'port', 'queryport', 'rconport', 'steamport', 'gameport', 'serverport'
]

# Regex to find lines with keywords and port numbers
PORT_REGEX = re.compile(
    r'(?i)\b(' + '|'.join(PORT_KEYWORDS) + r')\b[^0-9]{0,10}([0-9]{2,5})'
)

def buscar_puertos_en_archivo(filepath):
    # Find ports in file by keywords
    ports = defaultdict(set)
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            for match in PORT_REGEX.finditer(line):
                key = match.group(1).lower()
                port = int(match.group(2))
                ports[key].add(port)
    return ports

def agrupar_rangos(ports):
    # Group consecutive ports into ranges
    if not ports:
        return []
    ports = sorted(ports)
    ranges = []
    start = end = ports[0]
    for p in ports[1:]:
        if p == end + 1:
            end = p
        else:
            ranges.append((start, end))
            start = end = p
    ranges.append((start, end))
    return ranges

def clonar_repositorio(repo_url, destino, console):
    # Clone repository with progress bar
    if os.path.exists(destino):
        shutil.rmtree(destino)
    with Progress() as progress:
        task = progress.add_task("[cyan]Cloning AMPTemplates repository...", total=100)
        # Use subprocess to clone and show simulated progress
        process = subprocess.Popen(
            ["git", "clone", "--progress", repo_url, destino],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        percent = 0
        for line in process.stderr:
            if "Receiving objects" in line:
                # Extract percentage from the line
                match = re.search(r'(\d+)%', line)
                if match:
                    percent = int(match.group(1))
                    progress.update(task, completed=percent)
        process.wait()
        progress.update(task, completed=100)
    if process.returncode != 0:
        raise Exception("Error cloning AMPTemplates repository.")

def expandir_instancias_por_rango(ranges, max_instances=5):
    """
    Given a list of ranges [(start, end)], expand up to max_instances consecutive blocks.
    Example: [(12000,12005)] -> [12000,12001,...,12005,12006,12007,...,12011,...]
    """
    ports = set()
    used = set()
    for start, end in ranges:
        range_len = end - start + 1
        for i in range(max_instances):
            block_start = start + i * range_len
            block_end = block_start + range_len - 1
            block = set(range(block_start, block_end + 1))
            # Avoid overlaps
            if not block & used:
                ports.update(block)
                used.update(block)
    return ports

def expandir_instancias_por_puerto(ports, max_instances=5):
    """
    For single ports, expand up to max_instances consecutive ports for each base port.
    Avoid overlaps.
    """
    expanded_ports = set()
    used = set()
    for p in sorted(ports):
        block = set(p + i for i in range(max_instances))
        if not block & used:
            expanded_ports.update(block)
            used.update(block)
    return expanded_ports

def main():
    console = Console()
    console.rule("[bold blue]Port Scanner started")

    repo_url = "https://github.com/CubeCoders/AMPTemplates.git"
    repo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AMPTemplates")

    # Clone the repository with progress bar
    clonar_repositorio(repo_url, repo_dir, console)

    base_dir = repo_dir
    all_ports = defaultdict(set)

    # Collect all files to process
    files = []
    for root, _, filelist in os.walk(base_dir):
        for fname in filelist:
            fpath = os.path.join(root, fname)
            files.append(fpath)

    total_files = len(files)
    console.print(f"[bold cyan]Total files to read: {total_files}")

    with Progress() as progress:
        task = progress.add_task("[cyan]Processing files...", total=total_files)
        read_count = 0
        for fpath in files:
            ports = buscar_puertos_en_archivo(fpath)
            for key, portset in ports.items():
                all_ports[key].update(portset)
            read_count += 1
            progress.update(
                task,
                advance=1,
                description=f"[cyan]Processing: {os.path.basename(fpath)} ({read_count}/{total_files})"
            )

    # Expand ports for game instances (for each key)
    expanded_ports = set()
    for ports in all_ports.values():
        ports = list(ports)
        if not ports:
            continue
        if len(ports) == 1:
            # Single port, expand as individual
            expanded_ports.update(expandir_instancias_por_puerto(ports, max_instances=5))
        else:
            # Range, expand as blocks
            ranges = agrupar_rangos(ports)
            expanded_ports.update(expandir_instancias_por_rango(ranges, max_instances=5))

    unique_ports = sorted(expanded_ports)

    # Show all ports in a single line using OPNsense-compatible range format
    ranges = agrupar_rangos(unique_ports)
    console.rule("[bold green]Ports detected in all files (OPNsense range format)")
    opnsense_list = ','.join(
        f"{str(start).replace(' ', '')}:{str(end).replace(' ', '')}" if start != end else f"{str(start).replace(' ', '')}"
        for start, end in ranges
    )
    console.print(opnsense_list, style="bold yellow")

    # Save ports in plain text in ports.txt (range format, single line, no spaces)
    with open("ports.txt", "w") as f:
        f.write(opnsense_list)
    console.print(f"[bold green]ports.txt file generated in range format ({len(unique_ports)} ports).")

    # Delete the cloned repository
    try:
        shutil.rmtree(repo_dir)
        console.print(f"[bold red]AMPTemplates repository deleted.")
    except Exception as e:
        console.print(f"[red]Could not delete AMPTemplates repository: {e}")

    console.rule("[bold blue]Port Scanner finished")

if __name__ == "__main__":
    if os.environ.get("RUN_FROM_PANEL") != "1":
        print("This script must be run from Control_Panel.py")
        sys.exit(1)
    try:
        main()
    except Exception as e:
        Console().print(f"[red]Error: {e}[/red]")