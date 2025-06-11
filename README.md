# NPM Stream Maker

NPM Stream Maker is an advanced automated TCP/UDP stream management application for [Nginx Proxy Manager](https://nginxproxymanager.com/). It provides a complete system for automatic port detection, conflict resolution, remote management via WebSocket, and WireGuard support, all through an interactive menu interface.

This project is designed to simplify the management of multiple TCP/UDP streams, allowing users to easily create, edit, and delete stream configurations in Nginx Proxy Manager without manual intervention. It also includes a WebSocket server/client for real-time communication and synchronization between multiple instances.

This tool is ideal for users who need to manage multiple game servers, microservices, or distributed applications that require dynamic port management and remote control capabilities.
It can be used in scenarios such as a VPS is needed to allow access to a private network trough WireGuard, or when multiple game servers are running on different machines and need to be managed centrally using Nginx Proxy Manager as a reverse proxy.

## ⚠️ WebSocket Configuration Notes

The application uses optimized WebSocket settings for stability:
- **Ping Interval**: 60 seconds (increased for better network stability)
- **Ping Timeout**: 30 seconds (balanced for responsiveness and stability)
- **Close Timeout**: 10-15 seconds (adequate for clean disconnections)
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

- Python
- Docker
- Docker Compose >= 1.29
- Python packages: `rich`, `websockets`, `python-dotenv` (see `requirements.txt`)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/npm-stream-manager.git
cd npm-stream-manager
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

## Basic Usage

### Main Menu
The application runs through an interactive menu that offers the following options:

1. **Show existing streams** - View all active streams in NPM
2. **Add streams manually** - Manual creation of new streams
3. **Edit WebSocket URIs** - Configuration of WebSocket connections
4. **Clean all streams** - Mass deletion of configurations
5. **Start WebSocket Server** - Launch server for remote communication
6. **Start WebSocket Client** - Connect as client for automatic port sending
7. **Run Port Scanner** - Detection of active ports on the system
8. **WebSocket Diagnostics** - Testing and diagnostic tools
9. **Conflict resolution summary** - View resolved port conflicts
10. **Remote Control Menu** - Advanced remote management

### Typical Workflow

1. **Initial setup**: Run the application and configure WebSocket URIs
2. **Port detection**: Use the scanner to detect active services
3. **WebSocket server**: Start the server to receive information from clients
4. **Automatic clients**: Clients automatically send their detected ports
5. **Automatic resolution**: System resolves conflicts and creates streams automatically
6. **Remote management**: Use remote control to manage multiple instances

## Project Structure

```
NPM Stream Maker/
├── main.py                          # Main application entry point
├── requirements.txt                 # Required Python dependencies
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
├── Remote/                         # Remote control and distributed management
│   ├── remote_control.py          # Main remote controller
│   ├── remote_handler.py          # Remote operations handler
│   ├── remote_stream_add.py       # Remote stream addition via WebSocket
│   ├── menu.py                    # Remote control menu
│   ├── validation.py              # Remote data validation
│   └── extra_utils.py             # Additional remote utilities
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
- **Port**: 8765 (configurable)
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
- **Automatic detection** of active TCP/UDP ports
- **Cross-platform compatibility** (Windows/Linux)
- **WireGuard integration** for server detection
- **Export** results to `ports.txt`

#### 4. Stream Management (`Streams/`)
- **Automatic creation** of streams in SQLite database
- **Synchronization** with Nginx configuration files
- **Conflict management** with alternative ports
- **Complete support** for TCP and UDP protocols

#### 5. Remote Control (`Remote/`) [WIP]
- **Remote management** of multiple instances
- **Remote commands** to create/delete streams
- **Synchronization** between different servers
- **Service status monitoring**

### Database and Configuration

The application works directly with:
- **SQLite database** of Nginx Proxy Manager (`data/database.sqlite`)
- **Nginx configuration files** (`.conf`)
- **Docker Compose** for NPM container management

### Conflict Resolution

When multiple clients use the same port:
1. **Automatic detection** of conflict
2. **Alternative port assignment** (e.g.: 3306 → 13306)
3. **Stream creation** with redirection
4. **Persistence** of resolution in JSON files

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

### 4. Monitoring and Administration [WIP]
- Centralized view of all active streams
- WebSocket connectivity diagnostics
- Automatic cleanup of obsolete configurations

## Configuration Files

- **`.env`**: WebSocket tokens and environment configuration
- **`ports.txt`**: List of allowed ports for monitoring
- **`ws_ports.json`**: Client and port mapping
- **`port_conflict_resolutions.json`**: Persistent conflict resolutions
- **`docker-compose.yml`**: NPM configuration (automatically generated)

## Command Line Commands

```bash
[WIP]
# Run only WebSocket client
python main.py --ws-client-only
[WIP]
# Run only WebSocket server  
python main.py --ws-server-only

# Run with complete interface (default)
python main.py
```

## Environment Variables

- **`WS_TOKEN`**: WebSocket authentication token
- **`WS_SERVER_TOKEN`**: WebSocket server token
- **`SKIP_NPM_CHECK`**: Skip NPM verification on startup
- **`RUN_FROM_PANEL`**: Control panel execution indicator

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
