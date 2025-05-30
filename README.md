# NPM Stream Maker

NPM Stream Maker is a control panel and automation toolkit for managing Nginx Proxy Manager (NPM) streams, port scanning, and cleaning up proxy hosts. It is designed to simplify the process of extracting ports from AMP templates, generating stream configurations, and maintaining your NPM setup.

## Features

- **Port Scanner**: Automatically clones AMPTemplates, scans for port definitions, and generates a port list in OPNsense-compatible range format.
- **Stream Generator**: (Script not provided here) Generates and synchronizes stream configurations for NPM.
- **NPM Cleaner**: (Script not provided here) Cleans up unused streams and proxy hosts in NPM.
- **NPM Bootstrap**: If Nginx Proxy Manager is not detected, generates a ready-to-use `docker-compose.yml` for quick deployment.

## Requirements

- Python 3.7+
- [rich](https://pypi.org/project/rich/) Python package
- [git](https://git-scm.com/)
- [docker](https://www.docker.com/)
- [docker-compose](https://docs.docker.com/compose/)

## Installation

1. **Clone this repository or copy the project files.**

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Ensure required system commands are installed:**
   - `git`
   - `docker`
   - `docker-compose`
   - `python3`

   If any are missing, the control panel will provide installation tips.

## Usage

1. **Run the Control Panel:**
   ```bash
   python3 Control_Panel.py
   ```

2. **Follow the menu:**
   - **Port Scanner**: Scans AMPTemplates for ports and generates a `ports.txt` file.
   - **Stream Generator**: Generates and synchronizes NPM stream configs (script not included here).
   - **NPM Cleaner**: Cleans up streams and proxy hosts (script not included here).
   - **Exit**: Closes the control panel.

3. **First-time NPM setup:**
   - If Nginx Proxy Manager is not detected, a basic `docker-compose.yml` will be created in the `npm` directory.
   - To start NPM:
     ```bash
     cd npm
     docker-compose up -d
     ```

## Notes

- The Port Scanner clones the [AMPTemplates](https://github.com/CubeCoders/AMPTemplates) repository each run and deletes it after extracting ports.
- All output and progress is shown using rich terminal formatting.
- This project is intended for advanced users familiar with Docker and Nginx Proxy Manager.

## License

This project is provided as-is, without warranty. See individual scripts for further details.
