# Changelog

Toutes les modifications notables de MiniPBX sont suivies ici.

Le projet suit un versionnement semantique simple : `MAJEUR.MINEUR.CORRECTIF`.

## [0.1.0] - 2026-05-10

Premiere version de deploiement interne.

### Ajoute

- Interface FastAPI/Jinja2/HTMX avec assistant de premier demarrage.
- Creation du premier administrateur et session admin.
- Gestion des extensions SIP, groupes d'appel, trunk SIP, routes entrantes, regles sortantes, horaires et fermetures.
- Standard vocal avec message audio ou TTS et routage DTMF.
- Messagerie vocale avec messages personnalises par extension.
- Generation et application de configuration Asterisk PJSIP, dialplan, RTP et voicemail.
- Supervision temps reel des extensions, appels actifs et trunk SIP.
- Journal d'appels CDR avec filtres et export CSV.
- Sauvegardes completes, inspection, restauration controlee et rollback en cas d'echec.
- Dockerfile, Compose host/bridge, volumes persistants, healthcheck et script `install.sh`.
- Smoke test Docker `docker/smoke-test.sh`.

### Durci

- CSRF sur les actions admin.
- Secrets generes par `install.sh` et refuses au demarrage s'ils restent sur les placeholders.
- Migrations Alembic au demarrage avec bootstrap des anciens volumes.
- Rollback des fichiers Asterisk si un reload echoue.
- Execution d'Asterisk et Uvicorn sous utilisateur non-root `asterisk` apres preparation des volumes.
- Hachage des mots de passe admin via PBKDF2 standard library, sans dependance `passlib`.
- Rejet des sauvegardes ZIP dangereuses ou trop volumineuses.
- `.dockerignore` pour exclure `.env`, volumes locaux et caches du contexte Docker.

### Limites connues

- Le mode de production cible Linux avec `network_mode: host`.
- Le mode bridge reste prevu pour le developpement et peut necessiter un reglage manuel de `ASTERISK_EXTERNAL_ADDRESS`.
- HTTPS et reverse proxy sont hors perimetre MiniPBX.
