# SmartPi H3 — Projets adaptés à la puissance disponible

Allwinner H3 · 4× Cortex-A7 @ 1.2GHz · 1GB RAM · USB 2.0 · Ethernet 100Mbps  
Armbian Bookworm · GPIO 40 pins · I2C, SPI, UART · Mali-400 (GPU non utile en headless)

**Principe :** le H3 est un CPU ARM lent mais sobre (~2W). Il excelle dans tout ce qui est
*attente réseau, I/O capteurs, services légers en permanence*. Il souffre dès qu'on lui demande
du calcul intensif ou du multimédia.

---

## Ce que le H3 fait très bien (sans souffrir)

### Réseau & services

| Projet | Charge H3 | Notes |
| --- | --- | --- |
| **Serveur Git local (Gitea)** | Faible | Déjà installé — push/pull/web UI fluide |
| **Reverse proxy nginx** | Très faible | Des milliers de req/s statiques |
| **DNS local + bloqueur pub (Pi-hole)** | Très faible | Toutes les requêtes DNS du réseau local |
| **DHCP + DNS (dnsmasq)** | Très faible | Remplace la box pour plus de contrôle |
| **VPN WireGuard** | Faible | Accès sécurisé au réseau local depuis l'extérieur |
| **MQTT broker (Mosquitto)** | Très faible | Hub central pour objets connectés |
| **Serveur web statique** | Très faible | Portfolio, docs, sites simples |
| **API REST Python/Flask** | Faible | Petites APIs, pas de calcul lourd |
| **Serveur NTP** | Quasi nul | Horloge réseau local |
| **Monitoring réseau (Uptime Kuma)** | Faible | Surveillance de services, alertes |

---

### Stockage & fichiers

| Projet | Charge H3 | Notes |
| --- | --- | --- |
| **NAS Samba** | Faible | Partage fichiers Windows/Linux, limité à ~35MB/s USB 2.0 |
| **Serveur FTP/SFTP** | Faible | Transferts de fichiers |
| **Sauvegarde réseau (rsync)** | Moyenne (pendant transfert) | Backup automatique des PCs du réseau |
| **Syncthing** | Faible | Synchronisation dossiers entre machines |
| **Gestionnaire fichiers web (FileBrowser)** | Très faible | Déjà installé |

---

### Domotique & IoT

| Projet | Charge H3 | Notes |
| --- | --- | --- |
| **Station météo** | Très faible | BMP280/BME680 via I2C → web dashboard |
| **Centrale domotique (Home Assistant)** | Moyenne | HA Core (sans add-ons lourds) — fonctionne, un peu lent au démarrage |
| **Node-RED** | Faible | Automatisation visuelle (flux, scénarios, capteurs) |
| **Collecteur de données capteurs** | Très faible | UART/I2C → InfluxDB → Grafana |
| **Gateway Zigbee/Z-Wave** | Faible | Avec dongle USB (Sonoff Zigbee 3.0, etc.) |
| **Contrôle robots via GPIO** | Faible | PWM, I2C moteurs, UART comm série |
| **Oscilloscope/multimètre** | Faible | Déjà fait — ADS1115, INA219, microphone |

---

### Audio & reconnaissance vocale

| Projet | Charge H3 | Notes |
| --- | --- | --- |
| **Wake word (PocketSphinx)** | Très faible | Écoute permanente d'un mot clé, ~10MB RAM |
| **Commandes vocales locales (Vosk small)** | Faible | FR/EN, temps réel, offline, ~40MB RAM |
| **Assistant vocal hybride** | Faible en veille | PocketSphinx → Vosk → ChatGPT API (voir fiche dédiée) |
| **Transcription batch (whisper.cpp tiny)** | Moyenne | ~4x temps réel, pas temps réel mais précis |
| **Radio internet / lecture audio** | Très faible | MPD + sortie jack SmartPi |

---

### Développement & outils

| Projet | Charge H3 | Notes |
| --- | --- | --- |
| **Serveur CI simple (Gitea Actions)** | Moyenne | Build Python/scripts shell, pas de gros projets C++ |
| **Registre Docker privé** | Faible | Stocker ses images Docker (pas les exécuter sur H3) |
| **Serveur de packages pip/apt local** | Faible | Cache de packages pour les machines du réseau |
| **Jupyter Notebook léger** | Moyenne | Python, pandas sur petits datasets — utilisable |
| **Serveur code (code-server = VSCode web)** | Moyenne-haute | Lent mais utilisable pour édition légère |

---

### Audio & impression

| Projet | Charge H3 | Notes |
| --- | --- | --- |
| **Serveur d'impression (CUPS)** | Très faible | Partage imprimante réseau |
| **Lecteur audio réseau (MPD)** | Très faible | Musique depuis USB/NAS via réseau |
| **Radio internet** | Très faible | Stream MP3/AAC, sortie jack 3.5mm intégrée |

---

### Sécurité & réseau avancé

| Projet | Charge H3 | Notes |
| --- | --- | --- |
| **Honeypot (Cowrie SSH)** | Faible | Piège les scans SSH, log les attaquants |
| **Analyseur trafic (ntopng lite)** | Moyenne | Stats réseau en temps réel |
| **Proxy filtrant (Squid)** | Moyenne | Cache + filtrage web du réseau local |
| **Passerelle série ↔ réseau** | Très faible | UART/RS485 → TCP (utile pour équipements industriels) |

---

## Ce qui marche mais souffre (à éviter ou adapter)

| Projet | Problème | Alternative |
| --- | --- | --- |
| **Jellyfin / Plex** | Transcodage vidéo impossible (pas de VPU utilisable) | Direct play seulement (le client décode) |
| **Home Assistant complet** | Add-ons lourds (Frigate, ML) saturent la RAM | HA Core sans add-ons lourds |
| **Base de données lourde** | PostgreSQL avec millions de lignes → lent | SQLite ou MariaDB sur petits volumes |
| **Docker avec conteneurs lourds** | RAM insuffisante, swapping | 1-2 conteneurs légers max |
| **Build C++/Rust** | Très lent (des heures) | Cross-compiler depuis PC, déployer le binaire |
| **Tor relay** | Chiffrement AES sans accélération = CPU saturé | Non recommandé |
| **Machine learning** | Impossible en temps réel | Inférence ONNX très légère possible |

---

## Ce qu'on ne peut pas faire

| Projet | Pourquoi |
| --- | --- |
| Transcodage vidéo H.264/H.265 | Pas de VPU accessible sous Linux |
| Inférence ML temps réel | Pas de NPU, CPU trop lent |
| NAS haute vitesse | USB 2.0 limité à ~35MB/s, pas de SATA |
| Nombreux utilisateurs simultanés | 1GB RAM sature vite |
| Jeux / émulation > SNES | GPU Mali inutilisable en headless |

---

## Optimisations recommandées avant tout projet

```bash
# 1. zRAM — "rajoute" ~400MB de RAM utilisable par compression
apt install zram-tools
echo -e "ALGO=zstd\nPERCENT=50" >> /etc/default/zramswap
systemctl restart zramswap

# 2. Gouverneur CPU performant (réactif aux pics de charge)
echo schedutil > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# Rendre permanent dans /etc/rc.local

# 3. Rootfs sur USB (I/O 2-3x plus rapide que SD)
nand-sata-install   # voir docs/nas-server.md
```

---

## Matériel utile à avoir avec le H3

| Composant | Usage | Prix |
| --- | --- | --- |
| Dissipateur + pâte thermique | Overclocking stable, moins de throttling | ~2€ |
| Disque USB SSD 2.5" | Rootfs + NAS — 10x plus fiable que SD | ~25€ |
| Dongle Zigbee USB (Sonoff) | Gateway domotique | ~12€ |
| ADS1115 (I2C) | ADC 16-bit pour capteurs | ~2€ |
| BMP280 (I2C) | Pression / température / humidité | ~2€ |
| INA219 (I2C) | Mesure courant/tension | ~2€ |
| Relais 5V (GPIO) | Contrôle d'appareils | ~1€ |
| Pi Pico (USB) | ADC rapide, générateur PWM | ~5€ |

---

## Projets déjà réalisés sur ce SmartPi

| Projet | État | Doc |
| --- | --- | --- |
| Oscilloscope / multimètre Kivy | ✓ Fonctionnel | `docs/scope-project.md` |
| Serveur Git local (Gitea v28) | ✓ Installé | `docs/nas-server.md` |
| Hub web + FileBrowser + Cockpit | ✓ Installé | `docs/nas-server.md` |
| Interface web unifiée | ⬜ Backlog V2 | `docs/nas-server.md` |
| Migration rootfs USB | ⬜ À faire | `docs/nas-server.md` |
