"""Configuration management for the Wake-on-LAN Game Server Proxy."""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional
import ipaddress


logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading, validation, and hot-reloading."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._default_config = self._get_default_config()
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "server": {
                "target_ip": "192.168.1.100",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "network_interface": "eth0"
            },
            "timing": {
                "boot_wait_seconds": 90,
                "health_check_interval": 15,
                "wol_retry_interval": 5,
                "connection_timeout": 30,
                "server_check_timeout": 5
            },
            "minecraft": {
                "enabled": True,
                "port": 25565,
                "protocol_version": 763,
                "motd_offline": "§aJoin to start server",
                "motd_starting": "§eServer is starting, please wait",
                "version_text_starting": "Starting...",
                "kick_message": "§eServer is starting up, try joining again in a minute.",
                "max_players_display": 20
            },
            "satisfactory": {
                "enabled": True,
                "game_port": 7777,
                "query_port": 15000,
                "beacon_port": 15777
            },
            "logging": {
                "level": "INFO",
                "file": "/var/log/wol-proxy.log",
                "max_size_mb": 10,
                "backup_count": 3,
                "console_output": True
            },
            "monitoring": {
                "health_check_enabled": True,
                "status_endpoint_port": 8080,
                "metrics_enabled": False
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file with validation."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Config file {self.config_path} not found, using defaults")
                self._config = self._default_config.copy()
                return self._config
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            # Merge with defaults to ensure all keys exist
            self._config = self._merge_config(self._default_config, loaded_config)
            
            # Validate configuration
            self._validate_config()
            
            logger.info(f"Configuration loaded successfully from {self.config_path}")
            return self._config
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise ValueError(f"Configuration file contains invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def _merge_config(self, default: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge loaded config with defaults."""
        result = default.copy()
        
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def _validate_config(self) -> None:
        """Validate configuration values."""
        errors = []
        
        # Validate server configuration
        if not self._validate_ip_address(self._config["server"]["target_ip"]):
            errors.append(f"Invalid target IP address: {self._config['server']['target_ip']}")
        
        if not self._validate_mac_address(self._config["server"]["mac_address"]):
            errors.append(f"Invalid MAC address: {self._config['server']['mac_address']}")
        
        # Validate ports
        minecraft_port = self._config["minecraft"]["port"]
        if not self._validate_port(minecraft_port):
            errors.append(f"Invalid Minecraft port: {minecraft_port}")
        
        satisfactory_ports = [
            self._config["satisfactory"]["game_port"],
            self._config["satisfactory"]["query_port"],
            self._config["satisfactory"]["beacon_port"]
        ]
        
        for port in satisfactory_ports:
            if not self._validate_port(port):
                errors.append(f"Invalid Satisfactory port: {port}")
        
        # Validate timing values (skip comment fields)
        timing = self._config["timing"]
        for key, value in timing.items():
            if key.startswith('_comment'):
                continue
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"Invalid timing value for {key}: {value}")
        
        # Validate logging configuration
        log_level = self._config["logging"]["level"].upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level not in valid_levels:
            errors.append(f"Invalid log level: {log_level}. Must be one of {valid_levels}")
        
        if errors:
            error_msg = "Configuration validation failed:\\n" + "\\n".join(errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _validate_ip_address(self, ip: str) -> bool:
        """Validate IP address format."""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def _validate_mac_address(self, mac: str) -> bool:
        """Validate MAC address format."""
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        return bool(mac_pattern.match(mac))
    
    def _validate_port(self, port: int) -> bool:
        """Validate port number."""
        return isinstance(port, int) and 1 <= port <= 65535
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'server.target_ip')."""
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def reload_config(self) -> bool:
        """Reload configuration from file."""
        try:
            old_config = self._config.copy()
            self.load_config()
            logger.info("Configuration reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            # Restore old configuration
            self._config = old_config
            return False
    
    def save_example_config(self, path: Optional[str] = None) -> None:
        """Save an example configuration file with comments."""
        if path is None:
            path = "config.json.example"
        
        example_config = {
            "_comment_server": "Main server configuration",
            "server": {
                "_comment": "IP address and MAC of the main game server",
                "target_ip": "192.168.1.100",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "network_interface": "eth0"
            },
            "_comment_timing": "Timing and timeout configuration",
            "timing": {
                "_comment": "All values in seconds",
                "boot_wait_seconds": 90,
                "health_check_interval": 15,
                "wol_retry_interval": 5,
                "connection_timeout": 30,
                "server_check_timeout": 5
            },
            "_comment_minecraft": "Minecraft-specific settings",
            "minecraft": {
                "enabled": True,
                "port": 25565,
                "protocol_version": 763,
                "motd_offline": "§aJoin to start server",
                "motd_starting": "§eServer is starting, please wait",
                "version_text_starting": "Starting...",
                "kick_message": "§eServer is starting up, try joining again in a minute.",
                "max_players_display": 20
            },
            "_comment_satisfactory": "Satisfactory-specific settings",
            "satisfactory": {
                "enabled": True,
                "game_port": 7777,
                "query_port": 15000,
                "beacon_port": 15777
            },
            "_comment_logging": "Logging configuration",
            "logging": {
                "level": "INFO",
                "file": "/var/log/wol-proxy.log",
                "max_size_mb": 10,
                "backup_count": 3,
                "console_output": True
            },
            "_comment_monitoring": "Monitoring and health check settings",
            "monitoring": {
                "health_check_enabled": True,
                "status_endpoint_port": 8080,
                "metrics_enabled": False
            }
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(example_config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Example configuration saved to {path}")
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get the current configuration."""
        return self._config.copy()