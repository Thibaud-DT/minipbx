# Cahier des charges — PBX léger pour TPE

## 1. Objectif du projet

Développer un petit serveur SIP/PBX destiné aux entreprises de **1 à 10 salariés**, avec une interface d’administration très simple.

Le produit doit permettre de gérer les besoins téléphoniques essentiels sans la complexité de FreePBX ou FusionPBX :

* créer des utilisateurs/extensions ;
* connecter un ou plusieurs trunks SIP opérateur ;
* gérer les appels entrants ;
* gérer les appels sortants ;
* définir des horaires d’ouverture ;
* mettre en place un message d’accueil simple ;
* consulter les journaux d’appels ;
* configurer la messagerie vocale ;
* sauvegarder/restaurer la configuration.

Le système doit être utilisable par un administrateur non spécialiste VoIP.

---

## 2. Positionnement

Nom provisoire : **MiniPBX**

MiniPBX n’est pas une distribution PBX complète. C’est une **surcouche simplifiée autour d’Asterisk**.

Asterisk reste responsable de :

* l’enregistrement SIP ;
* les appels internes ;
* les appels entrants/sortants ;
* le RTP/audio ;
* les trunks opérateur ;
* les règles de routage ;
* la messagerie vocale ;
* les CDR.

Notre application sera responsable de :

* l’interface web ;
* la gestion des utilisateurs ;
* la génération des fichiers de configuration ;
* la validation des paramètres ;
* le rechargement contrôlé d’Asterisk ;
* la consultation simplifiée des appels ;
* les sauvegardes ;
* l’assistant d’installation.

---

## 3. Périmètre fonctionnel MVP

### 3.1 Extensions internes

Le système doit permettre de créer des postes internes.

Chaque extension aura :

* un numéro court, par exemple `101`, `102`, `103` ;
* un nom d’utilisateur ;
* un identifiant SIP ;
* un mot de passe SIP généré automatiquement ;
* une adresse e-mail optionnelle ;
* une messagerie vocale activable ou non ;
* une option “peut appeler vers l’extérieur” ;
* une option “peut recevoir les appels entrants”.

Exemple :

| Extension | Nom       | SIP login | Messagerie | Appels sortants |
| --------- | --------- | --------- | ---------- | --------------- |
| 101       | Accueil   | 101       | Oui        | Oui             |
| 102       | Direction | 102       | Oui        | Oui             |
| 103       | Atelier   | 103       | Non        | Non             |

---

### 3.2 Trunk SIP opérateur

Le système doit permettre de configurer au moins un trunk SIP.

Champs nécessaires :

* nom du trunk ;
* domaine ou IP de l’opérateur ;
* identifiant ;
* mot de passe ;
* numéro principal ;
* mode d’authentification ;
* transport UDP/TCP/TLS, avec UDP par défaut pour le MVP ;
* préfixe de sortie optionnel, par exemple `0` pour sortir ;
* codecs autorisés.

Pour le MVP, on limite volontairement à un trunk principal.

---

### 3.3 Appels internes

Les utilisateurs doivent pouvoir s’appeler entre eux par numéro court.

Exemple :

* `101` appelle `102` ;
* `102` appelle `103`.

---

### 3.4 Appels sortants

Le système doit permettre de router les appels sortants via le trunk SIP.

Règles MVP :

* appels nationaux autorisés ;
* appels mobiles autorisés ;
* appels internationaux désactivés par défaut ;
* numéros d’urgence à traiter séparément selon le pays et l’opérateur ;
* possibilité d’ajouter un préfixe de sortie.

Exemple :

* l’utilisateur compose `0123456789` ;
* MiniPBX route l’appel vers le trunk opérateur.

---

### 3.5 Appels entrants

Le système doit permettre de définir une destination pour les appels entrants.

Destinations possibles MVP :

* une extension ;
* un groupe d’appel ;
* un message d’accueil puis une extension ;
* une messagerie vocale ;
* fermeture selon horaires.

Exemple simple :

> En journée, les appels entrants sonnent sur `101`, `102` et `103`.
> Hors horaires, les appels sont envoyés vers la messagerie de l’accueil.

---

### 3.6 Groupe d’appel

Le système doit permettre de créer un groupe d’appel.

Pour le MVP :

* sonnerie simultanée ;
* délai avant échec, par exemple 20 secondes ;
* destination de secours si personne ne répond.

Exemple :

Groupe `Accueil` :

* membres : `101`, `102`, `103` ;
* durée de sonnerie : 20 secondes ;
* si non-réponse : messagerie vocale de `101`.

---

### 3.7 Horaires d’ouverture

Le système doit permettre de configurer des horaires simples.

Exemple :

| Jour     | Ouverture | Fermeture |
| -------- | --------: | --------: |
| Lundi    |     09:00 |     18:00 |
| Mardi    |     09:00 |     18:00 |
| Mercredi |     09:00 |     18:00 |
| Jeudi    |     09:00 |     18:00 |
| Vendredi |     09:00 |     17:00 |
| Samedi   |     Fermé |     Fermé |
| Dimanche |     Fermé |     Fermé |

Le MVP doit gérer :

* ouvert ;
* fermé ;
* destination pendant ouverture ;
* destination pendant fermeture.

Les jours fériés et calendriers avancés seront hors MVP.

---

### 3.8 Message d’accueil

Le système doit permettre d’utiliser un message d’accueil.

Pour le MVP :

* upload d’un fichier audio ;
* conversion si nécessaire vers un format compatible ;
* association du message à une règle entrante.

Fonctionnalité optionnelle V2 :

* synthèse vocale ;
* enregistrement depuis un téléphone ;
* menus vocaux interactifs.

---

### 3.9 Messagerie vocale

Le système doit permettre d’activer une messagerie vocale par extension.

Asterisk fournit une application `VoiceMail` qui permet à un appelant de laisser un message dans une boîte vocale définie. ([docs.asterisk.org][3])

Pour le MVP :

* activation/désactivation par extension ;
* code PIN ;
* notification e-mail optionnelle ;
* consultation depuis le téléphone via un numéro spécial, par exemple `*97`.

---

### 3.10 Journal d’appels

Le système doit afficher les appels récents.

Informations affichées :

* date ;
* appelant ;
* appelé ;
* statut ;
* durée ;
* direction : entrant, sortant, interne ;
* trunk utilisé si applicable.

Asterisk CDR suit notamment le début, la réponse, la fin, la durée et le temps facturable d’un appel. ([docs.asterisk.org][4])

Pour le MVP, l’interface devra proposer :

* liste des appels ;
* filtre par date ;
* filtre par extension ;
* filtre entrant/sortant/interne ;
* export CSV.

---

## 4. Hors périmètre MVP

Pour éviter de recréer FreePBX, les éléments suivants seront exclus au départ :

* multi-tenant ;
* centres d’appels complexes ;
* files d’attente avancées ;
* statistiques poussées ;
* WebRTC ;
* softphone intégré ;
* fax ;
* visioconférence ;
* provisioning automatique de téléphones IP ;
* haute disponibilité ;
* cluster ;
* intégration CRM ;
* menus vocaux complexes ;
* facturation ;
* gestion avancée des droits ;
* chiffrement SIP/TLS et SRTP obligatoire.

Certains de ces points pourront être ajoutés ensuite, mais ils ne doivent pas polluer la première version.

---

# 5. Architecture proposée

## 5.1 Vue générale

```text
+---------------------------+
| Interface Web MiniPBX     |
| FastAPI + HTMX            |
+-------------+-------------+
              |
              v
+---------------------------+
| Base de données SQLite    |
| extensions, trunks, etc.  |
+-------------+-------------+
              |
              v
+---------------------------+
| Générateur de config      |
| pjsip.conf, extensions... |
+-------------+-------------+
              |
              v
+---------------------------+
| Asterisk 22 LTS           |
| SIP, RTP, dialplan, CDR   |
+---------------------------+
```

---

## 5.2 Choix technique recommandé

Je propose cette stack pour rester simple :

| Composant              | Choix                            |
| ---------------------- | -------------------------------- |
| Moteur téléphonique    | Asterisk 22 LTS                  |
| SIP                    | PJSIP                            |
| Backend web            | Python FastAPI                   |
| Interface              | HTMX + templates Jinja2          |
| Base de données        | SQLite au départ                 |
| Authentification admin | Session web + mot de passe hashé |
| Génération config      | Templates Jinja2                 |
| Déploiement            | Debian/Ubuntu + systemd          |
| Reverse proxy          | Nginx optionnel                  |
| Tests                  | Pytest                           |
| Assistant dev          | Codex                            |

Pourquoi pas React ? Parce que pour un outil d’administration simple, React ajouterait de la complexité inutile. FastAPI + HTMX permet une interface moderne, mais très légère.

---

# 6. Écrans à développer

## 6.1 Tableau de bord

Le tableau de bord affichera :

* état d’Asterisk ;
* nombre d’extensions ;
* état du trunk principal ;
* derniers appels ;
* alertes de configuration.

Exemples d’alertes :

* trunk non configuré ;
* extension sans mot de passe ;
* aucun routage entrant ;
* configuration modifiée mais non appliquée.

---

## 6.2 Extensions

Fonctions :

* lister les extensions ;
* créer une extension ;
* modifier une extension ;
* supprimer une extension ;
* régénérer le mot de passe SIP ;
* afficher les paramètres de configuration du téléphone.

---

## 6.3 Trunk SIP

Fonctions :

* configurer le trunk principal ;
* tester l’enregistrement ;
* voir l’état du trunk ;
* activer/désactiver le trunk.

---

## 6.4 Routage entrant

Fonctions :

* choisir la destination des appels entrants ;
* définir le comportement ouvert/fermé ;
* sélectionner un groupe d’appel ;
* sélectionner une messagerie vocale.

---

## 6.5 Groupes d’appel

Fonctions :

* créer un groupe ;
* choisir les membres ;
* choisir la durée de sonnerie ;
* choisir la destination si personne ne répond.

---

## 6.6 Horaires

Fonctions :

* configurer les horaires hebdomadaires ;
* activer/désactiver la gestion horaire ;
* choisir destination ouverte ;
* choisir destination fermée.

---

## 6.7 Journaux d’appels

Fonctions :

* afficher les appels ;
* filtrer ;
* exporter CSV.

---

## 6.8 Sauvegarde/restauration

Fonctions :

* exporter la configuration MiniPBX ;
* restaurer une configuration ;
* sauvegarder les fichiers Asterisk générés ;
* conserver un historique local des dernières configurations appliquées.

---

# 7. Modèle de données initial

Tables principales :

```text
users_admin
- id
- username
- password_hash
- created_at

extensions
- id
- number
- display_name
- sip_username
- sip_password_hash_or_secret
- voicemail_enabled
- voicemail_pin
- outbound_enabled
- enabled
- created_at
- updated_at

sip_trunks
- id
- name
- host
- username
- password_secret
- from_user
- from_domain
- transport
- enabled
- created_at
- updated_at

ring_groups
- id
- name
- number
- timeout_seconds
- fallback_type
- fallback_target

ring_group_members
- id
- ring_group_id
- extension_id

business_hours
- id
- weekday
- open_time
- close_time
- is_closed

inbound_routes
- id
- name
- did_number
- use_business_hours
- open_destination_type
- open_destination_target
- closed_destination_type
- closed_destination_target

system_settings
- key
- value

config_revisions
- id
- created_at
- status
- summary
- generated_path
```

---

# 8. Fichiers Asterisk générés

MiniPBX générera principalement :

```text
/etc/asterisk/pjsip_minipbx.conf
/etc/asterisk/extensions_minipbx.conf
/etc/asterisk/voicemail_minipbx.conf
/etc/asterisk/queues_minipbx.conf
```

Puis les fichiers principaux Asterisk incluront ces fichiers.

Exemple :

```ini
; pjsip.conf
#include pjsip_minipbx.conf
```

```ini
; extensions.conf
#include extensions_minipbx.conf
```

Cela permet de ne pas écraser toute la configuration Asterisk et de garder une séparation claire.

---

# 9. Règles de sécurité

## 9.1 Interface web

* accès admin protégé par mot de passe ;
* mot de passe hashé ;
* session sécurisée ;
* pas d’accès public recommandé ;
* restriction IP optionnelle ;
* logs d’administration.

## 9.2 SIP

* mots de passe SIP générés automatiquement ;
* longueur minimale élevée ;
* interdiction des mots de passe faibles ;
* appels internationaux désactivés par défaut ;
* limitation des destinations sortantes ;
* fail2ban recommandé ;
* pare-feu obligatoire ;
* plage RTP limitée ;
* trunk SIP non exposé inutilement.

## 9.3 Configuration

Avant application, MiniPBX devra :

* générer les fichiers ;
* valider les champs ;
* sauvegarder l’ancienne configuration ;
* appliquer la nouvelle configuration ;
* recharger Asterisk ;
* vérifier que le service répond encore.

---

# 10. Parcours utilisateur cible

## Installation

1. L’administrateur installe MiniPBX sur un petit serveur Debian/Ubuntu.
2. Il accède à l’interface web.
3. Il crée le compte administrateur.
4. Il configure le trunk SIP.
5. Il crée les extensions.
6. Il définit les appels entrants.
7. Il applique la configuration.
8. Il configure les téléphones IP avec les identifiants affichés.

## Utilisation quotidienne

L’administrateur doit pouvoir :

* ajouter un salarié ;
* supprimer une extension ;
* changer le mot de passe SIP ;
* consulter les appels ;
* changer les horaires ;
* changer le message d’accueil ;
* sauvegarder la configuration.

---

# 11. Découpage de développement avec Codex

## Phase 1 — Squelette projet

Objectif : créer la base applicative.

À faire :

* projet FastAPI ;
* SQLite ;
* migrations ;
* authentification admin ;
* layout HTML ;
* page tableau de bord ;
* structure de tests.

Prompt Codex possible :

```text
Crée un projet Python FastAPI appelé minipbx.

Contraintes :
- FastAPI
- SQLite
- SQLAlchemy
- Alembic
- Jinja2 templates
- HTMX pour les interactions simples
- authentification admin par session
- pytest
- structure claire app/, tests/, templates/, static/

Génère le squelette complet avec un README d’installation.
```

---

## Phase 2 — Gestion des extensions

Objectif : CRUD extensions.

À faire :

* modèle `Extension` ;
* page liste ;
* formulaire création ;
* formulaire édition ;
* suppression ;
* génération mot de passe SIP ;
* validation des numéros.

Prompt Codex :

```text
Ajoute la gestion des extensions au projet MiniPBX.

Fonctionnalités :
- lister les extensions
- créer une extension
- modifier une extension
- supprimer une extension
- générer automatiquement un mot de passe SIP fort
- valider que le numéro d’extension est unique
- accepter uniquement des extensions numériques de 2 à 6 chiffres

Ajoute les tests pytest correspondants.
```

---

## Phase 3 — Génération PJSIP

Objectif : générer la configuration SIP des extensions.

À faire :

* template `pjsip_minipbx.conf.j2` ;
* génération fichier ;
* preview dans l’interface ;
* sauvegarde en révision ;
* tests de génération.

Prompt Codex :

```text
Ajoute un module de génération de configuration Asterisk PJSIP.

Entrée :
- liste des extensions actives
- trunk SIP optionnel

Sortie :
- texte pjsip_minipbx.conf généré depuis un template Jinja2

Contraintes :
- ne pas écrire directement dans /etc/asterisk pendant les tests
- écrire dans un répertoire configurable
- ajouter des tests unitaires sur le rendu
- ne jamais afficher les secrets en clair dans les logs
```

---

## Phase 4 — Dialplan appels internes/sortants

Objectif : générer `extensions_minipbx.conf`.

À faire :

* appels internes ;
* appels sortants via trunk ;
* blocage international par défaut ;
* numéros spéciaux internes ;
* messagerie vocale.

Prompt Codex :

```text
Ajoute un générateur de dialplan Asterisk pour MiniPBX.

Fonctions nécessaires :
- appels internes entre extensions
- appels sortants via trunk SIP
- blocage des appels internationaux par défaut
- numéro *97 pour accéder à la messagerie vocale
- fallback vers messagerie si extension indisponible

Le générateur doit produire extensions_minipbx.conf via Jinja2.
Ajoute des tests unitaires.
```

---

## Phase 5 — Trunk SIP

Objectif : configurer un trunk opérateur.

À faire :

* écran trunk ;
* modèle `SipTrunk` ;
* stockage sécurisé du secret ;
* génération PJSIP trunk ;
* état du trunk via commande Asterisk.

Prompt Codex :

```text
Ajoute la gestion d’un trunk SIP principal.

Fonctionnalités :
- formulaire de configuration
- host
- username
- password
- from_user
- from_domain
- transport UDP par défaut
- activation/désactivation
- génération de configuration PJSIP
- masquage du mot de passe dans l’interface après sauvegarde

Ajoute les tests.
```

---

## Phase 6 — Routage entrant et groupes

Objectif : acheminer les appels entrants.

À faire :

* groupes d’appel ;
* destination entrante ;
* fallback ;
* horaires simples.

Prompt Codex :

```text
Ajoute les groupes d’appel et le routage entrant.

Fonctionnalités :
- créer un groupe d’appel
- ajouter des extensions membres
- définir un timeout
- définir une destination de secours
- créer une route entrante vers extension, groupe ou voicemail
- générer le dialplan correspondant

Ajoute les tests de rendu du dialplan.
```

---

## Phase 7 — CDR / journal d’appels

Objectif : lire et afficher les appels.

À faire :

* connexion aux CDR ;
* liste des appels ;
* filtres ;
* export CSV.

Prompt Codex :

```text
Ajoute une page journal d’appels.

Fonctionnalités :
- lire les CDR Asterisk depuis une base SQLite ou CSV configurable
- afficher date, source, destination, statut, durée, billsec
- filtrer par date
- filtrer par extension
- export CSV

Ajoute des tests sur le parsing et les filtres.
```

---

## Phase 8 — Application de configuration

Objectif : appliquer proprement la configuration.

À faire :

* bouton “Prévisualiser” ;
* bouton “Appliquer” ;
* sauvegarde ancienne config ;
* écriture atomique ;
* reload Asterisk ;
* vérification de statut.

Prompt Codex :

```text
Ajoute un service d’application de configuration.

Étapes :
1. générer tous les fichiers dans un répertoire temporaire
2. valider que les fichiers ne sont pas vides
3. sauvegarder les anciens fichiers
4. copier les nouveaux fichiers vers le répertoire Asterisk configuré
5. exécuter une commande reload configurable
6. enregistrer une config_revision

Contraintes :
- mode dry-run
- pas de sudo hardcodé
- toutes les commandes système doivent être configurables
- tests avec mocks
```

---

# 12. Critères d’acceptation MVP

Le MVP sera considéré comme fonctionnel si :

* un admin peut se connecter ;
* il peut créer 3 extensions ;
* les téléphones SIP peuvent s’enregistrer ;
* les extensions peuvent s’appeler entre elles ;
* un trunk SIP peut être configuré ;
* un appel sortant fonctionne ;
* un appel entrant peut sonner sur un groupe ;
* hors horaires, l’appel va vers la messagerie ;
* les appels apparaissent dans le journal ;
* la configuration peut être sauvegardée ;
* la configuration peut être restaurée ;
* l’application peut générer les fichiers Asterisk sans intervention manuelle.

---

# 13. Première version du backlog

## Priorité 1

* Squelette FastAPI
* Authentification admin
* CRUD extensions
* Génération PJSIP extensions
* Génération dialplan appels internes
* Application de configuration

## Priorité 2

* Trunk SIP
* Appels sortants
* Appels entrants
* Groupes d’appel
* Messagerie vocale

## Priorité 3

* Horaires
* Journal d’appels
* Export CSV
* Sauvegarde/restauration

## Priorité 4

* Interface plus jolie
* Assistant d’installation
* Test de trunk
* État Asterisk dans le dashboard
* Documentation utilisateur

---

# 14. Décision technique importante

Je recommande cette ligne directrice :

> **MiniPBX ne modifie jamais Asterisk directement à la main. Il génère des fichiers dédiés, sauvegarde l’existant, puis recharge Asterisk proprement.**

Cela évite les effets de bord, rend le système testable, et permet de revenir en arrière facilement.

# Ajout au cahier des charges : installation simplifiée

## Objectif d’installation

L’installation cible doit ressembler à ceci :

```bash
git clone https://github.com/mon-org/minipbx.git
cd minipbx
cp .env.example .env
./install.sh
docker compose up -d
```

Puis accès à l’interface :

```text
http://IP_DU_SERVEUR:8080
```

Le premier lancement doit afficher un assistant :

1. création du compte administrateur ;
2. détection ou saisie de l’adresse IP du serveur ;
3. configuration du réseau local ;
4. choix du pays ;
5. création des premières extensions ;
6. configuration du trunk SIP ;
7. test d’appel interne ;
8. test d’appel sortant ;
9. test d’appel entrant.

---

# Décision technique recommandée

Je propose de prévoir **deux modes Docker**.

## Mode 1 — Docker “appliance”, recommandé

Un conteneur principal contient :

* Asterisk ;
* l’application web MiniPBX ;
* SQLite ;
* les templates de configuration ;
* les scripts de reload ;
* les sauvegardes.

Avantages :

* installation très simple ;
* pas de communication compliquée entre conteneurs ;
* l’application peut lancer directement les commandes Asterisk ;
* idéal pour une TPE de moins de 10 utilisateurs.

Inconvénient :

* moins “pur Docker” qu’une architecture multi-conteneurs ;
* un seul conteneur porte plusieurs responsabilités.

Pour notre cas, c’est acceptable, parce que la priorité est la simplicité.

---

## Mode 2 — Docker Compose multi-conteneurs, optionnel

Architecture plus propre :

```text
+-------------------------+
| minipbx-web             |
| FastAPI + interface     |
+------------+------------+
             |
             | volume partagé / AMI
             |
+------------v------------+
| minipbx-asterisk        |
| Asterisk + PJSIP + RTP  |
+-------------------------+
```

Services :

* `minipbx-web` ;
* `minipbx-asterisk` ;
* éventuellement `minipbx-backup`.

Ce mode pourra être ajouté plus tard, mais je ne le mettrais pas comme priorité MVP.

---

# Point important : Docker et SIP/RTP

Le SIP dans Docker peut vite devenir pénible à cause du NAT, du RTP et des plages de ports audio. Pour éviter ça, le mode recommandé sur Linux sera :

```yaml
network_mode: host
```

Avec le mode réseau `host`, le conteneur partage la pile réseau de l’hôte, et les mappings `ports:` sont ignorés par Docker. C’est justement utile lorsqu’un service doit manipuler une grande plage de ports, comme c’est le cas pour RTP. ([Docker Documentation][1])

Pour Asterisk derrière NAT, la documentation Asterisk montre typiquement le besoin d’acheminer le trafic SIP et RTP, par exemple SIP sur `5060` et RTP sur une plage comme `10000-20000`. ([Documentation Asterisk][2])
Le fichier d’exemple `rtp.conf` d’Asterisk expose aussi les paramètres `rtpstart` et `rtpend`, ce qui confirme qu’on doit rendre cette plage configurable dans MiniPBX. ([GitHub][3])

---

# Nouvelle exigence : profils réseau

## Profil recommandé : `host`

Pour une installation sur un petit serveur Linux local :

```yaml
services:
  minipbx:
    build: .
    container_name: minipbx
    network_mode: host
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - minipbx_data:/var/lib/minipbx
      - minipbx_asterisk_etc:/etc/asterisk
      - minipbx_asterisk_spool:/var/spool/asterisk
      - minipbx_asterisk_logs:/var/log/asterisk

volumes:
  minipbx_data:
  minipbx_asterisk_etc:
  minipbx_asterisk_spool:
  minipbx_asterisk_logs:
```

Dans ce mode, on ne publie pas les ports dans `docker-compose.yml`, puisque le conteneur utilise directement le réseau de la machine hôte.

---

## Profil alternatif : `bridge`

À prévoir pour les tests ou certains environnements Docker :

```yaml
services:
  minipbx:
    build: .
    container_name: minipbx
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "8080:8080/tcp"
      - "5060:5060/udp"
      - "10000-10100:10000-10100/udp"
    volumes:
      - minipbx_data:/var/lib/minipbx
      - minipbx_asterisk_etc:/etc/asterisk
      - minipbx_asterisk_spool:/var/spool/asterisk
      - minipbx_asterisk_logs:/var/log/asterisk
```

Docker permet bien de publier des ports TCP ou UDP, par exemple avec `/udp`, mais les ports publiés deviennent accessibles depuis l’extérieur si on ne restreint pas l’adresse d’écoute. ([Docker Documentation][4])

Le mode `bridge` sera donc utile pour le développement, mais je le déconseille comme mode par défaut pour un PBX en production.

---

# Nouveau chapitre : packaging Docker

## Image Docker

L’image devra contenir :

* Python 3.12+ ;
* FastAPI ;
* Uvicorn ;
* Asterisk ;
* SQLite ;
* les dépendances audio nécessaires ;
* les scripts MiniPBX ;
* un système de supervision simple.

Structure proposée :

```text
docker/
- Dockerfile
- entrypoint.sh
- supervisord.conf ou s6/
- asterisk/
  - pjsip.conf.base
  - extensions.conf.base
  - rtp.conf
  - voicemail.conf.base
```

Je partirais sur une image Debian slim plutôt qu’Alpine pour éviter des surprises avec Asterisk, les modules audio et les dépendances système.

---

# Variables `.env`

Le fichier `.env.example` devra être simple :

```env
MINIPBX_WEB_HOST=0.0.0.0
MINIPBX_WEB_PORT=8080
MINIPBX_SECRET_KEY=change-me

MINIPBX_TIMEZONE=Europe/Paris
MINIPBX_COUNTRY=FR

ASTERISK_SIP_PORT=5060
ASTERISK_RTP_START=10000
ASTERISK_RTP_END=10100

ASTERISK_EXTERNAL_ADDRESS=
ASTERISK_LOCAL_NET=192.168.1.0/24

MINIPBX_ADMIN_USERNAME=admin
```

Pour moins de 10 salariés, une plage RTP courte suffit généralement. Par exemple `10000-10100` donne déjà 101 ports UDP, ce qui est largement assez pour quelques appels simultanés.

---

# Assistant d’installation

L’assistant doit générer automatiquement :

* `MINIPBX_SECRET_KEY` ;
* mot de passe admin initial ;
* plage RTP ;
* configuration réseau ;
* configuration Asterisk de base ;
* fichiers inclus MiniPBX ;
* première sauvegarde.

Il doit aussi afficher les informations utiles :

```text
Interface MiniPBX :
http://192.168.1.10:8080

Ports à autoriser :
- Web admin : TCP 8080, idéalement seulement depuis le LAN
- SIP : UDP 5060
- RTP : UDP 10000-10100

Première extension suggérée :
101 - Accueil
```

---

# Règles de sécurité Docker

À ajouter au cahier des charges :

* l’interface web ne doit pas être exposée publiquement par défaut ;
* le mot de passe admin doit être créé au premier démarrage ;
* les secrets ne doivent jamais être écrits dans les logs ;
* les volumes doivent contenir les données persistantes ;
* la configuration doit survivre à une recréation du conteneur ;
* les sauvegardes doivent être exportables depuis l’interface ;
* le conteneur doit redémarrer automatiquement ;
* les ports SIP/RTP doivent être clairement documentés ;
* le mode `host` doit être recommandé uniquement sur Linux.

---

# Volumes persistants

MiniPBX devra persister :

```text
/var/lib/minipbx
- base SQLite
- fichiers uploadés
- sauvegardes
- révisions de configuration

/etc/asterisk
- configuration générée
- fichiers inclus MiniPBX

/var/spool/asterisk
- messages vocaux

/var/log/asterisk
- logs
- CDR
```

Critère d’acceptation :

> Supprimer et recréer le conteneur ne doit pas supprimer les extensions, les trunks, les messages vocaux, les journaux ou les sauvegardes.

---

# Commandes d’administration simples

On doit fournir un petit script CLI :

```bash
./minipbx status
./minipbx logs
./minipbx backup
./minipbx restore backup.tar.gz
./minipbx restart
./minipbx shell
```

Et côté Docker :

```bash
docker compose ps
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d
```

---

# Mise à jour du cahier des charges MVP

J’ajouterais cette section dans les critères d’acceptation.

## Critères d’acceptation installation

Le MVP est acceptable si :

* l’installation Docker fonctionne avec `docker compose up -d` ;
* aucune compilation manuelle n’est nécessaire côté utilisateur ;
* le premier démarrage crée un assistant de configuration ;
* les données persistent après redémarrage ;
* les données persistent après recréation du conteneur ;
* l’interface web est accessible sur le port configuré ;
* les téléphones peuvent s’enregistrer après configuration ;
* un appel interne fonctionne ;
* un appel entrant/sortant fonctionne avec le trunk ;
* une sauvegarde peut être créée depuis l’interface ;
* une sauvegarde peut être restaurée ;
* les ports nécessaires sont affichés clairement à l’utilisateur.

---

# Nouveau backlog Docker

## Phase Docker 1 — Image de base

```text
Créer une image Docker MiniPBX contenant :
- Asterisk
- Python 3.12+
- l’application FastAPI
- SQLite
- les dépendances système nécessaires
- un entrypoint de démarrage
- les volumes persistants

Le conteneur doit démarrer l’application web et Asterisk.
```

## Phase Docker 2 — Docker Compose

```text
Créer un docker-compose.yml de production simple.

Contraintes :
- mode réseau host par défaut sur Linux
- volumes persistants
- restart unless-stopped
- fichier .env
- pas de secrets hardcodés
- documentation claire
```

## Phase Docker 3 — Assistant de premier démarrage

```text
Créer un assistant de premier démarrage.

Il doit :
- détecter qu’aucun administrateur n’existe
- créer le compte admin
- demander l’adresse IP ou le domaine du serveur
- demander le réseau local
- configurer la plage RTP
- générer la configuration Asterisk initiale
- appliquer la configuration
```

## Phase Docker 4 — Sauvegarde/restauration

```text
Ajouter une fonction de sauvegarde/restauration compatible Docker.

La sauvegarde doit inclure :
- base SQLite
- configuration MiniPBX
- fichiers Asterisk générés
- messages vocaux
- fichiers audio uploadés

La restauration doit pouvoir être faite depuis l’interface ou en CLI.
```