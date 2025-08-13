#!/usr/bin/env python3
"""Wake-on-LAN Game Server Proxy - Main Entry Point

A Python service that acts as a transparent proxy for game servers,
automatically waking the main server via Wake-on-LAN when players attempt to join.
"""

import asyncio
import argparse
import logging
import logging.handlers
import sys
import os
import json
from pathlib import Path

try:
    import sdnotify
except ImportError:
    sdnotify = None

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.proxy_manager import ProxyManager
from src.config_manager import ConfigManager


def setup_logging(config: dict) -> None:
    """Set up logging configuration."""
    log_config = config.get("logging", {})
    log_level = getattr(logging, log_config.get("level", "INFO").upper())
    log_file = log_config.get("file", "/var/log/wol-proxy.log")
    max_size_mb = log_config.get("max_size_mb", 10)
    backup_count = log_config.get("backup_count", 3)
    console_output = log_config.get("console_output", True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        logging.info(f"Logging configured - Level: {log_config.get('level', 'INFO')}, File: {log_file}")
        
    except Exception as e:
        print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)
        print("Continuing with console logging only", file=sys.stderr)


async def status_server(config: dict, port: int, proxy_manager_ref=None) -> None:
    """Start a simple HTTP status server for monitoring."""
    from aiohttp import web, web_runner
    
    async def get_status(request):
        """Get proxy status as JSON."""
        if proxy_manager_ref and proxy_manager_ref.is_running:
            status = proxy_manager_ref.get_status()
            config_info = proxy_manager_ref.get_config_info()
            return web.json_response({
                "status": "running",
                "proxy": status,
                "config": config_info
            })
        else:
            return web.json_response({
                "status": "stopped",
                "message": "Proxy is not running"
            }, status=503)
    
    async def health_check(request):
        """Simple health check endpoint."""
        return web.json_response({"status": "healthy"})
    
    # Create web application
    app = web.Application()
    app.router.add_get('/status', get_status)
    app.router.add_get('/health', health_check)
    app.router.add_get('/', get_status)
    
    # Start server
    runner = web_runner.AppRunner(app)
    await runner.setup()
    
    site = web_runner.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logging.info(f"Status server started on port {port}")
    return runner


async def main_service(args) -> int:
    """Main service function."""
    try:
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load_config()
        
        # Set up logging
        setup_logging(config)
        
        logging.info("Starting WoL Game Server Proxy")
        logging.info(f"Configuration loaded from: {args.config}")
        
        # Create proxy manager
        proxy_manager = ProxyManager(args.config)
        
        # Initialize proxy
        if not await proxy_manager.initialize():
            logging.error("Failed to initialize proxy")
            return 1
        
        # Start status server if enabled
        status_runner = None
        if config["monitoring"]["health_check_enabled"]:
            status_port = config["monitoring"]["status_endpoint_port"]
            try:
                status_runner = await status_server(config, status_port, proxy_manager)
            except Exception as e:
                logging.warning(f"Failed to start status server: {e}")
        
        # Start proxy service
        if not await proxy_manager.start():
            logging.error("Failed to start proxy service")
            return 1
        
        # Run until shutdown
        try:
            await proxy_manager.run_forever()
        except KeyboardInterrupt:
            logging.info("Received interrupt signal")
        
        # Clean shutdown
        await proxy_manager.shutdown()
        
        if status_runner:
            await status_runner.cleanup()
        
        logging.info("WoL Game Server Proxy stopped")
        return 0
        
    except Exception as e:
        logging.error(f"Fatal error in main service: {e}")
        return 1


def create_example_config(path: str) -> None:
    """Create an example configuration file."""
    config_manager = ConfigManager()
    config_manager.save_example_config(path)
    print(f"Example configuration saved to: {path}")


def validate_config(path: str) -> None:
    """Validate configuration file."""
    try:
        config_manager = ConfigManager(path)
        config = config_manager.load_config()
        print(f"Configuration file {path} is valid")
        
        # Print summary
        print("\nConfiguration Summary:")
        print(f"  Target Server: {config['server']['target_ip']} ({config['server']['mac_address']})")
        print(f"  Minecraft: {'Enabled' if config['minecraft']['enabled'] else 'Disabled'}")
        if config['minecraft']['enabled']:
            print(f"    Port: {config['minecraft']['port']}")
        print(f"  Satisfactory: {'Enabled' if config['satisfactory']['enabled'] else 'Disabled'}")
        if config['satisfactory']['enabled']:
            satisfactory = config['satisfactory']
            print(f"    Ports: {satisfactory['game_port']}, {satisfactory['query_port']}, {satisfactory['beacon_port']}")
        print(f"  Boot Wait Time: {config['timing']['boot_wait_seconds']} seconds")
        
    except Exception as e:
        print(f"Configuration validation failed: {e}", file=sys.stderr)
        sys.exit(1)


def show_status(config_path: str) -> None:
    """Show current proxy status."""
    try:
        import requests
        
        # Load config to get status port
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()
        
        if not config["monitoring"]["health_check_enabled"]:
            print("Status endpoint is disabled in configuration")
            return
        
        port = config["monitoring"]["status_endpoint_port"]
        url = f"http://localhost:{port}/status"
        
        response = requests.get(url, timeout=5)
        status_data = response.json()
        
        print("WoL Game Server Proxy Status:")
        print(f"  Status: {status_data['status']}")
        
        if 'proxy' in status_data:
            proxy = status_data['proxy']
            print(f"  Proxy State: {proxy['proxy_state']}")
            print(f"  Server State: {proxy['server_state']}")
            print(f"  IP Bound: {proxy['ip_bound']}")
            print(f"  Running: {proxy['is_running']}")
            
            stats = proxy['statistics']
            print(f"  Wake Attempts: {stats['wake_attempts']}")
            print(f"  Successful Wakes: {stats['successful_wakes']}")
            print(f"  Minecraft Connections: {stats['minecraft_connections']}")
            print(f"  Satisfactory Connections: {stats['satisfactory_connections']}")
        
    except ImportError:
        print("requests library not available for status checking")
    except Exception as e:
        print(f"Failed to get status: {e}")


def main():
    """Main entry point with command line argument handling."""
    parser = argparse.ArgumentParser(
        description="Wake-on-LAN Game Server Proxy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Run with default config.json
  %(prog)s --config /etc/wol-proxy.json # Run with custom config
  %(prog)s --create-config               # Create example config
  %(prog)s --validate-config             # Validate current config
  %(prog)s --status                      # Show current status
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config.json',
        help='Configuration file path (default: config.json)'
    )
    
    parser.add_argument(
        '--create-config',
        action='store_true',
        help='Create an example configuration file'
    )
    
    parser.add_argument(
        '--validate-config',
        action='store_true',
        help='Validate the configuration file'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show current proxy status'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='WoL Game Server Proxy 1.0.0'
    )
    
    args = parser.parse_args()
    
    # Handle special commands
    if args.create_config:
        create_example_config(args.config + '.example')
        return 0
    
    if args.validate_config:
        validate_config(args.config)
        return 0
    
    if args.status:
        show_status(args.config)
        return 0
    
    # Run main service
    try:
        return asyncio.run(main_service(args))
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())