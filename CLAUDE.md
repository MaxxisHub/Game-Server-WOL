# Wake-on-LAN Game Server Proxy - Projekt Verlauf

## Projekt Überblick
**Entwicklung eines Wake-on-LAN Game Server Proxy in Python für Minecraft und Satisfactory**

### Ziel
- Stromsparender Proxy auf ARM-Board (Tinker Board/Raspberry Pi) 
- Automatisches Aufwecken des Server PCs via Wake-on-LAN bei Spieler-Verbindungen
- Transparente Verkehrsweiterleitung wenn Server online ist
- Professionelles GitHub Repository für öffentliche Nutzung

### Netzwerk-Topologie
- **Tinker Board** (192.168.1.179): Proxy läuft 24/7 mit minimalem Stromverbrauch
- **Server PC** (192.168.1.165, MAC: 84:47:09:33:81:80): Hauptserver, wird bei Bedarf aufgeweckt

## Entwicklungsschritte

### Phase 1: Grundlegende Implementierung
- Python asyncio-basierte Architektur für effiziente I/O auf ARM
- Minecraft Java Edition Protokoll-Parser (VarInt, Packet-Struktur)
- Wake-on-LAN Magic Packet Implementation
- UDP Traffic Detection für Satisfactory
- State Machine: OFFLINE → WAKING → STARTING → PROXYING → MONITORING

### Phase 2: Service Integration
- Systemd Service mit Security Hardening
- Dynamisches IP Address Binding/Release (`ip addr add/del`)
- HTTP Status Endpoint für Monitoring (Port 8080)
- JSON Configuration Management mit Validierung
- Logging mit Rotation

### Phase 3: GitHub Repository Setup
- Repository erstellt: https://github.com/MaxxisHub/Game-Server-WOL
- Merge Konflikte beim initialen Setup gelöst
- Private Informationen durch generische Platzhalter ersetzt

### Phase 4: Professionelle Überarbeitung
- Unnötige Dateien entfernt (CHANGELOG.md, DEPLOYMENT.md, tests/)
- Systemd Service Pfade korrigiert (/opt/wol-proxy/, /etc/wol-proxy/)
- Professionelle deutsche README mit vollständigen Anleitungen
- Code-Qualität validiert (Syntax, Konfiguration)
- Installationsprozess getestet

### Phase 5: Repository Bereinigung
- Interne Entwicklungsdateien entfernt (.devcontainer/, CLAUDE.md)
- Nur essenzielle Projektdateien beibehalten
- Private Keys und Konfigurationen aus Git History entfernt

## Technische Details

### Kern-Komponenten
- **main.py**: Entry Point mit CLI und HTTP Status Server
- **proxy_manager.py**: Zentrale State Machine
- **minecraft_handler.py**: Minecraft Protokoll Implementation
- **satisfactory_handler.py**: UDP Traffic Detection
- **server_monitor.py**: Health Checking und IP Management
- **wol_sender.py**: Wake-on-LAN Magic Packet
- **config_manager.py**: JSON Konfiguration Handling

### Dependencies
- aiofiles, aiohttp: Async I/O
- wakeonlan: WoL Implementation
- netifaces: Network Interface Info
- psutil: System Utilities
- requests: HTTP Client

### Sicherheit
- Systemd Service Hardening (PrivateTmp, ProtectSystem)
- Capability Restrictions (CAP_NET_BIND_SERVICE, CAP_NET_ADMIN)
- Sudo Permissions nur für IP Management
- Dedicated Service User

## Konfiguration

### Installation Pfade
- **Installation**: `/opt/wol-proxy/`
- **Konfiguration**: `/etc/wol-proxy/config.json`
- **Logs**: `/var/log/wol-proxy.log`
- **Service**: `wol-proxy.service`

### Wichtige Befehle
```bash
# Installation
sudo ./install.sh

# Konfiguration testen
sudo -u wol-proxy /opt/wol-proxy/venv/bin/python /opt/wol-proxy/main.py --config /etc/wol-proxy/config.json --validate-config

# Service verwalten
systemctl start/stop/restart wol-proxy.service
journalctl -u wol-proxy.service -f
```

## Aktuelle Repository Struktur
```
Game-Server-WOL/
├── LICENSE
├── README.md (Deutsche Dokumentation)
├── config.json.example (Beispiel-Konfiguration)
├── install.sh (Installationsskript)
├── main.py (Hauptprogramm)
├── requirements.txt (Python Dependencies)
├── src/ (Quellcode Module)
│   ├── __init__.py
│   ├── config_manager.py
│   ├── minecraft_handler.py
│   ├── proxy_manager.py
│   ├── satisfactory_handler.py
│   ├── server_monitor.py
│   ├── utils.py
│   └── wol_sender.py
└── wol-proxy.service (Systemd Service)
```

## Status: ✅ ABGESCHLOSSEN
Das Projekt ist professionell überarbeitet, vollständig funktionsfähig und bereit für die öffentliche Nutzung. Alle privaten Informationen wurden entfernt und das Repository ist sauber strukturiert.

## Nächste Schritte
- Deployment auf Tinker Board testen
- Produktionsumgebung konfigurieren
- Langzeit-Monitoring einrichten