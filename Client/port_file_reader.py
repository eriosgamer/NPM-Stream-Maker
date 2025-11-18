import sys
import os
from collections import defaultdict
from UI.console_handler import ws_error, ws_info
import re
from rich.console import Console

console = Console()

# Add the parent directory to sys.path to allow imports from the project
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg

# Compile a regex to find lines with keywords (from config) and port numbers
PORT_REGEX = re.compile(
    r"(?i)\b(" + "|".join(cfg.PORT_KEYWORDS) + r")\b[^0-9]{0,10}([0-9]{2,5})"
)


def search_ports_in_file(filepath):
    """
    Searches for ports in a file using keywords defined in the configuration.
    Returns a dictionary with the keyword as key and a set of found ports as value.
    """
    # Find ports in file by keywords
    ports = defaultdict(set)
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            for match in PORT_REGEX.finditer(line):
                key = match.group(1).lower()
                port = int(match.group(2))
                ports[key].add(port)
    return ports


def group_ranges(ports):
    """
    Groups a list of consecutive ports into ranges.
    Example: [80,81,82,90] -> [(80,82),(90,90)]
    """
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


def expand_instances_per_range(ranges, max_instances=5, use_alternative_ranges=True):
    """
    Given a list of ranges [(start, end)], expands up to max_instances consecutive blocks.
    If use_alternative_ranges is True, also generates alternative blocks for repeated ports.
    Returns a set of expanded ports.
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
    # If alternative ranges are needed (simulate ws_server repeated port logic)
    if use_alternative_ranges:
        # For each range, add alternative incoming ports for repeated outgoing ports
        for start, end in ranges:
            range_len = end - start + 1
            # For each port in the range, simulate alternative incoming ports
            for i in range(max_instances):
                for offset in range(range_len):
                    alt_incoming = start + i * range_len + offset
                    ports.add(alt_incoming)
    return ports


def expand_ports(line):
    """
    Converts a line like '80,443,1000:1005' into a set of integers.
    Supports ranges and comma-separated lists.
    """
    ports = set()
    parts = re.split(r"[,\n]+", line)
    for part in parts:
        part = part.strip()
        if ":" in part:
            start, end = part.split(":", 1)
            if start.isdigit() and end.isdigit():
                ports.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            ports.add(int(part))
    return ports


def load_ports(path):
    """
    Loads ports from a plain text file.
    Returns a set of ports.
    """
    if not os.path.exists(path):
        ws_error("[WS_CLIENT]", f"Ports file not found: {path}")
        return set()

    try:
        with open(path, "r") as f:
            content = f.read()
        return expand_ports(content)
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error loading ports from {path}: {e}")
        return set()


def expand_instances_per_port(ports, max_instances=5):
    """
    For individual ports, expands up to max_instances consecutive ports for each base.
    Avoids overlaps.
    """
    expanded_ports = set()
    used = set()
    for p in sorted(ports):
        block = set(p + i for i in range(max_instances))
        if not block & used:
            expanded_ports.update(block)
            used.update(block)
    return expanded_ports


# --- Module summary ---
# This module provides utilities for reading, parsing, and expanding port numbers from text files.
# It supports extracting ports by keywords, grouping into ranges, expanding ranges and individual ports,
# and loading ports from a file for use in the client application.
