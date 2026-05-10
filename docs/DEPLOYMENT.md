# Deploiement MiniPBX

Ce guide decrit un premier deploiement de MiniPBX sur un serveur Linux.

## Prerequis

- Serveur Linux avec Docker et Docker Compose v2.
- Acces reseau UDP entrant vers le serveur pour SIP et RTP.
- Ports libres :
  - TCP `8080` pour l'interface web MiniPBX.
  - UDP `5060` pour SIP.
  - UDP `10000-10100` pour RTP par defaut.
- Un nom ou une adresse IP stable pour les softphones.

## Installation

Depuis le dossier du projet :

```bash
cp .env.example .env
./install.sh
docker compose up -d --build
```

Ouvrir ensuite :

```text
http://IP_DU_SERVEUR:8080
```

L'assistant de premier demarrage permet de creer l'administrateur, regler le reseau PBX et creer une premiere extension.

## Configuration reseau recommandee

En production Linux, garder le service `minipbx` par defaut, qui utilise `network_mode: host`.

Dans `.env`, verifier :

```env
MINIPBX_WEB_PORT=8080
ASTERISK_SIP_PORT=5060
ASTERISK_RTP_START=10000
ASTERISK_RTP_END=10100
ASTERISK_EXTERNAL_ADDRESS=
ASTERISK_LOCAL_NET=192.168.1.0/24
```

En mode host, `ASTERISK_EXTERNAL_ADDRESS` peut rester vide sur un LAN simple. Si le PBX est derriere un NAT, renseigner l'adresse publique ou l'adresse annoncee aux softphones.

## Pare-feu

Autoriser au minimum :

```text
TCP 8080
UDP 5060
UDP 10000-10100
```

La plage RTP doit correspondre a `ASTERISK_RTP_START` et `ASTERISK_RTP_END`.

## Donnees persistantes

Les donnees sont stockees dans des volumes Docker nommes :

- `minipbx_data` : base SQLite, revisions, sauvegardes, prompts.
- `minipbx_asterisk_etc` : configuration Asterisk active.
- `minipbx_asterisk_spool` : messagerie vocale.
- `minipbx_asterisk_logs` : logs Asterisk et CDR.

Ne pas supprimer ces volumes lors d'une mise a jour, sauf si l'objectif est de repartir de zero.

## Verification apres demarrage

Verifier le conteneur :

```bash
docker compose ps
docker compose logs --tail=100 minipbx
```

Verifier Asterisk :

```bash
docker compose exec minipbx asterisk -C /etc/asterisk/asterisk.conf -rx "core show uptime"
docker compose exec minipbx asterisk -C /etc/asterisk/asterisk.conf -rx "pjsip show endpoints"
```

Le healthcheck Docker appelle `/health/ready`.

## Sauvegarde

Depuis l'interface MiniPBX, utiliser la page `Sauvegardes` pour telecharger une sauvegarde complete.

Avant une mise a jour importante, telecharger une sauvegarde complete et conserver une copie hors du serveur.

## Mise a jour

Depuis le dossier du projet :

```bash
docker compose build
docker compose up -d
```

Les migrations Alembic sont appliquees au demarrage.

Apres mise a jour :

```bash
docker compose ps
docker compose logs --tail=100 minipbx
```

## Restauration

Dans MiniPBX :

1. Aller dans `Sauvegardes`.
2. Importer une sauvegarde complete.
3. Inspecter l'archive.
4. Confirmer l'application.
5. Si une base SQLite importee est activee, redemarrer le conteneur comme indique par l'interface.

## Developpement en mode bridge

Pour Docker Desktop ou un poste de developpement :

```bash
docker compose --profile bridge up -d --build minipbx-bridge
```

Dans ce mode, configurer `ASTERISK_EXTERNAL_ADDRESS` avec l'adresse LAN de la machine Docker, par exemple :

```env
ASTERISK_EXTERNAL_ADDRESS=192.168.1.42
ASTERISK_LOCAL_NET=172.18.0.0/16
```

## Smoke test avant livraison

Le script suivant demarre MiniPBX temporairement en profil bridge, verifie Asterisk, Uvicorn et les warnings de demarrage :

```bash
docker/smoke-test.sh
```

Il doit afficher :

```text
MiniPBX smoke test OK
```
