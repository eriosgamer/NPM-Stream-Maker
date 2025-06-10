"""
port_scanner.py

This module provides utilities to detect open/listening ports on the local machine,
distinguishing between TCP and UDP protocols. It uses different detection methods
depending on the operating system (Windows or Linux/Unix). It also includes logic
to process newly detected ports, interact with remote servers for conflict resolution,
and update client assignments, including integration with WireGuard servers.

Dependencies:
- rich.console for colored console output
- Core.id_tools for server discovery
- Client.server_querys for server communication
- Config.config for client assignments
- Client.ws_client for assignment persistence
- Wireguard.wireguard_tools for WireGuard integration
"""

import sys
import os
import subprocess
import re
from rich.console import Console

console = Console()

# Add parent directory to sys.path to allow relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Core import id_tools
from Client import server_querys as sq
from Config import config as cfg
from Client import ws_client
from Wireguard import wireguard_tools as wg_tools


def get_listening_ports_with_proto():
    """
    Returns a list of tuples (port, protocol) for listening ports.
    The protocol can be 'tcp' or 'udp'.
    Uses different methods depending on the operating system to detect open ports.
    """
    ports = set()
    try:
        if sys.platform.startswith("win"):
            # Windows: use netstat -anob for better UDP detection
            try:
                output = subprocess.check_output(
                    ["netstat", "-anob"], text=True, encoding="utf-8", errors="ignore")

                current_process = None
                for line in output.splitlines():
                    line = line.strip()

                    # Check for process name lines (they start with bracket)
                    if line.startswith("[") and line.endswith("]"):
                        current_process = line[1:-1]  # Remove brackets
                        continue

                    # TCP ports - look for LISTENING
                    if "LISTENING" in line and line.startswith("TCP"):
                        match = re.search(r':(\d+)', line)
                        if match:
                            port = int(match.group(1))
                            ports.add((port, "tcp"))
                            console.print(
                                f"[bold blue][PORT_DETECTION][/bold blue] Found TCP listening port: {port} [{current_process}]")

                    # UDP ports - look for any UDP binding (including game servers)
                    elif line.startswith("UDP") and "*:*" in line:
                        match = re.search(r':(\d+)', line)
                        if match:
                            port = int(match.group(1))
                            ports.add((port, "udp"))
                            console.print(
                                f"[bold green][PORT_DETECTION][/bold green] Found UDP port: {port} [{current_process}]")

            except subprocess.CalledProcessError as e:
                console.print(
                    f"[bold red][PORT_DETECTION][/bold red] Error running netstat -anob: {e}")
                # Fallback to basic netstat
                try:
                    output = subprocess.check_output(
                        ["netstat", "-ano"], text=True, encoding="utf-8", errors="ignore")
                    for line in output.splitlines():
                        if "LISTENING" in line:
                            match = re.search(r':(\d+)', line)
                            if match:
                                ports.add((int(match.group(1)), "tcp"))
                        elif "UDP" in line and "*:*" in line:
                            match = re.search(r':(\d+)', line)
                            if match:
                                ports.add((int(match.group(1)), "udp"))
                except Exception as e2:
                    console.print(
                        f"[bold red][PORT_DETECTION][/bold red] Error with fallback netstat: {e2}")
        else:
            # Linux/Unix: enhanced detection with multiple methods
            try:
                # Method 1: ss command for TCP listening ports
                output_tcp = subprocess.check_output(["ss", "-tnl"], text=True)
                for line in output_tcp.splitlines():
                    if re.search(r'LISTEN', line):
                        match = re.search(r':(\d+)', line)
                        if match:
                            port = int(match.group(1))
                            ports.add((port, "tcp"))

                # Method 2: ss command for UDP ports (both listening and bound)
                output_udp = subprocess.check_output(["ss", "-unl"], text=True)
                for line in output_udp.splitlines():
                    # UDP doesn't have LISTEN state, look for any UDP binding
                    if "UDP" in line or line.strip().startswith("udp"):
                        match = re.search(r':(\d+)', line)
                        if match:
                            port = int(match.group(1))
                            ports.add((port, "udp"))

            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to netstat
                try:
                    # TCP listening ports
                    output_tcp = subprocess.check_output(
                        ["netstat", "-tnl"], text=True)
                    for line in output_tcp.splitlines():
                        if "LISTEN" in line:
                            match = re.search(r':(\d+)', line)
                            if match:
                                ports.add((int(match.group(1)), "tcp"))

                    # UDP ports (netstat shows them differently)
                    output_udp = subprocess.check_output(
                        ["netstat", "-unl"], text=True)
                    for line in output_udp.splitlines():
                        # Look for UDP entries
                        if re.match(r'udp\s+', line) or "UDP" in line:
                            match = re.search(r':(\d+)', line)
                            if match:
                                ports.add((int(match.group(1)), "udp"))

                except Exception as e:
                    console.print(
                        f"[bold red][PORT_DETECTION][/bold red] Error with Linux port detection: {e}")

            # Method 3: Additional check with lsof for active network connections
            try:
                output_lsof = subprocess.check_output(
                    ["lsof", "-i", "-P", "-n"], text=True, errors="ignore")
                for line in output_lsof.splitlines()[1:]:  # Skip header
                    if "LISTEN" in line or "UDP" in line:
                        # Parse lsof output for port information
                        parts = line.split()
                        if len(parts) >= 9:
                            network_info = parts[8]  # Usually contains IP:PORT
                            if ":" in network_info:
                                try:
                                    port_part = network_info.split(":")[-1]
                                    if port_part.isdigit():
                                        port = int(port_part)
                                        proto = "tcp" if "LISTEN" in line else "udp"
                                        ports.add((port, proto))
                                except ValueError:
                                    continue

            except (subprocess.CalledProcessError, FileNotFoundError):
                # lsof not available, skip this method
                console.print(
                    "[bold yellow][PORT_DETECTION][/bold yellow] lsof command not found, skipping additional port detection method")
                pass

        unique_ports = list(ports)
        console.print(
            f"[bold cyan][PORT_DETECTION][/bold cyan] Detected {len(unique_ports)} total ports: {len([p for p in unique_ports if p[1] == 'tcp'])} TCP, {len([p for p in unique_ports if p[1] == 'udp'])} UDP")

        return unique_ports

    except Exception as e:
        console.print(
            f"[bold red][PORT_DETECTION][/bold red] Error in port detection: {e}")
        return []


async def process_new_ports_with_discovery(local_ip, hostname, new_ports):
    """
    Process new ports using server discovery and proper routing.
    This function:
    - Discovers available conflict resolution and WireGuard servers.
    - Sends the new ports to the conflict resolution server.
    - Updates client assignments based on the server's response.
    - Sends approved ports to WireGuard servers if available.
    """
    console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Processing {len(new_ports)} new ports with server discovery...")

    # Discover server types
    conflict_resolution_servers, wireguard_servers = await id_tools.discover_server_types()

    if not conflict_resolution_servers:
        console.print(f"[bold red][WS_CLIENT][/bold red] No conflict resolution servers available")
        return False

    # Use the first conflict resolution server
    cr_uri, cr_token, cr_capabilities = conflict_resolution_servers[0]

    # Send to conflict resolution server
    response = await sq.send_ports_to_conflict_resolution_server(cr_uri, cr_token, local_ip, hostname, new_ports)

    if not response:
        console.print(f"[bold red][WS_CLIENT][/bold red] Failed to process ports through conflict resolution")
        return False

    # Process results and update client assignments
    results = response.get("resultados", [])
    conflict_resolutions = response.get("conflict_resolutions", [])

    console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Processed {len(results)} port results")
    if conflict_resolutions:
        console.print(f"[bold yellow][WS_CLIENT][/bold yellow] Received {len(conflict_resolutions)} conflict resolutions")

    # Update client assignments
    approved_ports = []

    for result in results:
        port = result.get("puerto")
        proto = result.get("protocolo", "tcp")
        incoming_port = result.get("incoming_port", port)
        conflict_resolved = result.get("conflict_resolved", False)

        if port:
            cfg.client_assignments[(port, proto)] = {
                "assigned": not conflict_resolved,
                "incoming_port": incoming_port
            }

            # Add to approved ports for WG servers
            approved_ports.append({
                "port": port,
                "protocol": proto,
                "incoming_port": incoming_port,
                "conflict_resolved": conflict_resolved
            })

            if conflict_resolved:
                console.print(f"[bold yellow][WS_CLIENT][/bold yellow] Port {port} ({proto}) assigned alternative incoming port: {incoming_port}")
            else:
                console.print(f"[bold green][WS_CLIENT][/bold green] Port {port} ({proto}) assigned normally")

    # Save client assignments
    ws_client.save_client_assignments()

    # Send approved ports to WireGuard servers
    if approved_ports and wireguard_servers:
        await wg_tools.send_approved_ports_to_wireguard_servers(approved_ports, local_ip, hostname, wireguard_servers)

    return True
