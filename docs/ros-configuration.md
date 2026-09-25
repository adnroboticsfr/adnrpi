# Configuration ROS

Les images ROS d'ADNRPi incluent `adnrpi-ros-config`, un outil en ligne de commande pour configurer l'environnement ROS à tout moment.

## Images disponibles

| Image | ROS | Base |
|-------|-----|------|
| `*-jammy-ubuntu22.04-ros2-server` | ROS2 Humble | Ubuntu 22.04 |
| `*-jammy-ubuntu22.04-ros1-server` | ROS1 Noetic | Ubuntu 22.04 |

## Configuration au premier démarrage

Édite `adnrpi-config.txt` sur la partition SD avant de démarrer :

```ini
APPLY_CONFIG=1

# Commun
ROS_ROBOT_NAME=mon_robot
ROS_WORKSPACE=/home/pi/ros_ws

# ROS1 Noetic
ROS_MASTER_URI=http://192.168.1.10:11311
ROS_HOSTNAME=192.168.1.50

# ROS2 Humble
ROS_DOMAIN_ID=42
ROS_RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

## adnrpi-ros-config

### Voir la configuration actuelle

```bash
adnrpi-ros-config show
```

```
=== ADNRPi ROS Configuration ===
  ROS2 Humble : installed
  Config file : /etc/ros/adnrpi-ros.conf

  ROS_DOMAIN_ID              = 42
  ROS_RMW_IMPLEMENTATION     = rmw_cyclonedds_cpp
  ROS_ROBOT_NAME             = mon_robot
```

### Assistant interactif

```bash
sudo adnrpi-ros-config
# ou
sudo adnrpi-ros-config interactive
```

Guide pas-à-pas pour configurer tous les paramètres.

### Modifier un paramètre directement

```bash
sudo adnrpi-ros-config set ROS_MASTER_URI http://192.168.1.10:11311
sudo adnrpi-ros-config set ROS_DOMAIN_ID 42
sudo adnrpi-ros-config set ROS_ROBOT_NAME mon_robot
sudo adnrpi-ros-config set ROS_WORKSPACE /home/pi/ros_ws
```

### Supprimer un paramètre

```bash
sudo adnrpi-ros-config unset ROS_MASTER_URI
```

### Tester la connectivité

```bash
adnrpi-ros-config test
```

```
=== ROS connectivity test ===
  ROS2 nodes (domain 42): OK — /mon_noeud /autre_noeud
```

### Appliquer manuellement

Si tu modifies `/etc/ros/adnrpi-ros.conf` à la main :

```bash
sudo adnrpi-ros-config apply
source /etc/bash.bashrc
```

## Paramètres disponibles

| Paramètre | ROS | Description |
|-----------|-----|-------------|
| `ROS_ROBOT_NAME` | ROS1+2 | Nom du robot, namespace, hostname |
| `ROS_WORKSPACE` | ROS1+2 | Workspace à sourcer automatiquement |
| `ROS_MASTER_URI` | ROS1 | URI du master ROS1 |
| `ROS_HOSTNAME` | ROS1 | Hostname annoncé sur le réseau ROS |
| `ROS_IP` | ROS1 | IP annoncée (alternative à hostname) |
| `ROS_DOMAIN_ID` | ROS2 | Isolation réseau (0-232, défaut: 0) |
| `ROS_RMW_IMPLEMENTATION` | ROS2 | Middleware DDS |

## Fichiers

| Fichier | Description |
|---------|-------------|
| `/etc/ros/adnrpi-ros.conf` | Config persistée (key=value) |
| `/etc/bash.bashrc` | Block ROS auto-généré (ne pas éditer à la main) |
| `/var/log/adnrpi-firstboot.log` | Log du premier démarrage |

## Packages installés

### ROS2 Humble
- `ros-humble-ros-base` — middleware complet
- `ros-humble-tf2`, `tf2-ros`, `tf2-tools`
- `ros-humble-nav-msgs`, `geometry-msgs`, `sensor-msgs`
- `ros-humble-image-transport`, `compressed-image-transport`
- `ros-humble-rosbridge-suite` — WebSocket bridge
- `ros-humble-teleop-twist-joy`, `teleop-twist-keyboard`
- `ros-humble-serial-driver`
- `ros-humble-robot-state-publisher`, `joint-state-publisher`, `xacro`
- `python3-colcon-common-extensions`, `python3-rosdep`

### ROS1 Noetic
- `ros-noetic-ros-base` — middleware complet
- `ros-noetic-tf`, `tf2`, `tf2-ros`, `tf2-tools`
- `ros-noetic-nav-msgs`, `geometry-msgs`, `sensor-msgs`
- `ros-noetic-image-transport`, `compressed-image-transport`
- `ros-noetic-rosserial`, `rosserial-arduino`
- `ros-noetic-rosbridge-suite`
- `ros-noetic-map-server`, `move-base-msgs`
- `ros-noetic-teleop-twist-joy`, `teleop-twist-keyboard`
- `ros-noetic-robot-state-publisher`, `joint-state-publisher`, `xacro`
- `python3-rosdep`, `python3-rosinstall`
