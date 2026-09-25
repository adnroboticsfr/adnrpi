# ROS Configuration

ADNRPi ROS images include `adnrpi-ros-config`, a command-line tool to configure the ROS environment at any time — at first boot or later.

## Available images

| Image | ROS | Base OS |
|-------|-----|---------|
| `*-jammy-ubuntu22.04-ros2-server` | ROS2 Humble | Ubuntu 22.04 |
| `*-jammy-ubuntu22.04-ros1-server` | ROS1 Noetic | Ubuntu 22.04 |

## Configure at first boot

Edit `adnrpi-config.txt` on the SD card before booting:

```ini
APPLY_CONFIG=1

# Common
ROS_ROBOT_NAME=my_robot
ROS_WORKSPACE=/home/pi/ros_ws

# ROS1 Noetic
ROS_MASTER_URI=http://192.168.1.10:11311
ROS_HOSTNAME=192.168.1.50

# ROS2 Humble
ROS_DOMAIN_ID=42
ROS_RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

## adnrpi-ros-config

### Show current configuration

```bash
adnrpi-ros-config show
```

```text
=== ADNRPi ROS Configuration ===
  ROS2 Humble : installed
  Config file : /etc/ros/adnrpi-ros.conf

  ROS_DOMAIN_ID              = 42
  ROS_RMW_IMPLEMENTATION     = rmw_cyclonedds_cpp
  ROS_ROBOT_NAME             = my_robot
```

### Interactive setup wizard

```bash
sudo adnrpi-ros-config
# or explicitly
sudo adnrpi-ros-config interactive
```

Step-by-step guide to configure all parameters.

### Set a parameter directly

```bash
sudo adnrpi-ros-config set ROS_MASTER_URI http://192.168.1.10:11311
sudo adnrpi-ros-config set ROS_DOMAIN_ID 42
sudo adnrpi-ros-config set ROS_ROBOT_NAME my_robot
sudo adnrpi-ros-config set ROS_WORKSPACE /home/pi/ros_ws
```

### Remove a parameter

```bash
sudo adnrpi-ros-config unset ROS_MASTER_URI
```

### Test connectivity

```bash
adnrpi-ros-config test
```

```text
=== ROS connectivity test ===
  ROS2 nodes (domain 42): OK — /my_node /other_node
```

### Apply manually

If you edit `/etc/ros/adnrpi-ros.conf` by hand:

```bash
sudo adnrpi-ros-config apply
source /etc/bash.bashrc
```

## Parameters reference

| Parameter | ROS | Description |
|-----------|-----|-------------|
| `ROS_ROBOT_NAME` | ROS1+2 | Robot name, used as namespace and hostname |
| `ROS_WORKSPACE` | ROS1+2 | Workspace path to source automatically |
| `ROS_MASTER_URI` | ROS1 | URI of the ROS1 master node |
| `ROS_HOSTNAME` | ROS1 | Hostname advertised on the ROS network |
| `ROS_IP` | ROS1 | IP advertised (alternative to hostname) |
| `ROS_DOMAIN_ID` | ROS2 | Network isolation (0-232, default: 0) |
| `ROS_RMW_IMPLEMENTATION` | ROS2 | DDS middleware |

## Files

| File | Description |
|------|-------------|
| `/etc/ros/adnrpi-ros.conf` | Persistent config (key=value) |
| `/etc/bash.bashrc` | Auto-generated ROS block (do not edit manually) |
| `/var/log/adnrpi-firstboot.log` | First boot log |

## Installed packages

### ROS2 Humble

- `ros-humble-ros-base` — full middleware
- `ros-humble-tf2`, `tf2-ros`, `tf2-tools`
- `ros-humble-nav-msgs`, `geometry-msgs`, `sensor-msgs`, `std-msgs`
- `ros-humble-image-transport`, `compressed-image-transport`
- `ros-humble-rosbridge-suite` — WebSocket bridge
- `ros-humble-teleop-twist-joy`, `teleop-twist-keyboard`
- `ros-humble-serial-driver`
- `ros-humble-robot-state-publisher`, `joint-state-publisher`, `xacro`
- `python3-colcon-common-extensions`, `python3-rosdep`

### ROS1 Noetic

- `ros-noetic-ros-base` — full middleware
- `ros-noetic-tf`, `tf2`, `tf2-ros`, `tf2-tools`
- `ros-noetic-nav-msgs`, `geometry-msgs`, `sensor-msgs`, `std-msgs`
- `ros-noetic-image-transport`, `compressed-image-transport`
- `ros-noetic-rosserial`, `rosserial-arduino`
- `ros-noetic-rosbridge-suite`
- `ros-noetic-map-server`, `move-base-msgs`
- `ros-noetic-teleop-twist-joy`, `teleop-twist-keyboard`
- `ros-noetic-robot-state-publisher`, `joint-state-publisher`, `xacro`
- `python3-rosdep`, `python3-rosinstall`
