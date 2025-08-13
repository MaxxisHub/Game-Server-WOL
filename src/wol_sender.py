"""Wake-on-LAN packet sender with retry logic and validation."""

import asyncio
import logging
import socket
import struct
from typing import Optional
import re
import ipaddress


logger = logging.getLogger(__name__)


class WoLSender:
    """Handles sending Wake-on-LAN magic packets with retry logic."""
    
    def __init__(self, config: dict):
        self.config = config
        self.target_ip = config["server"]["target_ip"]
        self.mac_address = config["server"]["mac_address"]
        self.retry_interval = config["timing"]["wol_retry_interval"]
        
        # Parse and validate MAC address
        self.mac_bytes = self._parse_mac_address(self.mac_address)
        
        # Calculate broadcast address
        self.broadcast_ip = self._get_broadcast_address(self.target_ip)
        
    def _parse_mac_address(self, mac: str) -> bytes:
        """Parse MAC address string into bytes."""
        # Remove separators and convert to uppercase
        mac_clean = re.sub(r'[:-]', '', mac.upper())
        
        if len(mac_clean) != 12:
            raise ValueError(f"Invalid MAC address length: {mac}")
        
        try:
            # Convert hex string to bytes
            return bytes.fromhex(mac_clean)
        except ValueError as e:
            raise ValueError(f"Invalid MAC address format: {mac}") from e
    
    def _get_broadcast_address(self, ip: str) -> str:
        """Calculate broadcast address for the network using the ipaddress module."""
        try:
            # Get network mask from config (e.g., 24) or default to 24
            network_mask = self.config.get("server", {}).get("network_mask", 24)

            # Create an IPv4 interface object
            interface = ipaddress.IPv4Interface(f"{ip}/{network_mask}")

            # Get the broadcast address
            broadcast_addr = str(interface.network.broadcast_address)

            logger.debug(f"Calculated broadcast address: {broadcast_addr} for {ip}/{network_mask}")
            return broadcast_addr

        except (ValueError, KeyError) as e:
            logger.warning(f"Could not calculate broadcast address for {ip}: {e}. "
                           "Falling back to global broadcast '255.255.255.255'.")
            # Fallback to general broadcast
            return '255.255.255.255'
    
    def _create_magic_packet(self) -> bytes:
        """Create the Wake-on-LAN magic packet."""
        # Magic packet format:
        # - 6 bytes of 0xFF
        # - MAC address repeated 16 times
        
        magic_header = b'\xff' * 6
        mac_repeated = self.mac_bytes * 16
        
        return magic_header + mac_repeated
    
    async def send_wol_packet(self) -> bool:
        """Send a single Wake-on-LAN packet to multiple destinations for reliability."""
        magic_packet = self._create_magic_packet()
        sent_successfully = False

        # Define destinations: calculated broadcast, target IP, and global broadcast.
        # Using a dictionary to ensure unique IPs and provide descriptive names.
        destinations = {
            self.broadcast_ip: "Calculated Broadcast",
            self.target_ip: "Target IP",
            "255.255.255.255": "Global Broadcast"
        }

        try:
            # Create UDP socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                
                wol_ports = [9, 7]  # Standard WoL ports (9 is primary)
                
                for ip_addr, name in destinations.items():
                    if not ip_addr:  # Skip if IP is empty
                        continue

                    for port in wol_ports:
                        try:
                            sock.sendto(magic_packet, (ip_addr, port))
                            logger.debug(f"Successfully sent WoL packet via {name} to {ip_addr}:{port}")
                            sent_successfully = True
                        except OSError as e:
                            # Log specific OS errors, e.g., "Network is unreachable"
                            logger.warning(f"Could not send WoL packet via {name} to {ip_addr}:{port}. Error: {e}")
                        except Exception as e:
                            logger.error(f"An unexpected error occurred when sending WoL packet via {name} to {ip_addr}:{port}: {e}")

            if sent_successfully:
                packet_info = self.get_packet_info()
                logger.info(f"Wake-on-LAN packet sent for MAC {self.mac_address} "
                           f"(broadcast: {self.broadcast_ip}, size: {packet_info['packet_size']} bytes)")
                return True
            else:
                logger.error(f"Failed to send Wake-on-LAN packet for MAC {self.mac_address} to any destination.")
                return False

        except Exception as e:
            logger.error(f"Failed to create socket for sending Wake-on-LAN packet: {e}")
            return False
    
    async def wake_server_with_retry(self, max_retries: int = 3) -> bool:
        """Send WoL packets with retry logic."""
        for attempt in range(max_retries):
            logger.info(f"Sending Wake-on-LAN packet (attempt {attempt + 1}/{max_retries})")
            
            success = await self.send_wol_packet()
            if success:
                if attempt > 0:
                    logger.info(f"Wake-on-LAN packet sent successfully after {attempt + 1} attempts")
                return True
            
            if attempt < max_retries - 1:
                logger.warning(f"WoL send failed, retrying in {self.retry_interval} seconds")
                await asyncio.sleep(self.retry_interval)
        
        logger.error(f"Failed to send Wake-on-LAN packet after {max_retries} attempts")
        return False
    
    async def wake_server(self) -> bool:
        """Wake the server (single attempt)."""
        return await self.send_wol_packet()
    
    def validate_configuration(self) -> bool:
        """Validate WoL configuration."""
        try:
            # Test MAC address parsing
            self._parse_mac_address(self.mac_address)
            
            # Validate IP address format
            socket.inet_aton(self.target_ip)
            
            logger.debug("WoL configuration validation successful")
            return True
            
        except Exception as e:
            logger.error(f"WoL configuration validation failed: {e}")
            return False
    
    def get_packet_info(self) -> dict:
        """Get information about the WoL packet configuration."""
        return {
            "target_ip": self.target_ip,
            "broadcast_ip": self.broadcast_ip,
            "mac_address": self.mac_address,
            "mac_bytes_hex": self.mac_bytes.hex(':').upper(),
            "packet_size": len(self._create_magic_packet()),
            "retry_interval": self.retry_interval
        }