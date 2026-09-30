#!/bin/bash
# =============================================================================
# ADNRPi — Sélection stockage Gitea (SD ou disque USB)
#
# Logique :
#   1. Cherche un disque USB branché (amovible, type disk ou partition)
#   2. Si trouvé et montable → /mnt/gitea-usb  (préféré)
#   3. Sinon              → /opt/gitea/data     (SD, fallback)
#   4. Crée/met à jour le symlink /opt/gitea/storage → dossier choisi
#
# Appelé par gitea-storage.service avant le démarrage de Gitea.
# =============================================================================

SYMLINK="/opt/gitea/storage"
SD_PATH="/opt/gitea/data-sd"
USB_MOUNT="/mnt/gitea-usb"
USB_DATA="$USB_MOUNT/gitea"
LOG="/opt/gitea/storage-select.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

mkdir -p "$SD_PATH" "$USB_MOUNT"
chown git:git "$SD_PATH"

# ── Cherche un disque/partition USB amovible ──────────────────────────────────
find_usb() {
    # lsblk : NAME RM(amovible) TYPE(disk/part) FSTYPE MOUNTPOINT
    while IFS= read -r line; do
        dev=$(echo "$line" | awk '{print $1}')
        rm=$(echo  "$line" | awk '{print $2}')
        type=$(echo "$line" | awk '{print $3}')
        fs=$(echo  "$line" | awk '{print $4}')
        mp=$(echo  "$line" | awk '{print $5}')

        # amovible + (disk ou part) + système de fichiers connu + pas système
        if [ "$rm" = "1" ] && [ "$type" != "rom" ] && \
           echo "$fs" | grep -qE 'ext[234]|btrfs|xfs|vfat' && \
           ! echo "$mp" | grep -qE '^/$|^/boot'; then
            echo "/dev/$dev"
            return
        fi
    done < <(lsblk -o NAME,RM,TYPE,FSTYPE,MOUNTPOINT -r -n)
}

USB_DEV=$(find_usb)

# ── Tentative de montage USB ──────────────────────────────────────────────────
if [ -n "$USB_DEV" ]; then
    log "Disque USB détecté : $USB_DEV"

    # Déjà monté ?
    if mountpoint -q "$USB_MOUNT"; then
        log "Déjà monté sur $USB_MOUNT"
    else
        mount "$USB_DEV" "$USB_MOUNT" 2>>"$LOG"
        if mountpoint -q "$USB_MOUNT"; then
            log "Monté $USB_DEV → $USB_MOUNT"
        else
            log "WARN : montage échoué, repli SD"
            USB_DEV=""
        fi
    fi
fi

# ── Choix du stockage ─────────────────────────────────────────────────────────
if [ -n "$USB_DEV" ] && mountpoint -q "$USB_MOUNT"; then
    CHOSEN="$USB_DATA"
    mkdir -p "$USB_DATA"
    chown -R git:git "$USB_DATA"
    log "Stockage → USB  ($CHOSEN)"
else
    CHOSEN="$SD_PATH"
    log "Stockage → SD   ($CHOSEN)"
fi

# ── Mise à jour du symlink ────────────────────────────────────────────────────
ln -sfn "$CHOSEN" "$SYMLINK"
chown -h git:git "$SYMLINK"
log "Symlink : $SYMLINK → $(readlink $SYMLINK)"
