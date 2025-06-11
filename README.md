# NPM Stream Maker

NPM Stream Maker is an advanced automated TCP/UDP stream management application for [Nginx Proxy Manager](https://nginxproxymanager.com/). It provides a complete system for automatic port detection, conflict resolution, remote management via WebSocket, and WireGuard support, all through an interactive menu interface.

This project is designed to simplify the management of multiple TCP/UDP streams, allowing users to easily create, edit, and delete stream configurations in Nginx Proxy Manager without manual intervention. It also includes a WebSocket server/client for real-time communication and synchronization between multiple instances.

This tool is ideal for users who need to manage multiple game servers, microservices, or distributed applications that require dynamic port management and remote control capabilities.

**Personal use case as example**
- Allows access to a private network through WireGuard, using a VPS as an entry point with NPM to redirect specific ports to the VPN tunnel. These connections are received on an OPNsense router, and using port forwarding, everything is redirected to a secondary NPM instance inside the private network, which is in charge of the final port redirection to the target server.

## ⚠️ WebSocket Configuration Notes

The application uses optimized WebSocket settings for stability:
- **Ping Interval**: 60 seconds (increased for better network stability)
- **Ping Timeout**: 120 seconds (balanced for responsiveness and stability)
- **Close Timeout**: 20 seconds (adequate for clean disconnections)
- **Connection Retry**: Automatic reconnection with exponential backoff

If you experience connection timeouts, ensure your network allows WebSocket connections and consider adjusting firewall settings.


## Key Features

- **Automatic Deployment of NPM**: Automatically deploys Nginx Proxy Manager using Docker Compose if needed
- **Automated Stream Management**: Automatic creation, editing, and deletion of TCP/UDP stream configurations in Nginx Proxy Manager
- **Automatic Port Detection**: Real-time scanning of ports in use on the local system
- **Intelligent Conflict Resolution**: Automatic system to resolve port conflicts by assigning alternative ports
- **WebSocket Server/Client**: Real-time communication between multiple clients for configuration synchronization
- **Remote Control**: Remote management of streams and configurations through WebSocket
- **WireGuard Integration**: Native support for WireGuard servers with peer IP management
- **SQLite Database**: Complete management of the Nginx Proxy Manager database
- **Rich Menu Interface**: Colorful and interactive user interface using Rich
- **WebSocket Diagnostics**: Diagnostic and testing tools for WebSocket connections

## System Requirements

- Python 3.7+
- Docker
- Docker Compose >= 1.29
- Python packages: `rich`, `websockets`, `python-dotenv` (see `requirements.txt`)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/eriosgamer/NPM-Stream-Maker.git
cd NPM-Stream-Maker
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```
2.1. If you are using a virtual environment, make sure to activate it before running the above command.
2.2. If you are using a system without `pip` installed, you can install it using:
```bash
sudo apt install python3-pip  # For Debian/Ubuntu
```
```bash
sudo pacman -S python-pip  # For Arch Linux
```
```bash
sudo dnf install python3-pip  # For Fedora
```
```bash
sudo yum install python3-pip  # For CentOS/RHEL
```
2.3. If you are using Windows, you can install `pip` by downloading the [get-pip.py](https://bootstrap.pypa.io/get-pip.py) script and running:
```bash
python get-pip.py
```
2.4. If you are using macOS, you can install `pip` using Homebrew:
```bash
brew install python  # This will install Python and pip
```

**⚠️ In some systems you might need to install the packages running commands with `sudo` privileges.**
Like in arch linux you can install the dependencies using:
```bash
sudo pacman -S python-rich python-websockets python-dotenv
```

3. Run the application (might require administrative privileges on some systems):
Linux ask for sudo and in windows need to run as administrator
```bash
python main.py
```

## Basic Usage

### Main Menu
The application runs through an interactive menu that offers the following options:

1. **Show existing streams** - View all active streams in NPM *(requires NPM)*
2. **Add streams manually** - Manual creation of new streams *(requires NPM)*
3. **Edit WebSocket URIs** - Configuration of WebSocket connections
4. **Clear all streams** - Mass deletion of configurations *(requires NPM)*
5. **Start WebSocket Server** - Launch server for remote communication *(requires NPM)*
6. **Start WebSocket Client** - Connect as client for automatic port sending *(requires WebSocket URIs)*
7. **Remote Control Menu** - Advanced remote management *(requires WebSocket URIs)*
0. **Exit** - Close the application

**Note**: Options requiring NPM will be disabled if Nginx Proxy Manager is not running. Options requiring WebSocket URIs will be disabled if no WebSocket URIs are configured.

### Typical Workflow

1. **Initial setup**: Run the application and configure WebSocket URIs if the application is run for the first time and is a client instance.
2. **If used as Server**: Start the WebSocket server to listen for client connections
3. **If used as Client**: Start the WebSocket client to send port information
4. **Port detection**: Client detects local ports that are common in gaming and sends them to the server
5. **Automatic resolution**: Server resolves conflicts and creates streams automatically on the host NPM instance
5.1. If there is multiple NPM instance servers, the local server without wireguard will be used to manage conflicts and send the resolved ports to the remote servers via websocket using the connected clients as a bridge.
6. **Remote management**: Use remote control to manage multiple instances [Work In Progress]

## Project Structure

```
NPM Stream Maker/
├── main.py                          # Main application entry point
├── requirements.txt                 # Required Python dependencies (rich, websockets, python-dotenv)
├── README.md                        # Complete project documentation
│
├── Client/                         # WebSocket client modules
│   ├── ws_client.py               # Main WebSocket client with automatic reconnection
│   ├── ws_client_main_thread.py   # Main WebSocket client thread
│   ├── port_file_reader.py        # Port file reading and processing
│   ├── steam_ports.py             # Specific Steam port management
│   ├── server_querys.py           # Server queries and communication
│   └── ws_server_messages.py      # WebSocket server message handling
│
├── Config/                         # Configuration and script loading
│   ├── config.py                  # Main application configuration
│   ├── script_loader.py           # Dynamic script and module loader
│   └── ws_config_handler.py       # WebSocket configuration handler
│
├── Core/                           # Core system functionalities
│   ├── token_manager.py           # WebSocket token and authentication management
│   ├── id_tools.py                # Identification tools and utilities
│   ├── dependency_manager.py      # System dependency management
│   └── message_handler.py         # System message processing
│
├── npm/                            # Nginx Proxy Manager management
│   ├── npm_handler.py             # Main NPM and database controller
│   ├── docker_utils.py            # Docker container management utilities
│   ├── git_utils.py               # Git version control utilities
│   └── npm_status.py              # NPM status monitor
│
├── ports/                          # Port management and detection
│   ├── port_scanner.py            # Cross-platform TCP/UDP port scanner
│   ├── port_scanner_main.py       # Main scanner controller
│   ├── conflict_handler.py        # Port conflict management and detection
│   ├── conflict_resolution.py     # Conflict resolution algorithms
│   ├── conflict_cleaner.py        # Obsolete conflict cleanup
│   └── ports_utils.py             # General port utilities
│
├── Remote/                         # Remote control and distributed management (WIP)
│   ├── remote_control.py          # Main remote controller (WIP)
│   ├── remote_handler.py          # Remote operations handler (WIP)
│   ├── remote_stream_add.py       # Remote stream addition via WebSocket (WIP)
│   ├── menu.py                    # Remote control menu (WIP)
│   ├── validation.py              # Remote data validation (WIP)
│   └── extra_utils.py             # Additional remote utilities (WIP)
│
├── Server/                         # WebSocket server
│   └── ws_server.py               # Main WebSocket server with client management
│
├── Streams/                        # TCP/UDP stream management
│   ├── stream_handler.py          # Main stream operations handler
│   ├── stream_creation.py         # Automatic stream creation in NPM
│   ├── stream_creation_db.py      # Database stream creation
│   ├── stream_db_handler.py       # SQLite stream database management
│   ├── stream_cleaning.py         # Obsolete stream cleanup
│   └── stream_com_handler.py      # Stream communication handler
│
├── UI/                             # User interface
│   ├── menu.py                    # Interactive main menu with Rich
│   └── uri_menu.py                # WebSocket URI configuration menu
│
├── WebSockets/                     # WebSocket configuration and diagnostics
│   ├── websocket_config.py        # WebSocket connection configuration
│   ├── uri_config.py              # WebSocket URI configuration
│   └── diagnostics.py             # Diagnostic and testing tools
│
└── Wireguard/                      # WireGuard integration
    ├── wireguard_tools.py         # WireGuard management tools
    └── wireguard_utils.py         # WireGuard utilities and helpers
```


### System Dependencies Diagram

[![Architecture Diagram](https://img.shields.io/badge/View%20Diagram-Mermaid%20Chart-blue?style=for-the-badge&logo=mermaid)](https://www.mermaidchart.com/app/projects/b304923a-163f-4054-aa95-6ae4c73bca8e/diagrams/d108af48-1618-4415-80a2-75d35da1a2b6/version/v0.1/edit)

> **📊 [View Interactive Diagram on MermaidChart →](https://www.mermaidchart.com/app/projects/b304923a-163f-4054-aa95-6ae4c73bca8e/diagrams/d108af48-1618-4415-80a2-75d35da1a2b6/version/v0.1/)**

The diagram shows the relationships and dependencies between all system modules, organized by categories:

- 🔴 **Main File**: Entry point (main.py)
- 🟡 **User Interface**: Interactive menus 
- 🟣 **WebSocket**: Client, server and configuration
- 🔵 **Stream Management**: Main operations
- 🟦 **Port Management**: Detection and conflict resolution
- 🟢 **Remote Control**: Distributed management
- 🟠 **NPM**: Nginx Proxy Manager integration
- 🔵 **Configuration**: Configuration and core tools

### Main Components

#### 1. WebSocket Server (`Server/ws_server.py`)
- **Port**: Configurable (default: 8765, set via `--ws-server-port` or `WS_SERVER_PORT` environment variable)
- **Functions**: 
  - Receives port information from multiple clients
  - Manages automatic port conflict resolution
  - Automatically creates streams in NPM database
  - Handles remote commands for stream management
  - WireGuard integration for IP mapping

#### 2. WebSocket Client (`Client/ws_client.py`)
- **Functions**:
  - Detects ports in use locally
  - Automatically sends port information to server
  - Maintains persistent connection with automatic reconnection
  - Filters ports according to allowed list in `ports.txt`

#### 3. Port Scanner (`ports/port_scanner.py`)
- **Automatic detection** of active TCP/UDP ports related to gaming (uses AMPTemplates to scan common game ports used in AMP by cubecoders and some hardcoded ports common in steam games)
- **Cross-platform compatibility** (Windows/Linux)
- **WireGuard integration** for managing reverse proxy connections through WireGuard VPN.
- **Export** results to `ports.txt`, this list can be used to make a alias in OPNsense for common ports used in games and used in port forwarding.

#### 4. Stream Management (`Streams/`)
- **Automatic creation** of streams in SQLite database
- **Synchronization** with Nginx configuration files
- **Conflict management** with alternative ports
- **Complete support** for TCP and UDP protocols

#### 5. Remote Control (`Remote/`) - **Work In Progress**
- **Remote management** of multiple instances (Under development)
- **Remote commands** to create/delete streams (Under development)
- **Synchronization** between different servers (Under development)
- **Service status monitoring** (Under development)

### Database and Configuration

The application works directly with:
- **SQLite database** of Nginx Proxy Manager (`data/database.sqlite`)
- **Nginx configuration files** (`.conf`)
- **Docker Compose** for NPM container management

### Conflict Resolution

When multiple clients use the same port:
1. **Automatic detection** of conflict, if a port is already in use by another client, the server suggests an alternative port to the client.
2. **Alternative port assignment** (e.g.: 3306 → 13306), this port is broadcasted to all connected clients and servers so they can update their configurations.
3. **Stream creation** with redirection to the new port in Nginx Proxy Manager.
4. **Persistence** of resolution in JSON files so the system can remember the resolution for future sessions.

## Common Use Cases

### 1. Multiple Game Servers
- Multiple game servers on different machines
- Port conflicts resolved automatically
- Centralized management of all instances

### 2. Microservices Development
- Development services with dynamic ports
- Automatic detection of new services
- Automatic proxy through NPM

### 3. WireGuard Network
- Distributed servers connected via WireGuard
- Automatic peer IP management
- Streams configured for WireGuard internal IPs

### 4. Monitoring and Administration
- Centralized view of all active streams
- WebSocket connectivity diagnostics
- Automatic cleanup of obsolete configurations

## Configuration Files

- **`.env`**: WebSocket tokens and environment configuration
- **`ports.txt`**: List of allowed ports for monitoring, generated during client startup
- **`ws_ports.json`**: Client and port mapping
- **`port_conflict_resolutions.json`**: Persistent conflict resolutions
- **`docker-compose.yml`**: NPM configuration (automatically generated), the network is set to `host` mode to allow direct access to the host ports.

## Command Line Usage

The application supports different execution modes through command-line arguments:

```bash
# Run with complete interactive interface (default)
python main.py

# Run only WebSocket client without dependency checks
python main.py --ws-client-only

# Run only WebSocket server without dependency checks
python main.py --ws-server-only

# Run WebSocket server on a custom port
python main.py --ws-server-only --ws-server-port 9000

# Run interactive mode with custom WebSocket server port
python main.py --ws-server-port 9000
```

### Command Line Arguments

- **`--ws-client-only`**: Runs only the WebSocket client (`ws_client_main_loop()`) without showing the main menu or performing dependency checks. Useful for automated client deployments.

- **`--ws-server-only`**: Runs only the WebSocket server (`start_ws_server()`) without the main menu. Automatically sets the `RUN_FROM_PANEL` environment variable to `1` and starts the server directly.

- **`--ws-server-port PORT`**: Specifies the port for the WebSocket server (default: 8765). Can be used with any execution mode. Example: `--ws-server-port 9000`

- **No arguments**: Launches the full interactive application with the main menu interface, allowing access to all features through the Rich-based UI.

### Error Handling

The application includes comprehensive error handling:
- **KeyboardInterrupt**: Graceful shutdown when user presses Ctrl+C
- **Exception handling**: Catches and displays unexpected errors
- **Logging**: Configures logging with timestamps and levels for debugging
- **Port conflicts**: Automatic detection and suggestions for alternative ports

## Environment Variables

- **`WS_TOKEN`**: WebSocket authentication token
- **`WS_SERVER_TOKEN`**: WebSocket server token
- **`WS_SERVER_PORT`**: WebSocket server port (default: 8765)
- **`SKIP_NPM_CHECK`**: Skip NPM verification on startup
- **`RUN_FROM_PANEL`**: Control panel execution indicator (automatically set when using `--ws-server-only`)

## Dependencies

The project requires the following Python packages (defined in `requirements.txt`):

- **`rich`**: For colorful and interactive console interface
- **`websockets`**: For WebSocket server and client functionality
- **`python-dotenv`**: For loading environment variables from `.env` files

Install all dependencies with:
```bash
pip install -r requirements.txt
```

## Contributions

Contributions are welcome. Please:

1. Fork the repository
2. Create a branch for your feature (`git checkout -b feature/new-functionality`)
3. Commit your changes (`git commit -am 'Add new functionality'`)
4. Push to the branch (`git push origin feature/new-functionality`)
5. Create a Pull Request

## License

This project is licensed under the MIT License with Non-Commercial Clause - see the LICENSE file for details.

**Important**: This software is free for personal, educational, and non-commercial use. Commercial use, including sale or incorporation into commercial products, requires explicit written permission from the copyright holder.

## Support and Documentation

For more information about the specific use of each module, review the detailed comments in each source code file. Each module includes extensive documentation about its functionality and use cases.
