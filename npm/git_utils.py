import os
import re
import shutil
import subprocess
from rich.progress import Progress

# This module provides utilities for working with git repositories,
# specifically cloning a repository with a progress bar using 'rich'.

def check_git_available():
    """
    Checks if git is available on the system.
    Returns True if git is available, False otherwise.
    """
    try:
        # Try to run 'git --version' to check if git is installed and accessible
        result = subprocess.run(
            ["git", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        if result.returncode == 0:
            # Git is available
            return True
        else:
            # Git command failed
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False

def fix_permissions(path, uid=None, gid=None):
    """
    Cambia recursivamente el propietario de todos los archivos y carpetas en 'path' al usuario y grupo dados.
    Si uid/gid no se especifican, usa los del usuario actual.
    """
    if uid is None:
        uid = os.getuid()
    if gid is None:
        gid = os.getgid()
    for root, dirs, files in os.walk(path):
        for momo in dirs:
            os.chown(os.path.join(root, momo), uid, gid)
        for momo in files:
            os.chown(os.path.join(root, momo), uid, gid)
    os.chown(path, uid, gid)

def repo_clone(repo_url, destino):
    """
    Clones a git repository showing a progress bar.
    Removes the destination if it already exists before cloning.
    Raises an exception if cloning fails.
    Args:
        repo_url (str): URL of the git repository to clone.
        destino (str): Path where the repository will be cloned.
        console: Rich console object (not used in this function).
    """
    # Clone the repository with progress bar
    if os.path.exists(destino):
        # Remove the destination directory if it already exists
        shutil.rmtree(destino)
    with Progress() as progress:
        # Add a new task to the progress bar for cloning
        task = progress.add_task(
            "[cyan]Cloning AMPTemplates repository...", total=100)
        # Use subprocess to clone and show simulated progress
        process = subprocess.Popen(
            ["git", "clone", "--progress", repo_url, destino],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        percent = 0
        # Read lines from stderr to parse git progress output
        if process.stderr is not None:
            for line in process.stderr:
                if "Receiving objects" in line:
                    # Extract percentage from line using regular expressions
                    match = re.search(r'(\d+)%', line)
                    if match:
                        percent = int(match.group(1))
                        # Update progress bar with current percentage
                        progress.update(task, completed=percent)
        process.wait()
        # Make sure progress bar reaches 100% at the end
        progress.update(task, completed=100)
    if process.returncode != 0:
        # Raise exception if git clone command failed
        raise Exception("Error cloning AMPTemplates repository.")
    # Corregir permisos del repositorio clonado
    fix_permissions(destino)
