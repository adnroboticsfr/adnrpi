# ADNRPi — Serveur local & NAS

Serveur web embarqué sur SmartPi One H3 (Armbian Bookworm).  
Accès réseau local uniquement — gestion à distance sans clavier/écran.

**Démarré :** 2026-09-30  
**Dernière mise à jour :** 2026-09-30  
**IP SmartPi :** 192.168.1.89  
**SSH :** `root@192.168.1.89` — clé `SHA256:E3BK5nqO95X4iBCW84rLjwZEBgb22IUTpmU/IfihrHY`

---

## Version 1 — installée (2026-09-30)

### Ce qui tourne

| Service | Port | Accès | État |
|---------|------|-------|------|
| nginx (hub) | 80 | `http://192.168.1.89/` | ✓ actif |
| Stats API (Python) | 8079 (local) | `/api/stats` via nginx | ✓ actif |
| Cockpit (admin système) | 9090 | `http://192.168.1.89:9090/` | ✓ actif |
| FileBrowser (fichiers) | 8081 (local) | `http://192.168.1.89/files/` | ✓ actif |
| Gitea (git local) | 3000 | `http://192.168.1.89:3000/` | ✓ actif (v28.0.0) |

### Page d'accueil hub

`http://192.168.1.89/` — page sombre ADN Robotics avec :
- 4 cartes de services cliquables
- Barre de stats live (CPU, temp, RAM, disque, uptime) toutes les 10s via `/api/stats`

### Scripts d'installation

```
scripts/server/
├── install_server.sh   — installe nginx, Cockpit, FileBrowser, stats_api
├── hub.html            — page d'accueil (copiée dans /var/www/adnrpi/)
└── stats_api.py        — mini API JSON (port 8079)

scripts/gitea/
├── install_gitea.sh    — télécharge Gitea ARM7, systemd, app.ini
└── select-storage.sh   — monte USB ou SD automatiquement au boot
```

### Fix Cockpit (note technique)

Cockpit ne supporte pas les sous-chemins nginx — `base href="/"` hardcodé dans son HTML.
Le proxy `/admin/` était cassé (assets JS/CSS 404).

**Fix appliqué :** lien direct `http://<ip>:9090/` généré dynamiquement dans hub.html via `location.hostname`.

---

## Problème identifié — trop d'interfaces

**Trop fragmenté :** Cockpit (9090) + FileBrowser (/files) + Gitea (3000) + hub (/), chacun avec ses propres identifiants, sa propre UI, ses propres conventions.

**Objectif V2 :** Une seule interface web unifiée pour tout contrôler.

---

## V2 — Interface unifiée (à coder)

### Principe

Une seule appli web maison sur le port 80, construite en HTML/JS pur (pas de framework), qui regroupe tout :

| Section | Ce qu'elle remplace |
|---------|-------------------|
| Tableau de bord (stats) | hub.html actuel + stats API |
| Terminal web | Cockpit (pour les commandes courantes) |
| Gestionnaire de fichiers | FileBrowser |
| Gestion Gitea | Cockpit + interface Gitea |
| Contrôle services | Cockpit |

### Architecture cible

```
nginx (port 80)
└── / → adnrpi_panel (appli Python légère, port 8080)
         ├── GET  /api/stats      → CPU, RAM, disque, temp, uptime
         ├── GET  /api/services   → état des services systemd
         ├── POST /api/service    → start/stop/restart un service
         ├── GET  /api/files?path=  → liste fichiers
         ├── GET  /api/file?path=   → télécharger un fichier
         ├── POST /api/file         → uploader un fichier
         ├── GET  /api/git/repos    → liste dépôts Gitea (via API Gitea)
         └── WS  /ws/terminal      → terminal web (pty)
```

Gitea reste installé (port 3000) mais on l'utilise via son API REST — pas besoin d'y accéder directement.  
Cockpit peut rester pour les cas avancés mais n'est plus le chemin principal.

### Backlog V2

| # | Tâche | Priorité |
|---|-------|----------|
| V2-1 | Tableau de bord unifié (stats + services) | Haute |
| V2-2 | Gestionnaire fichiers intégré (upload/download) | Haute |
| V2-3 | Terminal web (xterm.js + pty Python) | Moyenne |
| V2-4 | Vue dépôts Gitea (liste + clone URL) | Moyenne |
| V2-5 | Start/stop services depuis l'interface | Basse |
| V2-6 | Logs en direct (scope, gitea, système) | Basse |

---

## Backlog V1 restant

| # | Tâche | État |
|---|-------|------|
| N1 | Installer Gitea | ✓ v28.0.0 arm-6, tourne sur port 3000 |
| N2 | Créer compte admin Gitea (première visite navigateur) | ⬜ à faire — ouvrir `http://192.168.1.89:3000/` |
| N3 | Pousser les projets locaux vers Gitea | ⬜ après N2 |
| N4 | FileBrowser : changer mot de passe par défaut (admin/admin) | ⬜ à faire |

---

## Commandes utiles

```bash
# SSH
plink -ssh -pw pi -batch -hostkey "ssh-ed25519 255 SHA256:E3BK5nqO95X4iBCW84rLjwZEBgb22IUTpmU/IfihrHY" root@192.168.1.89 "commande"

# Statut services
systemctl status nginx cockpit.socket filebrowser adnrpi-stats gitea

# Logs
journalctl -u nginx -n 30
journalctl -u gitea -n 30

# Installer Gitea (depuis SmartPi)
bash /tmp/adnrpi-install/gitea/install_gitea.sh

# Redéployer hub.html
pscp -pw pi -batch -hostkey "..." scripts/server/hub.html root@192.168.1.89:/var/www/adnrpi/index.html
```

---

## Notes stockage NAS (SD vs USB)

Le script `select-storage.sh` s'exécute au boot :
- USB branché → Gitea stocke sur USB (`/mnt/gitea-usb`)
- Sinon → SD (`/opt/gitea/data-sd`)

Symlink `/opt/gitea/storage` → cible active (transparent pour Gitea).

Log sélection : `/opt/gitea/storage-select.log`

---

## Boot depuis USB/HDD — état des lieux

### Contrainte matérielle H3

Le H3 (Allwinner) n'a pas de BIOS/UEFI. U-Boot est gravé à un offset fixe sur la SD.  
**La SD est obligatoire pour démarrer** — impossible de s'en passer complètement.

### Ce qui est possible : rootfs sur USB

U-Boot démarre depuis la SD, puis charge le kernel, puis monte le rootfs… depuis USB/HDD.  
La SD ne contient plus que U-Boot + `/boot` (kernel, dtb) → **200MB suffisent**.  
Tout le reste (OS, `/opt`, données, Gitea) tourne depuis USB/HDD.

```text
SD card (mini, 4GB) : U-Boot + /boot
USB/HDD (500GB+)    : / (rootfs complet)
```

### Migration avec Armbian — ⬜ À FAIRE (disque USB requis)

**Réversible à tout moment** — U-Boot et le kernel sur la SD ne sont jamais touchés.  
Pour revenir en arrière : supprimer la ligne `rootdev=` dans `/boot/armbianEnv.txt` et redémarrer.  
Pire cas : re-flasher la SD (5 min), les données USB restent intactes.

#### Prérequis

- Un disque USB branché au SmartPi (HDD ou SSD — pas une clé USB, trop lente/fragile pour rootfs)
- Vérifier qu'il est détecté : `lsblk`

#### Procédure

```bash
# 1. Vérifier le disque USB
lsblk -o NAME,SIZE,TYPE,MODEL

# 2. Lancer la migration (interactif)
nand-sata-install
# → choisir "Boot from SD - system on USB/SATA"
# → sélectionner la partition USB cible
# → copie le rootfs (~2.7GB, prend 10-20 min selon vitesse USB)
# → modifie automatiquement /boot/armbianEnv.txt : rootdev=UUID=xxx
# → redémarre → SmartPi inaccessible ~2 min puis repart depuis USB

# 3. Vérifier après reboot
df -h /        # doit afficher /dev/sdaX (USB) et non mmcblk0p2 (SD)
cat /proc/cmdline | grep root
```

#### Pour revenir sur SD (retour arrière)

```bash
# Supprimer la ligne rootdev dans armbianEnv.txt et redémarrer
sed -i '/^rootdev=/d' /boot/armbianEnv.txt
reboot
# → repart depuis la SD comme avant, USB ignoré (données intactes)
```

### Comparatif

| Critère | SD seule (actuel) | SD boot + rootfs USB |
| --- | --- | --- |
| Stockage | 28 GB | 500 GB+ |
| Endurance écriture | Faible (SD s'use) | Élevée (HDD/SSD) |
| Vitesse I/O | ~20 MB/s | ~35 MB/s USB 2.0 |
| SD requise | Oui (tout) | Oui (U-Boot + /boot seulement) |
| SD si elle casse | OS perdu | OS intact sur USB, juste regraver U-Boot |
| Retour arrière | — | 1 ligne à supprimer + reboot |

### Backlog migration

| # | Tâche | Notes |
| --- | --- | --- |
| USB-1 | **Brancher un disque USB et lancer `nand-sata-install`** | Procédure documentée ci-dessus |
| USB-2 | Vérifier compatibilité USB branché au boot | Certains hubs USB posent problème |
| USB-3 | Script regraver U-Boot sur SD de remplacement | En cas de SD HS |
