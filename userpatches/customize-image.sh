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
                ros2) installROS2Humble ;;
                ros1) installROS1Noetic ;;
            esac
            ;;
    esac
}

installADNRPiPadDetection() {
    # The ADNRPi Pad is a ADNRPi One fitted with a 4.3" 800x480 HDMI touchscreen
    # mounted upside-down. Rotation is decided at runtime by detecting that
    # screen (resolution + touchscreen), so a single image works on both a
    # bare ADNRPi One (normal monitor) and a ADNRPi Pad.
    echo "Install ADNRPi Pad screen detection + console rotation ..."

    cp -v /tmp/overlay/adnrpipad-detect.sh /usr/local/bin/adnrpipad-detect.sh
    chmod 755 /usr/local/bin/adnrpipad-detect.sh

    cp -v /tmp/overlay/adnrpipad-console-rotate.sh /usr/local/bin/adnrpipad-console-rotate.sh
    chmod 755 /usr/local/bin/adnrpipad-console-rotate.sh

    cp -v /tmp/overlay/adnrpipad-console-rotate.service /etc/systemd/system/adnrpipad-console-rotate.service
    chmod 644 /etc/systemd/system/adnrpipad-console-rotate.service
    systemctl enable adnrpipad-console-rotate.service

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
    # picture on every screen — 4K UHD included, they all accept and upscale
    # 720p — and is the mode RetroMi already ships with for the same reason.
    # The forced mode lands FIRST in the DRM mode list, which is why
    # adnrpipad-detect.sh scans the whole list instead of the first entry.
    echo "Force universal 720p video mode (4K screen compatibility) ..."
    local bootcfg="/boot/armbianEnv.txt"
    if grep -q "^extraargs=" "${bootcfg}" 2>/dev/null; then
        sed -i "s|^extraargs=\(.*\)|extraargs=\1 video=HDMI-A-1:1280x720@60|" "${bootcfg}"
    else
        echo "extraargs=video=HDMI-A-1:1280x720@60" >> "${bootcfg}"
    fi
    grep "^extraargs=" "${bootcfg}"
    echo "Force universal 720p video mode ... [DONE]"
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

installROS2Humble() {
    echo "Installing ROS2 Humble (armhf) ..."
    apt-get install -y curl gnupg lsb-release

    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc \
        | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu jammy main" \
        > /etc/apt/sources.list.d/ros2.list

    apt-get update

    # ros-base: core middleware (rcl, rclpy, rclcpp, topics, services, actions)
    apt-get install -y \
        ros-humble-ros-base \
        python3-colcon-common-extensions \
        python3-rosdep \
        python3-argcomplete \
        ros-humble-rmw-cyclonedds-cpp \
        ros-humble-diagnostic-updater \
        ros-humble-tf2 \
        ros-humble-tf2-ros \
        ros-humble-tf2-tools \
        ros-humble-geometry-msgs \
        ros-humble-sensor-msgs \
        ros-humble-nav-msgs \
        ros-humble-std-msgs \
        ros-humble-std-srvs \
        ros-humble-image-transport \
        ros-humble-compressed-image-transport \
        ros-humble-joy \
        ros-humble-teleop-twist-joy \
        ros-humble-teleop-twist-keyboard \
        ros-humble-serial-driver \
        ros-humble-rosbridge-suite \
        ros-humble-robot-state-publisher \
        ros-humble-joint-state-publisher \
        ros-humble-xacro || true

    rosdep init || true
    rosdep update || true

    # Install adnrpi-ros-config tool
    cp -v /tmp/overlay/adnrpi-ros-config /usr/local/bin/adnrpi-ros-config
    chmod 755 /usr/local/bin/adnrpi-ros-config
    mkdir -p /etc/ros

    # Source ROS2 at login via adnrpi-ros-config apply (first-boot will call it)
    echo "source /opt/ros/humble/setup.bash" >> /etc/skel/.bashrc

    echo "Installing ROS2 Humble ... [DONE]"
}

installROS1Noetic() {
    echo "Installing ROS1 Noetic (armhf via focal repo on jammy) ..."
    apt-get install -y curl gnupg lsb-release

    # ROS1 Noetic: official packages target Ubuntu Focal (20.04).
    # Using focal repo on Jammy — works for ros-base + common packages.
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

    echo "ADNRPi first-boot configuration system ... [DONE]"
}

Main "$@"
