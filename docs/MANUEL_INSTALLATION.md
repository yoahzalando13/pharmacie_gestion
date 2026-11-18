# PharmaGest — Manuel d'installation et de configuration

**Sommaire** : [1. Prérequis](#1-prérequis) · [2. Installation rapide](#2-installation-rapide-script) · [3. Installation pas à pas](#3-installation-pas-à-pas) · [4. Premier compte](#4-créer-le-premier-compte) · [5. Configuration](#5-configuration) · [6. Tests](#6-lancer-les-tests-automatisés) · [7. Sauvegarde](#7-sauvegarde-et-restauration) · [8. Production](#8-mise-en-production) · [9. Dépannage](#9-dépannage)

---

## 1. Prérequis

| Élément | Version | Vérification |
|---|---|---|
| Python | 3.12 ou plus récent (Django 6.1) | `python3 --version` (Windows : `py --version`) |
| pip | fourni avec Python | `python3 -m pip --version` |
| Connexion Internet | pour installer les paquets ; le navigateur charge aussi Bootstrap depuis un CDN | — |
| Navigateur récent | Chrome, Firefox, Edge | — |

Paquets Python installés automatiquement (`requirements.txt`) : **Django** 6.1, **Pillow** (photos des médicaments), **ReportLab** (documents PDF).

## 2. Installation rapide (script)

Placez-vous dans le dossier qui contient `manage.py`, puis :

**Linux / macOS**

```bash
./installer.sh            # installation + données de démonstration
./installer.sh --vide     # installation sans données de démonstration
```

**Windows**

```bat
installer.bat
installer.bat --vide
```

Le script crée l'environnement virtuel `.venv`, installe les dépendances, crée les tables, les 5 rôles et, sauf `--vide`, le jeu de données fictives. Passez ensuite à la section 4 si vous n'avez pas chargé les données de démonstration, sinon lancez le serveur :

```bash
source .venv/bin/activate        # Windows : .venv\Scripts\activate
python manage.py runserver
```

Ouvrez **http://127.0.0.1:8000/**.

## 3. Installation pas à pas

```bash
# 1. Se placer dans le projet (le dossier qui contient manage.py)
cd pharmacie/pharmacie

# 2. Créer et activer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate              # Windows : .venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Créer ou mettre à jour les tables (applique toutes les migrations)
python manage.py migrate

# 5. Créer les 5 rôles (groupes)
python manage.py init_roles

# 6. (Facultatif) Charger le jeu de données fictives
python manage.py donnees_demo

# 7. Vérifier puis démarrer
python manage.py check
python manage.py runserver
```

> La commande de démarrage est **`runserver`**. `python manage.py run` n'existe pas et renvoie *Unknown command: 'run'*.

### Base de données livrée

Le fichier `db.sqlite3` du projet est la base de travail. Si elle provient d'une ancienne version, l'étape 4 (`migrate`) ajoute les tables manquantes (stock, achats, ventes) **sans effacer les données existantes**. Pour repartir d'une base neuve :

```bash
python manage.py sauvegarder           # garde une copie de l'ancienne base
rm db.sqlite3                          # Windows : del db.sqlite3
python manage.py migrate
python manage.py init_roles
python manage.py donnees_demo          # ou createsuperuser, voir section 4
```

### Jeu de données fictives

`python manage.py donnees_demo` crée, sur une base vide :

- 5 comptes, un par rôle, mot de passe commun `Demo-PharmaGest-2026` :

  | Identifiant | Rôle |
  |---|---|
  | `admin_demo` | Administrateur |
  | `pharmacien` | Pharmacien responsable |
  | `stock` | Gestionnaire de stock |
  | `caissier` | Caissier |
  | `gestion` | Responsable de gestion |

- 8 médicaments dans 7 catégories, avec code-barres (`3400930000001` à `…008`) ;
- 2 fournisseurs, 2 clients ;
- 3 commandes : une reçue en totalité, une reçue partiellement, une en brouillon ;
- 13 ventes réparties sur les 20 derniers jours, en espèces, mobile money et carte, dont un paiement vérifié, deux paiements en attente, un retour remis en stock et une vente annulée ;
- un lot proche de la péremption, un lot périmé et un lot bloqué (rappel fabricant), pour voir les alertes.

La commande ne fait rien si les comptes de démonstration existent déjà. **Supprimez ou désactivez ces comptes avant une utilisation réelle.**

## 4. Créer le premier compte

Sans les données de démonstration, créez un super-administrateur :

```bash
python manage.py createsuperuser
```

Connectez-vous avec ce compte, puis menu **Utilisateurs** → **Créer un utilisateur** pour chaque employé, en cochant son ou ses rôles.

## 5. Configuration

### Variables d'environnement

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `DJANGO_SECRET_KEY` | clé de développement | Clé secrète. **Obligatoire en production**, longue chaîne aléatoire |
| `DJANGO_DEBUG` | `1` | `0` en production : désactive les pages d'erreur détaillées, active les cookies sécurisés et HSTS |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Noms de domaine ou adresses IP autorisés, séparés par des virgules |
| `DJANGO_SSL_REDIRECT` | `1` | Redirige vers HTTPS quand `DJANGO_DEBUG=0` ; mettre `0` si le HTTPS est géré par le serveur frontal |

Exemple Linux :

```bash
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
export DJANGO_DEBUG=0
export DJANGO_ALLOWED_HOSTS=pharmagest.mg,192.168.1.10
```

### Paramètres de l'officine (`pharmacie/settings.py`)

| Paramètre | Rôle |
|---|---|
| `PHARMACIE` | Nom, adresse, téléphone, NIF et STAT imprimés sur les reçus, factures, bons et rapports PDF. **À compléter.** |
| `PEREMPTION_ALERTE_JOURS` | Nombre de jours avant péremption à partir duquel un lot est signalé (90 par défaut) |
| `TIME_ZONE` | `Indian/Antananarivo` |
| `SAUVEGARDES_DIR` | Dossier des sauvegardes (`sauvegardes/`) |
| `MEDIA_ROOT` | Dossier des photos des médicaments (`media/`) |

### Utilisation sans Internet

Bootstrap et ses icônes sont chargés depuis un CDN dans `templates/base.html`. Pour un poste hors ligne, téléchargez `bootstrap.min.css`, `bootstrap.bundle.min.js` et `bootstrap-icons.min.css` (avec son dossier `fonts/`) dans `static/vendor/`, puis remplacez les trois liens `https://cdn.jsdelivr.net/...` par `{% static 'vendor/...' %}`. La police Inter (Google Fonts) est facultative : sans Internet, le navigateur utilise la police du système.

## 6. Lancer les tests automatisés

```bash
python manage.py test                  # toute la suite
python manage.py test ventes           # une seule application
python manage.py test -v 2             # affiche le nom de chaque test
```

68 tests couvrent les modèles, les formulaires (photo comprise), les permissions de chaque rôle, les calculs, les opérations de stock et les règles de gestion RG02 à RG12. Le test de deux ventes simultanées ne s'exécute que sous PostgreSQL ; il est ignoré sous SQLite.

## 7. Sauvegarde et restauration

```bash
python manage.py sauvegarder
# → sauvegardes/pharmagest_AAAAMMJJ_HHMMSS.sqlite3  (+ media_AAAAMMJJ_HHMMSS.zip pour les photos)
```

La copie est vérifiée (`PRAGMA integrity_check`). Programmez-la chaque soir, par exemple avec `cron` (Linux) :

```cron
30 20 * * *  cd /chemin/vers/pharmacie && .venv/bin/python manage.py sauvegarder
```

Restauration, **serveur arrêté** :

```bash
python manage.py restaurer sauvegardes/pharmagest_AAAAMMJJ_HHMMSS.sqlite3 --oui
```

La base actuelle est d'abord copiée dans `db_avant_restauration.sqlite3`.

## 8. Mise en production

Le serveur `runserver` sert au développement uniquement. Pour un poste serveur de l'officine (Linux) :

1. **Base PostgreSQL** (recommandée pour plusieurs caisses) : installez `psycopg[binary]`, puis remplacez `DATABASES` dans `settings.py` :

   ```python
   DATABASES = {
       "default": {
           "ENGINE": "django.db.backends.postgresql",
           "NAME": "pharmagest",
           "USER": "pharmagest",
           "PASSWORD": os.environ["DJANGO_DB_PASSWORD"],
           "HOST": "127.0.0.1",
           "PORT": "5432",
       }
   }
   ```

   puis `python manage.py migrate` et `python manage.py init_roles`.

2. **Variables d'environnement** de la section 5 (`DJANGO_DEBUG=0`, clé secrète, hôtes).
3. **Fichiers statiques** : `python manage.py collectstatic` (copie dans `staticfiles/`).
4. **Serveur d'application** : `pip install gunicorn`, puis `gunicorn pharmacie.wsgi:application --bind 127.0.0.1:8000 --workers 3`.
5. **Serveur frontal** (Nginx) : HTTPS, `location /static/` → `staticfiles/`, `location /media/` → `media/`, le reste vers Gunicorn.
6. **Sauvegardes** : avec PostgreSQL, remplacez `manage.py sauvegarder` par `pg_dump` et copiez aussi le dossier `media/`.
7. **Vérification** : `python manage.py check --deploy`.

## 9. Dépannage

| Message | Cause | Solution |
|---|---|---|
| `Unknown command: 'run'` | Commande mal tapée | `python manage.py runserver` |
| `ModuleNotFoundError: No module named 'django'` (ou `reportlab`, `PIL`) | Environnement virtuel non activé ou dépendances absentes | `source .venv/bin/activate` puis `pip install -r requirements.txt` |
| `no such table: achats_commandeachat` (ou `stock_…`, `ventes_…`) | Migrations non appliquées | `python manage.py migrate` |
| « Accès interdit » pour tout compte sauf le super-administrateur | Rôles non créés ou non attribués | `python manage.py init_roles`, puis cocher les rôles dans **Utilisateurs** |
| Pages sans mise en forme | Pas d'accès à Internet (CDN) | Voir *Utilisation sans Internet* |
| Les photos ne s'affichent pas en production | `DEBUG=0` : Django ne sert plus `media/` | Configurer `location /media/` dans Nginx |
| `CSRF verification failed` en production | Nom de domaine absent ou HTTPS mal configuré | Compléter `DJANGO_ALLOWED_HOSTS`, vérifier le HTTPS ; en local, laisser `DJANGO_DEBUG=1` |
| `database is locked` (SQLite) | Plusieurs postes écrivent en même temps | Passer à PostgreSQL |
| Port 8000 déjà utilisé | Un autre serveur tourne | `python manage.py runserver 8001` |
