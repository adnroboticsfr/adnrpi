# Premier démarrage — adnrpi-config.txt

Le fichier `adnrpi-config.txt` se trouve sur la partition FAT de la carte SD. Il est lisible et éditable depuis Windows, macOS et Linux **avant** d'insérer la carte dans la carte.

## Activer la configuration

Par défaut `APPLY_CONFIG=0` — rien n'est appliqué. Pour activer :

```ini
APPLY_CONFIG=1
```

## Options disponibles

### Réseau
```ini
HOSTNAME=mon-robot          # nom de la machine sur le réseau

WIFI_SSID=MonReseau         # nom du réseau WiFi
WIFI_PASSWORD=motdepasse    # mot de passe
WIFI_COUNTRY=FR             # code pays (FR, US, DE...)

# IP statique (laisser vide pour DHCP)
STATIC_IP=192.168.1.50
NETMASK=255.255.255.0
GATEWAY=192.168.1.1
DNS=8.8.8.8
```

### Accès
```ini
SSH_ENABLED=1               # 1 = activé (défaut), 0 = désactivé

USERNAME=pi                 # créer un utilisateur
USER_PASSWORD=motdepasse

ROOT_PASSWORD=nouveaumotdepasse
```

### Système
```ini
TIMEZONE=Europe/Paris       # fuseau horaire
LOCALE=fr_FR.UTF-8          # langue
```

### ROS (images ROS uniquement)
```ini
ROS_ROBOT_NAME=mon_robot    # nom du robot (namespace + hostname)
ROS_WORKSPACE=/home/pi/ros_ws

# ROS1 Noetic
ROS_MASTER_URI=http://192.168.1.10:11311
ROS_HOSTNAME=192.168.1.50
ROS_IP=192.168.1.50

# ROS2 Humble
ROS_DOMAIN_ID=42
ROS_RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

Voir [Configuration ROS](ros-configuration.md) pour plus de détails.

## Après le premier démarrage

Le fichier est renommé en `adnrpi-config.txt.done` une fois appliqué. Pour relancer une configuration, renomme-le en `adnrpi-config.txt` et remets `APPLY_CONFIG=1`.

## Log

Le résultat de la configuration est visible dans :
```bash
cat /var/log/adnrpi-firstboot.log
```

## Compatibilité Raspberry Pi Imager

Le système est compatible avec les fichiers générés par Raspberry Pi Imager :
- `ssh` / `ssh.txt` → active SSH
- `wpa_supplicant.conf` → configure le WiFi
- `userconf.txt` → crée un utilisateur
- `user-data` → cloud-init
