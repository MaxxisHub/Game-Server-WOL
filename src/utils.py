"""Shared utilities for the Wake-on-LAN Game Server Proxy."""

import asyncio
import logging
import socket
import time
from typing import Optional, Tuple, Any
import ipaddress


logger = logging.getLogger(__name__)


async def check_port_open(host: str, port: int, timeout: float = 5.0, protocol: str = "tcp") -> bool:
    """
    Check if a port is open on a remote host.
    
    Args:
        host: Target hostname or IP address
        port: Target port number
        timeout: Connection timeout in seconds
        protocol: Protocol type ("tcp" or "udp")
        
    Returns:
        True if port is open/reachable, False otherwise
    """
    try:
        if protocol.lower() == "tcp":
            # TCP port check using asyncio
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
            
        elif protocol.lower() == "udp":
            # UDP port check is less reliable, but we can try
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            try:
                sock.connect((host, port))
                # For UDP, successful connect doesn't mean the port is open
                # but at least the host is reachable
                return True
            finally:
                sock.close()
        
        return False
        
    except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
        return False


def validate_ip_address(ip_str: str) -> bool:
    """
    Validate IP address format.
    
    Args:
        ip_str: IP address string to validate
        
    Returns:
        True if valid IP address, False otherwise
    """
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def validate_port(port: Any) -> bool:
    """
    Validate port number.
    
    Args:
        port: Port number to validate
        
    Returns:
        True if valid port number, False otherwise
    """
    try:
        port_int = int(port)
        return 1 <= port_int <= 65535
    except (ValueError, TypeError):
        return False


def validate_mac_address(mac: str) -> bool:
    """
    Validate MAC address format.
    
    Args:
        mac: MAC address string to validate
        
    Returns:
        True if valid MAC address format, False otherwise
    """
    import re
    
    # Support formats: XX:XX:XX:XX:XX:XX, XX-XX-XX-XX-XX-XX, XXXXXXXXXXXX
    patterns = [
        r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',  # XX:XX or XX-XX format
        r'^[0-9A-Fa-f]{12}$'  # XXXXXXXXXXXX format
    ]
    
    return any(re.match(pattern, mac) for pattern in patterns)


def normalize_mac_address(mac: str) -> str:
    """
    Normalize MAC address to standard format (XX:XX:XX:XX:XX:XX).
    
    Args:
        mac: MAC address in any supported format
        
    Returns:
        Normalized MAC address string
        
    Raises:
        ValueError: If MAC address format is invalid
    """
    if not validate_mac_address(mac):
        raise ValueError(f"Invalid MAC address format: {mac}")
    
    # Remove separators and convert to uppercase
    clean_mac = mac.replace(':', '').replace('-', '').upper()
    
    # Insert colons every 2 characters
    return ':'.join(clean_mac[i:i+2] for i in range(0, 12, 2))


def format_bytes(size_bytes: int) -> str:
    """
    Format byte size in human readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def format_duration(seconds: float) -> str:
    """
    Format duration in human readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string (e.g., "1h 30m 45s")
    """
    if seconds < 0:
        return "0s"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


class RateLimiter:
    """Simple rate limiter for controlling operation frequency."""
    
    def __init__(self, max_calls: int, time_window: float):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    def is_allowed(self) -> bool:
        """
        Check if a call is allowed within the rate limit.
        
        Returns:
            True if call is allowed, False if rate limited
        """
        current_time = time.time()
        
        # Remove calls outside the time window
        self.calls = [call_time for call_time in self.calls 
                     if current_time - call_time < self.time_window]
        
        # Check if we can make another call
        if len(self.calls) < self.max_calls:
            self.calls.append(current_time)
            return True
        
        return False
    
    def time_until_allowed(self) -> float:
        """
        Get time until next call is allowed.
        
        Returns:
            Seconds until next call is allowed (0 if allowed now)
        """
        if self.is_allowed():
            # Remove the call we just added for the check
            self.calls.pop()
            return 0.0
        
        if not self.calls:
            return 0.0
        
        # Time until oldest call falls outside the window
        current_time = time.time()
        oldest_call = min(self.calls)
        return max(0.0, self.time_window - (current_time - oldest_call))


class AsyncTimer:
    """Async timer for periodic operations."""
    
    def __init__(self, interval: float, callback, *args, **kwargs):
        """
        Initialize async timer.
        
        Args:
            interval: Time interval in seconds
            callback: Callback function to call
            *args, **kwargs: Arguments to pass to callback
        """
        self.interval = interval
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self) -> None:
        """Start the timer."""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run())
    
    async def stop(self) -> None:
        """Stop the timer."""
        if not self.running:
            return
        
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
    
    async def _run(self) -> None:
        """Internal timer loop."""
        while self.running:
            try:
                await asyncio.sleep(self.interval)
                if self.running:  # Check again after sleep
                    if asyncio.iscoroutinefunction(self.callback):
                        await self.callback(*self.args, **self.kwargs)
                    else:
                        self.callback(*self.args, **self.kwargs)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in async timer callback: {e}")


def get_network_info() -> dict:
    """
    Get basic network information.
    
    Returns:
        Dictionary with network interface information
    """
    import netifaces
    
    info = {
        "interfaces": [],
        "default_gateway": None,
        "local_ips": []
    }
    
    try:
        # Get all network interfaces
        for interface in netifaces.interfaces():
            addresses = netifaces.ifaddresses(interface)
            
            interface_info = {
                "name": interface,
                "ipv4": [],
                "ipv6": [],
                "mac": None
            }
            
            # IPv4 addresses
            if netifaces.AF_INET in addresses:
                for addr in addresses[netifaces.AF_INET]:
                    interface_info["ipv4"].append({
                        "addr": addr.get("addr"),
                        "netmask": addr.get("netmask"),
                        "broadcast": addr.get("broadcast")
                    })
                    info["local_ips"].append(addr.get("addr"))
            
            # IPv6 addresses
            if netifaces.AF_INET6 in addresses:
                for addr in addresses[netifaces.AF_INET6]:
                    interface_info["ipv6"].append({
                        "addr": addr.get("addr"),
                        "netmask": addr.get("netmask")
                    })
            
            # MAC address
            if netifaces.AF_LINK in addresses:
                link_addrs = addresses[netifaces.AF_LINK]
                if link_addrs:
                    interface_info["mac"] = link_addrs[0].get("addr")
            
            info["interfaces"].append(interface_info)
        
        # Get default gateway
        gateways = netifaces.gateways()
        default_gw = gateways.get('default', {}).get(netifaces.AF_INET)
        if default_gw:
            info["default_gateway"] = {
                "gateway": default_gw[0],
                "interface": default_gw[1]
            }
    
    except ImportError:
        logger.warning("netifaces not available for network info")
    except Exception as e:
        logger.error(f"Error getting network info: {e}")
    
    return info