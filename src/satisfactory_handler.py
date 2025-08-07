"""Satisfactory game server UDP handler for traffic detection and forwarding."""

import asyncio
import logging
import socket
from typing import Optional, Tuple, Dict, Any, Callable
import time


logger = logging.getLogger(__name__)


class SatisfactoryHandler:
    """Handles Satisfactory UDP traffic detection and forwarding."""
    
    def __init__(self, config: dict):
        self.config = config
        self.satisfactory_config = config["satisfactory"]
        
        # Port configuration
        self.game_port = self.satisfactory_config["game_port"]
        self.query_port = self.satisfactory_config["query_port"]
        self.beacon_port = self.satisfactory_config["beacon_port"]
        
        # Server configuration
        self.target_ip = config["server"]["target_ip"]
        self.connection_timeout = config["timing"]["connection_timeout"]
        
        # Active UDP servers
        self.udp_servers: Dict[int, asyncio.DatagramTransport] = {}
        self.forwarding_active = False
        
        # Statistics
        self.stats = {
            "packets_received": 0,
            "packets_forwarded": 0,
            "connections_detected": 0,
            "last_activity": None
        }
    
    async def start_udp_listeners(self, on_traffic_callback: Optional[Callable] = None) -> Dict[int, asyncio.DatagramTransport]:
        """Start UDP listeners on all Satisfactory ports."""
        servers = {}
        
        for port in [self.game_port, self.query_port, self.beacon_port]:
            try:
                # Create UDP server for each port
                transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
                    lambda: SatisfactoryProtocol(
                        port=port,
                        target_ip=self.target_ip,
                        handler=self,
                        on_traffic_callback=on_traffic_callback
                    ),
                    local_addr=('0.0.0.0', port),
                    reuse_port=True
                )
                
                servers[port] = transport
                logger.info(f"Satisfactory UDP listener started on port {port}")
                
            except Exception as e:
                logger.error(f"Failed to start UDP listener on port {port}: {e}")
                
        self.udp_servers = servers
        return servers
    
    async def stop_udp_listeners(self) -> None:
        """Stop all UDP listeners."""
        for port, transport in self.udp_servers.items():
            try:
                transport.close()
                logger.debug(f"UDP listener on port {port} stopped")
            except Exception as e:
                logger.error(f"Error stopping UDP listener on port {port}: {e}")
        
        self.udp_servers.clear()
        logger.info("All Satisfactory UDP listeners stopped")
    
    def enable_forwarding(self) -> None:
        """Enable transparent UDP forwarding to the main server."""
        self.forwarding_active = True
        logger.info("Satisfactory UDP forwarding enabled")
    
    def disable_forwarding(self) -> None:
        """Disable UDP forwarding (proxy mode)."""
        self.forwarding_active = False
        logger.info("Satisfactory UDP forwarding disabled")
    
    async def forward_packet(self, data: bytes, addr: Tuple[str, int], port: int) -> bool:
        """Forward a UDP packet to the main server."""
        if not self.forwarding_active:
            return False
        
        try:
            # Create a new UDP socket for forwarding
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.connection_timeout)
            
            # Forward to main server
            sock.sendto(data, (self.target_ip, port))
            sock.close()
            
            self.stats["packets_forwarded"] += 1
            logger.debug(f"Forwarded UDP packet from {addr} to {self.target_ip}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to forward UDP packet to {self.target_ip}:{port}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            **self.stats,
            "ports_listening": list(self.udp_servers.keys()),
            "forwarding_active": self.forwarding_active,
            "target_server": self.target_ip
        }
    
    def reset_stats(self) -> None:
        """Reset handler statistics."""
        self.stats = {
            "packets_received": 0,
            "packets_forwarded": 0,
            "connections_detected": 0,
            "last_activity": self.stats.get("last_activity")
        }


class SatisfactoryProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for Satisfactory traffic."""
    
    def __init__(self, port: int, target_ip: str, handler: SatisfactoryHandler, 
                 on_traffic_callback: Optional[Callable] = None):
        self.port = port
        self.target_ip = target_ip
        self.handler = handler
        self.on_traffic_callback = on_traffic_callback
        self.transport: Optional[asyncio.DatagramTransport] = None
        
        # Connection tracking
        self.active_connections: Dict[str, float] = {}
        self.connection_timeout = 300  # 5 minutes
    
    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Called when the UDP socket is ready."""
        self.transport = transport
        sock = transport.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                # SO_REUSEPORT not available on all platforms
                pass
        
        logger.debug(f"Satisfactory UDP protocol ready on port {self.port}")
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle received UDP datagram."""
        try:
            client_id = f"{addr[0]}:{addr[1]}"
            current_time = time.time()
            
            # Update statistics
            self.handler.stats["packets_received"] += 1
            self.handler.stats["last_activity"] = current_time
            
            # Track new connections
            if client_id not in self.active_connections:
                self.active_connections[client_id] = current_time
                self.handler.stats["connections_detected"] += 1
                logger.info(f"New Satisfactory connection detected from {addr} on port {self.port}")
                
                # Notify about traffic (potential server wake trigger)
                if self.on_traffic_callback:
                    asyncio.create_task(self.on_traffic_callback(
                        protocol="satisfactory",
                        port=self.port,
                        client_addr=addr,
                        data_size=len(data)
                    ))
            else:
                # Update existing connection timestamp
                self.active_connections[client_id] = current_time
            
            # Clean up old connections
            self._cleanup_old_connections(current_time)
            
            # Log packet details for debugging
            logger.debug(f"Satisfactory UDP packet from {addr} on port {self.port}: {len(data)} bytes")
            
            # Handle packet based on current mode
            if self.handler.forwarding_active:
                # Forward to main server
                asyncio.create_task(self.handler.forward_packet(data, addr, self.port))
            else:
                # In proxy mode - could respond with server starting message
                # For Satisfactory, we typically just drop packets or close connection
                logger.debug(f"Packet from {addr} dropped (server not ready)")
            
        except Exception as e:
            logger.error(f"Error handling Satisfactory UDP packet from {addr}: {e}")
    
    def error_received(self, exc: Exception) -> None:
        """Handle UDP errors."""
        logger.error(f"Satisfactory UDP error on port {self.port}: {exc}")
    
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection loss."""
        if exc:
            logger.error(f"Satisfactory UDP connection lost on port {self.port}: {exc}")
        else:
            logger.debug(f"Satisfactory UDP connection closed on port {self.port}")
    
    def _cleanup_old_connections(self, current_time: float) -> None:
        """Remove old connection tracking entries."""
        cutoff_time = current_time - self.connection_timeout
        
        old_connections = [
            client_id for client_id, timestamp in self.active_connections.items()
            if timestamp < cutoff_time
        ]
        
        for client_id in old_connections:
            del self.active_connections[client_id]
            logger.debug(f"Cleaned up old Satisfactory connection: {client_id}")
    
    def get_active_connections(self) -> Dict[str, float]:
        """Get currently active connections."""
        current_time = time.time()
        self._cleanup_old_connections(current_time)
        return self.active_connections.copy()


class SatisfactoryForwarder:
    """Transparent UDP forwarder for when the main server is online."""
    
    def __init__(self, config: dict):
        self.config = config
        self.target_ip = config["server"]["target_ip"]
        self.satisfactory_config = config["satisfactory"]
        
        self.forwarders: Dict[int, asyncio.DatagramTransport] = {}
        self.is_active = False
    
    async def start_transparent_forwarding(self) -> bool:
        """Start transparent UDP forwarding to main server."""
        try:
            ports = [
                self.satisfactory_config["game_port"],
                self.satisfactory_config["query_port"],
                self.satisfactory_config["beacon_port"]
            ]
            
            for port in ports:
                # Create transparent forwarder
                transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
                    lambda p=port: TransparentForwardProtocol(self.target_ip, p),
                    local_addr=('0.0.0.0', port),
                    reuse_port=True
                )
                
                self.forwarders[port] = transport
                logger.debug(f"Transparent UDP forwarder started on port {port}")
            
            self.is_active = True
            logger.info("Satisfactory transparent UDP forwarding active")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start transparent forwarding: {e}")
            await self.stop_transparent_forwarding()
            return False
    
    async def stop_transparent_forwarding(self) -> None:
        """Stop transparent UDP forwarding."""
        for port, transport in self.forwarders.items():
            try:
                transport.close()
            except Exception as e:
                logger.error(f"Error stopping forwarder on port {port}: {e}")
        
        self.forwarders.clear()
        self.is_active = False
        logger.info("Satisfactory transparent UDP forwarding stopped")


class TransparentForwardProtocol(asyncio.DatagramProtocol):
    """Simple transparent UDP forwarding protocol."""
    
    def __init__(self, target_ip: str, target_port: int):
        self.target_ip = target_ip
        self.target_port = target_port
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.forward_socket: Optional[socket.socket] = None
    
    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Initialize transparent forwarding."""
        self.transport = transport
        
        # Create forwarding socket
        try:
            self.forward_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.forward_socket.settimeout(1.0)
        except Exception as e:
            logger.error(f"Failed to create forward socket: {e}")
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Forward all packets transparently."""
        if self.forward_socket:
            try:
                self.forward_socket.sendto(data, (self.target_ip, self.target_port))
            except Exception as e:
                logger.debug(f"Forward failed for {addr}: {e}")
    
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Clean up forwarding socket."""
        if self.forward_socket:
            try:
                self.forward_socket.close()
            except:
                pass