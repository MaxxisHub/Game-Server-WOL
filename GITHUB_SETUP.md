# 🌐 GitHub Setup - Quick Guide

## Schritt 1: Repository auf GitHub erstellen

1. Gehe zu [github.com](https://github.com) → Login
2. Klicke "New Repository" (grüner Button)
3. **Repository Name**: `wol-game-proxy`
4. **Description**: `Wake-on-LAN Game Server Proxy for Minecraft & Satisfactory`
5. ✅ Public
6. ❌ **NICHT** "Initialize with README" ankreuzen
7. "Create repository"

## Schritt 2: Code hochladen

### Terminal/PowerShell öffnen:
```bash
# In /workspace Verzeichnis wechseln
cd /workspace

# Git initialisieren
git init

# Alle Dateien hinzufügen
git add .

# Commit erstellen
git commit -m "Initial commit: WoL Game Server Proxy v1.0"

# GitHub Repository verknüpfen (DEINE URL verwenden!)
git remote add origin https://github.com/DEIN-USERNAME/wol-game-proxy.git

# Code hochladen
git push -u origin main
```

### Falls Git nicht installiert ist:
```bash
# Windows:
winget install Git.Git
# Oder von https://git-scm.com herunterladen

# Nach Installation PowerShell neu öffnen
```

## Schritt 3: Auf Tinker Board installieren

### SSH zum Tinker Board:
```bash
ssh root@192.168.1.179
```

### Repository klonen:
```bash
# Auf dem Tinker Board:
cd /root
git clone https://github.com/DEIN-USERNAME/wol-game-proxy.git
cd wol-game-proxy

# Installation
chmod +x install.sh
./install.sh
```

### Konfiguration:
```bash
# Config bearbeiten
nano /etc/wol-proxy/config.json

# Deine Werte:
# "target_ip": "192.168.1.165"
# "mac_address": "84:47:09:33:81:80"

# Service starten
systemctl start wol-proxy.service
systemctl enable wol-proxy.service
```

## 🎯 Das war's!

- ✅ Code auf GitHub
- ✅ Einfache Installation auf Tinker Board
- ✅ Updates mit `git pull`
- ✅ Professionelles Setup

**Jetzt einfach diese Befehle ausführen und du hast ein sauberes GitHub-basiertes Deployment!**