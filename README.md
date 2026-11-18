# PharmaGest — Application web de gestion de pharmacie (Django)

> Liste des livrables : [LIVRABLES.md](LIVRABLES.md) · Installation détaillée : [docs/MANUEL_INSTALLATION.md](docs/MANUEL_INSTALLATION.md) · Utilisation : [docs/GUIDE_UTILISATION.md](docs/GUIDE_UTILISATION.md) · Conception : [docs/DOSSIER_CONCEPTION.md](docs/DOSSIER_CONCEPTION.md)
>
> Installation automatique : `./installer.sh` (Linux / macOS) ou `installer.bat` (Windows).

## 1. Installation (Linux)

```bash
cd pharmacie/pharmacie            # le dossier qui contient manage.py
source ../venv/bin/activate       # votre environnement virtuel existant
pip install -r requirements.txt   # ajoute ReportLab (PDF), absent de votre venv

python manage.py migrate          # crée les tables Stock, Achats et Ventes
python manage.py init_roles       # crée les 5 rôles (groupes)
python manage.py runserver
```

Ouvrez http://127.0.0.1:8000/ puis connectez-vous.

### Données de démonstration (facultatif)

Sur une base **vide ou de test** :

```bash
python manage.py donnees_demo
```

La commande crée 5 comptes (`admin_demo`, `pharmacien`, `stock`, `caissier`, `gestion`,
mot de passe `Demo-PharmaGest-2026`), 8 médicaments, 2 fournisseurs, 2 clients,
3 commandes (reçue, partielle, brouillon), 13 ventes sur 20 jours avec un retour et une annulation,
un lot périmé, un lot proche de la péremption et un lot bloqué. Supprimez ces comptes avant
toute utilisation réelle.

### Donner un rôle à votre compte existant

Votre superutilisateur a déjà accès à tout. Pour un autre compte :
menu **Utilisateurs** → **Modifier** → cochez le ou les rôles.

## 2. Tests automatisés

```bash
python manage.py test
```

68 tests couvrent les modèles, formulaires, permissions, calculs et opérations de stock,
dont les scénarios du §9 du cahier des charges.

## 3. Sauvegarde et restauration

```bash
python manage.py sauvegarder
# → sauvegardes/pharmagest_AAAAMMJJ_HHMMSS.sqlite3 (+ media_….zip pour les photos)

# Restauration : arrêtez d'abord le serveur
python manage.py restaurer sauvegardes/pharmagest_AAAAMMJJ_HHMMSS.sqlite3 --oui
```

La sauvegarde est vérifiée (`PRAGMA integrity_check`). Avant de restaurer, la base actuelle
est conservée dans `db_avant_restauration.sqlite3`.

## 4. Mise en production

Variables d'environnement à définir :

| Variable | Exemple | Rôle |
|---|---|---|
| `DJANGO_SECRET_KEY` | longue chaîne aléatoire | Clé secrète (jamais dans le code) |
| `DJANGO_DEBUG` | `0` | Désactive le mode debug et active les cookies sécurisés / HTTPS |
| `DJANGO_ALLOWED_HOSTS` | `pharmagest.mg` | Noms de domaine autorisés |

Puis `python manage.py collectstatic`. Base recommandée : PostgreSQL.
Les informations imprimées sur les PDF (nom, adresse, NIF, STAT) se règlent dans
`PHARMACIE` à la fin de `pharmacie/settings.py`.

## 5. Guide d'utilisation rapide

| Rôle | Ce qu'il fait |
|---|---|
| Administrateur | Tout, plus la gestion des comptes et le journal d'audit |
| Pharmacien responsable | Médicaments, lots (blocage), achats, caisse, annulations, rapports |
| Gestionnaire de stock | Fournisseurs, commandes, réceptions, corrections, inventaire |
| Caissier | Caisse, reçus, retours, vérification des paiements mobile money |
| Responsable de gestion | Consultation : tableau de bord, ventes, achats, rapports |

**Approvisionner** — Achats → Nouvelle commande → ajouter les médicaments → *Valider la commande*
→ *Réceptionner* en saisissant les quantités reçues, le n° de lot et la date de péremption.
Le stock n'augmente qu'à la réception.

**Vendre** — Ventes → Caisse → rechercher ou scanner le code-barres → ajuster les quantités
(le lot est choisi automatiquement en FEFO, ou manuellement) → mode de paiement → *Confirmer
la vente* → imprimer le reçu. Un paiement mobile money reste « en attente » jusqu'à ce qu'il soit
vérifié depuis la fiche de la vente.

**Retour / annulation** — fiche de la vente → *Retour produit* (partiel, avec ou sans remise en
stock) ou *Annuler la vente* (pharmacien). La vente d'origine n'est jamais supprimée.

**Stock** — État du stock, Alertes (ruptures, seuil, péremptions), Mouvements, Inventaire
physique. Un lot périmé ou bloqué n'est jamais proposé à la vente.

**Rapports** — choisir la période puis télécharger les PDF (ventes, achats, stock, péremptions).
