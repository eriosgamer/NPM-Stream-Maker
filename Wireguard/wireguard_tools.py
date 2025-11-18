"""
WireGuard Tools Module

This module provides utility functions for interacting with WireGuard interfaces,
detecting peers, sending pre-approved ports to WireGuard servers via WebSockets,
and checking for WireGuard presence on the system.

It is used as part of the NPM Stream Maker project to manage WireGuard-based
networking and communication with remote servers.
"""

import asyncio
import json
import socket
import subprocess
import struct
import platform as platform_module
import ipaddress
import time
from rich.console import Console
import sys
import os

import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from WebSockets import diagnostics
from UI.console_handler import ws_info, ws_error, ws_warning


def get_peer_ip_for_client_stream():
    """
    Scan the WireGuard subnet and return the first peer IP that responds to ping.
    Used to detect active peers in the WireGuard network.
    """
    if not cfg.FCNTL_AVAILABLE:
        ws_warning("[STREAM_MANAGER]", "fcntl not available (Windows), skipping WireGuard peer detection")
        return None

    try:
        wg_interface = "wg0"

        # Get local WG IP address
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_ip = socket.inet_ntoa(cfg.fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', wg_interface[:15].encode('utf-8'))
            )[20:24])
        except Exception:
            try:
                output = subprocess.check_output(
                    ["ip", "addr", "show", wg_interface], text=True)
                for line in output.splitlines():
                    line = line.strip()
                    if line.startswith("inet "):
                        local_ip = line.split()[1].split('/')[0]
                        break
                else:
                    return None
            except Exception:
                return None

        if not local_ip:
            return None

        # Get the subnet from the interface
        output = subprocess.check_output(
            ["ip", "addr", "show", wg_interface], text=True)
        subnet = None
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                subnet = line.split()[1]
                break
        if not subnet:
            return None

        net = ipaddress.ip_network(subnet, strict=False)

        # Scan for active peers in the WG subnet
        candidates = [str(ip) for ip in net.hosts() if str(ip) != local_ip]
        param = "-n" if platform_module.system().lower() == "windows" else "-c"

        for ip in candidates:
            try:
                result = subprocess.run(
                    ["ping", param, "1", "-W", "1", ip],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if result.returncode == 0:
                    return ip
            except Exception:
                continue

        return None
    except Exception:
        return None


def get_local_ip():
    """
    Get the main local IP address of the machine.
    """
    # Get the main local IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# Copied
async def send_approved_ports_to_wg_servers(approved_ports, local_ip, hostname):
    """
    Send the list of pre-approved ports to the configured WireGuard servers.
    Skips the first server (non-WG) and sends to the rest.
    """
    uri_token_pairs = diagnostics.get_ws_uris_and_tokens()
    
    # Skip the first server (non-WG) and send to remaining servers (WG)
    if len(uri_token_pairs) <= 1:
        ws_info("[WS_CLIENT]", "No WireGuard servers configured, skipping WG forwarding")
        return
    
    wg_servers = uri_token_pairs[1:]  # Skip first server
    
    for uri, token in wg_servers:
        try:
            ws_info("[WS_CLIENT]", f"Sending approved ports to WG server: {uri}")
            
            async with websockets.connect(uri, ping_timeout=10) as wg_websocket:
                # Send token first
                token_data = {"token": token}
                await wg_websocket.send(json.dumps(token_data))
                
                # Wait for token validation
                token_response = await asyncio.wait_for(wg_websocket.recv(), timeout=10)
                token_result = json.loads(token_response)
                
                if token_result.get("status") != "ok":
                    ws_error("[WS_CLIENT]", f"Token validation failed for WG server {uri}")
                    continue
                
                # Send pre-approved ports
                wg_data = {
                    "type": "conflict_resolution_ports",
                    "ip": local_ip,
                    "hostname": hostname,
                    "token": token,
                    "timestamp": int(time.time()),
                    "ports": approved_ports,  # Send approved ports with incoming_port info
                    "ports_pre_approved": True  # NEW: Mark as pre-approved
                }
                
                await wg_websocket.send(json.dumps(wg_data))
                
                # Wait for WG server response
                wg_response_msg = await asyncio.wait_for(wg_websocket.recv(), timeout=15)
                wg_response = json.loads(wg_response_msg)
                
                if wg_response.get("status") == "ok":
                    ws_info("[WS_CLIENT]", f"WG server {uri} processed approved ports successfully")
                else:
                    ws_error("[WS_CLIENT]", f"WG server {uri} error: {wg_response.get('msg', 'unknown')}")

        except Exception as e:
            ws_error("[WS_CLIENT]", f"Failed to send approved ports to WG server {uri}: {e}")


# Copied
async def send_approved_ports_to_wireguard_servers(approved_ports, local_ip, hostname, wireguard_servers):
    """
    Send the list of pre-approved ports to all specified WireGuard servers.
    """
    if not approved_ports or not wireguard_servers:
        ws_warning("[WS_CLIENT]", "No ports to send or no WireGuard servers configured")
        return

    ws_info("[WS_CLIENT]", f"Sending {len(approved_ports)} approved ports to {len(wireguard_servers)} WireGuard servers...")

    for uri, token, capabilities in wireguard_servers:
        try:
            ws_info("[WS_CLIENT]", f"Sending to WireGuard server: {uri}")

            async with websockets.connect(uri, ping_timeout=15) as websocket:
                # Send token first
                token_data = {"token": token}
                await websocket.send(json.dumps(token_data))

                # Wait for token validation
                token_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                token_result = json.loads(token_response)

                if token_result.get("status") != "ok":
                    ws_error("[WS_CLIENT]", f"Token validation failed for WG server {uri}")
                    continue

                # Send pre-approved ports
                wg_data = {
                    "type": "conflict_resolution_ports",
                    "ip": local_ip,
                    "hostname": hostname,
                    "token": token,
                    "timestamp": int(time.time()),
                    "ports": approved_ports,
                    "ports_pre_approved": True  # Mark as pre-approved
                }

                await websocket.send(json.dumps(wg_data))

                # Wait for WG server response
                wg_response_msg = await asyncio.wait_for(websocket.recv(), timeout=15)
                wg_response = json.loads(wg_response_msg)

                if wg_response.get("status") == "ok":
                    ws_info("[WS_CLIENT]", f"✓ WireGuard server {uri} processed ports successfully")
                else:
                    ws_error("[WS_CLIENT]", f"✗ WireGuard server {uri} error: {wg_response.get('msg', 'unknown')}")

        except Exception as e:
            ws_error("[WS_CLIENT]", f"Failed to send to WireGuard server {uri}: {e}")

# Copied
def wireguard_present():
    """
    Check if WireGuard is present on the system.
    Returns True if WireGuard is installed, False otherwise.
    """
    try:
        subprocess.run(["wg", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        ws_warning("[WS_CLIENT]", f"Error checking WireGuard: {e}")
        return False


# Copied
def get_local_wg_ip(interface="wg0"):
    """
    Get the local WireGuard interface IP address (e.g., 10.10.0.1).
    """
    if not cfg.FCNTL_AVAILABLE:
        ws_warning("[WS_CLIENT]", "fcntl not available (Windows), skipping WireGuard IP detection")
        return None

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(cfg.fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', interface[:15].encode('utf-8'))
        )[20:24])
    except Exception:
        try:
            output = subprocess.check_output(["ip", "addr", "show", interface], text=True)
            for line in output.splitlines():
                if "inet " in line:
                    return line.split()[1].split('/')[0]
        except Exception:
            pass
    return None

