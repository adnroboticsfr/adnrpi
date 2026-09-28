# ADNRPi — Customizations Tracking

This document lists every modification applied on top of the Armbian base image.
When upgrading to a new Armbian version, go through each section and verify that
the change is still needed, still compatible, and still applied correctly.

**Last reviewed against:** Armbian main (26.11.x) — 2026-09-28

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
| Risk on upgrade | **Medium** — dépend de la compatibilité Kivy + SDL2 + Xorg sur le nouvel OS |

### Ce que ça fait
Un OS de pentest complet avec une interface tactile Kivy sous **X11** (Xorg modesetting
+ Lima DRI3). Démarre automatiquement au boot via `adnrpi-hackpad.service` (xinit).
Depuis l'interface, l'utilisateur peut basculer en mode desktop (XFCE) avec
`adnrpi-switch-mode desktop`.

### Découverte critique — SDL2 KMS non disponible sur Debian Bookworm

> **La libSDL2 Debian Bookworm (ARM) ne contient PAS le backend `kmsdrm`.**
> `strings libSDL2-2.0.so.0 | grep -E "^(kmsdrm|fbdev)"` → vide.
> Seuls `offscreen` et `wayland` sont compilés. `SDL_VIDEODRIVER=kmsdrm` tombe
> silencieusement en mode `offscreen` (rendu en mémoire, écran noir).
>
> **Solution : utiliser Xorg** avec le driver `modesetting` (Lima DRI3, glamor).

### Séquence de démarrage

```text
boot
 └─ systemd → adnrpi-firstboot.service (config hostname/wifi/password — 1re fois seulement)
     └─ adnrpi-hackpad.service (After=adnrpi-firstboot.service)
         └─ xinit launch.sh -- :0 vt1 -nolisten tcp
             └─ Xorg :0  (modesetting driver, Lima DRI3)
                 └─ launch.sh → xrandr force 800×480 si besoin → python3 main.py
                     └─ HackPad Kivy (DISPLAY=:0, SDL2 X11 backend, borderless 800×480)
```

Fichiers de démarrage :

| Fichier | Rôle |
|---------|------|
| `/etc/systemd/system/adnrpi-hackpad.service` | Service systemd — `xinit launch.sh -- :0 vt1`, `After=adnrpi-firstboot.service` |
| `/opt/adnrpi-hackpad/launch.sh` | Détecte écran, force 800×480 si 5 pouces, lance python3 main.py |
| `/etc/X11/xorg.conf.d/99-adnrpi-hackpad.conf` | Xorg config — force PreferredMode 800×480 sur HDMI-1 |

### Détection d'écran et résolution (launch.sh)

`launch.sh` interroge `xrandr` pour identifier l'écran connecté **avant** de
lancer Kivy. Il ne change la résolution **que si nécessaire** — évite le flash
visible causé par un double changement de mode au démarrage.

| Écran connecté | Mode préféré EDID | Comportement |
|---|---|---|
| 5 pouces 800×480 (pentest nomade) | `800x480+` | Force 800×480 si pas déjà actif → `HACKPAD_W=800 HACKPAD_H=480` |
| Moniteur externe (bureau/dev) | autre (ex: `1920x1080+`) | Aucun xrandr — résolution native → `HACKPAD_W=W HACKPAD_H=H` |

`main.py` lit `HACKPAD_W/H` via `os.environ` pour créer la fenêtre Kivy à la
bonne taille dans les deux cas — borderless à (0,0), remplit l'écran.

**Xorg config** (`/etc/X11/xorg.conf.d/99-adnrpi-hackpad.conf`) :
force `PreferredMode 800x480` sur HDMI-1 pour que Xorg démarre directement à
la bonne résolution (1er niveau de protection, avant même launch.sh).

**Pourquoi le flash se produit sans cette logique** : si `xrandr` est appelé
inconditionnellement après que Xorg a déjà choisi 800x480, il force quand même
un 2e changement de mode → flash visible inutile.

### Polices emoji

Les emoji dans l'app (grille catégories) utilisent `NotoColorEmoji.ttf` via markup Kivy :

```python
LabelBase.register("NotoEmoji", "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf")
# Utilisation dans les widgets :
text="[font=NotoEmoji][size=26]🌐[/size][/font]\n[size=18]Network[/size]"
```

> **Attention** : NotoColorEmoji est une police bitmap — `[size=X]` ne réduit pas
> proportionnellement. Pour les petits boutons header, utiliser du texte Roboto (`"SET"`, `"MODE"`).

### Apt packages requis dans `installHackPad()`

```bash
python3-kivy
libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0
libgles2 libgbm1 libegl-mesa0 libdrm2 libmtdev1
xserver-xorg-core xserver-xorg-video-fbdev xserver-xorg-input-evdev xinit x11-xserver-utils
fonts-noto fonts-noto-color-emoji fonts-dejavu-core
xfce4 xfce4-terminal lightdm
```

> **Ne pas inclure** : `python3-kivymd` (absent des repos Debian), `libsdl2-*-dev` (headers build-time).

### Structure de l'app Kivy (`/opt/adnrpi-hackpad/`)

```text
main.py               — config Kivy (800×480, fullscreen, keyboard_mode="")
                        + LabelBase.register("NotoEmoji", ...)
screens/
  home.py             — grille 3×2 catégories, boutons SET/MODE texte
  category.py         — liste outils filtrée par catégorie (scroll 2 colonnes)
  tool.py             — champs tap-to-edit + pré-remplissage depuis settings,
                        RUN/STOP/CLR, output live subprocess
  settings.py         — 4 champs tap-to-edit (target_ip, interface, wordlist, output_dir)
  mode.py             — bascule server/desktop + reboot en 5 s
  keyboard.py         — InputPopup partagé (clavier tactile + physique)
tools/
  registry.py         — 41 outils, 6 catégories
```

### Clavier partagé (`screens/keyboard.py`)

`InputPopup` est le composant central utilisé dans tous les écrans qui ont des champs
de saisie. Il s'ouvre en popup au tap, ne perturbe pas le layout de fond.

Points critiques d'implémentation :

- **`keyboard_mode=""`** dans `main.py` — empêche Kivy de tenter d'ouvrir un clavier
  système (ce qui redimensionnerait la fenêtre et ferait descendre le header)
- **`Window.bind(on_key_down=...)` dans `on_open`** (pas dans `__init__`) + délai 400 ms
  via `Clock.schedule_once` — évite de capturer le tap d'ouverture comme saisie
- **Debounce 150 ms** dans `_type()` — anti double-tap sur écran résistif
- **`auto_dismiss=False`** — le popup ne se ferme pas en tapant à côté
- **`on_dismiss` délie** toujours le handler — pas de fuites de bindings

```python
class InputPopup(Popup):
    def on_open(self):
        Clock.schedule_once(self._enable_keys, 0.4)   # grâce de 400 ms

    def _enable_keys(self, dt):
        self._keys_enabled = True
        Window.bind(on_key_down=self._physical_key)

    def _type(self, val):
        now = time.monotonic()
        if now - self._last_type < 0.15:              # anti double-tap
            return
        ...

    def _physical_key(self, window, key, scancode, codepoint, modifiers):
        if not self._keys_enabled:
            return True                               # ignorer pendant la grâce
        ...
        return True                                   # consommer l'événement
```

`make_field_button(label, value, on_confirm, hint="")` — helper qui retourne un `Button`
stylé sombre qui ouvre `InputPopup` au tap. Affiche le hint en gris quand vide.
Utilisé dans `settings.py` et `tool.py`.

### Bug fix tool.py (Python 3 lambda + exception)

```python
# FAUX — Python 3 supprime `e` après le bloc except, le lambda plante
except Exception as e:
    Clock.schedule_once(lambda dt: self._append(f"[ERROR] {e}\n"), 0)

# CORRECT — capturer avant le lambda
except Exception as e:
    err = str(e)
    Clock.schedule_once(lambda dt, err=err: self._append(f"[ERROR] {err}\n"), 0)
```

### Clavier virtuel (settings.py) — popup custom

Trois approches ont échoué avant de trouver la solution finale :

| Approche | Problème |
| --- | --- |
| `keyboard_mode="dock"` (VKeyboard Kivy) | Focus TextInput perdu au `touch_up` → clavier disparaît immédiatement |
| VKeyboard inline dans BoxLayout (`do_translation=False`) | Widget Scatter ne se rend pas dans un layout normal → clavier invisible |
| Clavier custom permanent en bas de l'écran | Double entrée à chaque touche tactile |

**Solution finale** : `InputPopup` — un `Popup` custom qui s'ouvre au tap sur un champ,
avec son propre affichage de la valeur en cours + grille de boutons QWERTY.

```python
class InputPopup(Popup):
    # Popup (size_hint 0.97×0.80) avec :
    # - Label affichant la valeur + curseur "▌"
    # - 4 rangées de lettres (GridLayout de Button)
    # - Rangée symboles : . / - _ SPACE ⌫ OK✓
    # - Window.bind(on_key_down=...) pour clavier physique simultané
    # - Debounce 150 ms dans _type() contre le double-tap touchscreen

    def _type(self, val):
        now = time.monotonic()
        if now - self._last_type < 0.15:   # anti double-tap résistif
            return
        self._last_type = now
        ...

    def _physical_key(self, window, key, scancode, codepoint, modifiers):
        # key 8 = backspace, 13/271 = enter (confirm), 27 = escape (cancel)
        # return True consomme l'événement pour ne pas l'envoyer aux widgets de fond
        ...

    def on_dismiss(self):
        Window.unbind(on_key_down=self._physical_key)  # toujours nettoyer
```

Avantages de cette approche :

- Aucun problème de focus — le TextInput de fond n'est jamais ciblé
- Clavier physique + tactile simultanément
- Popup `auto_dismiss=False` : ne se ferme pas accidentellement
- `on_dismiss` délie toujours le handler physique (pas de fuites)

Les champs settings sont des `Button` (non des `TextInput`) stylés en sombre — le tap
ouvre le popup, la valeur confirmée est réécrite dans `self._values[key]` et
affichée dans le bouton.

### Registre d'outils (registry.py)

41 outils au total, 6 catégories. Les champs `target`, `iface`, `wordlist`, `output` sont
pré-remplis automatiquement depuis `/etc/adnrpi-hackpad/settings.conf` si la valeur par
défaut est vide.

| Catégorie | # | Contenu |
| --- | --- | --- |
| network | 12 | ping, arp-scan, arp -a, nmap (quick/full/os/vuln/script), masscan, traceroute, netdiscover, port-check |
| wifi | 6 | workflow numéroté : 1.airmon start → 2.airodump scan → 3.airodump capture → 4.aireplay deauth → 5.aircrack → 6.airmon stop |
| web | 5 | curl headers, nikto, gobuster dir/dns, sqlmap |
| passwords | 7 | hashid, john, hydra ssh/ftp/http, smbclient, crunch |
| recon | 4 | whois, dig (+ reverse), dnsrecon, host lookup (dig -x) |
| capture | 7 | tcpdump, tshark capture/read, netstat (ss -tulpn), ngrep, nc listen/connect |

Outils retirés car non disponibles sur Debian Bookworm ARM :
`wifite`, `whatweb`, `enum4linux`, `fierce`, `theHarvester`, `responder`,
`kismet`, `reaver`, `bully`, `hashcat`, `medusa`, `wireshark`, `ettercap`, `metasploit`.

**Outils apt requis** (voir `installPentestTools()` dans `customize-image.sh`) :

```bash
apt-get install -y nmap masscan netdiscover arp-scan net-tools traceroute whois dnsutils \
  aircrack-ng iw rfkill \
  nikto sqlmap gobuster dirb curl wget \
  john hydra crunch smbclient dnsrecon \
  tcpdump tshark ngrep netcat-traditional socat \
  xsel python3-pip
pip3 install hashid
# Wordlists (Kali 'wordlists' package absent — téléchargement manuel) :
mkdir -p /usr/share/wordlists
ln -sf /usr/share/dirb/wordlists/common.txt /usr/share/wordlists/common.txt
curl -L ".../rockyou-75.txt" -o /usr/share/wordlists/rockyou.txt
```

**Wordlists** — `/usr/share/wordlists/` n'existe pas sur Debian (package Kali uniquement).
Le script crée ce dossier et télécharge `rockyou.txt` (59k mots, SecLists).
Defaults dans le registry : Hydra/John/Aircrack → `rockyou.txt` ; Gobuster → `common.txt`.

**Workflow WiFi** : les outils sont numérotés 1→6 dans l'ordre d'utilisation pour une
attaque WPA. L'utilisateur suit les étapes dans l'ordre depuis la liste de la catégorie.

**Note adaptateur WiFi RTL8188EUS** (`rtl8xxxu` driver) : contrairement aux chipsets Atheros,
ce driver n'ajoute **pas** le suffixe `mon` à l'interface. Après `airmon-ng start wlx...`,
l'interface garde le même nom `wlx40a5ef1333f3` en mode monitor.
`1. Airmon Start` exécute `airmon-ng check kill && airmon-ng start <iface>` pour tuer
NetworkManager/wpa_supplicant avant de démarrer le mode monitor.

### Pré-remplissage intelligent des paramètres

`tool.py` lit `settings.conf` à chaque ouverture d'outil et pré-remplit :

| Clé param | Depuis settings | Exemple |
| --- | --- | --- |
| `target` / `host` | `target_ip` | 192.168.1.1 |
| `iface` | `interface` | eth0 |
| `wordlist` | `wordlist` | /usr/share/wordlists/rockyou.txt |
| `output` | `output_dir` + nom outil | /tmp/nmap_quick |

Les champs vides affichent le hint en gris (ex: `192.168.1.0/24`) pour guider l'utilisateur.

### Vérification après upgrade

- `strings /usr/lib/arm-linux-gnueabihf/libSDL2-2.0.so.0 | grep kmsdrm` → vide = normal, utiliser Xorg
- `which Xorg && Xorg -version` — Xorg installé
- `systemctl is-enabled adnrpi-hackpad.service` → `enabled`
- `systemctl status adnrpi-hackpad.service` → `active (running)` + PID xinit + PID python3
- `which nmap arp-scan aircrack-ng hydra hashid gobuster` — outils pentest installés
- `ls /usr/share/wordlists/rockyou.txt /usr/share/dirb/wordlists/common.txt` — wordlists présentes
- Démarrage hardware : boot → premier démarrage firstboot → HackPad en ≤ 30 s après reboot

---

## Checklist for a new Armbian release

- [ ] Update `ARMBIAN_BRANCH` in `config-default.conf`
- [ ] Trigger `BuildSingleImage` on `adnrpi1-bookworm-server` as smoke test
- [ ] Check §6 — does Armbian's first-run mechanism still work the same way?
- [ ] Check §10 — do the DRM sysfs paths still exist?
- [ ] Check §11 — does the OPP overlay compile cleanly with the new kernel?
- [ ] Check §13 — are ROS GPG keys still valid?
- [ ] Check §15 — does Kivy install and start via xinit/Xorg? (bookworm-pentest build)
- [ ] Check §15 — are all pentesting tools still in APT repos for the new base OS?
- [ ] Re-enable jammy configs (§3) if the `no sunxi` BSP error is fixed upstream
- [ ] Update **Last reviewed against** at the top of this file
