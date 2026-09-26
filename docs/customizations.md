# ADNRPi — Customizations Tracking

This document lists every modification applied on top of the Armbian base image.
When upgrading to a new Armbian version, go through each section and verify that
the change is still needed, still compatible, and still applied correctly.

**Last reviewed against:** Armbian main (26.11.x) — 2026-09-26

---

## How to use this document for an Armbian upgrade

1. Run the new build and check which sections show failures in CI logs.
2. For each section below, check **Status after upgrade** and re-test on hardware.
3. Update the **Last reviewed against** date above when done.

---

## 1. Board definition

| Item | Value |
|------|-------|
| File | `boards/adnrpi1.conf` |
| Risk on upgrade | **Medium** — Armbian may rename or restructure board config fields |

### What it does
Declares the SmartPi One (Allwinner H3) as the `adnrpi1` board with the
`sun8i` board family, FAT boot partition, and legacy/current/edge kernel targets.

### Key fields
```
BOARDFAMILY="sun8i"
BOOTCONFIG="adnrpi1_defconfig"
SERIALCON="ttyS0"
KERNEL_TARGET="legacy,current,edge"
SUNXI_OVERLAY_PREFIX="sun8i-h3"
```

### Verification after upgrade
- Build succeeds without "no sunxi" or "unknown board" errors.
- `uname -r` on the image shows a sun8i kernel.

---

## 2. Build defaults

| Item | Value |
|------|-------|
| File | `configs/config-default.conf` |
| Risk on upgrade | **Low** — our overrides are in separate per-image configs |

### What it does
- Sets `VENDOR="ADNRPi"` and `DIST_VERSION`
- Disables BTF kernel debug info (`KERNEL_BTF=no`) — GitHub Actions runners do
  not have enough RAM (needs 6.5 GB+); would cause OOM kills during build.
- Sets `KERNEL_CONFIGURE=no` and `CLEAN_LEVEL` for CI.

### Verification after upgrade
- Builds complete without OOM kills.
- Image filenames carry the `ADNRPi-` prefix.

---

## 3. Ubuntu jammy (22.04) — disabled

| Item | Value |
|------|-------|
| Files | `configs/adnrpi1-jammy-*.disabled` |
| Risk on upgrade | **Revisit each release** |

### Why disabled
Armbian's BSP postinst for custom H3 boards fails on Ubuntu 22.04 with
`no sunxi` error during dpkg installation of `armbian-bsp-cli-adnrpi1-current`.
Reproducible on both Armbian `main` and `v24.11`. Root cause is in the Armbian
BSP package, not our board file.

### When to re-enable
Check Armbian release notes for fixes to custom board support on Ubuntu 22.04.
Test by re-naming one `.disabled` back to `.conf` and triggering a single build
via **BuildSingleImage** workflow.

---

## 4. First-boot configuration system

| Item | Value |
|------|-------|
| Files | `userpatches/overlay/adnrpi-config.txt`, `adnrpi-firstboot.sh`, `adnrpi-firstboot.service` |
| Script install | `customize-image.sh → installFirstBootConfig()` |
| Risk on upgrade | **Low** — self-contained, no Armbian internals dependency |

### What it does
On first boot, reads `/boot/adnrpi-config.txt` (editable before inserting the SD
card) and applies: hostname, SSH, timezone, locale, keyboard, WiFi, static IP,
root password, user creation, ROS configuration.

Compatible with Raspberry Pi Imager files (`ssh`, `wpa_supplicant.conf`,
`userconf.txt`, `user-data`) for users familiar with that workflow.

### Verification after upgrade
- Edit `adnrpi-config.txt` with `APPLY_CONFIG=1` and a custom hostname.
- Boot the image; confirm hostname and settings are applied.
- Check `/var/log/adnrpi-firstboot.log` for errors.

---

## 5. Interactive setup wizard

| Item | Value |
|------|-------|
| Files | `userpatches/overlay/adnrpi-setup`, `adnrpi-setup-profile.sh` |
| Script install | `customize-image.sh → installFirstBootConfig()` |
| Risk on upgrade | **Low — BUT check Armbian first-run suppression (see §6)** |

### What it does
On first root login, launches an interactive wizard covering hostname, timezone,
locale, keyboard, root/user passwords, and WiFi. Saves state to
`/etc/adnrpi/setup.conf`. Profile.d trigger re-launches until setup completes.
On OS update, prompts to review new options if `SETUP_VERSION` increased.

### Load priority in `load_current()`
1. Hard-coded defaults (lowest)
2. `/boot/adnrpi-config.txt` — only if `setup.conf` does not yet exist
3. `/etc/adnrpi/setup.conf` — always wins (highest)

### Verification after upgrade
- Delete `/etc/adnrpi/setup.conf` and `/root/.not_logged_in_yet` then log in as root.
- Wizard should appear once, save state, and not re-appear on next login.

---

## 6. Armbian first-run wizard — suppressed

| Item | Value |
|------|-------|
| Script install | `customize-image.sh → installFirstBootConfig()` |
| Risk on upgrade | **High** — Armbian may change the mechanism between releases |

### What it does
Removes `/root/.not_logged_in_yet` and disables
`/etc/profile.d/armbian-check-first-run.sh` so Armbian's built-in wizard
(which asks for the same hostname/password/locale/user settings) does not
run alongside our `adnrpi-setup` wizard.

### What to check after upgrade
Armbian may introduce a new first-run mechanism. Search the built image for:
```bash
grep -r "not_logged_in" /etc/profile.d/ /etc/rc.local /root/
find /etc/profile.d/ -name "*armbian*" -o -name "*first*"
```
If a new mechanism exists, add its suppression to `installFirstBootConfig()`.

---

## 7. USB gadget network (OTG)

| Item | Value |
|------|-------|
| Files | `userpatches/overlay/usb-gadget-net.sh`, `usb-gadget-net.service` |
| Script install | `customize-image.sh → installUsbGadgetNet()` |
| Risk on upgrade | **Low** — uses standard kernel g_ncm module and systemd |

### What it does
Configures the OTG USB port as a CDC-NCM network gadget. Connecting the OTG
port to a computer gives SSH access at `172.22.1.1` without Ethernet.

### Verification after upgrade
- Connect OTG cable to a computer.
- SSH to `172.22.1.1` as root.
- `ip link` on the host should show a USB network interface.

---

## 8. simpledrm blacklist

| Item | Value |
|------|-------|
| Script install | `customize-image.sh → disableSimpledrm()` |
| Risk on upgrade | **Low** — blacklist via modprobe.d and kernel cmdline |

### Why needed
U-Boot hands the kernel a simple-framebuffer node. The `simpledrm` driver binds
to it alongside `sun4i-drm`, causing two conflicting framebuffers. The console
ends up drawn into the one that is not scanned out → black screen (verified on
hardware).

### What it sets
- `/etc/modprobe.d/adnrpi-no-simpledrm.conf` — `blacklist simpledrm`
- `extraargs=module_blacklist=simpledrm` in `/boot/armbianEnv.txt`

### Verification after upgrade
- Boot the image; confirm you get a visible console on HDMI.
- `dmesg | grep simpledrm` should show the module is blacklisted.

---

## 9. HDMI video mode

| Item | Value |
|------|-------|
| Script install | `customize-image.sh → forceUniversalVideoMode()` |
| Risk on upgrade | **Low** |

### What it sets
`video=HDMI-A-1:1280x720@60` in `armbianEnv.txt`.

### Why needed
Without a forced mode, H3 negotiates with 4K screens and attempts 4K@60 which
it cannot drive (HDMI 1.4, max 4K@30). Forcing 720p gives a picture on every
screen.

### Interaction with ADNRPi Pad
`adnrpipad-console-rotate.service` detects the 4.3" pad and automatically
switches `armbianEnv.txt` to `800x480@60`, then reboots once. On non-pad boots
it restores 720p. See §10.

---

## 10. ADNRPi Pad — screen detection, rotation, resolution, font

| Item | Value |
|------|-------|
| Files | `adnrpipad-detect.sh`, `adnrpipad-console-rotate.sh`, `adnrpipad-console-rotate.service`, `adnrpi-pad-font.sh` |
| Script install | `customize-image.sh → installADNRPiPadDetection()` |
| Risk on upgrade | **Medium** — depends on DRM sysfs paths staying stable |

### What it does
At boot, the service waits up to 20 s for the USB touchscreen and DRM connector
to enumerate. If the 4.3" 800×480 panel is detected:

1. **Rotation** — writes `2` to `/sys/class/graphics/fbcon/rotate_all` (180°).
2. **Resolution** — if `armbianEnv.txt` still has `720p`, updates to `800x480`
   and reboots once (flag: `/boot/.adnrpi-display-reboot` prevents loops).
3. **Font** — applies `Uni2-Terminus32x16.psf.gz` to all 6 TTYs.
4. **Profile.d** — `adnrpi-pad-font.sh` re-applies the font at each TTY login.

If no pad is found and `armbianEnv.txt` has `800x480`, restores `720p` and
reboots once.

### Packages installed
`kbd` (provides `setfont`) and `console-setup-linux` (provides Terminus fonts).

### DRM sysfs paths to verify after upgrade
```
/sys/class/graphics/fbcon/rotate_all   # console rotation
/sys/class/graphics/fb0/mode           # live resolution switch (currently unused — H3 does not support it)
```

### Verification after upgrade
- Boot with pad connected: rotation + large font + 800×480 on second boot.
- Boot with normal monitor: 720p, no rotation, default font.

---

## 11. H3 overclock control

| Item | Value |
|------|-------|
| Files | `userpatches/overlay/adnrpi-oc`, `opp1368.dts` |
| Script install | `customize-image.sh → installOverclockControl()` |
| Risk on upgrade | **Medium** — device tree overlay format may change between kernel versions |

### What it does
Provides `adnrpi-oc on/off`. Off: stock 1296 MHz, adaptive governor.
On: 1368 MHz at 1.40 V, performance governor (ADNRPi-validated, no frequency
hopping which hangs the board at boot).

The 1368 MHz OPP is applied via a device tree overlay (`opp1368.dtbo`) compiled
at build time and stored in `/boot/overlay-user/`.

### Verification after upgrade
```bash
adnrpi-oc on
cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq   # expect 1368000
adnrpi-oc off
```

---

## 12. Desktop — Chromium software GL

| Item | Value |
|------|-------|
| Files | `userpatches/overlay/adnrpi-mali-softgl` |
| Script install | `customize-image.sh → installChromiumFlags()` |
| Risk on upgrade | **Low** — env file in `/etc/chromium.d/` |
| Applies to | trixie, forky, sid desktop builds only |

### Why needed
Mali-400 (lima driver) is GLES2-only. Chromium's GPU process cannot create a
usable GL context and crashes. `LIBGL_ALWAYS_SOFTWARE=1` forces Mesa software
rendering. Noble is not affected (uses xtradeb Chromium which renders fine).

### Verification after upgrade
- Open Chromium on a trixie/forky desktop build.
- Confirm pages render; no white/blank windows.

---

## 13. ROS installation

| Item | Value |
|------|-------|
| Function | `customize-image.sh → installROS2()`, `installROS1Noetic()` |
| Risk on upgrade | **Medium** — ROS APT repo keys and package names change between distros |

### Configs and targets

| Config                      | OS            | ROS        | État                            |
|-----------------------------|---------------|------------|---------------------------------|
| `noble-ros2-jazzy-server`   | Ubuntu 24.04  | ROS2 Jazzy | actif                           |
| `focal-ros1-server`         | Ubuntu 20.04  | ROS1 Noetic| désactivé `.disabled` (EOL)     |

### Ubuntu 20.04 focal — désactivé (EOL avril 2025)

`adnrpi1-focal-ros1-server.conf` renommé en `.disabled`. Ubuntu 20.04 a atteint sa
fin de vie en avril 2025 : les paquets ne sont plus accessibles sur les miroirs
standards. Armbian `artifact-armbian-base-files.sh` échoue avec
`found_package_filename est nul` car `base-files` n'est plus dans `focal-updates`.
ROS1 Noetic est également EOL depuis mai 2025.

Pour réactiver si besoin : patcher Armbian pour pointer vers `old-releases.ubuntu.com`
au lieu des miroirs standards, puis renommer le `.disabled` en `.conf`.

### APT key rotation

ROS GPG keys are imported at build time. If the key changes, the build fails
with a GPG verification error. Update the key URL in `installROS2()` as needed.

### Verification after upgrade

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic list
```

---

## 14. GitHub Actions — build matrix

| Item | Value |
|------|-------|
| Files | `.github/workflows/BuildImages.yml`, `BuildSingleImage.yml`, `actions/build-image/action.yml` |
| Risk on upgrade | **Low** |

### Key behaviors
- Matrix is auto-generated from `configs/*.conf` (excludes `*.disabled`).
- `ARMBIAN_BRANCH` can be overridden per config file.
- Kernel debs uploaded from `trixie-server` (current branch) and `bullseye-server` (legacy branch).
- `focal-` added to the image name prefix mapping alongside `jammy-` and `noble-`.

### When upgrading Armbian branch
Change `ARMBIAN_BRANCH` in `configs/config-default.conf`. Test one config with
`BuildSingleImage` before updating the default.

---

## 15. HackPad — interface pentesting tactile Kivy

| Item | Valeur |
|------|--------|
| Files app | `userpatches/overlay/hackpad/` (main.py, screens/, tools/) |
| Files système | `adnrpi-hackpad.service`, `adnrpi-hackpad.desktop`, `hackpad/adnrpi-switch-mode` |
| Config build | `configs/adnrpi1-bookworm-pentest-server.conf` (`ADNRPI_PENTEST=yes`) |
| Script install | `customize-image.sh → installPentestTools() + installHackPad()` |
| Risk on upgrade | **Medium** — dépend de la compatibilité Kivy + SDL2 backend KMS |

### Ce que ça fait
Un OS de pentest complet démarrant en **mode serveur** (pas d'X11) avec une interface
tactile Kivy sur le framebuffer KMS. Depuis l'interface, l'utilisateur peut basculer
en **mode desktop** (XFCE + LightDM) via un bouton qui change la cible systemd et redémarre.

#### Architecture mode dual

| Mode            | systemd default      | Service actif              |
|-----------------|----------------------|----------------------------|
| Server (défaut) | `multi-user.target`  | `adnrpi-hackpad.service`   |
| Desktop         | `graphical.target`   | `lightdm.service`          |

CLI helper : `adnrpi-switch-mode [server|desktop]`

#### Outils pentesting installés

`installPentestTools()` installe : nmap, masscan, aircrack-ng, nikto, sqlmap, gobuster,
john, hydra, hashcat, dnsrecon, theHarvester, tcpdump, tshark, responder, netcat, curl, wget

#### Structure de l'app Kivy (`/opt/adnrpi-hackpad/`)

```text
main.py               — détecte framebuffer vs X11, SDL env vars
screens/
  home.py             — grille 3×2 catégories avec boutons settings/mode
  category.py         — liste outils filtrée par catégorie (scroll 2 colonnes)
  tool.py             — champs paramètres, RUN/STOP/CLEAR, output live via subprocess
  settings.py         — IP cible, interface, wordlist, dossier output, sysinfo
  mode.py             — bascule server/desktop + reboot en 5 s
tools/
  registry.py         — 35 outils, 6 catégories
```

#### Registre d'outils (registry.py)

| Catégorie | Nombre | Exemples                                   |
|-----------|--------|--------------------------------------------|
| network   | 8      | nmap (ping/ports/full/vuln), masscan, netcat |
| wifi      | 7      | airodump-ng, aireplay-ng, aircrack-ng      |
| web       | 6      | nikto, sqlmap, gobuster, curl              |
| passwords | 6      | hydra, john, hashcat                       |
| recon     | 6      | dnsrecon, theHarvester, whois              |
| capture   | 7      | tcpdump, tshark, responder                 |

#### Service systemd

```ini
[Service]
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_RENDERDRIVER=opengles2
Environment=KIVY_WINDOW=sdl2
Environment=KIVY_GL_BACKEND=sdl2
Environment=DISPLAY=
ExecStart=/usr/bin/python3 /opt/adnrpi-hackpad/main.py
Restart=on-failure
RestartSec=5
WantedBy=multi-user.target
```

#### Paramètres sauvegardés

`/etc/adnrpi-hackpad/settings.conf` — IP cible, interface réseau, wordlist, dossier output

### Vérification après upgrade

- `python3 -c "import kivy"` — Kivy s'installe correctement sur le nouvel OS
- `SDL_VIDEODRIVER=kmsdrm python3 -c "import kivy"` — backend KMS détecté sans erreur
- Lima / GLES2 toujours fonctionnel sur H3 (`/dev/dri/card0` présent, `dmesg | grep lima`)
- `systemctl status adnrpi-hackpad` — service démarre en mode server
- Bascule mode Desktop dans l'app → `graphical.target` → LightDM démarre bien au reboot
- `adnrpi-switch-mode server` → revient en mode Kivy au reboot
- Tous les outils pentesting disponibles dans les dépôts APT du nouvel OS

---

## Checklist for a new Armbian release

- [ ] Update `ARMBIAN_BRANCH` in `config-default.conf`
- [ ] Trigger `BuildSingleImage` on `adnrpi1-bookworm-server` as smoke test
- [ ] Check §6 — does Armbian's first-run mechanism still work the same way?
- [ ] Check §10 — do the DRM sysfs paths still exist?
- [ ] Check §11 — does the OPP overlay compile cleanly with the new kernel?
- [ ] Check §13 — are ROS GPG keys still valid?
- [ ] Check §15 — does Kivy install and start on KMS framebuffer? (bookworm-pentest build)
- [ ] Check §15 — are all pentesting tools still in APT repos for the new base OS?
- [ ] Re-enable jammy configs (§3) if the `no sunxi` BSP error is fixed upstream
- [ ] Update **Last reviewed against** at the top of this file
