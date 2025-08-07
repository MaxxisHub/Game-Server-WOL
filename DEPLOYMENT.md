# 🚀 Wake-on-LAN Game Server Proxy - Deployment Guide

Komplette Anleitung für die Installation auf ARM-basierten Systemen (Tinker Board, Raspberry Pi, etc.)

## 📋 Übersicht

Dieses Projekt implementiert einen Wake-on-LAN Proxy für Game Server:
- **Entwicklung**: Auf Gaming PC mit Claude Code
- **Deployment**: Auf ARM Board (Tinker Board/Raspberry Pi)
- **Ziel**: Server PC automatisch aufwecken bei Spielerverbindungen

---

## 🌐 GitHub Setup (Einmalig)

### Schritt 1: Repository auf GitHub erstellen

1. Gehe zu [github.com](https://github.com) und logge dich ein
2. Klicke auf "New Repository" (oder das + Symbol)
3. Repository Name: `wol-game-proxy`
4. Beschreibung: `Wake-on-LAN Game Server Proxy for Minecraft & Satisfactory`
5. ✅ Public (oder Private wenn gewünscht)
6. ❌ NICHT "Initialize with README" ankreuzen (wir haben schon eine)
7. Klicke "Create repository"

### Schritt 2: Code auf GitHub hochladen

```bash
# Im Gaming PC Terminal (PowerShell/CMD):
cd /workspace

# Git Repository initialisieren
git init

# Alle Dateien hinzufügen
git add .

# Ersten Commit erstellen
git commit -m "Initial commit: WoL Game Server Proxy v1.0"

# Remote Repository hinzufügen (DEINE GitHub URL verwenden!)
git remote add origin https://github.com/DEIN-USERNAME/wol-game-proxy.git

# Code hochladen
git push -u origin main
```

**Falls git nicht installiert ist:**
```bash
# Windows: Git für Windows herunterladen von git-scm.com
# Oder über chocolatey:
choco install git

# Oder über winget:
winget install Git.Git
```

---

## 🎯 Deployment auf Tinker Board

### Schritt 1: SSH-Verbindung zum Tinker Board

```bash
# Von Gaming PC aus:
ssh root@192.168.1.179
```

### Schritt 2: System vorbereiten

```bash
# Auf dem Tinker Board:
# System aktualisieren
apt update && apt upgrade -y

# Git installieren (falls nicht vorhanden)
apt install -y git

# Python und Dependencies installieren
apt install -y python3 python3-pip python3-venv curl iputils-arping iproute2 sudo
```

### Schritt 3: Repository klonen

```bash
# Auf dem Tinker Board:
cd /root
git clone https://github.com/DEIN-USERNAME/wol-game-proxy.git
cd wol-game-proxy
```

### Schritt 4: Installation ausführen

```bash
# Auf dem Tinker Board:
chmod +x install.sh
./install.sh
```

**Der Installer macht automatisch:**
- ✅ Erstellt Service-User `wol-proxy`
- ✅ Installiert Python Dependencies
- ✅ Konfiguriert Sudo-Permissions für IP Management
- ✅ Erstellt Systemd Service
- ✅ Konfiguriert Logging

### Schritt 5: Konfiguration anpassen

```bash
# Auf dem Tinker Board:
nano /etc/wol-proxy/config.json
```

**Beispiel-Konfiguration:**
```json
{
  "server": {
    "target_ip": "192.168.1.100",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "network_interface": "eth0"
  },
  "timing": {
    "boot_wait_seconds": 90,
    "health_check_interval": 15,
    "wol_retry_interval": 5,
    "connection_timeout": 30
  },
  "minecraft": {
    "enabled": true,
    "port": 25565,
    "motd_offline": "§a🎮 Join to start server",
    "motd_starting": "§e⏳ Server is starting, please wait",
    "kick_message": "§eServer is starting up, try joining again in a minute."
  },
  "satisfactory": {
    "enabled": true,
    "game_port": 7777,
    "query_port": 15000,
    "beacon_port": 15777
  },
  "logging": {
    "level": "INFO",
    "file": "/var/log/wol-proxy.log",
    "console_output": true
  },
  "monitoring": {
    "health_check_enabled": true,
    "status_endpoint_port": 8080
  }
}
```

### Schritt 6: Service starten

```bash
# Auf dem Tinker Board:
# Konfiguration validieren
sudo -u wol-proxy /opt/wol-proxy/venv/bin/python /opt/wol-proxy/main.py \\
  --config /etc/wol-proxy/config.json --validate-config

# Service starten
systemctl start wol-proxy.service
systemctl enable wol-proxy.service

# Status prüfen
systemctl status wol-proxy.service
```

---

## 🧪 Testing & Verification

### Schritt 1: Service Status prüfen

```bash
# Auf dem Tinker Board:
systemctl status wol-proxy.service
journalctl -u wol-proxy.service -n 20
```

### Schritt 2: HTTP Status Endpoint testen

```bash
# Auf dem Tinker Board:
curl http://localhost:8080/status

# Von anderem Gerät:
curl http://192.168.1.179:8080/status
```

### Schritt 3: WoL manuell testen

```bash
# Auf dem Tinker Board:
# Server PC ausschalten
# Dann WoL testen:
wakeonlan 84:47:09:33:81:80
```

### Schritt 4: Game Server Funktionalität testen

**Minecraft Test:**
1. Server PC (192.168.1.165) ausschalten
2. Minecraft Client: Server `192.168.1.165:25565` hinzufügen
3. Sollte "🎮 Join to start server" zeigen
4. Bei Join-Versuch: Server sollte aufwachen

**Satisfactory Test:**
1. Server PC ausschalten  
2. Satisfactory: Direct IP `192.168.1.165:7777`
3. Verbindungsversuch sollte Server aufwecken

---

## 📊 Monitoring & Logs

### Live Logs anschauen

```bash
# Systemd Logs
journalctl -u wol-proxy.service -f

# Application Logs
tail -f /var/log/wol-proxy.log

# Beide gleichzeitig
journalctl -u wol-proxy.service -f & tail -f /var/log/wol-proxy.log
```

### Status Dashboard

```bash
# Status über HTTP API
curl -s http://192.168.1.179:8080/status | python3 -m json.tool

# Oder einfacher:
curl http://192.168.1.179:8080/status
```

### Wichtige Log-Events

```bash
# Nach Wake-Attempts suchen
grep "Wake-on-LAN" /var/log/wol-proxy.log

# State Transitions
grep "State transition" /var/log/wol-proxy.log

# Connection Attempts
grep "connection" /var/log/wol-proxy.log
```

---

## 🔧 Updates & Wartung

### Code-Updates von GitHub

```bash
# Auf dem Tinker Board:
cd /root/wol-game-proxy
git pull origin main

# Service neu starten
systemctl restart wol-proxy.service
```

### Konfiguration ändern

```bash
# Config editieren
nano /etc/wol-proxy/config.json

# Service neu laden
systemctl reload wol-proxy.service
# Oder komplett neu starten:
systemctl restart wol-proxy.service
```

### Service Wartung

```bash
# Service stoppen
systemctl stop wol-proxy.service

# Service starten
systemctl start wol-proxy.service

# Status prüfen
systemctl status wol-proxy.service

# Service deaktivieren (nicht autostart)
systemctl disable wol-proxy.service
```

---

## 🐛 Troubleshooting

### Häufige Probleme

**1. Service startet nicht:**
```bash
# Permissions prüfen
ls -la /opt/wol-proxy/
sudo chown -R wol-proxy:wol-proxy /opt/wol-proxy/

# Konfiguration validieren
sudo -u wol-proxy /opt/wol-proxy/venv/bin/python /opt/wol-proxy/main.py \\
  --config /etc/wol-proxy/config.json --validate-config
```

**2. IP Binding schlägt fehl:**
```bash
# Sudo permissions prüfen
sudo -u wol-proxy sudo ip addr add 192.168.1.165/24 dev eth0
sudo -u wol-proxy sudo ip addr del 192.168.1.165/24 dev eth0

# Sudoers file prüfen
cat /etc/sudoers.d/wol-proxy
```

**3. WoL funktioniert nicht:**
```bash
# Network Interface prüfen
ip addr show eth0

# ARP Table prüfen
arp -a | grep 192.168.1.165

# Direkt testen
wakeonlan 84:47:09:33:81:80
```

**4. Ports sind blockiert:**
```bash
# Firewall prüfen (falls vorhanden)
ufw status

# Ports prüfen
netstat -tulpn | grep -E "(25565|7777|15000|15777|8080)"
```

### Log-Analyse

```bash
# Fehler-Logs
journalctl -u wol-proxy.service --since "1 hour ago" | grep -i error

# Warning-Logs  
journalctl -u wol-proxy.service --since "1 hour ago" | grep -i warn

# Letzte 50 Zeilen
journalctl -u wol-proxy.service -n 50
```

---

## 📈 Performance Monitoring

### Ressourcenverbrauch prüfen

```bash
# Memory Usage
ps aux | grep wol-proxy

# System Resources
top -p $(pgrep -f wol-proxy)

# Disk Usage
du -sh /opt/wol-proxy/
du -sh /var/log/wol-proxy.log
```

### Netzwerk Monitoring

```bash
# Offene Ports
ss -tulpn | grep -E "(25565|7777|15000|15777|8080)"

# Netzwerk Statistiken
netstat -i

# Verbindungen
netstat -an | grep -E "(25565|7777|15000|15777)"
```

---

## 🎯 Produktionssetup

### Für 24/7 Betrieb optimieren

```bash
# Log Rotation konfigurieren
cat > /etc/logrotate.d/wol-proxy << EOF
/var/log/wol-proxy.log {
    weekly
    rotate 4
    missingok
    notifempty
    compress
    delaycompress
    create 644 wol-proxy wol-proxy
    postrotate
        systemctl reload-or-restart wol-proxy.service > /dev/null 2>&1 || true
    endscript
}
EOF

# Automatische Updates (optional)
cat > /etc/cron.weekly/wol-proxy-update << EOF
#!/bin/bash
cd /root/wol-game-proxy
git pull origin main
systemctl restart wol-proxy.service
EOF
chmod +x /etc/cron.weekly/wol-proxy-update
```

### Monitoring Setup

```bash
# Einfaches Health Check Script
cat > /usr/local/bin/wol-proxy-health << EOF
#!/bin/bash
if ! curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "WoL Proxy unhealthy, restarting..."
    systemctl restart wol-proxy.service
fi
EOF
chmod +x /usr/local/bin/wol-proxy-health

# Cron Job für Health Check (alle 5 Minuten)
echo "*/5 * * * * /usr/local/bin/wol-proxy-health" | crontab -
```

---

## ✅ Quick Command Reference

```bash
# Service Management
systemctl start|stop|restart|reload wol-proxy.service
systemctl status wol-proxy.service
systemctl enable|disable wol-proxy.service

# Logs
journalctl -u wol-proxy.service -f
tail -f /var/log/wol-proxy.log

# Configuration
nano /etc/wol-proxy/config.json
/opt/wol-proxy/venv/bin/python /opt/wol-proxy/main.py --validate-config

# Status Check
curl http://localhost:8080/status
curl http://localhost:8080/health

# Manual WoL
wakeonlan 84:47:09:33:81:80

# Updates
cd /root/wol-game-proxy && git pull origin main && systemctl restart wol-proxy.service
```

---

**🎮 Viel Erfolg beim Gaming! Dein Server wacht nur noch auf, wenn wirklich gespielt wird! 🎯**