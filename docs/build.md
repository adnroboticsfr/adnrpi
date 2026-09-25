# Building Images

## Via GitHub Actions (recommended)

### Single image (quick test)

1. Go to **Actions → Build single image**
2. Click **Run workflow**
3. Enter the config name (without `.conf`):
   - `adnrpi1-trixie-server`
   - `adnrpi1-jammy-ros2-server`
   - `adnrpi1-noble-desktop_XFCE`
4. Run — artifact available in ~40 min

### All images

1. Go to **Actions → Build Images**
2. Click **Run workflow** on the `develop` branch
3. All configs in `configs/` are built in parallel (~60 min)

### Kernel only

To test a kernel patch without building the full image:

1. **Actions → Build kernel only**
2. Select the kernel branch (`legacy` = 6.12, `current` = 6.18)

### U-Boot only

To test the boot logo or defconfig:

1. **Actions → Build U-Boot only**
2. The generated `.deb` can be installed directly on a running board:

```bash
dpkg -i linux-u-boot-adnrpi1-current_*.deb
dd if=/usr/lib/linux-u-boot-current-adnrpi1/u-boot-sunxi-with-spl.bin \
   of=/dev/mmcblk0 bs=1024 seek=8 conv=fsync
```

## Local build (Linux / WSL2 required)

```bash
git clone https://github.com/armbian/build.git
cd build

# Copy patches and configs
cp -R /path/to/adnrpi/boards/* config/boards/
cp -R /path/to/adnrpi/userpatches/* userpatches/
cp /path/to/adnrpi/configs/adnrpi1-trixie-server.conf userpatches/config-settings.conf

# Build
./compile.sh settings BOARD=adnrpi1 BRANCH=current RELEASE=trixie
```

## Add a new image

1. Create `configs/adnrpi1-{codename}-{variant}.conf`:

```ini
BOARD="adnrpi1"
BOOTSIZE="512"
BOOTFS_TYPE="fat"
RELEASE="trixie"
BUILD_DESKTOP="no"
BRANCH="current"
```

1. Push to `develop` — the workflow picks it up automatically on the next run.

## Create a release

1. Wait for a successful **Build Images** run on `develop`
2. **Actions → Release Images → Run workflow**
3. Enter the version number (e.g. `v1.0.0`)
4. Artifacts are attached to the GitHub release
