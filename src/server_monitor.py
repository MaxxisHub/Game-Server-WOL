"""Server monitoring and health checking functionality."""

import asyncio
import logging
import socket
import subprocess
import time
from enum import Enum
from typing import Optional, Dict, Any, List
import ipaddress


logger = logging.getLogger(__name__)


class ServerState(Enum):
    """Server states for monitoring."""
    OFFLINE = "offline"
    STARTING = "starting"
    ONLINE = "online"
    UNKNOWN = "unknown"


class ServerMonitor:
    """Monitors main game server health and availability."""
    
    def __init__(self, config: dict):
        self.config = config
        self.target_ip = config["server"]["target_ip"]
        self.network_interface = config["server"]["network_interface"]
        
        # Monitoring configuration
        self.health_check_interval = config["timing"]["health_check_interval"]
        self.server_check_timeout = config["timing"]["server_check_timeout"]
        self.connection_timeout = config["timing"]["connection_timeout"]
        
        # Game port configuration
        self.minecraft_enabled = config["minecraft"]["enabled"]
        self.minecraft_port = config["minecraft"]["port"] if self.minecraft_enabled else None
        
        self.satisfactory_enabled = config["satisfactory"]["enabled"]
        self.satisfactory_ports = []
        if self.satisfactory_enabled:
            satisfactory_config = config["satisfactory"]
            self.satisfactory_ports = [
                satisfactory_config["game_port"],
                satisfactory_config["query_port"],
                satisfactory_config["beacon_port"]
            ]
        
        # State tracking
        self.current_state = ServerState.OFFLINE
        self.last_check_time = 0.0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
        # Statistics
        self.stats = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "state_changes": 0,
            "last_online_time": None,
            "last_offline_time": time.time(),
            "uptime_start": None
        }
        
        # Monitoring task
        self.monitor_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
    
    async def check_server_reachable(self) -> bool:
        """Check if the main server is reachable via TCP connection to game ports only."""
        # Only check Minecraft port - SSH port can be misleading due to network devices
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.target_ip, 25565),  # Minecraft port only
                timeout=self.server_check_timeout
            )
            writer.close()
            await writer.wait_closed()
            logger.debug(f"Server {self.target_ip} reachable via Minecraft port")
            return True
            
        except Exception as e:
            logger.debug(f"Server not reachable on Minecraft port: {e}")
            return False
    
    async def check_port_open(self, port: int, protocol: str = "tcp") -> bool:
        """Check if a specific port is open on the main server."""
        try:
            if protocol.lower() == "tcp":
                # TCP port check
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.target_ip, port),
                    timeout=self.server_check_timeout
                )
                writer.close()
                await writer.wait_closed()
                return True
                
            elif protocol.lower() == "udp":
                # UDP port check (basic socket connection)
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(self.server_check_timeout)
                try:
                    # For UDP, we can only check if the socket can be created
                    # and if the target responds (though this is not reliable)
                    sock.connect((self.target_ip, port))
                    return True
                finally:
                    sock.close()
            
            return False
            
        except Exception as e:
            logger.debug(f"{protocol.upper()} port {port} check failed for {self.target_ip}: {e}")
            return False
    
    async def comprehensive_server_check(self) -> bool:
        """Perform comprehensive server availability check."""
        checks = []
        
        # Basic reachability check
        ping_result = await self.check_server_reachable()
        checks.append(("ping", ping_result))
        
        if not ping_result:
            logger.debug("Server not reachable via ping")
            return False
        
        # Game-specific port checks
        if self.minecraft_enabled and self.minecraft_port:
            minecraft_check = await self.check_port_open(self.minecraft_port, "tcp")
            checks.append((f"minecraft_tcp_{self.minecraft_port}", minecraft_check))
        
        if self.satisfactory_enabled:
            for port in self.satisfactory_ports:
                # For Satisfactory, we mainly check if the server process is binding to ports
                # UDP checks are less reliable, so we rely more on ping + process detection
                udp_check = await self.check_port_open(port, "udp")
                checks.append((f"satisfactory_udp_{port}", udp_check))
        
        # Consider server online if ping works and at least one game port is available
        game_ports_available = any(result for name, result in checks if "tcp_" in name or "udp_" in name)
        
        if self.minecraft_enabled and not self.satisfactory_enabled:
            # Minecraft only - require Minecraft port
            return any(result for name, result in checks if "minecraft_tcp_" in name)
        elif self.satisfactory_enabled and not self.minecraft_enabled:
            # Satisfactory only - ping is sufficient (UDP checks are unreliable)
            return ping_result
        else:
            # Both games - require ping and at least one port
            return ping_result and game_ports_available
    
    async def update_server_state(self) -> ServerState:
        """Update and return current server state."""
        self.stats["total_checks"] += 1
        self.last_check_time = time.time()
        
        try:
            is_online = await self.comprehensive_server_check()
            
            if is_online:
                self.consecutive_failures = 0
                self.consecutive_successes += 1
                self.stats["successful_checks"] += 1
                
                if self.current_state != ServerState.ONLINE:
                    logger.info("Main server is now ONLINE")
                    self.current_state = ServerState.ONLINE
                    self.stats["state_changes"] += 1
                    self.stats["last_online_time"] = time.time()
                    self.stats["uptime_start"] = time.time()
                    
            else:
                self.consecutive_successes = 0
                self.consecutive_failures += 1
                self.stats["failed_checks"] += 1
                
                if self.current_state != ServerState.OFFLINE:
                    logger.info("Main server is now OFFLINE")
                    self.current_state = ServerState.OFFLINE
                    self.stats["state_changes"] += 1
                    self.stats["last_offline_time"] = time.time()
                    self.stats["uptime_start"] = None
                    
        except Exception as e:
            logger.error(f"Error during server state check: {e}")
            self.current_state = ServerState.UNKNOWN
        
        return self.current_state
    
    async def wait_for_server_online(self, max_wait_seconds: Optional[int] = None, 
                                   check_interval: int = 5) -> bool:
        """
        Wait for server to come online.
        
        Args:
            max_wait_seconds: Maximum time to wait (None = wait indefinitely)
            check_interval: Seconds between checks
            
        Returns:
            True if server came online, False if timeout
        """
        start_time = time.time()
        
        logger.info(f"Waiting for server to come online (max wait: {max_wait_seconds}s)")
        
        while True:
            current_state = await self.update_server_state()
            
            if current_state == ServerState.ONLINE:
                elapsed = time.time() - start_time
                logger.info(f"Server came online after {elapsed:.1f} seconds")
                return True
            
            # Check timeout
            if max_wait_seconds:
                elapsed = time.time() - start_time
                if elapsed >= max_wait_seconds:
                    logger.warning(f"Server did not come online within {max_wait_seconds} seconds")
                    return False
            
            # Wait before next check
            await asyncio.sleep(check_interval)
    
    async def start_monitoring(self, state_change_callback: Optional[callable] = None) -> None:
        """Start continuous server monitoring."""
        if self.is_monitoring:
            logger.warning("Server monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(
            self._monitoring_loop(state_change_callback)
        )
        logger.info(f"Server monitoring started (interval: {self.health_check_interval}s)")
    
    async def stop_monitoring(self) -> None:
        """Stop server monitoring."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Server monitoring stopped")
    
    async def _monitoring_loop(self, state_change_callback: Optional[callable] = None) -> None:
        """Main monitoring loop."""
        last_state = self.current_state
        
        while self.is_monitoring:
            try:
                # Update server state
                current_state = await self.update_server_state()
                
                # Check for state changes
                if current_state != last_state:
                    logger.info(f"Server state changed: {last_state.value} -> {current_state.value}")
                    
                    if state_change_callback:
                        try:
                            await state_change_callback(last_state, current_state)
                        except Exception as e:
                            logger.error(f"Error in state change callback: {e}")
                    
                    last_state = current_state
                
                # Wait for next check
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        current_time = time.time()
        
        uptime = None
        if self.stats["uptime_start"]:
            uptime = current_time - self.stats["uptime_start"]
        
        return {
            **self.stats,
            "current_state": self.current_state.value,
            "last_check_time": self.last_check_time,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "uptime_seconds": uptime,
            "monitoring_active": self.is_monitoring
        }
    
    def reset_stats(self) -> None:
        """Reset monitoring statistics."""
        current_time = time.time()
        self.stats = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "state_changes": 0,
            "last_online_time": self.stats.get("last_online_time"),
            "last_offline_time": current_time if self.current_state == ServerState.OFFLINE else self.stats.get("last_offline_time"),
            "uptime_start": self.stats.get("uptime_start") if self.current_state == ServerState.ONLINE else None
        }
        
        self.consecutive_failures = 0
        self.consecutive_successes = 0


class IPAddressManager:
    """Manages IP address binding for seamless server transitions."""
    
    def __init__(self, config: dict):
        self.config = config
        self.target_ip = config["server"]["target_ip"]
        self.network_interface = config["server"]["network_interface"]
        
        self.ip_bound = False
        
    async def bind_ip_address(self) -> bool:
        """Bind the target IP address to the network interface."""
        try:
            # Use ip command to add address (with CAP_NET_ADMIN capability)
            cmd = [
                'ip', 'addr', 'add', 
                f'{self.target_ip}/24', 
                'dev', self.network_interface
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.ip_bound = True
                logger.info(f"Successfully bound IP {self.target_ip} to {self.network_interface}")
                return True
            else:
                # Check if IP is already assigned (not an error)
                stderr_text = stderr.decode('utf-8').lower()
                if 'file exists' in stderr_text or 'already' in stderr_text:
                    self.ip_bound = True
                    logger.debug(f"IP {self.target_ip} already bound to {self.network_interface}")
                    return True
                else:
                    logger.error(f"Failed to bind IP {self.target_ip}: {stderr.decode('utf-8')}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error binding IP address: {e}")
            return False
    
    async def release_ip_address(self) -> bool:
        """Release the target IP address from the network interface."""
        if not self.ip_bound:
            logger.debug(f"IP {self.target_ip} not currently bound")
            return True
            
        try:
            # Use ip command to delete address (with CAP_NET_ADMIN capability)
            cmd = [
                'ip', 'addr', 'del', 
                f'{self.target_ip}/24', 
                'dev', self.network_interface
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.ip_bound = False
                logger.info(f"Successfully released IP {self.target_ip} from {self.network_interface}")
                return True
            else:
                stderr_text = stderr.decode('utf-8').lower()
                if 'cannot assign' in stderr_text or 'not found' in stderr_text:
                    self.ip_bound = False
                    logger.debug(f"IP {self.target_ip} was not bound to {self.network_interface}")
                    return True
                else:
                    logger.error(f"Failed to release IP {self.target_ip}: {stderr.decode('utf-8')}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error releasing IP address: {e}")
            return False
    
    async def refresh_arp_table(self) -> bool:
        """Refresh ARP table to ensure network awareness of IP changes."""
        try:
            # Send gratuitous ARP to announce IP presence
            cmd = ['arping', '-c', '2', '-A', '-I', self.network_interface, self.target_ip]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            await asyncio.wait_for(process.wait(), timeout=5.0)
            logger.debug(f"ARP table refreshed for {self.target_ip}")
            return True
            
        except Exception as e:
            logger.debug(f"ARP refresh failed (non-critical): {e}")
            return False
    
    def is_ip_bound(self) -> bool:
        """Check if IP is currently bound."""
        return self.ip_bound