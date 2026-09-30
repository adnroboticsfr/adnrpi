# Gitea sur SmartPi One H3 — GitHub local privé

Interface web Git auto-hébergée, accessible uniquement sur ton réseau local.

## Ce que ça installe

| Composant | Détail |
|-----------|--------|
| **Gitea** v1.22 | Binaire ARM7, ~60MB RAM repos |
| **Stockage auto** | USB branché → utilisé en priorité / sinon SD |
| **Service systemd** | Démarre au boot, redémarre si crash |
| **SSH git** | Port 2222 (port 22 reste pour admin SSH) |
| **Interface web** | Port 3000 |

## Installation

```bash
# 1. Copier les scripts sur le SmartPi
scp -r scripts/gitea/ root@192.168.1.89:/tmp/gitea-install/

# 2. Se connecter et lancer
ssh root@192.168.1.89
cd /tmp/gitea-install
bash install_gitea.sh
```

## Après l'installation

**Première connexion :**  
Ouvrir `http://192.168.1.89:3000` dans un navigateur → créer le compte admin.

**Cloner un dépôt depuis Windows :**
```bash
git clone http://192.168.1.89:3000/tonuser/mon-projet.git
# ou via SSH :
git clone ssh://git@192.168.1.89:2222/tonuser/mon-projet.git
```

**Ajouter Gitea comme remote d'un projet existant :**
```bash
git remote add local http://192.168.1.89:3000/tonuser/mon-projet.git
git push local main
```

## Stockage SD vs USB

Le script `select-storage.sh` s'exécute à chaque boot :

```
Disque USB branché ?
    OUI → monte /mnt/gitea-usb → repos stockés sur USB
    NON → repos stockés sur SD  (/opt/gitea/data-sd)
```

Log de sélection : `/opt/gitea/storage-select.log`

> **Conseil** : SD correcte pour quelques projets perso.  
> Pour >20 dépôts ou binaires lourds → USB 2.5" recommandé.

## Commandes utiles

```bash
# Statut
systemctl status gitea

# Logs
journalctl -u gitea -f

# Voir quel stockage est utilisé
cat /opt/gitea/storage-select.log | tail -5
readlink /opt/gitea/storage

# Redémarrer
systemctl restart gitea

# Mise à jour Gitea
bash install_gitea.sh --upgrade
```

## Ports réseau

| Port | Usage |
|------|-------|
| 22   | SSH système (admin) |
| 2222 | SSH Gitea (git clone/push) |
| 3000 | Interface web Gitea |
