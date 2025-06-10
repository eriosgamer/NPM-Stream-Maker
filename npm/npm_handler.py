"""
This module provides utility functions to manage the Nginx Proxy Manager (NPM) Docker container
using docker-compose. It ensures the presence of the docker-compose.yml file, and provides
functions to stop, restart, and reload the NPM container, as well as perform a fresh restart
for clean startup scenarios.

Functions:
- ensure_npm_compose_file: Ensures the docker-compose.yml exists for NPM, creates it if missing.
- stop_npm: Stops the NPM container if it is running.
- restart_npm: Restarts the NPM container.
- reload_npm: Reloads Nginx inside the running NPM container.
- restart_npm_for_fresh_start: Performs a clean restart of NPM, stopping and removing containers before starting again.
"""

import os
import subprocess
import time

from rich.console import Console
from Config import config as cfg
console = Console()


def ensure_npm_compose_file():
    """
    Ensures that the docker-compose.yml file for Nginx Proxy Manager exists.
    If it does not exist, it creates one with the default configuration.
    """
    npm_dir = cfg.NGINX_BASE_DIR
    compose_file = os.path.join(npm_dir, "docker-compose.yml")
    if not os.path.exists(npm_dir):
        os.makedirs(npm_dir)
    if not os.path.exists(compose_file):
        with open(compose_file, "w") as f:
            f.write(
                """services:
  app:
    image: 'jc21/nginx-proxy-manager:latest'
    restart: unless-stopped
    network_mode: "host"
    volumes:
      - ./data:/data
      - ./letsencrypt:/etc/letsencrypt
      - ./data/logs:/data/logs
    environment:
      DISABLE_IPV6: 'true'
      X_FRAME_OPTIONS: "sameorigin"
""")
    print(f"[CONTROL_PANEL] docker-compose.yml generated at {compose_file}")


def stop_npm():
    """
    Stops the Nginx Proxy Manager container using docker-compose.
    Only stops if the container is currently running.
    """
    # Check if docker-compose.yml exists
    compose_dir = cfg.NGINX_BASE_DIR
    compose_file = os.path.join(compose_dir, "docker-compose.yml")
    if not os.path.exists(compose_file):
        print(
            f"[NPM_CLEANER] docker-compose.yml not found in {compose_dir}. Cannot stop NPM automatically.")
        return
    # Check if the container is running before attempting to stop it
    try:
        result = subprocess.run(
            ["docker-compose", "ps", "--services", "--filter", "status=running"],
            cwd=compose_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        running_services = result.stdout.strip().splitlines()
        if not running_services:
            print(
                "[NPM_CLEANER] Nginx Proxy Manager is not running. No need to stop it.")
            return
    except Exception as e:
        print(f"[NPM_CLEANER] Error checking running containers: {e}")
        return
    try:
        subprocess.run(["docker-compose", "down"], cwd=compose_dir, check=True)
        print("Container stopped.")
    except subprocess.CalledProcessError as e:
        print(
            f"[NPM_CLEANER] Error stopping NPM:\nSTDOUT:\n{e.output}\nSTDERR:\n{e.stderr}")


def restart_npm():
    """
    Restarts the Nginx Proxy Manager container using docker-compose.
    """
    print("Restarting Nginx Proxy Manager with docker-compose...")
    compose_dir = cfg.NGINX_BASE_DIR
    compose_file = os.path.join(compose_dir, "docker-compose.yml")
    if not os.path.exists(compose_file):
        print(
            f"[NPM_CLEANER] docker-compose.yml not found in {compose_dir}. Cannot restart NPM automatically.")
        return
    try:
        subprocess.run(["docker-compose", "down"], cwd=compose_dir, check=True)
        subprocess.run(["docker-compose", "up", "-d"],
                       cwd=compose_dir, check=True)
        print("Container restarted.")
    except subprocess.CalledProcessError as e:
        print(
            f"[NPM_CLEANER] Error restarting NPM:\nSTDOUT:\n{e.output}\nSTDERR:\n{e.stderr}")


def reload_npm():
    """
    Reloads Nginx inside the Nginx Proxy Manager container using nginx -s reload.
    Only runs if Docker is available.
    """
    docker_available = os.environ.get("DOCKER_AVAILABLE", "0") == "1"
    
    if not docker_available:
        console.print("[bold yellow][NPM_CLEANER][/bold yellow] Docker not available - skipping NPM reload")
        return
    
    npm_container_name = None
    try:
        # Find the running NPM container ID or name
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}} {{.Image}} {{.Names}}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and "jc21/nginx-proxy-manager" in parts[1]:
                npm_container_name = parts[2]
                break
        if not npm_container_name:
            console.print(
                "[bold yellow][NPM_CLEANER][/bold yellow] Could not find a running Nginx Proxy Manager container to reload.")
            return
        # Execute nginx -s reload inside the container
        exec_result = subprocess.run(
            ["docker", "exec", npm_container_name, "nginx", "-s", "reload"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if exec_result.returncode == 0:
            console.print(
                "[bold green][NPM_CLEANER][/bold green] Nginx reloaded successfully inside the NPM container.")
        else:
            console.print(
                f"[bold yellow][NPM_CLEANER][/bold yellow] Warning reloading Nginx:\nSTDOUT:\n{exec_result.stdout}\nSTDERR:\n{exec_result.stderr}")
    except Exception as e:
        console.print(
            f"[bold yellow][NPM_CLEANER][/bold yellow] Warning reloading Nginx in NPM container (Docker may not be available): {e}")


def restart_npm_for_fresh_start():
    """
    Performs a fresh restart of the NPM container to ensure a clean start when launching ws_server.
    Stops and removes previous containers before starting again.
    """
    print("[NPM_CLEANER] Performing fresh restart of NPM for WebSocket server startup...")
    compose_dir = cfg.NGINX_BASE_DIR
    compose_file = os.path.join(compose_dir, "docker-compose.yml")
    
    if not os.path.exists(compose_file):
        print(f"[NPM_CLEANER] docker-compose.yml not found in {compose_dir}. Cannot restart NPM automatically.")
        return False
    
    try:
        # First check if any containers are running
        result = subprocess.run(
            ["docker-compose", "ps", "--services", "--filter", "status=running"],
            cwd=compose_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        
        running_services = result.stdout.strip().splitlines()
        
        if running_services:
            print(f"[NPM_CLEANER] Found {len(running_services)} running service(s). Performing clean restart...")
            # Force stop and remove containers
            subprocess.run(["docker-compose", "down", "--remove-orphans"], 
                         cwd=compose_dir, check=True, timeout=30)
            print("[NPM_CLEANER] NPM containers stopped successfully")
            time.sleep(2)  # Brief pause between stop and start
        else:
            print("[NPM_CLEANER] No running containers found. Starting fresh...")
        
        # Start containers
        result = subprocess.run(["docker-compose", "up", "-d"], 
                              cwd=compose_dir, check=True, timeout=60)
        print("[NPM_CLEANER] NPM containers started successfully")
        
        # Wait a moment for services to initialize
        print("[NPM_CLEANER] Waiting for NPM to initialize...")
        time.sleep(5)
        
        return True
        
    except subprocess.TimeoutExpired:
        print("[NPM_CLEANER] Timeout during NPM restart operation")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[NPM_CLEANER] Error during NPM restart:\nCommand: {e.cmd}\nReturn code: {e.returncode}")
        if e.stdout:
            print(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            print(f"STDERR:\n{e.stderr}")
        return False
    except Exception as e:
        print(f"[NPM_CLEANER] Unexpected error during NPM restart: {e}")
        return False