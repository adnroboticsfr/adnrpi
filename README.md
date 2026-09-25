# adnrpi

Custom Armbian image builder for the **SmartPi One** (Allwinner H3) by **ADN Robotics**.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub Issues](https://img.shields.io/github/issues/adnroboticsfr/adnrpi)](https://github.com/adnroboticsfr/adnrpi/issues)

---

## Documentation

| | |
|---|---|
| [Getting Started](docs/getting-started.md) | Flash an image and boot |
| [First Boot](docs/first-boot.md) | Configure from the SD card |
| [ROS Configuration](docs/ros-configuration.md) | ROS1/ROS2 + `adnrpi-ros-config` |
| [SSH over USB](docs/ssh-usb.md) | Access without Ethernet |
| [Build an image](docs/build.md) | GitHub Actions + local build |
| [H3 Overclock](docs/H3-OVERCLOCK.md) | 1296 → 1368 MHz |

---

## What is this?

`adnrpi` builds ready-to-flash Armbian images for the **SmartPi One** and **SmartPi Pad** (Allwinner H3) boards. It wraps the official Armbian build system with board-specific patches, kernel overlays, and automation scripts so you get a working image without manual configuration.

---

## Supported hardware

| Board       | SoC                    | RAM                     |
|-------------|------------------------|-------------------------|
| SmartPi One | Allwinner H3 quad-core | 1 GB                    |
| SmartPi Pad | Allwinner H3 quad-core | 1 GB + 4.3" touchscreen |

The SmartPi Pad uses the same `adnrpi1` images — the 800×480 screen and 180° rotation are detected and applied automatically at boot.

---

## Supported distributions

| OS | Codename | Status |
|----|----------|--------|
| Debian 11 | Bullseye | Legacy (server only) |
| Debian 12 | Bookworm | Oldstable |
| Debian 13 | Trixie | **Current stable** |
| Debian 14 | Forky | Testing preview |
| Ubuntu 22.04 | Jammy | LTS (server only) |
| Ubuntu 24.04 | Noble | **Current LTS** |

---

## Key features

- **Instant boot logo** — built into U-Boot, drawn the moment video initialises, before anything is read from the SD card
- **Universal display support** — fixed at 1280×720@60, works on everything from the ADNRPi Pad panel to 4K monitors
- **H3 CPU overclock to 1368 MHz** — explicit opt-in, stress-tested at fixed voltage
- **SSH over USB OTG** — one cable powers the board and provides a network interface (NCM gadget, works on Linux / Windows 11 / macOS)
- **Kernel headers pre-installed** — build DKMS modules directly on the board

---

## CPU overclock

By default images run at stock **1296 MHz** with the adaptive governor.

```bash
sudo adnrpi-oc on      # enable 1368 MHz, then reboot
sudo adnrpi-oc off     # back to stock, then reboot
sudo adnrpi-oc status  # current state
```

After enabling, verify:

```bash
sudo adnrpi-oc status
# overclock: on
# current max: 1368000 kHz
# governor:    performance
```

A heatsink with active fan is recommended for sustained workloads. The thermal throttle stays active at 85 °C.

See [docs/H3-OVERCLOCK.md](docs/H3-OVERCLOCK.md) for technical details.

---

## SSH over USB

Connect the OTG port to any computer — it powers the board and creates a USB network interface.

```bash
# Board IP
ssh root@172.22.1.1
# Set 172.22.1.2/24 on the host side
```

---

## Image naming

```
ADNRPi-{board}-{codename}-{distro_version}-{variant}-{timestamp}.img.xz
```

Examples:
- `ADNRPi-adnrpi1-trixie-debian13-server-2026-01-01-1200.img.xz`
- `ADNRPi-adnrpi1-trixie-debian13-desktop_XFCE-2026-01-01-1200.img.xz`

---

## Project structure

```
adnrpi/
├── boards/
│   └── adnrpi1.wip            # H3 board definition
├── configs/
│   ├── config-default.conf     # Default build settings
│   └── adnrpi1-*.conf         # Per-distro/variant configs
├── docs/
│   └── H3-OVERCLOCK.md
├── userpatches/
│   ├── customize-image.sh      # Post-build customisation
│   ├── extensions/             # Armbian extension overrides
│   ├── kernel/                 # Kernel patches
│   ├── overlay/                # Files copied into the image
│   └── u-boot/                 # U-Boot patches
└── tools/
    └── fix-nm-applet-in-framework.sh
```

---

## Build locally

Requires a Debian/Ubuntu x86-64 host (or WSL2).

```bash
git clone https://github.com/armbian/build.git
cd build
# Copy userpatches/ and configs/ from this repo into build/
bash compile.sh BOARD=adnrpi1 BRANCH=current RELEASE=trixie BUILD_DESKTOP=no
```

---

## Add a new distribution

1. Create `configs/adnrpi1-{codename}-{variant}.conf`
2. Set at minimum: `BOARD`, `RELEASE`, `BUILD_DESKTOP`, `BRANCH`
3. Push — the CI workflow picks it up automatically

---

## Kernel packages (DKMS)

Each release ships matching `.deb` packages (`linux-image`, `linux-headers`, `linux-dtb`, `linux-u-boot`). Install headers from the release, not from apt.armbian.com:

```bash
wget https://github.com/adnroboticsfr/adnrpi/releases/latest/download/linux-headers-current-sunxi_<version>.deb
sudo dpkg -i linux-headers-current-sunxi_<version>.deb
```

---

## Contributing

1. Fork the repo
2. Branch off `develop`
3. Open a pull request targeting `develop`

---

## License

GPL-3.0 — see [LICENSE](LICENSE).

---

## Credits

Based on the Armbian build system. Original board bring-up work derived from open-source contributions to the sunxi community.
