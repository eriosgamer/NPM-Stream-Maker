import ipaddress

# This module provides a function to validate if a string is a valid IP address or CIDR range.
# It supports both IPv4 and IPv6 formats.

def _validate_ip_or_cidr(ip_string):
    """
    Validates if a string is a valid IP address or a CIDR range.
    Supports IPv4 and IPv6.
    Returns True if valid, False otherwise.
    """

    try:
        # Try to parse as IP network (supports both single IPs and CIDR notation)
        ipaddress.ip_network(ip_string, strict=False)
        return True
    except ValueError:
        # If parsing as network fails, try to parse as individual IP address
        try:
            ipaddress.ip_address(ip_string)
            return True
        except ValueError:
            return False
