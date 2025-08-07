"""Main proxy manager coordinating all components and state transitions."""

import asyncio
import logging
import signal
import time
from enum import Enum
from typing import Optional, Dict, Any, Callable, List
import json

from .config_manager import ConfigManager
from .wol_sender import WoLSender
from .minecraft_handler import MinecraftHandler
from .satisfactory_handler import SatisfactoryHandler
from .server_monitor import ServerMonitor, ServerState, IPAddressManager


logger = logging.getLogger(__name__)


class ProxyState(Enum):
    """Proxy operational states."""
    OFFLINE = "offline"          # Proxy active, main server offline
    WAKING = "waking"           # WoL sent, waiting for server response
    STARTING = "starting"       # Server responding but not fully ready
    PROXYING = "proxying"       # Transparent forwarding to main server
    STOPPING = "stopping"      # Shutting down gracefully


class ProxyManager:
    """Central coordinator for the Wake-on-LAN game server proxy."""
    
    def __init__(self, config_path: str = "config.json"):
        # Configuration
        self.config_manager = ConfigManager(config_path)
        self.config = {}
        
        # Core components
        self.wol_sender: Optional[WoLSender] = None
        self.minecraft_handler: Optional[MinecraftHandler] = None
        self.satisfactory_handler: Optional[SatisfactoryHandler] = None
        self.server_monitor: Optional[ServerMonitor] = None
        self.ip_manager: Optional[IPAddressManager] = None
        
        # State management
        self.current_state = ProxyState.OFFLINE
        self.state_change_time = time.time()
        self.wake_attempt_time: Optional[float] = None
        
        # Active servers
        self.minecraft_server: Optional[asyncio.Server] = None
        self.satisfactory_servers: Dict[int, Any] = {}
        
        # Control
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # Statistics
        self.stats = {
            "start_time": time.time(),
            "wake_attempts": 0,
            "successful_wakes": 0,
            "minecraft_connections": 0,
            "satisfactory_connections": 0,
            "state_transitions": 0,
            "last_wake_time": None,
            "total_uptime": 0.0
        }
        
        # Callbacks
        self.state_change_callbacks: List[Callable] = []
    
    async def initialize(self) -> bool:
        """Initialize all components."""
        try:
            logger.info("Initializing WoL Game Server Proxy...")
            
            # Load configuration
            self.config = self.config_manager.load_config()
            logger.info("Configuration loaded successfully")
            
            # Initialize components
            self.wol_sender = WoLSender(self.config)
            logger.debug("WoL sender initialized")
            
            if self.config["minecraft"]["enabled"]:
                self.minecraft_handler = MinecraftHandler(self.config)
                logger.debug("Minecraft handler initialized")
            
            if self.config["satisfactory"]["enabled"]:
                self.satisfactory_handler = SatisfactoryHandler(self.config)
                logger.debug("Satisfactory handler initialized")
            
            self.server_monitor = ServerMonitor(self.config)
            self.ip_manager = IPAddressManager(self.config)
            logger.debug("Server monitor and IP manager initialized")
            
            # Validate configuration
            if not self.wol_sender.validate_configuration():
                raise ValueError("WoL configuration validation failed")
            
            logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the proxy service."""
        if self.is_running:
            logger.warning("Proxy is already running")
            return False
        
        try:
            logger.info("Starting WoL Game Server Proxy...")
            
            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            # Bind IP address
            if not await self.ip_manager.bind_ip_address():
                logger.error("Failed to bind target IP address")
                return False
            
            # Start game server handlers
            await self._start_game_handlers()
            
            # Start server monitoring
            await self.server_monitor.start_monitoring(self._on_server_state_change)
            
            # Initialize proxy state
            await self._transition_to_state(ProxyState.OFFLINE)
            
            self.is_running = True
            logger.info("WoL Game Server Proxy started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start proxy: {e}")
            await self.shutdown()
            return False
    
    async def _start_game_handlers(self) -> None:
        """Start game-specific protocol handlers."""
        # Start Minecraft server if enabled
        if self.minecraft_handler:
            self.minecraft_server = await self.minecraft_handler.start_server(
                self._handle_minecraft_connection
            )
            logger.info(f"Minecraft proxy started on port {self.config['minecraft']['port']}")
        
        # Start Satisfactory handlers if enabled
        if self.satisfactory_handler:
            self.satisfactory_servers = await self.satisfactory_handler.start_udp_listeners(
                self._handle_satisfactory_traffic
            )
            logger.info("Satisfactory UDP listeners started")
    
    async def _handle_minecraft_connection(self, reader: asyncio.StreamReader, 
                                         writer: asyncio.StreamWriter,
                                         handler: MinecraftHandler) -> None:
        """Handle incoming Minecraft connections."""
        self.stats["minecraft_connections"] += 1
        
        # Determine if we're in starting state
        is_starting = self.current_state in [ProxyState.WAKING, ProxyState.STARTING]
        
        # Handle connection based on current state
        if self.current_state == ProxyState.PROXYING:
            # Forward to main server (transparent proxying)
            await self._forward_minecraft_connection(reader, writer)
        else:
            # Handle with protocol simulation
            is_login, info = await handler.handle_client_connection(reader, writer, is_starting)
            
            if is_login and self.current_state == ProxyState.OFFLINE:
                # Login attempt detected - wake server
                logger.info(f"Login attempt detected: {info}")
                await self._wake_server("Minecraft login attempt")
    
    async def _forward_minecraft_connection(self, client_reader: asyncio.StreamReader,
                                          client_writer: asyncio.StreamWriter) -> None:
        """Forward Minecraft connection transparently to main server."""
        target_ip = self.config["server"]["target_ip"]
        minecraft_port = self.config["minecraft"]["port"]
        
        try:
            # Connect to main server
            server_reader, server_writer = await asyncio.open_connection(
                target_ip, minecraft_port
            )
            
            # Start bidirectional forwarding
            async def forward_data(source_reader, dest_writer, direction):
                try:
                    while True:
                        data = await source_reader.read(8192)
                        if not data:
                            break
                        dest_writer.write(data)
                        await dest_writer.drain()
                except Exception as e:
                    logger.debug(f"Minecraft forwarding {direction} ended: {e}")
                finally:
                    try:
                        dest_writer.close()
                        await dest_writer.wait_closed()
                    except:
                        pass
            
            # Start forwarding tasks
            client_to_server = asyncio.create_task(
                forward_data(client_reader, server_writer, "client->server")
            )
            server_to_client = asyncio.create_task(
                forward_data(server_reader, client_writer, "server->client")
            )
            
            # Wait for either direction to close
            await asyncio.gather(client_to_server, server_to_client, return_exceptions=True)
            
            logger.debug("Minecraft connection forwarding completed")
            
        except Exception as e:
            logger.error(f"Minecraft connection forwarding failed: {e}")
        finally:
            # Clean up connections
            for writer in [client_writer, server_writer]:
                try:
                    if writer and not writer.is_closing():
                        writer.close()
                        await writer.wait_closed()
                except:
                    pass
    
    async def _handle_satisfactory_traffic(self, protocol: str, port: int, 
                                         client_addr: tuple, data_size: int) -> None:
        """Handle detected Satisfactory traffic."""
        self.stats["satisfactory_connections"] += 1
        
        logger.info(f"Satisfactory traffic detected from {client_addr} on port {port}")
        
        if self.current_state == ProxyState.OFFLINE:
            # Wake server on any Satisfactory traffic
            await self._wake_server(f"Satisfactory traffic on port {port}")
    
    async def _wake_server(self, reason: str) -> bool:
        """Wake the main server and transition state."""
        if self.current_state not in [ProxyState.OFFLINE]:
            logger.debug(f"Server wake requested ({reason}) but current state is {self.current_state.value}")
            return False
        
        logger.info(f"Waking server: {reason}")
        self.stats["wake_attempts"] += 1
        self.stats["last_wake_time"] = time.time()
        self.wake_attempt_time = time.time()
        
        # Transition to waking state
        await self._transition_to_state(ProxyState.WAKING)
        
        # Send Wake-on-LAN packet
        success = await self.wol_sender.wake_server_with_retry(max_retries=3)
        if not success:
            logger.error("Failed to send Wake-on-LAN packet")
            await self._transition_to_state(ProxyState.OFFLINE)
            return False
        
        # Transition to starting state and wait for server
        await self._transition_to_state(ProxyState.STARTING)
        
        # Start waiting for server to come online
        asyncio.create_task(self._wait_for_server_online())
        
        return True
    
    async def _wait_for_server_online(self) -> None:
        """Wait for server to come online after wake attempt."""
        boot_wait_seconds = self.config["timing"]["boot_wait_seconds"]
        
        logger.info(f"Waiting up to {boot_wait_seconds} seconds for server to boot")
        
        # Wait for server to come online
        server_online = await self.server_monitor.wait_for_server_online(
            max_wait_seconds=boot_wait_seconds,
            check_interval=5
        )
        
        if server_online:
            logger.info("Server boot detected - transitioning to proxying mode")
            self.stats["successful_wakes"] += 1
            await self._transition_to_state(ProxyState.PROXYING)
        else:
            logger.warning(f"Server did not come online within {boot_wait_seconds} seconds")
            await self._transition_to_state(ProxyState.OFFLINE)
    
    async def _on_server_state_change(self, old_state: ServerState, new_state: ServerState) -> None:
        """Handle server state changes from monitor."""
        logger.info(f"Server monitor state change: {old_state.value} -> {new_state.value}")
        
        if new_state == ServerState.ONLINE and self.current_state == ProxyState.STARTING:
            # Server came online while we were waiting
            await self._transition_to_state(ProxyState.PROXYING)
            
        elif new_state == ServerState.OFFLINE and self.current_state == ProxyState.PROXYING:
            # Server went offline while we were proxying
            await self._transition_to_state(ProxyState.OFFLINE)
    
    async def _transition_to_state(self, new_state: ProxyState) -> None:
        """Transition to a new proxy state."""
        if new_state == self.current_state:
            return
        
        old_state = self.current_state
        logger.info(f"Proxy state transition: {old_state.value} -> {new_state.value}")
        
        # Update state tracking
        self.current_state = new_state
        self.state_change_time = time.time()
        self.stats["state_transitions"] += 1
        
        # Perform state-specific actions
        if new_state == ProxyState.OFFLINE:
            await self._enter_offline_state()
        elif new_state == ProxyState.WAKING:
            await self._enter_waking_state()
        elif new_state == ProxyState.STARTING:
            await self._enter_starting_state()
        elif new_state == ProxyState.PROXYING:
            await self._enter_proxying_state()
        elif new_state == ProxyState.STOPPING:
            await self._enter_stopping_state()
        
        # Notify callbacks
        for callback in self.state_change_callbacks:
            try:
                await callback(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    async def _enter_offline_state(self) -> None:
        """Enter offline state - proxy active, main server offline."""
        # Ensure IP is bound to proxy
        await self.ip_manager.bind_ip_address()
        
        # Disable forwarding
        if self.satisfactory_handler:
            self.satisfactory_handler.disable_forwarding()
        
        logger.debug("Entered OFFLINE state - proxy active")
    
    async def _enter_waking_state(self) -> None:
        """Enter waking state - WoL sent, waiting briefly."""
        # Keep IP bound, disable forwarding
        if self.satisfactory_handler:
            self.satisfactory_handler.disable_forwarding()
        
        logger.debug("Entered WAKING state - WoL packet sent")
    
    async def _enter_starting_state(self) -> None:
        """Enter starting state - server booting."""
        # Keep IP bound, show starting messages
        if self.satisfactory_handler:
            self.satisfactory_handler.disable_forwarding()
        
        logger.debug("Entered STARTING state - server booting")
    
    async def _enter_proxying_state(self) -> None:
        """Enter proxying state - transparent forwarding."""
        # Release IP (let main server bind)
        await self.ip_manager.release_ip_address()
        
        # Enable transparent forwarding
        if self.satisfactory_handler:
            self.satisfactory_handler.enable_forwarding()
        
        # Refresh ARP to announce IP change
        await self.ip_manager.refresh_arp_table()
        
        logger.debug("Entered PROXYING state - transparent forwarding active")
    
    async def _enter_stopping_state(self) -> None:
        """Enter stopping state - graceful shutdown."""
        logger.debug("Entered STOPPING state - shutting down")
    
    async def run_forever(self) -> None:
        """Run the proxy service until shutdown."""
        try:
            logger.info("WoL Game Server Proxy running...")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """Shutdown the proxy service gracefully."""
        if not self.is_running:
            return
        
        logger.info("Shutting down WoL Game Server Proxy...")
        await self._transition_to_state(ProxyState.STOPPING)
        
        self.is_running = False
        
        try:
            # Stop server monitoring
            if self.server_monitor:
                await self.server_monitor.stop_monitoring()
            
            # Stop game handlers
            if self.minecraft_server:
                self.minecraft_server.close()
                await self.minecraft_server.wait_closed()
            
            if self.satisfactory_handler:
                await self.satisfactory_handler.stop_udp_listeners()
            
            # Release IP address
            if self.ip_manager:
                await self.ip_manager.release_ip_address()
            
            # Update stats
            self.stats["total_uptime"] = time.time() - self.stats["start_time"]
            
            logger.info("WoL Game Server Proxy shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signame):
            logger.info(f"Received {signame}, initiating shutdown...")
            self.shutdown_event.set()
        
        # Set up signal handlers
        for signame in ['SIGTERM', 'SIGINT']:
            if hasattr(signal, signame):
                signal.signal(getattr(signal, signame), lambda s, f: signal_handler(signame))
    
    def add_state_change_callback(self, callback: Callable) -> None:
        """Add a callback for state changes."""
        self.state_change_callbacks.append(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current proxy status."""
        current_time = time.time()
        
        return {
            "proxy_state": self.current_state.value,
            "server_state": self.server_monitor.current_state.value if self.server_monitor else "unknown",
            "state_change_time": self.state_change_time,
            "time_in_current_state": current_time - self.state_change_time,
            "is_running": self.is_running,
            "ip_bound": self.ip_manager.is_ip_bound() if self.ip_manager else False,
            "wake_attempt_time": self.wake_attempt_time,
            "statistics": self.stats,
            "server_monitor_stats": self.server_monitor.get_stats() if self.server_monitor else {},
            "satisfactory_stats": self.satisfactory_handler.get_stats() if self.satisfactory_handler else {}
        }
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get configuration information."""
        return {
            "target_ip": self.config["server"]["target_ip"],
            "mac_address": self.config["server"]["mac_address"],
            "minecraft_enabled": self.config["minecraft"]["enabled"],
            "minecraft_port": self.config["minecraft"]["port"] if self.config["minecraft"]["enabled"] else None,
            "satisfactory_enabled": self.config["satisfactory"]["enabled"],
            "satisfactory_ports": [
                self.config["satisfactory"]["game_port"],
                self.config["satisfactory"]["query_port"],
                self.config["satisfactory"]["beacon_port"]
            ] if self.config["satisfactory"]["enabled"] else [],
            "boot_wait_seconds": self.config["timing"]["boot_wait_seconds"],
            "health_check_interval": self.config["timing"]["health_check_interval"]
        }