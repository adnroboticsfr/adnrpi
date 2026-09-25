# Getting Started

## 1. Download an image

Go to [Releases](https://github.com/adnroboticsfr/adnrpi/releases) and pick the image that fits your use case:

| Image | Use case |
|-------|----------|
| `ADNRPi-adnrpi1-trixie-debian13-server` | Lightweight server, general purpose |
| `ADNRPi-adnrpi1-noble-ubuntu24.04-server` | Ubuntu LTS server |
| `ADNRPi-adnrpi1-trixie-debian13-desktop_XFCE` | XFCE desktop |
| `ADNRPi-adnrpi1-jammy-ubuntu22.04-ros2-server` | **ROS2 Humble** |
| `ADNRPi-adnrpi1-jammy-ubuntu22.04-ros1-server` | **ROS1 Noetic** |

## 2. Flash the SD card

**With Balena Etcher (recommended):**
1. Download [Balena Etcher](https://etcher.balena.io)
2. Select the `.img.xz` file
3. Select your SD card
4. Flash

**With dd (Linux/macOS):**
```bash
xz -dc ADNRPi-adnrpi1-trixie-debian13-server-*.img.xz | sudo dd of=/dev/sdX bs=4M status=progress
sync
```

## 3. Configure before first boot (optional)

Before inserting the SD card, open the FAT partition and edit `adnrpi-config.txt`:

```ini
APPLY_CONFIG=1
HOSTNAME=my-robot
WIFI_SSID=MyNetwork
WIFI_PASSWORD=mypassword
WIFI_COUNTRY=FR
SSH_ENABLED=1
TIMEZONE=Europe/Paris
```

For ROS images, also add ROS parameters — see [ROS Configuration](ros-configuration.md).

## 4. First boot

1. Insert the SD card into the ADNRPi One
2. Plug in power
3. The ADN Robotics logo appears immediately (U-Boot, before SD card is read)
4. The system boots and applies the configuration automatically

**SSH over the network:**
```bash
ssh root@<board-ip>
```

**SSH over USB OTG** (see [SSH over USB](ssh-usb.md)):
```bash
ssh root@172.22.1.1
```

## 5. Default credentials

| User | Password |
|------|----------|
| `root` | `1234` (prompted to change on first login) |
