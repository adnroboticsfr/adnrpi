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
            case "${ADNRPI_ROS}" in
                ros2)
                    case "${RELEASE}" in
                        noble) installROS2Jazzy ;;
                        *)     installROS2Humble ;;
                    esac
                    ;;
                ros1) installROS1Noetic ;;
            esac
            if [[ "${ADNRPI_PENTEST}" == "yes" ]]; then
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
    echo "Installing ROS2 ${distro^} (armhf, Ubuntu ${release}) ..."
    apt-get install -y curl gnupg lsb-release

    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc \
        | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu ${release} main" \
        > /etc/apt/sources.list.d/ros2.list

    apt-get update

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

    rosdep init || true
    rosdep update || true

    cp -v /tmp/overlay/adnrpi-ros-config /usr/local/bin/adnrpi-ros-config
    chmod 755 /usr/local/bin/adnrpi-ros-config
    mkdir -p /etc/ros

    echo "source /opt/ros/${distro}/setup.bash" >> /etc/skel/.bashrc

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

    echo "ADNRPi first-boot configuration system ... [DONE]"
}

installPentestTools() {
    echo "Installing pentest tools ..."

    apt-get update

    # Network scanning
    apt-get install -y --no-install-recommends \
        nmap masscan netdiscover arp-scan nbtscan \
        net-tools iputils-ping traceroute whois dnsutils

    # WiFi
    apt-get install -y --no-install-recommends \
        aircrack-ng kismet reaver bully hostapd iw rfkill

    # Web
    apt-get install -y --no-install-recommends \
        nikto sqlmap gobuster dirb curl wget \
        whatweb wfuzz

    # Passwords & hashes
    apt-get install -y --no-install-recommends \
        john hydra hashcat crunch wordlists \
        medusa

    # Recon & OSINT
    apt-get install -y --no-install-recommends \
        dnsrecon fierce theharvester maltego \
        recon-ng

    # Capture & analysis
    apt-get install -y --no-install-recommends \
        tcpdump tshark wireshark ngrep ettercap-text-only \
        netcat-openbsd socat responder

    # Exploitation
    apt-get install -y --no-install-recommends \
        metasploit-framework exploitdb \
        beef-xss

    # Utilities
    apt-get install -y --no-install-recommends \
        python3 python3-pip git vim tmux screen \
        openssh-server ufw

    echo "Installing pentest tools ... [DONE]"
}

installHackPad() {
    echo "Installing HackPad (Kivy touchscreen interface) ..."

    # Kivy dependencies
    apt-get install -y --no-install-recommends \
        python3-kivy python3-kivymd \
        libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
        libgles2 libgles2-mesa-dev \
        xfce4 xfce4-terminal lightdm \
        fonts-dejavu-core

    # Disable LightDM by default — server mode uses KMS/framebuffer
    systemctl disable lightdm 2>/dev/null || true

    # Install HackPad application
    local appdir="/opt/adnrpi-hackpad"
    mkdir -p "${appdir}"
    cp -rv /tmp/overlay/hackpad/* "${appdir}/"
    chmod +x "${appdir}/main.py"
    chmod +x "${appdir}/adnrpi-switch-mode"

    # Global launcher
    ln -sf "${appdir}/adnrpi-switch-mode" /usr/local/bin/adnrpi-switch-mode

    # Systemd service — auto-start HackPad on framebuffer at boot
    cp -v /tmp/overlay/adnrpi-hackpad.service /etc/systemd/system/
    chmod 644 /etc/systemd/system/adnrpi-hackpad.service
    systemctl enable adnrpi-hackpad.service

    # Desktop shortcut for XFCE mode
    mkdir -p /usr/share/applications
    cp -v /tmp/overlay/adnrpi-hackpad.desktop /usr/share/applications/
    chmod 644 /usr/share/applications/adnrpi-hackpad.desktop

    echo "Installing HackPad ... [DONE]"
}

Main "$@"
