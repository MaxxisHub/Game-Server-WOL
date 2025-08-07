# Changelog

All notable changes to the Wake-on-LAN Game Server Proxy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-XX-XX

### Added
- Initial release of Wake-on-LAN Game Server Proxy
- **Minecraft Support**
  - Protocol-aware status responses with custom MOTDs
  - Login attempt detection vs server list pings
  - Configurable kick messages and server info
  - Support for modern Minecraft protocol versions
- **Satisfactory Support**
  - UDP traffic detection on game ports (7777, 15000, 15777)
  - Wake-on-LAN trigger on any game traffic
  - Transparent UDP forwarding when server is online
- **Core Functionality**
  - Automated server wake via Wake-on-LAN magic packets
  - Dynamic IP address binding and release
  - State machine with OFFLINE → WAKING → STARTING → PROXYING → MONITORING states
  - Transparent TCP/UDP proxying when main server is online
  - Server health monitoring with automatic fallback to proxy mode
- **Configuration Management**
  - JSON-based configuration with validation
  - Hot-reload configuration support (SIGHUP)
  - Comprehensive configuration validation with helpful error messages
  - Example configuration generation
- **System Integration**
  - Systemd service with proper security sandboxing
  - Automated installation script for Debian-based systems
  - Sudo configuration for IP management privileges
  - Log rotation and management
- **Monitoring and Observability**
  - Built-in HTTP status endpoint for monitoring
  - Comprehensive logging with configurable levels
  - Statistics tracking for connections, wake attempts, and performance
  - Resource usage optimization for ARM boards
- **Security Features**
  - Dedicated service user with minimal privileges
  - Systemd security hardening (PrivateTmp, ProtectSystem, etc.)
  - Capability-based permissions for network operations
  - Secure configuration file handling
- **Developer Tools**
  - Comprehensive test suite
  - Configuration validation tools
  - Status monitoring commands
  - Development documentation

### Technical Details
- **Architecture**: Asynchronous Python using asyncio for high performance
- **Resource Usage**: Optimized for ARM boards (<50MB RAM, <1% CPU)
- **Compatibility**: Python 3.9+, Debian-based Linux systems
- **Protocols**: Minecraft Java Edition protocol, UDP traffic detection
- **Network**: IPv4 support, dynamic IP binding, ARP table management

### Documentation
- Complete README with installation and configuration guides
- Inline code documentation and type hints
- Troubleshooting guide with common issues and solutions
- Network configuration examples for routers and firewalls
- Windows gaming PC setup instructions

### Known Limitations
- Satisfactory server cannot appear "online" in server browser due to protocol complexity
- IPv6 support not implemented in initial release
- Wake-on-LAN requires main server to support magic packets
- Requires sudo privileges for IP address management

## [Unreleased]

### Planned Features
- IPv6 support
- Web-based configuration interface
- Multiple server support
- Docker containerization
- Integration with home automation systems
- Prometheus metrics export
- Additional game protocol support