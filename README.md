# MiniPBX

MiniPBX est une interface web legere pour administrer un petit PBX Asterisk destine aux TPE. L'objectif prioritaire est une installation simple, avec Asterisk, l'application FastAPI et SQLite dans un conteneur Docker appliance.

Version courante : `0.1.1`

Documentation :

- [Deploiement](docs/DEPLOYMENT.md)
- [Procedure de release](docs/RELEASE.md)
- [Changelog](CHANGELOG.md)

## Demarrage rapide

```bash
cp .env.example .env
./install.sh
docker compose up -d
```

Puis ouvrir :

```text
http://IP_DU_SERVEUR:8080
```

Au premier lancement, MiniPBX affiche l'assistant de creation du premier administrateur.

## Mode reseau

Le mode recommande en production Linux est le mode `host`, configure par defaut dans `docker-compose.yml`. Il evite les problemes classiques de NAT SIP/RTP.

Pour un usage de developpement en bridge :

```bash
docker compose --profile bridge up -d minipbx-bridge
```

Ports utilises :

- Web MiniPBX : TCP `8080`, configurable avec `MINIPBX_WEB_PORT`
- SIP PJSIP : UDP `5060`
- RTP : UDP `10000-10100` par defaut

### Audio absent en mode bridge

Si les softphones sonnent et decrochent mais qu'il n'y a aucun son, SIP fonctionne mais RTP ne passe pas correctement.

En mode bridge, configure `.env` avec l'adresse LAN de la machine qui lance Docker :

```env
ASTERISK_EXTERNAL_ADDRESS=192.168.1.42
ASTERISK_LOCAL_NET=172.18.0.0/16
ASTERISK_RTP_START=10000
ASTERISK_RTP_END=10100
```

En mode bridge, `ASTERISK_LOCAL_NET` doit correspondre au reseau interne Docker, pas au LAN. Si tu mets le LAN, par exemple `192.168.1.0/24`, Asterisk considere les softphones comme locaux et peut annoncer l'adresse du conteneur, comme `172.18.0.2`, dans le SIP/SDP.

Les deux softphones doivent utiliser cette meme adresse LAN comme serveur SIP, meme le softphone lance sur la machine Docker :

```text
Identite SIP : sip:100@192.168.1.42
Proxy        : sip:192.168.1.42:5060
Transport    : UDP
```

Eviter `127.0.0.1` pour les tests avec plusieurs appareils. `127.0.0.1` ne designe que la machine locale du softphone, pas le PBX vu depuis le smartphone.

Apres modification de `.env` :

```bash
docker compose --profile bridge up -d --build --force-recreate minipbx-bridge
```

Puis dans MiniPBX :

```text
Configuration -> Generer une revision -> Appliquer / reload
```

Pour diagnostiquer le RTP :

```bash
docker compose --profile bridge exec minipbx-bridge asterisk -C /etc/asterisk/asterisk.conf -rx "rtp set debug on"
docker compose --profile bridge logs -f minipbx-bridge
```

Pendant un appel, les logs doivent montrer des paquets RTP entrants et sortants. Des paquets dans un seul sens indiquent un probleme d'adresse annoncee, de pare-feu ou de ports UDP.

### INVITE entrant trunk : No matching endpoint / Failed to authenticate

Si un operateur envoie un appel entrant et qu'Asterisk loggue :

```text
Request 'INVITE' ... - No matching endpoint found
Request 'INVITE' ... - Failed to authenticate
```

cela signifie que l'IP source de l'operateur n'est pas reconnue comme le trunk SIP.

Dans `Configuration > Trunk SIP`, renseigner `IP/domaines entrants operateur` avec l'IP vue dans les logs. Exemple FreePro :

```text
85.31.193.213
```

Puis :

```text
Configuration -> Generer une revision -> Appliquer / reload
```

La configuration generee ajoute une section PJSIP `type=identify` pour rattacher les INVITE entrants au trunk.

## Donnees persistantes

Les donnees importantes sont stockees dans des volumes Docker :

- `/var/lib/minipbx` : SQLite, revisions generees, sauvegardes
- `/etc/asterisk` : configuration Asterisk et fichiers inclus MiniPBX
- `/var/spool/asterisk` : messagerie vocale
- `/var/log/asterisk` : logs et CDR

Aucune donnee importante ne doit dependre uniquement du filesystem ephemere du conteneur.

## Configuration generee

MiniPBX genere des fichiers dedies :

- `pjsip_minipbx.conf`
- `extensions_minipbx.conf`
- `voicemail_minipbx.conf`
- `rtp.conf`

Les fichiers principaux Asterisk incluent les fichiers MiniPBX. L'application ne demande pas de modifier manuellement Asterisk apres installation.

Le conteneur initialise aussi un `asterisk.conf` minimal dans le volume `/etc/asterisk`. Ce fichier est necessaire car le volume Docker masque les fichiers de configuration fournis par le paquet Asterisk.

Au demarrage du conteneur, MiniPBX ecrit la configuration courante dans `/etc/asterisk` uniquement si un administrateur existe, si la configuration est valide et si les fichiers actifs ne correspondent plus a la base. Asterisk demarre donc avec la derniere configuration connue sans recreer une revision inutile a chaque redemarrage.

## Garde-fous production

- `./install.sh` genere `MINIPBX_SECRET_KEY` et `MINIPBX_AMI_PASSWORD`. Le demarrage est refuse si ces valeurs restent sur les placeholders de `.env.example`.
- Les formulaires admin utilisent un jeton CSRF en session.
- Les sessions expirent par defaut apres 8 heures (`MINIPBX_SESSION_MAX_AGE_SECONDS`).
- Les commandes Asterisk configurables sont executees sans shell.
- Si un reload Asterisk echoue apres application ou restauration, MiniPBX restaure les anciens fichiers de configuration sauvegardes.
- Les migrations Alembic sont appliquees au demarrage par defaut (`MINIPBX_MIGRATIONS_ENABLED=true`).
- Les anciennes bases creees avant Alembic sont detectees et estampillees avant application des nouvelles migrations.
- Les services Docker ont un healthcheck HTTP sur `/health`.
- L'entrypoint corrige les permissions des volumes puis lance Asterisk et Uvicorn avec l'utilisateur non-root `MINIPBX_RUNTIME_USER` (`asterisk` par defaut).

## Developpement local

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export MINIPBX_DATA_DIR=/tmp/minipbx
export MINIPBX_DATABASE_URL=sqlite:////tmp/minipbx/minipbx.db
export MINIPBX_SECRET_KEY=dev-secret-change-me
export MINIPBX_GENERATED_CONFIG_DIR=/tmp/minipbx/generated
export MINIPBX_BACKUP_DIR=/tmp/minipbx/backups
export MINIPBX_ASTERISK_CONFIG_DIR=/tmp/minipbx/asterisk
export MINIPBX_ASTERISK_APPLY_ENABLED=false
uvicorn app.main:app --reload --port 8080
```

Tests :

```bash
docker compose --profile bridge run --rm --entrypoint pytest minipbx-bridge
```

Smoke test Docker :

```bash
docker/smoke-test.sh
```

## Etat initial implemente

- Page d'accueil
- Assistant de premier demarrage avec administrateur, reseau PBX, premiere extension et trunk optionnel
- Creation du premier administrateur
- Session admin
- Dashboard protege
- Creation, modification, suppression des extensions
- Regeneration du mot de passe SIP d'une extension
- Affichage des informations de configuration telephone
- Page de configuration unifiee avec onglets
- Reglages PBX modifiables apres le premier demarrage
- Validation de configuration affichee par section
- Groupes d'appel avec sonnerie simultanee
- Standard vocal avec touches DTMF vers extensions ou groupes
- Message de standard par fichier audio ou texte TTS
- Routes entrantes multiples par numero appele
- Routage entrant vers extension, groupe d'appel, standard ou messagerie
- Horaires d'ouverture pour le routage entrant
- Fermetures exceptionnelles par date
- Consultation, telechargement et suppression des messages vocaux
- Message de messagerie personnalise par extension, via fichier audio ou TTS
- Regles d'appels sortants avec prefixe optionnel
- Blocage international par defaut
- Journal d'appels depuis les CDR Asterisk
- Filtres par date, extension et direction d'appel
- Export CSV du journal d'appels
- Diagnostics PJSIP/RTP depuis l'interface
- Page Sante Asterisk avec synthese serveur, trunk, extensions et appels actifs
- Test statique de la configuration generee avant application
- Supervision temps reel WebSocket des extensions et appels actifs
- Supervision du trunk SIP avec etat d'enregistrement PJSIP
- Configuration AMI locale preparee pour les evenements Asterisk
- Client AMI en tache de fond pour reveiller la supervision WebSocket sur evenement
- Page sauvegardes avec telechargement ZIP des revisions et backups Asterisk
- Restauration guidee d'une sauvegarde Asterisk avec confirmation
- Sauvegarde applicative complete avec SQLite, revisions et fichiers Asterisk
- Inspection d'une sauvegarde complete avant import
- Application controlee d'une sauvegarde complete avec base SQLite en staging
- Activation confirmee d'une base SQLite importee avec sauvegarde de l'ancienne base
- Alerte persistante de redemarrage requis apres activation d'une base SQLite importee
- Rejet des sauvegardes ZIP completes avec chemin dangereux ou contenu decompresse trop volumineux
- Configuration du trunk SIP principal
- Masquage du secret trunk dans l'interface apres sauvegarde
- Previsualisation des fichiers Asterisk generes
- Validation de coherence avant generation/application de la configuration
- Historique des revisions de configuration avec application ciblee
- Etat global de configuration dans le menu
- Application en un clic de la configuration courante
- Generation minimale `PJSIP`, dialplan, voicemail et RTP
- Application/reload Asterisk via commande configurable
- Sauvegarde des anciennes configurations avant application
- Dockerfile, Compose, `.env.example` et `install.sh`
- Protection CSRF des actions admin
- Healthcheck Docker
- Migrations Alembic au demarrage
- Bootstrap Alembic pour les volumes existants sans historique de migration
- Rollback des fichiers Asterisk si reload echoue
- Tests de rollback sur application de revision et restauration Asterisk
- Assistant initial transactionnel pour eviter un administrateur sans configuration PBX
- Retrait du module carnet d'adresse pour recentrer MiniPBX sur la gestion serveur
- Timestamps applicatifs generes en UTC timezone-aware
- Normalisation WAV interne sans dependance `audioop`
- Rendu templates compatible avec la signature Starlette recente
- Hachage des mots de passe admin via PBKDF2 standard library, sans dependance `passlib`, avec compatibilite des anciens hashes
- Execution d'Asterisk et Uvicorn avec l'utilisateur non-root `asterisk` apres preparation des volumes par l'entrypoint
- Fichiers optionnels Asterisk initialises par l'entrypoint pour eviter les avertissements de demarrage parasites
- Smoke test Docker pour verifier demarrage court, utilisateur effectif des processus et CLI Asterisk

## Prochaines etapes techniques

- Brancher `docker/smoke-test.sh` dans une verification CI ou pre-release
