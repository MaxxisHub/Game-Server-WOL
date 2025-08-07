# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wake-on-LAN Proxy for game servers (Minecraft and Satisfactory) that runs on ARM boards. The proxy takes over the game server's IP when the main server is offline, detects real join attempts, sends WoL packets, and seamlessly hands off control to the main server when it boots.

## Architecture

### State Management
- **OFFLINE**: Proxy binds to server IP, listens on game ports, shows "Join to start server" 
- **STARTING**: WoL sent, proxy shows "Server starting" messages, retains IP binding
- **ONLINE**: Main server is up, proxy releases IP/ports, forwards all traffic transparently
- **MONITORING**: Proxy monitors main server health, returns to OFFLINE when server shuts down

### Protocol Handling
- **Minecraft (TCP 25565)**: Protocol-aware - distinguishes status pings from login attempts, provides custom MOTDs and kick messages
- **Satisfactory (UDP 7777/15000/15777)**: Simple traffic detection - any packet triggers WoL

### Technical Implementation
- Asyncio-based for efficiency on low-power ARM boards
- Dynamic IP binding using `sudo ip addr add/del` commands
- Transparent TCP proxying after server handoff
- SO_REUSEADDR for seamless port transitions

## Development Commands

```bash
# Install dependencies  
pip install -r requirements.txt

# Run development server
python main.py

# Install as systemd service
sudo cp wol-proxy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wol-proxy.service

# Monitor service
systemctl status wol-proxy.service
journalctl -u wol-proxy.service -f
```

## Required Project Files

- `main.py` - Main asyncio service with state machine
- `config.json` - All parameters (IPs, MACs, ports, messages, timeouts)  
- `requirements.txt` - Dependencies (wakeonlan, asyncio libraries)
- `wol-proxy.service` - Systemd unit file
- `README.md` - Complete setup guide from clean ARM board install

## Configuration Structure

Key config sections needed:
- Server details (IP, MAC address)
- Game-specific settings (ports, MOTD messages, kick messages)
- Timing parameters (boot wait, health check intervals)
- Logging configuration

## Critical Implementation Notes

- Must handle IP/port binding conflicts gracefully during server transitions
- Requires sudo privileges for IP management - document sudoers setup
- All user-facing messages must be configurable
- Comprehensive logging of state transitions, WoL events, and errors
- Health checking to detect main server shutdown and resume proxy mode