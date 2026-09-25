# Démarrage rapide

## 1. Télécharger une image

Va sur [Releases](https://github.com/adnroboticsfr/adnrpi/releases) et télécharge l'image qui correspond à ton usage :

| Image | Usage |
|-------|-------|
| `ADNRPi-adnrpi1-trixie-debian13-server` | Serveur léger, usage général |
| `ADNRPi-adnrpi1-noble-ubuntu24.04-server` | Ubuntu LTS serveur |
| `ADNRPi-adnrpi1-trixie-debian13-desktop_XFCE` | Bureau XFCE |
| `ADNRPi-adnrpi1-jammy-ubuntu22.04-ros2-server` | **ROS2 Humble** |
| `ADNRPi-adnrpi1-jammy-ubuntu22.04-ros1-server` | **ROS1 Noetic** |

## 2. Flasher la carte SD

**Avec Balena Etcher (recommandé) :**
1. Télécharge [Balena Etcher](https://etcher.balena.io)
2. Sélectionne le fichier `.img.xz`
3. Sélectionne ta carte SD
4. Flash

**Avec dd (Linux/macOS) :**
```bash
xz -dc ADNRPi-adnrpi1-trixie-debian13-server-*.img.xz | sudo dd of=/dev/sdX bs=4M status=progress
sync
```

## 3. Configurer avant le premier démarrage (optionnel)

Avant d'insérer la carte, ouvre la partition FAT (`/boot`) et édite `adnrpi-config.txt` :

```ini
APPLY_CONFIG=1
HOSTNAME=mon-robot
WIFI_SSID=MonReseau
WIFI_PASSWORD=monmotdepasse
WIFI_COUNTRY=FR
SSH_ENABLED=1
TIMEZONE=Europe/Paris
```

Pour les images ROS, ajoute également les paramètres ROS — voir [Configuration ROS](ros-configuration.md).

## 4. Premier démarrage

1. Insère la carte SD dans l'ADNRPi One
2. Branche l'alimentation
3. Le logo ADN Robotics s'affiche immédiatement (U-Boot)
4. Le système démarre, la configuration est appliquée automatiquement

**Connexion SSH (réseau) :**
```bash
ssh root@<ip-du-board>
```

**Connexion SSH via USB OTG** (voir [SSH via USB](ssh-usb.md)) :
```bash
ssh root@172.22.1.1
```

## 5. Mot de passe par défaut

| Utilisateur | Mot de passe |
|-------------|--------------|
| `root` | `1234` (à changer au premier login) |
