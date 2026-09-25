# Builder une image

## Via GitHub Actions (recommandé)

### Image unique (test rapide)

1. Va sur **Actions → Build single image**
2. Clique **Run workflow**
3. Entre le nom du config (sans `.conf`) :
   - `adnrpi1-trixie-server`
   - `adnrpi1-jammy-ros2-server`
   - `adnrpi1-noble-desktop_XFCE`
4. Lance — résultat disponible dans les artefacts (~40 min)

### Toutes les images

1. Va sur **Actions → Build Images**
2. Clique **Run workflow** sur la branche `develop`
3. Toutes les configs de `configs/` sont buildées en parallèle (~60 min)

### Kernel uniquement

Pour tester un patch kernel sans builder l'image complète :

1. **Actions → Build kernel only**
2. Sélectionne la branche kernel (`legacy` = 6.12, `current` = 6.18)

### U-Boot uniquement

Pour tester le logo de boot ou le defconfig :

1. **Actions → Build U-Boot only**
2. Le `.deb` généré peut s'installer directement sur une carte :
```bash
dpkg -i linux-u-boot-adnrpi1-current_*.deb
dd if=/usr/lib/linux-u-boot-current-adnrpi1/u-boot-sunxi-with-spl.bin \
   of=/dev/mmcblk0 bs=1024 seek=8 conv=fsync
```

## En local (Linux/WSL2 requis)

```bash
git clone https://github.com/armbian/build.git
cd build

# Copier les patches et configs
cp -R /path/to/adnrpi/boards/* config/boards/
cp -R /path/to/adnrpi/userpatches/* userpatches/
cp /path/to/adnrpi/configs/adnrpi1-trixie-server.conf userpatches/config-settings.conf

# Builder
./compile.sh settings BOARD=adnrpi1 BRANCH=current RELEASE=trixie
```

## Ajouter une nouvelle image

1. Crée `configs/adnrpi1-{codename}-{variant}.conf` :
```ini
BOARD="adnrpi1"
BOOTSIZE="512"
BOOTFS_TYPE="fat"
RELEASE="trixie"
BUILD_DESKTOP="no"
BRANCH="current"
```

2. Push sur `develop` — le workflow la détecte automatiquement dans la prochaine run

## Créer une release

1. Attends qu'un **Build Images** réussisse sur `develop`
2. **Actions → Release Images → Run workflow**
3. Entre le numéro de version (ex: `v1.0.0`)
4. Les artefacts sont attachés à la release GitHub
