"""Minecraft protocol handler for status responses and login detection."""

import asyncio
import json
import logging
import socket
import struct
from enum import Enum
from typing import Optional, Dict, Any, Tuple
import time


logger = logging.getLogger(__name__)


class MinecraftState(Enum):
    """Minecraft connection states."""
    HANDSHAKING = 0
    STATUS = 1
    LOGIN = 2
    PLAY = 3


class PacketBuffer:
    """Handles Minecraft packet buffer operations with VarInt support."""
    
    def __init__(self, data: bytes = b''):
        self.data = data
        self.pos = 0
    
    def read_varint(self) -> int:
        """Read a VarInt from the buffer."""
        value = 0
        position = 0
        
        while True:
            if self.pos >= len(self.data):
                raise ValueError("Unexpected end of buffer while reading VarInt")
            
            byte = self.data[self.pos]
            self.pos += 1
            
            value |= (byte & 0x7F) << position
            
            if (byte & 0x80) == 0:
                break
                
            position += 7
            if position >= 32:
                raise ValueError("VarInt too long")
        
        return value
    
    def write_varint(self, value: int) -> None:
        """Write a VarInt to the buffer."""
        if value < 0:
            raise ValueError("VarInt cannot be negative")
            
        data = b''
        while True:
            byte = value & 0x7F
            value >>= 7
            if value != 0:
                byte |= 0x80
            data += bytes([byte])
            if value == 0:
                break
        
        self.data += data
    
    def read_string(self) -> str:
        """Read a UTF-8 string from the buffer."""
        length = self.read_varint()
        if self.pos + length > len(self.data):
            raise ValueError("String length exceeds buffer size")
        
        string_data = self.data[self.pos:self.pos + length]
        self.pos += length
        
        return string_data.decode('utf-8')
    
    def write_string(self, value: str) -> None:
        """Write a UTF-8 string to the buffer."""
        encoded = value.encode('utf-8')
        self.write_varint(len(encoded))
        self.data += encoded
    
    def read_ushort(self) -> int:
        """Read an unsigned short (2 bytes, big-endian)."""
        if self.pos + 2 > len(self.data):
            raise ValueError("Not enough data for unsigned short")
        
        value = struct.unpack('>H', self.data[self.pos:self.pos + 2])[0]
        self.pos += 2
        return value
    
    def write_ushort(self, value: int) -> None:
        """Write an unsigned short (2 bytes, big-endian)."""
        self.data += struct.pack('>H', value)
    
    def read_long(self) -> int:
        """Read a long (8 bytes, big-endian)."""
        if self.pos + 8 > len(self.data):
            raise ValueError("Not enough data for long")
        
        value = struct.unpack('>Q', self.data[self.pos:self.pos + 8])[0]
        self.pos += 8
        return value
    
    def remaining(self) -> int:
        """Get number of remaining bytes in buffer."""
        return len(self.data) - self.pos
    
    def to_bytes(self) -> bytes:
        """Get the complete buffer as bytes."""
        return self.data


class MinecraftHandler:
    """Handles Minecraft protocol interactions."""
    
    def __init__(self, config: dict):
        self.config = config
        self.minecraft_config = config["minecraft"]
        self.port = self.minecraft_config["port"]
        self.protocol_version = self.minecraft_config["protocol_version"]
        
        # Server status information
        self.server_info = {
            "offline": {
                "version": {
                    "name": "WoL Proxy",
                    "protocol": self.protocol_version
                },
                "players": {
                    "max": self.minecraft_config["max_players_display"],
                    "online": 0
                },
                "description": self.minecraft_config["motd_offline"],
                "favicon": None
            },
            "starting": {
                "version": {
                    "name": self.minecraft_config["version_text_starting"],
                    "protocol": self.protocol_version
                },
                "players": {
                    "max": self.minecraft_config["max_players_display"],
                    "online": 0
                },
                "description": self.minecraft_config["motd_starting"],
                "favicon": None
            }
        }
    
    def create_status_response(self, is_starting: bool = False) -> str:
        """Create a status response JSON string."""
        status_key = "starting" if is_starting else "offline"
        response = self.server_info[status_key].copy()
        
        # Add current timestamp for ping calculation
        response["time"] = int(time.time() * 1000)
        
        return json.dumps(response, separators=(',', ':'))
    
    def create_packet(self, packet_id: int, data: bytes = b'') -> bytes:
        """Create a complete Minecraft packet with length prefix."""
        buffer = PacketBuffer()
        
        # Write packet ID
        buffer.write_varint(packet_id)
        
        # Add packet data
        buffer.data += data
        
        # Create final packet with length prefix
        final_buffer = PacketBuffer()
        final_buffer.write_varint(len(buffer.data))
        final_buffer.data += buffer.data
        
        return final_buffer.to_bytes()
    
    def parse_handshake_packet(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse a handshake packet and return connection info."""
        try:
            buffer = PacketBuffer(data)
            
            # Read packet length
            packet_length = buffer.read_varint()
            
            # Read packet ID (should be 0x00 for handshake)
            packet_id = buffer.read_varint()
            if packet_id != 0x00:
                logger.debug(f"Expected handshake packet (0x00), got {packet_id}")
                return None
            
            # Read handshake data
            protocol_version = buffer.read_varint()
            server_address = buffer.read_string()
            server_port = buffer.read_ushort()
            next_state = buffer.read_varint()
            
            logger.debug(f"Handshake: protocol={protocol_version}, address={server_address}, "
                        f"port={server_port}, next_state={next_state}")
            
            return {
                "protocol_version": protocol_version,
                "server_address": server_address,
                "server_port": server_port,
                "next_state": next_state  # 1 = status, 2 = login
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse handshake packet: {e}")
            return None
    
    def create_status_response_packet(self, is_starting: bool = False) -> bytes:
        """Create a status response packet."""
        try:
            # Create response JSON
            response_json = self.create_status_response(is_starting)
            
            # Create packet data
            buffer = PacketBuffer()
            buffer.write_string(response_json)
            
            # Create complete packet (packet ID 0x00 for status response)
            return self.create_packet(0x00, buffer.data)
            
        except Exception as e:
            logger.error(f"Failed to create status response packet: {e}")
            return b''
    
    def create_pong_packet(self, payload: int) -> bytes:
        """Create a pong response packet."""
        try:
            buffer = PacketBuffer()
            # Write the ping payload back as a long
            buffer.data += struct.pack('>Q', payload)
            
            # Create complete packet (packet ID 0x01 for pong)
            return self.create_packet(0x01, buffer.data)
            
        except Exception as e:
            logger.error(f"Failed to create pong packet: {e}")
            return b''
    
    def create_disconnect_packet(self, reason: str) -> bytes:
        """Create a disconnect packet with a reason."""
        try:
            # Create disconnect reason JSON
            disconnect_json = json.dumps({"text": reason})
            
            buffer = PacketBuffer()
            buffer.write_string(disconnect_json)
            
            # Create complete packet (packet ID 0x00 for login disconnect)
            return self.create_packet(0x00, buffer.data)
            
        except Exception as e:
            logger.error(f"Failed to create disconnect packet: {e}")
            return b''
    
    async def handle_client_connection(self, reader: asyncio.StreamReader, 
                                     writer: asyncio.StreamWriter, 
                                     is_starting: bool = False) -> Tuple[bool, str]:
        """
        Handle a Minecraft client connection.
        
        Returns:
            Tuple[bool, str]: (is_login_attempt, client_info)
        """
        client_addr = writer.get_extra_info('peername')
        logger.debug(f"Minecraft connection from {client_addr}")
        
        try:
            # Read handshake packet
            try:
                handshake_data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                if not handshake_data:
                    return False, "Connection closed during handshake"
            except asyncio.TimeoutError:
                return False, "Handshake timeout"
            
            handshake_info = self.parse_handshake_packet(handshake_data)
            if not handshake_info:
                return False, "Invalid handshake packet"
            
            next_state = handshake_info["next_state"]
            
            if next_state == 1:  # Status request
                logger.debug(f"Status request from {client_addr}")
                await self._handle_status_request(reader, writer, is_starting)
                return False, f"Status request from {client_addr}"
                
            elif next_state == 2:  # Login attempt
                logger.info(f"Login attempt detected from {client_addr}")
                await self._handle_login_attempt(writer)
                return True, f"Login attempt from {client_addr}"
            
            else:
                logger.warning(f"Unknown next state {next_state} from {client_addr}")
                return False, f"Unknown state {next_state}"
                
        except Exception as e:
            logger.error(f"Error handling Minecraft connection from {client_addr}: {e}")
            return False, f"Error: {e}"
        
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def _handle_status_request(self, reader: asyncio.StreamReader, 
                                   writer: asyncio.StreamWriter, 
                                   is_starting: bool) -> None:
        """Handle a status request (server list ping)."""
        try:
            # Send status response
            response_packet = self.create_status_response_packet(is_starting)
            writer.write(response_packet)
            await writer.drain()
            
            # Wait for ping packet
            try:
                ping_data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                if ping_data and len(ping_data) >= 9:  # Minimum ping packet size
                    # Parse ping packet to get payload
                    buffer = PacketBuffer(ping_data)
                    packet_length = buffer.read_varint()
                    packet_id = buffer.read_varint()
                    
                    if packet_id == 0x01:  # Ping packet
                        payload = buffer.read_long()
                        
                        # Send pong response
                        pong_packet = self.create_pong_packet(payload)
                        writer.write(pong_packet)
                        await writer.drain()
                        
                        logger.debug("Status request completed with ping/pong")
            
            except asyncio.TimeoutError:
                logger.debug("No ping packet received after status response")
                
        except Exception as e:
            logger.error(f"Error in status request handling: {e}")
    
    async def _handle_login_attempt(self, writer: asyncio.StreamWriter) -> None:
        """Handle a login attempt by sending a disconnect message."""
        try:
            disconnect_packet = self.create_disconnect_packet(
                self.minecraft_config["kick_message"]
            )
            writer.write(disconnect_packet)
            await writer.drain()
            
            logger.debug("Login attempt handled with disconnect packet")
            
        except Exception as e:
            logger.error(f"Error handling login attempt: {e}")
    
    async def start_server(self, on_connection_callback=None) -> asyncio.Server:
        """Start the Minecraft proxy server."""
        async def handle_connection(reader, writer):
            if on_connection_callback:
                await on_connection_callback(reader, writer, self)
            else:
                await self.handle_client_connection(reader, writer)
        
        # Start server with compatibility for older Python versions
        try:
            server = await asyncio.start_server(
                handle_connection,
                '0.0.0.0',  # Bind to all interfaces
                self.port,
                reuse_port=True
            )
        except TypeError:
            # Fallback for older Python versions
            server = await asyncio.start_server(
                handle_connection,
                '0.0.0.0',  # Bind to all interfaces
                self.port
            )
        
        logger.info(f"Minecraft proxy server started on port {self.port}")
        return server