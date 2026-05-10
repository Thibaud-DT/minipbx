# Procedure de release

Cette procedure prepare une version livrable de MiniPBX.

## 1. Choisir la version

MiniPBX utilise un versionnement semantique simple.

Exemples :

- `0.1.1` : correctif.
- `0.2.0` : nouvelle fonctionnalite compatible.
- `1.0.0` : premiere version consideree stable.

Mettre a jour :

- `VERSION`
- `CHANGELOG.md`

## 2. Verifier les fichiers sensibles

Ne jamais versionner :

- `.env`
- volumes ou exports locaux dans `data/`
- bases SQLite
- logs

Verifier :

```bash
git status --short
```

## 3. Lancer les validations

```bash
docker compose --profile bridge build minipbx-bridge
docker compose --profile bridge run --rm --entrypoint pytest minipbx-bridge
docker compose --profile bridge run --rm --entrypoint alembic minipbx-bridge upgrade head
docker compose --profile bridge config
docker/smoke-test.sh
```

## 4. Creer le commit

```bash
git add .
git commit -m "Release v$(cat VERSION)"
```

## 5. Creer le tag

```bash
git tag -a "v$(cat VERSION)" -m "MiniPBX v$(cat VERSION)"
```

## 6. Deployer

Sur le serveur :

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 minipbx
```

Consulter ensuite l'interface MiniPBX et verifier la page Sante.
