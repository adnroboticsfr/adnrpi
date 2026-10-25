#!/bin/bash

# arguments: $RELEASE $LINUXFAMILY $BOARD $BUILD_DESKTOP
#
# This is the image customization script

# NOTE: It is copied to /tmp directory inside the image
# and executed there inside chroot environment
# so don't reference any files that are not already installed

# NOTE: If you want to transfer files between chroot and host
# userpatches/overlay directory on host is bind-mounted to /tmp/overlay in chroot
# The sd card's root path is accessible via $SDCARD variable.

# shellcheck enable=requires-variable-braces
# shellcheck disable=SC2034

RELEASE=$1
LINUXFAMILY=$2
BOARD=$3
BUILD_DESKTOP=$4

Main() {
    # Install dwarves (provides pahole) on Bullseye where pahole is not a standalone package
    if [[ "${RELEASE}" == "bullseye" ]]; then
        echo "Installing dwarves (pahole) for Bullseye ..."
        apt-get update && apt-get install -y dwarves
        echo "Installing dwarves (pahole) for Bullseye ... [DONE]"
    fi

    installFirstBootConfig

    case "${BOARD}" in
        adnrpi1)
            installADNRPiPadDetection
            installUsbGadgetNet
            disableSimpledrm
            forceUniversalVideoMode
            installOverclockControl
            if [[ "${BUILD_DESKTOP}" = "yes" ]]; then
                installRotationScript
                patchLightdm
                copyOnboardConf
                patchOnboardAutostart
                installScreensaverSetup
                case "${RELEASE}" in
                    trixie|forky|sid) installChromiumFlags ;;
                esac
            fi
            installCH57xTouchscreen
            installScreenSleep
            installIRSupport
            # ADNRPI_ROS n'est pas transmis au chroot — détection via marqueur
            if [[ "${ADNRPI_ROS}" == "ros2" ]] || [[ -f /tmp/overlay/.adnrpi-ros2 ]]; then
                case "${RELEASE}" in
                    noble) installROS2Jazzy ;;
                    *)     installROS2Humble ;;
                esac
            elif [[ "${ADNRPI_ROS}" == "ros1" ]] || [[ -f /tmp/overlay/.adnrpi-ros1 ]]; then
                installROS1Noetic
            fi
            # ADNRPI_PENTEST n'est pas transmis au chroot par Armbian (seuls
            # RELEASE/LINUXFAMILY/BOARD/BUILD_DESKTOP sont passés en args).
            # action.yml crée /tmp/overlay/.adnrpi-pentest avant le build.
            if [[ "${ADNRPI_PENTEST}" == "yes" ]] || [[ -f /tmp/overlay/.adnrpi-pentest ]]; then
                installPentestTools
                installHackPad
            fi
            ;;
    esac
}

installADNRPiPadDetection() {
    # The ADNRPi Pad is a ADNRPi One fitted with a 4.3" 800x480 HDMI touchscreen
    # mounted upside-down. Rotation is decided at runtime by detecting that
    # screen (resolution + touchscreen), so a single image works on both a
    # bare ADNRPi One (normal monitor) and a ADNRPi Pad.
    echo "Install ADNRPi Pad screen detection + console rotation ..."

    # kbd provides setfont; console-setup-linux provides Terminus and other
    # large PSF fonts used by adnrpipad-console-rotate.sh for the 4.3" panel.
    apt-get install -y --no-install-recommends kbd console-setup-linux

    cp -v /tmp/overlay/adnrpipad-detect.sh /usr/local/bin/adnrpipad-detect.sh
    chmod 755 /usr/local/bin/adnrpipad-detect.sh

    cp -v /tmp/overlay/adnrpipad-console-rotate.sh /usr/local/bin/adnrpipad-console-rotate.sh
    chmod 755 /usr/local/bin/adnrpipad-console-rotate.sh

    cp -v /tmp/overlay/adnrpipad-console-rotate.service /etc/systemd/system/adnrpipad-console-rotate.service
    chmod 644 /etc/systemd/system/adnrpipad-console-rotate.service
    systemctl enable adnrpipad-console-rotate.service

    # Re-apply large font at each TTY login when pad is connected
    cp -v /tmp/overlay/adnrpi-pad-font.sh /etc/profile.d/adnrpi-pad-font.sh
    chmod 644 /etc/profile.d/adnrpi-pad-font.sh

    # Drop-in: re-apply large font AFTER every systemd-vconsole-setup run.
    # This ensures our large font survives no matter how many times
    # vconsole-setup re-triggers (udev, keyboard hotplug, setupcon, etc.).
    cp -v /tmp/overlay/adnrpipad-apply-font.sh /usr/local/bin/adnrpipad-apply-font.sh
    chmod 755 /usr/local/bin/adnrpipad-apply-font.sh
    mkdir -p /etc/systemd/system/systemd-vconsole-setup.service.d
    cat > /etc/systemd/system/systemd-vconsole-setup.service.d/adnrpi-font.conf << 'EOF'
[Service]
ExecStartPost=-/usr/local/bin/adnrpipad-apply-font.sh
EOF
    chmod 644 /etc/systemd/system/systemd-vconsole-setup.service.d/adnrpi-font.conf

    # Manual display-mode switcher (pad ↔ hdmi) — edits armbianEnv.txt + reboots
    cp -v /tmp/overlay/adnrpi-display-mode /usr/local/bin/adnrpi-display-mode
    chmod 755 /usr/local/bin/adnrpi-display-mode

    echo "Install ADNRPi Pad screen detection + console rotation ... [DONE]"
}

disableSimpledrm() {
    # U-Boot hands the kernel a simple-framebuffer node, and simpledrm binds to
    # it alongside the native sun4i-drm driver. Both framebuffers then exist and
    # the console can end up drawn into the one that is no longer scanned out,
    # leaving a black screen after boot (verified on hardware). sun4i-drm always
    # drives this board, so the fallback driver is not needed.
    # Blocked on the kernel command line rather than through modprobe.d alone:
    # updating the initramfs fails on this FAT boot partition (no symlinks), so
    # a modprobe.d rule may never reach early boot.
    echo "Disable simpledrm (conflicts with sun4i-drm) ..."
    echo "blacklist simpledrm" > /etc/modprobe.d/adnrpi-no-simpledrm.conf
    local bootcfg="/boot/armbianEnv.txt"
    if grep -q "^extraargs=" "${bootcfg}" 2>/dev/null; then
        sed -i "s|^extraargs=\(.*\)|extraargs=\1 module_blacklist=simpledrm|" "${bootcfg}"
    else
        echo "extraargs=module_blacklist=simpledrm" >> "${bootcfg}"
    fi
    grep "^extraargs=" "${bootcfg}"
    echo "Disable simpledrm ... [DONE]"
}

forceUniversalVideoMode() {
    # The H3 tops out at 4K@30 (HDMI 1.4): letting the kernel negotiate with a
    # 4K UHD screen ends badly (unsupported 4K@60 preferred mode, or a 4K@30
    # framebuffer the Mali-400 cannot drive). Forcing 1280x720@60 guarantees a
    # picture on every HDMI screen at boot.
    # adnrpipad-console-rotate.service then switches to 800x480 at runtime when
    # the ADNRPi Pad is detected, without needing a reboot.
    echo "Force 720p video mode (safe default for all HDMI screens) ..."
    local bootcfg="/boot/armbianEnv.txt"
    if grep -q "^extraargs=" "${bootcfg}" 2>/dev/null; then
        sed -i "s|^extraargs=\(.*\)|extraargs=\1 video=HDMI-A-1:1280x720@60|" "${bootcfg}"
    else
        echo "extraargs=video=HDMI-A-1:1280x720@60" >> "${bootcfg}"
    fi
    grep "^extraargs=" "${bootcfg}"
    echo "Force 720p video mode ... [DONE]"
}

installOverclockControl() {
    # The 1368 MHz OPP is no longer force-enabled in the kernel patches:
    # with Armbian's current voltage tables the frequency hopping during
    # boot hangs boards right after "Reached target Paths." (verified on
    # hardware; the same image boots with cpufreq disabled). Default is
    # now the stock table — max 1296 MHz, adaptive governor — and
    # "adnrpi-oc on" opts in to 1368 MHz at the ADNRPi-validated 1.40 V
    # with the performance governor (no frequency hopping).
    echo "Install overclock control (adnrpi-oc) ..."
    apt-get install -y --no-install-recommends device-tree-compiler
    mkdir -p /boot/overlay-user
    dtc -@ -I dts -O dtb -o /boot/overlay-user/opp1368.dtbo /tmp/overlay/opp1368.dts
    cp -v /tmp/overlay/adnrpi-oc /usr/local/bin/adnrpi-oc
    chmod 755 /usr/local/bin/adnrpi-oc
    echo "Install overclock control ... [DONE]"
}

installCH57xTouchscreen() {
    # The YUMI 4.3" panel uses a CH57x (VID=1a86, PID=e5e3) as an I2C→USB HID
    # bridge for the capacitive touchscreen. Without this udev rule libinput
    # never sees ID_INPUT_TOUCHSCREEN=1 and ignores absolute coordinates.
    # The rule also disables USB autosuspend to prevent disconnect spikes when
    # another USB cable is plugged in (inrush current on the 5V rail).
    echo "Install CH57x touchscreen udev rule ..."
    mkdir -p /etc/udev/rules.d
    cp -v /tmp/overlay/70-ch57x-touch.rules /etc/udev/rules.d/70-ch57x-touch.rules
    chmod 644 /etc/udev/rules.d/70-ch57x-touch.rules
    # USB_QUIRK_RESET (0x0400): force a clean USB reset on each reconnect instead
    # of reusing potentially corrupted device state after a power-rail glitch.
    echo 'options usbcore quirks=1a86:e5e3:0x0400' \
        > /etc/modprobe.d/adnrpi-ch57x-quirk.conf
    echo "Install CH57x touchscreen udev rule ... [DONE]"
}

installScreenSleep() {
    # adnrpi-screen on/off/toggle/status — screen sleep without DPMS.
    # The YUMI 4.3" panel has no DPMS; we blank the framebuffer and suspend
    # the CH57x USB device (which cuts the backlight on most panels that draw
    # their 5V from the same USB bus).
    echo "Install adnrpi-screen (screen sleep/wake) ..."
    cp -v /tmp/overlay/adnrpi-screen /usr/local/bin/adnrpi-screen
    chmod 755 /usr/local/bin/adnrpi-screen
    echo "Install adnrpi-screen ... [DONE]"
}

installIRSupport() {
    # The H3 hardware IR receiver (GPIOL11 = r_ir_rx_pin, enabled in DTS) needs
    # the NEC protocol decoder loaded at boot. ir-keytable handles this; we
    # install a oneshot systemd unit that runs ir-keytable -p NEC on /dev/rc0.
    echo "Install IR receiver support (NEC protocol) ..."
    apt-get install -y --no-install-recommends ir-keytable
    cp -v /tmp/overlay/adnrpi-ir.service /etc/systemd/system/adnrpi-ir.service
    chmod 644 /etc/systemd/system/adnrpi-ir.service
    systemctl enable adnrpi-ir.service
    echo "Install IR receiver support ... [DONE]"
}

installUsbGadgetNet() {
    # USB0 (OTG) runs as a network gadget (g_ether, enabled in the device
    # tree): plugging the OTG port into a computer gives SSH access at
    # 172.22.1.1 without Ethernet.
    echo "Install USB gadget network ..."
    cp -v /tmp/overlay/usb-gadget-net.sh /usr/local/bin/usb-gadget-net.sh
    chmod 755 /usr/local/bin/usb-gadget-net.sh
    cp -v /tmp/overlay/usb-gadget-net.service /etc/systemd/system/usb-gadget-net.service
    chmod 644 /etc/systemd/system/usb-gadget-net.service
    systemctl enable usb-gadget-net.service
    echo "Install USB gadget network ... [DONE]"
}

installRotationScript() {
    # Install xrandr-based rotation script (gated on ADNRPi Pad screen detection)
    echo "Installing ADNRPi Pad rotation script ..."

    # Install the rotation script
    local scriptSrc="/tmp/overlay/adnrpipad-rotate.sh"
    local scriptDest="/usr/local/bin/adnrpipad-rotate.sh"
    if [[ -f "${scriptSrc}" ]]; then
        cp -v "${scriptSrc}" "${scriptDest}"
        chmod 755 "${scriptDest}"
        echo "Rotation script installed to ${scriptDest}"
    fi

    # Install autostart desktop file
    local desktopSrc="/tmp/overlay/adnrpipad-rotate.desktop"
    local desktopDest="/etc/xdg/autostart/adnrpipad-rotate.desktop"
    if [[ -f "${desktopSrc}" ]]; then
        mkdir -p /etc/xdg/autostart
        cp -v "${desktopSrc}" "${desktopDest}"
        chmod 644 "${desktopDest}"
        echo "Rotation autostart installed"
    fi

    # Also add to LightDM session setup for login screen rotation
    local lightdmScript="/etc/lightdm/lightdm.conf.d/50-adnrpipad-rotate.conf"
    mkdir -p /etc/lightdm/lightdm.conf.d
    cat > "${lightdmScript}" << 'EOF'
[Seat:*]
display-setup-script=/usr/local/bin/adnrpipad-rotate.sh
EOF
    chmod 644 "${lightdmScript}"
    echo "LightDM rotation configured"

    echo "ADNRPi Pad rotation script ... [DONE]"
}

patchLightdm() {
    local conf="/etc/lightdm/lightdm.conf.d/12-onboard.conf"
    echo "Enable OnScreen Keyboard in Lightdm ..."
    echo "onscreen-keyboard = true" | tee "${conf}"
    echo "Enable OnScreen Keyboard in Lightdm ... [DONE]"
}

copyOnboardConf() {
    echo "Copy onboard default configuration ..."
    mkdir -p /etc/onboard
    cp -v /tmp/overlay/onboard-defaults.conf /etc/onboard/
    echo "Copy onboard default configuration ... [DONE]"
}

patchOnboardAutostart() {
    local conf="/etc/xdg/autostart/onboard-autostart.desktop"
    echo "Patch Onboard Autostart file ..."
    if [[ -f "${conf}" ]]; then
        sed -i '/OnlyShowIn/s/^/# /' "${conf}"
        # Start the on-screen keyboard only when the ADNRPi Pad touchscreen is present
        sed -i 's|^Exec=.*|Exec=sh -c "/usr/local/bin/adnrpipad-detect.sh \&\& exec onboard"|' "${conf}"
    else
        echo "WARNING: ${conf} not found (is the onboard package installed?)"
    fi
    echo "Patch Onboard Autostart file ... [DONE]"
}

installScreensaverSetup() {
    local src="/tmp/overlay/skel-xscreensaver"
    local dest="/etc/skel/.xscreensaver"
    echo "Install screensaver configuration ..."
    \cp -fv "${src}" "${dest}"
    echo "DEBUG:"
    ls -al "$(dirname "${dest}")"
    echo "Install screensaver configuration ... [DONE]"
}


installChromiumFlags() {
    # Chromium's GPU process cannot create a usable GL context on the
    # Mali400 (lima is GLES2-only): the viz process dies and windows
    # render white. LIBGL_ALWAYS_SOFTWARE=1 hands it a Mesa software
    # context instead (validated on hardware). Also drop Armbian's
    # AcceleratedVideoDecoder flags meant for SBCs with an exposed VPU
    # (the H3 has none here). Noble is not affected: its xtradeb
    # chromium renders fine and keeps its stock configuration.
    echo "Install Chromium software-GL environment ..."
    mkdir -p /etc/chromium.d
    cp -v /tmp/overlay/adnrpi-mali-softgl /etc/chromium.d/adnrpi-mali-softgl
    rm -f /etc/chromium.d/armbian-flags
    echo "Install Chromium software-GL environment ... [DONE]"
}

installROS2() {
    local distro="$1"    # humble or jazzy
    local release="$2"   # jammy or noble
    local arch
    arch="$(dpkg --print-architecture)"
    echo "Installing ROS2 ${distro^} (${arch}, Ubuntu ${release}) ..."
    apt-get install -y curl gnupg lsb-release

    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc \
        -o /tmp/ros2.asc
    gpg --batch --no-tty --dearmor < /tmp/ros2.asc \
        > /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=${arch} signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu ${release} main" \
        > /etc/apt/sources.list.d/ros2.list
    apt-get update

    # ── armhf: no binary ROS2 packages exist — install build tools + helper ──
    # ROS2 only publishes amd64/arm64 binaries. On armhf the user must build
    # from source. We pre-install all build dependencies and drop a script
    # /usr/local/bin/adnrpi-ros2-build that automates the source build.
    if [[ "${arch}" == "armhf" ]]; then
        echo "[armhf] No ROS2 binary packages for armhf — installing build deps + adnrpi-ros2-build script"
        apt-get install -y \
            python3-colcon-common-extensions \
            python3-rosdep \
            python3-argcomplete \
            python3-pip \
            cmake \
            build-essential \
            git \
            wget \
            libbullet-dev \
            python3-flake8 \
            python3-pytest-cov \
            python3-setuptools \
            libpython3-dev || true

        cat > /usr/local/bin/adnrpi-ros2-build << BUILDSCRIPT
#!/bin/bash
# adnrpi-ros2-build — build ROS2 ${distro^} from source on armhf
# Run once after first boot: sudo adnrpi-ros2-build
# This takes 6-10 hours on the SmartPi H3.
set -e
DISTRO="${distro}"
INSTALL_DIR="/opt/ros/\${DISTRO}"
SRC_DIR="/opt/ros2_src"

echo "=== ROS2 \${DISTRO^} source build for armhf ==="
echo "    This will take 6-10 hours. Run in a screen session:"
echo "    screen -S ros2build"
echo ""
read -r -p "Continue? [y/N] " yn
[[ "\${yn,,}" =~ ^y ]] || exit 0

apt-get update
apt-get install -y python3-rosdep python3-colcon-common-extensions \
    python3-vcstool cmake build-essential git wget \
    libbullet-dev libpython3-dev python3-pip

rosdep init 2>/dev/null || true
rosdep update

mkdir -p "\${SRC_DIR}/src"
cd "\${SRC_DIR}"
wget -q "https://raw.githubusercontent.com/ros2/ros2/\${DISTRO}/ros2.repos"
vcs import src < ros2.repos

rosdep install --from-paths src --ignore-src -y \
    --skip-keys "fastcdr rti-connext-dds-6.0.1 urdfdom_headers" || true

mkdir -p "\${INSTALL_DIR}"
colcon build \
    --symlink-install \
    --install-base "\${INSTALL_DIR}" \
    --cmake-args -DCMAKE_BUILD_TYPE=Release \
    --packages-skip-regex '.*rviz.*' '.*rqt.*' '.*gui.*' \
    2>&1 | tee /var/log/ros2-build.log

echo "source \${INSTALL_DIR}/setup.bash" >> /root/.bashrc
grep -q "source \${INSTALL_DIR}/setup.bash" /etc/skel/.bashrc || \
    echo "source \${INSTALL_DIR}/setup.bash" >> /etc/skel/.bashrc

echo "=== ROS2 \${DISTRO^} build complete ==="
echo "    Log: /var/log/ros2-build.log"
echo "    Re-login or: source \${INSTALL_DIR}/setup.bash"
BUILDSCRIPT
        chmod 755 /usr/local/bin/adnrpi-ros2-build

        # MOTD notice
        cat > /etc/update-motd.d/50-ros2-build-notice << 'MOTD'
#!/bin/sh
if [ ! -f /opt/ros/*/setup.bash ]; then
    echo ""
    echo "  ROS2 not yet installed — binary packages unavailable for armhf."
    echo "  To build from source (~6-10h): sudo adnrpi-ros2-build"
    echo ""
fi
MOTD
        chmod 755 /etc/update-motd.d/50-ros2-build-notice

        echo "[armhf] Build script installed at /usr/local/bin/adnrpi-ros2-build"
        echo "Installing ROS2 ${distro^} (armhf — source build required) ... [DONE]"
        return
    fi

    # ── amd64 / arm64 : binary install ───────────────────────────────────────
    apt-get install -y \
        "ros-${distro}-ros-base" \
        python3-colcon-common-extensions \
        python3-rosdep \
        python3-argcomplete \
        "ros-${distro}-rmw-cyclonedds-cpp" \
        "ros-${distro}-diagnostic-updater" \
        "ros-${distro}-tf2" \
        "ros-${distro}-tf2-ros" \
        "ros-${distro}-tf2-tools" \
        "ros-${distro}-geometry-msgs" \
        "ros-${distro}-sensor-msgs" \
        "ros-${distro}-nav-msgs" \
        "ros-${distro}-std-msgs" \
        "ros-${distro}-std-srvs" \
        "ros-${distro}-image-transport" \
        "ros-${distro}-compressed-image-transport" \
        "ros-${distro}-joy" \
        "ros-${distro}-teleop-twist-joy" \
        "ros-${distro}-teleop-twist-keyboard" \
        "ros-${distro}-serial-driver" \
        "ros-${distro}-rosbridge-suite" \
        "ros-${distro}-robot-state-publisher" \
        "ros-${distro}-joint-state-publisher" \
        "ros-${distro}-xacro" || true

    # ── Desktop tools ─────────────────────────────────────────────────────────
    if [[ "${ADNRPI_ROS_DESKTOP}" == "yes" ]] || [[ -f /tmp/overlay/.adnrpi-ros-desktop ]]; then
        echo "Installing ROS2 desktop tools ..."
        apt-get install -y \
            "ros-${distro}-rqt" \
            "ros-${distro}-rqt-graph" \
            "ros-${distro}-rqt-topic" \
            "ros-${distro}-rqt-action" \
            "ros-${distro}-rqt-service-caller" \
            "ros-${distro}-rqt-param" \
            "ros-${distro}-rqt-console" \
            "ros-${distro}-rqt-plot" \
            "ros-${distro}-rviz2" \
            "ros-${distro}-nav2-bringup" \
            "ros-${distro}-nav2-map-server" \
            "ros-${distro}-nav2-lifecycle-manager" \
            "ros-${distro}-nav2-controller" \
            "ros-${distro}-nav2-planner" \
            "ros-${distro}-slam-toolbox" \
            "ros-${distro}-cartographer-ros" \
            "ros-${distro}-laser-geometry" \
            "ros-${distro}-pcl-ros" \
            "ros-${distro}-moveit-ros-planning-interface" || true
        echo "Installing ROS2 desktop tools ... [DONE]"
    fi

    rosdep init || true
    rosdep update || true

    cp -v /tmp/overlay/adnrpi-ros-config /usr/local/bin/adnrpi-ros-config
    chmod 755 /usr/local/bin/adnrpi-ros-config
    mkdir -p /etc/ros

    echo "source /opt/ros/${distro}/setup.bash" >> /etc/skel/.bashrc
    grep -q "source /opt/ros/${distro}/setup.bash" /root/.bashrc || \
        echo "source /opt/ros/${distro}/setup.bash" >> /root/.bashrc

    echo "--- ROS2 install check ---"
    /opt/ros/${distro}/bin/ros2 --version 2>/dev/null || \
        echo "[WARN] ros2 binary not found in /opt/ros/${distro}/bin"
    echo "--------------------------"
    echo "Installing ROS2 ${distro^} ... [DONE]"
}

installROS2Humble() { installROS2 "humble" "jammy"; }
installROS2Jazzy()  { installROS2 "jazzy"  "noble"; }

installROS1Noetic() {
    echo "Installing ROS1 Noetic (armhf, Ubuntu focal) ..."
    apt-get install -y curl gnupg lsb-release

    curl -sSL 'http://keyserver.ubuntu.com/pks/lookup?op=get&search=0xC1CF6E31E6BADE8868B172B4F42ED6FBAB17C654' \
        | apt-key add -
    echo "deb http://packages.ros.org/ros/ubuntu focal main" \
        > /etc/apt/sources.list.d/ros-latest.list

    apt-get update

    apt-get install -y \
        ros-noetic-ros-base \
        python3-rosdep \
        python3-rosinstall \
        python3-rosinstall-generator \
        python3-wstool \
        build-essential \
        ros-noetic-geometry-msgs \
        ros-noetic-sensor-msgs \
        ros-noetic-nav-msgs \
        ros-noetic-std-msgs \
        ros-noetic-std-srvs \
        ros-noetic-tf \
        ros-noetic-tf2 \
        ros-noetic-tf2-ros \
        ros-noetic-tf2-tools \
        ros-noetic-image-transport \
        ros-noetic-compressed-image-transport \
        ros-noetic-joy \
        ros-noetic-teleop-twist-joy \
        ros-noetic-teleop-twist-keyboard \
        ros-noetic-rosserial \
        ros-noetic-rosserial-arduino \
        ros-noetic-rosbridge-suite \
        ros-noetic-robot-state-publisher \
        ros-noetic-joint-state-publisher \
        ros-noetic-xacro \
        ros-noetic-map-server \
        ros-noetic-move-base-msgs || true

    rosdep init || true
    rosdep update || true

    # Install adnrpi-ros-config tool
    cp -v /tmp/overlay/adnrpi-ros-config /usr/local/bin/adnrpi-ros-config
    chmod 755 /usr/local/bin/adnrpi-ros-config
    mkdir -p /etc/ros

    echo "source /opt/ros/noetic/setup.bash" >> /etc/skel/.bashrc

    echo "Installing ROS1 Noetic ... [DONE]"
}

installFirstBootConfig() {
    echo "Installing ADNRPi first-boot configuration system ..."

    # Install the config template to /boot
    local configSrc="/tmp/overlay/adnrpi-config.txt"
    local configDest="/boot/adnrpi-config.txt"
    if [[ -f "${configSrc}" ]]; then
        cp -v "${configSrc}" "${configDest}"
        # Set default hostname in config based on board name
        sed -i "s/^HOSTNAME=.*/HOSTNAME=${BOARD}/" "${configDest}"
        chmod 644 "${configDest}"
        echo "Config template installed to ${configDest} with HOSTNAME=${BOARD}"
    fi

    # Install the first-boot script
    local scriptSrc="/tmp/overlay/adnrpi-firstboot.sh"
    local scriptDest="/usr/local/bin/adnrpi-firstboot.sh"
    if [[ -f "${scriptSrc}" ]]; then
        cp -v "${scriptSrc}" "${scriptDest}"
        chmod 755 "${scriptDest}"
        echo "First-boot script installed to ${scriptDest}"
    fi

    # Install the systemd service
    local serviceSrc="/tmp/overlay/adnrpi-firstboot.service"
    local serviceDest="/etc/systemd/system/adnrpi-firstboot.service"
    if [[ -f "${serviceSrc}" ]]; then
        cp -v "${serviceSrc}" "${serviceDest}"
        chmod 644 "${serviceDest}"
        # Enable the service
        systemctl enable adnrpi-firstboot.service
        echo "First-boot service installed and enabled"
    fi

    # Install the interactive setup wizard
    local setupSrc="/tmp/overlay/adnrpi-setup"
    local setupDest="/usr/local/bin/adnrpi-setup"
    if [[ -f "${setupSrc}" ]]; then
        cp -v "${setupSrc}" "${setupDest}"
        chmod 755 "${setupDest}"
        echo "Setup wizard installed to ${setupDest}"
    fi

    # Install the profile.d trigger (auto-launch on login until setup is done)
    local profileSrc="/tmp/overlay/adnrpi-setup-profile.sh"
    local profileDest="/etc/profile.d/adnrpi-setup.sh"
    if [[ -f "${profileSrc}" ]]; then
        cp -v "${profileSrc}" "${profileDest}"
        chmod 644 "${profileDest}"
        echo "Setup profile trigger installed to ${profileDest}"
    fi

    # Disable Armbian's built-in first-run wizard.
    # It asks for the same things (root password, user, locale, timezone) as
    # adnrpi-setup, so running both would confuse the user.
    # Removing the flag file is enough — the profile.d script checks for it
    # before launching the wizard.
    rm -f /root/.not_logged_in_yet
    chmod -x /etc/profile.d/armbian-check-first-run.sh 2>/dev/null || true

    # Masquer console-setup.service : sur H3 le driver VT n'est pas prêt au moment
    # où ce service s'exécute → il bloque et retarde ou empêche getty@tty1 de démarrer.
    # La configuration clavier/police est appliquée par adnrpi-setup via setupcon.
    systemctl mask console-setup.service 2>/dev/null || true

    # Plymouth : seul plymouth-quit-wait bloque sur H3 (attend DRM/KMS indéfiniment).
    # On masque uniquement ce service — les autres restent actifs pour voir les
    # messages de boot en mode console.
    systemctl mask plymouth-quit-wait.service 2>/dev/null || true
    # Retirer 'splash' du cmdline si Armbian l'a ajouté (splash active l'écran Plymouth
    # graphique qui lui aussi peut bloquer sur H3 sans GPU DRM)
    sed -i 's/ *splash//' /boot/armbianEnv.txt 2>/dev/null || true

    echo "ADNRPi first-boot configuration system ... [DONE]"
}

installPentestTools() {
    echo "Installing pentest tools ..."

    # Packages verified on Debian Bookworm ARM (Allwinner H3)
    # Removed (not in Debian repos): wordlists, kismet, reaver, bully, whatweb, wfuzz,
    #   hashcat, medusa, fierce, theharvester, maltego, recon-ng, wireshark,
    #   ettercap-text-only, responder, metasploit-framework, exploitdb, beef-xss

    apt-get update

    # Network scanning
    apt-get install -y --no-install-recommends \
        nmap masscan netdiscover arp-scan \
        net-tools iputils-ping traceroute whois dnsutils

    # WiFi (aircrack-ng suite — mode monitor via mac80211, no extra driver needed)
    apt-get install -y --no-install-recommends \
        aircrack-ng iw rfkill

    # Web
    apt-get install -y --no-install-recommends \
        nikto sqlmap gobuster dirb curl wget

    # Passwords & hashes
    apt-get install -y --no-install-recommends \
        john hydra crunch smbclient

    # Recon
    apt-get install -y --no-install-recommends \
        dnsrecon

    # Capture & analysis
    apt-get install -y --no-install-recommends \
        tcpdump tshark ngrep netcat-traditional socat

    # Kivy clipboard dependency
    apt-get install -y --no-install-recommends xsel

    # Utilities
    apt-get install -y --no-install-recommends \
        python3 python3-pip git vim tmux screen openssh-server ufw

    # hashid — pip only (not in Debian repos)
    # --break-system-packages requis sur Debian 12 (PEP 668)
    pip3 install hashid --break-system-packages

    # Wordlists — Debian Bookworm has no 'wordlists' package (Kali-specific)
    mkdir -p /usr/share/wordlists
    ln -sf /usr/share/dirb/wordlists/common.txt /usr/share/wordlists/common.txt
    if [ ! -f /usr/share/wordlists/rockyou.txt ]; then
        curl -L --max-time 120 \
            "https://github.com/danielmiessler/SecLists/raw/master/Passwords/Leaked-Databases/rockyou-75.txt" \
            -o /usr/share/wordlists/rockyou.txt || \
            echo "WARNING: rockyou.txt download failed — add manually"
    fi

    echo "Installing pentest tools ... [DONE]"
}

installHackPad() {
    echo "Installing HackPad (Kivy touchscreen interface) ..."

    # ── Kivy + SDL2 runtime (X11 backend — kmsdrm absent de Debian Bookworm ARM) ──
    # python3-kivymd : absent des repos Debian — non utilisé
    # libsdl2-*-dev  : headers build-time — pas nécessaires à l'exécution
    apt-get install -y --no-install-recommends \
        python3-kivy \
        libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
        libgles2 libgbm1 libegl-mesa0 libdrm2 libmtdev1

    # ── Dépendances Scope ─────────────────────────────────────────────────────────
    # numpy : import global dans scope_screen.py et audio_capture.py — obligatoire
    # python3-serial : liaison STM32/Pico via /dev/ttyACM0
    # sounddevice + smbus2 : imports lazy (pas de crash si absent, mais fonctions désactivées)
    apt-get install -y --no-install-recommends python3-numpy python3-serial
    pip3 install --break-system-packages sounddevice smbus2 2>/dev/null || \
        pip3 install sounddevice smbus2 2>/dev/null || true

    # ── Xorg (backend SDL2 fonctionnel sur Bookworm ARM via modesetting + Lima) ──
    apt-get install -y --no-install-recommends \
        xserver-xorg-core xserver-xorg-video-fbdev \
        xserver-xorg-input-evdev xserver-xorg-input-libinput \
        xinit x11-xserver-utils

    # ── Polices + clipboard Kivy ──────────────────────────────────────────────────
    apt-get install -y --no-install-recommends \
        fonts-noto fonts-noto-color-emoji fonts-dejavu-core \
        xsel

    # ── XFCE (mode desktop optionnel) ────────────────────────────────────────────
    apt-get install -y --no-install-recommends \
        xfce4 xfce4-terminal lightdm

    systemctl disable lightdm 2>/dev/null || true

    # ── Xorg config — force 800x480, évite que modesetting choisisse 1280x720 ────
    mkdir -p /etc/X11/xorg.conf.d
    cp -v /tmp/overlay/99-adnrpi-hackpad.conf /etc/X11/xorg.conf.d/

    # ── Application HackPad ───────────────────────────────────────────────────────
    local appdir="/opt/adnrpi-hackpad"
    mkdir -p "${appdir}"
    cp -rv /tmp/overlay/hackpad/* "${appdir}/"
    chmod +x "${appdir}/main.py"
    chmod +x "${appdir}/launch.sh"
    chmod +x "${appdir}/adnrpi-switch-mode"

    # Global launcher
    ln -sf "${appdir}/adnrpi-switch-mode" /usr/local/bin/adnrpi-switch-mode
    chmod +x "${appdir}/adnrpi-vnc"
    ln -sf "${appdir}/adnrpi-vnc" /usr/local/bin/adnrpi-vnc

    # ── Service systemd — xinit :0 vt1 → Xorg → HackPad ─────────────────────────
    cp -v /tmp/overlay/adnrpi-hackpad.service /etc/systemd/system/
    chmod 644 /etc/systemd/system/adnrpi-hackpad.service
    systemctl enable adnrpi-hackpad.service

    # ── Application Scope ─────────────────────────────────────────────────────────
    local scopedir="/opt/adnrpi-scope"
    mkdir -p "${scopedir}"
    cp -rv /tmp/overlay/scope/* "${scopedir}/"
    chmod +x "${scopedir}/launch.sh"
    cp -v /tmp/overlay/adnrpi-scope.service /etc/systemd/system/
    chmod 644 /etc/systemd/system/adnrpi-scope.service
    # Pas activé ici — activé par adnrpi-setup au choix de l'utilisateur

    # ── Application Launcher ──────────────────────────────────────────────────────
    local launcherdir="/opt/adnrpi-launcher"
    mkdir -p "${launcherdir}"
    cp -rv /tmp/overlay/launcher/* "${launcherdir}/"
    chmod +x "${launcherdir}/run.sh"
    cp -v /tmp/overlay/adnrpi-launcher.service /etc/systemd/system/
    chmod 644 /etc/systemd/system/adnrpi-launcher.service
    # Pas activé ici — activé par adnrpi-setup au choix de l'utilisateur

    # ── Config par défaut (pré-remplie dans les outils) ──────────────────────────
    mkdir -p /etc/adnrpi-hackpad
    cat > /etc/adnrpi-hackpad/settings.conf <<'CONF'
target_ip=
interface=eth0
wordlist=/usr/share/wordlists/rockyou.txt
output_dir=/tmp
CONF

    # ── Config Kivy pré-générée — évite le "upgrading config" au premier démarrage ──
    # Sans ce fichier, Kivy v2.1 réécrit sa config au premier lancement et peut
    # provoquer un resize de fenêtre si la résolution détectée diffère du défaut.
    mkdir -p /root/.kivy/logs
    cat > /root/.kivy/config.ini <<'KIVYCONF'
[kivy]
log_level = warning
log_enable = 1
log_dir = /root/.kivy/logs
log_name = kivy_%y-%m-%d_%_.txt
log_maxfiles = 5
keyboard_mode =

[graphics]
width = 800
height = 480
fullscreen = 0
borderless = 1
position = custom
left = 0
top = 0
minimum_width = 0
minimum_height = 0
show_cursor = 1

[input]
mouse = mouse,disable_multitouch

[postproc]
double_tap_time = 250
double_tap_distance = 20

[widgets]
scroll_timeout = 55
scroll_distance = 10
KIVYCONF

    # ── Raccourci desktop XFCE ───────────────────────────────────────────────────
    mkdir -p /usr/share/applications
    cp -v /tmp/overlay/adnrpi-hackpad.desktop /usr/share/applications/
    chmod 644 /usr/share/applications/adnrpi-hackpad.desktop

    # ── MOTD SSH — logo + IP + statut HackPad ────────────────────────────────────
    cp -v /tmp/overlay/20-adnrpi-pentest /etc/update-motd.d/
    chmod 755 /etc/update-motd.d/20-adnrpi-pentest

    # ── VNC (x11vnc) — activé/configuré depuis adnrpi-setup ou settings HackPad ──
    apt-get install -y --no-install-recommends x11vnc xinput
    cp -v /tmp/overlay/adnrpi-vnc.service /etc/systemd/system/
    chmod 644 /etc/systemd/system/adnrpi-vnc.service
    # Le service est installé mais pas activé — activé via adnrpi-setup ou Settings HackPad
    systemctl daemon-reload

    # ── Xorg InputClass libinput — tactile USB hotplug automatique ───────────────
    # libinput gère le hotplug des écrans tactiles USB sans redémarrer Xorg
    cat > /etc/X11/xorg.conf.d/99-adnrpi-touch.conf <<'TOUCHEOF'
Section "InputClass"
    Identifier "touchscreen"
    MatchIsTouchscreen "on"
    Driver "libinput"
    Option "Tapping" "on"
    Option "CalibrationMatrix" "1 0 0 0 1 0 0 0 1"
EndSection
TOUCHEOF
    chmod 644 /etc/X11/xorg.conf.d/99-adnrpi-touch.conf

    # ── Masquer le curseur HW sur tty1 (HackPad plein écran) ─────────────────────
    # quiet/loglevel=1 retiré pour que les messages de boot restent visibles.
    # vt.global_cursor_default=0 conservé : le cursor hardware clignote sur
    # l'interface Kivy et nuit à l'expérience utilisateur.
    if [ -f /boot/armbianEnv.txt ]; then
        if grep -q "^extraargs=" /boot/armbianEnv.txt; then
            if ! grep -q "vt.global_cursor_default" /boot/armbianEnv.txt; then
                sed -i 's/^extraargs=\(.*\)/extraargs=\1 vt.global_cursor_default=0/' \
                    /boot/armbianEnv.txt
            fi
        else
            echo "extraargs=vt.global_cursor_default=0" >> /boot/armbianEnv.txt
        fi
    fi

    # ── Wizard premier boot — service dédié sur tty1 ─────────────────────────────
    # adnrpi-wizard.service prend tty1 directement (StandardInput/Output=tty)
    # sans passer par getty ni profile.d — plus fiable sur H3 Armbian.
    cp -v /tmp/overlay/adnrpi-wizard.service /etc/systemd/system/
    cp -v /tmp/overlay/adnrpi-wizard-launcher.sh /usr/local/bin/
    chmod 755 /usr/local/bin/adnrpi-wizard-launcher.sh
    chmod 644 /etc/systemd/system/adnrpi-wizard.service
    systemctl enable adnrpi-wizard.service

    # ── getty@tty1 override — login shell après setup, hackpad prend le relais ──
    # Avant setup.conf : adnrpi-wizard.service prend tty1 (Conflicts= dans wizard.service)
    # Après setup.conf : hackpad.service prend vt1 (Conflicts= dans hackpad.service)
    mkdir -p /etc/systemd/system/getty@tty1.service.d
    cp -v /tmp/overlay/getty@tty1.service.d/hackpad.conf \
          /etc/systemd/system/getty@tty1.service.d/hackpad.conf
    chmod 644 /etc/systemd/system/getty@tty1.service.d/hackpad.conf
    systemctl daemon-reload

    # ── Codec audio H3 — active le micro embarqué ─────────────────────────────
    # Le .dtbo sun8i-h3-analog-codec est déjà fourni par Armbian.
    # Il suffit d'ajouter overlays=analog-codec dans armbianEnv.txt.
    if [ -f /boot/armbianEnv.txt ]; then
        if grep -q "^overlay_prefix=sun8i-h3" /boot/armbianEnv.txt; then
            if ! grep -q "analog-codec" /boot/armbianEnv.txt; then
                sed -i '/^overlay_prefix=sun8i-h3/a overlays=analog-codec' /boot/armbianEnv.txt
                echo "Codec audio H3 : overlay analog-codec ajouté"
            fi
        fi
    fi
    # Config ALSA : active Mic1 et le routage vers l'ADC (persiste via asound.state)
    # Les commandes amixer tournent dans le chroot, alsactl store génère /var/lib/alsa/asound.state
    amixer -c 0 cset numid=18 1 2>/dev/null   # Mic1 Capture Switch → on
    amixer -c 0 cset numid=8  3 2>/dev/null   # Mic1 Boost → 27 dB
    amixer -c 0 cset numid=9  7 2>/dev/null   # ADC Gain → max
    amixer -c 0 cset numid=15 1 2>/dev/null   # Mixer Capture Switch → on
    alsactl store 0 2>/dev/null && echo "ALSA Mic1 config sauvegardée" \
        || echo "WARN: alsactl store échoué (normal si pas de soundcard en chroot)"

    echo "Installing HackPad ... [DONE]"
}

Main "$@"
