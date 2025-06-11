import os
import sys
import threading
import time

# Add the parent directory to sys.path to allow importing modules from Core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core import token_manager

# Make fcntl optional for Windows compatibility
try:
    import fcntl
    FCNTL_AVAILABLE = True
except ImportError:
    FCNTL_AVAILABLE = False

# File where WebSocket port assignments are stored
WS_PORTS_FILE = "ws_ports.json"

# List of keywords used to identify port-related configuration fields
PORT_KEYWORDS = [
    'port', 'queryport', 'rconport', 'steamport', 'gameport', 'serverport'
]

# List of available scripts and their descriptions for the main menu
SCRIPTS = [
    ("Generate ports.txt (Port_Scanner)", "Port_Scanner.py"),
    ("Clean streams and proxy_host (NPM_Cleaner)", "NPM_Cleaner.py"),
    ("Edit WebSocket URIs", "__edit_ws_uris__"),
    ("Generate docker-compose.yml (NPM)", "__ensure_npm_compose_file__"),
    ("Check NPM Status", "__check_npm__"),
    ("WebSocket Server", "ws_server.py"),
    ("WebSocket Client", "ws_client.py"),
    ("View Port Conflict Resolutions", "__view_conflicts__"),
    ("Exit", None)
]

# List of required system commands and their names for environment validation
REQUIRED_COMMANDS = [
    ("git", "git"),
    ("docker", "docker"),
    ("docker-compose", "docker-compose"),
    ("python3", "python3"),
]

# List of files related to port conflicts and client assignments
CONFLICT_FILES = [
    "port_conflict_resolutions.json",
    "client_assignments.json",
    "assigned_ports.json",
    "connected_clients.json",
    "ws_ports.json"
]

# Name of the environment variable file
ENV_FILE = ".env"

# Paths for NGINX configuration and database files
NGINX_BASE_DIR = os.path.join(os.getcwd(), "nginx")
NGINX_STREAM_DIR = os.path.join(os.getcwd(), "nginx", "data", "nginx", "stream")
SQLITE_DB_PATH = os.path.join(os.getcwd(), "nginx", "data", "database.sqlite")

# Load the WebSocket token using the token manager from Core
WS_TOKEN = token_manager.load_ws_token()

# WebSocket Server Configuration
WS_SERVER_PORT = int(os.environ.get("WS_SERVER_PORT", 8765))  # Default port 8765, configurable via environment

# File paths for port and client assignment tracking
ASSIGNED_PORTS_FILE = "assigned_ports.json"
CONNECTED_CLIENTS_FILE = "connected_clients.json"
PORT_CONFLICT_RESOLUTIONS_FILE = "port_conflict_resolutions.json"  # New file for conflict mappings

# In-memory dictionaries for tracking connected clients, assigned ports, and conflict resolutions
connected_clients = {}
assigned_ports = {}
port_conflict_resolutions = {}  # New: {(original_port, protocol, server_ip): alternative_port}

# Lock for synchronizing access to ws_ports.json
ws_ports_lock = threading.Lock()

# Server start time (used for uptime or logging)
server_start_time = time.time()

# Dictionary for tracking client assignments: {(port, proto): {"assigned": bool, "incoming_port": int}}
client_assignments = {}

# File for storing client assignment information
CLIENT_ASSIGNMENTS_FILE = "client_assignments.json"