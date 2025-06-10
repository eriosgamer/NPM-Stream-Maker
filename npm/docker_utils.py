import subprocess
import os

# This module provides utility functions to check Docker availability
# and set an environment variable accordingly.

def check_docker_available():
    """
    Checks if Docker is available on the system and sets the environment variable DOCKER_AVAILABLE.
    Returns True if Docker is available, False otherwise.
    """
    try:
        # Try to run 'docker --version' to check if Docker is installed and accessible
        result = subprocess.run(
            ["docker", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        if result.returncode == 0:
            # Docker is available, set environment variable to "1"
            os.environ["DOCKER_AVAILABLE"] = "1"
            return True
        else:
            # Docker command failed, set environment variable to "0"
            os.environ["DOCKER_AVAILABLE"] = "0" 
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        # Exception occurred (timeout, not found, or other), set environment variable to "0"
        os.environ["DOCKER_AVAILABLE"] = "0"
        return False
