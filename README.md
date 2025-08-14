# 🎮 Wake-on-LAN Game Server Proxy

> **Sparen Sie Energie! Lassen Sie Ihren Game Server nur dann laufen, wenn wirklich gespielt wird.**

Ein robuster Python-Service, der als transparenter Proxy für Game Server fungiert und Ihren Hauptserver automatisch per Wake-on-LAN aufweckt, wenn Spieler beitreten möchten. Speziell für stromsparende ARM-Boards entwickelt.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ARM Compatible](https://img.shields.io/badge/ARM-Compatible-green.svg)](https://www.arm.com/)

## 🎯 Unterstützte Spiele

- **Minecraft (Java Edition)** - Vollständige Protokollunterstützung mit benutzerdefinierten Server-Status
- **Satisfactory** - UDP-Traffic-Erkennung auf Game-Ports (7777, 15000, 15777)

## ⚡ So funktioniert es

```
🔴 Server PC: AUS (0W Stromverbrauch)
🟢 ARM Board: Proxy aktiv (5W)

Spieler verbindet → 💤 WoL Magic Packet → 🚀 Server startet automatisch
```

### Zustandsmaschine
1. **OFFLINE** - Proxy übernimmt Server-IP, zeigt "Join to start server"
2. **WAKING** - WoL-Paket gesendet, kurzer Übergangszustand
3. **STARTING** - Server bootet, zeigt "Server starting" Nachrichten  
4. **PROXYING** - Server online, transparente Verkehrsweiterleitung
5. **MONITORING** - Überwacht Server-Gesundheit, bereit für Rückkehr in Proxy-Modus

## 📋 Voraussetzungen

### Hardware
- ARM Board (Raspberry Pi 3+, ASUS Tinker Board, etc.)
- Mindestens 512MB RAM, 1GB Speicher
- Ethernet-Verbindung (WiFi nicht empfohlen)

### Software
- Debian-basiertes OS (Raspberry Pi OS, Armbian, Ubuntu)
- Python 3.9+
- Systemd für Service-Management

### Netzwerk-Setup
- Statische IP-Adresse für Ihren Server PC
- Wake-on-LAN aktiviert auf Server PC
- Port-Weiterleitung für Game-Ports (bei Remote-Zugriff)

## 🚀 Installation

### Automatische Installation

```bash
# Repository klonen
git clone https://github.com/MaxxisHub/Game-Server-WOL.git
cd Game-Server-WOL

# Installation ausführen
chmod +x install.sh
sudo ./install.sh
```

## ⚙️ Konfiguration

### Schritt 1: MAC-Adresse des Servers herausfinden

```bash
# Auf Windows Server (als Administrator):
ipconfig /all

# Auf Linux Server:
ip addr show eth0

# Von anderem Gerät aus:
ping YOUR_SERVER_IP
arp -a | grep YOUR_SERVER_IP
```

### Schritt 2: Konfiguration bearbeiten

```bash
# Nach der Installation:
sudo nano /etc/wol-proxy/config.json
```

**Beispiel-Konfiguration:**
```json
{
  "server": {
    "target_ip": "192.168.1.100",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "network_interface": "eth0",
    "network_mask": 24,
    "additional_check_ports": [22]
  },
  "timing": {
    "boot_wait_seconds": 90,
    "health_check_interval": 15,
    "wol_retry_interval": 5,
    "connection_timeout": 30,
    "server_check_timeout": 5
  },
  "minecraft": {
    "enabled": true,
    "port": 25565,
    "motd_offline": "§aJoin to start server",
    "motd_starting": "§eServer is starting, please wait",
    "kick_message": "§eServer is starting up, try joining again in a minute."
  },
  "satisfactory": {
    "enabled": true,
    "game_port": 7777,
    "query_port": 15000,
    "beacon_port": 15777
  }
}
```

### Schritt 3: Konfiguration validieren

```bash
sudo -u wol-proxy /opt/wol-proxy/venv/bin/python /opt/wol-proxy/main.py --config /etc/wol-proxy/config.json --validate-config
```

## 🎯 Server PC Setup

### BIOS/UEFI Einstellungen
- Boot in BIOS-Einstellungen
- Suchen Sie nach "Wake on LAN", "WoL" oder "Power Management"
- Aktivieren Sie die entsprechenden Optionen

### Windows Setup
```powershell
# PowerShell als Administrator ausführen
Get-NetAdapter | Set-NetAdapterPowerManagement -WakeOnMagicPacket Enabled

# Einstellungen überprüfen
Get-NetAdapterPowerManagement
```

### Linux Setup
```bash
# WoL auf Netzwerk-Interface aktivieren
sudo ethtool -s eth0 wol g

# Einstellungen überprüfen  
sudo ethtool eth0 | grep "Wake-on"
```

## 🔧 Service-Verwaltung

```bash
# Service starten und aktivieren
sudo systemctl enable --now wol-proxy.service

# Status prüfen
sudo systemctl status wol-proxy.service

# Logs anzeigen
journalctl -u wol-proxy.service -f

# Service neu starten
sudo systemctl restart wol-proxy.service

# Konfiguration neu laden
sudo systemctl reload wol-proxy.service
```

## 📊 Überwachung

### HTTP Status-Endpoint
```bash
# Vollständigen Status abrufen
curl http://localhost:8080/status

# Nur Health-Check
curl http://localhost:8080/health
```

### Log-Analyse
```bash
# Live-Logs verfolgen
tail -f /var/log/wol-proxy.log

# Nach bestimmten Ereignissen suchen
grep "Wake-on-LAN" /var/log/wol-proxy.log
grep "State transition" /var/log/wol-proxy.log
```

## 🔍 Fehlerbehandlung

### Server wacht nicht auf
```bash
# WoL-Paket manuell testen
wakeonlan AA:BB:CC:DD:EE:FF

# Netzwerk-Konnektivität prüfen
ping 192.168.1.100

# MAC-Adresse überprüfen
arp -a | grep 192.168.1.100
```

### IP-Binding-Fehler
```bash
# Aktuelle IP-Bindungen prüfen
ip addr show

# IP-Management-Berechtigungen testen
# (Ersetzen Sie /24 mit Ihrer network_mask aus der Konfiguration)
sudo ip addr add 192.168.1.100/24 dev eth0
sudo ip addr del 192.168.1.100/24 dev eth0
```

### Service-Probleme
```bash
# Service-Logs prüfen
journalctl -u wol-proxy.service -n 50

# Konfiguration validieren
/opt/wol-proxy/venv/bin/python /opt/wol-proxy/main.py --validate-config

# Berechtigungen prüfen
sudo cat /etc/sudoers.d/wol-proxy
groups wol-proxy
```

## 🎮 Game-spezifisches Verhalten

### Minecraft
- **Server-Liste**: Zeigt benutzerdefinierten MOTD basierend auf Server-Status
  - Offline: "🟢 Join to start server"
  - Starting: "🟡 Server is starting, please wait"
- **Join-Versuche**: Erkennt echte Login-Versuche vs. Status-Pings
- **Protokoll-Unterstützung**: Kompatibel mit modernen Minecraft-Versionen

### Satisfactory
- **Einschränkungen**: Kann aufgrund der Protokoll-Komplexität nicht als "online" im Server-Browser erscheinen
- **Wake-Trigger**: Jeder UDP-Traffic auf Game-Ports löst Server-Wake aus
- **Verbindungsmethode**: Spieler sollten sich über direkte IP verbinden
- **Port-Weiterleitung**: Stellen Sie sicher, dass alle drei UDP-Ports weitergeleitet werden

## 📈 Performance

### Ressourcenverbrauch (Typisches ARM Board)
- **Arbeitsspeicher**: 25-45MB RAM
- **CPU**: <1% durchschnittliche Nutzung  
- **Netzwerk**: Minimaler Bandbreitenverbrauch
- **Speicher**: <100MB Installation

### Skalierbarkeit
- **Gleichzeitige Verbindungen**: 100+ simultane Spieler unterstützt
- **Antwortzeit**: <10ms für Status-Anfragen
- **Wake-Zeit**: 60-90 Sekunden typische Server-Boot-Zeit

## 🤝 Beitragen

Beiträge sind willkommen! Bitte verwenden Sie:
- **Issues**: Fehlerberichte und Feature-Anfragen
- **Pull Requests**: Code-Verbesserungen und neue Features
- **Dokumentation**: Hilfe bei der Verbesserung der Setup-Anleitungen

## 📝 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe die [LICENSE](LICENSE) Datei für Details.

## 🙏 Danksagungen

- Minecraft-Protokolldokumentation von [wiki.vg](https://wiki.vg/Protocol)
- Wake-on-LAN-Implementierung basierend auf standardmäßigem Magic-Packet-Format
- Systemd-Service-Härtungs-Best-Practices

---

**Happy Gaming! 🎮**

*Lassen Sie Ihren Server schlafen, bis Spieler wirklich spielen möchten!*
