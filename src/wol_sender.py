"""Wake-on-LAN packet sender with retry logic and validation."""

import asyncio
import logging
import socket
import struct
from typing import Optional
import re


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
        """Calculate broadcast address for the network."""
        try:
            # For simplicity, assume /24 network and calculate broadcast
            ip_parts = ip.split('.')
            if len(ip_parts) != 4:
                raise ValueError(f"Invalid IP address: {ip}")
            
            # Simple /24 broadcast calculation
            broadcast_parts = ip_parts[:-1] + ['255']
            return '.'.join(broadcast_parts)
            
        except Exception:
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
        """Send a single Wake-on-LAN packet."""
        try:
            magic_packet = self._create_magic_packet()
            
            # Create UDP socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                
                # Send to multiple ports for better compatibility
                wol_ports = [7, 9]  # Standard WoL ports
                
                # Send to broadcast address
                for port in wol_ports:
                    sock.sendto(magic_packet, (self.broadcast_ip, port))
                    logger.debug(f"WoL packet sent to {self.broadcast_ip}:{port}")
                
                # Also send directly to target IP if different from broadcast
                if self.target_ip != self.broadcast_ip:
                    for port in wol_ports:
                        try:
                            sock.sendto(magic_packet, (self.target_ip, port))
                            logger.debug(f"WoL packet sent to {self.target_ip}:{port}")
                        except Exception as e:
                            logger.debug(f"Direct send to {self.target_ip}:{port} failed: {e}")
                
                # Additional broadcast to 255.255.255.255 for better coverage
                for port in wol_ports:
                    try:
                        sock.sendto(magic_packet, ('255.255.255.255', port))
                        logger.debug(f"WoL packet sent to 255.255.255.255:{port}")
                    except Exception as e:
                        logger.debug(f"Global broadcast to port {port} failed: {e}")
            
            # Verify packet content
            packet_info = self.get_packet_info()
            logger.info(f"Wake-on-LAN packet sent to MAC {self.mac_address} "
                       f"(packet size: {packet_info['packet_size']} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Wake-on-LAN packet: {e}")
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