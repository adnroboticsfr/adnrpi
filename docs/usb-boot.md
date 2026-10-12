# Démarrer depuis un USB / SSD / NVMe

Par défaut, l'ADNRPi démarre depuis la carte SD. Ce guide explique comment migrer le système vers un support externe plus rapide et plus fiable.

## Pourquoi migrer ?

| Carte SD | USB/SSD/NVMe |
|----------|-------------|
| Lente en écriture (~10 Mo/s) | Rapide (40–500 Mo/s) |
| Durée de vie limitée (cycles d'écriture) | Nettement plus durable |
| Taille limitée (8–64 Go) | Jusqu'à plusieurs To |
| Risque de corruption si coupure | Meilleure résistance |

## Fonctionnement

L'Allwinner H3 (puce du ADNRPi One) charge toujours **U-Boot depuis la carte SD** au démarrage. U-Boot cherche ensuite le système d'exploitation sur USB en priorité.

```
Démarrage :  SD (U-Boot) → USB/SSD (système Linux)
```

> **La carte SD reste nécessaire** — elle contient uniquement le bootloader (~8 Mo utilisés).

---

## Méthode 1 — Via adnrpi-setup (recommandée)

Lors du premier démarrage, `adnrpi-setup` propose l'option automatiquement :

```
── Stockage système (optionnel) ─────────────────────
    Par défaut le système démarre depuis la carte SD.
    Vous pouvez le migrer vers une clé USB, un disque dur ou un SSD NVMe.

    Migrer vers USB/SSD/NVMe après la configuration [y/N]:
```

Répondez `y` — le script `adnrpi-install-usb` se lance automatiquement après la configuration.

---

## Méthode 2 — Commande manuelle

Disponible à tout moment depuis une session root ou SSH :

```bash
sudo adnrpi-install-usb
```

Le script :
1. Détecte les périphériques disponibles (USB, SSD, NVMe)
2. Vous demande de choisir la cible
3. Formate la partition cible en ext4
4. Copie le système avec `rsync`
5. Met à jour `/boot/armbianEnv.txt` avec l'UUID du nouveau disque
6. Propose le redémarrage

### Mode automatique (sans interaction)

```bash
sudo adnrpi-install-usb --auto /dev/sda
```

Utile pour les scripts de déploiement automatisé.

---

## Méthode 3 — Migration manuelle

Si vous préférez contrôler chaque étape :

```bash
# 1. Identifier votre périphérique USB/SSD
lsblk

# 2. Partitionner et formater
sudo parted /dev/sda mklabel msdos
sudo parted /dev/sda mkpart primary ext4 1MiB 100%
sudo mkfs.ext4 -L "adnrpi-root" /dev/sda1

# 3. Monter et copier
sudo mkdir -p /mnt/usb
sudo mount /dev/sda1 /mnt/usb
sudo rsync -axHAWXS --progress / /mnt/usb/ \
    --exclude={/boot,/proc,/sys,/dev,/run,/tmp,/mnt,/media}

# 4. Recréer les points de montage
for d in boot proc sys dev run tmp mnt media; do
    sudo mkdir -p /mnt/usb/$d
done

# 5. Récupérer l'UUID du nouveau disque
sudo blkid -s UUID -o value /dev/sda1

# 6. Mettre à jour armbianEnv.txt
sudo nano /boot/armbianEnv.txt
# Modifier ou ajouter la ligne :
# rootdev=UUID=<votre-UUID>

# 7. Démonter et redémarrer
sudo umount /mnt/usb
sudo reboot
```

---

## Vérification après redémarrage

```bash
# Confirmer que le rootfs est sur le bon disque
df -h /
# Résultat attendu : /dev/sda1 (ou nvme0n1p1, etc.)

# Voir l'UUID configuré
grep rootdev /boot/armbianEnv.txt
```

---

## Revenir à la carte SD

Si le démarrage USB pose problème, retirez le périphérique USB et redémarrez. Le système reviendra automatiquement sur la carte SD (si le rootfs y est encore intact).

Pour re-pointer définitivement sur la SD :

```bash
sudo nano /boot/armbianEnv.txt
# Supprimer ou commenter la ligne rootdev=UUID=...
sudo reboot
```

---

## Périphériques compatibles

| Type | Interface | Performances |
|------|-----------|-------------|
| Clé USB 3.0 | USB-A | 40–100 Mo/s |
| SSD 2.5" | Boîtier USB 3.0 | 200–400 Mo/s |
| SSD NVMe | Adaptateur USB-C/A | 300–500 Mo/s |
| Disque dur 2.5" | Boîtier USB 3.0 | 80–120 Mo/s |

> Le port USB de l'ADNRPi One est USB 2.0 — les vitesses sont plafonnées à ~40 Mo/s en pratique.

---

## Dépannage

**Le système démarre toujours depuis la SD après migration**
→ Vérifiez `/boot/armbianEnv.txt` : la ligne `rootdev=UUID=...` doit être présente.
→ Vérifiez que l'UUID correspond bien à votre partition : `blkid /dev/sda1`

**Erreur "cannot mount rootfs" au démarrage**
→ La partition USB n'est pas reconnue. Vérifiez le câble et le formatage ext4.
→ Retirez le USB pour démarrer en secours depuis la SD.

**rsync trop lent**
→ Normal pour des systèmes >4 Go. Comptez 10–20 min pour une copie complète sur USB 2.0.

---

*Voir aussi : [first-boot.md](first-boot.md) — [ssh-usb.md](ssh-usb.md)*
